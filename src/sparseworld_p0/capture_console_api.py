"""FastAPI application for the local Gemini capture console."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import FileResponse, Response
    from fastapi.staticfiles import StaticFiles
except ImportError:  # pragma: no cover - optional runtime
    FastAPI = None


def create_app(session=None):
    if FastAPI is None:
        raise RuntimeError("capture console requires optional dependencies; install sparseworld-p0[console]")
    if session is None:
        from .capture_console import CaptureSession
        session = CaptureSession("artifacts/rosbags")
    app = FastAPI(title="SparseWorld Gemini 335 Capture Console")
    static = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static), name="static")

    @app.get("/api/status")
    def status() -> dict[str, Any]:
        return session.snapshot()

    @app.post("/api/start")
    def start(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return session.start(payload.get("run_name", ""), payload.get("duration_s"), payload.get("topics") or [], mode=payload.get("mode", "capture"), debug_bag=bool(payload.get("debug_bag", False)))
        except Exception as exc:
            from .capture_console import SessionBusyError
            if isinstance(exc, SessionBusyError):
                raise HTTPException(409, str(exc))
            raise HTTPException(400, str(exc))

    @app.post("/api/stop")
    def stop() -> dict[str, Any]:
        return session.stop()

    @app.get("/api/runs")
    def runs() -> list[dict[str, Any]]:
        return session.list_runs()

    @app.get("/api/objects")
    def objects() -> list[dict[str, Any]]:
        snapshot = session.snapshot()
        run_dir = snapshot.get("run_dir")
        candidate = Path(run_dir) / "objects.json" if run_dir else None
        if not candidate or not candidate.is_file():
            return []
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    @app.get("/api/map/preview")
    def map_preview():
        run_dir = session.snapshot().get("run_dir")
        candidate = Path(run_dir) / "map-preview.jpg" if run_dir else None
        if not candidate or not candidate.is_file():
            raise HTTPException(404, "map_preview_unavailable")
        return FileResponse(candidate, media_type="image/jpeg")

    @app.get("/api/runs/{run_id}")
    def run_detail(run_id: str) -> dict[str, Any]:
        if Path(run_id).name != run_id:
            raise HTTPException(400, "invalid run id")
        for run in session.list_runs():
            if run["run_id"] == run_id:
                root = Path(run["manifest_path"]).parent
                run["files"] = sorted(p.name for p in root.iterdir() if p.is_file())
                return run
        raise HTTPException(404, "run not found")

    @app.get("/api/runs/{run_id}/files/{file_name}")
    def run_file(run_id: str, file_name: str):
        if Path(run_id).name != run_id or Path(file_name).name != file_name:
            raise HTTPException(400, "invalid path")
        for run in session.list_runs():
            if run["run_id"] == run_id:
                root = Path(run["manifest_path"]).parent
                candidate = root / file_name
                if not candidate.is_file():
                    raise HTTPException(404, "file not found")
                return FileResponse(candidate)
        raise HTTPException(404, "run not found")

    @app.get("/api/preview.mjpg")
    def preview():
        data = session.preview_jpeg()
        if data is None:
            raise HTTPException(404, "preview_unavailable")
        return Response(content=data, media_type="image/jpeg")

    @app.get("/api/preview/depth.jpg")
    def depth_preview():
        run_dir = session.snapshot().get("run_dir")
        candidate = Path(run_dir) / "depth-preview.jpg" if run_dir else None
        if not candidate or not candidate.is_file():
            raise HTTPException(404, "depth_preview_unavailable")
        return FileResponse(candidate, media_type="image/jpeg")

    @app.get("/")
    def index():
        return FileResponse(static / "capture_console.html")

    return app


def mjpeg_stream(session):
    """Yield a latest-frame MJPEG stream for simple browser clients."""
    import time
    while True:
        frame = session.preview_jpeg()
        if frame:
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
        time.sleep(0.2)
