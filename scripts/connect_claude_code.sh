#!/usr/bin/env bash
# scripts/connect_claude_code.sh
# 为 Claude Code 生成 .mcp.json 配置
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_PYTHON="${PROJECT_ROOT}/.venv/bin/python"

echo "StableAgent — Claude Code MCP 配置"
echo "=================================="

# 检查 .venv
if [ ! -f "$VENV_PYTHON" ]; then
    echo "错误: 未找到 .venv，请先运行: bash scripts/quickstart.sh"
    exit 1
fi

# 获取绝对路径
ABS_PYTHON="$(cd "$(dirname "$VENV_PYTHON")" && pwd)/$(basename "$VENV_PYTHON")"
ABS_PROJECT="$(cd "$PROJECT_ROOT" && pwd)"

# 备份旧 .mcp.json
MCP_JSON="${ABS_PROJECT}/.mcp.json"
if [ -f "$MCP_JSON" ]; then
    BACKUP="${MCP_JSON}.bak.$(date +%Y%m%d%H%M%S)"
    cp "$MCP_JSON" "$BACKUP"
    echo "已备份旧配置: $BACKUP"
fi

# 生成 .mcp.json
cat > "$MCP_JSON" << EOF
{
  "mcpServers": {
    "stableagent": {
      "type": "stdio",
      "command": "${ABS_PYTHON}",
      "args": [
        "-m",
        "stable_agent.mcp_stdio",
        "--profile",
        "minimal"
      ],
      "env": {
        "PYTHONPATH": "${ABS_PROJECT}",
        "STABLE_AGENT_TOOL_PROFILE": "minimal",
        "STABLE_AGENT_CURATOR_V2": "1",
        "STABLE_AGENT_SKILL_REPO_BACKEND": "file+sqlite",
        "STABLE_AGENT_OBSERVER_MODE": "replay_api"
      }
    }
  }
}
EOF

echo ""
echo "已生成 .mcp.json: $MCP_JSON"
echo ""
echo "下一步:"
echo "  1. 在 Claude Code 中运行: claude"
echo "  2. 在 Claude Code 中运行: /mcp"
echo "  3. 检查 stableagent 是否已连接"
echo ""
echo "配置内容:"
cat "$MCP_JSON"
