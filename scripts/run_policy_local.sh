#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec "$ROOT/scripts/run_python.sh" "$ROOT/scripts/run_policy.py" "$@"
