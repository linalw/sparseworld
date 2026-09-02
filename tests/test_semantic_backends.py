import json
from pathlib import Path

import numpy as np
import pytest

from sparseworld_p0.semantic_backends import load_backend


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
    with pytest.raises(RuntimeError, match="semantic backend unavailable"):
        load_backend("sam2_florence_siglip", {"weights_dir": str(tmp_path)})
