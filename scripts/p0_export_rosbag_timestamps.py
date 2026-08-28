#!/usr/bin/env python3
"""CLI wrapper for sparseworld_p0.rosbag_export."""

from __future__ import annotations

import argparse

from sparseworld_p0.rosbag_export import export_rosbag_timestamps


def main() -> int:
    parser = argparse.ArgumentParser(description="Export ROS bag recorded/header timestamps as JSONL")
    parser.add_argument("bag_path")
    parser.add_argument("output_jsonl")
    args = parser.parse_args()
    export_rosbag_timestamps(args.bag_path, args.output_jsonl)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
