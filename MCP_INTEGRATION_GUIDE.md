# MCP Integration Guide

> StableAgent Cloud MCP 集成指南
> 版本: v2.2

## 快速接入

### Claude Code

```json
{
  "mcpServers": {
    "stableagent": {
      "url": "http://localhost:8000/mcp",
      "transport": "http"
    }
  }
}
```

### Codex / Cursor

在 Connect 页面 (`/connect`) 一键生成配置。

## 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/mcp` | POST | JSON-RPC 2.0 (initialize/tools/list/tools/call) |
| `/mcp` | GET | SSE 事件流 (?run_id=xxx) |
| `/mcp/legacy` | POST | 向后兼容旧 MCP |
| `/dashboard-sync` | WebSocket | Dashboard 实时同步 |

## 工具命名空间

所有工具使用 `stableagent.<domain>.<action>` 格式:

| Domain | Tools | Count |
|--------|-------|-------|
| `stableagent.task.*` | process, os_agent | 2 |
| `stableagent.context.*` | build, estimate_budget | 2 |
| `stableagent.memory.*` | retrieve, write_candidate | 2 |
| `stableagent.rag.*` | retrieve | 1 |
| `stableagent.eval.*` | evaluate, run | 2 |
| `stableagent.badcase.*` | record | 1 |
| `stableagent.skillopt.*` | status, get_current_skill, run_epoch, export_best | 4 |
| `stableagent.skill.*` | patch_propose, validate, review, export_best | 4 |
| `stableagent.workspace.*` | create | 1 |
| `stableagent.project.*` | create, list | 2 |
| `stableagent.run.*` | get | 1 |
| `stableagent.trace.*` | get_run | 1 |
| `stableagent.regression.*` | create | 1 |
| `stableagent.usage.*` | get | 1 |
| `stableagent.apikey.*` | create, revoke | 2 |
| `stableagent.approval.*` | respond | 1 |

## 调用示例

### tools/list

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
```

### tools/call

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "id":1,
    "method":"tools/call",
    "params":{
      "name":"stableagent.task.os_agent",
      "arguments":{"task_input":"分析这个项目架构","mode":"auto"}
    }
  }'
```

### SSE 事件流

```bash
curl -N http://localhost:8000/mcp?run_id=run_abc123
```

## 风险等级

| Risk | 行为 | 示例 |
|------|------|------|
| low | 直接执行 | memory.retrieve |
| medium | 记录但不阻断 | task.process |
| high | 硬阻断，需审批 | skill.export_best |
| forbidden | 禁止执行 | — |

## SaaS 模式

在 SaaS 模式下，需要 API Key 或 JWT Token:

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk_your_api_key_here" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
```
