# PRODUCTION_CODE_AUDIT.md

> StableAgent Cloud 生产级代码审计报告
> 审计日期: 2026-05-29
> 审计范围: 全部核心模块 (gateway, saas, observation, web, runtime, approval, db, experiments)

## 审计总结

| 维度 | 状态 | 说明 |
|------|------|------|
| 核心功能 | ✅ 完整 | 28 个 MCP 工具, 44 个 API endpoint, 12 页面 SaaS Dashboard |
| 架构质量 | ✅ 良好 | web/server.py 已拆分, RunLifecycle 已实现, MCP Gateway V5 统一入口 |
| 审批阻断 | ✅ 已硬化 | high risk 工具硬阻断, ApprovalResume 闭环, PendingToolStore 持久化 |
| 显式错误 | ✅ 已硬化 | 18 处 return False → RepositoryError 异常, 异常层次完整 |
| 决策可解释 | ✅ 已集成 | DecisionTraceBuilder 接入 ToolRouter, Dashboard 事件含决策字段 |
| 迁移管理 | ✅ 已实现 | MigrationRunner + 3 个 migration SQL 文件 |
| 权限防护 | ✅ 已实现 | SecurityContext + get_current_user + require_role + local mode 放行 |
| 回归验证 | ✅ 已实现 | RegressionRunner + ValidationReport + new_score > old_score gate |
| 实验复现 | ✅ 已完成 | dataset.jsonl + run_experiment.py + results.json + report.md (demo 标注) |
| 测试覆盖 | ✅ 371 passed | 核心 + 新增 14 个测试文件, 1 error (Windows 文件锁) |

## 逐模块审计

### 1. Gateway 层 (stable_agent/gateway/)

| 文件 | 真实实现 | 吞异常 | 测试 | 备注 |
|------|----------|--------|------|------|
| mcp_gateway.py | ✅ 完整 | ❌ 已用 logger.debug | ✅ | V5 统一 MCP 入口 |
| tool_router.py | ✅ 完整 | ✅ 已修复 | ✅ | 高风险硬阻断 + DecisionTrace 集成 |
| response_adapter.py | ✅ 完整 | ✅ 无 | ✅ | Dashboard 字段完整透传 |
| unified_tool_registry.py | ✅ 完整 | ✅ 无 | ✅ | 28 tools handler |
| tool_schemas.py | ✅ 完整 | ✅ 无 | ✅ | 14 语义场景映射 |
| run_context.py | ✅ 完整 | ✅ 无 | ✅ | SaaS 字段内置 |

### 2. SaaS 层 (stable_agent/saas/)

| 文件 | 真实实现 | 吞异常 | 测试 | 备注 |
|------|----------|--------|------|------|
| models.py | ✅ 完整 (18 models) | ✅ 无 | ✅ | 所有实体含 ws_id/proj_id |
| repository.py | ✅ 已硬化 | ✅ 已修复 (18→0 False) | ✅ | 写操作抛 RepositoryError |
| errors.py | ✅ 完整 | ✅ 无 | ✅ | 7 种异常类型 |
| auth.py | ✅ 完整 | ✅ 无 | ✅ | JWT HMAC-SHA256 |
| api_keys.py | ✅ 完整 | ✅ 无 | ✅ | SHA256 hashed, sk_ prefix |
| permissions.py | ✅ 完整 | ✅ 无 | ✅ | 5 级角色 |
| security_context.py | ✅ 完整 | ✅ 无 | ✅ | local/saas 双模式 |
| regression_runner.py | ✅ 完整 | ✅ 无 | ✅ | 已集成 validation_report |
| validation_report.py | ✅ 新创建 | ✅ 无 | ✅ | 独立模块, new_score>old_score gate |
| skill_review_service.py | ✅ 完整 | ✅ 无 | ✅ | Validation + Human Review |

### 3. Observation 层 (stable_agent/observation/)

| 文件 | 真实实现 | 吞异常 | 测试 | 备注 |
|------|----------|--------|------|------|
| decision_trace.py | ✅ 完整 | ✅ 无 | ✅ | DecisionTrace + RunInsight |
| decision_trace_builder.py | ✅ 完整 | ✅ 无 | ✅ | 已集成到 ToolRouter |
| run_store.py | ✅ 完整 | ✅ 无 | ✅ | 内存 + SQLite |
| event_stream.py | ✅ 完整 | ✅ 无 | ✅ | Pub/sub |
| run_insight.py | ✅ 完整 | ✅ 无 | ✅ | 任务总结生成 |

