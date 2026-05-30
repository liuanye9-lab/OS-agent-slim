#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PORT="${PORT:-8000}"
HOST="${HOST:-127.0.0.1}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "======================================"
echo " StableAgent Cloud Local Deployment"
echo "======================================"
echo "Root: $ROOT_DIR"
echo "Host: $HOST"
echo "Port: $PORT"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "[ERROR] Python not found: $PYTHON_BIN"
  exit 1
fi

echo "[1/7] Python version"
"$PYTHON_BIN" --version

echo "[2/7] Creating virtual environment"
if [ ! -d ".venv" ]; then
  "$PYTHON_BIN" -m venv .venv
fi

echo "[3/7] Activating virtual environment"
# shellcheck disable=SC1091
source .venv/bin/activate

echo "[4/7] Installing dependencies"
python -m pip install --upgrade pip

if [ -f "requirements.txt" ]; then
  pip install -r requirements.txt
else
  pip install fastapi uvicorn pydantic pytest httpx websockets python-dotenv
fi

echo "[5/7] Preparing runtime directories"
mkdir -p data logs skills/candidates skills/rejected reports

echo "[6/7] Environment"
export STABLE_AGENT_MODE="${STABLE_AGENT_MODE:-local}"
export STABLE_AGENT_DB_PATH="${STABLE_AGENT_DB_PATH:-data/stable_agent.db}"
export PYTHONPATH="$ROOT_DIR:${PYTHONPATH:-}"

echo "STABLE_AGENT_MODE=$STABLE_AGENT_MODE"
echo "STABLE_AGENT_DB_PATH=$STABLE_AGENT_DB_PATH"

echo "[7/7] Starting server"
echo ""
echo "Open:"
echo "  API Docs:    http://$HOST:$PORT/docs"
echo "  MCP:         http://$HOST:$PORT/mcp"
echo "  Dashboard:   http://$HOST:$PORT"
echo "  Connect:     http://$HOST:$PORT/connect"
echo ""
echo "Press Ctrl+C to stop."
echo ""

exec uvicorn web.server:app --host "$HOST" --port "$PORT" --reload
