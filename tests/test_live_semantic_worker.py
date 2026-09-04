import json
from pathlib import Path

import numpy as np

from sparseworld_p0.live_semantic_worker import LiveSemanticProcessor
from sparseworld_p0.semantic_mapping import InitialPoseFrame
from sparseworld_p0.semantic_backends import FixtureSemanticBackend


def _backend() -> FixtureSemanticBackend:
    return FixtureSemanticBackend([{
        "mask": [[True, True], [True, True]],
        "labels": [{"label": "cup", "probability": 0.9}],
    }])


def test_processor_deduplicates_replayed_keyframe_and_persists_objects(tmp_path: Path):
    processor = LiveSemanticProcessor(_backend(), output_dir=tmp_path, minimum_valid_depth_pixels=1)
    rgb = np.zeros((2, 2, 3), dtype=np.uint8)
    depth_mm = np.full((2, 2), 1000, dtype=np.uint16)
    metadata = {"fx": 100.0, "fy": 100.0, "cx": 0.0, "cy": 0.0}

    pose = np.eye(4).tolist()
    assert processor.process("kf-000001", "2026-09-03T00:00:00Z", rgb, depth_mm, metadata, map_T_camera=pose)
    assert not processor.process("kf-000001", "2026-09-03T00:00:00Z", rgb, depth_mm, metadata, map_T_camera=pose)
    processor.persist()

    document = json.loads((tmp_path / "objects.json").read_text())
    assert len(document["objects"]) == 1
    assert document["objects"][0]["object_id"] == "obj_cup_0001"
    assert processor.snapshot()["processed"] == 1
    assert processor.snapshot()["duplicates"] == 1


def test_processor_records_rejected_depth_and_backend_failures(tmp_path: Path):
    processor = LiveSemanticProcessor(_backend(), output_dir=tmp_path, minimum_valid_depth_pixels=3)
    rgb = np.zeros((2, 2, 3), dtype=np.uint8)
    depth_mm = np.zeros((2, 2), dtype=np.uint16)
    assert processor.process("kf-000001", "2026-09-03T00:00:00Z", rgb, depth_mm, {"fx": 100, "fy": 100, "cx": 0, "cy": 0}, map_T_camera=np.eye(4).tolist())
    stats = processor.snapshot()
    assert stats["processed"] == 1
    assert stats["rejected"] == 1


def test_processor_explicitly_counts_rgb_depth_shape_mismatch(tmp_path: Path):
    processor = LiveSemanticProcessor(_backend(), output_dir=tmp_path, minimum_valid_depth_pixels=1)
    rgb = np.zeros((2, 2, 3), dtype=np.uint8)
    depth_mm = np.full((1, 2), 1000, dtype=np.uint16)
    processor.process("kf-000001", "2026-09-03T00:00:00Z", rgb, depth_mm, {"fx": 100, "fy": 100, "cx": 0, "cy": 0}, map_T_camera=np.eye(4).tolist())
    assert processor.snapshot()["rgb_depth_shape_mismatch"] == 1


def test_initial_pose_frame_places_first_camera_at_origin_and_heading_forward():
    pose = np.array([
        [0.0, -1.0, 0.0, 10.0],
        [1.0, 0.0, 0.0, 20.0],
        [0.0, 0.0, 1.0, 1.5],
        [0.0, 0.0, 0.0, 1.0],
    ])

    origin = InitialPoseFrame.from_map_T_camera(pose)

    assert np.allclose(origin.local_T_map @ pose, np.eye(4))
    assert origin.as_document()["origin_definition"] == "first_valid_map_T_camera_position_and_horizontal_heading"
    assert origin.as_document()["axis_convention"].startswith("x_forward_at_initial_camera_heading")


def test_initial_pose_frame_retains_the_single_reference_frame_used_for_all_coordinates():
    origin = InitialPoseFrame.from_map_T_camera(np.eye(4), reference_frame="odom")

    assert origin.as_document()["slam_reference_frame"] == "odom"


def test_processor_writes_objects_in_initial_camera_frame(tmp_path: Path):
    processor = LiveSemanticProcessor(_backend(), output_dir=tmp_path, minimum_valid_depth_pixels=1)
    rgb = np.zeros((2, 2, 3), dtype=np.uint8)
    depth_mm = np.full((2, 2), 1000, dtype=np.uint16)
    map_T_camera = np.array([
        [0.0, -1.0, 0.0, 10.0],
        [1.0, 0.0, 0.0, 20.0],
        [0.0, 0.0, 1.0, 1.5],
        [0.0, 0.0, 0.0, 1.0],
    ])
    processor.set_initial_pose(map_T_camera)
    local_T_camera = processor.initial_pose.local_T_map @ map_T_camera

    assert processor.process("kf-000001", "2026-09-03T00:00:00Z", rgb, depth_mm, {"fx": 100, "fy": 100, "cx": 0, "cy": 0}, map_T_camera=local_T_camera)
    document = processor.document()

    assert document["map_frame"]["name"] == "initial_camera_map"
    # The fixture mask projects slightly right/down of the optical centre;
    # importantly that anchor is expressed relative to the frozen first pose.
    assert document["objects"][0]["geometry"]["anchor_xyz"] == [0.005, 0.005, 1.0]
