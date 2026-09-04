import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(importlib.util.find_spec("fastapi") is None, reason="console extra not installed")


def test_status_and_start_stop_routes(tmp_path):
    from fastapi.testclient import TestClient
    from sparseworld_p0.capture_console import CaptureSession
    from sparseworld_p0.capture_console_api import create_app

    session = CaptureSession(tmp_path, dry_run=True)
    client = TestClient(create_app(session))
    assert client.get("/api/status").json()["state"] == "idle"
    response = client.post("/api/start", json={"run_name": "客厅-路线", "duration_s": 1, "topics": ["/tf"]})
    assert response.status_code == 200
    assert response.json()["active"] is True
    assert client.post("/api/start", json={"run_name": "again"}).status_code == 409
    assert client.post("/api/stop").json()["state"] == "complete"


def test_invalid_start_returns_bad_request(tmp_path):
    from fastapi.testclient import TestClient
    from sparseworld_p0.capture_console import CaptureSession
    from sparseworld_p0.capture_console_api import create_app

    client = TestClient(create_app(CaptureSession(tmp_path, dry_run=True)))
    assert client.post("/api/start", json={"run_name": "", "duration_s": 1}).status_code == 400


def test_runs_endpoint_exposes_saved_manifest(tmp_path):
    from fastapi.testclient import TestClient
    from sparseworld_p0.capture_console import CaptureSession
    from sparseworld_p0.capture_console_api import create_app

    session = CaptureSession(tmp_path, dry_run=True)
    session.start("route", None, ["/tf"])
    session.stop()
    client = TestClient(create_app(session))
    response = client.get("/api/runs")
    assert response.status_code == 200
    assert response.json()[0]["run_name"] == "route"


def test_run_detail_returns_manifest_and_file_list(tmp_path):
    from fastapi.testclient import TestClient
    from sparseworld_p0.capture_console import CaptureSession
    from sparseworld_p0.capture_console_api import create_app

    session = CaptureSession(tmp_path, dry_run=True)
    started = session.start("route", None, ["/tf"])
    session.stop()
    client = TestClient(create_app(session))
    response = client.get(f"/api/runs/{Path(started['run_dir']).name}")
    assert response.status_code == 200
    assert "capture_manifest.json" in response.json()["files"]


def test_run_file_endpoint_serves_manifest_only_inside_run(tmp_path):
    from fastapi.testclient import TestClient
    from sparseworld_p0.capture_console import CaptureSession
    from sparseworld_p0.capture_console_api import create_app

    session = CaptureSession(tmp_path, dry_run=True)
    started = session.start("route", None, ["/tf"])
    session.stop()
    client = TestClient(create_app(session))
    run_id = Path(started["run_dir"]).name
    response = client.get(f"/api/runs/{run_id}/files/capture_manifest.json")
    assert response.status_code == 200
    assert "stopped_unassessed" in response.text
    assert client.get(f"/api/runs/{run_id}/files/../capture_manifest.json").status_code in {400, 404}


def test_depth_preview_endpoint_returns_404_until_depth_frame_exists(tmp_path):
    from fastapi.testclient import TestClient
    from sparseworld_p0.capture_console import CaptureSession
    from sparseworld_p0.capture_console_api import create_app

    client = TestClient(create_app(CaptureSession(tmp_path, dry_run=True)))
    assert client.get("/api/preview/depth.jpg").status_code == 404


def test_live_start_validates_mode_and_returns_live_metrics(tmp_path):
    from fastapi.testclient import TestClient
    from sparseworld_p0.capture_console import CaptureSession
    from sparseworld_p0.capture_console_api import create_app

    client = TestClient(create_app(CaptureSession(tmp_path, dry_run=True)))
    invalid = client.post("/api/start", json={"run_name": "x", "mode": "wrong"})
    assert invalid.status_code == 400
    live = client.post("/api/start", json={"run_name": "live", "mode": "live", "debug_bag": False})
    assert live.status_code == 200
    assert live.json()["mode"] == "live"
    assert live.json()["storage_policy"] == "sparse_no_raw_bag"


def test_live_map_and_objects_endpoints_are_explicit_when_unavailable(tmp_path):
    from fastapi.testclient import TestClient
    from sparseworld_p0.capture_console import CaptureSession
    from sparseworld_p0.capture_console_api import create_app

    client = TestClient(create_app(CaptureSession(tmp_path, dry_run=True)))
    assert client.get("/api/objects").json() == []
    response = client.get("/api/map/preview")
    assert response.status_code == 404


