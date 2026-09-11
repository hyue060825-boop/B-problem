#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
CUDA_LIB="$ROOT/.venv/lib/python3.11/site-packages/nvidia"
export LD_LIBRARY_PATH="$CUDA_LIB/nvjitlink/lib:$CUDA_LIB/cusparse/lib:$CUDA_LIB/cublas/lib:$CUDA_LIB/cudnn/lib:$CUDA_LIB/cuda_runtime/lib:$CUDA_LIB/cuda_nvrtc/lib:${LD_LIBRARY_PATH:-}"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$ROOT"
exec "$ROOT/.venv/bin/python" "$@"
