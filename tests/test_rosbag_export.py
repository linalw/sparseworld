import json
from pathlib import Path

from sparseworld_p0.rosbag_export import export_rosbag_timestamps


def test_exporter_preserves_unknown_ros_sequence_as_null(tmp_path: Path):
    bag = tmp_path / "bag.jsonl"
    bag.write_text(
        json.dumps(
            {
                "topic": "/camera/color/image_raw",
                "recorded_timestamp_ns": 123,
                "header": {"stamp_ns": 120},
                "topic_type": "sensor_msgs/msg/Image",
                "qos": {"reliability": "reliable"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "timestamps.jsonl"
    export_rosbag_timestamps(bag, out)
    row = json.loads(out.read_text(encoding="utf-8").strip())
    assert row["recorded_timestamp_ns"] == 123
    assert row["header_timestamp_ns"] == 120
    assert row["sequence"] is None
    assert row["topic_type"] == "sensor_msgs/msg/Image"
