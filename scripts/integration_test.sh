#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"

echo "======================================"
echo " StableAgent Cloud Integration Test"
echo "======================================"
echo "Base URL: $BASE_URL"

if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

PY_BIN="$ROOT_DIR/.venv/bin/python"
if [ ! -x "$PY_BIN" ]; then
  echo "ERROR: .venv/bin/python not found. Do not use system python for StableAgent integration tests."
  exit 1
fi

export PYTHONPATH="$ROOT_DIR:${PYTHONPATH:-}"

"$PY_BIN" tools/integration_test.py --base-url "$BASE_URL"
"$PY_BIN" tools/check_closed_loop.py --base-url "$BASE_URL"

echo ""
echo "Integration test completed."
