import json
import time
from pathlib import Path

import pytest

from sparseworld_p0.capture_console import CaptureSession, SessionBusyError


class FakeProcess:
    def __init__(self, argv):
        self.argv = argv
        self.pid = 123
        self.returncode = None
        self.terminated = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = 0

    def wait(self, timeout=None):
        return self.returncode or 0

    def kill(self):
        self.terminated = True
        self.returncode = -9


def test_idle_snapshot_is_explicit(tmp_path):
    session = CaptureSession(tmp_path, process_factory=lambda argv, **kw: FakeProcess(argv))
    state = session.snapshot()
    assert state["state"] == "idle"
    assert state["active"] is False
    assert state["preview_available"] is False


def test_only_one_capture_can_be_active(tmp_path):
    session = CaptureSession(tmp_path, process_factory=lambda argv, **kw: FakeProcess(argv))
    session.start("route-a", duration_s=None, topics=["/tf"])
    with pytest.raises(SessionBusyError):
        session.start("route-b", duration_s=None, topics=["/tf"])
    session.stop()


def test_stop_writes_manifest_and_preserves_run_directory(tmp_path):
    session = CaptureSession(tmp_path, process_factory=lambda argv, **kw: FakeProcess(argv))
    started = session.start("Living Room / morning", duration_s=None, topics=["/tf"])
    result = session.stop()
    run_dir = Path(started["run_dir"])
    assert result["state"] == "complete"
    assert run_dir.is_dir()
    manifest = json.loads((run_dir / "capture_manifest.json").read_text())
    assert manifest["status"] == "stopped_unassessed"
    assert manifest["run_name"] == "Living Room morning"
    assert manifest["topics"] == ["/tf"]


def test_duration_auto_stops_and_marks_complete(tmp_path):
    session = CaptureSession(tmp_path, process_factory=lambda argv, **kw: FakeProcess(argv))
    session.start("short", duration_s=0.01, topics=["/tf"])
    time.sleep(0.05)
    assert session.snapshot()["state"] == "complete"
