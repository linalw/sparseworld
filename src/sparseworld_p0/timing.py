"""Deterministic timing analysis for normalized JSONL samples."""
from __future__ import annotations
from collections.abc import Mapping, Sequence
from statistics import pstdev
from typing import Any


def _num(sample: Mapping[str, Any], *keys: str):
    for key in keys:
        value = sample.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
    return None


def _timestamp(sample: Mapping[str, Any]):
    value = _num(sample, "timestamp_ns", "ts_ns", "timestamp")
    if isinstance(value, Mapping):
        return None
    return value


def _frame(sample: Mapping[str, Any], include_seq: bool = True, ros_header: bool = False):
    keys = ("frame_number", "sdk_frame_number", "frame_num") + (("seq",) if include_seq else ())
    for key in keys:
        value = sample.get(key)
        if isinstance(value, (int, str)) and not isinstance(value, bool):
            return value
    header = sample.get("header")
    if ros_header and isinstance(header, Mapping):
        value = header.get("frame_number", header.get("seq"))
        if isinstance(value, (int, str)) and not isinstance(value, bool):
            return value
    return None


def analyze_stream(samples: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    rows = [s for s in samples if isinstance(s, Mapping)]
    timestamps = [float(_timestamp(s)) for s in rows if _timestamp(s) is not None]
    result: dict[str, Any] = {
        "status": "not_measured", "sample_count": len(rows),
        "missing_sequences": None, "nonmonotonic_timestamps": None,
        "observed_rate_hz": None, "jitter_s": None,
    }
    seqs = [_num(s, "seq", "sequence") for s in rows]
    seqs = [int(v) for v in seqs if v is not None]
    if seqs:
        result["missing_sequences"] = max(0, sum(max(0, b - a - 1) for a, b in zip(seqs, seqs[1:])))
    if len(timestamps) >= 2:
        intervals = [b - a for a, b in zip(timestamps, timestamps[1:])]
        result["nonmonotonic_timestamps"] = sum(1 for d in intervals if d <= 0)
        result["monotonic"] = result["nonmonotonic_timestamps"] == 0
        duration = timestamps[-1] - timestamps[0]
        # A timestamp_ns stream is converted to seconds; plain timestamp is assumed seconds.
        scale = 1e-9 if any(_timestamp(s) is not None and abs(float(_timestamp(s))) > 1e6 for s in rows) else 1.0
        duration_s = duration * scale
        intervals_s = [d * scale for d in intervals]
        if duration_s > 0:
            result["observed_rate_hz"] = len(rows) / duration_s
            result["jitter_s"] = pstdev(intervals_s) if len(intervals_s) > 1 else 0.0
        result["status"] = "measured"
    return result


def analyze_interstream(
    samples_by_stream: Mapping[str, Sequence[Mapping[str, Any]]], pairing_policy: str | None = None
) -> dict[str, Any]:
    offsets: dict[str, list[float]] = {}
    streams = list(samples_by_stream)
    for i, left_name in enumerate(streams):
        for right_name in streams[i + 1:]:
            ros_header = bool(pairing_policy and "ros" in pairing_policy.lower() and "header" in pairing_policy.lower())
            left = {str(_frame(s, include_seq=False, ros_header=ros_header)): _timestamp(s) for s in samples_by_stream[left_name] if _frame(s, include_seq=False, ros_header=ros_header) is not None and _timestamp(s) is not None}
            right = {str(_frame(s, include_seq=False, ros_header=ros_header)): _timestamp(s) for s in samples_by_stream[right_name] if _frame(s, include_seq=False, ros_header=ros_header) is not None and _timestamp(s) is not None}
            common = sorted(set(left) & set(right))
            if common:
                offsets[f"{left_name}-{right_name}"] = [float(right[k]) - float(left[k]) for k in common]
    return {"pairing_status": "measured" if offsets else "not_measured", "offsets_ns": offsets,
            "drift_ns_per_s": _drift(samples_by_stream, offsets, pairing_policy)}


def _drift(samples_by_stream, offsets, pairing_policy):
    # Drift is only meaningful with >=2 compatible pairs and timestamps.
    values = []
    for pair, offs in offsets.items():
        if len(offs) < 2: continue
        a, b = pair.split("-", 1)
        ros_header = bool(pairing_policy and "ros" in pairing_policy.lower() and "header" in pairing_policy.lower())
        left = {str(_frame(s, include_seq=False, ros_header=ros_header)): _timestamp(s) for s in samples_by_stream[a] if _frame(s, include_seq=False, ros_header=ros_header) is not None and _timestamp(s) is not None}
        right = {str(_frame(s, include_seq=False, ros_header=ros_header)): _timestamp(s) for s in samples_by_stream[b] if _frame(s, include_seq=False, ros_header=ros_header) is not None and _timestamp(s) is not None}
        for k in sorted(set(left)&set(right)):
            values.append((float(left[k]), float(right[k])-float(left[k])))
    if len(values) < 2: return None
    x0, y0 = values[0]
    x1, y1 = values[-1]
    dt = (x1-x0) * (1e-9 if max(abs(x0), abs(x1)) > 1e6 else 1.0)
    return (y1-y0)/dt if dt else None
