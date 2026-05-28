# Session Context — 2026-05-28

## 已完成

1. **部署服务** — `web.server:app` 运行在 `localhost:8000`，PID 在后台
2. **修复 V5 MCP Gateway** — 两个 bug：
   - 挂载顺序：`/mcp/v5` 移到 `/mcp` 之前，避免被遮蔽
   - FastAPI 0.136.3 兼容性：`from __future__ import annotations` 导致 Request 类型注入失败，将 FastAPI/Request/JSONResponse 等导入移到模块级
3. **验证通过** — `POST /mcp/v5/mcp` 返回 14 个工具
4. **架构评估** — 骨架真实但部分后端是 mock（MockLLMClient），需接入真实 LLM 后才有真价值
5. **CODEX.md** — 20 条编码规范已生成

## 当前状态

- 服务 PID: (lsof -ti:8000)
- Dashboard: http://localhost:8000
- MCP 端点: POST http://localhost:8000/mcp/v5/mcp
- OpenCode 配置: .opencode/mcp.json（自动加载）

## 修改过的文件

- `web/server.py` — 调整 mount 顺序（V5 先于 V3）
- `stable_agent/gateway/mcp_gateway.py` — 模块级导入 FastAPI 类型，移除内联 import
- `stable_agent/gateway/tool_router.py` — 已知 event loop 反模式（待修复）
