# P0 Observability Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish an auditable P0 baseline for the attached Orbbec Gemini 335: freeze actual configuration, assess calibration/time/data quality, and produce a repeatable indoor ROS 2 rosbag procedure without claiming unmeasured performance.

**Architecture:** A Python package creates immutable evidence snapshots and analyzes normalized JSONL samples. Optional Gemini SDK and ROS 2 adapters produce this common input format. Profiles and procedures freeze the hardware/route contract, while project records retain only evidence-backed results.

**Tech Stack:** Python 3.10 (`sparseworld`); pytest; PyYAML; optional Orbbec SDK; ROS 2 Humble/rosbag2; Git/GitHub.

**Spec:** `docs/semantic_world_model_proposal.md` sections 2, 3, 11-14; `engineering_projects/world_sparse_semantic_mapping/project_records/NEW_CONVERSATION_HANDOFF.md`; D-001-D-007; `VERIFICATION.md`.

## Global Constraints

- Preserve the four-layer model and D-001-D-007. P0 must not be reported as P1 localization/navigation/safety validation.
- Without a measured external datum, `map` is a local initialization frame. Use SI units and UTC ISO-8601 timestamps.
- Each measured result needs raw evidence, command, tool/firmware version, criterion, and SHA-256. Other states are `fail` or `not_measured`.
- Do not persist unbounded dense data. Keep raw bags Git-ignored and commit only small evidence summaries/hashes.
- Live calibration is stationary; the route is hand-carried, in a clear space, with a human monitor and immediate-stop rule. No motor controls are included.

## Task 1: Project and Git Baseline

**Files:** `.gitignore`, `pyproject.toml`, `src/sparseworld_p0/__init__.py`, `tests/test_package_layout.py`

**Produces:** distribution `sparseworld-p0`, version `0.1.0`, with console command `sparseworld-p0`.

- [ ] Initialize `main` branch and set repository-local Git identity. Create a private GitHub remote only after a local commit succeeds.
- [ ] Write this failing test first:

```python
from importlib.metadata import version

def test_package_exposes_a_version() -> None:
    assert version("sparseworld-p0") == "0.1.0"
```

- [ ] Run `conda run -n sparseworld pytest tests/test_package_layout.py -q`; observe failure because the distribution does not exist.
- [ ] Add setuptools `src` layout, Python `>=3.10`, dependency `PyYAML>=6.0`, test extra `pytest>=8.0`, and entry point `sparseworld-p0 = sparseworld_p0.cli:main`.
- [ ] Ignore `captures/`, `artifacts/raw/`, `artifacts/rosbags/`, rendered diagnostics, virtual environments, and test caches; retain profiles, reports, and checksums.
- [ ] Install with `conda run -n sparseworld python -m pip install -e '.[test]'`, verify the test passes, then commit `chore: initialize P0 observability project`.

## Task 2: Frozen Capture Profile

**Files:** `src/sparseworld_p0/models.py`, `src/sparseworld_p0/profile.py`, `config/p0_capture_profile.example.yaml`, `config/p0_capture_profile.yaml`, `tests/test_profile.py`

**Produces:** `load_profile(path)` and `validate_profile(profile)`.

- [ ] Write a failing test that loads `schema_version: p0/v1` alone and asserts validation includes `topology.requires_realtime_clearance_check must be true`.
- [ ] Run `conda run -n sparseworld pytest tests/test_profile.py -q`; observe missing-module failure.
- [ ] Implement immutable profile records. Require the canonical frame tree, RGB/depth/left/right/IMU streams, local map origin semantics, explicit quality/time gates, 10-60 s diagnostic window, and `requires_realtime_clearance_check: true`.
- [ ] The real profile records Gemini 335 USB discovery as fact, but retains unmeasured resolutions, intrinsics, external transforms, time offset, and firmware values as `pending_measurement`.
- [ ] Verify test pass and commit `feat: add auditable P0 capture profile`.

## Task 3: Read-Only Environment Discovery

**Files:** `src/sparseworld_p0/discovery.py`, `src/sparseworld_p0/cli.py`, `tests/test_discovery.py`, `artifacts/evidence/.gitkeep`

**Produces:** `discover_environment(command_runner, sysfs_root)` and `sparseworld-p0 discover --output PATH`.

- [ ] Write a failing injected-command test: an exit 127 `ros2` command must produce `software.ros2.status == "not_installed"` and `collection_mode == "read_only"`.
- [ ] Run the test and observe missing-module failure.
- [ ] Implement discovery of OS/kernel/Python/GPU, USB Gemini fields, `/dev/v4l/by-id`, sysfs labels, groups, ROS 2 and Orbbec SDK. Discovery must never start a stream or alter device state.
- [ ] Model unavailable outcomes as `not_installed`, `permission_denied`, or `not_detected`, never as an empty successful value.
- [ ] Verify tests, create `artifacts/evidence/p0_environment_20260828T100734Z.json` plus SHA-256, then commit `feat: capture read-only P0 environment evidence`.

## Task 4: Timing and Quality Assessment

