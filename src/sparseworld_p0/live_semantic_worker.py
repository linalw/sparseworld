"""Persistent, load-shed semantic association for live RGB-D keyframes.

This module deliberately receives only gated keyframes.  It never subscribes
to a camera stream, which makes the one-slot queue the sole load-shedding
boundary for expensive segmentation and labelling models.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .semantic_mapping import (
    InitialPoseFrame,
    LabelCandidate,
    SemanticObjectStore,
    SemanticObservation,
    _transform_point,
    project_mask_depth,
)


def atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.stem}-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


class LiveSemanticProcessor:
    """Turn pose-qualified RGB-D keyframes into a compact object document."""

    def __init__(self, backend: Any, *, output_dir: str | Path, minimum_valid_depth_pixels: int = 20) -> None:
        if minimum_valid_depth_pixels < 1:
            raise ValueError("minimum_valid_depth_pixels must be positive")
        self.backend = backend
        self.output_dir = Path(output_dir)
        self.minimum_valid_depth_pixels = minimum_valid_depth_pixels
        self.store = SemanticObjectStore()
        self._processed_ids: set[str] = set()
        self._processed = 0
        self._duplicates = 0
        self._rejected = 0
        self._pose_unavailable = 0
        self._errors = 0
        self._last_error: str | None = None
        self._rgb_depth_shape_mismatch = 0
        self.initial_pose: InitialPoseFrame | None = None
        self._trajectory: list[dict[str, Any]] = []

    def set_initial_pose(self, map_T_camera: Any, *, reference_frame: str = "map") -> InitialPoseFrame:
        """Freeze the requested local coordinate frame at the first valid pose."""
        if self.initial_pose is None:
            self.initial_pose = InitialPoseFrame.from_map_T_camera(map_T_camera, reference_frame=reference_frame)
        return self.initial_pose

    def record_pose(self, keyframe_id: str, timestamp: str, local_T_camera: Any) -> None:
        matrix = np.asarray(local_T_camera, dtype=float)
        if matrix.shape != (4, 4) or not np.all(np.isfinite(matrix)):
            return
        if self._trajectory and self._trajectory[-1]["keyframe_id"] == keyframe_id:
            return
        self._trajectory.append({"keyframe_id": keyframe_id, "timestamp": timestamp, "position_xyz": [round(float(value), 9) for value in matrix[:3, 3]]})

    def process(
        self,
        keyframe_id: str,
        timestamp: str,
        rgb: np.ndarray,
        depth: np.ndarray,
        intrinsics: Mapping[str, Any],
        *,
        map_T_camera: Any = None,
        pose_frame: str | None = None,
    ) -> bool:
        """Process a keyframe once; false means an already-seen input.

        Persistent world-object association requires a valid ``map_T_camera``.
        Inputs lacking it are counted and retained only as keyframe evidence by
        the bridge; they are not mislabeled as global map objects.
        """
        if keyframe_id in self._processed_ids:
            self._duplicates += 1
            return False
        self._processed_ids.add(keyframe_id)
        self._processed += 1
        if np.asarray(rgb).ndim >= 2 and np.asarray(depth).ndim >= 2 and np.asarray(rgb).shape[:2] != np.asarray(depth).shape[:2]:
            self._rgb_depth_shape_mismatch += 1
            self._rejected += 1
            return True
        if map_T_camera is None:
            self._pose_unavailable += 1
            return True
        self.record_pose(keyframe_id, timestamp, map_T_camera)
        try:
            depth_m = np.asarray(depth, dtype=np.float32) * float(intrinsics.get("depth_unit_m", 0.001))
            masks = self.backend.generate_masks(rgb)
            for mask_instance in masks:
                labels = self.backend.label(mask_instance, rgb)
                if not labels:
                    self._rejected += 1
                    continue
                projection = project_mask_depth(
                    mask_instance.mask, depth_m, intrinsics,
                    minimum_valid_pixels=self.minimum_valid_depth_pixels,
                )
                if projection.status != "projected":
                    self._rejected += 1
                    continue
                anchor = _transform_point(projection.anchor_camera_xyz, map_T_camera, "map")
                primary = labels[0]
                self.store.upsert(SemanticObservation(
                    frame_id=keyframe_id,
                    timestamp=timestamp,
                    anchor_xyz=anchor,
                    frame=pose_frame or "map",
                    class_candidates=tuple(LabelCandidate(label=item.label, probability=item.probability) for item in labels),
                    confidence=float(primary.probability),
                    depth_valid_fraction=projection.depth_valid_fraction,
                    valid_depth_pixels=projection.valid_depth_pixels,
                    model_metadata={"mask": mask_instance.model_metadata, "label": primary.model_metadata},
                    mask_area=int(np.count_nonzero(mask_instance.mask)),
                ))
        except Exception as exc:
            self._errors += 1
            self._last_error = f"{type(exc).__name__}: {exc}"
        return True

    def snapshot(self) -> dict[str, Any]:
        return {
            "status": "running",
            "processed": self._processed,
            "duplicates": self._duplicates,
            "rejected": self._rejected,
            "pose_unavailable": self._pose_unavailable,
            "errors": self._errors,
            "last_error": self._last_error,
            "rgb_depth_shape_mismatch": self._rgb_depth_shape_mismatch,
            "global_accuracy": "unvalidated",
        }

    def document(self) -> dict[str, Any]:
        document = self.store.as_document()
        if self.initial_pose:
            document["map_frame"] = self.initial_pose.as_document()
        document["inference_runs"] = [{
            "backend": type(self.backend).__name__,
            "keyframes_processed": self._processed,
            "duplicates_ignored": self._duplicates,
            "rejected_observations": self._rejected,
            "pose_unavailable": self._pose_unavailable,
            "errors": self._errors,
            "global_accuracy": "unvalidated",
        }]
        return document

    def persist(self) -> None:
        atomic_json(self.output_dir / "objects.json", self.document())
        atomic_json(self.output_dir / "trajectory.json", {
            "schema_version": "p0/live-semantic-trajectory/v1",
            "coordinate_frame": self.initial_pose.as_document() if self.initial_pose else None,
            "poses": list(self._trajectory),
            "global_accuracy": "unvalidated",
        })
