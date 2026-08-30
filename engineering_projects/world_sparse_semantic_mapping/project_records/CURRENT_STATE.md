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
