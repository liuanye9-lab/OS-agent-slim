# SAAS_ARCHITECTURE_AUDIT.md — StableAgent OS 仓库审计

> 审计时间：2026-05-28 | 版本：v5.6.0 → SaaS v1.0
> 仓库状态：clean（792 tests passed，无未提交变更）

## 1. 审计范围与方法

### 审计命令执行结果

```
git status      → clean，branch main，up to date with origin/main
find . -maxdepth 3 -type f → 167 files（不含 .git/__pycache__/.workbuddy/）
python --version → 3.13.12
pytest --version → 9.0.3
pytest -q        → 792 passed, 33 warnings, 3.92s
```

## 2. 当前已有模块（可复用）

### 2.1 核心架构层（✅ 完整，可复用）

| 模块 | 文件 | 状态 | 可复用到SaaS |
|------|------|------|-------------|
| 数据模型 | `stable_agent/models.py` (798行) | ✅ | 所有dataclass已支持扩展字段 |
| SQLite存储 | `stable_agent/storage.py` (918行) | ✅ | 7张表CRUD，可加SaaS表 |
| MCP Gateway V5 | `stable_agent/gateway/mcp_gateway.py` (157行) | ✅ | 统一入口，支持扩展 |
| UnifiedToolRegistry | `stable_agent/gateway/unified_tool_registry.py` | ✅ | 15+工具，可新增SaaS工具 |
| RunContext | `stable_agent/gateway/run_context.py` (82行) | ✅ | 已有run_id/trace_id/span_id |
| RunStore | `stable_agent/observation/run_store.py` | ✅ | 事件存储+回放 |
| EventStream | `stable_agent/observation/event_stream.py` | ✅ | SSE事件流 |
| ToolRouter | `stable_agent/gateway/tool_router.py` | ✅ | 安全检查+审批 |
| ResponseAdapter | `stable_agent/gateway/response_adapter.py` | ✅ | 统一返回格式 |
| JSONRPCHandler | `stable_agent/gateway/jsonrpc_handler.py` | ✅ | JSON-RPC 2.0标准 |

### 2.2 Skill优化体系（✅ 完整，可复用）

| 模块 | 文件 | 状态 | 可复用到SaaS |
|------|------|------|-------------|
| ValidationGate | `stable_agent/skill_optimizer/validation_gate.py` (411行) | ✅ | 评分对比+回归检查 |
| SkillExporter | `stable_agent/skill_optimizer/skill_exporter.py` (168行) | ✅ | 已含Human Review Gate |
| SkillDocumentStore | `stable_agent/skill_optimizer/skill_document_store.py` | ✅ | 版本管理 |
| PatchApplier/Merger/Ranker | `stable_agent/skill_optimizer/` | ✅ | 补丁管线 |
| RolloutCollector | `stable_agent/skill_optimizer/rollout_collector.py` | ✅ | 轨迹收集 |
| IntentSignalExtractor | `stable_agent/skill_optimizer/intent_signal_extractor.py` | ✅ | 意图信号 |

### 2.3 评测与BadCase体系（✅ 完整，可复用）

| 模块 | 文件 | 状态 | 可复用到SaaS |
|------|------|------|-------------|
| Evaluator | `stable_agent/eval_and_bad_case.py` (925行) | ✅ | 三层评测+drift检测 |
| BadCaseManager | `stable_agent/eval_and_bad_case.py` | ✅ | 转EvalCase/RegressionCase |
| EvalCase | `stable_agent/models.py` | ✅ | 数据模型完整 |
| BadCase | `stable_agent/models.py` | ✅ | V6已加id/tags/source_run_id |
| EvaluationResult | `stable_agent/models.py` | ✅ | V6已加failure_attribution |

### 2.4 可观测性体系（✅ 完整，可复用）

| 模块 | 文件 | 状态 | 可复用到SaaS |
|------|------|------|-------------|
| DecisionNarrator | `stable_agent/explanation/decision_narrator.py` | ✅ | 22事件类型 |
| DecisionTrace | `stable_agent/observation/decision_trace.py` | ✅ | 双语解释 |
| ProgressModel | `stable_agent/observation/progress_model.py` | ✅ | 11级进度 |
| RunInsight | `stable_agent/observation/run_insight.py` | ✅ | 运行洞察 |
| BilingualText | `stable_agent/explanation/bilingual_text.py` | ✅ | 双语支持 |

