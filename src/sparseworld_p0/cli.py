"""Console entry point for P0 evidence commands."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .discovery import discover_environment


def main() -> int:
    parser = argparse.ArgumentParser(prog="sparseworld-p0")
    subparsers = parser.add_subparsers(dest="command", required=True)
    discover = subparsers.add_parser("discover", help="collect read-only environment evidence")
    discover.add_argument("--output", required=True, type=Path)
    discover.add_argument("--collected-at-utc")
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
    return 2
