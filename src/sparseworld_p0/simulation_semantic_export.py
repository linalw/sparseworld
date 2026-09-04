"""Compact keyframe export shared by Isaac Sim and semantic backends."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np


def pose_matrix_from_odom(x: float, y: float, yaw: float, *, camera_height_m: float = 0.8) -> np.ndarray:
    matrix = np.eye(4, dtype=float)
    c, s = np.cos(float(yaw)), np.sin(float(yaw))
    matrix[:3, :3] = ((c, -s, 0.0), (s, c, 0.0), (0.0, 0.0, 1.0))
    matrix[:3, 3] = (float(x), float(y), float(camera_height_m))
    return matrix


def write_keyframe(output_dir: str | Path, *, frame_id: str, timestamp: str, rgb: np.ndarray, depth_m: np.ndarray, map_T_camera: np.ndarray) -> dict[str, Any]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    rgb_array = np.asarray(rgb, dtype=np.uint8)
    depth_array = np.asarray(depth_m, dtype=np.float32)
    if rgb_array.ndim != 3 or rgb_array.shape[2] != 3 or depth_array.ndim != 2 or rgb_array.shape[:2] != depth_array.shape:
        raise ValueError("RGB/depth keyframe shapes are incompatible")
    if np.asarray(map_T_camera).shape != (4, 4):
        raise ValueError("map_T_camera must be 4x4")
    rgb_path = root / f"{frame_id}.rgb.npy"
    depth_path = root / f"{frame_id}.depth.npy"
    np.save(rgb_path, rgb_array)
    np.save(depth_path, depth_array)
    return {"frame_id": frame_id, "timestamp": timestamp, "rgb_path": str(rgb_path), "depth_path": str(depth_path), "map_T_camera": np.asarray(map_T_camera, dtype=float).tolist()}


def build_manifest(output_dir: str | Path, *, intrinsics: Mapping[str, float], frames: Iterable[Mapping[str, Any]], simulation_truth: Mapping[str, Any] | None = None) -> dict[str, Any]:
    root = Path(output_dir)
    normalized = [dict(frame) for frame in frames]
    manifest: dict[str, Any] = {"schema_version": "p0/semantic-input/v1", "evidence_class": "simulation_evidence", "intrinsics": dict(intrinsics), "frames": normalized, "minimum_valid_depth_pixels": 20, "coordinate_frame": "initial_camera_map", "global_accuracy": "unvalidated"}
    if simulation_truth is not None:
        manifest["simulation_truth"] = dict(simulation_truth)
    encoded = json.dumps(manifest, sort_keys=True, ensure_ascii=False, indent=2).encode("utf-8")
    manifest["manifest_sha256"] = hashlib.sha256(encoded).hexdigest()
    root.mkdir(parents=True, exist_ok=True)
    (root / "semantic_manifest.json").write_text(json.dumps(manifest, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest
