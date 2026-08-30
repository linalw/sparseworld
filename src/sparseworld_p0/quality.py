"""Quality metrics and profile-gated P0 assessment."""
from __future__ import annotations
import hashlib, json
from collections.abc import Mapping, Sequence
from math import pi
from typing import Any
from .timing import analyze_device_host_clock_relation, analyze_device_host_offset, analyze_interstream, analyze_stream

def _metric(rows, keys):
    vals=[]
    for row in rows:
        for key in keys:
            value=row.get(key) if isinstance(row, Mapping) else None
            if isinstance(value,(int,float)) and not isinstance(value,bool): vals.append(float(value)); break
    return (sum(vals)/len(vals) if vals else None, len(vals))


def _fraction_from_counts(rows):
    vals = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        direct = next((row.get(k) for k in ("depth_valid_fraction", "valid_depth_fraction", "valid_fraction") if isinstance(row.get(k), (int, float))), None)
        if direct is not None:
            vals.append(float(direct)); continue
        valid = row.get("valid_count", row.get("valid_depth_count"))
        total = row.get("total_count", row.get("depth_count"))
        if isinstance(valid, (int,float)) and isinstance(total, (int,float)) and total > 0:
            vals.append(float(valid) / float(total))
    return (sum(vals) / len(vals) if vals else None, len(vals))


def _saturation_fraction(rows, vector_keys, limit, sensor=None):
    if limit is None or limit <= 0:
        return None, 0
    flags = []
    for row in rows:
        if sensor is not None and (not isinstance(row, Mapping) or row.get("sensor") != sensor):
            continue
        vec = next((row.get(k) for k in vector_keys if isinstance(row.get(k), (list, tuple))), None)
        if vec is None:
            candidate = row.get("imu_value") if isinstance(row, Mapping) else None
            if isinstance(candidate, Mapping):
                vec = candidate.values()
        if vec:
            flags.append(any(abs(float(v)) >= limit for v in vec if isinstance(v, (int,float))))
    return (sum(flags) / len(flags), len(flags)) if flags else (None, 0)


def _full_scale_observation(rows, sensor, full_scale):
    """Summarize normalized IMU magnitude against the SDK-declared range."""
    if full_scale is None or full_scale <= 0:
        return {"value": None, "sample_count": 0, "full_scale": None}
    values = []
    for row in rows:
        if not isinstance(row, Mapping) or row.get("sensor") != sensor:
            continue
        vector = row.get("imu_value")
        if not isinstance(vector, Mapping):
            continue
        components = [value for value in vector.values() if isinstance(value, (int, float)) and not isinstance(value, bool)]
        if components:
            values.append(max(abs(float(value)) for value in components) / full_scale)
    return {"value": sum(values) / len(values) if values else None, "sample_count": len(values), "full_scale": full_scale}


def _imu_full_scales(profile):
    stream = profile.streams.get("imu", {}) if hasattr(profile, "streams") else {}
    accel = stream.get("accel_full_scale_range") if isinstance(stream, Mapping) else None
    gyro = stream.get("gyro_full_scale_range") if isinstance(stream, Mapping) else None
    # SDK values are m/s^2 for accel and rad/s for gyro; convert declared dps.
    accel_scale = 4.0 * 9.80665 if accel == "ACCEL_FS_4g" else None
    gyro_scale = 1000.0 * pi / 180.0 if gyro == "FS_1000dps" else None
    return accel_scale, gyro_scale

def _threshold(profile, name, *aliases):
    gates = profile.quality_gates
    node = gates.get(name, {})
    if isinstance(node, Mapping):
        for key in aliases + ("threshold", "min", "max"):
            if key in node and isinstance(node[key], (int,float)): return float(node[key]), key
    for key in aliases + (name,):
        value = gates.get(key)
        if isinstance(value,(int,float)): return float(value), key
    return None, None


def _time_threshold(profile, name):
    node = profile.time_gates.get(name)
    if isinstance(node, Mapping):
        for key in ("maximum_ns", "max_ns", "threshold_ns"):
            value = node.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
    return None

def _gate(value, threshold, *, minimum=True, count=0, minimum_samples=2):
    criterion = "value >= profile threshold" if minimum else "value <= profile threshold"
    if value is None or count < minimum_samples: return {"status":"not_measured", "value":value, "sample_count":count, "criterion": criterion}
    if threshold is None: return {"status":"not_measured", "value":value, "sample_count":count, "criterion": criterion}
    passed = value >= threshold if minimum else value <= threshold
    return {"status":"pass" if passed else "fail", "value":value, "threshold":threshold, "sample_count":count, "criterion":criterion}

