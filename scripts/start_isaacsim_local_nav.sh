#!/usr/bin/env bash
# Launch Isaac Sim 6 with ABI-compatible bundled Python 3.12 ROS bindings.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ISAAC_ROOT="/home/ubuntu/linalw/App/isaacsim/_build/linux-x86_64/release"
ISAAC_ROS="${ISAAC_ROOT}/exts/isaacsim.ros2.core/humble"
OUTPUT="${1:-${ROOT_DIR}/artifacts/evidence/isaacsim_local_nav_smoke.json}"

if [[ ! -x "${ISAAC_ROOT}/python.sh" ]]; then
  echo "Isaac Sim launcher not found: ${ISAAC_ROOT}/python.sh" >&2
  exit 2
fi

# Do not source /opt/ros/humble/setup.bash here: it prepends Python 3.10
# modules, which are incompatible with Isaac Sim 6's Python 3.12 runtime.
export ROS_DISTRO=humble
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export AMENT_PREFIX_PATH=/opt/ros/humble
export LD_LIBRARY_PATH="${ISAAC_ROS}/lib:/opt/ros/humble/lib:/opt/ros/humble/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
unset PYTHONPATH
unset CONDA_PREFIX
unset CONDA_DEFAULT_ENV

exec "${ISAAC_ROOT}/python.sh" "${ROOT_DIR}/scripts/isaacsim_local_nav_smoke.py" --duration-s 20 --output "${OUTPUT}"
