#!/usr/bin/env python3
"""Local, network-independent Isaac Sim 6 semantic-navigation smoke test.

The scene is created procedurally, so this test does not require Nucleus or
downloaded USD assets. A small kinematic differential-drive base is controlled
through ROS 2 ``/cmd_vel`` and emits the same sensor contracts consumed by the
prototype. This is simulation evidence, not a real-base safety result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path

# Isaac Sim 6 runs Python 3.12.  Never import the system ROS 2 Python 3.10
# modules into this process: use the matching Humble bindings bundled with Sim.
ISAAC_ROS = "/home/ubuntu/linalw/App/isaacsim/_build/linux-x86_64/release/exts/isaacsim.ros2.core/humble"
if os.path.isdir(f"{ISAAC_ROS}/rclpy"):
    sys.path.insert(0, f"{ISAAC_ROS}/rclpy")
    os.environ["PYTHONPATH"] = f"{ISAAC_ROS}/rclpy" + (":" + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "")
    ros_libs = f"{ISAAC_ROS}/lib:/opt/ros/humble/lib:/opt/ros/humble/lib/x86_64-linux-gnu"
    os.environ["LD_LIBRARY_PATH"] = ros_libs + (":" + os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else "")
    os.environ.setdefault("AMENT_PREFIX_PATH", "/opt/ros/humble")
    os.environ.setdefault("RMW_IMPLEMENTATION", "rmw_fastrtps_cpp")
    os.environ.setdefault("ROS_DISTRO", "humble")

from isaacsim import SimulationApp

parser = argparse.ArgumentParser()
parser.add_argument("--duration-s", type=float, default=12.0)
parser.add_argument("--output", type=Path, required=True)
args, _ = parser.parse_known_args()
if args.duration_s <= 0 or not math.isfinite(args.duration_s):
    raise ValueError("--duration-s must be positive and finite")

app = SimulationApp({"headless": True, "renderer": "RayTracedLighting"})
print("sparseworld: Isaac Sim started", flush=True)


def _set_cube(stage, path: str, position: tuple[float, float, float], size: tuple[float, float, float], color=None):
    from pxr import Gf, UsdGeom

    cube = UsdGeom.Cube.Define(stage, path)
    api = UsdGeom.XformCommonAPI(cube)
    api.SetTranslate(Gf.Vec3d(*position))
    api.SetScale(Gf.Vec3f(size[0] / 2.0, size[1] / 2.0, size[2] / 2.0))
    if color is not None:
        cube.GetDisplayColorAttr().Set([Gf.Vec3f(*color)])
    return cube


def _sim_time(sec: float):
    from builtin_interfaces.msg import Time

    whole = int(sec)
    return Time(sec=whole, nanosec=int(round((sec - whole) * 1_000_000_000)))


def _yaw_quaternion(yaw: float):
    from geometry_msgs.msg import Quaternion

    return Quaternion(z=math.sin(yaw / 2.0), w=math.cos(yaw / 2.0))


try:
    import numpy as np
    import carb
    import isaacsim.core.experimental.utils.app as app_utils
    import isaacsim.core.experimental.utils.stage as stage_utils
    import omni
    import omni.graph.core as og
    import usdrt.Sdf
    from isaacsim.sensors.camera import Camera
    from isaacsim.core.simulation_manager import SimulationManager

    app_utils.enable_extension("isaacsim.ros2.bridge")
    app.update()
    print("sparseworld: ROS 2 bridge enabled", flush=True)
    carb.settings.get_settings().set_bool("/exts/isaacsim.ros2.bridge/publish_without_verification", True)
    stage_utils.set_stage_units(meters_per_unit=1.0)
    stage = omni.usd.get_context().get_stage()

    # Procedural indoor scene: walls/obstacle plus a labelled target object.
    _set_cube(stage, "/World/Ground", (2.5, 0.0, -0.05), (8.0, 6.0, 0.1), (0.25, 0.25, 0.25))
    _set_cube(stage, "/World/WallLeft", (2.5, 2.8, 1.0), (8.0, 0.2, 2.0), (0.55, 0.55, 0.55))
    _set_cube(stage, "/World/WallRight", (2.5, -2.8, 1.0), (8.0, 0.2, 2.0), (0.55, 0.55, 0.55))
    _set_cube(stage, "/World/Obstacle", (2.0, 0.0, 0.45), (0.8, 1.0, 0.9), (0.7, 0.2, 0.1))
    target = _set_cube(stage, "/World/SemanticTarget", (3.7, 0.0, 0.35), (0.45, 0.45, 0.7), (0.1, 0.8, 0.2))
    target.GetPrim().CreateAttribute("semantic:class", __import__("pxr").Sdf.ValueTypeNames.String).Set("target_object")
    _set_cube(stage, "/World/Robot/Base", (0.0, 0.0, 0.2), (0.45, 0.36, 0.4), (0.1, 0.3, 0.9))
    camera = Camera(prim_path="/World/Robot/Camera", position=np.array([0.0, 0.0, 1.0]), frequency=15, resolution=(320, 240))
    camera.initialize()
    app.update()
    print("sparseworld: camera initialized", flush=True)

    # Camera RGB/depth/camera_info ROS graph.
    graph_path = "/World/Robot/CameraROS"
    keys = og.Controller.Keys
    graph, _, _, _ = og.Controller.edit(
        {"graph_path": graph_path, "evaluator_name": "push", "pipeline_stage": og.GraphPipelineStage.GRAPH_PIPELINE_STAGE_ONDEMAND},
        {
            keys.CREATE_NODES: [
                ("OnTick", "omni.graph.action.OnTick"),
                ("CreateRenderProduct", "isaacsim.core.nodes.IsaacCreateRenderProduct"),
                ("RGB", "isaacsim.ros2.bridge.ROS2CameraHelper"),
                ("Depth", "isaacsim.ros2.bridge.ROS2CameraHelper"),
                ("Info", "isaacsim.ros2.bridge.ROS2CameraInfoHelper"),
            ],
            keys.CONNECT: [
                ("OnTick.outputs:tick", "CreateRenderProduct.inputs:execIn"),
                ("CreateRenderProduct.outputs:execOut", "RGB.inputs:execIn"),
                ("CreateRenderProduct.outputs:execOut", "Depth.inputs:execIn"),
                ("CreateRenderProduct.outputs:execOut", "Info.inputs:execIn"),
                ("CreateRenderProduct.outputs:renderProductPath", "RGB.inputs:renderProductPath"),
                ("CreateRenderProduct.outputs:renderProductPath", "Depth.inputs:renderProductPath"),
                ("CreateRenderProduct.outputs:renderProductPath", "Info.inputs:renderProductPath"),
            ],
            keys.SET_VALUES: [
                ("CreateRenderProduct.inputs:cameraPrim", [usdrt.Sdf.Path("/World/Robot/Camera")]),
                ("CreateRenderProduct.inputs:width", 320),
                ("CreateRenderProduct.inputs:height", 240),
                ("RGB.inputs:frameId", "camera_link"),
                ("RGB.inputs:topicName", "/sim/camera/rgb"),
                ("RGB.inputs:type", "rgb"),
                ("Depth.inputs:frameId", "camera_link"),
                ("Depth.inputs:topicName", "/sim/camera/depth"),
                ("Depth.inputs:type", "depth"),
                ("Info.inputs:frameId", "camera_link"),
                ("Info.inputs:topicName", "/sim/camera/camera_info"),
            ],
        },
    )
    og.Controller.evaluate_sync(graph)
    print("sparseworld: camera ROS graph created", flush=True)

    import rclpy
    print(f"sparseworld: rclpy={rclpy.__file__}", flush=True)
    from geometry_msgs.msg import TransformStamped, Twist
    from nav_msgs.msg import Odometry
    from sensor_msgs.msg import Imu
    from tf2_msgs.msg import TFMessage

    rclpy.init()
    print("sparseworld: ROS node initializing", flush=True)
    node = rclpy.create_node("sparseworld_local_isaac_nav")
    print("sparseworld: ROS node created", flush=True)
    cmd_pub = node.create_publisher(Twist, "/cmd_vel", 10)
    odom_pub = node.create_publisher(Odometry, "/sim/odom", 10)
    imu_pub = node.create_publisher(Imu, "/sim/imu", 10)
    tf_pub = node.create_publisher(TFMessage, "/tf", 10)
    command = {"linear": 0.0, "angular": 0.0}

    def on_cmd(message):
        command["linear"] = max(-0.45, min(0.45, float(message.linear.x)))
        command["angular"] = max(-1.2, min(1.2, float(message.angular.z)))

    node.create_subscription(Twist, "/cmd_vel", on_cmd, 10)
    print("sparseworld: subscriptions ready", flush=True)
    counts = {"rgb": 0, "depth": 0, "camera_info": 0, "imu": 0, "odom": 0, "tf": 0}
    for topic, module_name, class_name, key in (
        ("/sim/camera/rgb", "sensor_msgs.msg", "Image", "rgb"),
        ("/sim/camera/depth", "sensor_msgs.msg", "Image", "depth"),
        ("/sim/camera/camera_info", "sensor_msgs.msg", "CameraInfo", "camera_info"),
        ("/sim/imu", "sensor_msgs.msg", "Imu", "imu"),
        ("/sim/odom", "nav_msgs.msg", "Odometry", "odom"),
        ("/tf", "tf2_msgs.msg", "TFMessage", "tf"),
    ):
        module = __import__(module_name, fromlist=[class_name])
        cls = getattr(module, class_name)
        node.create_subscription(cls, topic, lambda _msg, observed_key=key: counts.__setitem__(observed_key, counts[observed_key] + 1), 10)

    # Planned route around the obstacle. This is an execution test, not Nav2.
    route = [(1.1, 0.0), (1.1, 1.0), (3.2, 1.0), (3.2, 0.0)]
    waypoint_index = 0
    x = y = yaw = 0.0
    elapsed = 0.0
    collision_count = 0
    trajectory = []
    app_utils.play()
    print("sparseworld: simulation loop starting", flush=True)
    SimulationManager.setup_simulation(dt=1.0 / 60.0, device="cpu")
    total_steps = int(args.duration_s * 60)
    for step in range(total_steps):
        if waypoint_index < len(route):
            gx, gy = route[waypoint_index]
            distance = math.hypot(gx - x, gy - y)
            if distance < 0.12:
                waypoint_index += 1
                linear, angular = 0.0, 0.0
            else:
                desired = math.atan2(gy - y, gx - x)
                heading = (desired - yaw + math.pi) % (2 * math.pi) - math.pi
                linear = min(0.35, 1.4 * distance) * max(0.0, math.cos(heading))
                angular = max(-1.0, min(1.0, 2.5 * heading))
        else:
            linear, angular = 0.0, 0.0
        msg = Twist(); msg.linear.x = linear; msg.angular.z = angular; cmd_pub.publish(msg)
        app.update(); rclpy.spin_once(node, timeout_sec=0.0)
        dt = 1.0 / 60.0
        yaw = (yaw + command["angular"] * dt + math.pi) % (2 * math.pi) - math.pi
        x += command["linear"] * math.cos(yaw) * dt
        y += command["linear"] * math.sin(yaw) * dt
        # Keep the generated camera aligned to the base pose.
        from pxr import Gf, UsdGeom
        UsdGeom.XformCommonAPI(stage.GetPrimAtPath("/World/Robot/Base")).SetTranslate(Gf.Vec3d(x, y, 0.2))
        UsdGeom.XformCommonAPI(stage.GetPrimAtPath("/World/Robot/Camera")).SetTranslate(Gf.Vec3d(x, y, 1.0))
        UsdGeom.XformCommonAPI(stage.GetPrimAtPath("/World/Robot/Camera")).SetRotate((0.0, 0.0, math.degrees(yaw)), UsdGeom.XformCommonAPI.RotationOrderXYZ)
        elapsed += dt
        odom = Odometry(); odom.header.stamp = _sim_time(elapsed); odom.header.frame_id = "odom"; odom.child_frame_id = "base_link"; odom.pose.pose.position.x = x; odom.pose.pose.position.y = y; odom.pose.pose.orientation = _yaw_quaternion(yaw); odom_pub.publish(odom)
        imu = Imu(); imu.header.stamp = _sim_time(elapsed); imu.header.frame_id = "imu_link"; imu.linear_acceleration.z = 9.81; imu_pub.publish(imu)
        transform = TransformStamped(); transform.header.stamp = _sim_time(elapsed); transform.header.frame_id = "odom"; transform.child_frame_id = "base_link"; transform.transform.translation.x = x; transform.transform.translation.y = y; transform.transform.rotation = _yaw_quaternion(yaw); tf_pub.publish(TFMessage(transforms=[transform]))
        trajectory.append({"t": elapsed, "x": x, "y": y, "yaw": yaw, "waypoint": waypoint_index})
    cmd_pub.publish(Twist())
    for _ in range(10): app.update(); rclpy.spin_once(node, timeout_sec=0.0)
    goal_error = math.hypot(route[-1][0] - x, route[-1][1] - y)
    result = {
        "evidence_class": "simulation_evidence",
        "status": "executed_unverified" if waypoint_index >= len(route) and goal_error < 0.15 else "failed_timeout",
        "scene": "procedural_local_indoor",
        "controller": "deterministic_waypoint_cmd_vel",
        "route": route,
        "semantic_target": {"id": "target_object", "class": "target_object", "map_xyz": [3.7, 0.0, 0.35]},
        "topic_counts": counts,
        "sensor_contract": {name: counts[name] > 0 for name in counts},
        "motion_execution": {"observed": len(trajectory) > 0, "final_pose": [x, y, yaw], "goal_error_m": goal_error, "collision_count": collision_count, "waypoints_reached": waypoint_index, "waypoints_total": len(route)},
        "navigation_acceptance": "unvalidated",
        "physical_traversability": "unvalidated",
        "notes": ["Procedural local scene; no Nucleus asset download", "Kinematic base and waypoint controller are an interface smoke test, not a dynamics or safety validation"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    args.output.write_text(payload, encoding="utf-8")
    args.output.with_suffix(args.output.suffix + ".sha256").write_text(f"{hashlib.sha256(payload.encode()).hexdigest()}  {args.output.name}\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    node.destroy_node(); rclpy.shutdown(); app_utils.stop()
finally:
    app.close()
