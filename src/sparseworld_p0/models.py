"""Immutable records for the auditable P0 capture contract."""

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class CaptureProfile:
    """A frozen P0 capture configuration loaded from a YAML profile."""

    schema_version: str | None
    device: Mapping[str, Any]
    frames: Mapping[str, Any]
    streams: Mapping[str, Any]
    map: Mapping[str, Any]
    quality_gates: Mapping[str, Any]
    time_gates: Mapping[str, Any]
    diagnostics: Mapping[str, Any]
    topology: Mapping[str, Any]
    scope: Mapping[str, Any]
