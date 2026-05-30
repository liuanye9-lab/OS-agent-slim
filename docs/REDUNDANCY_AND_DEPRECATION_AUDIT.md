# REDUNDANCY_AND_DEPRECATION_AUDIT.md — V6.0 冗余审计

> 审计日期：2026-05-30

## 维度 1: MCP 入口 (4 套)

| 文件 | 层次 | 状态 | 判决 |
|------|------|------|------|
| `mcp_server.py` | V3 MCP | @deprecated, /mcp/legacy 已断连 | **deprecate** |
| `mcp/skillopt_tools.py` | V4 MCP | @deprecated, 已断连 | **deprecate** |
| `gateway/mcp_gateway.py` | V5 统一入口 | 唯一活跃入口 | **keep** |
| `/mcp_bridge.py` | stdio 桥接 | 活跃 | **keep** |

## 维度 2: Dashboard 页面 (5 套)

| 文件 | 路由 | 状态 | 判决 |
|------|------|------|------|
| `dashboard.html` | `/` | V5 实时观察 | **keep** |
| `dashboard_v2.html` | `/dashboard/v2` | V5.5 决策观察舱 | **keep** |
| `dashboard_v3.html` | `/runs/{run_id}` | SaaS Run 详情 | **keep** |
| `run_observer.html` | `/observe/{run_id}` | V6.5 新 Observer | **keep (推荐)** |
| `connect.html` | `/connect` | MCP 接入指南 | **keep** |

## 维度 3: ProgressModel (2 套)

| 文件 | 阶段数 | 状态 | 判决 |
|------|--------|------|------|
| `observation/progress_model.py` | 11 阶段 | @deprecated V6.0 | **deprecate** |
| `runtime/run_lifecycle.py` | 20 阶段 | 活跃（权威源） | **keep** |

## 维度 4: SkillOpt (4 路径)

| 路径 | 状态 | 判决 |
|------|------|------|
| `mcp/skillopt_tools.py` (V4 MCP) | @deprecated | **deprecate** |
| `skill_optimizer/` (V4 Engine) | 被 V5 handler 委托 | **keep** |
| `unified_tool_registry.py#_h_skillopt_*` (V5) | 活跃 MCP 工具 | **keep** |
| `self_improvement/` (V6) | 新闭环 | **keep** |

## 维度 5: 存储层 (3 互补)

| 文件 | 类型 | 判决 |
|------|------|------|
| `observation/run_store.py` | 内存事件存储 | **keep** (互补) |
| `observation/event_stream.py` | 异步事件广播 | **keep** (互补) |
| `observation/dashboard_sync.py` | WebSocket 桥接 | **keep** (互补) |

## 维度 6: Avatar 映射副本

| 位置 | 判决 |
|------|------|
| `tool_schemas.py` AVATAR_SCENE_MAP (13 状态) | **keep** (后端权威源) |
| `run_observer.js` 硬编码副本 | **merge** (提取为共享 JS 模块) |
| `dashboard_v3.js` 硬编码副本 | **merge** (同上) |

## 维度 7: 未使用文件

| 文件 | 判决 |
|------|------|
| `run_replay.py` | **delete_later** |
| `web/static/progress_bar.js` | **delete_later** |
| `web/static/decision_panel.js` | **delete_later** |
| `web/static/dashboard_run_client.js` | **delete_later** |
| `web/static/color_system_preview.html` | **delete_later** |

## V7.0 删除清单 (建议)

1. `stable_agent/mcp_server.py` + `mcp_tools.py` (V3)
2. `stable_agent/mcp/skillopt_tools.py` (V4)
3. `stable_agent/observation/progress_model.py`
4. `stable_agent/run_replay.py`
5. 5 个未使用 web/static/ 文件

## 推荐入口统一

- MCP: `/mcp`
- Observer: `/observe/{run_id}`
- Agent tool: `stableagent.task.os_agent`
- Skill output: `best_skill.md`
