"""Evidence-bound calibration and clock-offset assessment for P0.

This module never derives calibration values.  It only checks that operator-
provided raw outputs are present, hash-bound, and satisfy explicitly declared
residual criteria.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


_GATES = (
    "camera_intrinsics",
    "rgb_depth_alignment",
    "camera_imu_extrinsics",
    "base_camera_transform",
    "device_host_clock_offset",
)


def _raw_check(node: Any, evidence_dir: Path) -> tuple[str, str | None]:
    if not isinstance(node, Mapping):
        return "not_measured", "evidence_section_missing"
    raw_file = node.get("raw_file")
    expected = node.get("sha256")
    if not isinstance(raw_file, str) or not raw_file:
        return "not_measured", "raw_file_missing"
    root = evidence_dir.resolve()
    path = (root / raw_file).resolve()
    if root not in path.parents:
        return "fail", "raw_file_outside_evidence_directory"
    if not path.is_file():
        return "not_measured", "raw_file_missing"
    if not isinstance(expected, str) or len(expected) != 64:
        return "fail", "raw_file_sha256_missing"
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        return "fail", "raw_file_sha256_mismatch"
    return "measured", None


def _residual_gate(node: Mapping[str, Any], key: str = "residual", threshold_key: str = "acceptance_max_residual") -> dict[str, Any]:
    value = node.get(key)
    threshold = node.get(threshold_key)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not isinstance(threshold, (int, float)) or isinstance(threshold, bool):
        return {"status": "not_measured", "value": value, "threshold": threshold, "reason": "residual_or_threshold_missing"}
    return {"status": "pass" if value <= threshold else "fail", "value": value, "threshold": threshold, "reason": None if value <= threshold else "residual_exceeds_threshold"}


def _gate(name: str, node: Any, evidence_dir: Path) -> dict[str, Any]:
    status, reason = _raw_check(node, evidence_dir)
    result: dict[str, Any] = {"status": status, "reason": reason}
    if status != "measured":
        return result
    assert isinstance(node, Mapping)
    if name in ("camera_intrinsics", "rgb_depth_alignment"):
        result.update(_residual_gate(node, key="residual_px", threshold_key="acceptance_max_residual_px"))
    elif name == "camera_imu_extrinsics":
        if not (isinstance(node.get("translation_m"), list) and len(node["translation_m"]) == 3
                and isinstance(node.get("rotation_xyzw"), list) and len(node["rotation_xyzw"]) == 4):
            return {"status": "not_measured", "reason": "transform_fields_missing"}
        result.update(_residual_gate(node))
    elif name == "base_camera_transform":
        if not (isinstance(node.get("translation_m"), list) and len(node["translation_m"]) == 3
                and isinstance(node.get("rotation_xyzw"), list) and len(node["rotation_xyzw"]) == 4):
            return {"status": "not_measured", "reason": "transform_fields_missing"}
        result.update({"status": "pass", "reason": None})
    elif name == "device_host_clock_offset":
        if not isinstance(node.get("pairing_policy"), str) or not node.get("pairing_policy"):
            return {"status": "not_measured", "reason": "pairing_policy_missing"}
        result.update(_residual_gate(node, key="residual_ns", threshold_key="acceptance_max_residual_ns"))
    return result


def assess_calibration_evidence(evidence: Mapping[str, Any], evidence_dir: str | Path) -> dict[str, Any]:
    """Assess hash-bound calibration evidence without filling missing values."""
    root = Path(evidence_dir)
    if evidence.get("schema_version") != "p0/calibration-evidence/v1":
        return {
            "schema_version": "p0/calibration-assessment/v1",
            "status": "fail",
            "reason": "unsupported_evidence_schema",
            "source": {"schema_version": evidence.get("schema_version")},
            "gates": {name: {"status": "not_measured", "reason": "unsupported_evidence_schema"} for name in _GATES},
            "interpretation": "evidence schema is unsupported; no calibration claim is accepted",
        }
    gates = {name: _gate(name, evidence.get(name), root) for name in _GATES}
    statuses = [item["status"] for item in gates.values()]
    overall = "fail" if "fail" in statuses else ("pass" if statuses and all(item == "pass" for item in statuses) else "not_measured")
    canonical = json.dumps(evidence, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
    return {
        "schema_version": "p0/calibration-assessment/v1",
        "status": overall,
        "source": {"schema_version": evidence.get("schema_version"), "profile_sha256": evidence.get("profile_sha256"), "evidence_sha256": hashlib.sha256(canonical).hexdigest()},
        "gates": gates,
        "interpretation": "raw evidence is hash-bound; this is not a replacement for field calibration or robot acceptance",
    }


def render_calibration_report(assessment: Mapping[str, Any], output_dir: str | Path) -> dict[str, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(dict(assessment), sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    json_path = out / "calibration_assessment.json"
    md_path = out / "calibration_assessment.md"
    sha_path = out / "calibration_assessment.json.sha256"
    json_path.write_text(payload, encoding="utf-8")
    lines = ["# P0 Calibration and Time-Sync Assessment", "", f"Status: `{assessment.get('status')}`", "", "| Gate | Status | Reason |", "|---|---|---|"]
    for name, gate in sorted((assessment.get("gates") or {}).items()):
        lines.append(f"| {name} | {gate.get('status')} | {gate.get('reason')} |")
    lines += ["", str(assessment.get("interpretation", "")), ""]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    sha_path.write_text(f"{hashlib.sha256(payload.encode('utf-8')).hexdigest()}  {json_path.name}\n", encoding="utf-8")
    return {"json": json_path, "markdown": md_path, "sha256": sha_path}
