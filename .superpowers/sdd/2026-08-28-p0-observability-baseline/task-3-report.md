# Task 3 report — Read-only environment discovery

Status: complete.

## Files

- `src/sparseworld_p0/discovery.py`: injectable command runner and sysfs-root discovery for OS/kernel, Python, GPU, USB Gemini, V4L2 links/labels, groups, ROS 2 and pyorbbecsdk. All probes are enumeration/read-only; unavailable states are explicit.
- `src/sparseworld_p0/cli.py`: `sparseworld-p0 discover --output PATH`, deterministic JSON and sidecar SHA-256.
- `tests/test_discovery.py`: injected missing-ROS2 and missing-SDK behavior tests.
- `artifacts/evidence/.gitkeep`, `artifacts/evidence/p0_environment_20260828T100734Z.json`, and `.json.sha256`.

## TDD evidence

RED (`conda run -n sparseworld pytest -q tests/test_discovery.py`): collection failed with `ModuleNotFoundError: No module named 'sparseworld_p0.discovery'`.

GREEN (`conda run -n sparseworld pytest -q tests/test_discovery.py`): `2 passed`.

Full suite (`conda run -n sparseworld pytest -q`): `9 passed`.

## Evidence

Snapshot: `artifacts/evidence/p0_environment_20260828T100734Z.json`  
SHA-256: `99f312b5ff33ec9f9a6712cb8f081f4661736059b0a064663b59c9709b4a92f0` (also recorded in sidecar).

## Commit

`4a98e4c feat: capture read-only P0 environment evidence` (original implementation); hardening follow-up `69e0fa0`.

## Self-review / concerns

- No camera stream, V4L2 open, ROS launch, motor control, or sysfs write is performed.
- `sysfs_root` is injectable for deterministic fixtures; `/dev/v4l/by-id` remains host read-only enumeration.
- pyorbbecsdk import failures are classified as `not_installed`; command failures otherwise map to `permission_denied` or `not_detected`.
- OS facts are read from `/etc/os-release`; generated evidence is host-specific and timestamped UTC.

## Fix round 1

Added provenance (`source`, criterion, result type, interpretation) to claims; hardened permission/OSError handling for OS, V4L2, USB and video sysfs; empty command output and runner exceptions are `not_detected`; added injected permission, empty/raising, provenance, and CLI hash tests. RED showed the expected missing structured fields/statuses; GREEN focused Task 3 tests: `6 passed`; full suite: `13 passed`; `git diff --check` clean. Regenerated evidence and verified with `(cd artifacts/evidence && sha256sum -c p0_environment_20260828T100734Z.json.sha256)`: `OK`. JSON is deterministic only when a fixed `now` provider is supplied; live runs use UTC capture time and the filename is an operator-supplied run ID.
