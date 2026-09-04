import pytest

from sparseworld_p0.simulation import DifferentialDriveSim, SensorFrame, SimulationConfig, run_smoke_test


def test_config_rejects_non_positive_step() -> None:
    with pytest.raises(ValueError, match="step_s"):
        SimulationConfig(step_s=0)


def test_differential_drive_integrates_forward_motion() -> None:
    sim = DifferentialDriveSim(SimulationConfig(step_s=0.1, max_linear_speed=1.0))
    sim.step(1.0, 0.0)
    assert sim.pose.x == pytest.approx(0.1)
    assert sim.pose.y == pytest.approx(0.0)


def test_command_is_clamped_and_recorded() -> None:
    sim = DifferentialDriveSim(SimulationConfig(step_s=0.1, max_linear_speed=0.5, max_angular_speed=1.0))
    sim.step(2.0, 3.0)
    assert sim.last_command == pytest.approx((0.5, 1.0))
    assert "command_clamped" in sim.events


def test_sensor_frame_has_rgb_depth_imu_contract() -> None:
    frame = SensorFrame.synthetic(1.25, width=4, height=3)
    assert frame.frame_id == "camera_link"
    assert frame.rgb_shape == (3, 4, 3)
    assert frame.depth_shape == (3, 4)
    assert frame.imu_accel_mps2 == (0.0, 0.0, 9.81)


def test_smoke_test_reaches_target_without_collision() -> None:
    result = run_smoke_test(SimulationConfig(target=(1.0, 0.0), timeout_s=5.0))
    assert result["status"] == "completed"
    assert result["position_error_m"] < 0.08
    assert result["path_length_m"] > 0.9
    assert result["collision_count"] == 0
    assert result["evidence_class"] == "simulation_evidence"


def test_smoke_test_reports_collision_failure() -> None:
    cfg = SimulationConfig(target=(1.0, 0.0), obstacles=((0.25, -0.2, 0.25, 0.2),), timeout_s=2.0)
    result = run_smoke_test(cfg)
    assert result["status"] == "failed_collision"
    assert result["collision_count"] >= 1
