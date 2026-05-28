#!/bin/bash
# OS Agent 健康检查
ENDPOINT="${1:-http://127.0.0.1:8000}"
echo "检查 StableAgent OS 服务: $ENDPOINT"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$ENDPOINT/api/connect/health" 2>/dev/null)
if [ "$STATUS" = "200" ]; then
    echo "✅ 服务运行中"
    curl -s "$ENDPOINT/api/connect/health" | python3 -m json.tool
else
    echo "❌ 服务未运行 (HTTP $STATUS)"
    echo "启动命令: uvicorn web.server:app --host 127.0.0.1 --port 8000"
fi
