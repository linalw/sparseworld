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
    session = CaptureSession(tmp_path)
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


def test_elapsed_time_is_frozen_after_stop(tmp_path):
    session = CaptureSession(tmp_path, process_factory=lambda argv, **kw: FakeProcess(argv))
    session.start("short", duration_s=None, topics=["/tf"])
    time.sleep(0.01)
    stopped = session.stop()["elapsed_s"]
    time.sleep(0.03)
    assert session.snapshot()["elapsed_s"] == pytest.approx(stopped, abs=0.001)


def test_lists_completed_runs_with_manifest(tmp_path):
    session = CaptureSession(tmp_path, process_factory=lambda argv, **kw: FakeProcess(argv))
    session.start("route", duration_s=None, topics=["/tf"])
    session.stop()
    runs = session.list_runs()
    assert len(runs) == 1
    assert runs[0]["status"] == "stopped_unassessed"
    assert runs[0]["manifest_path"].endswith("capture_manifest.json")


def test_start_records_preview_status_and_command(tmp_path):
    session = CaptureSession(tmp_path, process_factory=lambda argv, **kw: FakeProcess(argv), dry_run=True)
    started = session.start("route", None, ["/tf"])
    assert started["preview_status"] == "dry_run"
    assert any("preview" in " ".join(cmd) for cmd in started["commands"])
    session.stop()


def test_start_records_rgb_and_depth_preview_commands(tmp_path):
    session = CaptureSession(tmp_path, process_factory=lambda argv, **kw: FakeProcess(argv), dry_run=True)
    started = session.start("route", None, ["/tf"])
    commands = [" ".join(cmd) for cmd in started["commands"]]
    assert any("preview.jpg" in cmd for cmd in commands)
    assert any("depth-preview.jpg" in cmd for cmd in commands)
    session.stop()


def test_real_capture_refuses_when_no_video_device_exists(tmp_path, monkeypatch):
    monkeypatch.setattr("sparseworld_p0.capture_console.glob.glob", lambda _: [])
    session = CaptureSession(tmp_path)
    with pytest.raises(RuntimeError, match="no /dev/video"):
        session.start("route", None, ["/tf"])


def test_live_mode_does_not_record_bag_without_debug_option(tmp_path):
    session = CaptureSession(tmp_path, process_factory=lambda argv, **kw: FakeProcess(argv), dry_run=True)
    state = session.start("live", None, ["/tf"], mode="live", debug_bag=False)
    commands = [" ".join(command) for command in state["commands"]]
    assert state["mode"] == "live"
    assert not any(" bag record " in f" {command} " for command in commands)
    assert state["storage_policy"] == "sparse_no_raw_bag"
    session.stop()


def test_live_mode_records_bag_only_when_debug_option_is_enabled(tmp_path):
    session = CaptureSession(tmp_path, process_factory=lambda argv, **kw: FakeProcess(argv), dry_run=True)
    state = session.start("live", None, ["/tf"], mode="live", debug_bag=True)
    assert any("bag record" in " ".join(command) for command in state["commands"])
    session.stop()


def test_live_mode_uses_rtabmap_launch_with_run_local_database(tmp_path):
    session = CaptureSession(tmp_path, process_factory=lambda argv, **kw: FakeProcess(argv), dry_run=True)
    state = session.start("live", None, ["/tf"], mode="live")
    slam = next(command for command in state["commands"] if "rtabmap_launch" in command)
    assert slam[:4] == ["ros2", "launch", "rtabmap_launch", "rtabmap.launch.py"]
    assert any("database_path:=" in arg and "rtabmap.db" in arg for arg in slam)
    session.stop()


def test_live_mode_launches_keyframe_bridge_and_reports_sparse_storage(tmp_path):
    session = CaptureSession(tmp_path, process_factory=lambda argv, **kw: FakeProcess(argv), dry_run=True)
    state = session.start("live", None, [], mode="live")
    assert any("p0_live_keyframe_bridge.py" in " ".join(command) for command in state["commands"])
    assert state["keyframe_policy"]["max_rate_hz"] == 1.0
    session.stop()
