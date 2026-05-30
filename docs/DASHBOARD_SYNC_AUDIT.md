# DASHBOARD_SYNC_AUDIT.md — Dashboard 同步链路审计

**审计日期**: 2026-05-29  
**版本**: V5.6 → V6.0 refactor

---

## 关键发现

**Dashboard V3 数据来源完全是后端事件**——无前端编造。但 **ToolRouter 原生事件缺少 progress_pct、status_text_zh、why_zh**，只有经过 DecisionTraceBuilder 二次加工才获得完整信息。

---

## 逐模块审计

### 1. MCP Gateway
| 属性 | 详情 |
|------|------|
| 文件 | `stable_agent/gateway/mcp_gateway.py` (203行) |
| 路由 | POST `/` (JSON-RPC 2.0) + GET `/?run_id=xxx` (SSE) |
| run_id | 第104行从 `structuredContent` 提取 |

### 2. ToolRouter
| 属性 | 详情 |
|------|------|
| 文件 | `stable_agent/gateway/tool_router.py` (584行) |
| run_id 生成 | ✅ 第107-122行 `RunContext.create()` 生成 `run_{uuid}` |
| 事件发布 | ✅ `mcp.call.received` → `tool.risk_checked` → `tool.started` → `tool.completed/failed` |
| progress_pct | ⚠️ `_make_event_dict()` 使用 `ctx.progress_pct`（默认0） |
| status_text_zh | ⚠️ `_make_event_dict()` 使用 `ctx.status_text_zh`（默认空字符串） |
| why_zh | ❌ 不存在于 ToolRouter 事件 |
| avatar_state | ✅ `get_avatar_state(event_type)` 映射 |

### 3. RunContext
| 属性 | 详情 |
|------|------|
| 文件 | `stable_agent/gateway/run_context.py` (103行) |
| 字段 | `run_id`, `tool_call_id`, `trace_id`, `span_id`, `progress_pct`, `avatar_state`, `status_text_zh` 等 |
| 默认值 | `progress_pct=0`, `status_text_zh=""`, `avatar_state="listening"` |

### 4. RunLifecycle（双重存在）
| 路径 | 类型 | 状态 |
|------|------|------|
| `gateway/run_lifecycle.py` (21行) | Re-export 封装 | 向后兼容层 |
| `runtime/run_lifecycle.py` (165行) | 主实现 | ✅ 20个 RunStage，含 progress_pct/status_text_zh/avatar_state/why_zh/next_step_zh |

### 5. RunStore
| 属性 | 详情 |
|------|------|
| 文件 | `stable_agent/observation/run_store.py` (145行) |
| 存储 | 内存字典 `run_id → {events, started_at, status}` |

### 6. EventStream
| 属性 | 详情 |
|------|------|
| 文件 | `stable_agent/observation/event_stream.py` (130行) |
| 机制 | `asyncio.Queue` 按 run_id 管理，支持多订阅者并发 |

### 7. DashboardSync
| 属性 | 详情 |
|------|------|
| 文件 | `stable_agent/observation/dashboard_sync.py` (150行) |
| WebSocket | `/ws/runs/{run_id}` |

### 8. DashboardProjection
| 属性 | 详情 |
|------|------|
| 文件 | `stable_agent/observation/dashboard_projection.py` (356行) |
| 转换 | DecisionTrace → 前端渲染数据（why_zh, avatar_state, scene, evidence等） |
| 映射 | `_STAGE_AVATAR` 18个阶段到头像 |

### 9. DecisionTrace
| 属性 | 详情 |
|------|------|
| 文件 | `stable_agent/observation/decision_trace.py` (82行) |
| 字段 | `run_id, span_id, stage, title_zh/en, what_happened_zh/en, why_zh, why_en, evidence, discarded_evidence, decision_zh/en, next_step_zh/en, risk_level, confidence, importance, token_used, token_budget, quality_score, avatar_state, timestamp, raw_payload` |
| chain_of_thought | ❌ **从来不存在**（代码声明+测试验证） |

### 10. DecisionTraceBuilder
| 属性 | 详情 |
|------|------|
| 文件 | `stable_agent/observation/decision_trace_builder.py` (166行) |
| 职责 | 封装 DecisionNarrator，注入 RunLifecycle 元信息 |

