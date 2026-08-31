# SparseWorld P0 observability baseline

This repository contains the auditable P0 capture and evidence tooling for
the Orbbec Gemini 335 semantic-world sparse-mapping prototype. It freezes the
capture contract, records normalized SDK observations, assesses timing and
sensor-quality gates, and provides a user-space MCAP diagnostic fallback when
ROS 2 is unavailable.

## Current hardware boundary

The connected device is a Gemini 335 (serial `CP0F4630001M`, firmware
`1.4.60`). The frozen profile is RGB `1280x720 MJPG @ 30 Hz`, depth/left/right
IR `848x480 Y16/Y8 @ 30 Hz`, and accel/gyro `200 Hz` with `±4g` and `±1000 dps`.
These values are profile and SDK observations; they do not constitute
calibration, clock synchronization, transport-loss, SLAM, navigation, or
safety acceptance. The project status remains
`proposal_ready; prototype_validation_pending`.

## Reproducible commands

```bash
conda run -n sparseworld pytest -q
conda run -n sparseworld pip check
sparseworld-p0 discover --output artifacts/evidence
sparseworld-p0 assess --profile config/p0_capture_profile.yaml \
  --capture-dir artifacts/evidence/<run-id> \
  --output artifacts/evidence/<run-id>/assessment
sparseworld-p0 package-mcap --capture-dir artifacts/evidence/<run-id> \
  --output artifacts/evidence/<run-id>/userspace_mcap
sparseworld-p0 assess-calibration \
  --evidence artifacts/evidence/<run-id>/calibration_evidence.json \
  --output artifacts/evidence/<run-id>/calibration_assessment
```

`assess-calibration` only accepts hash-bound raw files located below the
evidence directory. Missing field evidence is `not_measured`; a hash mismatch,
unsupported schema, or residual violation is `fail`. It never estimates or
fills calibration values.

## P0 evidence and safety boundary

Read [docs/p0/CALIBRATION_AND_TIME_SYNC.md](docs/p0/CALIBRATION_AND_TIME_SYNC.md)
and [docs/p0/INDOOR_ROSBAG_PROTOCOL.md](docs/p0/INDOOR_ROSBAG_PROTOCOL.md)
before any attended capture. ROS 2/rosbag2 and the official Orbbec ROS driver
are not installed in the current environment, so no official ROS bag is
claimed. The hand-carried route is motor-disabled and requires a human monitor
and immediate-stop criteria.

Authoritative evidence, hashes, decisions, and unresolved risks live under
`engineering_projects/world_sparse_semantic_mapping/project_records/`.
