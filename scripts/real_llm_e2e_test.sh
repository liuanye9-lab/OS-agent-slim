#!/usr/bin/env bash
# Real LLM E2E Test — V10
# 不 echo key，不打印 key，不泄露 key
set -euo pipefail

# 加载 .env（如果有）
if [ -f ".env" ]; then
  set -a
  source .env
  set +a
fi

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"

echo "=== Real LLM E2E Test ==="
echo "Base URL: $BASE_URL"
echo "Key configured: $([ -n "$OPENAI_API_KEY" ] && echo 'yes (masked)' || echo 'no')"
echo "Real LLM enabled: $STABLE_AGENT_ENABLE_REAL_LLM"
echo ""

python tools/real_llm_e2e_test.py --base-url "$BASE_URL"
