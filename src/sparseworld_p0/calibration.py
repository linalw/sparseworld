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


def reprojection_rms_px(deltas: Any) -> float:
    """Return RMS Euclidean reprojection error from ``(dx, dy)`` pairs."""
    values = [(float(dx), float(dy)) for dx, dy in deltas]
    if not values:
        raise ValueError("reprojection RMS requires at least one point")
    return (sum(dx * dx + dy * dy for dx, dy in values) / len(values)) ** 0.5


def calibrate_chessboard_intrinsics(
    image_dir: str | Path,
    *,
    pattern_size: tuple[int, int],
    square_size_m: float,
) -> dict[str, Any]:
    """Calibrate a monocular pinhole camera from checkerboard images.

    ``pattern_size`` is the number of *inner* corners (columns, rows), and
    ``square_size_m`` is the measured checkerboard square edge in metres.
    Returned calibration is observation evidence; callers must preserve the
    image hashes and review residuals before accepting it.
    """
    if len(pattern_size) != 2 or any(not isinstance(value, int) or value < 2 for value in pattern_size):
        raise ValueError("pattern_size must contain two integers >= 2")
    if not isinstance(square_size_m, (int, float)) or isinstance(square_size_m, bool) or square_size_m <= 0:
        raise ValueError("square_size_m must be positive")
    try:
        import cv2
        import numpy as np
    except ImportError as error:
        raise RuntimeError("checkerboard calibration refused: install opencv-python and numpy") from error
    source = Path(image_dir)
    images = sorted(path for suffix in ("*.png", "*.jpg", "*.jpeg", "*.bmp") for path in source.glob(suffix))
    if not images:
        raise RuntimeError("checkerboard calibration refused: no supported images found")
    columns, rows = pattern_size
    object_points = np.zeros((columns * rows, 3), np.float32)
    object_points[:, :2] = np.mgrid[0:columns, 0:rows].T.reshape(-1, 2) * float(square_size_m)
    detected_objects, detected_corners, views = [], [], []
    image_size = None
    for path in images:
        image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        entry: dict[str, Any] = {"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        if image is None:
            entry.update({"status": "unreadable", "corner_count": 0})
            views.append(entry)
            continue
        if image_size is None:
            image_size = (int(image.shape[1]), int(image.shape[0]))
        elif image_size != (int(image.shape[1]), int(image.shape[0])):
            entry.update({"status": "rejected_size_mismatch", "corner_count": 0, "image_size_px": [int(image.shape[1]), int(image.shape[0])]})
            views.append(entry)
            continue
        found, corners = cv2.findChessboardCornersSB(
            image, pattern_size, flags=cv2.CALIB_CB_NORMALIZE_IMAGE | cv2.CALIB_CB_EXHAUSTIVE | cv2.CALIB_CB_ACCURACY,
        )
        detector = "findChessboardCornersSB"
        if not found:
            found, corners = cv2.findChessboardCorners(image, pattern_size, flags=cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE)
            detector = "findChessboardCorners"
            if found:
                corners = cv2.cornerSubPix(image, corners, (11, 11), (-1, -1), (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1e-4))
        entry.update({"status": "detected" if found else "not_detected", "corner_count": 0 if corners is None else int(len(corners)), "detector": detector})
        views.append(entry)
        if found and corners is not None:
            detected_objects.append(object_points)
            detected_corners.append(corners)
    if len(detected_corners) < 3 or image_size is None:
        raise RuntimeError(f"checkerboard calibration refused: only {len(detected_corners)} valid views; need at least 3")
    rms, camera_matrix, distortion, rotations, translations = cv2.calibrateCamera(detected_objects, detected_corners, image_size, None, None)
    errors = []
    used = 0
    for entry, object_set, image_set, rotation, translation in zip((item for item in views if item["status"] == "detected"), detected_objects, detected_corners, rotations, translations):
        projected, _ = cv2.projectPoints(object_set, rotation, translation, camera_matrix, distortion)
        deltas = (image_set.reshape(-1, 2) - projected.reshape(-1, 2)).tolist()
        error_px = reprojection_rms_px(deltas)
        entry["reprojection_rms_px"] = error_px
        errors.append(error_px)
        used += 1
    return {
        "schema_version": "p0/chessboard-intrinsics/v1",
        "status": "measured",
        "source_image_directory": str(source),
        "pattern_inner_corners": [columns, rows],
        "square_size_m": float(square_size_m),
        "image_size_px": list(image_size),
        "view_count": len(images),
        "accepted_view_count": used,
        "opencv_version": cv2.__version__,
        "calibration_rms_px": float(rms),
        "mean_reprojection_rms_px": float(sum(errors) / len(errors)),
        "max_reprojection_rms_px": float(max(errors)),
        "camera_matrix": camera_matrix.tolist(),
        "distortion_coefficients": distortion.reshape(-1).tolist(),
        "views": views,
        "interpretation": "monocular RGB checkerboard calibration only; does not calibrate depth, stereo, IMU, base transform, clock offset, SLAM, navigation, or safety",
    }


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
