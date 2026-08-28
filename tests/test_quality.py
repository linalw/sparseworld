from pathlib import Path
import hashlib
from sparseworld_p0.profile import load_profile
from sparseworld_p0.quality import assess
from sparseworld_p0.reporting import render_report


def _profile(tmp_path: Path):
    src = Path(__file__).parents[1] / "config" / "p0_capture_profile.yaml"
    return load_profile(src)


def test_quality_unknown_fields_are_not_measured(tmp_path):
    profile = _profile(tmp_path)
    assessment = assess(profile, {"depth": [{"timestamp_ns": 1}]})
    assert assessment["gates"]["depth_valid_fraction"]["status"] == "not_measured"
    assert assessment["gates"]["blur"]["status"] == "not_measured"
    assert assessment["gates"]["gyro_saturation"]["status"] == "not_measured"


def test_quality_metrics_and_report_are_deterministic(tmp_path):
    profile = _profile(tmp_path)
    samples = {
        "depth": [{"timestamp_ns": i, "depth_valid_fraction": 0.9} for i in range(3)],
        "rgb": [{"timestamp_ns": i, "blur_score": 120.0} for i in range(3)],
        "imu": [
            {"timestamp_ns": 0, "gyro": [0.1, 0.2, 0.3], "acceleration": [1, 2, 3]},
            {"timestamp_ns": 1, "gyro": [0.2, 0.2, 0.3], "acceleration": [1, 2, 3]},
        ],
    }
    assessment = assess(profile, samples)
    assert assessment["gates"]["depth_valid_fraction"]["value"] == 0.9
    out = render_report(assessment, tmp_path)
    assert out["json"].exists() and out["markdown"].exists() and out["sha256"].exists()
    first = out["json"].read_text()
    render_report(assessment, tmp_path)
    assert out["json"].read_text() == first


def test_explicit_profile_thresholds_can_fail_quality_gates(tmp_path):
    profile_path = tmp_path / "profile.yaml"
    source = (Path(__file__).parents[1] / "config" / "p0_capture_profile.yaml").read_text()
    profile_path.write_text(source.replace(
        "quality_gates:\n", "quality_gates:\n  depth_valid_fraction: {minimum: 0.8}\n  blur: {minimum: 100}\n"
    ))
    assessment = assess(load_profile(profile_path), {
        "depth": [{"timestamp_ns": 0, "depth_valid_fraction": 0.5}, {"timestamp_ns": 1, "depth_valid_fraction": 0.5}],
        "rgb": [{"timestamp_ns": 0, "blur_score": 50.0}, {"timestamp_ns": 1, "blur_score": 50.0}],
    })
    assert assessment["gates"]["depth_valid_fraction"]["status"] == "fail"
    assert assessment["gates"]["blur"]["status"] == "fail"


def test_profile_defined_offset_gate_uses_same_sample_device_host_timestamps(tmp_path):
    profile_path = tmp_path / "profile.yaml"
    source = (Path(__file__).parents[1] / "config" / "p0_capture_profile.yaml").read_text()
    profile_path.write_text(source.replace(
        "  device_host_offset: pending_measurement", "  device_host_offset: {maximum_ns: 20}"
    ))
    assessment = assess(load_profile(profile_path), {
        "rgb": [
            {"frame_number": 1, "device_time_ns": 100, "host_receive_time_ns": 130},
            {"frame_number": 2, "device_time_ns": 200, "host_receive_time_ns": 230},
        ],
        # Large RGB-depth skew is intentionally not device-host offset evidence.
        "depth": [
            {"frame_number": 1, "device_time_ns": 1_000, "host_receive_time_ns": 1_005},
            {"frame_number": 2, "device_time_ns": 2_000, "host_receive_time_ns": 2_005},
        ],
    })
    assert assessment["gates"]["device_host_offset"]["status"] == "fail"
    assert assessment["gates"]["device_host_offset"]["value"] == 30
    assert assessment["device_host_offset"]["sample_count"] == 4
    assert assessment["device_host_offset"]["median_abs_ns"] == 17.5


def test_report_sidecar_contains_checksum_of_exact_json_content(tmp_path):
    assessment = assess(_profile(tmp_path), {"depth": [{"device_time_ns": 1}]})
    out = render_report(assessment, tmp_path)
    payload = out["json"].read_bytes()
    assert out["sha256"].read_text() == f"{hashlib.sha256(payload).hexdigest()}  assessment.json\n"
