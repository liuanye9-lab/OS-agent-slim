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

export PYTHONPATH="$ROOT_DIR:${PYTHONPATH:-}"

python tools/integration_test.py --base-url "$BASE_URL"
python tools/check_closed_loop.py --base-url "$BASE_URL"

echo ""
echo "Integration test completed."
