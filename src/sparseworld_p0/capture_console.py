"""Local, attended ROS 2 capture session controller."""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence


class SessionBusyError(RuntimeError):
    pass


DEFAULT_TOPICS = [
    "/camera/color/image_raw", "/camera/color/camera_info",
    "/camera/depth/image_raw", "/camera/depth/camera_info",
    "/camera/left_ir/image_raw", "/camera/left_ir/camera_info",
    "/camera/right_ir/image_raw", "/camera/right_ir/camera_info",
    "/camera/accel/sample", "/camera/gyro/sample",
    "/camera/accel/imu_info", "/camera/gyro/imu_info",
    "/camera/device_status", "/tf", "/tf_static",
]


class CaptureSession:
    def __init__(self, output_dir: str | Path, *, process_factory: Callable | None = None,
                 driver_command: Sequence[str] | None = None, dry_run: bool = False):
        self.output_dir = Path(output_dir)
        self.process_factory = process_factory or subprocess.Popen
        self.driver_command = list(driver_command or ["ros2", "launch", "orbbec_camera", "gemini_330_series.launch.py"])
        self.dry_run = dry_run
        self._lock = threading.RLock()
        self._state = "idle"
        self._run: dict = {}
        self._processes: list = []
        self._timer: threading.Timer | None = None

    def snapshot(self) -> dict:
        with self._lock:
            out = dict(self._run)
            out.update(state=self._state, active=self._state in {"starting", "recording", "stopping"},
                       preview_available=(self._run.get("preview_jpeg") is not None))
            if out.get("started_at"):
                out["elapsed_s"] = max(0.0, time.time() - self._run["started_epoch"])
            return out

    def start(self, run_name: str, duration_s: float | None, topics: list[str]) -> dict:
        clean = re.sub(r"[^A-Za-z0-9_.-]+", " ", str(run_name)).strip()
        if not clean:
            raise ValueError("run_name must contain at least one safe character")
        if duration_s is not None and (duration_s <= 0 or duration_s > 86400):
            raise ValueError("duration_s must be between 0 and 86400 seconds")
        selected = list(topics or DEFAULT_TOPICS)
        with self._lock:
            if self._state in {"starting", "recording", "stopping"}:
                raise SessionBusyError("a capture session is already active")
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            run_dir = self.output_dir / f"{stamp}_{clean.replace(' ', '_')}"
            run_dir.mkdir(parents=True, exist_ok=False)
            self._run = {"run_name": clean, "run_dir": str(run_dir), "topics": selected,
                         "started_at": datetime.now(timezone.utc).isoformat(), "started_epoch": time.time(),
                         "preview_jpeg": None, "error": None}
            self._state = "starting"
            record_cmd = ["ros2", "bag", "record", "-o", str(run_dir / "bag"), *selected]
            try:
                if not self.dry_run:
                    self._processes = [
                        self.process_factory(self.driver_command, stdout=(run_dir / "driver.log").open("wb"), stderr=subprocess.STDOUT, start_new_session=True),
                        self.process_factory(record_cmd, stdout=(run_dir / "rosbag.log").open("wb"), stderr=subprocess.STDOUT, start_new_session=True),
                    ]
                self._run["commands"] = [self.driver_command, record_cmd]
                self._state = "recording"
                if duration_s is not None:
                    self._timer = threading.Timer(duration_s, self.stop)
                    self._timer.daemon = True
                    self._timer.start()
            except Exception as exc:
                self._run["error"] = f"{type(exc).__name__}: {exc}"
                self._state = "failed"
                self._write_manifest("failed_incomplete")
                raise
            return self.snapshot()

    def stop(self) -> dict:
        with self._lock:
            if self._state not in {"starting", "recording"}:
                return self.snapshot()
            self._state = "stopping"
            if self._timer:
                self._timer.cancel()
            for proc in self._processes:
                try:
                    if proc.poll() is None:
                        if self.process_factory is subprocess.Popen and hasattr(proc, "pid"):
                            try: os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                            except (OSError, ProcessLookupError): proc.terminate()
                        else: proc.terminate()
                        proc.wait(timeout=5)
                except Exception:
                    try: proc.kill()
                    except Exception: pass
            self._write_manifest("stopped_unassessed")
            self._state = "complete"
            return self.snapshot()

    def preview_jpeg(self) -> bytes | None:
        with self._lock:
            path = self._run.get("preview_jpeg")
        if path and Path(path).is_file():
            return Path(path).read_bytes()
        return None

    def _write_manifest(self, status: str) -> None:
        run_dir = Path(self._run["run_dir"])
        self._run["status"] = status
        self._run["stopped_at"] = datetime.now(timezone.utc).isoformat()
        payload = {k: v for k, v in self._run.items() if k not in {"started_epoch", "preview_jpeg"}}
        (run_dir / "capture_manifest.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
