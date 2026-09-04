# Version 2 Path Planning and First-Person Replay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic target selection, graph-based candidate path planning, node/object inspection, and first-person route replay to the semantic-map explorer.

**Architecture:** A pure-Python planner reads the persisted local-frame trajectory and semantic objects, resolves a unique target, and runs Dijkstra over observed consecutive trajectory edges. The FastAPI layer exposes planner state and requests; the browser renders distinct layers, a click inspector, route controls, and an interpolation-only replay camera that never publishes robot commands.

**Tech Stack:** Python 3.10, dataclasses, FastAPI, vanilla JavaScript canvas renderer, pytest.

**Spec:** `docs/superpowers/specs/2026-09-04-version2-path-planning-design.md`

## Global Constraints

- Planning evaluates logic only; no mobile-base command or `/cmd_vel` publication.
- Candidate routes are always `planned_unverified`; no traversability or safety claim.
- Existing `initial_camera_map`, deduplicated objects, keyframe gating, and status `proposal_ready; prototype_validation_pending` remain unchanged.
- Missing, ambiguous, or disconnected inputs fail explicitly; no silent straight-line route.

### Task 1: Deterministic planner core

**Files:**
- Create: `src/sparseworld_p0/path_planning.py`
- Test: `tests/test_path_planning.py`

**Interfaces:**
- Produces `resolve_target(objects, query, object_id=None) -> TargetResolution`.
- Produces `plan_route(objects, trajectory, target_query, object_id=None, start_node_id=None) -> dict`.

- [ ] Write failing tests for exact/ambiguous/no target, disconnected graph, deterministic Dijkstra, and route length.
- [ ] Run `conda run -n sparseworld pytest -q tests/test_path_planning.py` and confirm expected missing-module failures.
- [ ] Implement normalized label matching, nearest trajectory node selection, consecutive-edge graph, and Dijkstra with structured failure statuses.
- [ ] Re-run focused tests until green.
- [ ] Commit `feat: add deterministic semantic path planner`.

### Task 2: Persist planning graph and expose API

**Files:**
- Modify: `src/sparseworld_p0/live_semantic_worker.py`
- Modify: `src/sparseworld_p0/capture_console_api.py`
- Test: `tests/test_capture_console_api.py`

**Interfaces:**
- Persists `planning_graph.json` with trajectory nodes, edges, and `planning_basis: observed_trajectory`.
- Adds `POST /api/plan` accepting `{target_query, object_id?, start_node_id?}`.

- [ ] Write failing API tests for successful plan, ambiguous query, and missing trajectory.
- [ ] Run focused API tests and confirm failure before implementation.
- [ ] Persist graph alongside `objects.json` and `trajectory.json`; map-state responses include graph metadata and latest route state.
- [ ] Implement safe request validation and planner response passthrough.
- [ ] Run focused API tests and full existing API tests.
- [ ] Commit `feat: expose semantic path planning API`.

### Task 3: Explorer visual layers and inspector

**Files:**
- Modify: `src/sparseworld_p0/static/capture_console.html`
- Modify: `src/sparseworld_p0/static/capture_console.css`
- Modify: `src/sparseworld_p0/static/capture_console.js`
- Test: `tests/test_capture_console_ui.py`

**Interfaces:**
- Adds target input/button, route summary, inspector panel, first-person controls.
- Canvas draws trajectory squares and connecting blue lines, objects as green images/markers, route as amber line, and camera as yellow cone.

- [ ] Add UI contract assertions for distinct style tokens, click handler, plan endpoint, inspector, and replay controls.
- [ ] Run UI tests to confirm missing strings.
- [ ] Implement rendering and click hit testing without duplicate object drawing.
- [ ] Implement inspector population for objects/nodes/current camera.
- [ ] Run UI tests and API tests.
- [ ] Commit `feat: add map inspector and route controls`.

### Task 4: First-person route replay

**Files:**
- Modify: `src/sparseworld_p0/static/capture_console.js`
- Modify: `src/sparseworld_p0/static/capture_console.css`
- Test: `tests/test_capture_console_ui.py`

- [ ] Add UI contract tests for `第一视角漫游路径`, pause/resume, step, exit, and no `/cmd_vel`.
- [ ] Implement route interpolation, heading calculation, playback timer, pause/resume/step/exit, and camera cone rendering.
- [ ] Ensure replay stops at final node and remains paused.
- [ ] Run full test suite, `pip check`, `py_compile`, and `git diff --check`.
- [ ] Update `CURRENT_STATE.md` and `VERIFICATION.md` with evidence boundary.
- [ ] Commit `feat: add first-person planned-route replay` and push `codex/live-sparse-mapping`.
