import builtins
import json
import sys
import types
from pathlib import Path

import pytest

from sparseworld_p0.orbbec_capture import (
    _SENSOR_NAMES,
    _canonical_profile_payload,
    _enable_requested_streams,
    _frame_for,
    _timestamp_ns,
    capture_orbbec,
)
from sparseworld_p0.models import CaptureProfile


def test_capture_profile_hash_uses_explicit_dataclass_fields_not_repr():
    profile = CaptureProfile(
        schema_version="p0/v1",
        device={"serial": "SERIAL"},
        frames={"tree": ["map"]},
        streams={"rgb": {"resolution": "pending_measurement", "nominal_rate": "pending_measurement"}},
        map={"origin": "local"},
        quality_gates={},
        time_gates={},
        diagnostics={},
        topology={},
        scope={},
    )
    assert _canonical_profile_payload(profile) == {
        "schema_version": "p0/v1",
        "device": {"serial": "SERIAL"},
        "frames": {"tree": ["map"]},
        "streams": {"rgb": {"resolution": "pending_measurement", "nominal_rate": "pending_measurement"}},
        "map": {"origin": "local"},
        "quality_gates": {},
        "time_gates": {},
        "diagnostics": {},
        "topology": {},
        "scope": {},
    }


def test_capture_fails_closed_when_pyorbbecsdk_is_unavailable(tmp_path: Path, monkeypatch):
    real_import = builtins.__import__

    def no_sdk(name, *args, **kwargs):
        if name == "pyorbbecsdk":
            raise ModuleNotFoundError("No module named 'pyorbbecsdk'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_sdk)
    with pytest.raises(RuntimeError, match="pyorbbecsdk"):
        capture_orbbec({"device": {"serial": "SERIAL"}, "streams": {}}, tmp_path, 1)


def test_gemini_sensor_names_and_canonical_timestamp_conversion():
    assert _SENSOR_NAMES["left"] == "LEFT_IR_SENSOR"
    assert _SENSOR_NAMES["right"] == "RIGHT_IR_SENSOR"

    class Frame:
        def get_timestamp_us(self):
            return 1234

    assert _timestamp_ns(Frame()) == 1_234_000


def test_nonfinite_sdk_timestamp_is_rejected_and_left_ir_prefers_left_frame():
    class BadFrame:
        def get_timestamp_us(self): return float("nan")

    class Frames:
        def get_ir_frame(self): return "generic"
        def get_left_ir_frame(self): return "left"

    assert _timestamp_ns(BadFrame()) is None
    assert _frame_for(Frames(), "left") == "left"


def test_sdk_native_load_failure_is_actionable(tmp_path: Path, monkeypatch):
    real_import = builtins.__import__

    def no_native(name, *args, **kwargs):
        if name == "pyorbbecsdk":
            raise OSError("libobsensor.so: cannot open shared object file")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_native)
    with pytest.raises(RuntimeError, match="pyorbbecsdk"):
        capture_orbbec({"device": {"serial": "SERIAL"}, "streams": {}}, tmp_path, 1)


