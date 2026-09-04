#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT="${1:-${ROOT_DIR}/artifacts/evidence/simulation_smoke.json}"
exec python3 -m sparseworld_p0.cli sim-smoke --output "${OUTPUT}"
