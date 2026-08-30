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
