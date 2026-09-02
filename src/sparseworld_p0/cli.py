"""Console entry point for P0 evidence commands."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .discovery import discover_environment
from .calibration import assess_calibration_evidence, calibrate_chessboard_intrinsics, render_calibration_report
from .profile import load_profile
from .quality import assess
from .reporting import render_report
from .rosbag_export import package_normalized_samples_mcap, summarize_rosbag_timestamps


def main() -> int:
    parser = argparse.ArgumentParser(prog="sparseworld-p0")
    subparsers = parser.add_subparsers(dest="command", required=True)
    discover = subparsers.add_parser("discover", help="collect read-only environment evidence")
    discover.add_argument("--output", required=True, type=Path)
    discover.add_argument("--collected-at-utc")
    assess_parser = subparsers.add_parser("assess", help="assess an existing capture directory")
    assess_parser.add_argument("--profile", required=True, type=Path)
    assess_parser.add_argument("--capture-dir", required=True, type=Path)
    assess_parser.add_argument("--output", required=True, type=Path)
    package_parser = subparsers.add_parser("package-mcap", help="package normalized SDK samples into a user-space MCAP diagnostic container")
    package_parser.add_argument("--capture-dir", required=True, type=Path)
    package_parser.add_argument("--output", required=True, type=Path)
    rosbag_quality_parser = subparsers.add_parser("assess-rosbag", help="summarize exported ROS bag timestamp diagnostics")
    rosbag_quality_parser.add_argument("--timestamps", required=True, type=Path)
    rosbag_quality_parser.add_argument("--output", required=True, type=Path)
    calibration_parser = subparsers.add_parser("assess-calibration", help="assess hash-bound calibration/time-sync evidence")
    calibration_parser.add_argument("--evidence", required=True, type=Path)
    calibration_parser.add_argument("--output", required=True, type=Path)
    chessboard_parser = subparsers.add_parser("calibrate-chessboard", help="measure RGB intrinsics from checkerboard images")
    chessboard_parser.add_argument("--image-dir", required=True, type=Path)
    chessboard_parser.add_argument("--inner-corners", required=True, nargs=2, type=int, metavar=("COLUMNS", "ROWS"))
    chessboard_parser.add_argument("--square-size-mm", required=True, type=float)
    chessboard_parser.add_argument("--output", required=True, type=Path)
    console_parser = subparsers.add_parser("capture-console", help="start the local attended Gemini capture console")
    console_parser.add_argument("--host", default="127.0.0.1")
    console_parser.add_argument("--port", default=8765, type=int)
    console_parser.add_argument("--output-dir", default=Path("artifacts/rosbags"), type=Path)
    console_parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.command == "discover":
        from datetime import datetime, timezone
        fixed = datetime.fromisoformat(args.collected_at_utc.replace("Z", "+00:00")) if args.collected_at_utc else None
        captured = fixed or datetime.now(timezone.utc).replace(microsecond=0)
        snapshot = discover_environment(now=lambda: captured)
        output = args.output
        if output.suffix != ".json":
            output = output / f"p0_environment_{captured.strftime('%Y%m%dT%H%M%SZ')}.json"
        payload = json.dumps(snapshot, indent=2, sort_keys=True) + "\n"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        output.with_suffix(output.suffix + ".sha256").write_text(
            f"{digest}  {output.name}\n", encoding="utf-8"
        )
        return 0
    if args.command == "assess":
        profile = load_profile(args.profile)
        samples: dict[str, list[dict[str, object]]] = {}
        source = Path(args.capture_dir) / "timestamps.jsonl"
        for line_number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict) or not isinstance(row.get("stream"), str):
                raise ValueError(f"assessment refused: invalid sample at line {line_number}")
            samples.setdefault(row["stream"], []).append(row)
        capture_metadata = None
        manifest_path = Path(args.capture_dir) / "capture_manifest.json"
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict):
                raise ValueError("assessment refused: capture manifest must be an object")
            capture_metadata = dict(manifest)
            capture_metadata["manifest_sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        render_report(assess(profile, samples, capture_metadata=capture_metadata), args.output)
        return 0
    if args.command == "package-mcap":
        result = package_normalized_samples_mcap(args.capture_dir / "timestamps.jsonl", args.output)
        payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
        metadata_path = args.output / "package_manifest.json"
        metadata_path.write_text(payload, encoding="utf-8")
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        metadata_path.with_suffix(metadata_path.suffix + ".sha256").write_text(
            f"{digest}  {metadata_path.name}\n", encoding="utf-8"
        )
        return 0
    if args.command == "assess-rosbag":
        result = summarize_rosbag_timestamps(args.timestamps)
        payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
        args.output.with_suffix(args.output.suffix + ".sha256").write_text(
            f"{hashlib.sha256(payload.encode('utf-8')).hexdigest()}  {args.output.name}\n", encoding="utf-8"
        )
        return 0
    if args.command == "assess-calibration":
        evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
        if not isinstance(evidence, dict):
            raise ValueError("calibration assessment refused: evidence must be an object")
        result = assess_calibration_evidence(evidence, args.evidence.parent)
        render_calibration_report(result, args.output)
        return 0
    if args.command == "calibrate-chessboard":
        result = calibrate_chessboard_intrinsics(
            args.image_dir, pattern_size=tuple(args.inner_corners), square_size_m=args.square_size_mm / 1000.0,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
        args.output.write_text(payload, encoding="utf-8")
        args.output.with_suffix(args.output.suffix + ".sha256").write_text(
            f"{hashlib.sha256(payload.encode('utf-8')).hexdigest()}  {args.output.name}\n", encoding="utf-8"
        )
        return 0
    if args.command == "capture-console":
        if args.host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("capture console refuses non-local host; use an authenticated reverse proxy if remote access is required")
        try:
            import uvicorn
        except ImportError as exc:
            raise RuntimeError("capture console requires optional dependencies; install sparseworld-p0[console]") from exc
        from .capture_console import CaptureSession
        from .capture_console_api import create_app
        uvicorn.run(create_app(CaptureSession(args.output_dir, dry_run=args.dry_run)), host=args.host, port=args.port)
        return 0
    return 2
