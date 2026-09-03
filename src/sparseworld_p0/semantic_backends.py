"""Replaceable semantic perception backends with deterministic fixture support."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any
import time

import numpy as np

from .semantic_mapping import LabelCandidate

DEFAULT_MASK_MODEL_ID = "facebook/sam-vit-base"
DEFAULT_LABEL_MODEL_ID = "microsoft/Florence-2-base"


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


class HuggingFaceSemanticBackend:
    """Lazy Hugging Face mask + image-to-text backend.

    The adapter intentionally loads no weights at import time. It accepts any
    transformers pipeline that returns standard mask-generation or
    image-to-text structures, allowing SAM/SAM2 and Florence-2-compatible
    checkpoints to be pinned by the operator.
    """

    def __init__(self, *, mask_model_id: str, label_model_id: str, device: int = 0) -> None:
        try:
            from transformers import pipeline
        except (ImportError, ModuleNotFoundError) as error:
            raise RuntimeError("semantic backend unavailable: install the semantic extra with torch and transformers") from error
        self._mask_model_id = mask_model_id
        self._label_model_id = label_model_id
        try:
            self._mask_pipeline = pipeline("mask-generation", model=mask_model_id, device=device)
            self._florence = label_model_id.lower().startswith("microsoft/florence-2-")
            if self._florence:
                from transformers import AutoModelForCausalLM, AutoProcessor
                import torch
                self._torch = torch
                self._label_processor = AutoProcessor.from_pretrained(label_model_id, trust_remote_code=True)
                self._label_model = AutoModelForCausalLM.from_pretrained(label_model_id, trust_remote_code=True).eval()
                self._label_device = torch.device("cpu" if device < 0 else f"cuda:{device}")
                self._label_model.to(self._label_device)
            else:
                self._florence = False
                self._label_pipeline = pipeline("image-text-to-text", model=label_model_id, device=device, trust_remote_code=True)
        except Exception as error:
            raise RuntimeError(
                "semantic backend unavailable: unable to load the requested model runtime or weights "
                f"({type(error).__name__}: {error})"
            ) from error
        self._mask_counter = 0

    def generate_masks(self, image: np.ndarray) -> list[MaskInstance]:
        if image.ndim != 3 or image.shape[2] != 3:
            raise ValueError("RGB image must have shape HxWx3")
        from PIL import Image
        started = time.perf_counter()
        outputs = self._mask_pipeline(Image.fromarray(image))
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if isinstance(outputs, dict) and isinstance(outputs.get("masks"), list):
            masks = outputs["masks"]
            scores = outputs.get("scores", [1.0] * len(masks))
            outputs = [{"mask": mask, "score": score} for mask, score in zip(masks, scores)]
        elif not isinstance(outputs, list):
            outputs = [outputs]
        result = []
        for output in outputs:
            raw_mask = output.get("mask") if isinstance(output, dict) else None
            if raw_mask is None:
                continue
            mask = np.asarray(raw_mask, dtype=bool)
            if mask.shape != image.shape[:2]:
                raise ValueError("mask-generation pipeline returned a mask with the wrong shape")
            self._mask_counter += 1
            result.append(MaskInstance(mask=mask, score=float(output.get("score", 1.0)), mask_id=f"mask-{self._mask_counter:04d}", model_metadata={"model_name": "huggingface-mask-generation", "model_version": "transformers", "weights_id": self._mask_model_id, "latency_ms": round(elapsed_ms, 3)}))
        return result

    def label(self, mask: MaskInstance, image: np.ndarray) -> list[BackendLabelCandidate]:
        from PIL import Image
        masked = np.where(mask.mask[..., None], image, 0).astype(np.uint8)
        started = time.perf_counter()
        if self._florence:
            prompt = "<CAPTION>"
            inputs = self._label_processor(text=prompt, images=Image.fromarray(masked), return_tensors="pt")
            inputs = {name: value.to(self._label_device) for name, value in inputs.items()}
            with self._torch.inference_mode():
                generated = self._label_model.generate(**inputs, max_new_tokens=32, num_beams=3)
            generated_text = self._label_processor.batch_decode(generated, skip_special_tokens=False)[0]
            parsed = self._label_processor.post_process_generation(generated_text, task=prompt, image_size=(image.shape[1], image.shape[0]))
            text = str(parsed.get(prompt, generated_text)) if isinstance(parsed, dict) else str(parsed)
        else:
            try:
                outputs = self._label_pipeline(text="What is the main object in this image?", images=Image.fromarray(masked), max_new_tokens=32)
            except (TypeError, ValueError):
                outputs = self._label_pipeline(Image.fromarray(masked), max_new_tokens=32)
            text = ""
            if isinstance(outputs, list) and outputs and isinstance(outputs[0], dict):
                text = str(outputs[0].get("generated_text", outputs[0].get("text", "")))
            elif outputs:
                text = str(outputs)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        label = _normalise_generated_label(text)
        return [BackendLabelCandidate(label=label, probability=0.7 if label != "unknown" else 0.0, model_metadata={"model_name": "florence-2", "model_version": "transformers", "weights_id": self._label_model_id, "latency_ms": round(elapsed_ms, 3)})]


def load_backend(kind: str, config: dict[str, Any]) -> Any:
    if kind == "fixture":
        fixture_path = config.get("fixture_path")
        if not fixture_path:
            raise ValueError("fixture backend requires fixture_path")
        return FixtureSemanticBackend.from_json(Path(fixture_path))
    if kind in {"sam2_florence_siglip", "sam2"}:
        mask_model_id = config.get("mask_model_id", DEFAULT_MASK_MODEL_ID)
        label_model_id = config.get("label_model_id", DEFAULT_LABEL_MODEL_ID)
        return HuggingFaceSemanticBackend(mask_model_id=mask_model_id, label_model_id=label_model_id, device=int(config.get("device", 0)))
    raise ValueError(f"unknown semantic backend: {kind}")


def _normalise_generated_label(text: str) -> str:
    prompt = "describe the object in this image with one short noun phrase."
    cleaned = text.strip()
    if cleaned.lower().startswith(prompt):
        cleaned = cleaned[len(prompt):].strip()
    cleaned = cleaned.split("\n", 1)[0].strip(" .,:;-")
    return cleaned or "unknown"
