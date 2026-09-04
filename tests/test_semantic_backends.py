import json
from pathlib import Path

import numpy as np
import pytest

from sparseworld_p0.semantic_backends import _normalise_generated_label, _object_rgb_crop, load_backend


def test_fixture_backend_returns_masks_and_labels_with_audit_metadata(tmp_path: Path):
    """Breaks if fixture inference loses mask/label provenance needed for audit."""
    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps({"masks": [{"mask": [[1, 1], [0, 0]], "labels": [{"label": "cup", "probability": 0.9}]}]}), encoding="utf-8")
    backend = load_backend("fixture", {"fixture_path": str(fixture)})

    masks = backend.generate_masks(np.zeros((2, 2, 3), dtype=np.uint8))
    labels = backend.label(masks[0], np.zeros((2, 2, 3), dtype=np.uint8))

    assert masks[0].model_metadata["model_name"] == "fixture-mask-generator"
    assert labels[0].label == "cup"
    assert labels[0].model_metadata["model_name"] == "fixture-labeler"


def test_real_model_backend_fails_closed_without_explicit_runtime(tmp_path: Path):
    import sparseworld_p0.semantic_backends as module
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setitem(__import__("sys").modules, "transformers", None)
    with pytest.raises(RuntimeError, match="semantic backend unavailable"):
        load_backend("sam2_florence_siglip", {"weights_dir": str(tmp_path)})
    monkeypatch.undo()


def test_huggingface_backend_records_requested_model_ids_without_loading_weights(monkeypatch):
    """Breaks if real-backend configuration silently ignores the pinned model IDs."""
    captured = []

    class FakeTransformers:
        @staticmethod
        def pipeline(task, model, device, **kwargs):
            captured.append((task, model, device, kwargs))
            return lambda *args, **kwargs: []

    monkeypatch.setitem(__import__("sys").modules, "transformers", FakeTransformers)
    backend = load_backend("sam2_florence_siglip", {"mask_model_id": "org/mask", "label_model_id": "org/label", "device": -1})

    assert backend._mask_model_id == "org/mask"
    assert backend._label_model_id == "org/label"
    assert captured == [("mask-generation", "org/mask", -1, {}), ("image-text-to-text", "org/label", -1, {"trust_remote_code": True})]


def test_default_label_model_is_florence_two():
    import sparseworld_p0.semantic_backends as module
    assert module.DEFAULT_LABEL_MODEL_ID == "microsoft/Florence-2-base"


def test_generated_label_removes_the_image_to_text_prompt_echo():
    """Breaks if prompt text becomes a semantic label in the persistent map."""
    assert _normalise_generated_label("Describe the object in this image with one short noun phrase. checker") == "checker"


def test_generated_label_rejects_florence_prompt_echo():
    assert _normalise_generated_label("What is the main object in this image?") == "unknown"


def test_generated_label_strips_photo_style_and_background_noise():
    assert _normalise_generated_label("a_black_and_white_photo_of_a_laptop_computer") == "laptop computer"
    assert _normalise_generated_label("a_metal_door_with_a_black_background") == "metal door"
    assert _normalise_generated_label("a_black_and_white_image_of_a_person_in_a_wheelchair") == "person in a wheelchair"


def test_object_crop_keeps_rgb_context_instead_of_black_mask_background():
    rgb = np.arange(4 * 4 * 3, dtype=np.uint8).reshape((4, 4, 3))
    mask = np.zeros((4, 4), dtype=bool)
    mask[1:3, 1:3] = True

    crop = _object_rgb_crop(mask, rgb)

    assert crop.shape == (2, 2, 3)
    assert np.array_equal(crop, rgb[1:3, 1:3])
