# Requirements-to-Evidence Verification

This is a concept/prototype design verification, not a hardware acceptance test. The 2026-08-29 SDK preflight failed closed before stream start because USB device access was denied; no calibration, synchronization, rate, SLAM, navigation, or safety result is inferred.

| ID | Requirement | Evidence | Status | Remaining proof |
|---|---|---|---|---|
| V-001 | Estimate camera pose in a local global map with IMU and natural features | Proposal sections 3-4: frame tree, visual-inertial state, sparse landmarks, loop closure, factor-graph optimization | Covered by design | Measure ATE/RPE and covariance on replayed and live data |
| V-002 | Avoid mandatory pre-installed markers while supporting stronger external anchors | Proposal section 4.4 and decision D-002 | Covered by design | Test weak-texture and cross-session relocalization; compare natural-only and anchored modes |
| V-003 | Project segmented objects from RGB-D into map coordinates | Proposal section 5.2 and inverse-projection equations | Covered by design | Evaluate mask/depth association and object anchor error per object class |
| V-004 | Preserve coarse object semantics, obstacle state, geometry, screenshot, and uncertainty | `schemas/semantic_world_model.schema.json`; `schemas/semantic_world_model.example.json`; proposal section 10 | Fields and example covered; standard validation pending | Run a standards-compliant JSON Schema validator in CI and test update/retention behavior |
| V-005 | Build a structurally connected traversability map with room/door/turn/stair/elevator nodes | Proposal sections 6-8; topology node and edge definitions in Schema | Covered by design | Confirm topology extraction and manual review workflow in a mapped building |
| V-006 | Support multiple floors without flattening them into one ambiguous 2D map | Proposal section 8; `floor_id`, z interval, and cross-floor edge model | Covered by design | Validate floor recognition and post-transition relocalization |
| V-007 | Use real-time dense depth for current clearance, local path execution, and fine operation | Proposal sections 2.1 and 7; edge contract requires real-time clearance check | Covered by design | Measure obstacle false negatives, latency, and stop behavior on hardware |
| V-008 | Answer language queries such as “find the red cup” | Proposal section 9: parse, retrieve, confirm, generate observation/operation goal | Covered by design | Test multiple candidates, moved objects, occlusion, and no-match behavior |
| V-009 | Keep long-term storage compact | Proposal sections 2.1 and 10.2; persistent store versus ephemeral navigation buffer | Covered by design | Record actual bytes per keyframe/object/topology edge and TTL behavior |
| V-010 | Deliver readable engineering artifacts | `outputs/semantic_world_model_proposal.pdf` (13 pages, rendered and visually inspected); DOCX generated and OOXML-checked | PDF passed; DOCX visual QA open | Render DOCX with LibreOffice/soffice when available |

## P0 execution evidence (2026-08-29)

| Check | Evidence | Result | Boundary |
|---|---|---|---|
| SDK binding installation/import | `artifacts/evidence/p0_sdk_preflight_20260829T024616Z.json` (sidecar SHA-256 verified); `pyorbbecsdk2==2.1.2`; `import pyorbbecsdk` succeeded in `sparseworld`; wheel SHA-256 `e1d3e207995ac60e2bf3350086777df1ba15669a41c6dcfb81c0d896cbb17fcb` | Software dependency available | Does not prove device access or capture |
| Gemini 335 SDK open preflight | `artifacts/evidence/p0_capture_preflight_20260829T024616Z/capture_manifest.json` (status `failed_incomplete`, zero samples); `Log/OrbbecSDK.log.txt` (Access denied, status 113) | Failed closed before stream start | Permission/configuration blocker; not a sensor-quality or performance result |
| Adapter audit hardening | `c1118fa` plus current tests; deterministic profile payload, pending profile markers, IMU provenance, partial-capture manifest, actionable SDK access errors | Covered by automated tests | Mock/fixture coverage only; real streams still pending |

## P0 execution evidence (2026-08-30)

| Check | Evidence | Result | Boundary |
|---|---|---|---|
| User/device access | `id -nG` includes `video`; `/dev/video0`…`/dev/video7` are `root:video` | Access prerequisite satisfied for this session | Does not validate calibration or performance |
| Asynchronous FrameSet handling | `src/sparseworld_p0/orbbec_capture.py`; regression `test_capture_accumulates_async_framesets_instead_of_failing_on_missing_stream` | 45 automated tests pass; missing streams in one SDK batch no longer cause premature failure | Completeness is still enforced at end of bounded window |
| 30 s Gemini 335 stationary SDK capture | `artifacts/evidence/p0_stationary_capture_20260830T044323Z_async_window/capture_manifest.json`; raw `timestamps.jsonl`; SDK log additions in `Log/OrbbecSDK.log.txt` | `captured_unassessed`; serial `CP0F4630001M`, FW `1.4.60`, SDK `2.1.2`; RGB 884, depth 887, left 887, right 887, IMU 3600 samples | Timestamp-only evidence; no calibration, rosbag, or hardware performance claim |
| Initial timestamp assessment | `artifacts/evidence/p0_stationary_capture_20260830T044323Z_async_window/quality_assessment.json` (SHA-256 `35b45adf6a0dcc6a8c9472266963127de4498f97196ab7628ed1638566b52c7f`) | RGB 29.998 Hz; depth/IR 29.663 Hz; video timestamps monotonic; accel and gyro each monotonic at 194.369 Hz; overall `not_measured` | Aggregate IMU is intentionally non-monotonic because the sensor types interleave; depth/blur/saturation/device-host model and synchronization acceptance gates remain unresolved |

| Factory camera calibration snapshot | `artifacts/evidence/p0_calibration_factory_20260830T053537Z/factory_calibration.json` (SHA-256 `d27102484adb77b7301920e337c0fb6dfd0f8d37ac5b2435285fd18869a7cd24`) | SDK returned intrinsics for RGB/depth/left-IR/right-IR and depth→RGB / IR transforms for active default profiles | Factory parameters only; checkerboard residuals, camera→IMU, base→camera, and clock offset remain pending |
| ROS 2 / rosbag2 preflight | `command -v ros2` on Ubuntu 22.04.5 returned no executable; no ROS apt source is configured and non-interactive sudo is unavailable | Blocked before driver launch; no ROS bag or MCAP replay claimed | Requires authorized system installation of ROS 2 Humble, rosbag2-storage-mcap, tf2, and matching Orbbec ROS driver |
| IMU payload observability | `artifacts/evidence/p0_imu_static_capture_20260830T055440Z/capture_manifest.json`; raw `timestamps.jsonl`; `quality_assessment.json` | 5-second capture: 1800 IMU rows, accel/gyro 900 each; all rows carry finite three-axis `imu_value` and `temperature_c` | Quality status remains `not_measured`; no saturation/noise threshold or calibration/synchronization pass is claimed |
| Frozen video profile and format verification | `artifacts/evidence/p0_profile_format_verified_20260830T061242Z/capture_manifest.json` (SHA-256 `c05c90231667c778d3cc41c36e1d31bf40dc7c36c4e522e32ef453876b412d51`) | Hardware re-check passed RGB 1280x720 MJPG, depth 848x480 Y16, left/right IR 848x480 Y8 at 30 fps; profile hash `38bcdfc91361f62c4e5acf95eeb146f99c57713f949c68b957eb681567cee561` | IMU rate/full-scale, exposure, depth validity, clock offset, calibration residuals, and ROS bag remain pending |
