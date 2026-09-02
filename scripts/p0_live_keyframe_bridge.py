#!/usr/bin/env python3
"""Save sparse RGB-D keyframes from ROS 2 without retaining all frames."""
from __future__ import annotations
import argparse, json, math, os, tempfile, time
from pathlib import Path

def atomic_json(path: Path, value: dict) -> None:
    fd, temporary = tempfile.mkstemp(prefix="live-status-", suffix=".json", dir=path.parent); os.close(fd)
    Path(temporary).write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path); parser.add_argument("--status", required=True, type=Path)
    parser.add_argument("--max-rate-hz", type=float, default=1.0); parser.add_argument("--min-translation-m", type=float, default=0.35); parser.add_argument("--min-rotation-deg", type=float, default=15.0)
    args = parser.parse_args(); args.output_dir.mkdir(parents=True, exist_ok=True); args.status.parent.mkdir(parents=True, exist_ok=True)
    try:
        import cv2, numpy as np, rclpy
        from cv_bridge import CvBridge
        from message_filters import ApproximateTimeSynchronizer, Subscriber
        from rclpy.node import Node
        from sensor_msgs.msg import CameraInfo, Image
    except Exception as exc:
        atomic_json(args.status, {"status": "unavailable", "error": f"{type(exc).__name__}: {exc}"}); return 2
    class Bridge(Node):
        def __init__(self):
            super().__init__("sparseworld_live_keyframes"); self.bridge=CvBridge(); self.last=None; self.accepted=0; self.rejected=0
            sync=ApproximateTimeSynchronizer([Subscriber(self,Image,"/camera/color/image_raw"),Subscriber(self,Image,"/camera/depth/image_raw"),Subscriber(self,CameraInfo,"/camera/color/camera_info")], 5, .08)
            sync.registerCallback(self.callback); self.write_status("waiting_for_rgbd")
        def write_status(self, state):
            atomic_json(args.status,{"status":state,"accepted":self.accepted,"rejected":self.rejected,"policy":{"max_rate_hz":args.max_rate_hz,"min_translation_m":args.min_translation_m,"min_rotation_deg":args.min_rotation_deg,"queue_capacity":1},"global_accuracy":"unvalidated"})
        def callback(self,rgb,depth,info):
            now=rgb.header.stamp.sec+rgb.header.stamp.nanosec/1e9
            if self.last is not None and now-self.last < 1.0/args.max_rate_hz:
                self.rejected+=1; self.write_status("running"); return
            try:
                color=self.bridge.imgmsg_to_cv2(rgb,"bgr8"); depth_image=self.bridge.imgmsg_to_cv2(depth,"passthrough")
                index=self.accepted; stem=f"kf-{index:06d}"; cv2.imwrite(str(args.output_dir/(stem+".jpg")),color)
                np.save(args.output_dir/(stem+"-depth.npy"),depth_image)
                (args.output_dir/(stem+".json")).write_text(json.dumps({"keyframe_id":stem,"timestamp_s":now,"intrinsics":{"fx":info.k[0],"fy":info.k[4],"cx":info.k[2],"cy":info.k[5]},"global_accuracy":"unvalidated","source":"live_keyframe_gate"},sort_keys=True)+"\n")
                self.accepted+=1; self.last=now; self.write_status("running")
            except Exception as exc:
                self.get_logger().warning(f"keyframe rejected: {exc}"); self.rejected+=1; self.write_status("error")
    rclpy.init(); node=Bridge()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally:
        node.destroy_node()
        if rclpy.ok(): rclpy.shutdown()
    return 0
if __name__ == "__main__": raise SystemExit(main())
