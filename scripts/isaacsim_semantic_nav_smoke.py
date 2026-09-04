#!/usr/bin/env python3
"""Run an auditable Isaac Sim 6 Nova Carter ROS 2 motion/sensor smoke test.

Uses NVIDIA's public warehouse navigation USD. Results remain simulation-only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from isaacsim import SimulationApp

parser = argparse.ArgumentParser()
parser.add_argument("--duration-s", type=float, default=6.0)
parser.add_argument("--linear-mps", type=float, default=0.15)
parser.add_argument("--output", type=Path, required=True)
args, _ = parser.parse_known_args()
if args.duration_s <= 0 or not math.isfinite(args.duration_s):
    raise ValueError("--duration-s must be positive and finite")
app = SimulationApp({"headless": True, "renderer": "RayTracedLighting"})

def _message_class(type_name: str):
    known = {
        "sensor_msgs/msg/Image": ("sensor_msgs.msg", "Image"),
        "sensor_msgs/msg/CameraInfo": ("sensor_msgs.msg", "CameraInfo"),
        "sensor_msgs/msg/Imu": ("sensor_msgs.msg", "Imu"),
        "nav_msgs/msg/Odometry": ("nav_msgs.msg", "Odometry"),
        "tf2_msgs/msg/TFMessage": ("tf2_msgs.msg", "TFMessage"),
    }
    pair = known.get(type_name)
    if pair is None:
        return None
    module = __import__(pair[0], fromlist=[pair[1]])
    return getattr(module, pair[1])

def _kind(topic: str, type_name: str):
    lower = topic.lower()
    if type_name == "sensor_msgs/msg/CameraInfo": return "camera_info"
    if type_name == "sensor_msgs/msg/Imu": return "imu"
    if type_name == "nav_msgs/msg/Odometry": return "odom"
    if type_name == "tf2_msgs/msg/TFMessage": return "tf"
    if type_name == "sensor_msgs/msg/Image": return "depth" if "depth" in lower else "rgb"
    return None

try:
    import carb
    import isaacsim.core.experimental.utils.app as app_utils
    import isaacsim.core.experimental.utils.stage as stage_utils
    import omni
    import omni.graph.core as og
    from isaacsim.core.simulation_manager import SimulationManager
    from isaacsim.storage.native import get_assets_root_path
    app_utils.enable_extension("isaacsim.ros2.bridge")
    app.update()
    carb.settings.get_settings().set_bool("/exts/isaacsim.ros2.bridge/publish_without_verification", True)
    assets_root = get_assets_root_path()
    if assets_root is None: raise RuntimeError("Isaac Sim assets root unavailable")
    scene_name = "carter_warehouse_navigation.usd"
    omni.usd.get_context().open_stage(assets_root + "/Isaac/Samples/ROS2/Scenario/" + scene_name, None)
    app.update(); app.update()
    while stage_utils.is_stage_loading(): app.update()
    SimulationManager.setup_simulation(dt=1.0 / 60.0, device="cpu")
    camera_graph = "/World/Nova_Carter_ROS/front_hawk"
    for name in ("left_camera_render_product", "right_camera_render_product"):
        attr = og.Controller.attribute(f"{camera_graph}/{name}.inputs:enabled")
        if attr.is_valid(): attr.set(True)
    import rclpy
    from geometry_msgs.msg import Twist
    rclpy.init()
    node = rclpy.create_node("sparseworld_isaac_smoke")
    publisher = node.create_publisher(Twist, "cmd_vel", 10)
    app_utils.play(); app.update()
    for _ in range(90): app.update(); rclpy.spin_once(node, timeout_sec=0.0)
    topic_counts = {key: 0 for key in ("rgb", "depth", "camera_info", "imu", "odom", "tf")}
    odom_positions = []
    subscriptions = []
    for topic, types in node.get_topic_names_and_types():
        for type_name in types:
            kind, message_type = _kind(topic, type_name), _message_class(type_name)
            if kind is None or message_type is None: continue
            def callback(message, observed_kind=kind):
                topic_counts[observed_kind] += 1
                if observed_kind == "odom": odom_positions.append((message.pose.pose.position.x, message.pose.pose.position.y))
            subscriptions.append(node.create_subscription(message_type, topic, callback, 10))
            break
    for _ in range(int(args.duration_s * 60)):
        cmd = Twist(); cmd.linear.x = args.linear_mps; publisher.publish(cmd)
        app.update(); rclpy.spin_once(node, timeout_sec=0.0)
    publisher.publish(Twist())
    for _ in range(10): app.update(); rclpy.spin_once(node, timeout_sec=0.0)
    measured_distance = math.dist(odom_positions[0], odom_positions[-1]) if len(odom_positions) >= 2 else 0.0
    contract = {name: count > 0 for name, count in topic_counts.items()}
    motion_observed = topic_counts["odom"] > 0 and measured_distance > 1e-4
    commanded = args.duration_s * args.linear_mps
    result = {"evidence_class":"simulation_evidence", "status":"executed_unverified" if all(contract.values()) and motion_observed else "incomplete_sensor_contract", "scene":scene_name, "duration_s":args.duration_s, "topic_counts":topic_counts, "sensor_contract":contract, "motion_execution":{"observed":motion_observed,"commanded_distance_m":commanded,"measured_distance_m":measured_distance,"distance_error_m":abs(commanded-measured_distance)}, "navigation_acceptance":"unvalidated", "physical_traversability":"unvalidated", "notes":["Official Isaac Sim Nova Carter sample", "No Nav2 goal or collision/safety acceptance inferred"]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    args.output.write_text(payload, encoding="utf-8")
    args.output.with_suffix(args.output.suffix + ".sha256").write_text(f"{hashlib.sha256(payload.encode()).hexdigest()}  {args.output.name}\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    node.destroy_node(); rclpy.shutdown(); app_utils.stop()
finally:
    app.close()
