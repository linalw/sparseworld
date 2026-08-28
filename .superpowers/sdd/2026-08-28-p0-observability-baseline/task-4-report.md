# Task 4 report — Timing and Quality Assessment

## Status

Implemented and committed normalized JSONL timing/quality analysis and deterministic report rendering.

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

Full suite and hygiene:

    conda run -n sparseworld pytest -q
    24 passed in 0.10s
    git diff --check
    (no output; exit 0)

## Files

- `src/sparseworld_p0/timing.py`: stream rate, jitter, sequence gaps, monotonicity, compatible frame-number/explicit ROS-header pairing, offsets and drift.
- `src/sparseworld_p0/quality.py`: profile-gated depth validity, blur, gyro/acceleration saturation, paired offset, and three-state assessment with canonical source hash.
- `src/sparseworld_p0/reporting.py`: deterministic JSON, Markdown, and SHA-256 sidecar output.
- `tests/test_timing.py`, `tests/test_quality.py`, `tests/fixtures/timing_gap.jsonl`: real synthetic behavior fixtures, including required `0,1,3` timing series, nearest-timestamp rejection, unknown data, and threshold failures.

## Self-review and concerns

Unknown fields and insufficient samples remain `not_measured`; no hardware measurements or P1 claims are invented. Interstream pairing never uses arbitrary nearest timestamps and only accepts SDK frame numbers (or an explicitly supplied ROS-header policy). Source metadata includes canonical SHA-256, format, tool/version, and criterion. Thresholds are read from profile mappings; pending profile fields do not become passes. Dense inputs are bounded by caller-provided normalized samples and are not persisted by analysis.

## Commit

`dd4bb0e feat: assess P0 timing and sensor quality evidence`
