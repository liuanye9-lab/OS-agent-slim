# Claude Code MCP 配置指南

> V11.4 MCP + CLI Dual Gateway

## 两种 MCP 配置方式

### 方式 A：HTTP MCP

**优点**：Claude Code 直接识别为工具，支持实时调用
**缺点**：需要先启动 HTTP server

**配置文件**：`.mcp.json`（项目根目录）

```json
{
  "mcpServers": {
    "stableagent-http": {
      "type": "http",
      "url": "http://127.0.0.1:8000/mcp/",
      "timeout": 60000
    }
  }
}
```

**启动服务**：

```bash
cd /Users/Zhuanz/OS-Agent/OS-Agent
PYTHONPATH=. .venv/bin/python -m stable_agent.cli serve
```

**验证**：

```bash
# 检查服务状态
PYTHONPATH=. .venv/bin/python -m stable_agent.cli health --json

# 预期输出
{
  "ok": true,
  "server": true,
  "mcp": true,
  "tool_count": 55,
  "has_os_agent": true
}
```

---

### 方式 B：stdio MCP

**优点**：不需要先启动 HTTP server，更稳定
**缺点**：Claude Code 每次调用会启动一个新进程

**配置文件**：`.mcp.json`（项目根目录）

```json
{
  "mcpServers": {
    "stableagent-stdio": {
      "type": "stdio",
      "command": "/Users/Zhuanz/OS-Agent/OS-Agent/.venv/bin/python",
      "args": ["-m", "stable_agent.mcp_stdio"],
      "env": {
        "PYTHONPATH": "/Users/Zhuanz/OS-Agent/OS-Agent"
      }
    }
  }
}
```

**验证**：

```bash
# 手动测试 stdio MCP
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | \
  PYTHONPATH=. .venv/bin/python -m stable_agent.mcp_stdio

# 预期输出
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2024-11-05",
    "serverInfo": {
      "name": "StableAgent OS stdio",
      "version": "11.4.0"
    },
    "capabilities": {
      "tools": {}
    }
  }
}
```

---

## 两种方式对比

| 特性 | HTTP MCP | stdio MCP |
|------|----------|-----------|
| 是否需要 server | 需要先启动 server | 不需要 |
| Claude Code 是否识别为工具 | 是 | 是 |
| 稳定性 | 中高 | 高 |
| 适合场景 | 正式集成 | 本地稳定集成 |
| 启动速度 | 快（server 已运行） | 稍慢（每次启动进程） |
| 资源占用 | 低（共享 server） | 中（每次新进程） |

---

## 推荐配置

**日常开发**：使用 stdio MCP（更稳定，不需要手动启动 server）

**生产环境**：使用 HTTP MCP（server 常驻，资源占用低）

**两者不要同时命名为 stableagent**，避免冲突。可以保留：
- `stableagent-http`
- `stableagent-stdio`

---

## CLI Fallback

如果 MCP 都不可用，使用 CLI fallback：

```bash
PYTHONPATH=. /Users/Zhuanz/OS-Agent/OS-Agent/.venv/bin/python -m stable_agent.cli task run \
  --task-input "<user task>" \
  --open-dashboard \
  --json
```

**禁止**：
- 不要使用 `python`（会调用系统 Python 3.9）
- 不要使用 `python3`（会调用系统 Python 3.9）
- 必须使用 `.venv/bin/python`

---

## 故障排查

### 1. Claude Code 显示 "MCP 工具执行失败"

**原因**：HTTP MCP server 未启动或端口冲突

**解决**：

```bash
# 检查 server 是否运行
curl http://127.0.0.1:8000/api/health

# 如果未运行，启动 server
PYTHONPATH=. .venv/bin/python -m stable_agent.cli serve

# 如果端口被占用，使用其他端口
PYTHONPATH=. .venv/bin/python -m stable_agent.cli serve --port 8001
```

### 2. CLI 返回 ok=false 但没有 error

**原因**：HTTP MCP 返回的 structuredContent 缺少错误信息

**解决**：已修复（V11.4），确保 structuredContent 包含 error 字段

### 3. stdio MCP 启动失败

**原因**：Python 路径错误或依赖缺失

**解决**：

```bash
# 检查 Python 路径
.venv/bin/python --version

# 检查依赖
.venv/bin/pip list | grep fastapi

# 手动测试 stdio MCP
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | \
  PYTHONPATH=. .venv/bin/python -m stable_agent.mcp_stdio
```

### 4. 工具列表为空

**原因**：tool_schemas.py 或 unified_tool_registry.py 加载失败

**解决**：

```bash
# 检查工具数量
curl http://127.0.0.1:8000/mcp/tools | jq '.tool_count'

# 预期：55
```

---

## 人工核验步骤

### 1. 验证 HTTP MCP

```bash
# 启动 server
PYTHONPATH=. .venv/bin/python -m stable_agent.cli serve

# 新终端：检查健康状态
PYTHONPATH=. .venv/bin/python -m stable_agent.cli health --json

# 调用 os_agent
curl -s -X POST http://127.0.0.1:8000/mcp/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "stableagent.task.os_agent",
      "arguments": {
        "task_input": "测试任务",
        "open_dashboard": false
      }
    },
    "id": 1
  }' | jq '.result.structuredContent.ok'

# 预期：true
```

### 2. 验证 stdio MCP

```bash
# 测试 initialize
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | \
  PYTHONPATH=. .venv/bin/python -m stable_agent.mcp_stdio

# 测试 tools/list
echo '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | \
  PYTHONPATH=. .venv/bin/python -m stable_agent.mcp_stdio | jq '.result.tools | length'

# 预期：8
```

### 3. 验证 CLI Fallback

```bash
# 测试 CLI task run
PYTHONPATH=. .venv/bin/python -m stable_agent.cli task run \
  --task-input "测试任务" \
  --json

# 预期：包含 run_id, dashboard_url, observer_url
```

---

## 参考文档

- [MCP 协议规范](https://modelcontextprotocol.io/)
- [Claude Code MCP 配置](https://docs.anthropic.com/claude-code/mcp)
- [StableAgent OS README](../README.md)
