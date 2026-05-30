#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"

echo "======================================"
echo " StableAgent Cloud Smoke Test"
echo "======================================"
echo "Base URL: $BASE_URL"

function check_url() {
  local name="$1"
  local url="$2"

  echo "[CHECK] $name -> $url"
  status=$(curl -s -o /tmp/stableagent_smoke.out -w "%{http_code}" "$url" || true)

  if [ "$status" -ge 200 ] && [ "$status" -lt 500 ]; then
    echo "  OK status=$status"
  else
    echo "  FAIL status=$status"
    cat /tmp/stableagent_smoke.out || true
    exit 1
  fi
}

check_url "Root" "$BASE_URL/"
check_url "Docs" "$BASE_URL/docs"
check_url "Connect" "$BASE_URL/connect"

echo "[CHECK] MCP tools/list"
mcp_status=$(curl -s -o /tmp/stableagent_mcp.out -w "%{http_code}" \
  -X POST "$BASE_URL/mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' || true)

if [ "$mcp_status" -ge 200 ] && [ "$mcp_status" -lt 500 ]; then
  echo "  OK status=$mcp_status"
  cat /tmp/stableagent_mcp.out
else
  echo "  FAIL status=$mcp_status"
  cat /tmp/stableagent_mcp.out || true
  exit 1
fi

echo ""
echo "Smoke test completed."