def test_map_state_endpoint_returns_coordinate_frame_objects_and_trajectory(tmp_path):
    from fastapi.testclient import TestClient
    from sparseworld_p0.capture_console import CaptureSession
    from sparseworld_p0.capture_console_api import create_app

    session = CaptureSession(tmp_path, dry_run=True)
    started = session.start("live", None, ["/tf"], mode="live")
    run_dir = Path(started["run_dir"])
    (run_dir / "objects.json").write_text('{"map_frame":{"name":"initial_camera_map"},"objects":[{"object_id":"obj_cup_0001"}]}')
    (run_dir / "trajectory.json").write_text('{"poses":[{"keyframe_id":"kf-000000","position_xyz":[0,0,0]}]}')
    client = TestClient(create_app(session))

    response = client.get("/api/map/state")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["coordinate_frame"]["name"] == "initial_camera_map"
    assert payload["objects"][0]["object_id"] == "obj_cup_0001"
    assert payload["trajectory"][0]["position_xyz"] == [0, 0, 0]


def test_map_state_exposes_safe_representative_image_url(tmp_path):
    from fastapi.testclient import TestClient
    from sparseworld_p0.capture_console import CaptureSession
    from sparseworld_p0.capture_console_api import create_app

    session = CaptureSession(tmp_path, dry_run=True)
    started = session.start("live", None, ["/tf"], mode="live")
    run_id = Path(started["run_dir"]).name
    crop_dir = Path(started["run_dir"]) / "semantic-crops"
    crop_dir.mkdir()
    (crop_dir / "cup.jpg").write_bytes(b"jpeg")
    (Path(started["run_dir"]) / "objects.json").write_text('{"map_frame":{"name":"initial_camera_map"},"objects":[{"object_id":"obj_cup_0001","representative_image_uri":"semantic-crops/cup.jpg"}]}')
    client = TestClient(create_app(session))

    payload = client.get("/api/map/state").json()
    assert payload["objects"][0]["representative_image_url"] == f"/api/runs/{run_id}/assets/semantic-crops/cup.jpg"
    assert client.get(payload["objects"][0]["representative_image_url"]).content == b"jpeg"


def test_plan_endpoint_returns_observed_trajectory_route(tmp_path):
    from fastapi.testclient import TestClient
    from sparseworld_p0.capture_console import CaptureSession
    from sparseworld_p0.capture_console_api import create_app

    session = CaptureSession(tmp_path, dry_run=True)
    started = session.start("live", None, ["/tf"], mode="live")
    root = Path(started["run_dir"])
    (root / "objects.json").write_text('{"objects":[{"object_id":"obj_cup_0001","class_candidates":[{"label":"red cup"}],"geometry":{"anchor_xyz":[2,0,1]}}]}')
    (root / "trajectory.json").write_text('{"poses":[{"keyframe_id":"kf-0","position_xyz":[0,0,0]},{"keyframe_id":"kf-1","position_xyz":[1,0,0]},{"keyframe_id":"kf-2","position_xyz":[2,0,0]}]}')
    client = TestClient(create_app(session))

    response = client.post("/api/plan", json={"target_query":"red cup","start_node_id":"kf-0"})

    assert response.status_code == 200
    assert response.json()["route_status"] == "planned_unverified"
    assert response.json()["nodes"] == ["kf-0", "kf-1", "kf-2"]


def test_map_state_exposes_planning_graph_metadata(tmp_path):
    from fastapi.testclient import TestClient
    from sparseworld_p0.capture_console import CaptureSession
    from sparseworld_p0.capture_console_api import create_app

    session = CaptureSession(tmp_path, dry_run=True)
    started = session.start("live", None, ["/tf"], mode="live")
    root = Path(started["run_dir"])
    (root / "objects.json").write_text('{"map_frame":{"name":"initial_camera_map"},"objects":[]}')
    (root / "trajectory.json").write_text('{"poses":[{"keyframe_id":"kf-0","position_xyz":[0,0,0]},{"keyframe_id":"kf-1","position_xyz":[1,0,0]}]}')
    (root / "planning_graph.json").write_text('{"planning_basis":"observed_trajectory","nodes":[{"node_id":"kf-0"}],"edges":[]}')
    payload = TestClient(create_app(session)).get("/api/map/state").json()
    assert payload["planning_graph"]["planning_basis"] == "observed_trajectory"
