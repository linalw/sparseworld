"""Read-only host and camera-enumeration evidence collection."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from subprocess import CompletedProcess, run
from typing import Callable, Sequence


CommandRunner = Callable[[list[str]], CompletedProcess[str]]


def discover_environment(
    command_runner: CommandRunner | None = None,
    sysfs_root: str | Path = "/sys",
    now=None,
) -> dict[str, object]:
    """Return a snapshot collected exclusively by enumeration commands and reads.

    No command in this module opens a V4L2 device, launches ROS, or writes to
    sysfs.  ``command_runner`` makes command outcomes deterministic in tests.
    """
    runner = command_runner or _run_read_only
    commands: list[dict[str, object]] = []

    def probe(name: str, command: list[str]) -> dict[str, object]:
        try:
            result = runner(command)
        except Exception as error:
            result = CompletedProcess(command, 1, "", f"{type(error).__name__}: {error}")
        record = {
            "name": name,
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
        commands.append(record)
        return record

    os_release = _safe(_os_release)
    kernel = probe("kernel", ["uname", "-r"])
    python = probe("python", ["python", "--version"])
    gpu = probe(
        "gpu",
        ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
    )
    groups = probe("groups", ["id", "-nG"])
    ros2 = probe("ros2", ["ros2", "--version"])
    sdk = probe(
        "pyorbbecsdk",
        ["python", "-c", "import pyorbbecsdk; print(getattr(pyorbbecsdk, '__version__', 'installed'))"],
    )
    root = Path(sysfs_root)
    usb_devices = _usb_devices(root)
    video_labels = _video_labels(root)
    v4l2_links = _safe(_v4l2_links)

    return {
        "schema_version": "p0/environment/v1",
        "collection_mode": "read_only",
        "collected_at_utc": (now or (lambda: datetime.now(timezone.utc)))().isoformat().replace("+00:00", "Z"),
        "commands_attempted": commands,
        "os": {**os_release, "kernel": _fact(kernel)},
        "python": _fact(python),
        "gpu": _fact(gpu),
        "groups": _fact(groups),
        "usb": {"gemini": usb_devices},
        "v4l2": {"by_id": v4l2_links, "sysfs_labels": video_labels},
        "software": {"ros2": _software_fact(ros2), "pyorbbecsdk": _software_fact(sdk)},
    }


def _run_read_only(command: list[str]) -> CompletedProcess[str]:
    try:
        return run(command, text=True, capture_output=True, check=False)
    except FileNotFoundError as error:
        return CompletedProcess(command, 127, "", str(error))
    except PermissionError as error:
        return CompletedProcess(command, 126, "", str(error))


def _fact(record: dict[str, object]) -> dict[str, object]:
    status = _status(record)
    if status == "available" and not record["stdout"]:
        status = "not_detected"
    result: dict[str, object] = {"status": status, "source": {"command": record["command"]}, "criterion": "read_only_enumeration_succeeded" if status == "available" else "read_only_enumeration_unavailable", "result_type": "enumeration_only", "interpretation": "not_a_calibration_or_performance_result"}
    if status == "available" and record["stdout"]:
        result["value"] = record["stdout"]
    return result

def _safe(action):
    try:
        return action()
    except PermissionError:
        return _meta("permission_denied", {})
    except OSError:
        return _meta("not_detected", {})

def _meta(status, source, **values):
    return {"status": status, "source": source, "criterion": "read_only_enumeration_succeeded" if status == "available" else "read_only_enumeration_unavailable", "result_type": "enumeration_only", "interpretation": "not_a_calibration_or_performance_result", **values}


def _software_fact(record: dict[str, object]) -> dict[str, object]:
    status = _status(record)
    if status == "available" and not record["stdout"]:
        status = "not_detected"
    result: dict[str, object] = {"status": status, "source": {"command": record["command"]}, "criterion": "read_only_enumeration_succeeded" if status == "available" else "read_only_enumeration_unavailable", "result_type": "enumeration_only", "interpretation": "not_a_calibration_or_performance_result"}
    if status == "available":
        result["version"] = record["stdout"]
    return result


def _status(record: dict[str, object]) -> str:
    code = record["returncode"]
    stderr = str(record["stderr"]).lower()
    if code == 0:
        return "available"
    if code in (126,) or "permission denied" in stderr:
        return "permission_denied"
    if code == 127 or "not found" in stderr or "no such file" in stderr or "modulenotfounderror" in stderr:
        return "not_installed"
    return "not_detected"


def _os_release() -> dict[str, str]:
    path = Path("/etc/os-release")
    try:
      if not path.is_file(): return _meta("not_detected", {"path": str(path)})
      values = {
        key: value.strip().strip('"')
        for line in path.read_text(encoding="utf-8").splitlines()
        if "=" in line
        for key, value in [line.split("=", 1)]
      }
      return _meta("available", {"path": str(path)}, name=values.get("PRETTY_NAME", "unknown"))
    except PermissionError: return _meta("permission_denied", {"path": str(path)})
    except OSError: return _meta("not_detected", {"path": str(path)})


def _usb_devices(root: Path) -> list[dict[str, str]] | dict[str, str]:
    records: list[dict[str, str]] = []
    for vendor in root.glob("bus/usb/devices/*/idVendor"):
        rv = _read(vendor)
        if rv.get("value", "").lower() != "2bc5":
            continue
        device = vendor.parent
        records.append({
            "vendor_id": rv,
            "product_id": _read(device / "idProduct"),
            "serial": _read(device / "serial"),
            "product": _read(device / "product"),
            "path": str(device),
        })
    return _meta("available" if records else "not_detected", {"sysfs_path": str(root / "bus/usb/devices")}) | ({"devices": records} if records else {})


def _video_labels(root: Path) -> list[dict[str, str]] | dict[str, str]:
    labels: list[dict[str, str]] = []
    for name in sorted(root.glob("class/video4linux/video*/name")):
        labels.append({"device": name.parent.name, "label": _read(name)})
    return _meta("available" if labels else "not_detected", {"sysfs_path": str(root / "class/video4linux")}) | ({"labels": labels} if labels else {})


def _v4l2_links() -> list[dict[str, str]] | dict[str, str]:
    base = Path("/dev/v4l/by-id")
    if not base.is_dir():
        return _meta("not_detected", {"path": str(base)})
    links = [{"link": str(path), "target": str(path.resolve())} for path in sorted(base.iterdir())]
    return _meta("available" if links else "not_detected", {"path": str(base)}) | ({"links": links} if links else {})


def _read(path: Path) -> dict[str, str]:
    try:
        return {"status": "available", "value": path.read_text(encoding="utf-8").strip()}
    except PermissionError:
        return {"status": "permission_denied"}
    except OSError:
        return {"status": "not_detected"}
