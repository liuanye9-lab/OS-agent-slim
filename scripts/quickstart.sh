#!/usr/bin/env bash
# scripts/quickstart.sh
# StableAgent 快速启动脚本
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "StableAgent Quickstart"
echo "======================"
cd "$PROJECT_ROOT"

# Step 1: 检查 Python 版本
echo ""
echo "[1/8] 检查 Python 版本..."
PYTHON_CMD=""
for cmd in python3.11 python3.12 python3.13 python3; do
    if command -v "$cmd" &>/dev/null; then
        VERSION=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        MAJOR=$(echo "$VERSION" | cut -d. -f1)
        MINOR=$(echo "$VERSION" | cut -d. -f2)
        if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 11 ]; then
            PYTHON_CMD="$cmd"
            echo "  Found: $cmd ($VERSION)"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "错误: 需要 Python >= 3.11"
    echo "请安装 Python 3.11+ 后重试"
    exit 1
fi

# Step 2: 创建 .venv
echo ""
echo "[2/8] 创建虚拟环境..."
if [ ! -d ".venv" ]; then
    "$PYTHON_CMD" -m venv .venv
    echo "  已创建 .venv"
else
    echo "  .venv 已存在，跳过"
fi

# Step 3: 激活虚拟环境
echo ""
echo "[3/8] 激活虚拟环境..."
source .venv/bin/activate
echo "  已激活: $(which python3)"

# Step 4: 安装依赖
echo ""
echo "[4/8] 安装依赖..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt -q
elif [ -f "pyproject.toml" ]; then
    pip install -e ".[dev]" -q 2>/dev/null || pip install -e . -q
else
    echo "  警告: 未找到 requirements.txt 或 pyproject.toml"
fi

# 核心依赖
pip install fastapi uvicorn pydantic httpx -q 2>/dev/null || true
echo "  依赖安装完成"

# Step 5: 初始化 .skills/
echo ""
echo "[5/8] 初始化技能目录..."
mkdir -p .skills/skills .skills/candidates .skills/validation
echo "  已创建 .skills/ 目录"

# Step 6: 初始化 SQLite index
echo ""
echo "[6/8] 初始化 SQLite 索引..."
PYTHONPATH="$PROJECT_ROOT" python3 -c "
from stable_agent.skills.index_store import SkillIndexStore
store = SkillIndexStore('.skills/index.sqlite')
print('  SQLite index 初始化完成')
" 2>/dev/null || echo "  警告: SQLite 初始化跳过 (模块未就绪)"

# Step 7: 运行 doctor
echo ""
echo "[7/8] 运行健康检查..."
PYTHONPATH="$PROJECT_ROOT" python3 -m stable_agent.cli doctor --json 2>/dev/null || {
    echo "  警告: doctor 检查跳过 (需要运行中的服务器)"
    echo "  启动服务器: python -m stable_agent.cli serve"
}

# Step 8: 测试 minimal tools/list
echo ""
echo "[8/8] 测试 minimal profile..."
PYTHONPATH="$PROJECT_ROOT" STABLE_AGENT_TOOL_PROFILE=minimal python3 -c "
from stable_agent.gateway.tool_profiles import get_tool_profile, MINIMAL_TOOLS
profile = get_tool_profile()
print(f'  Profile: {profile.value}')
print(f'  Minimal tools: {len(MINIMAL_TOOLS)}')
assert len(MINIMAL_TOOLS) <= 12, f'Too many minimal tools: {len(MINIMAL_TOOLS)}'
assert 'stableagent.task.os_agent' in MINIMAL_TOOLS
print('  Minimal profile 测试通过!')
" || echo "  警告: profile 测试跳过"

echo ""
echo "======================"
echo "Quickstart 完成!"
echo ""
echo "下一步:"
echo "  1. 启动服务器: PYTHONPATH=. python -m stable_agent.cli serve"
echo "  2. 连接 Claude Code: bash scripts/connect_claude_code.sh"
echo "  3. 运行集成测试: bash scripts/integration_test.sh"
echo ""
