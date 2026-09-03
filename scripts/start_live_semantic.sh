#!/usr/bin/env bash
set -euo pipefail

# One-command launcher for the attended Gemini 335 live semantic console.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONDA_ROOT="${SPARSEWORLD_CONDA_ROOT:-/home/ubuntu/linalw/App/minconda3}"
source "${CONDA_ROOT}/etc/profile.d/conda.sh"
conda activate sparseworld

if [[ "${ALL_PROXY:-}" == socks5://* ]] && ! python -c 'import socksio' 2>/dev/null; then
  echo "SOCKS 代理需要 Python 包 socksio；正在安装…" >&2
  python -m pip install socksio
fi

# ROS Humble's generated setup scripts read optional variables without
# defaults. Scope nounset disablement to setup loading, then restore it.
set +u
source /opt/ros/humble/setup.bash
if [[ -f /home/ubuntu/ros2_ws/install-systempy4/setup.bash ]]; then
  source /home/ubuntu/ros2_ws/install-systempy4/setup.bash
fi
set -u

export PYTHONPATH="${ROOT_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}"
export SPARSEWORLD_PYTHON="${SPARSEWORLD_PYTHON:-${CONDA_PREFIX}/bin/python}"
export SPARSEWORLD_SEMANTIC_BACKEND="${SPARSEWORLD_SEMANTIC_BACKEND:-sam2_florence_siglip}"
export SPARSEWORLD_MASK_MODEL_ID="${SPARSEWORLD_MASK_MODEL_ID:-facebook/sam-vit-base}"
export SPARSEWORLD_LABEL_MODEL_ID="${SPARSEWORLD_LABEL_MODEL_ID:-microsoft/Florence-2-base}"
export SPARSEWORLD_SEMANTIC_DEVICE="${SPARSEWORLD_SEMANTIC_DEVICE:-0}"

OUTPUT_DIR="${SPARSEWORLD_OUTPUT_DIR:-${ROOT_DIR}/artifacts/rosbags}"
HOST="${SPARSEWORLD_CONSOLE_HOST:-127.0.0.1}"
PORT="${SPARSEWORLD_CONSOLE_PORT:-8765}"
echo "Semantic backend: ${SPARSEWORLD_SEMANTIC_BACKEND}"
echo "Mask model: ${SPARSEWORLD_MASK_MODEL_ID}"
echo "Label model: ${SPARSEWORLD_LABEL_MODEL_ID}"
echo "Device: ${SPARSEWORLD_SEMANTIC_DEVICE} (0=GPU, -1=CPU)"
echo "Open http://${HOST}:${PORT}/"
exec sparseworld-p0 capture-console --host "${HOST}" --port "${PORT}" --output-dir "${OUTPUT_DIR}"