def test_sdk_device_open_permission_error_is_actionable(tmp_path: Path, monkeypatch):
    class OBError(Exception): pass

    class Context:
        def query_devices(self):
            class Devices:
                def get_count(self): return 1
                def get_device_by_index(self, index):
                    raise OBError("usbEnumerator openUsbDevice failed!")
            return Devices()

    monkeypatch.setitem(sys.modules, "pyorbbecsdk", types.SimpleNamespace(Context=Context, __version__="2.1.2"))
    with pytest.raises(RuntimeError, match="video-group access"):
        capture_orbbec({"device": {"serial": "SERIAL"}, "streams": {"rgb": {"resolution": "640x480", "nominal_rate": 30}}}, tmp_path, 1)
    manifest = json.loads((tmp_path / "capture_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "failed_incomplete"
    assert manifest["sdk_version"] == "2.1.2"
    assert manifest["error"]["message"] == "permission denied while opening Orbbec device"


def test_imu_setup_uses_accel_and_gyro_config_methods_and_video_streams_are_profile_checked():
    calls = []

    class Config:
        def enable_accel_stream(self):
            calls.append("accel")

        def enable_gyro_stream(self):
            calls.append("gyro")

        def enable_stream(self, profile):
            calls.append(("video", profile))

    class SensorType:
        COLOR_SENSOR = "color"
        DEPTH_SENSOR = "depth"
        LEFT_IR_SENSOR = "left_ir"
        RIGHT_IR_SENSOR = "right_ir"
        ACCEL_SENSOR = "accel_sensor"
        GYRO_SENSOR = "gyro_sensor"

    class Profile:
        def get_width(self): return 640
        def get_height(self): return 480
        def get_fps(self): return 30
        def get_format(self): return "RGB"

    class Profiles:
        def get_default_video_stream_profile(self): return Profile()

    class Pipeline:
        def get_stream_profile_list(self, sensor):
            return Profiles()

    sdk = types.SimpleNamespace(OBSensorType=SensorType)
    active, actual = _enable_requested_streams(
        sdk,
        Pipeline(),
        Config(),
        {
            "rgb": {"resolution": "640x480", "nominal_rate": 30},
            "depth": {"resolution": "pending_measurement", "nominal_rate": "pending_measurement"},
            "left": {"resolution": "pending_measurement", "nominal_rate": "pending_measurement"},
            "right": {"resolution": "pending_measurement", "nominal_rate": "pending_measurement"},
            "imu": {"resolution": "pending_measurement", "nominal_rate": "pending_measurement"},
        },
    )
    assert active == ["rgb", "depth", "left", "right", "imu"]
    assert "accel" in calls and "gyro" in calls
    assert actual["rgb"]["width"] == 640
    assert actual["rgb"]["height"] == 480


def test_imu_provenance_records_sdk_default_rate_and_full_scale_when_available():
    class SensorType:
        ACCEL_SENSOR = "accel"
        GYRO_SENSOR = "gyro"

    class Enum:
        def __init__(self, name): self.name = name
        def __str__(self): return self.name

    class Profile:
        def __init__(self, sensor): self.sensor = sensor
        def as_accel_stream_profile(self): return self
        def as_gyro_stream_profile(self): return self
        def get_sample_rate(self): return Enum("SAMPLE_RATE_200_HZ")
        def get_full_scale_range(self): return Enum("ACCEL_FS_4g" if self.sensor == "accel" else "FS_1000dps")

    class Profiles:
        def __init__(self, sensor): self.sensor = sensor
        def get_stream_profile_by_index(self, index): return Profile(self.sensor)
        def get_count(self): return 1

    class Pipeline:
        def get_stream_profile_list(self, sensor): return Profiles(sensor)

    class Config:
        def enable_accel_stream(self): pass
        def enable_gyro_stream(self): pass

    active, actual = _enable_requested_streams(
        types.SimpleNamespace(OBSensorType=SensorType), Pipeline(), Config(),
        {"imu": {"resolution": "pending_measurement", "nominal_rate": "pending_measurement"}},
    )
    assert active == ["imu"]
    assert actual["imu"]["accel"]["sample_rate"] == "SAMPLE_RATE_200_HZ"
    assert actual["imu"]["accel"]["full_scale_range"] == "ACCEL_FS_4g"
    assert actual["imu"]["gyro"]["full_scale_range"] == "FS_1000dps"
    assert actual["imu"]["profile_validation"] == "validated"


def test_imu_streams_use_explicit_profile_when_frozen_in_request():
    calls = []

    class SensorType:
        ACCEL_SENSOR = "accel"
        GYRO_SENSOR = "gyro"

    class Enum:
        def __init__(self, name): self.name = name
        def __str__(self): return self.name

    class Config:
        def enable_accel_stream(self, full_scale, sample_rate): calls.append(("accel", full_scale.name, sample_rate.name))
        def enable_gyro_stream(self, full_scale, sample_rate): calls.append(("gyro", full_scale.name, sample_rate.name))

    class SDK:
        OBSensorType = SensorType
        OBAccelFullScaleRange = type("A", (), {"ACCEL_FS_4g": Enum("ACCEL_FS_4g")})
        OBGyroFullScaleRange = type("G", (), {"FS_1000dps": Enum("FS_1000dps")})
        OBGyroSampleRate = type("R", (), {"SAMPLE_RATE_200_HZ": Enum("SAMPLE_RATE_200_HZ")})

    class Pipeline:
        def get_stream_profile_list(self, sensor):
            class Profiles:
                def get_stream_profile_by_index(self, index): raise RuntimeError("not used")
            return Profiles()

    active, _ = _enable_requested_streams(SDK, Pipeline(), Config(), {
        "imu": {
            "resolution": "native", "nominal_rate": 200,
            "accel_sample_rate": "SAMPLE_RATE_200_HZ", "accel_full_scale_range": "ACCEL_FS_4g",
            "gyro_sample_rate": "SAMPLE_RATE_200_HZ", "gyro_full_scale_range": "FS_1000dps",
        }
    })
    assert active == ["imu"]
    assert calls == [("accel", "ACCEL_FS_4g", "SAMPLE_RATE_200_HZ"), ("gyro", "FS_1000dps", "SAMPLE_RATE_200_HZ")]


def test_concrete_profile_mismatch_fails_closed():
    class SensorType:
        COLOR_SENSOR = "color"

    class Profile:
        def get_width(self): return 640
        def get_height(self): return 480
        def get_fps(self): return 30
        def get_format(self): return "RGB"

    class Profiles:
        def get_default_video_stream_profile(self): return Profile()

    class Pipeline:
        def get_stream_profile_list(self, sensor): return Profiles()

    class Config:
        def enable_stream(self, profile): pass

    with pytest.raises(RuntimeError, match="resolution"):
        _enable_requested_streams(
            types.SimpleNamespace(OBSensorType=SensorType),
            Pipeline(), Config(),
            {"rgb": {"resolution": "320x240", "nominal_rate": 30}},
        )


def test_concrete_profile_format_mismatch_fails_closed():
    class SensorType:
        COLOR_SENSOR = "color"

    class Profile:
        def get_width(self): return 640
        def get_height(self): return 480
        def get_fps(self): return 30
        def get_format(self): return "MJPG"

    class Profiles:
        def get_default_video_stream_profile(self): return Profile()

    class Pipeline:
        def get_stream_profile_list(self, sensor): return Profiles()

    class Config:
        def enable_stream(self, profile): pass

    with pytest.raises(RuntimeError, match="format"):
        _enable_requested_streams(
            types.SimpleNamespace(OBSensorType=SensorType),
            Pipeline(), Config(),
            {"rgb": {"resolution": "640x480", "nominal_rate": 30, "format": "Y16"}},
        )


def test_capture_manifest_has_per_stream_counts_and_canonical_sample_fields(tmp_path: Path, monkeypatch):
    # The fake SDK is intentionally small but follows the official v2 API names.
    class Info:
        def get_serial_number(self): return "SERIAL"
        def get_name(self): return "Gemini 335"
        def get_firmware_version(self): return "1.8.10"

    class Frame:
        def __init__(self, index, timestamp_us): self.index, self.timestamp_us = index, timestamp_us
        def get_timestamp_us(self): return self.timestamp_us
        def get_index(self): return self.index

    class Frames:
        def __init__(self): self.index = 0
        def _frame(self):
            self.index += 1
            return Frame(self.index, self.index * 1000)
        def get_color_frame(self): return self._frame()
        def get_depth_frame(self): return self._frame()
        def get_left_ir_frame(self): return self._frame()
        def get_right_ir_frame(self): return self._frame()
        def get_accel_frame(self): return self._frame()
        def get_gyro_frame(self): return self._frame()

    class Device:
        def get_device_info(self): return Info()

    class Devices:
        def get_count(self): return 1
        def get_device_by_index(self, index): return Device()

    class Context:
        def query_devices(self): return Devices()

    class Profile:
        def get_width(self): return 640
        def get_height(self): return 480
        def get_fps(self): return 30
        def get_format(self): return "RGB"

    class Profiles:
        def get_default_video_stream_profile(self): return Profile()

    class Config:
        def enable_stream(self, profile): pass
        def enable_accel_stream(self): pass
        def enable_gyro_stream(self): pass

    class Pipeline:
        def __init__(self, device): self.frames = Frames()
        def get_stream_profile_list(self, sensor): return Profiles()
        def start(self, config): pass
        def wait_for_frames(self, timeout): return self.frames
        def stop(self): pass

    fake = types.SimpleNamespace(
        __version__="2.9.3", Context=Context, Config=Config, Pipeline=Pipeline,
        OBSensorType=types.SimpleNamespace(
            COLOR_SENSOR="color", DEPTH_SENSOR="depth", LEFT_IR_SENSOR="left", RIGHT_IR_SENSOR="right",
            ACCEL_SENSOR="accel", GYRO_SENSOR="gyro",
        ),
    )
    monkeypatch.setitem(sys.modules, "pyorbbecsdk", fake)
    monkeypatch.setattr("sparseworld_p0.orbbec_capture.time.monotonic", lambda: 0.0)
    monkeypatch.setattr("sparseworld_p0.orbbec_capture.time.time_ns", lambda: 9_000_000_000)
    # One loop iteration is enough; the implementation must still stop cleanly.
    ticks = iter([0.0, 0.0, 2.0])
    monkeypatch.setattr("sparseworld_p0.orbbec_capture.time.monotonic", lambda: next(ticks))
    profile = {
        "device": {"serial": "SERIAL"},
        "streams": {
            "rgb": {"resolution": "640x480", "nominal_rate": 30},
            "depth": {"resolution": "pending_measurement", "nominal_rate": "pending_measurement"},
            "left": {"resolution": "pending_measurement", "nominal_rate": "pending_measurement"},
            "right": {"resolution": "pending_measurement", "nominal_rate": "pending_measurement"},
            "imu": {"resolution": "pending_measurement", "nominal_rate": "pending_measurement"},
        },
        "diagnostics": {"window_seconds": 10, "storage": "bounded_local_dense"},
    }
    manifest = capture_orbbec(profile, tmp_path, 1)
    rows = [json.loads(line) for line in (tmp_path / "timestamps.jsonl").read_text().splitlines()]
    assert rows and {"device_time_ns", "host_receive_time_ns", "sdk_frame_number"} <= rows[0].keys()
    assert all("device_timestamp" not in row and "host_timestamp_ns" not in row for row in rows)
    assert manifest["per_stream_counts"]["imu"] == 2
    assert manifest["imu_sensor_counts"] == {"accel": 1, "gyro": 1}
    assert manifest["actual_stream_profiles"]["rgb"]["width"] == 640
    assert manifest["actual_stream_profiles"]["rgb"]["profile_validation"] == "validated"
    assert manifest["actual_stream_profiles"]["depth"]["profile_validation"] == "pending_measurement"
    assert manifest["actual_stream_profiles"]["imu"]["accel"]["sample_rate"] == "pending_measurement"
    assert manifest["actual_stream_profiles"]["imu"]["gyro"]["profile"] == "sdk_default"


def test_capture_accumulates_async_framesets_instead_of_failing_on_missing_stream(tmp_path: Path, monkeypatch):
    """SDK may deliver video and IMU frames in separate FrameSets."""
    class Info:
        def get_serial_number(self): return "SERIAL"
        def get_name(self): return "Gemini 335"
        def get_firmware_version(self): return "1.8.10"

    class Frame:
        def __init__(self, index): self.index = index
        def get_timestamp_us(self): return self.index * 1000
        def get_index(self): return self.index

    class Frames:
        def __init__(self, index, present):
            self.index, self.present = index, present
        def _get(self, name):
            return Frame(self.index) if name in self.present else None
        def get_color_frame(self): return self._get("rgb")
        def get_depth_frame(self): return self._get("depth")
        def get_left_ir_frame(self): return self._get("left")
        def get_right_ir_frame(self): return self._get("right")
        def get_accel_frame(self): return self._get("accel")
        def get_gyro_frame(self): return self._get("gyro")

    class InfoDevice:
        def get_device_info(self): return Info()

    class Devices:
        def get_count(self): return 1
        def get_device_by_index(self, index): return InfoDevice()

    class Context:
        def query_devices(self): return Devices()

    class Profile:
        def get_width(self): return 640
        def get_height(self): return 480
        def get_fps(self): return 30
        def get_format(self): return "RGB"

    class Profiles:
        def get_default_video_stream_profile(self): return Profile()

    class Config:
        def enable_stream(self, profile): pass
        def enable_accel_stream(self): pass
        def enable_gyro_stream(self): pass

    class Pipeline:
        def __init__(self, device): self.calls = 0
        def get_stream_profile_list(self, sensor): return Profiles()
        def start(self, config): pass
        def wait_for_frames(self, timeout):
            self.calls += 1
            # First set contains video only; second set contains depth/IR and IMU.
            return Frames(self.calls, {"rgb"} if self.calls == 1 else {"depth", "left", "right", "accel", "gyro"})
        def stop(self): pass

    fake = types.SimpleNamespace(
        __version__="2.9.3", Context=Context, Config=Config, Pipeline=Pipeline,
        OBSensorType=types.SimpleNamespace(
            COLOR_SENSOR="color", DEPTH_SENSOR="depth", LEFT_IR_SENSOR="left", RIGHT_IR_SENSOR="right",
        ),
    )
    monkeypatch.setitem(sys.modules, "pyorbbecsdk", fake)
    ticks = iter([0.0, 0.0, 0.0, 2.0])
    monkeypatch.setattr("sparseworld_p0.orbbec_capture.time.monotonic", lambda: next(ticks))
    monkeypatch.setattr("sparseworld_p0.orbbec_capture.time.time_ns", lambda: 9_000_000_000)
    profile = {
        "device": {"serial": "SERIAL"},
        "streams": {
            "rgb": {"resolution": "640x480", "nominal_rate": 30},
            "depth": {"resolution": "pending_measurement", "nominal_rate": "pending_measurement"},
            "left": {"resolution": "pending_measurement", "nominal_rate": "pending_measurement"},
            "right": {"resolution": "pending_measurement", "nominal_rate": "pending_measurement"},
            "imu": {"resolution": "pending_measurement", "nominal_rate": "pending_measurement"},
        },
        "diagnostics": {"window_seconds": 10, "storage": "bounded_local_dense"},
    }
    manifest = capture_orbbec(profile, tmp_path, 1)
    assert manifest["status"] == "captured_unassessed"
    assert all(manifest["per_stream_counts"][name] > 0 for name in ("rgb", "depth", "left", "right", "imu"))
    assert manifest["imu_sensor_counts"] == {"accel": 1, "gyro": 1}


def test_normalise_imu_frame_records_value_temperature_and_sensor_type():
    class Value:
        x, y, z = 1.0, -2.0, 9.8

    class Frame:
        def get_timestamp_us(self): return 1234
        def get_index(self): return 7
        def get_value(self): return Value()
        def get_temperature(self): return 26.5

    from sparseworld_p0.orbbec_capture import _normalise_frame
    row = _normalise_frame("imu", "accel", Frame(), 9_000)
    assert row["sensor"] == "accel"
    assert row["imu_value"] == {"x": 1.0, "y": -2.0, "z": 9.8}
    assert row["temperature_c"] == 26.5


def test_capture_failure_writes_failed_incomplete_manifest(tmp_path: Path, monkeypatch):
    class Info:
        def get_serial_number(self): return "SERIAL"
        def get_name(self): return "Gemini 335"
        def get_firmware_version(self): return "1.8.10"

    class Device:
        def get_device_info(self): return Info()

    class Devices:
        def get_count(self): return 1
        def get_device_by_index(self, index): return Device()

    class Context:
        def query_devices(self): return Devices()

    class Config:
        def enable_stream(self, profile): pass

    class Pipeline:
        def __init__(self, device): pass
        def get_stream_profile_list(self, sensor):
            class Profiles:
                def get_default_video_stream_profile(self):
                    class Profile:
                        def get_width(self): return 640
                        def get_height(self): return 480
                        def get_fps(self): return 30
                        def get_format(self): return "RGB"
                    return Profile()
            return Profiles()
        def start(self, config): pass
        def wait_for_frames(self, timeout):
            raise RuntimeError("device disconnected")
        def stop(self): pass

    fake = types.SimpleNamespace(
        __version__="2.9.3", Context=Context, Config=Config, Pipeline=Pipeline,
        OBSensorType=types.SimpleNamespace(COLOR_SENSOR="color"),
    )
    monkeypatch.setitem(sys.modules, "pyorbbecsdk", fake)
    monkeypatch.setattr("sparseworld_p0.orbbec_capture.time.time_ns", lambda: 9_000_000_000)
    monkeypatch.setattr("sparseworld_p0.orbbec_capture.time.monotonic", lambda: 0.0)
    profile = {"device": {"serial": "SERIAL"}, "streams": {"rgb": {"resolution": "640x480", "nominal_rate": 30}}}
    with pytest.raises(RuntimeError, match="device disconnected"):
        capture_orbbec(profile, tmp_path, 1)
    manifest = json.loads((tmp_path / "capture_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "failed_incomplete"
    assert manifest["actual_stream_profiles"]["rgb"]["width"] == 640
    assert manifest["error"]["type"] == "RuntimeError"
    assert "device disconnected" in manifest["error"]["message"]


def test_missing_device_timestamp_fails_closed():
    class Frame:
        def get_timestamp(self): return None
    with pytest.raises(RuntimeError, match="device timestamp"):
        from sparseworld_p0.orbbec_capture import _normalise_frame
        _normalise_frame("rgb", None, Frame(), 123)
