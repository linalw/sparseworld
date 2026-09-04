from sparseworld_p0.path_planning import plan_route, resolve_target

OBJECTS = [
    {"object_id": "obj_cup_0001", "class_candidates": [{"label": "red cup"}], "geometry": {"anchor_xyz": [2.0, 0.0, 1.0]}},
    {"object_id": "obj_cup_0002", "class_candidates": [{"label": "blue cup"}], "geometry": {"anchor_xyz": [4.0, 0.0, 1.0]}},
]
TRAJECTORY = [{"keyframe_id": f"kf-{i:04d}", "position_xyz": [float(i), 0.0, 0.0]} for i in range(5)]


def test_resolve_target_requires_id_for_ambiguous_query():
    result = resolve_target(OBJECTS, "cup")
    assert result.status == "ambiguous"
    assert {item["object_id"] for item in result.candidates} == {"obj_cup_0001", "obj_cup_0002"}


def test_plan_route_uses_dijkstra_over_observed_trajectory():
    result = plan_route(OBJECTS, TRAJECTORY, "red cup", start_node_id="kf-0000")
    assert result["status"] == "planned"
    assert result["route_status"] == "planned_unverified"
    assert result["planning_basis"] == "observed_trajectory"
    assert result["nodes"] == ["kf-0000", "kf-0001", "kf-0002"]
    assert result["total_length_m"] == 2.0


def test_plan_route_reports_missing_and_disconnected_inputs():
    assert plan_route(OBJECTS, [], "red cup")["status"] == "missing_trajectory"
    result = plan_route(OBJECTS, TRAJECTORY, "missing")
    assert result["status"] == "target_not_found"
