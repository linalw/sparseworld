"""Fail-closed, optional Orbbec SDK capture adapter for P0 evidence."""

from __future__ import annotations

import json
import hashlib
from math import isfinite
import re
import time
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any, Mapping


_SENSOR_NAMES = {
    "rgb": "COLOR_SENSOR",
    "depth": "DEPTH_SENSOR",
    "left": "LEFT_IR_SENSOR",
    "right": "RIGHT_IR_SENSOR",
}


def capture_orbbec(profile: Any, output_dir: str | Path, duration_s: float) -> dict[str, Any]:
    """Capture bounded timestamp evidence with the matching Orbbec device.

    This deliberately does not choose another connected camera, invent stream
    data, or continue after an SDK/device/permission/stream failure.  It is
    intended for an attended run after the documented preflight checks.
    """
    if not isinstance(duration_s, (int, float)) or isinstance(duration_s, bool) or duration_s <= 0:
        raise ValueError("duration_s must be a positive number")
    device_config = _section(profile, "device")
    streams = _section(profile, "streams")
    serial = device_config.get("serial")
    if not isinstance(serial, str) or not serial.strip():
        raise RuntimeError("capture refused: profile device.serial is required")
    try:
        import pyorbbecsdk as sdk
    except (ImportError, ModuleNotFoundError, OSError) as error:
        raise RuntimeError(
            "capture refused: pyorbbecsdk is unavailable; install the checksum-recorded Orbbec SDK Python binding first"
        ) from error
    if not streams:
        raise RuntimeError("capture refused: profile must request at least one stream")

    output = Path(output_dir)
    samples_path = output / "timestamps.jsonl"
    started_ns: int | None = None
    active_streams: list[str] = []
    per_stream_counts: dict[str, int] = {}
    info: Any = None
    actual_serial: Any = serial
    actual_profiles: dict[str, Any] = {}
    pipeline: Any = None

    try:
        context = sdk.Context()
        device = _device_with_serial(context, serial)
        if device is None:
            raise RuntimeError(f"capture refused: no Orbbec device matched requested serial {serial!r}")
        info = device.get_device_info()
        actual_serial = _call_first(info, "get_serial_number", "serial_number")
        if actual_serial != serial:
            raise RuntimeError(f"capture refused: SDK returned serial {actual_serial!r}, expected {serial!r}")
        pipeline = sdk.Pipeline(device)
        config = sdk.Config()
        active_streams, actual_profiles = _enable_requested_streams(sdk, pipeline, config, streams)
        pipeline.start(config)
    except PermissionError as error:
        _write_failure_manifest(output, profile, samples_path, actual_serial, info, active_streams, actual_profiles, per_stream_counts, started_ns, error)
        raise RuntimeError("capture refused: permission denied while opening Orbbec device; verify video-group access after a new login") from error
    except RuntimeError as error:
        if _looks_like_device_access_error(error):
            _write_failure_manifest(output, profile, samples_path, actual_serial, info, active_streams, actual_profiles, per_stream_counts, started_ns, error)
            raise RuntimeError("capture refused: permission denied while opening Orbbec device; verify video-group access after a new login") from error
        _write_failure_manifest(output, profile, samples_path, actual_serial, info, active_streams, actual_profiles, per_stream_counts, started_ns, error)
        raise
    except Exception as error:
        if _looks_like_device_access_error(error):
            _write_failure_manifest(output, profile, samples_path, actual_serial, info, active_streams, actual_profiles, per_stream_counts, started_ns, error, getattr(sdk, "__version__", "unknown"))
            raise RuntimeError("capture refused: permission denied while opening Orbbec device; verify video-group access after a new login") from error
        _write_failure_manifest(output, profile, samples_path, actual_serial, info, active_streams, actual_profiles, per_stream_counts, started_ns, error, getattr(sdk, "__version__", "unknown"))
        raise RuntimeError(f"capture refused: Orbbec SDK setup failed ({type(error).__name__}: {error})") from error

    try:
        output.mkdir(parents=True, exist_ok=True)
        diagnostics = _section(profile, "diagnostics")
        window_s = diagnostics.get("window_seconds", 30)
        max_samples = max(1, int(float(window_s) * 120))
        per_stream_limit = {name: max_samples for name in active_streams}
        per_stream_counts = {name: 0 for name in active_streams}
        started_ns = time.time_ns()
        deadline = time.monotonic() + float(duration_s)
        with samples_path.open("w", encoding="utf-8") as handle:
            while time.monotonic() < deadline:
                frames = pipeline.wait_for_frames(1000)
                host_timestamp_ns = time.time_ns()
                if frames is None:
                    continue
                emitted = 0
                for name, sensor, frame in _frames_for(frames, active_streams):
                    if frame is None:
                        # Gemini 335 may return video and IMU frames in separate
                        # FrameSets.  A missing frame here only means it was not
                        # delivered in this SDK batch; capture completeness is
                        # checked across the full bounded window below.
                        continue
                    if per_stream_counts[name] >= per_stream_limit[name]:
                        continue
                    row = _normalise_frame(name, sensor, frame, host_timestamp_ns)
                    handle.write(json.dumps(row, sort_keys=True) + "\n")
                    per_stream_counts[name] += 1
                    emitted += 1
        if any(per_stream_counts[name] == 0 for name in active_streams):
            raise RuntimeError("capture refused: one or more requested streams produced no retained samples")
        stopped_ns = time.time_ns()
        profile_payload = json.dumps(_canonical_profile_payload(profile), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        manifest = {
            "schema_version": "p0/orbbec-capture/v1",
            "status": "captured_unassessed",
            "serial": actual_serial,
            "model": _call_first(info, "get_name", "name"),
            "firmware": _call_first(info, "get_firmware_version", "firmware_version"),
            "sdk_version": getattr(sdk, "__version__", "unknown"),
            "requested_streams": sorted(streams),
            "active_streams": active_streams,
            "actual_stream_profiles": actual_profiles,
            "profile_sha256": hashlib.sha256(profile_payload).hexdigest(),
            "started_host_timestamp_ns": started_ns,
            "stopped_host_timestamp_ns": stopped_ns,
            "duration_s_requested": duration_s,
            "timestamp_file": samples_path.name,
            "timestamp_samples_written": sum(per_stream_counts.values()),
            "per_stream_counts": per_stream_counts,
            "imu_sensor_counts": {sensor: sum(1 for line in samples_path.read_text(encoding="utf-8").splitlines() if json.loads(line).get("sensor") == sensor) for sensor in ("accel", "gyro")},
            "timestamp_contract": {"device_time_field": "device_time_ns", "host_time_field": "host_receive_time_ns", "device_unit": "nanoseconds", "source": "Frame.get_timestamp_us multiplied by 1000"},
            "diagnostics": {"storage": diagnostics.get("storage"), "window_seconds": window_s, "max_timestamp_samples_per_stream": max_samples},
            "interpretation": "capture evidence only; calibration, synchronization, and performance remain unassessed until raw outputs are reviewed",
        }
        (output / "capture_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return manifest
    except PermissionError as error:
        _write_failure_manifest(output, profile, samples_path, actual_serial, info, active_streams, actual_profiles, per_stream_counts, started_ns, error, getattr(sdk, "__version__", "unknown"))
        raise RuntimeError("capture refused: permission denied while writing capture evidence") from error
    except RuntimeError as error:
        _write_failure_manifest(output, profile, samples_path, actual_serial, info, active_streams, actual_profiles, per_stream_counts, started_ns, error, getattr(sdk, "__version__", "unknown"))
        raise
    except Exception as error:
        _write_failure_manifest(output, profile, samples_path, actual_serial, info, active_streams, actual_profiles, per_stream_counts, started_ns, error, getattr(sdk, "__version__", "unknown"))
        raise RuntimeError(f"capture refused: capture failed ({type(error).__name__}: {error})") from error
    finally:
        try:
            pipeline.stop()
        except Exception:
            pass


def _section(profile: Any, name: str) -> Mapping[str, Any]:
    value = getattr(profile, name, None)
    if value is None and isinstance(profile, Mapping):
        value = profile.get(name)
    return value if isinstance(value, Mapping) else {}


def _device_with_serial(context: Any, serial: str) -> Any | None:
    devices = context.query_devices()
    count = devices.get_count()
    for index in range(count):
        device = devices.get_device_by_index(index)
        info = device.get_device_info()
        if _call_first(info, "get_serial_number", "serial_number") == serial:
            return device
    return None


def _enable_requested_streams(sdk: Any, pipeline: Any, config: Any, streams: Mapping[str, Any]) -> tuple[list[str], dict[str, Any]]:
    active: list[str] = []
    actual: dict[str, Any] = {}
    for name, requested in streams.items():
        if not isinstance(requested, Mapping):
            raise RuntimeError(f"capture refused: stream {name!r} configuration must be a mapping")
        if not requested.get("resolution") or not requested.get("nominal_rate"):
            raise RuntimeError(f"capture refused: stream {name!r} must declare resolution and nominal_rate")
        sensor_name = _SENSOR_NAMES.get(name)
        if name == "imu":
            try:
                config.enable_accel_stream()
                config.enable_gyro_stream()
            except Exception as error:
                raise RuntimeError("capture refused: IMU requires enable_accel_stream and enable_gyro_stream") from error
            active.append(name)
            actual[name] = {
                "accel": _imu_profile_provenance(requested, "accel"),
                "gyro": _imu_profile_provenance(requested, "gyro"),
                "profile_validation": "pending_measurement",
            }
            continue
        if sensor_name is None:
            raise RuntimeError(f"capture refused: unsupported requested stream {name!r}")
        sensor_type = getattr(sdk.OBSensorType, sensor_name, None)
        if sensor_type is None:
            raise RuntimeError(f"capture refused: SDK lacks {sensor_name} required for {name}")
        try:
            profiles = pipeline.get_stream_profile_list(sensor_type)
            profile = profiles.get_default_video_stream_profile()
            actual_profile = _profile_description(profile)
            actual_profile["profile_validation"] = _validate_requested_profile(name, requested, actual_profile)
            config.enable_stream(profile)
        except RuntimeError:
            raise
        except Exception as error:
            raise RuntimeError(f"capture refused: requested {name} stream is unavailable") from error
        active.append(name)
        actual[name] = actual_profile
    return active, actual


def _frame_for(frames: Any, name: str) -> Any:
    methods = {
        "rgb": ("get_color_frame",), "depth": ("get_depth_frame",),
        "left": ("get_left_ir_frame", "get_ir_frame"), "right": ("get_right_ir_frame",),
        "imu": ("get_accel_frame",),
    }[name]
    for method in methods:
        candidate = getattr(frames, method, None)
        if candidate is not None:
            value = candidate()
            if value is not None:
                return value
    return None


def _frames_for(frames: Any, active_streams: list[str]):
    for name in active_streams:
        if name == "imu":
            yield "imu", "accel", _call_first(frames, "get_accel_frame", "accel_frame")
            yield "imu", "gyro", _call_first(frames, "get_gyro_frame", "gyro_frame")
        else:
            yield name, None, _frame_for(frames, name)


def _timestamp_ns(frame: Any) -> int | None:
    value = _call_first(frame, "get_timestamp_us")
    if isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value):
        return int(value * 1000)
    value = _call_first(frame, "get_timestamp")
    if isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value):
        return int(value * 1_000_000)
    return None


