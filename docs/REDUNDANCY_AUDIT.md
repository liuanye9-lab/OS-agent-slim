# REDUNDANCY_AUDIT.md — 冗余模块审计

**审计日期**: 2026-05-29  
**版本**: V5.6 → V6.0 refactor

---

## 判决汇总

| # | 对象 | 判决 |
|---|------|------|
| 1 | `stable_agent/mcp_server.py` + `mcp_tools.py` (V3 MCP) | **deprecate** |
| 2 | `stable_agent/mcp/skillopt_tools.py` (V4 MCP) | **deprecate** |
| 3 | `stable_agent/gateway/` (V5 MCP) | **keep** — 唯一活跃入口 |
| 4 | `/mcp_bridge.py` (独立桥接) | **keep** — 独立 stdio→HTTP 工具 |
| 5 | `dashboard.html` (V1) | **keep** — 默认首页 |
| 6 | `dashboard_v2.html` (V2) | **keep** — 决策观察舱 |
| 7 | `dashboard_v3.html` (V3) | **keep** — SaaS Run 详情 |
| 8 | `observation/progress_model.py` | **deprecate** — 与 RunLifecycle 重复 |
| 9 | `runtime/run_lifecycle.py` | **keep** — 唯一权威进度源 |
| 10 | `models.py` Event/TraceEvent | **keep** — 共享数据模型 |
| 11 | `gateway/tool_schemas.py` | **keep** — 权威 Schema 源 |
| 12 | `gateway/unified_tool_registry.py` | **keep** — Handler 绑定 |
| 13 | `skill_optimizer/skill_optimization_engine.py` | **keep** — 核心引擎 |
| 14 | `observation/run_store.py` | **keep** — 互补非重复 |
| 15 | `observation/event_stream.py` | **keep** — 互补非重复 |
| 16 | `observation/dashboard_sync.py` | **keep** — 互补非重复 |
| 17 | `stable_agent/approval.py` (旧版) | **deprecate** — 迁移到 approval/ |
| 18 | `stable_agent/approval/` (新版) | **keep** — 标准化入口 |
| 19 | `gateway/run_lifecycle.py` (re-export) | **merge** — 合并到 runtime/ |
| 20 | `web/static/progress_bar.js` | **delete_later** — 未引用 |
| 21 | `web/static/decision_panel.js` | **delete_later** — 未引用 |
| 22 | `web/static/dashboard_run_client.js` | **delete_later** — 未引用 |
| 23 | `web/static/color_system_preview.html` | **delete_later** — 未引用 |
| 24 | `stable_agent/run_replay.py` | **delete_later** — 无导入 |

---

## 详细分析

### 1. 重复 MCP 实现（4层入口）

| 层级 | 文件 | 路由 | 状态 |
|------|------|------|------|
| V3 | `mcp_server.py` + `mcp_tools.py` | `/mcp/legacy` | 兼容保留，所有能力已被V5覆盖 |
| V4 | `mcp/skillopt_tools.py` | `/mcp/legacy/tools/skillopt/*` | 已被 UnifiedToolRegistry 替代 |
| V5 | `gateway/` (7个模块) | `/mcp` | **唯一活跃主入口** |
| Bridge | `/mcp_bridge.py` | 独立脚本 | stdio→HTTP 桥接工具 |
| Vercel | `/api/index.py` | Serverless | web/app 薄包装 |

**处理**: V3/V4 加 `@deprecated` 注释，READM 推荐 `/mcp` 入口

### 2. 重复 Dashboard 页面（3版本共存）

不是真正的冗余——三者功能不同：
- V1 (`dashboard.html`): 实时 WebSocket 观察面板，默认首页
- V2 (`dashboard_v2.html`): 决策观察舱（5区布局），带 DecisionTrace 时间线
- V3 (`dashboard_v3.html`): SaaS Run 详情，工作空间/项目维度

**处理**: 保留三者，统一导航入口

### 3. 重复 ProgressModel（2套进度系统）

| 模块 | 阶段数 | 实际使用 |
|------|--------|----------|
| `progress_model.py` | 11阶段 | **无人使用**（仅 observation/__init__.py 暴露） |
| `runtime/run_lifecycle.py` | 20阶段 | 被 unified_tool_registry、decision_trace_builder 等核心模块导入 |

**处理**: `progress_model.py` → **deprecate**，保留为兼容层，内部转用 RunLifecycle

### 4. 重复 SkillOpt 入口

| 入口 | 文件 | 判决 |
|------|------|------|
| V4 包装 | `mcp/skillopt_tools.py` (10个MCP工具) | **deprecate** |
| V5 包装 | `gateway/unified_tool_registry.py` (4个 _h_skillopt_* handler) | **keep** |

需要将 V4 独有的工具（submit_user_feedback, collect_rollout, validate_candidate_skill 等）迁移到 V5

### 5. approval 模块双重存在

| 路径 | 说明 |
|------|------|
| `stable_agent/approval.py` (旧) | 单文件模块 |
| `stable_agent/approval/` (新) | 包结构，含 `__init__.py`（带动态兼容导入）、`pending_tool_store.py`、`approval_resume_service.py` |

**处理**: `approval.py` → **deprecate**，逻辑迁移到 `approval/` 包

### 6. gateway/run_lifecycle.py 重复

`gateway/run_lifecycle.py` (21行) 仅是 `runtime/run_lifecycle.py` 的 re-export。

**处理**: **merge** — 更新导入路径，移除 gateway 版本

### 7. 未使用文件

| 文件 | 原因 |
|------|------|
| `web/static/progress_bar.js` | 无任何 HTML 模板引用 |
| `web/static/decision_panel.js` | 无任何 HTML 模板引用 |
| `web/static/dashboard_run_client.js` | 无任何 HTML 模板引用 |
| `web/static/color_system_preview.html` | 未被路由引用 |
| `stable_agent/run_replay.py` | 全代码库无 import |

**处理**: **delete_later**（本轮不加删除，加 `@deprecated: unused` 注释）

### 8. 文档错误

| 文档 | 错误 |
|------|------|
| `docs/system_design.md` 第591行 | `web/static/dashboard_v2.html` → 应为 `web/templates/dashboard_v2.html` |
| `docs/saas/SAAS_ARCHITECTURE_AUDIT.md` 第166行 | `web/templates/project_dashboard.html` — 文件从未创建 |

---

## 清理计划

### P0 (本轮执行)
1. ✅ 加 deprecation 注释到 V3/V4 MCP、approval.py、progress_model.py
2. ✅ gateway/run_lifecycle.py 合并到 runtime/run_lifecycle.py
3. ✅ 未使用文件加 `@deprecated: unused` 注释
4. ✅ 修复文档路径错误

### P1 (下轮)
1. 移除 V3/V4 MCP 端点（先确保零调用）
2. 移除 approval.py 旧文件
3. 删除未使用 JS/CSS 文件
4. V4 SkillOpt 工具迁移到 V5
