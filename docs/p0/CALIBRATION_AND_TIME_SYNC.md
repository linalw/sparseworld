# Gemini 335 calibration and time-sync protocol

This protocol defines evidence required before any calibration or timing field
in `config/p0_capture_profile.yaml` can move from `pending_measurement`.
The adapter and assessor must preserve raw outputs and source metadata; a
missing tool, stream, or permission is a failed preflight, never a measured
pass.

## Required raw evidence

- Factory/device intrinsics for every RGB, depth, left-IR, and right-IR stream:
  resolution, focal lengths, principal point, distortion model and coefficients.
- Stereo left/right and RGB/depth alignment, with the SDK profile and calibration
  blob used to obtain it.
- Camera-to-IMU rigid transform (rotation and translation) and camera/IMU clock
  offset, including the estimation method and residuals.
- Base-to-camera transform (`base_link` → `camera_link`) and frame convention.
- Device timestamps and host UTC timestamps for every sample; report offset,
  drift, pairing policy, residuals, and rejected pairs.
- Tool versions, SDK/firmware versions, profile hash, operator, and UTC run ID.

## Rejection conditions

Reject and repeat the run if any requested stream is absent, serial/model does
not match, permissions prevent opening or writing, timestamps are non-monotonic,
pairing uses an incompatible frame number, calibration raw files are missing,
residuals exceed the declared acceptance threshold, or the device/host clock
relationship cannot be reproduced. Unknown values remain `null` or
`pending_measurement`; no interpolation or nearest-timestamp synthesis is
allowed.

## Evidence file and deterministic checker

Copy `config/p0_calibration_evidence.example.json` into the run evidence
directory, place the unedited raw outputs under that same directory, and fill
each `raw_file` and `sha256` from the exact bytes. Then run:

```bash
sparseworld-p0 assess-calibration \
  --evidence artifacts/evidence/<run-id>/calibration_evidence.json \
  --output artifacts/evidence/<run-id>/calibration_assessment
```

The checker validates five gates: camera intrinsics, RGB-depth alignment,
camera-IMU extrinsics, base-camera transform, and device-host clock offset.
It rejects path traversal, missing/incorrect hashes, unsupported evidence
schemas, malformed transforms, absent pairing policy, and residuals above the
operator-declared threshold. A complete report with `pass` is still evidence
of the declared calibration run only; it is not SLAM, navigation, or safety
acceptance.

### RGB checkerboard extractor

Use `sparseworld-p0 calibrate-chessboard` for a monocular RGB image set. The
CLI requires the actual count of **inner corners** and measured square edge in
millimetres. It stores every input image SHA-256, detector method, rejection
status, camera matrix, distortion coefficients, and per-view/overall RMS. The
2026-09-02 supplied image set is 9 images at 1280×720, 9×7 squares / 8×6 inner
corners, and 20 mm square edge. Its result is stored as P0 evidence, but has
no acceptance threshold and therefore is measured rather than passed.

## Current state

`pyorbbecsdk2==2.1.2` is installed and importable in `sparseworld`; its wheel
SHA-256 is `e1d3e207995ac60e2bf3350086777df1ba15669a41c6dcfb81c0d896cbb17fcb`.
ROS 2 Humble/rosbag2/MCAP/tf2 tools, `v4l-utils`, and the matching Orbbec ROS
driver are still unavailable (`ros2` is not on PATH on Ubuntu 22.04.5). A
2026-08-30 SDK run found one Gemini 335 and completed a 30-second timestamp
capture after `video`-group access became effective. The factory SDK parameter
snapshot is recorded at
`artifacts/evidence/p0_calibration_factory_20260830T053537Z/factory_calibration.json`.
It contains active-profile intrinsics plus depth→RGB and IR transforms, but is
not a checkerboard recalibration and does not measure camera→IMU, base→camera,
or clock offset. The prior Access-denied preflight remains preserved as
historical evidence.

The frozen IMU request is accel `SAMPLE_RATE_200_HZ` / `ACCEL_FS_4g` and gyro
`SAMPLE_RATE_200_HZ` / `FS_1000dps`, verified by
`artifacts/evidence/p0_explicit_imu_profile_validated_20260830T070442Z/`.
The SDK payload uses m/s² for acceleration and rad/s for angular velocity; the
assessment reports short-window maximum-axis/full-scale occupancy as an
observation, not an acceptance result. Clock alignment, calibration residuals,
and project-level saturation thresholds remain pending.
