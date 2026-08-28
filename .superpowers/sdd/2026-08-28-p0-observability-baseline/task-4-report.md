# Task 4 report — Timing and Quality Assessment

## Status

Implemented and committed normalized JSONL timing/quality analysis and deterministic report rendering. Review
fix round 1 closes the normalized timestamp, device/host offset, unit safety, ordering, duplicate, fail-closed,
and sidecar checksum findings. No hardware evidence or performance result is inferred.

## TDD evidence

RED (before implementation):

    conda run -n sparseworld pytest -q tests/test_timing.py tests/test_quality.py
    ModuleNotFoundError: No module named 'sparseworld_p0.timing'
    ModuleNotFoundError: No module named 'sparseworld_p0.quality'

Initial GREEN focused run:

    conda run -n sparseworld pytest -q tests/test_timing.py tests/test_quality.py
    5 passed (after implementing the minimal interfaces)

Final focused run:

    conda run -n sparseworld pytest -q tests/test_timing.py tests/test_quality.py
    8 passed in 0.03s

Review fix round 1 RED (before fixes):

    conda run -n sparseworld pytest -q tests/test_timing.py tests/test_quality.py
    5 failed, 8 passed (normalized fields, ROS header clock, duplicate/order,
    fail-closed duration, and same-sample offset assertions)

Review fix round 1 GREEN:

    conda run -n sparseworld pytest -q tests/test_timing.py tests/test_quality.py
    13 passed in 0.03s

Review fix round 1 full suite:

    conda run -n sparseworld pytest -q
    31 passed in 0.11s

Full suite and hygiene:

    conda run -n sparseworld pytest -q
    24 passed in 0.10s
    git diff --check
    (no output; exit 0)

## Files

- `src/sparseworld_p0/timing.py`: explicit `device_time_ns` timestamps, optional `header_time_ns` ROS pairing,
  unit-safe rate/jitter/drift, deterministic sequence/frame ordering, duplicate reporting, and fail-closed timing.
- `src/sparseworld_p0/quality.py`: profile-gated depth validity, blur, gyro/acceleration saturation, paired offset, and three-state assessment with canonical source hash.
- `src/sparseworld_p0/quality.py`: profile-gated quality metrics plus same-sample `host_receive_time_ns - device_time_ns` offset evidence; inter-stream skew remains separate.
- `src/sparseworld_p0/reporting.py`: deterministic JSON, Markdown, and SHA-256 sidecar output (sidecar content is asserted against the exact JSON bytes).
- `tests/test_timing.py`, `tests/test_quality.py`, `tests/fixtures/timing_gap.jsonl`: synthetic normalized-schema, ROS-header,
  duplicate/order, fail-closed, same-sample offset, nearest-timestamp rejection, unknown data, threshold, and checksum fixtures.

## Self-review and concerns

Unknown fields and insufficient samples remain `not_measured`; no hardware measurements or P1 claims are invented. Interstream pairing never uses arbitrary nearest timestamps and only accepts SDK frame numbers (or an explicitly supplied ROS-header policy). Source metadata includes canonical SHA-256, format, tool/version, and criterion. Thresholds are read from profile mappings; pending profile fields do not become passes. Dense inputs are bounded by caller-provided normalized samples and are not persisted by analysis.

## Commit

`5d609ec feat: assess P0 timing and sensor quality evidence`
