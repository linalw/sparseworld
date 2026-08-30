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
    relation = assessment.get("device_host_clock_relation")
    if isinstance(relation, dict):
        lines += ["", "Device/host elapsed-clock relation:"]
        for name, metric in sorted(relation.items()):
            if isinstance(metric, dict):
                lines.append(f"- {name}: status={metric.get('status')}, relative_rate={metric.get('relative_rate')}, absolute_offset_ns={metric.get('absolute_offset_ns')}")
    capture = assessment.get("capture")
    if isinstance(capture, dict):
        lines += ["", "Capture manifest:", f"- status={capture.get('status')}, manifest_sha256={capture.get('manifest_sha256')}"]
        diagnostics = capture.get("frame_number_diagnostics")
        if isinstance(diagnostics, dict):
            for name, metric in sorted(diagnostics.items()):
                if isinstance(metric, dict):
                    lines.append(f"- {name}: missing_frame_numbers={metric.get('missing_frame_numbers')}, duplicate_frame_numbers={metric.get('duplicate_frame_numbers')}, out_of_order_frame_numbers={metric.get('out_of_order_frame_numbers')}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    digest=hashlib.sha256(payload.encode()).hexdigest(); hash_path.write_text(f"{digest}  {json_path.name}\n", encoding="utf-8")
    return {"json":json_path, "markdown":md_path, "sha256":hash_path}
