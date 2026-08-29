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
driver are still unavailable. On 2026-08-29, an SDK preflight found one Gemini
335 but failed before stream start with USB Access denied (status 113). The
`video` group is not present in the current login groups (`ubuntu adm cdrom sudo
dip plugdev lpadmin lxd sambashare`); `/dev/video*` is owned by `root:video`.
Adding approved udev or group access requires a new login before recording can
resume. See `artifacts/evidence/p0_capture_preflight_20260829T024616Z/` and
`Log/OrbbecSDK.log.txt`. No hardware calibration or timing measurement is
claimed.
