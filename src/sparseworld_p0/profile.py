"""Load and validate the frozen P0 capture profile."""

from pathlib import Path
from typing import Any, Mapping
from types import MappingProxyType

import yaml

from .models import CaptureProfile


CANONICAL_FRAME_TREE = ("map", "odom", "base_link", "camera_link", "camera_optical_frame")
REQUIRED_STREAMS = ("rgb", "depth", "left", "right", "imu")


def load_profile(path: str | Path) -> CaptureProfile:
    """Load a YAML profile into immutable top-level capture records."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("profile root must be a mapping")
    return CaptureProfile(
        schema_version=data.get("schema_version"),
        device=_freeze_mapping(data, "device"),
        frames=_freeze_mapping(data, "frames"),
        streams=_freeze_mapping(data, "streams"),
        map=_freeze_mapping(data, "map"),
        quality_gates=_freeze_mapping(data, "quality_gates"),
        time_gates=_freeze_mapping(data, "time_gates"),
        diagnostics=_freeze_mapping(data, "diagnostics"),
        topology=_freeze_mapping(data, "topology"),
        scope=_freeze_mapping(data, "scope"),
    )


def validate_profile(profile: CaptureProfile) -> list[str]:
    """Return every profile-contract violation; an empty list means valid."""
    errors: list[str] = []
    if profile.schema_version != "p0/v1":
        errors.append("schema_version must be p0/v1")
    if tuple(profile.frames.get("tree", ())) != CANONICAL_FRAME_TREE:
        errors.append("frames.tree must be map -> odom -> base_link -> camera_link -> camera_optical_frame")
    if profile.frames.get("imu_parent") != "base_link" or profile.frames.get("imu_frame") != "imu_link":
        errors.append("frames must define base_link -> imu_link")
    if any(name not in profile.streams for name in REQUIRED_STREAMS):
        errors.append("streams must include rgb, depth, left, right, and imu")
    for name in REQUIRED_STREAMS:
        stream = profile.streams.get(name)
        if not isinstance(stream, Mapping):
            errors.append(f"streams.{name} must be a mapping")
            continue
        for field in ("resolution", "nominal_rate"):
            if not stream.get(field):
                errors.append(f"streams.{name}.{field} must be non-empty")
    if profile.map.get("origin") != "local_initialization_without_external_datum":
        errors.append("map.origin must be local_initialization_without_external_datum")
    if profile.map.get("units") != "SI":
        errors.append("map.units must be SI")
    if profile.map.get("timestamp_standard") != "UTC ISO-8601":
        errors.append("map.timestamp_standard must be UTC ISO-8601")
    for field in ("stationary_calibration", "hand_carried_supervised_route"):
        if not profile.quality_gates.get(field):
            errors.append(f"quality_gates.{field} must be explicit")
    for field in ("device_host_offset", "timestamp_pairing_policy"):
        if not profile.time_gates.get(field):
            errors.append(f"time_gates.{field} must be explicit")
    window = profile.diagnostics.get("window_seconds")
    if not isinstance(window, (int, float)) or not 10 <= window <= 60:
        errors.append("diagnostics.window_seconds must be between 10 and 60")
    if profile.diagnostics.get("storage") != "bounded_local_dense":
        errors.append("diagnostics.storage must be bounded_local_dense")
    dense_buffer = profile.diagnostics.get("dense_buffer")
    if not isinstance(dense_buffer, Mapping):
        errors.append("diagnostics.dense_buffer must be a mapping")
    else:
        if not dense_buffer.get("local_origin_frame"):
            errors.append("diagnostics.dense_buffer.local_origin_frame must be explicit")
        if not dense_buffer.get("timestamp_field"):
            errors.append("diagnostics.dense_buffer.timestamp_field must be explicit")
        ttl = dense_buffer.get("ttl_seconds")
        if not isinstance(ttl, (int, float)) or not 10 <= ttl <= 60:
            errors.append("diagnostics.dense_buffer.ttl_seconds must be between 10 and 60")
    if profile.topology.get("requires_realtime_clearance_check") is not True:
        errors.append("topology.requires_realtime_clearance_check must be true")
    if profile.scope.get("motor_control") is not False:
        errors.append("scope.motor_control must be false")
    return errors


def _freeze_mapping(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = data.get(key, {})
    return _freeze(value) if isinstance(value, dict) else MappingProxyType({})


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value
