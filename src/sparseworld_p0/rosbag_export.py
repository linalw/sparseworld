"""Normalize ROS 2 bag timestamp metadata without manufacturing sequence IDs."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any, Iterable, Mapping


def export_rosbag_timestamps(bag_path: str | Path, output_jsonl: str | Path) -> dict[str, Any]:
    """Export recorded and header timestamps to JSONL.

    A ``.jsonl`` input is a deterministic fixture interchange format. Other
    paths require ROS 2's ``rosbag2_py`` and retain each message's recorded
    timestamp separately from its message-header timestamp.
    """
    source, destination = Path(bag_path), Path(output_jsonl)
    try:
        rows = _fixture_rows(source) if source.suffix == ".jsonl" else _rosbag_rows(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with destination.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, sort_keys=True) + "\n")
                count += 1
        return {"schema_version": "p0/rosbag-timestamps/v1", "bag_path": str(source), "output": str(destination), "message_count": count}
    except PermissionError as error:
        raise RuntimeError("rosbag export refused: permission denied") from error
    except RuntimeError:
        raise
    except Exception as error:
        raise RuntimeError(f"rosbag export refused: {type(error).__name__}: {error}") from error


def package_normalized_samples_mcap(source_jsonl: str | Path, output_dir: str | Path) -> dict[str, Any]:
    """Package normalized SDK samples into a user-space ROS 2 MCAP container.

    This is a diagnostic replay container, not an Orbbec ROS driver recording:
    each original JSON row is serialized as ``std_msgs/msg/String`` on one
    explicitly named topic.  No image, TF, camera-info, or missing sample is
    synthesized.  The optional ``rosbags`` dependency is imported lazily so
    SDK-only installations remain usable.
    """
    source, destination = Path(source_jsonl), Path(output_dir)
    try:
        from rosbags.rosbag2 import StoragePlugin, Writer
        from rosbags.typesys import Stores, get_typestore
    except (ImportError, ModuleNotFoundError) as error:
        raise RuntimeError("MCAP packaging refused: install the optional rosbags dependency") from error
    try:
        typestore = get_typestore(Stores.ROS2_HUMBLE)
        message_type = "std_msgs/msg/String"
        message_class = typestore.types[message_type]
        rows: list[dict[str, Any]] = []
        for line_number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            raw = json.loads(line)
            if not isinstance(raw, Mapping):
                raise RuntimeError(f"MCAP packaging refused: line {line_number} must be an object")
            rows.append(dict(raw))
        destination.parent.mkdir(parents=True, exist_ok=True)
        bag_path = destination / f"{destination.name}.mcap"
        with Writer(destination, version=9, storage_plugin=StoragePlugin.MCAP) as writer:
            connection = writer.add_connection(
                "/sparseworld/p0/normalized_sample",
                message_type,
                typestore=typestore,
            )
            for index, row in enumerate(rows):
                timestamp = row.get("host_receive_time_ns", row.get("device_time_ns"))
                if not isinstance(timestamp, int) or isinstance(timestamp, bool) or timestamp < 0:
                    raise RuntimeError(f"MCAP packaging refused: line {index + 1} has no non-negative integer timestamp")
                payload = json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                message = message_class(data=payload)
                writer.write(connection, timestamp, typestore.serialize_cdr(message, message_type))
        if not bag_path.is_file():
            raise RuntimeError("MCAP packaging refused: writer did not produce the MCAP file")
        return {
            "schema_version": "p0/normalized-samples-mcap/v1",
            "status": "packaged_unassessed",
            "source_jsonl": str(source),
            "source_jsonl_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "output_dir": str(destination),
            "mcap_path": str(bag_path),
            "mcap_sha256": hashlib.sha256(bag_path.read_bytes()).hexdigest(),
            "message_count": len(rows),
            "topic": "/sparseworld/p0/normalized_sample",
            "message_type": message_type,
            "interpretation": "user-space diagnostic replay container; not an Orbbec ROS driver bag and not a calibration, synchronization, or performance result",
        }
    except PermissionError as error:
        raise RuntimeError("MCAP packaging refused: permission denied") from error
    except RuntimeError:
        raise
    except Exception as error:
        raise RuntimeError(f"MCAP packaging refused: {type(error).__name__}: {error}") from error


def _fixture_rows(path: Path) -> Iterable[dict[str, Any]]:
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"rosbag export refused: invalid JSONL fixture line {line_number}") from error
        if not isinstance(raw, Mapping):
            raise RuntimeError(f"rosbag export refused: fixture line {line_number} must be an object")
        yield _normalise(raw)


def _rosbag_rows(path: Path) -> Iterable[dict[str, Any]]:
    try:
        import rosbag2_py
        from rclpy.serialization import deserialize_message
        from rosidl_runtime_py.utilities import get_message
    except (ImportError, ModuleNotFoundError) as error:
        raise RuntimeError("rosbag export refused: ROS 2 rosbag2_py, rclpy, and rosidl_runtime_py are required") from error
    try:
        reader = rosbag2_py.SequentialReader()
        reader.open(rosbag2_py.StorageOptions(uri=str(path), storage_id="mcap"), rosbag2_py.ConverterOptions("", ""))
        topics = {item.name: item for item in reader.get_all_topics_and_types()}
        while reader.has_next():
            topic, data, recorded_timestamp_ns = reader.read_next()
            metadata = topics[topic]
            message = deserialize_message(data, get_message(metadata.type))
            header = getattr(message, "header", None)
            yield _normalise({
                "topic": topic,
                "recorded_timestamp_ns": recorded_timestamp_ns,
                "header": _header_mapping(header),
                "topic_type": metadata.type,
                "qos": getattr(metadata, "offered_qos_profiles", None),
            })
    except PermissionError:
        raise
    except Exception as error:
        raise RuntimeError(f"unable to read ROS bag {path}: {error}") from error


def _normalise(raw: Mapping[str, Any]) -> dict[str, Any]:
    header = raw.get("header")
    header = header if isinstance(header, Mapping) else {}
    sequence = _value(header, "seq", "sequence")
    if sequence is None:
        sequence = raw.get("sequence")
    return {
        "topic": raw.get("topic"),
        "recorded_timestamp_ns": raw.get("recorded_timestamp_ns", raw.get("recorded_ns")),
        "header_timestamp_ns": raw.get("header_timestamp_ns") if isinstance(raw.get("header_timestamp_ns"), int) else _header_timestamp_ns(header),
        "sequence": sequence if isinstance(sequence, (int, str)) and not isinstance(sequence, bool) else None,
        "topic_type": raw.get("topic_type"),
        "qos": raw.get("qos"),
    }


def _header_mapping(header: Any) -> dict[str, Any]:
    if header is None:
        return {}
    stamp = getattr(header, "stamp", None)
    return {"stamp": {"sec": getattr(stamp, "sec", None), "nanosec": getattr(stamp, "nanosec", None)}, "seq": getattr(header, "seq", None)}


def _header_timestamp_ns(header: Mapping[str, Any]) -> int | None:
    stamp_ns = header.get("stamp_ns")
    if isinstance(stamp_ns, int) and not isinstance(stamp_ns, bool):
        return stamp_ns
    stamp = header.get("stamp")
    if isinstance(stamp, Mapping):
        sec, nanosec = stamp.get("sec"), stamp.get("nanosec")
        if isinstance(sec, int) and isinstance(nanosec, int) and not isinstance(sec, bool) and not isinstance(nanosec, bool):
            return sec * 1_000_000_000 + nanosec
    return None


def _value(mapping: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in mapping:
            return mapping[name]
    return None
