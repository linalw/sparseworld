"""Deterministic timing analysis for normalized JSONL samples."""
from __future__ import annotations
from collections.abc import Mapping, Sequence
from statistics import median, pstdev
from typing import Any

def _num(sample: Mapping[str, Any], *keys: str):
    for key in keys:
        value = sample.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
    return None

def _timestamp_ns(sample: Mapping[str, Any], *, ros_header: bool = False):
    # Explicit *_ns fields only; unitless timestamps are rejected.
    return _num(sample, "header_time_ns") if ros_header else _num(sample, "device_time_ns", "timestamp_ns", "ts_ns")

def _normalized_id(value: Any):
    if isinstance(value, bool): return None
    if isinstance(value, int): return value
    if isinstance(value, str):
        try: return int(value)
        except ValueError: return value
    return None

def _frame(sample: Mapping[str, Any], include_seq: bool = True, ros_header: bool = False):
    keys = ("frame_number", "sdk_frame_number", "frame_num") + (("seq",) if include_seq else ())
    for key in keys:
        value = _normalized_id(sample.get(key))
        if value is not None: return value
    header = sample.get("header")
    if ros_header and isinstance(header, Mapping):
        for key in ("frame_number", "seq"):
            value = _normalized_id(header.get(key))
            if value is not None: return value
    return None

def _sorted_ids(values):
    return sorted(values, key=lambda value: (0, value) if isinstance(value, int) else (1, value))

def _sequence_summary(rows):
    seen, duplicates, out_of_order = set(), set(), 0
    previous = None
    for row in rows:
        value = _normalized_id(row.get("seq", row.get("sequence")))
        if not isinstance(value, int): continue
        if previous is not None and value < previous: out_of_order += 1
        previous = value
        if value in seen: duplicates.add(value)
        seen.add(value)
    ordered = sorted(seen)
    missing = sum(max(0, right-left-1) for left, right in zip(ordered, ordered[1:])) if ordered else None
    return missing, sorted(duplicates), out_of_order

def analyze_stream(samples: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    rows = [sample for sample in samples if isinstance(sample, Mapping)]
    timestamps = [float(value) for sample in rows if (value := _timestamp_ns(sample)) is not None]
    missing, duplicates, out_of_order = _sequence_summary(rows)
    result = {"status":"not_measured", "sample_count":len(rows), "timestamp_count":len(timestamps),
              "missing_sequences":missing, "duplicate_sequences":duplicates,
              "out_of_order_sequences":out_of_order, "nonmonotonic_timestamps":None,
              "observed_rate_hz":None, "jitter_s":None}
    if len(timestamps) < 2: return result
    intervals_ns = [b-a for a,b in zip(timestamps, timestamps[1:])]
    result["nonmonotonic_timestamps"] = sum(delta <= 0 for delta in intervals_ns)
    result["monotonic"] = result["nonmonotonic_timestamps"] == 0
    duration_ns = timestamps[-1] - timestamps[0]
    if result["nonmonotonic_timestamps"] or duration_ns <= 0: return result
    result["observed_rate_hz"] = len(timestamps) / (duration_ns * 1e-9)
    result["jitter_s"] = pstdev([d * 1e-9 for d in intervals_ns]) if len(intervals_ns) > 1 else 0.0
    result["status"] = "measured"
    return result

def _pair_rows(rows, *, ros_header):
    grouped = {}
    for sample in rows:
        if not isinstance(sample, Mapping): continue
        frame, timestamp = _frame(sample, include_seq=False, ros_header=ros_header), _timestamp_ns(sample, ros_header=ros_header)
        if frame is not None and timestamp is not None: grouped.setdefault(frame, []).append(float(timestamp))
    duplicates = _sorted_ids(frame for frame, values in grouped.items() if len(values) > 1)
    return {frame: values[0] for frame, values in grouped.items() if len(values) == 1}, duplicates

def analyze_interstream(samples_by_stream: Mapping[str, Sequence[Mapping[str, Any]]], pairing_policy: str | None = None) -> dict[str, Any]:
    ros_header = bool(pairing_policy and "ros" in pairing_policy.lower() and "header" in pairing_policy.lower())
    indexed = {name: _pair_rows(rows, ros_header=ros_header) for name, rows in samples_by_stream.items()}
    offsets, duplicate_frame_ids = {}, {name: dup for name, (_, dup) in indexed.items() if dup}
    streams = list(samples_by_stream)
    for i, left_name in enumerate(streams):
        for right_name in streams[i+1:]:
            left, right = indexed[left_name][0], indexed[right_name][0]
            common = _sorted_ids(set(left) & set(right))
            if common: offsets[f"{left_name}-{right_name}"] = [right[k]-left[k] for k in common]
    return {"pairing_status":"measured" if offsets else "not_measured", "pairing_clock":"header_time_ns" if ros_header else "device_time_ns",
            "offsets_ns":offsets, "duplicate_frame_ids":duplicate_frame_ids, "drift_ns_per_s":_drift(indexed, offsets)}

def _drift(indexed, offsets):
    values = []
    for pair, pair_offsets in offsets.items():
        if len(pair_offsets) < 2: continue
        a,b = pair.split("-",1); left,right = indexed[a][0], indexed[b][0]
        for frame in _sorted_ids(set(left)&set(right)): values.append((left[frame], right[frame]-left[frame]))
    if len(values) < 2: return None
    elapsed_s = (values[-1][0]-values[0][0]) * 1e-9
    return (values[-1][1]-values[0][1])/elapsed_s if elapsed_s > 0 else None

def analyze_device_host_offset(samples_by_stream):
    offsets = []
    for rows in samples_by_stream.values():
        for sample in rows:
            if not isinstance(sample, Mapping): continue
            device, host = _num(sample, "device_time_ns"), _num(sample, "host_receive_time_ns")
            if device is not None and host is not None: offsets.append(float(host)-float(device))
    absolute = [abs(value) for value in offsets]
    return {"status":"measured" if offsets else "not_measured", "offsets_ns":offsets, "sample_count":len(offsets),
            "median_abs_ns":median(absolute) if absolute else None, "max_abs_ns":max(absolute) if absolute else None}
