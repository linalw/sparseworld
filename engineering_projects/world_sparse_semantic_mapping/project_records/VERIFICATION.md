# Requirements-to-Evidence Verification

This is a concept/prototype design verification, not a hardware acceptance test.

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
