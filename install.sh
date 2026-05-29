#!/usr/bin/env bash
# StableAgent OS — 一键安装脚本 (小白友好版)
# 用法: curl -fsSL https://raw.githubusercontent.com/liuanye9-lab/OS-Agent/main/install.sh | bash
# 或:   bash install.sh

set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info() { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║    StableAgent OS — 一键安装             ║"
echo "║    让 AI Agent 越用越懂你的偏好          ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# 1. 检查 Python
PYTHON=""
for py in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v $py &>/dev/null; then
        ver=$($py -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        if [ "$(echo "$ver" | cut -d. -f1)" -ge 3 ] && [ "$(echo "$ver" | cut -d. -f2)" -ge 10 ]; then
            PYTHON=$py; break
        fi
    fi
done
[ -z "$PYTHON" ] && err "未找到 Python 3.10+，请先安装: https://python.org/downloads/"
info "Python: $($PYTHON --version)"

# 2. 安装依赖
info "安装依赖..."
$PYTHON -m pip install -q fastapi uvicorn websockets jinja2 pydantic httpx 2>/dev/null || warn "部分包已安装"

# 3. 确认项目位置
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
info "项目目录: $SCRIPT_DIR"

# 4. 检查服务是否已运行
if lsof -ti:8000 &>/dev/null; then
    info "服务已在 http://localhost:8000 运行"
else
    info "启动服务..."
    $PYTHON -m uvicorn web.server:app --host 127.0.0.1 --port 8000 &
    sleep 2
    if lsof -ti:8000 &>/dev/null; then
        info "服务启动成功"
    else
        warn "服务可能未正常启动，请手动运行: uvicorn web.server:app --host 127.0.0.1 --port 8000"
    fi
fi

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  🎉 安装完成！                           ║"
echo "╠══════════════════════════════════════════╣"
echo "║  Dashboard:  http://localhost:8000/dashboard/v3"
echo "║  一键接入:   http://localhost:8000/connect"
echo "║  MCP 端点:   http://localhost:8000/mcp/v5/mcp"
echo "║                                          ║"
echo "║  下一步：                                 ║"
echo "║  1. 打开 http://localhost:8000/connect   ║"
echo "║  2. 选择你的 AI 工具（Codex/Claude）      ║"
echo "║  3. 复制配置 → 粘贴到你的 AI 工具设置     ║"
echo "║  4. 在 AI 工具中输入 /os-agent 你的任务   ║"
echo "╚══════════════════════════════════════════╝"
echo ""
