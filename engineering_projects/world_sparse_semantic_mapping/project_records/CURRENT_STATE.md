# Current State — world_sparse_semantic_mapping

- Updated: 2026-08-28T01:27:24+00:00
- Status: proposal_ready; prototype_validation_pending
- Next action: freeze sensor/compute configuration, collect a repeatable indoor rosbag, and execute P0/P1 calibration and localization tests
- Continuation package: `project_records/NEW_CONVERSATION_HANDOFF.md` contains the new-task context, evidence boundary, and P0/P1 checklist
- COLLECT_ONLY: false
- Baseline: v0.2 proposal, JSON Schema, and a JSON-parseable example world model aligned to the schema
- Key boundary: natural features plus loop closure can stabilize a local building map; absolute building coordinates require an external datum
- Safety boundary: persistent topology expresses structural connectivity only; current clearance is decided by the real-time local dense depth/costmap
- Open validation: ATE/RPE, relocalization, semantic association, multi-floor transitions, obstacle false-negative rate, latency, and failure recovery are not yet measured on hardware