### 4. Runtime (stable_agent/runtime/)

| 文件 | 真实实现 | 吞异常 | 测试 | 备注 |
|------|----------|--------|------|------|
| run_lifecycle.py | ✅ 完整 | ✅ 已修复 fallback | ✅ | 20 阶段 + 未知 fallback CREATED |

### 5. Approval (stable_agent/approval/)

| 文件 | 真实实现 | 吞异常 | 测试 | 备注 |
|------|----------|--------|------|------|
| pending_tool_store.py | ✅ 完整 | ✅ 无 | ✅ | 内存 + SQLite 双层 |
| approval_resume_service.py | ✅ 完整 | ✅ 无 | ✅ | approve/resume + reject |

### 6. Database (stable_agent/db/)

| 文件 | 真实实现 | 吞异常 | 测试 | 备注 |
|------|----------|--------|------|------|
| migration_runner.py | ✅ 完整 | ✅ 无 | ✅ | 3 个 migration SQL |

### 7. Web (web/)

| 文件 | 真实实现 | 吞异常 | 测试 | 备注 |
|------|----------|--------|------|------|
| server.py → app.py | ✅ 已拆分 | ✅ 无 | ✅ | 向后兼容 |
| routes/dashboard.py | ✅ 完整 | ✅ 无 | ✅ | 12 页面 |
| routes/auth.py | ✅ 完整 | ✅ 无 | ✅ | Register/Login |
| routes/workspaces.py | ✅ 完整 | ✅ 无 | ✅ | CRUD |
| routes/projects.py | ✅ 完整 | ✅ 无 | ✅ | CRUD |
| routes/runs.py | ✅ 完整 | ✅ 无 | ✅ | 含 SSE |
| routes/approvals.py | ✅ 完整 | ✅ 无 | ✅ | |
| routes/reviews.py | ✅ 完整 | ✅ 无 | ✅ | |
| routes/api.py | ✅ 完整 | ✅ 无 | ✅ | Usage/Audit/Skills/Keys |
| dependencies.py | ✅ 完整 | ✅ 无 | ✅ | 权限 Guard |

## 闭环完整性审计

### Task → Plan → Action → Observation → Trace → Eval → BadCase → Regression → Skill Patch → Validation Gate → Human Review → Export best_skill.md

| 环节 | 状态 | 实现文件 |
|------|------|----------|
| Task | ✅ | tool_schemas: stableagent.task.* |
| Plan | ✅ | run_lifecycle: PLANNING stage |
| Action | ✅ | tool_router: handler execution |
| Observation | ✅ | tool_router: observing stage |
| Trace | ✅ | decision_trace + run_store |
| Eval | ✅ | stableagent.eval.evaluate |
| BadCase | ✅ | stableagent.badcase.record |
| Regression | ✅ | regression_runner + validation_report |
| Skill Patch | ✅ | stableagent.skill.patch_propose |
| Validation Gate | ✅ | new_score > old_score check |
| Human Review | ✅ | skill_review_service |
| Export | ✅ | stableagent.skill.export_best (high risk, needs approval) |

## 安全审计

| 检查项 | 状态 |
|--------|------|
| high risk 工具硬阻断 | ✅ |
| approval approve 可恢复 | ✅ |
| approval reject 不执行 | ✅ |
| best_skill.md 不能绕过 Human Review | ✅ (high risk + approval gate) |
| 用户隐私不写入 skill | ✅ (规则约束) |
| saas mode API 权限 guard | ✅ |
| local mode 放行 | ✅ |
| API Key SHA256 哈希 | ✅ |
| JWT HMAC-SHA256 | ✅ |
| 审计日志不可变 | ✅ |

## 风险清单

| 风险 | 级别 | 说明 |
|------|------|------|
| SQLite 并发 | 中 | 当前单实例, 生产建议 PostgreSQL |
| Windows 文件锁 | 低 | 测试环境 teardown 偶尔失败 |
| 前端状态来源 | 低 | Dashboard V3 需确认完全来自后端事件 |
| 实验数据标注 | 低 | README 指标已标注 simulated demo |
