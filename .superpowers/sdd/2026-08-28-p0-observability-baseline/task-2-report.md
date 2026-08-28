# Task 2 report: Frozen Capture Profile

## Files

- `src/sparseworld_p0/models.py`: frozen `CaptureProfile` record.
- `src/sparseworld_p0/profile.py`: YAML loader and contract validator.
- `config/p0_capture_profile.yaml`: sanitized, evidence-backed Gemini 335 profile.
- `config/p0_capture_profile.example.yaml`: reference profile with device discovery fields sanitized to `pending_measurement`.
- `tests/test_profile.py`: required RED test plus valid real-profile coverage.

## TDD evidence

RED (before implementation):

    conda run -n sparseworld pytest tests/test_profile.py -q
    ModuleNotFoundError: No module named 'sparseworld_p0.profile'

GREEN (focused):

    conda run -n sparseworld pytest tests/test_profile.py -q
    2 passed in 0.01s

Full suite:

    conda run -n sparseworld pytest -q
    3 passed in 0.02s

Additional check: `git diff --check` passed.

## Self-review and concerns

The profile preserves the four-layer boundaries and explicitly limits P0 to capture observability; it does not claim P1 localization, navigation, or safety performance. The canonical frame tree, required RGB/depth/left/right/IMU streams, local map-origin semantics, SI/UTC conventions, explicit quality/time gates, bounded 30-second diagnostic window, and mandatory real-time clearance check are validated. Device identity is recorded only from read-only discovery facts; all unmeasured rates, resolutions, firmware, intrinsics, extrinsics, and time offset remain `pending_measurement`. No SDK/ROS installation, stream start, or motor control is performed. Future tasks should extend the schema only with evidence-bearing fields and retain immutable loading semantics.

## Commit

`feat: add auditable P0 capture profile`
