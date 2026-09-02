#!/usr/bin/env python3
"""Best-effort ROS 2 RGB/depth preview writer; recording never depends on it."""
from __future__ import annotations
import argparse, os, tempfile
from pathlib import Path

def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--output", required=True); parser.add_argument("--depth-output", required=True); args = parser.parse_args()
    try:
        import rclpy
        from rclpy.node import Node
        from sensor_msgs.msg import Image
        from cv_bridge import CvBridge
        import cv2
    except Exception as exc:
        Path(args.output).with_suffix(".error").write_text(f"preview unavailable: {type(exc).__name__}: {exc}\n", encoding="utf-8")
        return 2
    class Preview(Node):
        def __init__(self):
            super().__init__("sparseworld_capture_preview")
            self.bridge, self.output, self.depth_output = CvBridge(), Path(args.output), Path(args.depth_output)
            self.create_subscription(Image, "/camera/color/image_raw", self.callback, 10)
            self.create_subscription(Image, "/camera/depth/image_raw", self.depth_callback, 10)
        def callback(self, msg):
            try:
                image = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
                fd, tmp = tempfile.mkstemp(prefix="preview-", suffix=".jpg", dir=self.output.parent); os.close(fd)
                if cv2.imwrite(tmp, image): os.replace(tmp, self.output)
                else: os.unlink(tmp)
            except Exception as exc: self.get_logger().warning(f"preview frame failed: {exc}")
        def depth_callback(self, msg):
            try:
                image = self.bridge.imgmsg_to_cv2(msg, desired_encoding="passthrough")
                import numpy as np
                image = np.nan_to_num(image).astype("float32")
                valid = image[image > 0]
                if valid.size == 0: return
                low, high = np.percentile(valid, (2, 98))
                if high <= low: return
                display = ((image - low) * 255.0 / (high - low)).clip(0, 255).astype("uint8")
                display[image <= 0] = 0
                display = cv2.applyColorMap(display, cv2.COLORMAP_TURBO)
                fd, tmp = tempfile.mkstemp(prefix="depth-preview-", suffix=".jpg", dir=self.depth_output.parent); os.close(fd)
                if cv2.imwrite(tmp, display): os.replace(tmp, self.depth_output)
                else: os.unlink(tmp)
            except Exception as exc: self.get_logger().warning(f"depth preview frame failed: {exc}")
    rclpy.init(); node = Preview()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally: node.destroy_node(); rclpy.shutdown()
    return 0
if __name__ == "__main__": raise SystemExit(main())
