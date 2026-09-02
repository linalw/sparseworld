"""Replaceable semantic perception backends with deterministic fixture support."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import numpy as np

from .semantic_mapping import LabelCandidate


@dataclass(frozen=True)
class MaskInstance:
    mask: np.ndarray
    score: float
    model_metadata: dict[str, Any]
    mask_id: str


@dataclass(frozen=True)
class BackendLabelCandidate(LabelCandidate):
    model_metadata: dict[str, Any]


class FixtureSemanticBackend:
    def __init__(self, entries: list[dict[str, Any]]) -> None:
        self._entries = entries

    @classmethod
    def from_json(cls, path: Path) -> "FixtureSemanticBackend":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("masks"), list):
            raise ValueError("fixture backend requires an object with a masks array")
        return cls(payload["masks"])

    def generate_masks(self, image: np.ndarray) -> list[MaskInstance]:
        if image.ndim != 3 or image.shape[2] != 3:
            raise ValueError("RGB image must have shape HxWx3")
        result = []
        for index, entry in enumerate(self._entries):
            if not isinstance(entry, dict) or not isinstance(entry.get("mask"), list):
                raise ValueError(f"fixture mask {index} is malformed")
            mask = np.asarray(entry["mask"], dtype=bool)
            if mask.shape != image.shape[:2]:
                raise ValueError(f"fixture mask {index} shape does not match image")
            result.append(MaskInstance(mask=mask, score=float(entry.get("score", 1.0)), mask_id=f"mask-{index:04d}", model_metadata={"model_name": "fixture-mask-generator", "model_version": "1", "weights_id": "fixture"}))
        return result

    def label(self, mask: MaskInstance, image: np.ndarray) -> list[BackendLabelCandidate]:
        index = int(mask.mask_id.split("-")[-1])
        labels = self._entries[index].get("labels", [])
        return [BackendLabelCandidate(label=str(item["label"]), probability=float(item["probability"]), model_metadata={"model_name": "fixture-labeler", "model_version": "1", "weights_id": "fixture"}) for item in labels]


def load_backend(kind: str, config: dict[str, Any]) -> FixtureSemanticBackend:
    if kind == "fixture":
        fixture_path = config.get("fixture_path")
        if not fixture_path:
            raise ValueError("fixture backend requires fixture_path")
        return FixtureSemanticBackend.from_json(Path(fixture_path))
    if kind in {"sam2_florence_siglip", "sam2"}:
        raise RuntimeError("semantic backend unavailable: install matching SAM 2/Florence-2/SigLIP dependencies and provide weights")
    raise ValueError(f"unknown semantic backend: {kind}")
