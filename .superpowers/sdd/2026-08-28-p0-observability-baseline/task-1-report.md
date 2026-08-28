# Task 1 Report — Project and Git Baseline

## Status

Implemented and committed the P0 Python package baseline on branch `p0-observability`.

## Implementation

- Added `pyproject.toml` with setuptools `src` layout, distribution `sparseworld-p0`, version `0.1.0`, Python `>=3.10`, runtime dependency `PyYAML>=6.0`, test extra `pytest>=8.0`, and console entry point `sparseworld-p0 = sparseworld_p0.cli:main`.
- Added `src/sparseworld_p0/__init__.py` with package version `0.1.0`.
- Added `tests/test_package_layout.py`, asserting installed distribution metadata exposes version `0.1.0`.
- Added `.gitignore` entries for captures, raw/rosbag/rendered diagnostics, virtual environments, test caches, Python bytecode, and egg-info. Profiles, reports, and checksums remain trackable.

The console entry point intentionally remains nonfunctional until Task 3 adds `sparseworld_p0.cli`, per the SDD ruling; Task 1 only verifies package metadata.

## TDD evidence

RED (initial environment lacked pytest):

```text
conda run -n sparseworld pytest tests/test_package_layout.py -q
/tmp/...: pytest: 未找到命令
```

After installing the required test extra/tool, the same test failed as expected because the distribution metadata did not exist:

```text
E   importlib.metadata.PackageNotFoundError: No package metadata was found for sparseworld-p0
1 failed in 0.02s
```

GREEN and full suite:

```text
conda run -n sparseworld python -m pip install -e '.[test]'
conda run -n sparseworld pytest tests/test_package_layout.py -q
1 passed in 0.00s

conda run -n sparseworld pytest -q
1 passed in 0.01s
```

Pre-commit verification also ran `git diff --cached --check` successfully.

## Commit

`37b3058 chore: initialize P0 observability project`

No GitHub remote was created or pushed.

## Self-review and concerns

- Scope is limited to the four files required by Task 1; existing proposal and records were preserved.
- The declared console script targets the future Task 3 CLI and will raise an import error if invoked before that task; this is intentional and documented above.
- No P1 performance, localization, navigation, safety, or hardware measurement claims were added.
