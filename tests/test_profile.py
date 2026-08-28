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
