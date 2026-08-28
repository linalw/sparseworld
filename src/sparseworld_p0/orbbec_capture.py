"""Fail-closed, optional Orbbec SDK capture adapter for P0 evidence."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Mapping


_SENSOR_NAMES = {
    "rgb": "COLOR_SENSOR",
    "depth": "DEPTH_SENSOR",
    "left": "IR_LEFT_SENSOR",
    "right": "IR_RIGHT_SENSOR",
    "imu": "ACCEL_SENSOR",
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
    except (ImportError, ModuleNotFoundError) as error:
        raise RuntimeError(
            "capture refused: pyorbbecsdk is unavailable; install the checksum-recorded Orbbec SDK Python binding first"
        ) from error
    if not streams:
        raise RuntimeError("capture refused: profile must request at least one stream")

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
        active_streams = _enable_requested_streams(sdk, pipeline, config, streams)
        pipeline.start(config)
    except PermissionError as error:
        raise RuntimeError("capture refused: permission denied while opening Orbbec device; verify video-group access after a new login") from error
    except RuntimeError:
        raise
    except Exception as error:
        raise RuntimeError(f"capture refused: Orbbec SDK setup failed ({type(error).__name__}: {error})") from error

    output = Path(output_dir)
    try:
        output.mkdir(parents=True, exist_ok=True)
        samples_path = output / "timestamps.jsonl"
        diagnostics = _section(profile, "diagnostics")
        window_s = diagnostics.get("window_seconds", 30)
        max_samples = max(1, int(float(window_s) * max(1, len(active_streams)) * 120))
        frame_count = 0
        started_ns = time.time_ns()
        deadline = time.monotonic() + float(duration_s)
        with samples_path.open("w", encoding="utf-8") as handle:
            while time.monotonic() < deadline:
                frames = pipeline.wait_for_frames(1000)
                host_timestamp_ns = time.time_ns()
                if frames is None:
                    continue
                for name in active_streams:
                    frame = _frame_for(frames, name)
                    if frame is None:
                        raise RuntimeError(f"capture refused: requested {name} stream produced no frame")
                    if frame_count >= max_samples:
                        continue
                    row = {
                        "stream": name,
                        "host_timestamp_ns": host_timestamp_ns,
                        "device_timestamp": _call_first(frame, "get_timestamp", "timestamp"),
                        "sdk_frame_number": _call_first(frame, "get_frame_number", "frame_number"),
                    }
                    handle.write(json.dumps(row, sort_keys=True) + "\n")
                    frame_count += 1
        manifest = {
            "schema_version": "p0/orbbec-capture/v1",
            "status": "captured_unassessed",
            "serial": actual_serial,
            "model": _call_first(info, "get_name", "name"),
            "firmware": _call_first(info, "get_firmware_version", "firmware_version"),
            "sdk_version": getattr(sdk, "__version__", "unknown"),
            "requested_streams": sorted(streams),
            "active_streams": active_streams,
            "started_host_timestamp_ns": started_ns,
            "duration_s_requested": duration_s,
            "timestamp_file": samples_path.name,
            "timestamp_samples_written": frame_count,
            "diagnostics": {"storage": diagnostics.get("storage"), "window_seconds": window_s, "max_timestamp_samples": max_samples},
            "interpretation": "capture evidence only; calibration, synchronization, and performance remain unassessed until raw outputs are reviewed",
        }
        (output / "capture_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return manifest
    except PermissionError as error:
        raise RuntimeError("capture refused: permission denied while writing capture evidence") from error
    except RuntimeError:
        raise
    except Exception as error:
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


def _enable_requested_streams(sdk: Any, pipeline: Any, config: Any, streams: Mapping[str, Any]) -> list[str]:
    active: list[str] = []
    for name, requested in streams.items():
        if not isinstance(requested, Mapping):
            raise RuntimeError(f"capture refused: stream {name!r} configuration must be a mapping")
        if not requested.get("resolution") or not requested.get("nominal_rate"):
            raise RuntimeError(f"capture refused: stream {name!r} must declare resolution and nominal_rate")
        sensor_name = _SENSOR_NAMES.get(name)
        if sensor_name is None:
            raise RuntimeError(f"capture refused: unsupported requested stream {name!r}")
        sensor_type = getattr(sdk.OBSensorType, sensor_name, None)
        if sensor_type is None:
            raise RuntimeError(f"capture refused: SDK lacks {sensor_name} required for {name}")
        try:
            profiles = pipeline.get_stream_profile_list(sensor_type)
            profile = profiles.get_default_video_stream_profile()
            config.enable_stream(profile)
        except Exception as error:
            raise RuntimeError(f"capture refused: requested {name} stream is unavailable") from error
        active.append(name)
    return active


def _frame_for(frames: Any, name: str) -> Any:
    methods = {
        "rgb": ("get_color_frame",), "depth": ("get_depth_frame",),
        "left": ("get_ir_frame", "get_left_ir_frame"), "right": ("get_right_ir_frame",),
        "imu": ("get_accel_frame",),
    }[name]
    for method in methods:
        candidate = getattr(frames, method, None)
        if candidate is not None:
            value = candidate()
            if value is not None:
                return value
    return None


def _call_first(obj: Any, *names: str) -> Any:
    for name in names:
        value = getattr(obj, name, None)
        if value is not None:
            return value() if callable(value) else value
    return None
