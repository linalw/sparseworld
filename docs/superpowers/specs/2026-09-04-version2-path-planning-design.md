# Version 2 Semantic Path Planning and First-Person Replay

## Goal

Add an offline planning/replay layer to the live semantic-map explorer so an operator can select a semantic target, generate a candidate route from the current camera pose, inspect the route in first person, and distinguish planned geometry from verified traversability.

## Scope and boundary

- This version evaluates planning logic only; it does not command a mobile base.
- Real-time depth/costmap re-checking is intentionally deferred.
- A displayed route is a `planned_unverified` candidate. It must never be labelled safe, collision-free, or executable.
- The project status remains `proposal_ready; prototype_validation_pending`.

## Data model

`/api/map/state` continues to provide the local `initial_camera_map` frame, deduplicated semantic objects, camera trajectory points, and occupancy-preview availability. The live worker additionally persists a compact `planning_graph.json` containing:

- `nodes`: trajectory-derived candidate waypoints with `node_id`, `position_xyz`, timestamp, and source keyframe;
- `edges`: consecutive observed waypoints with Euclidean length and `planned_unverified` status;
- `occupancy`: optional 2-D grid metadata when RTAB-Map publishes an OccupancyGrid; absent occupancy is explicit rather than fabricated.

The current camera pose is the last trajectory point. The target is selected by exact object id or case-insensitive label substring. If several objects match, the API returns all candidates and requires an explicit object id before planning.

## Planning API

- `POST /api/plan` accepts `{target_query, object_id?, start_node_id?}`.
- The server resolves a unique semantic target, chooses the nearest graph node to that target anchor, and runs deterministic Dijkstra over the candidate graph. If an occupancy grid is present, blocked cells are excluded; otherwise the graph is trajectory-only and the response says `planning_basis: observed_trajectory`.
- The response includes `status`, `target`, `start`, `nodes`, `total_length_m`, `planning_basis`, `route_status: planned_unverified`, and `global_accuracy: unvalidated`.
- No target match, ambiguous match, missing trajectory, or disconnected graph returns a structured non-success status; no straight-line route is silently invented.

## First-person replay

The explorer gains a `第一视角漫游路径` mode. It starts at the current camera node (or the first node when no current node is selected), follows the planned node sequence, interpolates position and heading along each edge, and exposes pause, resume, step, and exit controls. The replay camera is a visualization camera only; it does not publish `/cmd_vel` or alter SLAM state.

## Interaction and visual semantics

- Trajectory nodes are blue squares connected in temporal order.
- Candidate route edges are amber and thicker than the trajectory.
- Semantic objects remain green image sprites/markers.
- The current/replay camera is a yellow cone with a forward ray.
- Clicking any node or object opens an inspector showing ids, coordinates, timestamps, labels, evidence, planning status, and `global_accuracy`.
- The route panel shows the selected target, route length, basis, and explicit unverified warning.

## Failure handling

- Planning never mutates semantic objects or the source trajectory.
- Duplicate object ids are rendered once.
- Missing representative images fall back to a labelled marker.
- A stale or malformed planning graph is reported as unavailable and does not produce a route.
- First-person replay stops at the final node and remains paused until the operator exits.

## Verification requirements

- Unit tests cover target resolution, ambiguous/no-match handling, deterministic Dijkstra, disconnected graphs, occupancy blocking, and route length.
- API tests cover `/api/plan` success and structured failures.
- UI contract tests cover distinct node/edge/object styles, click inspector, planning controls, and first-person replay controls.
- Full software verification must include `pytest`, `pip check`, `py_compile`, and `git diff --check`.
- No test result upgrades SLAM ATE/RPE, semantic accuracy, navigation safety, or physical traversability status.
