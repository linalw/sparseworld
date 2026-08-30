from pathlib import Path

from sparseworld_p0.profile import load_profile, validate_profile


def test_validation_requires_realtime_clearance_check(tmp_path: Path) -> None:
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text("schema_version: p0/v1\n", encoding="utf-8")

    errors = validate_profile(load_profile(profile_path))

    assert "topology.requires_realtime_clearance_check must be true" in errors


def test_real_profile_is_a_valid_p0_capture_contract() -> None:
    profile_path = Path(__file__).parents[1] / "config" / "p0_capture_profile.yaml"

    assert validate_profile(load_profile(profile_path)) == []


def test_loaded_profile_is_deeply_immutable() -> None:
    profile = load_profile(Path(__file__).parents[1] / "config" / "p0_capture_profile.yaml")
    try:
        profile.streams["rgb"]["resolution"] = "x"  # type: ignore[index]
    except TypeError:
        pass
    else:
        raise AssertionError("nested profile mapping must reject mutation")


def test_validation_requires_dense_buffer_contract(tmp_path: Path) -> None:
    source = Path(__file__).parents[1] / "config" / "p0_capture_profile.yaml"
    text = source.read_text(encoding="utf-8").replace("  dense_buffer:\n    local_origin_frame: camera_link\n    timestamp_field: UTC ISO-8601\n    ttl_seconds: 30\n", "")
    path = tmp_path / "profile.yaml"
    path.write_text(text, encoding="utf-8")
    errors = validate_profile(load_profile(path))
    assert any("dense_buffer" in error for error in errors)


def test_validation_rejects_missing_gate_keys(tmp_path: Path) -> None:
    source = Path(__file__).parents[1] / "config" / "p0_capture_profile.yaml"
    text = source.read_text(encoding="utf-8").replace("  stationary_calibration: pending_measurement\n", "")
    path = tmp_path / "profile.yaml"
    path.write_text(text, encoding="utf-8")
    errors = validate_profile(load_profile(path))
    assert any("quality_gates.stationary_calibration" in error for error in errors)


def test_validation_rejects_stream_without_required_fields(tmp_path: Path) -> None:
    source = Path(__file__).parents[1] / "config" / "p0_capture_profile.yaml"
    text = source.read_text(encoding="utf-8").replace("  rgb: {resolution: 1280x720, nominal_rate: 30, format: MJPG}", "  rgb: {resolution: 1280x720, format: MJPG}")
    path = tmp_path / "profile.yaml"
    path.write_text(text, encoding="utf-8")
    errors = validate_profile(load_profile(path))
    assert any("streams.rgb.nominal_rate" in error for error in errors)
