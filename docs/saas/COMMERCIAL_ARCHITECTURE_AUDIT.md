# COMMERCIAL_ARCHITECTURE_AUDIT.md

> 审计日期: 2026-05-29 | 基准: 923 tests passed | Python 3.13.12

## 1. 审计摘要

| 文件 | 实现 | Stub | 测试 | 吞异常 | 绕过权限 | 绕过审批 |
|------|------|------|------|--------|----------|----------|
| `response_adapter.py` | ⚠️ 字段缺失 | — | ✅ | ✅ | — | — |
| `tool_router.py` | ⚠️ 高风险未阻断 | — | ✅ | ✅ | — | ❌ STUB |
| `mcp_gateway.py` | ✅ | — | ✅ | ✅ | — | — |
| `unified_tool_registry.py` | ✅ | — | ✅ | ✅ | — | — |
| `tool_schemas.py` | ✅ | — | — | — | — | — |
| `models.py` | ✅ | — | ✅ | ✅ | — | — |
| `repository.py` | ⚠️ 吞错误 | — | ✅ | ❌ 大量 | — | — |
| `auth.py` | ✅ | — | — | ✅ | — | — |
| `permissions.py` | ✅ | — | ✅ | — | — | — |
| `api_keys.py` | ✅ | — | ✅ | ✅ | — | — |
| `usage.py` | ✅ | — | ✅ | ✅ | — | — |
| `skill_review_service.py` | ✅ | — | ✅ | ✅ | — | — |
| `regression_service.py` | ⚠️ | ⚠️ | — | ✅ | — | — |
| `web/server.py` | ✅ | — | ✅ | ✅ | — | — |

## 2. P0 级问题

### 2.1 ResponseAdapter 字段缺失 (P0)

`response_adapter.py:60-78`:
- 缺失: `progress_pct`, `status_text_zh`, `avatar_state`, `decision_summary_zh`, `why_zh`
- `dashboard_url` 硬编码 `f"/runs/{result.run_id}"` 忽略 result 自定义值
- `tool_call_id` 未传递

### 2.2 高风险工具未硬阻断 (P0 - CRITICAL)

`tool_router.py:163-188`:
- 代码注释明确写 "(STUB：简化处理，标记需要审批但继续执行)"
- high risk 工具创建审批后**继续执行** handler
- 违反了 Phase 6 安全要求

### 2.3 MCP 入口散乱 (P0)

- `/mcp/v5/mcp` - V5 Gateway（当前推荐入口）
- `/mcp` - 旧 MCPServer
- README 推荐 `/mcp/v5/mcp`，但应该是 `/mcp`

### 2.4 Repository 吞错误 (P0)

- `save_run` 失败返回 `False`，调用方可能忽略
- `save_usage_event` 失败返回 `None`
- 关键写入失败应该显式抛错

### 2.5 task.os_agent 缺阶段事件 (P0)

`unified_tool_registry.py`:
- `_h_task_os_agent` 只发 `tool.started` 和 `task.completed`
- 缺少中间阶段事件（intent parsed, context budgeted 等）
- Dashboard 无法展示多阶段进度

## 3. P1 级问题

- 权限 guard scaffold 已存在但 API 未接入
- 无 migration 系统
- 无 RegressionRunner
- 无 ValidationReport
- best_skill.md 无审批链路展示

## 4. 合规检查

| 要求 | 状态 |
|------|------|
| 无第4套 MCP 实现 | ✅ |
| high risk 硬阻断 | ❌ STUB |
| best_skill.md 不绕过 human review | ⚠️ 未完全阻断 |
| 不开静默覆盖 skill | ✅ |
| 不把隐私写入 skill | ✅ |
| 测试 923 passed | ✅ |

## 5. 建议执行顺序

```
Phase 2: MCP 入口收敛       (20 min)
Phase 5: ResponseAdapter 修复 (15 min)
Phase 6: 高风险硬阻断        (20 min)
Phase 8: Repository 错误     (15 min)
Phase 10: 权限 Guard         (15 min)
Phase 7: os_agent 事件       (30 min)
Other phases: scaffold only
```
