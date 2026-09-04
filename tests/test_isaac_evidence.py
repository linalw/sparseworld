import pytest
from sparseworld_p0.isaac_evidence import summarize_isaac_run


def test_marks_sensor_contract_incomplete_when_imu_is_not_observed() -> None:
    result = summarize_isaac_run(
        scene="carter_warehouse_navigation.usd",
        duration_s=4.0,
        topic_counts={"rgb": 12, "depth": 12, "camera_info": 12, "imu": 0, "odom": 50, "tf": 50},
        commanded_distance_m=0.8,
        measured_distance_m=0.7,
    )
    assert result["status"] == "incomplete_sensor_contract"
    assert result["evidence_class"] == "simulation_evidence"
    assert result["sensor_contract"]["imu"] is False


def test_marks_motion_execution_when_topics_and_motion_are_observed() -> None:
    result = summarize_isaac_run(
        scene="carter_warehouse_navigation.usd",
        duration_s=4.0,
        topic_counts={"rgb": 12, "depth": 12, "camera_info": 12, "imu": 12, "odom": 50, "tf": 50},
        commanded_distance_m=0.8,
        measured_distance_m=0.7,
    )
    assert result["status"] == "executed_unverified"
    assert result["motion_execution"]["observed"] is True
    assert result["motion_execution"]["distance_error_m"] == pytest.approx(0.1)
