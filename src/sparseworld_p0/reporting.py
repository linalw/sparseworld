"""Deterministic JSON/Markdown assessment reports."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
from typing import Any

def render_report(assessment: dict[str, Any], output_dir: str | Path) -> dict[str, Path]:
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(assessment, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    json_path = out / "assessment.json"; md_path = out / "assessment.md"; hash_path = out / "assessment.json.sha256"
    json_path.write_text(payload, encoding="utf-8")
    lines=["# P0 Timing and Quality Assessment", "", f"Source SHA-256: `{assessment.get('source_sha256','')}`", "", "| Gate | Status | Value |", "|---|---|---|"]
    for name, gate in sorted(assessment.get("gates", {}).items()):
        lines.append(f"| {name} | {gate.get('status','not_measured')} | {gate.get('value')} |")
    lines += ["", "Timing:", ""]
    for name, metric in sorted(assessment.get("timing", {}).items()):
        lines.append(f"- {name}: status={metric.get('status')}, rate={metric.get('observed_rate_hz')}, missing={metric.get('missing_sequences')}, nonmonotonic={metric.get('nonmonotonic_timestamps')}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    digest=hashlib.sha256(payload.encode()).hexdigest(); hash_path.write_text(f"{digest}  {json_path.name}\n", encoding="utf-8")
    return {"json":json_path, "markdown":md_path, "sha256":hash_path}