### 2.5 前端Dashboard（✅ 完整，可复用）

| 文件 | 状态 | 可复用到SaaS |
|------|------|-------------|
| `web/templates/dashboard_v3.html` | ✅ | iOS玻璃拟态UI，已有run_id路由 |
| `web/templates/dashboard_v2.html` | ✅ | 决策观察舱 |
| `web/static/liquid_glass.css` | ✅ | 玻璃拟态样式系统 |
| `web/static/dashboard_v3.js` | ✅ | Dashboard JS |
| `web/static/styles_v2.css` | ✅ | 全局样式 |
| `web/templates/connect.html` | ✅ | 接入页面 |
| `web/server.py` (450行) | ✅ | 路由齐全：/runs/{id}, /api/runs/{id}/* |

### 2.6 测试体系（✅ 完整）

| 测试文件 | 测试数 | 状态 |
|----------|--------|------|
| `tests/` | 792 passed | ✅ |
| 测试文件 | 48个 | ✅ |

### 2.7 已有文档（V6-Professional产出）

| 文件 | 状态 |
|------|------|
| `docs/v6-pro/RESEARCH_REPORT.md` | ✅ 已有 |
| `docs/v6-pro/ARCHITECTURE_AUDIT.md` | ✅ 已有 |
| `docs/v6-pro/IMPLEMENTATION_LOG.md` | ✅ 已有 |
| `docs/v6-pro/UPGRADE_PLAN.md` | ✅ 已有 |
| `docs/v6-pro/CHANGELOG.md` | ✅ 已有 |
| `docs/v6-pro/ROADMAP.md` | ✅ 已有 |
| `UPDATED_README.md` | ✅ 已有 |

## 3. 当前缺口（需新增/升级）

### 3.1 SaaS多租户数据模型（❌ 缺失）

当前：
- `RunRecord` 只有 `run_id`，无 workspace_id / project_id / agent_id
- `TraceSpan` 只有 `run_id`，无 project 归属
- `MemoryItem` 只有 `id`，无 workspace 归属
- `BadCase` 已有 `source_run_id`（V6新增）
- 存储层只有7张表，无 workspace/project/api_key/usage 表

需要：
- 新增 `Workspace` / `WorkspaceMember` / `Project` / `AgentProfile` 数据模型
- 升级 `RunRecord` 增加 `workspace_id` / `project_id` / `agent_id`
- 新增 `ApiKeyRecord` / `UsageEventRecord` / `SkillRecord` / `HumanReviewRecord`
- 新增对应数据库表

### 3.2 SaaS数据归属（❌ 缺失）

当前：
- RunContext 没有 workspace_id / project_id
- MCP tools/call 不支持 project_id 参数
- Dashboard 不支持按 project 筛选

需要：
- 升级 RunContext 增加 `workspace_id` / `project_id` / `agent_id`
- MCP 所有工具支持 `project_id`
- Dashboard 支持 Workspace/Project selector

### 3.3 Regression → Skill Patch 闭环（⚠️ 部分完成）

当前：
- `BadCaseManager.convert_to_regression_case()` ✅ V6已实现
- `BadCaseManager.convert_to_eval_case()` ✅ 已有
- `ValidationGate.validate()` ✅ 已有
- `SkillExporter.export()` ✅ 含 Human Review Gate
- 但缺少 `RegressionService` 独立服务层
- 缺少 `SkillReviewService` 服务层
- 缺少 `HumanReviewRecord` 数据持久化

需要：
- 新增 `stable_agent/saas/regression_service.py`
- 新增 `stable_agent/saas/skill_review_service.py`

### 3.4 Usage Counter（❌ 缺失）

- 无任何用量记录
- 无 billing scaffold
- 无 cost estimation 持久化

### 3.5 API Key 管理（❌ 缺失）

- 无 API Key 创建/撤销机制
- 无 API Key 校验中间件
- FastAPI 目前不要求认证

### 3.6 Dashboard SaaS化（⚠️ 部分完成）

当前 Dashboard V3：
- ✅ 按 run_id 查看
- ✅ 进度条 + 决策卡片 + 时间线
- ❌ 无 Workspace selector
- ❌ 无 Project selector
- ❌ 无 Agent selector
- ❌ 无 Runs 列表
- ❌ 无 Usage panel
- ❌ 无 Skill patch diff panel

需要：
- 新增 `web/templates/project_dashboard.html`（或升级现有dashboard）
- 新增 SaaS 相关 JS

### 3.7 MCP 工具缺口（⚠️ 部分完成）

当前工具（15+）：
- `stableagent.memory.*`、`stableagent.task.*` 等已有
- ❌ 无 `stableagent.project.*`
- ❌ 无 `stableagent.regression.create`
- ❌ 无 `stableagent.skill.review`
- ❌ 无 `stableagent.usage.get`

## 4. 哪些代码可复用（✅ 直接复用）

| 模块 | 复用理由 |
|------|---------|
| `stable_agent/models.py` | dataclass扩展性极好，加字段不破坏现有 |
| `stable_agent/storage.py` | SQLite足够SaaS MVP，加表即可 |
| `stable_agent/gateway/` | 所有Gateway组件可直接复用 |
| `stable_agent/skill_optimizer/` | ValidationGate和SkillExporter直接复用 |
| `stable_agent/eval_and_bad_case.py` | Evaluator+BadicCaseManager完整 |
| `stable_agent/observation/` | RunStore+EventStream+DecisionTrace全部复用 |
| `web/server.py` | 路由结构清晰，加路由即可 |
| `web/static/liquid_glass.css` | 视觉语言统一复用 |
| `web/templates/dashboard_v3.html` | 基础结构可升级 |

## 5. 哪些只是README声明（非真实实现）

核对结果：
- ✅ README中声称的792+测试 → 真实存在（pytest验证）
- ✅ README中声称的V5.6功能 → 代码和测试均已实现
- ✅ 决策可解释、双语字段、Dashboard V2/V3 → 均已实现
- ✅ EventStream.publish_sync() → 已在代码中使用
- ⚠️ README中的"一键安装" → install.sh存在但为 pip install 脚本
- ✅ `/connect` 页面 → 存在且可访问
- ✅ Codex/Claude skill文件 → `.codex/` 和 `.claude/` 目录存在

## 6. 哪些测试真实存在

- 792个测试全部通过，覆盖：
  - 数据模型 (models/v4/v5)
  - 存储层 (storage)
  - Gateway (mcp_gateway, tool_router, response_adapter, unified_tool_registry, tool_schemas)
  - Dashboard (sync, projection, skillopt_events)
  - Skill优化 (validation_gate, skill_document_store, skill_optimization_engine, patch_*)
  - 评测 (eval_dataset, intent_alignment_evaluator)
  - 审批 (approval_mcp_flow)
  - 安全 (security_policy)
  - 决策可解释 (decision_narrator, decision_trace, run_insight)
  - 无静默吞异常 (no_silent_exceptions)

## 7. 哪些功能需要先补齐（→ P0）

### P0（必须）：
1. SaaS 数据模型 scaffold
2. Project / Run / Trace 归属关系
3. MCP 支持 project_id
4. Dashboard 按 project 查看
5. Eval → Regression 闭环完善
6. Skill Review Service
7. Usage Counter
8. API Key scaffold
9. 新增测试覆盖
10. 文档产出

### P1（本轮可选）：
- Workspace管理UI
- API Key生成/撤销UI
- Usage面板
- billing scaffold

### P2（未来）：
- PostgreSQL迁移
- Stripe集成
- SSO/OAuth
- RBAC权限系统

## 8. 审计结论

**总评**：StableAgent OS v5.6.0 代码质量高，架构清晰，测试完备（792 passed），核心能力（评测、Skill优化、MCP Gateway、Dashboard）已完整实现。SaaS升级的核心工作在于 **多租户数据归属层** 和 **商业化管理功能** 的新增，而非对现有系统的重构。

**关键风险**：
- SQLite → 多租户：需要在现有7张表上扩展而不破坏现有功能
- 向后兼容：所有现有API和测试必须继续通过
- 权限隔离：local模式 vs SaaS模式的fallback逻辑

**建议策略**：增量扩展（不重构），优先在现有 models.py/storage.py/web/server.py 上扩展，新增 `stable_agent/saas/` 独立模块封装SaaS逻辑。
