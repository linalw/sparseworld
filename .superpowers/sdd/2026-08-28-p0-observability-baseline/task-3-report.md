# Task 3 report — Read-only environment discovery

Status: complete.

## Files (current primary)

- `src/sparseworld_p0/discovery.py`: injectable command runner and sysfs-root discovery for OS/kernel, Python, GPU, USB Gemini, V4L2 links/labels, groups, ROS 2 and pyorbbecsdk. All probes are enumeration/read-only; unavailable states are explicit.
- `src/sparseworld_p0/cli.py`: `sparseworld-p0 discover --output PATH`, deterministic JSON and sidecar SHA-256.
- `tests/test_discovery.py`: injected missing-ROS2 and missing-SDK behavior tests.
- `artifacts/evidence/p0_environment_20260828T041820Z.json` and its sidecar.

## TDD evidence

RED (`conda run -n sparseworld pytest -q tests/test_discovery.py`): collection failed with `ModuleNotFoundError: No module named 'sparseworld_p0.discovery'`.

GREEN (`conda run -n sparseworld pytest -q tests/test_discovery.py`): `2 passed`.

Full suite (`conda run -n sparseworld pytest -q`): `9 passed`.

## Evidence (current)

Snapshot: `artifacts/evidence/p0_environment_20260828T041820Z.json` (`2026-08-28T04:18:20Z`)  
SHA-256: `dab02ab15c0fbbc2287495c02c0de762eec2939d9f1e0e6f2562a7293e120d9a`.

## Commit

Commit chain: `4a98e4c`, `75b39b0`, `1fa5112`, `60c6b1f`, `76ebc9b`, `9c07428`.

## Self-review / concerns

- No camera stream, V4L2 open, ROS launch, motor control, or sysfs write is performed.
- `sysfs_root` is injectable for deterministic fixtures; `/dev/v4l/by-id` remains host read-only enumeration.
- pyorbbecsdk import failures are classified as `not_installed`; command failures otherwise map to `permission_denied` or `not_detected`.
- OS facts are read from `/etc/os-release`; generated evidence is host-specific and timestamped UTC.

## Fix round 1

Added provenance (`source`, criterion, result type, interpretation) to claims; hardened permission/OSError handling for OS, V4L2, USB and video sysfs; empty command output and runner exceptions are `not_detected`; added injected permission, empty/raising, provenance, and CLI hash tests. RED showed the expected missing structured fields/statuses; GREEN focused Task 3 tests: `6 passed`; full suite: `13 passed`; `git diff --check` clean. Regenerated evidence and verified with `(cd artifacts/evidence && sha256sum -c p0_environment_20260828T100734Z.json.sha256)`: `OK`. JSON is deterministic only when a fixed `now` provider is supplied; live runs use UTC capture time and the filename is an operator-supplied run ID.

## Fix round 2

Superseded history: earlier 100734Z/99f and intermediate 041421Z files are retained uncommitted diagnostics, not current evidence.

Final closure: current primary evidence `artifacts/evidence/p0_environment_20260828T041820Z.json`, payload UTC `2026-08-28T04:18:20Z`, SHA-256 `dab02ab15c0fbbc2287495c02c0de762eec2939d9f1e0e6f2562a7293e120d9a`. `sha256sum -c` succeeded; `git diff --check` clean. Prior artifacts are superseded. Commits: `4a98e4c`, `75b39b0`, `1fa5112`, `60c6b1f`, `76ebc9b`.

Added provenance metadata for USB/V4L2/sysfs and `/etc/os-release`, structured unavailable statuses, safe exception handling, and CLI `--collected-at-utc` deterministic mode. RED: CLI fixed-time test initially failed on unsupported injected `now`; GREEN: focused `7 passed`, full `14 passed`. Evidence sidecar verification: `(cd artifacts/evidence && sha256sum -c p0_environment_20260828T100734Z.json.sha256)` succeeded. Current payload mapping is `p0_environment_20260828T100734Z.json` → sidecar hash (regenerated in this round); prior hash claims are superseded. Hardening commit: `75b39b0`; this correction is committed separately.
