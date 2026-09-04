"""Evidence summarization for Isaac Sim ROS smoke runs."""
from __future__ import annotations

import math

REQUIRED_TOPICS = ("rgb", "depth", "camera_info", "imu", "odom", "tf")


def summarize_isaac_run(*, scene: str, duration_s: float, topic_counts: dict[str, int], commanded_distance_m: float, measured_distance_m: float) -> dict[str, object]:
    if not scene or not math.isfinite(float(duration_s)) or duration_s <= 0:
        raise ValueError("scene and positive duration_s are required")
    contract = {topic: int(topic_counts.get(topic, 0)) > 0 for topic in REQUIRED_TOPICS}
    motion_observed = int(topic_counts.get("odom", 0)) > 0 and abs(float(measured_distance_m)) > 1e-6
    distance_error = abs(float(commanded_distance_m) - float(measured_distance_m))
    status = "executed_unverified" if all(contract.values()) and motion_observed else "incomplete_sensor_contract"
    return {
        "evidence_class": "simulation_evidence",
        "status": status,
        "scene": scene,
        "duration_s": float(duration_s),
        "topic_counts": {k: int(v) for k, v in sorted(topic_counts.items())},
        "sensor_contract": contract,
        "motion_execution": {"observed": motion_observed, "commanded_distance_m": float(commanded_distance_m), "measured_distance_m": float(measured_distance_m), "distance_error_m": distance_error},
        "navigation_acceptance": "unvalidated",
        "physical_traversability": "unvalidated",
    }
