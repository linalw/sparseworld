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
| Initial timestamp assessment | `artifacts/evidence/p0_stationary_capture_20260830T044323Z_async_window/quality_assessment.json` (SHA-256 `6c7d2ec343af087f0803d89fc4df0f80c450197168c8ddfe0cfdebee6805ebe5`) | RGB 29.998 Hz; depth/IR 29.663 Hz; video device timestamps monotonic; overall `not_measured` | IMU accel/gyro currently share `stream=imu` and interleave, so IMU monotonicity and synchronization gates remain unresolved |
