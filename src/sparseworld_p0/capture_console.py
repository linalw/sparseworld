"""Local, attended ROS 2 capture session controller."""
from __future__ import annotations

import json
import glob
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
                       preview_available=(self._run.get("preview_jpeg") is not None or bool(self._run.get("run_dir") and Path(self._run["run_dir"], "preview.jpg").is_file())),
                       preview_status=self._run.get("preview_status", "unavailable"),
                       preview_error=self._run.get("preview_error"))
            if self._state == "recording":
                for proc in self._processes:
                    if proc.poll() not in (None, 0):
                        self._run["error"] = f"capture subprocess exited with code {proc.poll()}"
                        out["error"] = self._run["error"]
                        out["state_warning"] = "录制进程异常退出，请停止并检查日志"
                        break
            if out.get("started_at"):
                out["elapsed_s"] = self._run.get("elapsed_s", max(0.0, time.time() - self._run["started_epoch"]))
            return out

    def list_runs(self) -> list[dict]:
        """Return saved run manifests without exposing arbitrary filesystem paths."""
        if not self.output_dir.is_dir():
            return []
        records: list[dict] = []
        for manifest_path in sorted(self.output_dir.glob("*/capture_manifest.json"), reverse=True):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(manifest, dict):
                records.append({
                    "run_name": manifest.get("run_name", manifest_path.parent.name),
                    "status": manifest.get("status", "unknown"),
                    "started_at": manifest.get("started_at"),
                    "stopped_at": manifest.get("stopped_at"),
                    "run_id": manifest_path.parent.name,
                    "manifest_path": str(manifest_path),
                    "bag_available": (manifest_path.parent / "bag").is_dir(),
                })
        return records

    def start(self, run_name: str, duration_s: float | None, topics: list[str]) -> dict:
        clean = re.sub(r"[^A-Za-z0-9_.-]+", " ", str(run_name)).strip()
        if not clean:
            raise ValueError("run_name must contain at least one safe character")
        if duration_s is not None and (duration_s <= 0 or duration_s > 86400):
            raise ValueError("duration_s must be between 0 and 86400 seconds")
        selected = list(topics or DEFAULT_TOPICS)
        if not self.dry_run and self.process_factory is subprocess.Popen and not glob.glob("/dev/video*"):
            raise RuntimeError("no /dev/video device found; reconnect Gemini 335 and verify USB3/video-group access")
        with self._lock:
            if self._state in {"starting", "recording", "stopping"}:
                raise SessionBusyError("a capture session is already active")
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            run_dir = self.output_dir / f"{stamp}_{clean.replace(' ', '_')}"
            run_dir.mkdir(parents=True, exist_ok=False)
            self._run = {"run_name": clean, "run_dir": str(run_dir), "topics": selected,
                         "started_at": datetime.now(timezone.utc).isoformat(), "started_epoch": time.time(),
                         "preview_jpeg": None, "preview_status": "starting", "preview_error": None, "error": None}
            self._state = "starting"
            record_cmd = ["ros2", "bag", "record", "-o", str(run_dir / "bag"), *selected]
            preview_script = Path(__file__).resolve().parents[2] / "scripts" / "p0_ros_preview.py"
            preview_cmd = ["/usr/bin/python3", str(preview_script), "--output", str(run_dir / "preview.jpg")]
            try:
                if not self.dry_run:
                    self._processes = [
                        self.process_factory(self.driver_command, stdout=(run_dir / "driver.log").open("wb"), stderr=subprocess.STDOUT, start_new_session=True),
                        self.process_factory(record_cmd, stdout=(run_dir / "rosbag.log").open("wb"), stderr=subprocess.STDOUT, start_new_session=True),
                    ]
                    try:
                        self._processes.append(self.process_factory(preview_cmd, stdout=(run_dir / "preview.log").open("wb"), stderr=subprocess.STDOUT, start_new_session=True))
                    except Exception as exc:
                        self._run["preview_status"] = "unavailable"
                        self._run["preview_error"] = f"{type(exc).__name__}: {exc}"
                else:
                    self._run["preview_status"] = "dry_run"
                self._run["commands"] = [self.driver_command, record_cmd, preview_cmd]
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
            status = "stopped_unassessed"
            if self._run.get("error") or self._run.get("preview_error"):
                status = "failed_incomplete"
            self._write_manifest(status)
            self._state = "complete"
            return self.snapshot()

    def preview_jpeg(self) -> bytes | None:
        with self._lock:
            path = self._run.get("preview_jpeg")
        candidate = Path(path) if path else (Path(self._run.get("run_dir", "")) / "preview.jpg")
        if candidate.is_file():
            return candidate.read_bytes()
        return None

    def _write_manifest(self, status: str) -> None:
        run_dir = Path(self._run["run_dir"])
        self._run["status"] = status
        self._run["elapsed_s"] = max(0.0, time.time() - self._run["started_epoch"])
        self._run["stopped_at"] = datetime.now(timezone.utc).isoformat()
        payload = {k: v for k, v in self._run.items() if k not in {"started_epoch", "preview_jpeg"}}
        (run_dir / "capture_manifest.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
