"""Load-shed primitives for live sparse semantic mapping."""
from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable
from typing import Any


class KeyframeGate:
    def __init__(self, *, min_interval_s: float = 1.0, min_translation_m: float = 0.35, min_rotation_deg: float = 15.0):
        self.min_interval_s = min_interval_s
        self.min_translation_m = min_translation_m
        self.min_rotation_deg = min_rotation_deg
        self._last: tuple[float, tuple[float, float, float], float] | None = None

    def accept(self, timestamp: float, position: tuple[float, float, float], yaw: float) -> bool:
        if self._last is None:
            self._last = (timestamp, position, yaw)
            return True
        previous_time, previous_position, previous_yaw = self._last
        translation = math.dist(position, previous_position)
        angle = abs((yaw - previous_yaw + 180.0) % 360.0 - 180.0)
        if timestamp - previous_time >= self.min_interval_s or translation >= self.min_translation_m or angle >= self.min_rotation_deg:
            self._last = (timestamp, position, yaw)
            return True
        return False


class LatestFrameQueue:
    """Capacity-one queue: producers overwrite stale inference work."""
    def __init__(self):
        self._condition = threading.Condition()
        self._item: dict[str, Any] | None = None
        self._dropped = 0

    def put(self, frame: dict[str, Any]) -> None:
        with self._condition:
            if self._item is not None:
                self._dropped += 1
            self._item = frame
            self._condition.notify()

    def get(self, timeout: float | None = None) -> dict[str, Any] | None:
        with self._condition:
            if self._item is None:
                self._condition.wait(timeout)
            item, self._item = self._item, None
            return item

    def stats(self) -> dict[str, int]:
        with self._condition:
            return {"queued": int(self._item is not None), "dropped": self._dropped}


class LiveSemanticWorker:
    def __init__(self, handler: Callable[[dict[str, Any]], None]):
        self.queue = LatestFrameQueue()
        self.handler = handler
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._processed = 0
        self._failed = 0
        self._last_error: str | None = None
        self._last_latency_ms: float | None = None

    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="live-semantic-worker", daemon=True)
            self._thread.start()

    def submit(self, frame: dict[str, Any]) -> None:
        self.queue.put(frame)

    def stop(self) -> None:
        self._stop.set()
        self.queue.put({"_stop": True})
        if self._thread:
            self._thread.join(timeout=2)

    def snapshot(self) -> dict[str, Any]:
        return {"running": bool(self._thread and self._thread.is_alive()), "processed": self._processed,
                "failed": self._failed, "last_error": self._last_error, "last_latency_ms": self._last_latency_ms,
                **self.queue.stats()}

    def _run(self) -> None:
        while not self._stop.is_set():
            frame = self.queue.get(timeout=0.2)
            if frame is None or frame.get("_stop"):
                continue
            started = time.monotonic()
            try:
                self.handler(frame)
                self._processed += 1
            except Exception as exc:  # fail open: mapping front-end continues
                self._failed += 1
                self._last_error = f"{type(exc).__name__}: {exc}"
            finally:
                self._last_latency_ms = (time.monotonic() - started) * 1000.0