def _normalise_frame(stream: str, sensor: str | None, frame: Any, host_timestamp_ns: int) -> dict[str, Any]:
    device_time_ns = _timestamp_ns(frame)
    if device_time_ns is None:
        raise RuntimeError("capture refused: device timestamp is unavailable")
    row = {
        "stream": stream,
        "sensor": sensor,
        "device_time_ns": device_time_ns,
        "host_receive_time_ns": host_timestamp_ns,
        "sdk_frame_number": _call_first(frame, "get_frame_number", "get_index", "frame_number", "index"),
    }
    if stream == "imu":
        value = _call_first(frame, "get_value")
        components = {axis: getattr(value, axis, None) for axis in ("x", "y", "z")}
        if all(isinstance(component, (int, float)) and not isinstance(component, bool) and isfinite(component) for component in components.values()):
            row["imu_value"] = {axis: float(component) for axis, component in components.items()}
        temperature = _call_first(frame, "get_temperature", "temperature")
        if isinstance(temperature, (int, float)) and not isinstance(temperature, bool) and isfinite(temperature):
            row["temperature_c"] = float(temperature)
    return row


def _profile_description(profile: Any) -> dict[str, Any]:
    return {"width": _call_first(profile, "get_width", "width"), "height": _call_first(profile, "get_height", "height"), "fps": _call_first(profile, "get_fps", "fps"), "format": str(_call_first(profile, "get_format", "format"))}


