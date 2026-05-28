#!/bin/bash
# OS Agent Codex 一键启动
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "=== StableAgent OS — Codex 一键接入 ==="
echo ""

# 1. 检查 Python
if ! command -v python3 &>/dev/null; then
    echo "❌ 需要 Python 3.11+"
    exit 1
fi
echo "✅ Python $(python3 --version)"

# 2. 检查依赖
VENV="/Users/Zhuanz/.workbuddy/binaries/python/envs/default/bin"
if [ -f "$VENV/python" ]; then
    PYTHON="$VENV/python"
    UVICORN="$VENV/uvicorn"
else
    PYTHON="python3"
    UVICORN="uvicorn"
fi
echo "✅ Python: $PYTHON"

# 3. 检查端口
if lsof -i :8000 &>/dev/null; then
    echo "✅ 服务已在 8000 端口运行"
else
    echo "🚀 启动服务..."
    cd "$PROJECT_DIR"
    $UVICORN web.server:app --host 127.0.0.1 --port 8000 &
    sleep 2
fi

# 4. 健康检查
if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/api/connect/health 2>/dev/null | grep -q 200; then
    echo "✅ 服务健康"
else
    echo "⚠️  健康检查失败，可能需要手动启动"
fi

echo ""
echo "=== 接入信息 ==="
echo "MCP 端点:     http://127.0.0.1:8000/mcp/v5/mcp"
echo "Dashboard:    http://127.0.0.1:8000/dashboard/v2"
echo "连接页:       http://127.0.0.1:8000/connect"
echo "快捷命令:     /os-agent 你的任务描述"
echo ""
echo "在 Codex 中配置 MCP Server 使用 mcp_config.example.json"
