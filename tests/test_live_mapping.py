import time

from sparseworld_p0.live_mapping import KeyframeGate, LatestFrameQueue, LiveSemanticWorker


def test_keyframe_gate_accepts_time_translation_and_rotation_thresholds():
    gate = KeyframeGate(min_interval_s=1.0, min_translation_m=0.35, min_rotation_deg=15.0)
    assert gate.accept(0.0, (0, 0, 0), 0.0)
    assert not gate.accept(0.5, (0, 0, 0), 0.0)
    assert gate.accept(0.5, (0.4, 0, 0), 0.0)
    assert gate.accept(0.6, (0.4, 0, 0), 20.0)


def test_latest_queue_replaces_stale_frame():
    queue = LatestFrameQueue()
    queue.put({"id": "old"})
    queue.put({"id": "new"})
    assert queue.get(timeout=0.01)["id"] == "new"
    assert queue.get(timeout=0.01) is None
    assert queue.stats()["dropped"] == 1


def test_worker_processes_frame_and_reports_errors_without_blocking():
    seen = []
    worker = LiveSemanticWorker(lambda frame: seen.append(frame["id"]))
    worker.start()
    worker.submit({"id": "kf-1"})
    for _ in range(20):
        if seen:
            break
        time.sleep(0.01)
    worker.stop()
    assert seen == ["kf-1"]
    assert worker.snapshot()["processed"] == 1