def _validate_requested_profile(name: str, requested: Mapping[str, Any], actual: Mapping[str, Any]) -> str:
    resolution = requested.get("resolution")
    rate = requested.get("nominal_rate")
    requested_format = requested.get("format")
    pending = resolution == "pending_measurement" or rate == "pending_measurement" or requested_format == "pending_measurement"
    if resolution != "pending_measurement":
        match = re.fullmatch(r"\s*(\d+)x(\d+)\s*", str(resolution))
        if not match or (actual.get("width"), actual.get("height")) != (int(match.group(1)), int(match.group(2))):
            raise RuntimeError(f"capture refused: {name} profile resolution does not match requested {resolution!r}")
    if rate != "pending_measurement":
        try: expected = float(rate)
        except (TypeError, ValueError): raise RuntimeError(f"capture refused: {name} nominal_rate is invalid")
        if actual.get("fps") is None or float(actual["fps"]) != expected:
            raise RuntimeError(f"capture refused: {name} profile fps does not match requested {rate!r}")
    if requested_format not in (None, "pending_measurement"):
        actual_format = str(actual.get("format", "")).removeprefix("OBFormat.")
        if actual_format != str(requested_format):
            raise RuntimeError(f"capture refused: {name} profile format does not match requested {requested_format!r}")
    return "pending_measurement" if pending else "validated"


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping): return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [_plain(v) for v in value]
    return value


