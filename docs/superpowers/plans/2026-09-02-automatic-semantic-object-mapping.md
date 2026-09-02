# Automatic Semantic Object Mapping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an offline RGB-D semantic-perception pipeline that automatically masks, labels, projects, and deduplicates semantic objects.

**Architecture:** `semantic_mapping.py` owns projection, deterministic association, and JSON export. `semantic_backends.py` provides replaceable mask/label interfaces and a deterministic fixture backend. The CLI consumes an RGB-D manifest and emits an auditable world-model document; production model dependencies are optional and fail closed when unavailable.

**Tech Stack:** Python 3.10, NumPy, Pillow, pytest; optional PyTorch/transformers/SAM 2.

**Spec:** `docs/superpowers/specs/2026-09-02-automatic-semantic-object-mapping-design.md`

## Global Constraints

- Preserve the frozen four-layer architecture and D-001 through D-007.
- Keep status `proposal_ready; prototype_validation_pending`.
- Associate an observation before allocating a new ID; matching observations append evidence.
- Require valid RGB-D projection for persistent anchors; reject invalid observations explicitly.
- Import production model dependencies lazily; fixture outputs are synthetic test evidence only.

### Task 1: Projection records

**Files:** create `src/sparseworld_p0/semantic_mapping.py`, `tests/test_semantic_mapping.py`.

- [ ] Write a failing test for median valid-depth projection with `{fx,fy,cx,cy}` and a rejection test for insufficient depth.
- [ ] Run `conda run -n sparseworld pytest tests/test_semantic_mapping.py -v`; confirm failure because the module/API is absent.
- [ ] Implement immutable observation records and `project_mask_depth(mask, depth_m, intrinsics, minimum_valid_pixels)` returning `projected` or structured `rejected` results.
- [ ] Re-run the focused tests; expected result is PASS.
- [ ] Commit `feat: add RGB-D semantic observation projection`.

### Task 2: Deduplicating object store

**Files:** modify `src/sparseworld_p0/semantic_mapping.py`, `tests/test_semantic_mapping.py`.

- [ ] Add failing tests proving two same-label observations within `spatial_gate_m` create one object with two evidence records, while same-class observations outside the gate create two objects.
- [ ] Run the focused tests and confirm the expected missing-store failure.
- [ ] Implement `SemanticObjectStore.upsert(observation)` with deterministic distance/label gates, weighted anchor update, stable `obj_<label>_<counter>` IDs, and tentative-to-confirmed promotion after configured confirmations.
- [ ] Add a moved-object test: repeated out-of-gate observations update lifecycle to `moved` without cloning the old object.
- [ ] Run the complete semantic test file and commit `feat: deduplicate semantic object observations`.

### Task 3: Replaceable model backends

**Files:** create `src/sparseworld_p0/semantic_backends.py`, `tests/test_semantic_backends.py`, modify `pyproject.toml`.

- [ ] Add failing fixture-backend and fail-closed real-backend tests.
- [ ] Implement `MaskGenerator`, `Labeler`, `FixtureSemanticBackend`, and `load_backend(kind, config)`; fixture JSON supplies masks/labels and audit metadata, while SAM2/Florence2/SigLIP selection raises an actionable dependency/weights error until adapters are configured.
- [ ] Run focused backend tests and commit `feat: add pluggable semantic perception backends`.

### Task 4: Offline semantic-map CLI

**Files:** modify `src/sparseworld_p0/cli.py`, `src/sparseworld_p0/semantic_mapping.py`, `tests/test_semantic_mapping.py`, `README.md`; create `docs/p0/SEMANTIC_OBJECT_MAPPING.md`.

- [ ] Add a failing integration test for `sparseworld-p0 semantic-map --manifest PATH --backend fixture --output PATH`, feeding two frames of the same object and asserting one object/two evidence entries.
- [ ] Implement manifest parsing, backend invocation, projection, store updates, `inference_runs`, explicit rejection records, deterministic JSON output, and a `.sha256` sidecar.
- [ ] Document fixture and real-model invocation, deduplication gates, and the boundary that model smoke tests do not establish accuracy or navigation safety.
- [ ] Run `conda run -n sparseworld pytest -q`; commit `feat: add offline semantic map pipeline`.

### Task 5: Audit records

**Files:** modify project records under `engineering_projects/world_sparse_semantic_mapping/project_records/`.

- [ ] Record the automatic segmentation/labeling/projection/association capability and explicitly list real-model precision, recall, mask IoU, 3D error, duplicate rate, and latency as unmeasured.
- [ ] Refresh `FILE_MANIFEST.md` and `FILE_MANIFEST.sha256`, then run `cd engineering_projects/world_sparse_semantic_mapping && sha256sum -c project_records/FILE_MANIFEST.sha256 --strict`.
- [ ] Run `conda run -n sparseworld pytest -q && conda run -n sparseworld pip check && git diff --check`.
- [ ] Commit `docs: record semantic mapping implementation boundary` and push the branch.

