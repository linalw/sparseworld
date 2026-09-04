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

## RGB checkerboard calibration

For an 8×6-inner-corner checkerboard whose measured square edge is 20 mm:

```bash
sparseworld-p0 calibrate-chessboard \
  --image-dir /path/to/images \
  --inner-corners 8 6 --square-size-mm 20 \
  --output artifacts/evidence/<run-id>/rgb_checkerboard_intrinsics.json
```

The result stores SHA-256 for every input image, detector outcome, camera
matrix, distortion coefficients, and per-view/overall reprojection RMS. It is
only a monocular RGB calibration observation. Define acceptance criteria before
marking its residual as a pass.

## ROS 2 installation prerequisite

ROS 2 needs an interactive sudo password on this host. In a local terminal,
review then run:

```bash
bash scripts/p0_install_ros2_humble.sh
source /opt/ros/humble/setup.bash
ros2 --version
```

The script installs official ROS 2 Humble P0 tools only. The matching Orbbec
driver must then be pinned to its official Gemini 335 support-matrix version
before a `ros2 launch ... --show-args` preflight and any bag recording.

## P0 evidence and safety boundary

Read [docs/p0/CALIBRATION_AND_TIME_SYNC.md](docs/p0/CALIBRATION_AND_TIME_SYNC.md)
and [docs/p0/INDOOR_ROSBAG_PROTOCOL.md](docs/p0/INDOOR_ROSBAG_PROTOCOL.md)
before any attended capture. ROS 2/rosbag2 and the official Orbbec ROS driver
are not installed in the current environment, so no official ROS bag is
claimed. The hand-carried route is motor-disabled and requires a human monitor
and immediate-stop criteria.

Authoritative evidence, hashes, decisions, and unresolved risks live under
`engineering_projects/world_sparse_semantic_mapping/project_records/`.
# Local capture console

See [`docs/p0/CAPTURE_CONSOLE.md`](docs/p0/CAPTURE_CONSOLE.md) for the Gemini 335 browser console.
See [`docs/p0/LIVE_SPARSE_MAPPING.md`](docs/p0/LIVE_SPARSE_MAPPING.md) for the low-storage real-time mapping mode.
