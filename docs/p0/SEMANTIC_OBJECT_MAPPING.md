# Automatic semantic object mapping

The semantic-map MVP turns synchronized RGB-D frames into deduplicated object
records. Its production pipeline is designed for automatic SAM masks,
an image-to-text/open-vocabulary labeler, and optional SigLIP verification. The
repository includes a deterministic fixture backend for CI and an optional
Hugging Face adapter. Real inference loads only when requested packages and
weights are explicitly available; otherwise it fails closed.

## Input manifest

```json
{
  "schema_version": "p0/semantic-input/v1",
  "intrinsics": {"fx": 600, "fy": 600, "cx": 640, "cy": 360},
  "minimum_valid_depth_pixels": 20,
  "frames": [{
    "frame_id": "kf-0001",
    "timestamp": "2026-09-02T12:00:00Z",
    "rgb_path": "rgb-0001.npy",
    "depth_path": "depth-0001.npy",
    "map_T_camera": [[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]
  }]
}
```

RGB arrays are `H×W×3` uint8 NumPy files and depth arrays are `H×W` metres.
Each backend mask must match the RGB shape. Invalid or insufficient depth is a
structured rejection and cannot create a persistent map anchor.

## Fixture invocation

```bash
sparseworld-p0 semantic-map \
  --manifest examples/semantic_input.json \
  --backend fixture --fixture-path examples/semantic_fixture.json \
  --output artifacts/evidence/semantic_map/map.json
```

The command writes a deterministic JSON map and a SHA-256 sidecar. Repeated
observations are associated before ID allocation: same label and 3D anchor
within the configured 0.20 m gate update one object and append evidence. Same
class outside the gate remains separate. Repeated displacement is marked
`moved` without cloning an old object.

## Production model boundary

`--backend sam2_florence_siglip` uses SAM ViT Base masks and Florence-2 Base
caption inference by default. Florence-2 uses its official custom-code
`AutoProcessor + AutoModelForCausalLM` path, with `transformers==4.48.3`,
`timm`, and `einops` pinned as runtime dependencies. SigLIP is not yet enabled
as a second-stage re-ranker. The adapter records model/version/weights/input-size/latency
metadata and preserves `unknown` candidates when confidence is low. Install
the optional runtime with `pip install -e '.[semantic]'`, then pin and cache
model revisions before an offline run.
Installing or smoke-testing models does not establish mask IoU, class
precision/recall, 3D anchor error, duplicate rate, real-time throughput, SLAM,
navigation, or safety performance. Those require a labeled, attended Gemini
335 dataset and remain unmeasured.
