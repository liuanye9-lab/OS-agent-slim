# DASHBOARD_SYNC_STATUS_AUDIT.md — V6.0 Dashboard 同步审计

> 审计日期：2026-05-30

## 核心问题与答案

| # | 问题 | 答案 | 证据 |
|---|------|------|------|
| 1 | MCP tools/call 一定生成 run_id？ | **YES** | RunContext.create() 行 75: `final_run_id = uuid4()` |
| 2 | run_id 贯穿 ToolRouter→RunStore→Dashboard？ | **YES** | tool_router → EventStream.publish_sync → DashboardSync WebSocket |
| 3 | 每个关键事件有 progress_pct？ | **PARTIAL** | 字段存在但默认 0（RunContext 未自动填充） |
| 4 | 每个关键事件有 status_text_zh？ | **PARTIAL** | 字段存在但默认 ""（同上） |
| 5 | 每个关键事件有 why_zh？ | **YES** | DecisionTraceBuilder 注入 |
| 6 | 每个关键事件有 next_step_zh？ | **YES** | DecisionTraceBuilder 注入 |
| 7 | 每个关键事件有 avatar_state？ | **YES** | tool_schemas.py AVATAR_STATE_MAP fallback |
| 8 | Dashboard 只消费后端事件？ | **YES** | run_observer.js 行 2 明确声明 |
| 9 | 像素人只由 avatar_state 驱动？ | **YES** | renderAvatarScene(avatarState, canvasId) |

---

## 数据流架构

```
MCP JSON-RPC → ToolRouter.route() → _make_event_dict()
                                        ↓
                        工具事件 _publish_event() → EventStream
                           ↓                        ↓
                       RunStore              DashboardSync
                     (REST API)             (WebSocket)
                           ↓                      ↓
                    /api/runs/{id}/events   /dashboard-sync/ws/runs/{id}
                           ↓                      ↓
                    dashboard_v3.js        run_observer.js
```

---

## 关键缺口

### GAP-1: RunContext.progress_pct 始终为 0
- ToolRouter.route() 未在创建 RunContext 后调用 get_stage_meta() 更新进度
- progress_pct 和 status_text_zh 始终为默认值

### GAP-2: STAGE_MAP 仅映射 execution
- tool_router.py: _STAGE_MAP 仅 7 种事件类型
- 全部映射到 "execution"，缺失 planning/evaluating/learning 阶段

### GAP-3: DecisionTraceBuilder 有静默 except:pass
- tool_router.py:476-477 — 无日志静默降级
- decision_trace_builder.py:87-89 — 弱 debug log

### GAP-4: Dashboard V3 使用 polling 而非 WebSocket
- dashboard_run_detail.js 3 秒 polling REST API
- run_observer.js 正确使用 WebSocket

---

## WebSocket/SSE 端点确认

| 端点 | 路径 | 状态 |
|------|------|------|
| SSE | `/mcp?run_id=xxx` | 活跃 |
| Per-Run WS | `/dashboard-sync/ws/runs/{run_id}` | 活跃 |
| Observer | `/observe/{run_id}` | 活跃 |
| 全局 WS (旧) | `/dashboard/ws/events` | 活跃 |

---

## DecisionTrace 合规确认

- chain_of_thought: **不包含** ✅
- hidden_reasoning: **不包含** ✅
- model_inner_thought: **不包含** ✅
- 3 处测试断言验证此约束
