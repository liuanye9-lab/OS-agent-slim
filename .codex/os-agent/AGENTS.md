# AGENTS.md — StableAgent OS 项目约定

## 项目定位
StableAgent OS 是防止 AI 降智、控制 token 成本、持续学习优化的智能代理操作系统。

## MCP 接入
- 端点: `POST http://127.0.0.1:8000/mcp/v5/mcp`
- 传输: streamable_http (JSON-RPC 2.0)
- 工具前缀: `stableagent.*`

## 快捷入口
- `/os-agent` — 启动自优化工作流
- Dashboard: `http://127.0.0.1:8000/dashboard/v2`
- 连接页: `http://127.0.0.1:8000/connect`

## 关键约束
- V5 gateway/ 是唯一活跃 MCP 入口
- 所有工具三级命名: stableagent.<domain>.<action>
- 禁止静默吞异常
- 生产代码禁止 print
- 所有返回带 run_id + dashboard_url
