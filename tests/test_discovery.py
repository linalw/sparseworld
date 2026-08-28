from subprocess import CompletedProcess

from sparseworld_p0.discovery import discover_environment
import sparseworld_p0.discovery as discovery


def test_marks_missing_ros2_as_not_installed_and_stays_read_only(tmp_path) -> None:
    """This catches discovery incorrectly treating an absent executable as success."""
    def runner(command: list[str]) -> CompletedProcess[str]:
        if command == ["ros2", "--version"]:
            return CompletedProcess(command, 127, "", "ros2: command not found")
        return CompletedProcess(command, 0, "fixture-output\n", "")

    snapshot = discover_environment(runner, tmp_path)

    assert snapshot["collection_mode"] == "read_only"
    assert snapshot["software"]["ros2"]["status"] == "not_installed"


def test_marks_missing_orbbec_python_module_as_not_installed(tmp_path) -> None:
    """This catches missing SDK modules being reported as ambiguous detection failures."""
    def runner(command: list[str]) -> CompletedProcess[str]:
        if command[0] == "python" and "pyorbbecsdk" in command[-1]:
            return CompletedProcess(command, 1, "", "ModuleNotFoundError: No module named 'pyorbbecsdk'")
        return CompletedProcess(command, 0, "fixture-output\n", "")

    snapshot = discover_environment(runner, tmp_path)

    assert snapshot["software"]["pyorbbecsdk"]["status"] == "not_installed"


def test_permission_denied_sources_are_structured(monkeypatch, tmp_path) -> None:
    def denied_os():
        raise PermissionError("denied")
    def denied_v4l2():
        raise PermissionError("denied")
    monkeypatch.setattr(discovery, "_os_release", denied_os)
    monkeypatch.setattr(discovery, "_v4l2_links", denied_v4l2)
    snap = discover_environment(lambda c: CompletedProcess(c, 0, "ok", ""), tmp_path)
    assert snap["os"]["status"] == "permission_denied"
    assert snap["v4l2"]["by_id"]["status"] == "permission_denied"


def test_snapshot_facts_include_provenance(tmp_path) -> None:
    snap = discover_environment(lambda c: CompletedProcess(c, 0, "ok", ""), tmp_path)
    assert snap["collection_mode"] == "read_only"
    assert snap["os"]["criterion"] == "read_only_enumeration_succeeded"
    assert snap["os"]["result_type"] == "enumeration_only"


def test_cli_hash_matches_output(tmp_path, monkeypatch) -> None:
    import hashlib, json
    from sparseworld_p0 import cli
    monkeypatch.setattr(cli, "discover_environment", lambda now=None: {"collection_mode": "read_only"})
    out = tmp_path / "snapshot.json"
    monkeypatch.setattr("sys.argv", ["sparseworld-p0", "discover", "--output", str(out)])
    assert cli.main() == 0
    expected = hashlib.sha256(out.read_bytes()).hexdigest()
    assert out.with_suffix(".json.sha256").read_text() == f"{expected}  snapshot.json\n"

def test_cli_fixed_timestamp_is_byte_deterministic(tmp_path, monkeypatch) -> None:
    from sparseworld_p0 import cli
    monkeypatch.setattr(cli, "discover_environment", lambda now=None: {"collection_mode": "read_only", "collected_at_utc": now().isoformat().replace("+00:00", "Z")})
    outputs = []
    for name in ("a.json", "b.json"):
        out = tmp_path / name
        monkeypatch.setattr("sys.argv", ["sparseworld-p0", "discover", "--output", str(out), "--collected-at-utc", "2026-08-28T03:20:00Z"])
        assert cli.main() == 0
        outputs.append(out.read_bytes())
    assert outputs[0] == outputs[1]

def test_cli_evidence_directory_run_id_matches_payload_time(tmp_path) -> None:
    from sparseworld_p0 import cli
    import json
    import sys
    old = sys.argv
    try:
        sys.argv = ["sparseworld-p0", "discover", "--output", str(tmp_path), "--collected-at-utc", "2026-08-28T03:20:00Z"]
        assert cli.main() == 0
    finally:
        sys.argv = old
    output = tmp_path / "p0_environment_20260828T032000Z.json"
    assert json.loads(output.read_text())["collected_at_utc"] == "2026-08-28T03:20:00Z"

def test_empty_or_raising_probe_is_not_detected(tmp_path) -> None:
    def runner(command):
        if command == ["uname", "-r"]:
            raise RuntimeError("runner unavailable")
        return CompletedProcess(command, 0, "", "")
    snap = discover_environment(runner, tmp_path)
    assert snap["os"]["kernel"]["status"] == "not_detected"
    assert snap["python"]["status"] == "not_detected"
