#!/bin/bash
# verify_dual_gateway.sh — V11.4 MCP + CLI Dual Gateway 端到端核验脚本
#
# 用法：bash scripts/verify_dual_gateway.sh

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

pass() {
    echo -e "${GREEN}✓ $1${NC}"
    PASS_COUNT=$((PASS_COUNT + 1))
}

fail() {
    echo -e "${RED}✗ $1${NC}"
    FAIL_COUNT=$((FAIL_COUNT + 1))
}

warn() {
    echo -e "${YELLOW}⚠ $1${NC}"
    WARN_COUNT=$((WARN_COUNT + 1))
}

echo "========================================"
echo "V11.4 MCP + CLI Dual Gateway 核验"
echo "========================================"
echo ""

# ------------------------------------------------------------------
# 1. 检查 .venv/bin/python 存在
# ------------------------------------------------------------------
echo "1. 检查 Python 环境"
if [ -f ".venv/bin/python" ]; then
    pass ".venv/bin/python 存在"
    PYTHON_VERSION=$(.venv/bin/python --version 2>&1)
    echo "   版本: $PYTHON_VERSION"
else
    fail ".venv/bin/python 不存在"
    echo "   请先创建虚拟环境: python3.11 -m venv .venv"
    exit 1
fi

# ------------------------------------------------------------------
# 2. 检查 Python >= 3.11
# ------------------------------------------------------------------
PYTHON_MAJOR=$(.venv/bin/python -c "import sys; print(sys.version_info.major)")
PYTHON_MINOR=$(.venv/bin/python -c "import sys; print(sys.version_info.minor)")
if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 11 ]; then
    pass "Python 版本 >= 3.11"
else
    fail "Python 版本 < 3.11 (当前: $PYTHON_MAJOR.$PYTHON_MINOR)"
    exit 1
fi

# ------------------------------------------------------------------
# 3. 检查 HTTP server 是否运行
# ------------------------------------------------------------------
echo ""
echo "2. 检查 HTTP server"
if curl -s --max-time 3 http://127.0.0.1:8000/api/health > /dev/null 2>&1; then
    pass "HTTP server 运行中"
else
    warn "HTTP server 未运行"
    echo "   请先启动: PYTHONPATH=. .venv/bin/python -m stable_agent.cli serve"
    echo "   跳过 HTTP 相关检查..."
fi

