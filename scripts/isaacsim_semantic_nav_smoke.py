#!/usr/bin/env python3
from __future__ import annotations
import sys

def main() -> int:
    try:
        from isaacsim import SimulationApp  # type: ignore
    except Exception as exc:
        print("Isaac Sim 6 Python modules unavailable; run with Isaac Sim python.sh", file=sys.stderr)
        print(f"detail: {exc}", file=sys.stderr)
        return 2
    app = SimulationApp({"headless": True})
    try:
        try:
            import omni.kit.app
            import omni.isaac.core.utils.extensions as extensions
            extensions.enable_extension("isaacsim.ros2.bridge")
        except Exception as exc:
            print(f"ROS 2 bridge unavailable: {exc}", file=sys.stderr)
            return 3
        print("Isaac Sim adapter loaded; configure a Carter/Jetbot USD scene and ROS 2 graph before navigation.")
        print("evidence_class=simulation_evidence; physical traversability remains unvalidated")
        return 0
    finally:
        app.close()

if __name__ == "__main__":
    raise SystemExit(main())
