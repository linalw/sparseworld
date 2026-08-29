# Current State — world_sparse_semantic_mapping

- Updated: 2026-08-29T02:47:00Z
- Status: proposal_ready; prototype_validation_pending
- Next action: grant/reload USB camera access (video group/udev), then run the attended stationary and indoor rosbag protocol; calibration, synchronization, and performance gates remain pending
- Continuation package: `project_records/NEW_CONVERSATION_HANDOFF.md` contains the new-task context, evidence boundary, and P0/P1 checklist
- COLLECT_ONLY: false
- Baseline: v0.2 proposal, JSON Schema, and a JSON-parseable example world model aligned to the schema
- Key boundary: natural features plus loop closure can stabilize a local building map; absolute building coordinates require an external datum
- Safety boundary: persistent topology expresses structural connectivity only; current clearance is decided by the real-time local dense depth/costmap
- Open validation: ATE/RPE, relocalization, semantic association, multi-floor transitions, obstacle false-negative rate, latency, and failure recovery are not yet measured on hardware
- P0 software preflight: `pyorbbecsdk2==2.1.2` imports in `sparseworld`; a real Gemini 335 SDK open attempt on 2026-08-29 failed closed with `OBError: usbEnumerator openUsbDevice failed!` / insufficient USB permissions. Evidence: `artifacts/evidence/p0_capture_preflight_20260829T024616Z/capture_manifest.json` and `Log/OrbbecSDK.log.txt`.