def _canonical_profile_payload(profile: Any) -> dict[str, Any]:
    """Return the profile fields used for deterministic provenance hashing."""
    if is_dataclass(profile):
        return {field.name: _plain(getattr(profile, field.name)) for field in fields(profile)}
    if isinstance(profile, Mapping):
        return {str(key): _plain(value) for key, value in profile.items()}
    raise TypeError("profile must be a mapping or dataclass")


def _imu_profile_provenance(requested: Mapping[str, Any], sensor: str) -> dict[str, Any]:
    """Record requested IMU provenance without claiming SDK rates were measured."""
    rate = requested.get(f"{sensor}_rate", requested.get("nominal_rate"))
    scale = requested.get(f"{sensor}_full_scale_range", "pending_measurement")
    return {
        "profile": "sdk_default",
        "sample_rate": "pending_measurement",
        "requested_sample_rate": rate,
        "full_scale_range": scale,
    }


def _write_failure_manifest(
    output: Path,
    profile: Any,
    samples_path: Path,
    serial: Any,
    info: Any,
    active_streams: list[str],
    actual_profiles: Mapping[str, Any],
    per_stream_counts: Mapping[str, int],
    started_ns: int | None,
    error: BaseException,
    sdk_version: str = "unknown",
) -> None:
    """Best-effort, auditable record for a partial or failed capture."""
    try:
        output.mkdir(parents=True, exist_ok=True)
        profile_payload = json.dumps(_canonical_profile_payload(profile), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        manifest = {
            "schema_version": "p0/orbbec-capture/v1",
            "status": "failed_incomplete",
            "serial": serial,
            "model": _call_first(info, "get_name", "name") if info is not None else None,
            "firmware": _call_first(info, "get_firmware_version", "firmware_version") if info is not None else None,
            "sdk_version": sdk_version,
            "requested_streams": sorted(_section(profile, "streams")),
            "active_streams": active_streams,
            "actual_stream_profiles": dict(actual_profiles),
            "profile_sha256": hashlib.sha256(profile_payload).hexdigest(),
            "started_host_timestamp_ns": started_ns,
            "stopped_host_timestamp_ns": time.time_ns(),
            "timestamp_file": samples_path.name,
            "timestamp_samples_written": sum(per_stream_counts.values()),
            "per_stream_counts": dict(per_stream_counts),
            "error": {"type": type(error).__name__, "message": _failure_message(error)},
            "interpretation": "capture failed or was incomplete; no calibration, synchronization, or performance result is implied",
        }
        (output / "capture_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception:
        # Preserve the original capture error; manifest writing is best effort.
        pass


def _looks_like_device_access_error(error: BaseException) -> bool:
    message = str(error).lower()
    return any(token in message for token in ("openusbdevice", "permission denied", "access denied", "usbpermission")) or (type(error).__name__ == "OBError" and "usb" in message)


def _failure_message(error: BaseException) -> str:
    if _looks_like_device_access_error(error):
        return "permission denied while opening Orbbec device"
    return str(error)


def _call_first(obj: Any, *names: str) -> Any:
    for name in names:
        value = getattr(obj, name, None)
        if value is not None:
            return value() if callable(value) else value
    return None
