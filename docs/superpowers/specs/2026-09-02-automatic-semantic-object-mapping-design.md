# Automatic Semantic Object Mapping Design

## Goal

Build an offline-first semantic perception pipeline that automatically discovers objects in RGB frames, produces instance masks and open-vocabulary labels, projects each candidate into RGB-D 3D coordinates, and writes deduplicated semantic-object observations compatible with the existing sparse world-model schema.

## Scope and non-goals

The first implementation processes a directory of synchronized RGB/depth frames and optional camera poses. It must run with a deterministic fixture backend in CI and expose adapters for real SAM 2, Florence-2, and SigLIP inference. It does not claim model accuracy, real-time throughput, SLAM quality, navigation safety, or complete object discovery until measured on labeled hardware data.

## Model pipeline

```text
RGB frame
  -> MaskGenerator (SAM2 automatic masks or fixture backend)
  -> Labeler (Florence-2/open-vocabulary backend)
  -> LabelVerifier (SigLIP/text prompt scoring, optional)
  -> DepthProjector (mask pixels + intrinsics -> camera 3D)
  -> ObjectAssociator (spatial/category/appearance gates)
  -> SemanticWorldStore (deduplicated object + evidence records)
```

Each model adapter reports `model_name`, `model_version`, `weights_id`, input size, confidence, and inference latency. Missing optional model dependencies fail explicitly in production mode; fixture mode is the only path allowed to produce synthetic deterministic outputs for tests.

## Deduplication contract

An observation is matched against existing non-removed objects before a new ID is allocated. Matching uses these gates in order:

1. A valid 3D anchor is required for spatial matching. Reject the observation from persistent storage when the mask has fewer than the configured minimum valid depth pixels or the depth dispersion exceeds the configured bound; it may remain an ephemeral diagnostic record.
2. Candidate objects must be within `spatial_gate_m` (default 0.20 m) after transforming both anchors into the same frame.
3. At least one semantic compatibility condition must hold: top-label equality, overlapping candidate labels, or cosine appearance similarity above `appearance_gate` when an embedding is available.
4. Select the lowest normalized association cost, with deterministic tie-breaking by object ID. A matched observation appends evidence and updates a weighted anchor estimate; it never creates a second object ID.
5. If no candidate passes, allocate a stable ID of the form `obj_<label>_<counter>` and mark lifecycle `tentative`. Promotion to `confirmed` requires `min_confirmations` (default 3) observations from at least `min_distinct_frames` (default 2) frames.

Spatial matching must not merge distinct nearby objects solely by class. If two same-class objects are farther apart than the gate, they remain separate. A moved object is not duplicated at the old coordinate: repeated observations that consistently exceed the gate transition its lifecycle to `moved` and update `last_seen` while preserving prior evidence.

## Output contract

The store emits a JSON document with `schema_version`, `map_frame`, `objects`, and an `inference_runs` audit array. Every object contains `object_id`, `class_candidates`, `geometry.anchor_xyz`, `state`, `lifecycle_status`, `confidence`, and evidence references. Evidence includes source frame, mask area, depth-valid fraction, model metadata, and optional image crop URI. Objects without a map pose use `camera` frame and are not silently interpreted as global map coordinates.

## Error handling and safety boundary

- Invalid RGB/depth dimensions, missing intrinsics, malformed masks, or non-finite depth values produce a structured rejected-observation reason.
- Unknown or low-confidence labels remain `unknown`/`tentative`; they are never forced into a known class.
- The semantic store is read/write data only. It never commands a base, changes a costmap, or disables real-time clearance checks.
- All thresholds are explicit configuration and recorded in the output; changing them invalidates comparability between runs.

## Validation plan

- Unit tests cover mask validation, robust depth median projection, label compatibility, same-position deduplication, separation of nearby same-class objects, moved-object lifecycle, deterministic IDs, and schema-shaped output.
- A fixture integration test feeds two frames containing the same object and verifies exactly one persistent object with two evidence records.
- A real-model smoke test is opt-in and skipped when SAM 2/Florence-2/SigLIP weights are unavailable; it records dependency/version/weights metadata and never turns a smoke result into an accuracy pass.
- A later hardware validation run must use the attended indoor route and labeled review set to measure precision/recall, mask IoU, 3D anchor error, duplicate rate, latency, and failure cases.

