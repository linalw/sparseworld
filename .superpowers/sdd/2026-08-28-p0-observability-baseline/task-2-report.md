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

## Fix round (review follow-up)

Base commit: `702d142`; fix commit: `efc1108`.

Added deep recursive immutability, mandatory dense-buffer metadata (local origin frame, UTC timestamp field, and 10–60 s TTL), explicit required quality/time gate keys, and per-stream mapping validation with non-empty `resolution` and `nominal_rate` fields. Both YAML profiles now carry the complete contract.

Adversarial RED run (before fixes): focused tests reported 4 failures (nested mutation accepted; dense buffer, missing gate, and missing stream field were not rejected). GREEN/final runs:

    conda run -n sparseworld pytest tests/test_profile.py -q
    6 passed in 0.03s

    conda run -n sparseworld pytest -q
    7 passed in 0.03s

Self-review: profile records are deeply immutable through `MappingProxyType` and tuples; validators fail closed on omitted or null contract fields while accepting explicit `pending_measurement`. No unrelated task files were changed.

Audit correction: the amended Git fix commit is `efc1108` (the prior `e261698` SHA was superseded by the report-only amend).

    git diff --check
    (no output; exit 0)
