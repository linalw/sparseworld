"""Load and validate the frozen P0 capture profile."""

from pathlib import Path
from typing import Any, Mapping

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
        device=_mapping(data, "device"),
        frames=_mapping(data, "frames"),
        streams=_mapping(data, "streams"),
        map=_mapping(data, "map"),
        quality_gates=_mapping(data, "quality_gates"),
        time_gates=_mapping(data, "time_gates"),
        diagnostics=_mapping(data, "diagnostics"),
        topology=_mapping(data, "topology"),
        scope=_mapping(data, "scope"),
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
    missing_streams = [name for name in REQUIRED_STREAMS if name not in profile.streams]
    if missing_streams:
        errors.append("streams must include rgb, depth, left, right, and imu")
    if profile.map.get("origin") != "local_initialization_without_external_datum":
        errors.append("map.origin must be local_initialization_without_external_datum")
    if profile.map.get("units") != "SI":
        errors.append("map.units must be SI")
    if profile.map.get("timestamp_standard") != "UTC ISO-8601":
        errors.append("map.timestamp_standard must be UTC ISO-8601")
    if not profile.quality_gates:
        errors.append("quality_gates must be explicit")
    if not profile.time_gates:
        errors.append("time_gates must be explicit")
    window = profile.diagnostics.get("window_seconds")
    if not isinstance(window, (int, float)) or not 10 <= window <= 60:
        errors.append("diagnostics.window_seconds must be between 10 and 60")
    if profile.diagnostics.get("storage") != "bounded_local_dense":
        errors.append("diagnostics.storage must be bounded_local_dense")
    if profile.topology.get("requires_realtime_clearance_check") is not True:
        errors.append("topology.requires_realtime_clearance_check must be true")
    if profile.scope.get("motor_control") is not False:
        errors.append("scope.motor_control must be false")
    return errors


def _mapping(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = data.get(key, {})
    return value if isinstance(value, dict) else {}
