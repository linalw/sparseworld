import json
from pathlib import Path

import numpy as np

from sparseworld_p0.simulation_semantic_export import build_manifest, pose_matrix_from_odom, write_keyframe


def test_pose_matrix_keeps_map_coordinates_in_meter_units() -> None:
    matrix = pose_matrix_from_odom(1.5, -0.25, 0.4, camera_height_m=0.8)
    assert matrix[:3, 3].tolist() == [1.5, -0.25, 0.8]
    assert matrix[0, 0] == np.cos(0.4)


def test_keyframe_export_builds_hashable_semantic_manifest(tmp_path: Path) -> None:
    frame = write_keyframe(
        tmp_path,
        frame_id="sim_000001",
        timestamp="2026-09-04T10:00:00Z",
        rgb=np.zeros((2, 3, 3), dtype=np.uint8),
        depth_m=np.ones((2, 3), dtype=np.float32),
        map_T_camera=np.eye(4),
    )
    manifest = build_manifest(
        tmp_path,
        intrinsics={"fx": 100.0, "fy": 100.0, "cx": 1.0, "cy": 1.0},
        frames=[frame],
        simulation_truth={"object_id": "target_object", "class": "target_object"},
    )
    assert manifest["schema_version"] == "p0/semantic-input/v1"
    assert manifest["evidence_class"] == "simulation_evidence"
    assert Path(frame["rgb_path"]).is_file()
    assert Path(frame["depth_path"]).is_file()
    assert manifest["frames"][0]["frame_id"] == "sim_000001"
