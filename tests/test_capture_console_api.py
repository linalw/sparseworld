import importlib.util

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
