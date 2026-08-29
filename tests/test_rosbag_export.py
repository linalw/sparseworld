import json
import sys
import types
from pathlib import Path

from sparseworld_p0.rosbag_export import _rosbag_rows, export_rosbag_timestamps


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


def test_rosbag_reader_selects_mcap_and_keeps_message_clock_fields(monkeypatch, tmp_path: Path):
    opened = {}

    class Reader:
        def open(self, storage, converter):
            opened["storage_id"] = storage.storage_id
        def get_all_topics_and_types(self):
            return [types.SimpleNamespace(name="/color", type="sensor_msgs/msg/Image", offered_qos_profiles="reliable")]
        def has_next(self):
            return not getattr(self, "read", False)
        def read_next(self):
            self.read = True
            return "/color", b"x", 123

    class StorageOptions:
        def __init__(self, uri, storage_id): self.uri, self.storage_id = uri, storage_id

    class ConverterOptions:
        def __init__(self, input_format, output_format): pass

    rosbag = types.SimpleNamespace(SequentialReader=Reader, StorageOptions=StorageOptions, ConverterOptions=ConverterOptions)
    monkeypatch.setitem(sys.modules, "rosbag2_py", rosbag)
    serialization = types.SimpleNamespace(deserialize_message=lambda data, cls: types.SimpleNamespace())
    utilities = types.SimpleNamespace(get_message=lambda topic_type: object)
    monkeypatch.setitem(sys.modules, "rclpy.serialization", serialization)
    monkeypatch.setitem(sys.modules, "rosidl_runtime_py.utilities", utilities)
    rows = list(_rosbag_rows(tmp_path / "recording"))
    assert opened["storage_id"] == "mcap"
    assert rows == [{"topic": "/color", "recorded_timestamp_ns": 123, "header_timestamp_ns": None, "sequence": None, "topic_type": "sensor_msgs/msg/Image", "qos": "reliable"}]
