import builtins
from pathlib import Path

import pytest

from sparseworld_p0.orbbec_capture import capture_orbbec


def test_capture_fails_closed_when_pyorbbecsdk_is_unavailable(tmp_path: Path, monkeypatch):
    real_import = builtins.__import__

    def no_sdk(name, *args, **kwargs):
        if name == "pyorbbecsdk":
            raise ModuleNotFoundError("No module named 'pyorbbecsdk'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_sdk)
    with pytest.raises(RuntimeError, match="pyorbbecsdk"):
        capture_orbbec({"device": {"serial": "SERIAL"}, "streams": {}}, tmp_path, 1)