**Files:** `src/sparseworld_p0/timing.py`, `src/sparseworld_p0/quality.py`, `src/sparseworld_p0/reporting.py`, `tests/test_timing.py`, `tests/test_quality.py`, `tests/fixtures/*.jsonl`

**Produces:** `analyze_stream(samples)`, `analyze_interstream(samples_by_stream)`, `assess(profile, samples)`, and `render_report(assessment, output_dir)`.

- [ ] Write a failing time-series test with sequences `0, 1, 3` at timestamps `0`, `33_000_000`, `70_000_000`; assert one missing sequence, zero non-monotonic timestamps, and observed rate `3 / 0.07`.
- [ ] Run the timing/quality tests and observe missing-module failure.
- [ ] Implement rate, jitter, sequence gap, monotonicity, profile-defined paired offset, drift, depth-valid fraction, blur, gyro saturation, and acceleration saturation.
- [ ] Emit `not_measured` when there is inadequate data. Offset pairing must use a compatible SDK frame number or stated ROS-header policy, never arbitrary nearest timestamps.
- [ ] Render deterministic JSON and Markdown with source hashes and a pass/fail/not_measured entry for every gate. Verify fixtures and commit `feat: assess P0 timing and sensor quality evidence`.

## Task 5: Gemini/ROS Collection Adapters and Operating Protocol

**Files:** `src/sparseworld_p0/orbbec_capture.py`, `scripts/p0_export_rosbag_timestamps.py`, `docs/p0/CALIBRATION_AND_TIME_SYNC.md`, `docs/p0/INDOOR_ROSBAG_PROTOCOL.md`, `tests/test_orbbec_capture.py`, `tests/test_rosbag_export.py`

**Produces:** `capture_orbbec(profile, output_dir, duration_s)` and `export_rosbag_timestamps(bag_path, output_jsonl)`.

- [ ] Write a failing test that forces SDK import absence and asserts an actionable `RuntimeError` naming `pyorbbecsdk`; add exporter test that a missing ROS sequence remains null.
- [ ] Run tests and observe missing-adapter failure.
- [ ] Install and record version/source for `v4l-utils`, ROS 2 Humble/rosbag2/MCAP/tf2 tools, matching official Orbbec ROS driver, and checksum-recorded SDK Python binding. Record current group state before adding `video`; a new login is required before recording access as fixed.
- [ ] Live adapter matches the target by serial, validates requested streams, records device plus host timestamps, writes SDK/firmware/stream manifest, bounds diagnostic data, and fails closed on a mismatch, permission denial, missing stream, or unavailable SDK.
- [ ] Exporter records ROS recorded timestamp separately from header timestamp, topic type/QoS, and null unknown sequence.
- [ ] Calibration protocol requires raw intrinsics, stereo/RGB-depth alignment, camera-IMU rigid transform/time offset, base-camera transform, residuals, tool versions, and rejection conditions. Every current field remains pending until raw output exists.
- [ ] Rosbag protocol requires a 30-s stationary check and the exact loop: start -> textured wall/doorframe -> 90-degree turn -> texture-poor wall -> doorway -> return -> stop. It includes monitor, pace, light, clear test zone, stop criteria, topic list, record command, metadata, and replay.
- [ ] Verify fixture tests and `ros2 launch orbbec_camera gemini_330_series.launch.py --show-args` before any stream. This is the Gemini 335 launch file published by the official Orbbec ROS 2 v2 support matrix; commit `feat: add Gemini P0 capture and rosbag protocol`.

## Task 6: P0 Evidence Run and Authority Records

**Files:** `artifacts/evidence/<run-id>/`, ignored `artifacts/rosbags/<run-id>/`, and all project records/manifests.

**Produces:** source hashes, capture manifest, samples, assessment report, and exact evidence/result/risk updates.

- [ ] Validate profile and topic preflight. Do not record until required color/depth/camera-info/IMU/TF topics and metadata match the profile.
- [ ] Record 30 s stationary samples and unedited calibration sources, assess them, and preserve every gate as pass/fail/not_measured.
- [ ] Follow the supervised loop protocol to create one MCAP bag; save bag checksums, bytes, start/stop UTC times in the committed capture manifest.
- [ ] Export rosbag timestamps, assess the exported JSONL, and replay with `ros2 bag play ... --clock`. Playback proves only bag readability and replay, never SLAM/ATE/RPE/navigation/semantic/safety performance.
- [ ] Add paths, SHA-256, commands, tool versions, results, and risks to `VERIFICATION.md`; retain `prototype_validation_pending` unless every P0 exit condition has direct evidence. Update handoff/current state/errors/events and refresh manifest after final edits.
- [ ] Run full pytest, profile validation, `git diff --check`, and status. Commit summaries/source/procedures/records, not raw bags. Create and push a private GitHub repository only after local verification succeeds.

## Self-Review

- The six tasks trace each requested P0 outcome to evidence, while preserving the distinction between enumeration, installation, calibration/time checks, rosbag replay, and performance validation.
- The plan never changes decisions D-001-D-007 and never uses a documentation or playback check to support a hardware performance claim.
- `<run-id>` is an execution-time evidence identifier captured in every manifest; all implementation interfaces and acceptance conditions are explicit.
