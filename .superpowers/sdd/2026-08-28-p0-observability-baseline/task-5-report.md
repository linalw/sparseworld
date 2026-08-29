# Task 5 report — Gemini/ROS collection adapters and protocol

## Delivered scope

- `capture_orbbec(profile, output_dir, duration_s)` imports the optional SDK
  only when invoked, matches the configured serial, validates every requested
  stream, records device and host timestamps, writes a bounded-capture manifest,
  and fails closed for absent SDK, mismatch, unavailable stream, and permissions.
- `export_rosbag_timestamps(bag_path, output_jsonl)` retains bag-recorded and
  message-header timestamps separately, along with topic type, offered QoS, and
  a null sequence when ROS does not expose one. JSONL input is a deterministic
  test interchange format; real bags require `rosbag2_py`, `rclpy`, and
  `rosidl_runtime_py`.
- The calibration/time-sync and indoor rosbag protocols specify required raw
  evidence, rejection criteria, 30-second stationary check, and exact route.

## TDD and verification evidence

The initial focused run failed at collection because neither new adapter module
existed: `ModuleNotFoundError: sparseworld_p0.orbbec_capture` and
`ModuleNotFoundError: sparseworld_p0.rosbag_export`. After implementation,
`conda run -n sparseworld pytest -q tests/test_orbbec_capture.py tests/test_rosbag_export.py`
reported `2 passed`; the final complete suite command
`conda run -n sparseworld pytest -q` reported `31 passed in 0.12s`.

## Dependency/preflight status (not installed, not measured)

The current login groups are `ubuntu adm cdrom sudo dip plugdev lpadmin lxd
sambashare`; `video` is absent. No group change was made. If `video` access is
later granted, a new login is required before access can be considered fixed.

Read-only checks found `v4l2-ctl`/`v4l-utils`, `ros2`, ROS 2 Humble rosbag2,
MCAP, tf2 tools, `pyorbbecsdk`, and the official Orbbec ROS 2 driver absent.
Consequently there is no installed version, binding checksum, or recorded
driver-source commit to report, and
`ros2 launch orbbec_camera gemini_330_series.launch.py --show-args` could not
run (`ros2: command not found`). The required driver source is the official
Orbbec `OrbbecSDK_ROS2` v2 support line; Gemini 335 uses its published
`gemini_330_series.launch.py` launch name. These missing prerequisites block
hardware capture, and no hardware/calibration/timing claim is made.

## Pending state

All calibration, clock-offset, residual, stream-rate, and quality fields remain
`pending_measurement` or `not_measured` until an attended run produces retained
raw outputs.

## Follow-up addendum (2026-08-29)

Task 5 hardening after review: profile hashes now use explicit canonical
dataclass/mapping fields; each selected video profile records
`profile_validation`, IMU accel/gyro provenance records requested versus still
unmeasured rates, and setup/capture exceptions write a `failed_incomplete`
manifest with counts, profile hash, SDK version, and error. Orbbec USB access
errors are actionable and fail closed. Tests added for all behaviors (11
focused adapter tests; 44 tests in the current full suite). A real SDK preflight
then imported `pyorbbecsdk2==2.1.2` but failed to open the connected Gemini 335
with Access denied before stream start; see the project evidence records. No
calibration, timing, rosbag, SLAM, navigation, or safety result is claimed.