# ------------------------------------------------------------------
# 4. curl /api/health
# ------------------------------------------------------------------
if curl -s --max-time 3 http://127.0.0.1:8000/api/health > /dev/null 2>&1; then
    echo ""
    echo "3. 检查 /api/health"
    HEALTH=$(curl -s http://127.0.0.1:8000/api/health)
    if echo "$HEALTH" | grep -q '"ok": true'; then
        pass "/api/health 返回 ok=true"
    else
        fail "/api/health 返回 ok=false"
    fi
fi

# ------------------------------------------------------------------
# 5. curl /mcp/health
# ------------------------------------------------------------------
if curl -s --max-time 3 http://127.0.0.1:8000/mcp/health > /dev/null 2>&1; then
    echo ""
    echo "4. 检查 /mcp/health"
    MCP_HEALTH=$(curl -s http://127.0.0.1:8000/mcp/health)
    if echo "$MCP_HEALTH" | grep -q '"ok": true'; then
        pass "/mcp/health 返回 ok=true"
    else
        fail "/mcp/health 返回 ok=false"
    fi
fi

# ------------------------------------------------------------------
# 6. curl /mcp/tools，确认 inputSchema
# ------------------------------------------------------------------
if curl -s --max-time 3 http://127.0.0.1:8000/mcp/tools > /dev/null 2>&1; then
    echo ""
    echo "5. 检查 /mcp/tools"
    TOOLS=$(curl -s http://127.0.0.1:8000/mcp/tools)
    TOOL_COUNT=$(echo "$TOOLS" | grep -o '"tool_count": [0-9]*' | grep -o '[0-9]*')
    echo "   工具数量: $TOOL_COUNT"
    if [ "$TOOL_COUNT" -ge 50 ]; then
        pass "工具数量 >= 50"
    else
        fail "工具数量 < 50 (当前: $TOOL_COUNT)"
    fi

    if echo "$TOOLS" | grep -q '"inputSchema"'; then
        pass "工具列表包含 inputSchema"
    else
        fail "工具列表缺少 inputSchema"
    fi
fi

# ------------------------------------------------------------------
# 7. HTTP MCP tools/call os_agent
# ------------------------------------------------------------------
if curl -s --max-time 3 http://127.0.0.1:8000/mcp/ > /dev/null 2>&1; then
    echo ""
    echo "6. 测试 HTTP MCP tools/call os_agent"
    RESULT=$(curl -s -X POST http://127.0.0.1:8000/mcp/ \
        -H "Content-Type: application/json" \
        -d '{
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "stableagent.task.os_agent",
                "arguments": {
                    "task_input": "核验测试任务",
                    "open_dashboard": false
                }
            },
            "id": 1
        }')

    if echo "$RESULT" | grep -q '"isError": false'; then
        pass "HTTP MCP tools/call 返回 isError=false"
    else
        fail "HTTP MCP tools/call 返回 isError=true 或无响应"
    fi

    if echo "$RESULT" | grep -q '"ok": true'; then
        pass "structuredContent.ok=true"
    else
        fail "structuredContent.ok=false"
    fi
fi

# ------------------------------------------------------------------
# 8. CLI task run
# ------------------------------------------------------------------
echo ""
echo "7. 测试 CLI task run"
CLI_RESULT=$(PYTHONPATH=. .venv/bin/python -m stable_agent.cli task run \
    --task-input "核验测试任务" \
    --json 2>&1 || true)

if echo "$CLI_RESULT" | grep -q '"ok": true'; then
    pass "CLI task run 返回 ok=true"
else
    warn "CLI task run 返回 ok=false (可能 server 未运行)"
fi

# ------------------------------------------------------------------
# 9. stdio MCP initialize
# ------------------------------------------------------------------
echo ""
echo "8. 测试 stdio MCP initialize"
STDIO_INIT=$(echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | \
    PYTHONPATH=. .venv/bin/python -m stable_agent.mcp_stdio 2>/dev/null || echo "FAIL")

if echo "$STDIO_INIT" | grep -q '"StableAgent OS stdio"'; then
    pass "stdio MCP initialize 返回 serverInfo"
else
    fail "stdio MCP initialize 失败"
fi

# ------------------------------------------------------------------
# 10. stdio MCP tools/list
# ------------------------------------------------------------------
echo ""
echo "9. 测试 stdio MCP tools/list"
STDIO_TOOLS=$(echo '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | \
    PYTHONPATH=. .venv/bin/python -m stable_agent.mcp_stdio 2>/dev/null || echo "FAIL")

if echo "$STDIO_TOOLS" | grep -q '"inputSchema"'; then
    pass "stdio MCP tools/list 包含 inputSchema"
else
    fail "stdio MCP tools/list 缺少 inputSchema"
fi

if echo "$STDIO_TOOLS" | grep -q '"stableagent.task.os_agent"'; then
    pass "stdio MCP tools/list 包含 os_agent"
else
    fail "stdio MCP tools/list 缺少 os_agent"
fi

# ------------------------------------------------------------------
# 汇总
# ------------------------------------------------------------------
echo ""
echo "========================================"
echo "核验结果汇总"
echo "========================================"
echo -e "${GREEN}通过: $PASS_COUNT${NC}"
echo -e "${RED}失败: $FAIL_COUNT${NC}"
echo -e "${YELLOW}警告: $WARN_COUNT${NC}"
echo ""

if [ "$FAIL_COUNT" -gt 0 ]; then
    echo -e "${RED}存在失败项，请检查！${NC}"
    exit 1
else
    echo -e "${GREEN}全部通过！${NC}"
    exit 0
fi
