#!/usr/bin/env bash
# start_slim.sh — 本地启动 Slim Cloud Center (开发/测试用)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

export STABLEAGENT_PROFILE=slim
export STABLEAGENT_PORT=${STABLEAGENT_PORT:-18789}
export STABLEAGENT_BIND_HOST=${STABLEAGENT_BIND_HOST:-127.0.0.1}

cd "$PROJECT_DIR"

echo "Starting StableAgent OS Slim Cloud Center..."
echo "  Profile: $STABLEAGENT_PROFILE"
echo "  Bind:    $STABLEAGENT_BIND_HOST:$STABLEAGENT_PORT"
echo "  URL:     http://${STABLEAGENT_BIND_HOST}:${STABLEAGENT_PORT}/slim"
echo ""

PYTHONPATH="$PROJECT_DIR" "$PROJECT_DIR/.venv/bin/python" -m stable_agent.cli serve \
    --host "$STABLEAGENT_BIND_HOST" \
    --port "$STABLEAGENT_PORT" \
    --profile slim
