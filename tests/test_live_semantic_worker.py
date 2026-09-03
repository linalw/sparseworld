import json
from pathlib import Path

import numpy as np

from sparseworld_p0.live_semantic_worker import LiveSemanticProcessor
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
