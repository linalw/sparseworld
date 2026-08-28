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
    args = parser.parse_args()
    if args.command == "discover":
        payload = json.dumps(discover_environment(), indent=2, sort_keys=True) + "\n"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        args.output.with_suffix(args.output.suffix + ".sha256").write_text(
            f"{digest}  {args.output.name}\n", encoding="utf-8"
        )
        return 0
    return 2