### 11. DecisionNarrator
| 属性 | 详情 |
|------|------|
| 文件 | `stable_agent/explanation/decision_narrator.py` (779行) |
| 职责 | 22种事件类型双语叙述，提供 status_text_zh/en, why_zh/en, next_step_zh/en |
| 声明 | "不含 chain_of_thought — 只展示可观察决策摘要" |

### 12. ProgressModel（重复系统）
| 属性 | 详情 |
|------|------|
| 文件 | `stable_agent/observation/progress_model.py` (98行) |
| 阶段数 | 11个 ProgressStage |
| 使用状态 | ⚠️ 仅被 observation/__init__.py 导入，无人实际使用 |
| 判决 | **deprecate** — 与 RunLifecycle 重复 |

### 13. Pixel Avatar
| 文件 | 功能 | 驱动方式 |
|------|------|------|
| `web/static/pixel_avatar.js` (1019行) | Canvas 像素角色（Q版黑发女孩） | V5_AVATAR_STATES 映射 avatar_state → 动画 |
| `web/static/avatar_scene.js` (80+行) | Canvas 语义场景动画 | 13个场景绘制函数 |
| `web/static/dashboard_v3.js` (第124行) | CSS Emoji 头像 | 独立 AVATAR_SCENE_MAP（12个 emoji） |

### 14. Web 模板
| 模板 | 路由 | 用途 |
|------|------|------|
| `dashboard.html` | `/` | V1 实时观察面板 |
| `dashboard_v2.html` | `/dashboard/v2` | V2 决策观察舱 |
| `dashboard_v3.html` | `/runs/{run_id}` | V3 SaaS Run 详情 |
| 9个其他模板 | 各功能路由 | SaaS 功能页面 |

---

## 核心问题回答

| 问题 | 答案 | 说明 |
|------|------|------|
| MCP tools/call 生成 run_id？ | ✅ YES | ToolRouter `RunContext.create()` 自动生成 |
| run_id 贯穿 ToolRouter → RunStore → Dashboard？ | ✅ YES | 全链路通过 run_id 路由 |
| 每个关键事件有 progress_pct？ | ⚠️ PARTIAL | ToolRouter 原生事件 progress_pct=0，需 RunLifecycle 注入 |
| 每个关键事件有 status_text_zh？ | ⚠️ PARTIAL | ToolRouter 原生事件 status_text_zh=""，需 DecisionNarrator 补充 |
| 每个关键事件有 why_zh？ | ⚠️ PARTIAL | ToolRouter 原生事件无 why_zh，仅 DecisionTrace 有 |
| 每个关键事件有 avatar_state？ | ✅ YES | ToolRouter `get_avatar_state()` 映射所有事件类型 |
| Dashboard 只展示真实后端事件？ | ✅ YES | 无前端伪造/fallback 事件 |
| 像素人由 avatar_state 驱动？ | ✅ YES | V2: pixel_avatar.js Canvas；V3: CSS Emoji |

---

## 数据流总览

```
MCP POST → ToolRouter.route()
  ├── RunContext.create(run_id) ✅
  ├── _make_event_dict()
  │   ├── run_id: ✅
  │   ├── progress_pct: ⚠️ (ctx默认0)
  │   ├── status_text_zh: ⚠️ (ctx默认"")
  │   ├── why_zh: ❌ (不存在)
  │   └── avatar_state: ✅
  ├── _append_to_store(run_id, event) → RunStore ✅
  ├── _publish_event(event) → EventStream → DashboardSync WebSocket ✅
  │
  [另一路径]
  DecisionTraceBuilder + DecisionNarrator
  → DecisionTrace (完整 progress_pct/why_zh/avatar_state)
  → DashboardProjection → /api/runs/{run_id}/events
```

---

## 问题与改进

1. **Progress pct 空值问题**: ToolRouter 事件 progress_pct 始终为 0，应在 `_make_event_dict` 或 publish 时从 RunLifecycle 注入
2. **why_zh 缺失**: ToolRouter 事件不含 why_zh，应集成 DecisionNarrator 或 RunLifecycle 默认值
3. **Progress 重复**: `progress_model.py` 与 `runtime/run_lifecycle.py` 功能重复，应废弃前者
4. **avatar_scene.js 未使用**: `avatar_scene.js` 文件存在但 V3 dashboard 不使用；V2 引用但路径 `assets/js/avatar_scene.js` 可能不匹配

见 `DASHBOARD_SYNC_REFACTOR_PLAN.md`
