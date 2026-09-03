#!/usr/bin/env python3
"""Save sparse RGB-D keyframes from ROS 2 without retaining all frames."""
from __future__ import annotations
import argparse, json, math, os, tempfile, time, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

def atomic_json(path: Path, value: dict) -> None:
    fd, temporary = tempfile.mkstemp(prefix="live-status-", suffix=".json", dir=path.parent); os.close(fd)
    Path(temporary).write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)

def quaternion_matrix(x, y, z, w):
    return __import__("numpy").array([
        [1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
        [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
        [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)],
    ], dtype=float)

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path); parser.add_argument("--status", required=True, type=Path)
    parser.add_argument("--max-rate-hz", type=float, default=1.0); parser.add_argument("--min-translation-m", type=float, default=0.35); parser.add_argument("--min-rotation-deg", type=float, default=15.0)
    parser.add_argument("--semantic-backend", default="none", choices=("none", "fixture", "sam2", "sam2_florence_siglip")); parser.add_argument("--semantic-fixture", type=Path)
    parser.add_argument("--mask-model-id", default="facebook/sam-vit-base"); parser.add_argument("--label-model-id", default="Salesforce/blip-image-captioning-base"); parser.add_argument("--semantic-device", type=int, default=-1)
    args = parser.parse_args(); args.output_dir.mkdir(parents=True, exist_ok=True); args.status.parent.mkdir(parents=True, exist_ok=True)
    try:
        import cv2, numpy as np, rclpy
        from cv_bridge import CvBridge
        from message_filters import ApproximateTimeSynchronizer, Subscriber
        from rclpy.node import Node
        from sensor_msgs.msg import CameraInfo, Image
        from tf2_ros import Buffer, TransformListener
        from rclpy.duration import Duration
    except Exception as exc:
        atomic_json(args.status, {"status": "unavailable", "error": f"{type(exc).__name__}: {exc}"}); return 2
    class Bridge(Node):
        def __init__(self):
            super().__init__("sparseworld_live_keyframes"); self.bridge=CvBridge(); self.last=None; self.accepted=0; self.rejected=0
            self.semantic = None; self.semantic_worker = None; self.semantic_error = None
            if args.semantic_backend != "none":
                try:
                    from sparseworld_p0.semantic_backends import load_backend
                    from sparseworld_p0.live_semantic_worker import LiveSemanticProcessor
                    from sparseworld_p0.live_mapping import LiveSemanticWorker
                    config = {"mask_model_id": args.mask_model_id, "label_model_id": args.label_model_id, "device": args.semantic_device}
                    if args.semantic_fixture: config["fixture_path"] = str(args.semantic_fixture)
                    self.semantic = LiveSemanticProcessor(load_backend(args.semantic_backend, config), output_dir=args.output_dir)
                    self.semantic_worker = LiveSemanticWorker(lambda frame: self.semantic.process(**frame))
                    self.semantic_worker.start()
                except Exception as exc:
                    self.semantic_error = f"{type(exc).__name__}: {exc}"
            self.tf_buffer = Buffer(); self.tf_listener = TransformListener(self.tf_buffer, self)
            sync=ApproximateTimeSynchronizer([Subscriber(self,Image,"/camera/color/image_raw"),Subscriber(self,Image,"/camera/depth/image_raw"),Subscriber(self,CameraInfo,"/camera/color/camera_info")], 5, .08)
            sync.registerCallback(self.callback); self.write_status("waiting_for_rgbd")
            self.create_timer(1.0, self.persist_semantics)
        def write_status(self, state):
            payload={"status":state,"accepted":self.accepted,"rejected":self.rejected,"policy":{"max_rate_hz":args.max_rate_hz,"min_translation_m":args.min_translation_m,"min_rotation_deg":args.min_rotation_deg,"queue_capacity":1},"global_accuracy":"unvalidated","semantic_backend":args.semantic_backend}
            if self.semantic: payload["semantic_worker"] = {**self.semantic.snapshot(), **({"queue_dropped": self.semantic_worker.snapshot()["dropped"]} if self.semantic_worker else {})}
            elif self.semantic_error: payload["semantic_worker"] = {"status":"unavailable","error":self.semantic_error,"global_accuracy":"unvalidated"}
            else: payload["semantic_worker"] = {"status":"disabled","global_accuracy":"unvalidated"}
            atomic_json(args.status,payload)
        def persist_semantics(self):
            if self.semantic:
                self.semantic.persist(); self.write_status("running")
        def callback(self,rgb,depth,info):
            now=rgb.header.stamp.sec+rgb.header.stamp.nanosec/1e9
            if self.last is not None and now-self.last < 1.0/args.max_rate_hz:
                self.rejected+=1; self.write_status("running"); return
            try:
                color=self.bridge.imgmsg_to_cv2(rgb,"bgr8"); depth_image=self.bridge.imgmsg_to_cv2(depth,"passthrough")
                index=self.accepted; stem=f"kf-{index:06d}"; cv2.imwrite(str(args.output_dir/(stem+".jpg")),color)
                np.save(args.output_dir/(stem+"-depth.npy"),depth_image)
                (args.output_dir/(stem+".json")).write_text(json.dumps({"keyframe_id":stem,"timestamp_s":now,"intrinsics":{"fx":info.k[0],"fy":info.k[4],"cx":info.k[2],"cy":info.k[5]},"global_accuracy":"unvalidated","source":"live_keyframe_gate"},sort_keys=True)+"\n")
                self.accepted+=1; self.last=now
                if self.semantic:
                    pose = None
                    for frame in ("camera_link", "camera_color_optical_frame", rgb.header.frame_id):
                        if not frame: continue
                        try:
                            transform = self.tf_buffer.lookup_transform("map", frame, rclpy.time.Time.from_msg(rgb.header.stamp), timeout=Duration(seconds=0.02))
                            t, q = transform.transform.translation, transform.transform.rotation
                            matrix = np.eye(4); matrix[:3,:3] = quaternion_matrix(q.x,q.y,q.z,q.w); matrix[:3,3] = [t.x,t.y,t.z]; pose = matrix; break
                        except Exception: pass
                    self.semantic_worker.submit({"keyframe_id": stem, "timestamp": f"{now:.9f}", "rgb": cv2.cvtColor(color, cv2.COLOR_BGR2RGB), "depth": depth_image, "intrinsics": {"fx":info.k[0],"fy":info.k[4],"cx":info.k[2],"cy":info.k[5],"depth_unit_m":0.001}, "map_T_camera": pose})
                self.write_status("running")
            except Exception as exc:
                self.get_logger().warning(f"keyframe rejected: {exc}"); self.rejected+=1; self.write_status("error")
    rclpy.init(); node=Bridge()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally:
        if getattr(node, "semantic_worker", None):
            node.semantic_worker.stop()
            node.semantic.persist()
        node.destroy_node()
        if rclpy.ok(): rclpy.shutdown()
    return 0
if __name__ == "__main__": raise SystemExit(main())
