"""Deterministic RGB-D semantic observations and object association."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from pathlib import Path
from typing import Any, Mapping

import numpy as np


@dataclass(frozen=True)
class ProjectionResult:
    status: str
    anchor_camera_xyz: tuple[float, float, float] | None = None
    valid_depth_pixels: int = 0
    depth_valid_fraction: float = 0.0
    reason: str | None = None


@dataclass(frozen=True)
class LabelCandidate:
    label: str
    probability: float


@dataclass(frozen=True)
class SemanticObservation:
    frame_id: str
    timestamp: str
    anchor_xyz: tuple[float, float, float]
    frame: str
    class_candidates: tuple[LabelCandidate, ...]
    confidence: float
    depth_valid_fraction: float
    valid_depth_pixels: int
    model_metadata: Mapping[str, Any] = field(default_factory=dict)
    mask_area: int | None = None
    image_crop_uri: str | None = None


@dataclass(frozen=True)
class AssociationResult:
    action: str
    object_id: str


@dataclass
class _StoredObject:
    object_id: str
    label: str
    anchor_xyz: tuple[float, float, float]
    confidence: float
    state: str
    lifecycle_status: str
    evidence: list[dict[str, Any]] = field(default_factory=list)
    observation_count: int = 0
    frame_ids: set[str] = field(default_factory=set)
    pending_move_anchor: tuple[float, float, float] | None = None
    pending_move_count: int = 0


class SemanticObjectStore:
    """In-memory persistent object index with deterministic spatial deduplication."""

    def __init__(
        self,
        *,
        spatial_gate_m: float = 0.20,
        moved_gate_m: float | None = None,
        min_confirmations: int = 3,
        min_distinct_frames: int = 2,
        move_confirmations: int = 2,
    ) -> None:
        resolved_moved_gate_m = spatial_gate_m if moved_gate_m is None else moved_gate_m
        if spatial_gate_m <= 0 or resolved_moved_gate_m < spatial_gate_m:
            raise ValueError("moved_gate_m must be >= spatial_gate_m > 0")
        self.spatial_gate_m = float(spatial_gate_m)
        self.moved_gate_m = float(resolved_moved_gate_m)
        self.min_confirmations = int(min_confirmations)
        self.min_distinct_frames = int(min_distinct_frames)
        self.move_confirmations = int(move_confirmations)
        self._objects: list[_StoredObject] = []
        self._next_ids: dict[str, int] = {}

    def upsert(self, observation: SemanticObservation) -> AssociationResult:
        if not observation.class_candidates:
            raise ValueError("observation requires at least one class candidate")
        label = _normalise_label(observation.class_candidates[0].label)
        nearest: tuple[float, _StoredObject] | None = None
        for item in self._objects:
            if item.lifecycle_status == "removed" or item.label != label:
                continue
            distance = _distance(item.anchor_xyz, observation.anchor_xyz)
            if distance <= self.spatial_gate_m and (nearest is None or distance < nearest[0] or (distance == nearest[0] and item.object_id < nearest[1].object_id)):
                nearest = (distance, item)
        if nearest is not None:
            item = nearest[1]
            item.anchor_xyz = _weighted_anchor(item.anchor_xyz, item.observation_count, observation.anchor_xyz)
            item.confidence = max(item.confidence, float(observation.confidence))
            item.observation_count += 1
            item.frame_ids.add(observation.frame_id)
            item.pending_move_anchor = None
            item.pending_move_count = 0
            if item.observation_count >= self.min_confirmations and len(item.frame_ids) >= self.min_distinct_frames:
                item.lifecycle_status = "confirmed"
            item.evidence.append(_evidence(observation))
            return AssociationResult("updated", item.object_id)

        moved: tuple[float, _StoredObject] | None = None
        for item in self._objects:
            if item.lifecycle_status == "removed" or item.label != label:
                continue
            distance = _distance(item.anchor_xyz, observation.anchor_xyz)
            if distance <= self.moved_gate_m and (moved is None or distance < moved[0] or (distance == moved[0] and item.object_id < moved[1].object_id)):
                moved = (distance, item)
        if moved is not None:
            item = moved[1]
            if item.pending_move_anchor is not None and _distance(item.pending_move_anchor, observation.anchor_xyz) <= self.spatial_gate_m:
                item.pending_move_count += 1
            else:
                item.pending_move_anchor = observation.anchor_xyz
                item.pending_move_count = 1
            item.observation_count += 1
            item.frame_ids.add(observation.frame_id)
            item.evidence.append(_evidence(observation))
            if item.pending_move_count >= self.move_confirmations:
                item.anchor_xyz = observation.anchor_xyz
                item.lifecycle_status = "moved"
                item.pending_move_anchor = None
                item.pending_move_count = 0
                return AssociationResult("moved", item.object_id)
            return AssociationResult("pending_move", item.object_id)

        object_id = self._allocate_id(label)
        item = _StoredObject(
            object_id=object_id,
            label=label,
            anchor_xyz=observation.anchor_xyz,
            confidence=float(observation.confidence),
            state="movable",
            lifecycle_status="tentative",
            evidence=[_evidence(observation)],
            observation_count=1,
            frame_ids={observation.frame_id},
        )
        self._objects.append(item)
        return AssociationResult("created", object_id)

    def as_document(self) -> dict[str, Any]:
        objects = []
        for item in self._objects:
            objects.append({
                "object_id": item.object_id,
                "class_candidates": [{"label": item.label, "probability": round(item.confidence, 6)}],
                "geometry": {"anchor_xyz": [round(value, 9) for value in item.anchor_xyz], "geometry_type": "anchor_only", "geometry_quality": "coarse"},
                "state": item.state,
                "lifecycle_status": item.lifecycle_status,
                "confidence": round(item.confidence, 6),
                "retention": "persistent_compact",
                "evidence": list(item.evidence),
            })
        return {
            "schema_version": "p0/semantic-world-observations/v1",
            "map_frame": {"name": "map", "units": "m", "axis_convention": "x_forward_or_building_east_y_left_or_building_north_z_up", "origin_definition": "first reliable pose; not an external building datum"},
            "objects": objects,
            "inference_runs": [],
            "association_config": {"spatial_gate_m": self.spatial_gate_m, "moved_gate_m": self.moved_gate_m, "min_confirmations": self.min_confirmations, "min_distinct_frames": self.min_distinct_frames, "move_confirmations": self.move_confirmations},
        }

    def _allocate_id(self, label: str) -> str:
        self._next_ids[label] = self._next_ids.get(label, 0) + 1
        return f"obj_{label}_{self._next_ids[label]:04d}"


def _normalise_label(label: str) -> str:
    cleaned = "_".join(str(label).strip().lower().split())
    return cleaned or "unknown"


def _distance(first: tuple[float, float, float], second: tuple[float, float, float]) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(first, second)))


def _weighted_anchor(old: tuple[float, float, float], count: int, new: tuple[float, float, float]) -> tuple[float, float, float]:
    weight = max(count, 1)
    return tuple((weight * before + after) / (weight + 1) for before, after in zip(old, new))


def _evidence(observation: SemanticObservation) -> dict[str, Any]:
    result = {"source_type": "rgb", "timestamp": observation.timestamp, "keyframe_id": observation.frame_id, "score": round(float(observation.confidence), 6), "frame": observation.frame, "depth_valid_fraction": round(float(observation.depth_valid_fraction), 6), "valid_depth_pixels": int(observation.valid_depth_pixels), "model": dict(observation.model_metadata)}
    if observation.mask_area is not None:
        result["mask_area"] = int(observation.mask_area)
    if observation.image_crop_uri:
        result["image_crop_uri"] = observation.image_crop_uri
    return result


def project_mask_depth(
    mask: np.ndarray,
    depth_m: np.ndarray,
    intrinsics: Mapping[str, float],
    minimum_valid_pixels: int = 20,
) -> ProjectionResult:
    """Project valid mask pixels through a pinhole camera using robust medians."""
    mask_array = np.asarray(mask)
    depth_array = np.asarray(depth_m, dtype=float)
    if mask_array.ndim != 2 or depth_array.ndim != 2 or mask_array.shape != depth_array.shape:
        return ProjectionResult(status="rejected", reason="invalid_image_shape")
    if minimum_valid_pixels < 1:
        raise ValueError("minimum_valid_pixels must be positive")
    try:
        fx, fy = float(intrinsics["fx"]), float(intrinsics["fy"])
        cx, cy = float(intrinsics["cx"]), float(intrinsics["cy"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("intrinsics must contain numeric fx, fy, cx, cy") from error
    if not all(np.isfinite(value) and value > 0 for value in (fx, fy)):
        raise ValueError("intrinsics focal lengths must be finite and positive")
    selected = mask_array.astype(bool)
    valid = selected & np.isfinite(depth_array) & (depth_array > 0)
    valid_count = int(np.count_nonzero(valid))
    mask_count = int(np.count_nonzero(selected))
    fraction = valid_count / mask_count if mask_count else 0.0
    if valid_count < minimum_valid_pixels:
        return ProjectionResult(
            status="rejected", valid_depth_pixels=valid_count,
            depth_valid_fraction=fraction, reason="insufficient_valid_depth",
        )
    rows, columns = np.nonzero(valid)
    depths = depth_array[valid]
    z = float(np.median(depths))
    x = float(np.median((columns - cx) * depths / fx))
    y = float(np.median((rows - cy) * depths / fy))
    return ProjectionResult(
        status="projected", anchor_camera_xyz=(x, y, z),
        valid_depth_pixels=valid_count, depth_valid_fraction=fraction,
    )


def build_semantic_map(manifest: Mapping[str, Any], backend: Any) -> dict[str, Any]:
    """Run a backend over an offline RGB-D manifest and return an audited map."""
    if manifest.get("schema_version") != "p0/semantic-input/v1":
        raise ValueError("semantic manifest schema_version must be p0/semantic-input/v1")
    intrinsics = manifest.get("intrinsics")
    frames = manifest.get("frames")
    if not isinstance(intrinsics, Mapping) or not isinstance(frames, list):
        raise ValueError("semantic manifest requires intrinsics and frames")
    store = SemanticObjectStore()
    inference_runs: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for frame in frames:
        if not isinstance(frame, Mapping):
            raise ValueError("each semantic frame must be an object")
        rgb = np.load(Path(frame["rgb_path"]))
        depth = np.load(Path(frame["depth_path"]))
        masks = backend.generate_masks(rgb)
        for mask_instance in masks:
            labels = backend.label(mask_instance, rgb)
            if not labels:
                rejected.append({"frame_id": frame.get("frame_id"), "mask_id": mask_instance.mask_id, "reason": "no_label_candidate"})
                continue
            projection = project_mask_depth(mask_instance.mask, depth, intrinsics, minimum_valid_pixels=int(manifest.get("minimum_valid_depth_pixels", 1)))
            if projection.status != "projected":
                rejected.append({"frame_id": frame.get("frame_id"), "mask_id": mask_instance.mask_id, "reason": projection.reason})
                continue
            anchor = _transform_point(projection.anchor_camera_xyz, frame.get("map_T_camera"), frame.get("map_frame", "map"))
            observation = SemanticObservation(
                frame_id=str(frame["frame_id"]), timestamp=str(frame["timestamp"]), anchor_xyz=anchor, frame=str(frame.get("map_frame", "map")),
                class_candidates=tuple(LabelCandidate(label=item.label, probability=item.probability) for item in labels), confidence=float(labels[0].probability),
                depth_valid_fraction=projection.depth_valid_fraction, valid_depth_pixels=projection.valid_depth_pixels,
                model_metadata={"mask": mask_instance.model_metadata, "label": labels[0].model_metadata}, mask_area=int(np.count_nonzero(mask_instance.mask)),
            )
            store.upsert(observation)
    document = store.as_document()
    document["inference_runs"] = [{"backend": type(backend).__name__, "frames_processed": len(frames), "rejected_observations": rejected}]
    return document


def _transform_point(point: tuple[float, float, float], transform: Any, frame: str) -> tuple[float, float, float]:
    if transform is None:
        return point
    matrix = np.asarray(transform, dtype=float)
    if matrix.shape != (4, 4) or not np.all(np.isfinite(matrix)):
        raise ValueError("map_T_camera must be a finite 4x4 matrix")
    result = matrix @ np.array([*point, 1.0], dtype=float)
    if abs(result[3]) < 1e-12:
        raise ValueError("map_T_camera produced invalid homogeneous coordinate")
    return tuple(float(value / result[3]) for value in result[:3])