def assess(profile, samples: Mapping[str, Sequence[Mapping[str, Any]]], capture_metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
    canonical = json.dumps(samples, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()
    source_hash = hashlib.sha256(canonical).hexdigest()
    timing = {name: analyze_stream(rows) for name, rows in sorted(samples.items())}
    # The adapter stores accel and gyro under one logical ``imu`` stream, but
    # SDK delivery interleaves their timestamps.  Analyze each sensor clock
    # independently while retaining the aggregate entry for compatibility.
    imu_rows = samples.get("imu", [])
    if imu_rows:
        for sensor in ("accel", "gyro"):
            selected = [row for row in imu_rows if isinstance(row, Mapping) and row.get("sensor") == sensor]
            if selected:
                timing[f"imu.{sensor}"] = analyze_stream(selected)
    policy = profile.time_gates.get("timestamp_pairing_policy") if hasattr(profile, "time_gates") else None
    policy = policy if isinstance(policy, str) and policy != "pending_measurement" else None
    inter = analyze_interstream(samples, pairing_policy=policy)
    depth_v, depth_n = _fraction_from_counts(samples.get("depth", []))
    blur_v, blur_n = _metric(samples.get("rgb", []), ("blur_score", "blur", "laplacian_variance"))
    gyro_v, gyro_n = _metric(samples.get("imu", []), ("gyro_saturation_fraction", "gyro_saturation"))
    accel_v, accel_n = _metric(samples.get("imu", []), ("acceleration_saturation_fraction", "acceleration_saturation"))
    gyro_limit, _ = _threshold(profile, "gyro_saturation", "maximum", "max", "limit", "max_abs")
    accel_limit, _ = _threshold(profile, "acceleration_saturation", "maximum", "max", "limit", "max_abs")
    if gyro_v is None:
        gyro_v, gyro_n = _saturation_fraction(samples.get("imu", []), ("gyro", "angular_velocity"), gyro_limit, sensor="gyro")
    if accel_v is None:
        accel_v, accel_n = _saturation_fraction(samples.get("imu", []), ("acceleration", "linear_acceleration"), accel_limit, sensor="accel")
    # Explicit boolean saturation flags are accepted when fractions are absent.
    if gyro_v is None and gyro_n == 0:
        flags=[bool(r.get("gyro_saturated")) for r in samples.get("imu", []) if "gyro_saturated" in r]
        if flags: gyro_v=sum(flags)/len(flags); gyro_n=len(flags)
    if accel_v is None:
        flags=[bool(r.get("acceleration_saturated")) for r in samples.get("imu", []) if "acceleration_saturated" in r]
        if flags: accel_v=sum(flags)/len(flags); accel_n=len(flags)
    gates = {
      "depth_valid_fraction": _gate(depth_v, _threshold(profile,"depth_valid_fraction","minimum","min")[0], minimum=True, count=depth_n),
      "blur": _gate(blur_v, _threshold(profile,"blur","minimum","min")[0], minimum=True, count=blur_n),
      "gyro_saturation": _gate(gyro_v, _threshold(profile,"gyro_saturation","maximum","max")[0], minimum=False, count=gyro_n),
      "acceleration_saturation": _gate(accel_v, _threshold(profile,"acceleration_saturation","maximum","max")[0], minimum=False, count=accel_n),
    }
    accel_scale, gyro_scale = _imu_full_scales(profile)
    observations = {
        "acceleration_full_scale_fraction": _full_scale_observation(samples.get("imu", []), "accel", accel_scale),
        "gyro_full_scale_fraction": _full_scale_observation(samples.get("imu", []), "gyro", gyro_scale),
    }
    device_host_offset = analyze_device_host_offset(samples)
    device_host_clock_relation = analyze_device_host_clock_relation(samples)
    offset_value = device_host_offset["max_abs_ns"]
    gates["device_host_offset"] = _gate(
        offset_value, _time_threshold(profile, "device_host_offset"), minimum=False,
        count=device_host_offset["sample_count"], minimum_samples=1
    )
    # Profile-declared calibration/route gates remain unmeasured until evidence exists.
    for name in ("stationary_calibration", "hand_carried_supervised_route"):
        if name not in gates:
            gates[name] = {"status": "not_measured", "value": None, "sample_count": 0}
    statuses = [entry.get("status") for entry in gates.values()]
    overall = "fail" if "fail" in statuses else ("pass" if statuses and all(s == "pass" for s in statuses) else "not_measured")
    result = {"schema_version":"p0/assessment/v1", "status": overall,
            "source": {"raw": "normalized JSONL samples supplied to assess", "sha256": source_hash,
                       "format": "normalized_jsonl", "tool": "sparseworld-p0", "tool_version": "0.1.0",
                       "criterion": "deterministic_sha256_of_canonical_samples"},
            "source_sha256":source_hash, "timing":timing, "interstream":inter,
            "observations": observations,
            "device_host_clock_relation": device_host_clock_relation,
            "device_host_offset":device_host_offset, "gates":gates}
    if capture_metadata is not None:
        result["capture"] = dict(capture_metadata)
    return result
