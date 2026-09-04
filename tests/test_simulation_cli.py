import json
from pathlib import Path

from sparseworld_p0.cli import main


def test_sim_smoke_cli_writes_auditable_json(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "sim.json"
    monkeypatch.setattr("sys.argv", ["sparseworld-p0", "sim-smoke", "--output", str(output)])
    assert main() == 0
    payload = json.loads(output.read_text())
    assert payload["evidence_class"] == "simulation_evidence"
    assert payload["status"] == "completed"
    assert output.with_suffix(".json.sha256").is_file()
