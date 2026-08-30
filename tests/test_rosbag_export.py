import json
import sys
import types
from pathlib import Path

from sparseworld_p0.rosbag_export import _rosbag_rows, export_rosbag_timestamps, package_normalized_samples_mcap


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


def test_package_normalized_samples_mcap_writes_readable_user_space_mcap(tmp_path: Path):
    source = tmp_path / "timestamps.jsonl"
    source.write_text(
        json.dumps({"stream": "depth", "device_time_ns": 10, "host_receive_time_ns": 100}) + "\n"
        + json.dumps({"stream": "imu", "sensor": "accel", "device_time_ns": 20, "host_receive_time_ns": 200}) + "\n",
        encoding="utf-8",
    )
    result = package_normalized_samples_mcap(source, tmp_path / "capture_mcap")
    assert result["status"] == "packaged_unassessed"
    assert result["message_count"] == 2
    assert len(result["source_jsonl_sha256"]) == 64
    assert (tmp_path / "capture_mcap" / "capture_mcap.mcap").is_file()
    assert len(result["mcap_sha256"]) == 64

    from rosbags.rosbag2 import Reader
    with Reader(tmp_path / "capture_mcap") as reader:
        rows = list(reader.messages())
    assert len(rows) == 2
    assert {connection.topic for connection, _, _ in rows} == {"/sparseworld/p0/normalized_sample"}
    assert all(connection.msgtype == "std_msgs/msg/String" for connection, _, _ in rows)


def test_cli_package_mcap_writes_manifest_and_hash(tmp_path: Path, monkeypatch):
    from sparseworld_p0 import cli

    capture = tmp_path / "capture"
    capture.mkdir()
    (capture / "timestamps.jsonl").write_text(
        json.dumps({"stream": "depth", "device_time_ns": 10, "host_receive_time_ns": 100}) + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "mcap"
    monkeypatch.setattr(sys, "argv", ["sparseworld-p0", "package-mcap", "--capture-dir", str(capture), "--output", str(output)])
    assert cli.main() == 0
    manifest = json.loads((output / "package_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "packaged_unassessed"
    assert (output / "package_manifest.json.sha256").is_file()
