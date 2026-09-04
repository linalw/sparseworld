import json
import sys
from pathlib import Path

import numpy as np
import pytest

from sparseworld_p0.semantic_backends import load_backend
from sparseworld_p0.semantic_mapping import LabelCandidate, SemanticObjectStore, SemanticObservation, build_semantic_map, project_mask_depth


def test_project_mask_depth_uses_median_valid_depth_and_intrinsics():
    """Breaks if projection stops rejecting invalid pixels or uses the wrong pinhole math."""
    depth_m = np.array([[0.0, 1.0], [1.2, 0.0]])
    mask = np.array([[False, True], [True, False]])

    result = project_mask_depth(
        mask,
        depth_m,
        {"fx": 100.0, "fy": 100.0, "cx": 0.0, "cy": 0.0},
        minimum_valid_pixels=2,
    )

    assert result.status == "projected"
    assert result.anchor_camera_xyz == pytest.approx((0.005, 0.006, 1.1))
    assert result.valid_depth_pixels == 2
    assert result.depth_valid_fraction == pytest.approx(1.0)


def test_project_mask_depth_rejects_insufficient_valid_depth():
    """Breaks if an all-invalid mask is accepted as a persistent 3D anchor."""
    result = project_mask_depth(
        np.ones((2, 2), dtype=bool),
        np.zeros((2, 2)),
        {"fx": 100.0, "fy": 100.0, "cx": 0.0, "cy": 0.0},
        minimum_valid_pixels=1,
    )

    assert result.status == "rejected"
    assert result.reason == "insufficient_valid_depth"


def _observation(label: str, anchor_xyz: tuple[float, float, float], frame_id: str) -> SemanticObservation:
    return SemanticObservation(
        frame_id=frame_id,
        timestamp="2026-09-02T12:00:00Z",
        anchor_xyz=anchor_xyz,
        frame="map",
        class_candidates=(LabelCandidate(label=label, probability=0.9),),
        confidence=0.9,
        depth_valid_fraction=0.8,
        valid_depth_pixels=120,
        model_metadata={"model_name": "fixture-labeler", "model_version": "1"},
    )


def test_store_merges_same_label_observations_at_same_position():
    """Breaks if a matching observation allocates a duplicate object ID."""
    store = SemanticObjectStore(spatial_gate_m=0.2, min_confirmations=3)

    first = store.upsert(_observation("cup", (1.0, 2.0, 0.5), "frame-1"))
    second = store.upsert(_observation("cup", (1.04, 2.0, 0.5), "frame-2"))
    document = store.as_document()

    assert first.action == "created"
    assert second.action == "updated"
    assert len(document["objects"]) == 1
    assert document["objects"][0]["object_id"] == "obj_cup_0001"
    assert len(document["objects"][0]["evidence"]) == 2


def test_store_keeps_same_class_objects_outside_spatial_gate_separate():
    """Breaks if the association gate merges distinct nearby objects only by class."""
    store = SemanticObjectStore(spatial_gate_m=0.2, min_confirmations=3)
    store.upsert(_observation("cup", (0.0, 0.0, 1.0), "frame-1"))
    store.upsert(_observation("cup", (0.5, 0.0, 1.0), "frame-2"))

    document = store.as_document()

    assert len(document["objects"]) == 2
    assert [item["object_id"] for item in document["objects"]] == ["obj_cup_0001", "obj_cup_0002"]


def test_store_marks_repeated_isolated_movable_observation_as_moved_without_duplicate():
    """Breaks if a moved object is cloned instead of updating its lifecycle."""
    store = SemanticObjectStore(spatial_gate_m=0.2, moved_gate_m=1.0, move_confirmations=2)
    store.upsert(_observation("cup", (0.0, 0.0, 1.0), "frame-1"))

    first_new_location = store.upsert(_observation("cup", (0.6, 0.0, 1.0), "frame-2"))
    second_new_location = store.upsert(_observation("cup", (0.62, 0.0, 1.0), "frame-3"))
    document = store.as_document()

    assert first_new_location.action == "pending_move"
    assert second_new_location.action == "moved"
    assert len(document["objects"]) == 1
    assert document["objects"][0]["lifecycle_status"] == "moved"
    assert document["objects"][0]["geometry"]["anchor_xyz"] == pytest.approx([0.62, 0.0, 1.0])


def test_build_semantic_map_deduplicates_two_fixture_frames(tmp_path):
    """Breaks if the offline pipeline creates one map object per frame."""
    rgb1 = tmp_path / "rgb1.npy"
    rgb2 = tmp_path / "rgb2.npy"
    depth1 = tmp_path / "depth1.npy"
    depth2 = tmp_path / "depth2.npy"
    np.save(rgb1, np.zeros((2, 2, 3), dtype=np.uint8))
    np.save(rgb2, np.zeros((2, 2, 3), dtype=np.uint8))
    np.save(depth1, np.ones((2, 2), dtype=np.float32))
    np.save(depth2, np.ones((2, 2), dtype=np.float32))
    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps({"masks": [{"mask": [[1, 1], [0, 0]], "labels": [{"label": "cup", "probability": 0.9}]}]}), encoding="utf-8")
    manifest = {
        "schema_version": "p0/semantic-input/v1",
        "intrinsics": {"fx": 100.0, "fy": 100.0, "cx": 0.0, "cy": 0.0},
        "frames": [
            {"frame_id": "frame-1", "timestamp": "2026-09-02T12:00:00Z", "rgb_path": str(rgb1), "depth_path": str(depth1), "map_T_camera": np.eye(4).tolist()},
            {"frame_id": "frame-2", "timestamp": "2026-09-02T12:00:01Z", "rgb_path": str(rgb2), "depth_path": str(depth2), "map_T_camera": np.eye(4).tolist()},
        ],
    }
    backend = load_backend("fixture", {"fixture_path": str(fixture)})

    document = build_semantic_map(manifest, backend)

    assert len(document["objects"]) == 1
    assert len(document["objects"][0]["evidence"]) == 2
    assert document["objects"][0]["lifecycle_status"] == "tentative"
    assert document["inference_runs"][0]["frames_processed"] == 2


def test_semantic_map_cli_writes_hash_bound_deduplicated_document(tmp_path: Path, monkeypatch):
    """Breaks if CLI bypasses association or fails to bind its JSON output hash."""
    rgb = tmp_path / "rgb.npy"
    depth = tmp_path / "depth.npy"
    np.save(rgb, np.zeros((2, 2, 3), dtype=np.uint8))
    np.save(depth, np.ones((2, 2), dtype=np.float32))
    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps({"masks": [{"mask": [[1, 1], [0, 0]], "labels": [{"label": "cup", "probability": 0.9}]}]}), encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"schema_version": "p0/semantic-input/v1", "intrinsics": {"fx": 100, "fy": 100, "cx": 0, "cy": 0}, "frames": [{"frame_id": "f1", "timestamp": "2026-09-02T12:00:00Z", "rgb_path": str(rgb), "depth_path": str(depth)}, {"frame_id": "f2", "timestamp": "2026-09-02T12:00:01Z", "rgb_path": str(rgb), "depth_path": str(depth)}]}), encoding="utf-8")
    output = tmp_path / "map.json"
    from sparseworld_p0 import cli
    monkeypatch.setattr(sys, "argv", ["sparseworld-p0", "semantic-map", "--manifest", str(manifest), "--backend", "fixture", "--fixture-path", str(fixture), "--output", str(output)])

    assert cli.main() == 0
    assert len(json.loads(output.read_text(encoding="utf-8"))["objects"]) == 1
    assert output.with_suffix(".json.sha256").is_file()
