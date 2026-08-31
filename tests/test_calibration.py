import hashlib
import json
import sys
from pathlib import Path

from sparseworld_p0.calibration import assess_calibration_evidence, render_calibration_report


def _write_raw(path: Path, text: str = "raw calibration\n") -> str:
    path.write_text(text, encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_calibration_assessment_remains_not_measured_when_required_raw_evidence_is_missing(tmp_path: Path):
    result = assess_calibration_evidence({"schema_version": "p0/calibration-evidence/v1"}, tmp_path)

    assert result["status"] == "not_measured"
    assert result["gates"]["camera_intrinsics"]["status"] == "not_measured"
    assert result["gates"]["camera_imu_extrinsics"]["status"] == "not_measured"
    assert result["gates"]["device_host_clock_offset"]["status"] == "not_measured"


def test_calibration_assessment_fails_closed_for_an_unknown_evidence_schema(tmp_path: Path):
    result = assess_calibration_evidence({"schema_version": "unknown/v1"}, tmp_path)
    assert result["status"] == "fail"
    assert result["reason"] == "unsupported_evidence_schema"


def test_calibration_assessment_fails_on_hash_mismatch_instead_of_accepting_claimed_residuals(tmp_path: Path):
    raw = tmp_path / "intrinsics.json"
    _write_raw(raw)
    evidence = {
        "schema_version": "p0/calibration-evidence/v1",
        "profile_sha256": "a" * 64,
        "tool": {"name": "checkerboard", "version": "1.0"},
        "camera_intrinsics": {
            "raw_file": raw.name,
            "sha256": "0" * 64,
            "residual_px": 0.2,
            "acceptance_max_residual_px": 0.5,
        },
    }

    result = assess_calibration_evidence(evidence, tmp_path)

    assert result["status"] == "fail"
    assert result["gates"]["camera_intrinsics"]["status"] == "fail"
    assert result["gates"]["camera_intrinsics"]["reason"] == "raw_file_sha256_mismatch"


def test_calibration_assessment_passes_only_complete_hash_bound_evidence_and_writes_deterministic_report(tmp_path: Path):
    files = {name: _write_raw(tmp_path / name) for name in ("intrinsics.json", "rgb_depth.json", "camera_imu.json", "base_camera.json", "clock.json")}
    evidence = {
        "schema_version": "p0/calibration-evidence/v1",
        "profile_sha256": "a" * 64,
        "tool": {"name": "calibration-suite", "version": "1.0"},
        "camera_intrinsics": {"raw_file": "intrinsics.json", "sha256": files["intrinsics.json"], "residual_px": 0.2, "acceptance_max_residual_px": 0.5},
        "rgb_depth_alignment": {"raw_file": "rgb_depth.json", "sha256": files["rgb_depth.json"], "residual_px": 0.3, "acceptance_max_residual_px": 0.5},
        "camera_imu_extrinsics": {"raw_file": "camera_imu.json", "sha256": files["camera_imu.json"], "translation_m": [0.0, 0.0, 0.0], "rotation_xyzw": [0.0, 0.0, 0.0, 1.0], "residual": 0.1, "acceptance_max_residual": 0.5},
        "base_camera_transform": {"raw_file": "base_camera.json", "sha256": files["base_camera.json"], "translation_m": [0.0, 0.0, 0.1], "rotation_xyzw": [0.0, 0.0, 0.0, 1.0]},
        "device_host_clock_offset": {"raw_file": "clock.json", "sha256": files["clock.json"], "pairing_policy": "hardware_trigger_shared_clock", "offset_ns": 12, "residual_ns": 4, "acceptance_max_residual_ns": 10},
    }

    result = assess_calibration_evidence(evidence, tmp_path)
    assert result["status"] == "pass"
    assert all(gate["status"] == "pass" for gate in result["gates"].values())
    report = render_calibration_report(result, tmp_path / "report")
    assert json.loads(report["json"].read_text(encoding="utf-8"))["status"] == "pass"
    assert report["sha256"].read_text(encoding="utf-8") == f"{hashlib.sha256(report['json'].read_bytes()).hexdigest()}  calibration_assessment.json\n"


def test_camera_imu_transform_rejects_wrong_vector_lengths(tmp_path: Path):
    raw = tmp_path / "camera_imu.json"
    digest = _write_raw(raw)
    result = assess_calibration_evidence({
        "schema_version": "p0/calibration-evidence/v1",
        "camera_imu_extrinsics": {
            "raw_file": raw.name, "sha256": digest,
            "translation_m": [0.0, 0.0, 0.0, 0.0], "rotation_xyzw": [0.0, 0.0, 1.0],
            "residual": 0.1, "acceptance_max_residual": 0.5,
        },
    }, tmp_path)
    assert result["gates"]["camera_imu_extrinsics"] == {"status": "not_measured", "reason": "transform_fields_missing"}


def test_calibration_evidence_refuses_raw_file_outside_evidence_directory(tmp_path: Path):
    outside = tmp_path.parent / "outside-calibration.json"
    digest = _write_raw(outside)
    result = assess_calibration_evidence({
        "schema_version": "p0/calibration-evidence/v1",
        "camera_intrinsics": {"raw_file": "../outside-calibration.json", "sha256": digest, "residual_px": 0.1, "acceptance_max_residual_px": 0.5},
    }, tmp_path)
    assert result["gates"]["camera_intrinsics"] == {"status": "fail", "reason": "raw_file_outside_evidence_directory"}


def test_cli_assess_calibration_writes_hash_bound_report(tmp_path: Path, monkeypatch):
    from sparseworld_p0 import cli

    raw = tmp_path / "intrinsics.json"
    digest = _write_raw(raw)
    evidence = tmp_path / "evidence.json"
    evidence.write_text(json.dumps({
        "schema_version": "p0/calibration-evidence/v1",
        "camera_intrinsics": {"raw_file": raw.name, "sha256": digest, "residual_px": 0.1, "acceptance_max_residual_px": 0.5},
    }), encoding="utf-8")
    output = tmp_path / "report"
    monkeypatch.setattr(sys, "argv", ["sparseworld-p0", "assess-calibration", "--evidence", str(evidence), "--output", str(output)])
    assert cli.main() == 0
    assert (output / "calibration_assessment.json").is_file()
