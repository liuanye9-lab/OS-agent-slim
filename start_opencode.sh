#!/bin/bash
# ============================================================
# StableAgent OS — OpenCode 一键启动脚本
# 
# 1. 启动 StableAgent Web 服务 (localhost:8000)
# 2. 等待服务就绪
# 3. 打开 Dashboard 浏览器页面
# 4. 启动 OpenCode（如果已安装）
# ============================================================
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PYTHON="$HOME/.workbuddy/binaries/python/envs/default/bin"
PORT=8000

echo "=============================================="
echo "  StableAgent OS + OpenCode 启动"
echo "=============================================="
echo ""

# ---- Step 1: 启动 Web 服务 ----
echo "[1/4] 启动 StableAgent Web 服务..."
lsof -ti:$PORT | xargs kill -9 2>/dev/null || true
sleep 1

cd "$PROJECT_DIR"
"$VENV_PYTHON/uvicorn" web.server:app --host 0.0.0.0 --port $PORT &
SERVER_PID=$!
echo "      服务 PID: $SERVER_PID"

# ---- Step 2: 等待就绪 ----
echo "[2/4] 等待服务就绪..."
for i in $(seq 1 15); do
    if curl -s -o /dev/null -w "%{http_code}" "http://localhost:$PORT/" 2>/dev/null | grep -q 200; then
        echo "      服务已就绪 ✅"
        break
    fi
    sleep 1
done

# ---- Step 3: 打开 Dashboard ----
echo "[3/4] 打开可视化 Dashboard..."
open "http://localhost:$PORT" 2>/dev/null || echo "      请手动打开: http://localhost:$PORT"

# ---- Step 4: 启动 OpenCode ----
echo "[4/4] 启动 OpenCode..."
if command -v opencode &>/dev/null; then
    opencode "$PROJECT_DIR" &
    echo "      OpenCode 已启动 ✅"
elif [ -d "/Applications/OpenCode.app" ]; then
    open -a OpenCode "$PROJECT_DIR" &
    echo "      OpenCode 已启动 ✅"
else
    echo "      ⚠️ 未找到 OpenCode，请手动安装后启动"
    echo "      下载: https://opencode.ai"
fi

echo ""
echo "=============================================="
echo "  🎉 启动完成！"
echo "  Dashboard:  http://localhost:$PORT"
echo "  MCP 端点:   POST http://localhost:$PORT/mcp"
echo "  MCP 工具数: 14"
echo ""
echo "  在 OpenCode 中直接对话即可使用 StableAgent 能力"
echo "  每次对话会自动记录 run_id，可实时查看可视化"
echo "=============================================="

# 保持脚本运行（Ctrl+C 停止）
wait $SERVER_PID
