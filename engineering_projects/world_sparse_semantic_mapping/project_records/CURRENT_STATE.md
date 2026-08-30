# Current State — world_sparse_semantic_mapping

- Updated: 2026-08-30T04:43:23Z
- Status: proposal_ready; prototype_validation_pending
- Next action: run calibration/time-sync checks and the repeatable indoor rosbag protocol; calibration, synchronization, and performance gates remain pending
- Continuation package: `project_records/NEW_CONVERSATION_HANDOFF.md` contains the new-task context, evidence boundary, and P0/P1 checklist
- COLLECT_ONLY: false
- Baseline: v0.2 proposal, JSON Schema, and a JSON-parseable example world model aligned to the schema
- Key boundary: natural features plus loop closure can stabilize a local building map; absolute building coordinates require an external datum
- Safety boundary: persistent topology expresses structural connectivity only; current clearance is decided by the real-time local dense depth/costmap
- Open validation: ATE/RPE, relocalization, semantic association, multi-floor transitions, obstacle false-negative rate, latency, and failure recovery are not yet measured on hardware
- P0 software preflight: `pyorbbecsdk2==2.1.2` imports in `sparseworld`; a real Gemini 335 SDK open attempt on 2026-08-29 failed closed with `OBError: usbEnumerator openUsbDevice failed!` / insufficient USB permissions. Evidence: `artifacts/evidence/p0_capture_preflight_20260829T024616Z/capture_manifest.json` and `Log/OrbbecSDK.log.txt`.
- User access is now confirmed in the `video` group (`id -nG` includes `video`). A 30-second attended SDK capture completed on 2026-08-30 for serial `CP0F4630001M`; evidence: `artifacts/evidence/p0_stationary_capture_20260830T044323Z_async_window/` with RGB 884, depth 887, left IR 887, right IR 887, and IMU 3600 samples. The adapter now accumulates asynchronous FrameSets instead of failing on a missing stream in one batch.
- Initial timestamp assessment for that capture is `not_measured`: RGB is 29.998 Hz and depth/IR 29.663 Hz with monotonic device timestamps, but accel and gyro are interleaved under one `imu` stream key, producing 1,800 apparent non-monotonic transitions. This is an analysis/schema follow-up, not a synchronization pass/fail result.
- Sensor-specific reassessment now reports `imu.accel` and `imu.gyro` independently as monotonic at approximately 194.37 Hz each; the aggregate `imu` entry remains `not_measured` by design. A factory SDK calibration snapshot is preserved at `artifacts/evidence/p0_calibration_factory_20260830T053537Z/factory_calibration.json`; this does not replace checkerboard, camera-IMU, base-camera, or clock-offset calibration.
- ROS 2/rosbag2/MCAP preflight remains blocked because `ros2` is absent and no ROS apt source is configured; non-interactive sudo is unavailable in this session. No ROS bag or MCAP replay is claimed.
- A 5-second SDK capture with IMU payload fields completed at `artifacts/evidence/p0_imu_static_capture_20260830T055440Z/`; all 1800 IMU rows include finite `imu_value.{x,y,z}` and `temperature_c` (accel/gyro 900 each). Its quality assessment remains `not_measured`; this evidence does not establish saturation, noise, calibration, or synchronization acceptance.
- The frozen video profile was re-verified on hardware for 5 seconds at `artifacts/evidence/p0_profile_format_verified_20260830T061242Z/`; RGB 1280x720 MJPG and depth/left/right 848x480 Y16/Y8 all passed resolution, rate, and format checks. Profile hash: `38bcdfc91361f62c4e5acf95eeb146f99c57713f949c68b957eb681567cee561`.
- After freezing firmware `1.4.60` in the profile, a final 5-second re-check at `artifacts/evidence/p0_final_profile_recheck_20260830T062158Z/` again passed all four video resolution/rate/format checks. Final profile hash: `afbc552161c2c5930dd6191b04b7a4072d00508d86b648cbdc5f94255adda2ce`.
