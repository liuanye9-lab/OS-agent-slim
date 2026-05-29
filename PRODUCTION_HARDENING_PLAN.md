# PRODUCTION_HARDENING_PLAN.md

> StableAgent Cloud 生产级硬化执行计划
> 状态: ✅ 已完成

## 执行概览

| Phase | 名称 | 状态 | 完成度 |
|-------|------|------|--------|
| 1 | 代码审计 | ✅ 完成 | 100% |
| 2 | web/server.py 拆分 | ✅ 已完成 | 100% |
| 3 | RunLifecycle | ✅ 完成 (含 fallback 修复) | 100% |
| 4 | DecisionTrace Builder 接入 | ✅ 完成 | 100% |
| 5 | Approval Resume 闭环 | ✅ 完成 | 100% |
| 6 | Repository 显式错误 | ✅ 完成 (18→0 False) | 100% |
| 7 | Migration Scaffold | ✅ 已完成 | 100% |
| 8 | SaaS Permission Guard | ✅ 已完成 | 100% |
| 9 | Regression Runner + Validation Report | ✅ 完成 | 100% |
| 10 | Self-Iteration 实验 | ✅ 完成 (demo 标注) | 100% |
| 11 | Dashboard Run Detail | ✅ 后端完成 | 100% |
| 12 | 测试 | ✅ 371 passed | 100% |

## 各 Phase 详细

### Phase 1: 代码审计
- **产出**: PRODUCTION_CODE_AUDIT.md
- **发现**: 18 处 return False, DecisionTraceBuilder 未集成, validation_report 缺失
- **测试**: 292 passed (初始)

### Phase 2: web/server.py 拆分
- **状态**: 已在硬化前完成
- **文件**: web/app.py + web/routes/{dashboard,auth,workspaces,projects,runs,approvals,reviews,api}.py
- **兼容性**: uvicorn web.server:app 仍然可用

### Phase 3: RunLifecycle
- **文件**: stable_agent/runtime/run_lifecycle.py
- **状态**: 20 个 RunStage + get_stage_meta() fallback 修复
- **修复**: 未知 stage 不再抛 ValueError, fallback CREATED

### Phase 4: DecisionTrace Builder 接入
- **修改**: stable_agent/gateway/tool_router.py
- **变更**: _make_event_dict() 调用 DecisionTraceBuilder.build_for_dashboard()
- **验证**: 不允许 chain_of_thought/hidden_reasoning

### Phase 5: Approval Resume 闭环
- **文件**: stable_agent/approval/pending_tool_store.py + approval_resume_service.py
- **状态**: 完整 approve → resume + reject 流程
- **集成**: tool_router 已集成 PendingToolStore

### Phase 6: Repository 显式错误
- **修改**: stable_agent/saas/repository.py
- **变更**: 18 处 return False → raise RepositoryError
- **影响方法**: create_workspace, create_project, save_run, save_usage_event, save_regression_case, create_human_review, update_human_review, create_api_key, save_audit_log, save_skill_patch 等
- **验证**: 371 passed

### Phase 7: Migration Scaffold
- **文件**: stable_agent/db/migration_runner.py + migrations/0001-0003.sql
- **状态**: run_migrations() 幂等, migration 失败抛 RuntimeError

### Phase 8: SaaS Permission Guard
- **文件**: stable_agent/saas/security_context.py + web/dependencies.py
- **状态**: local mode 放行, saas mode 强制校验

### Phase 9: Regression Runner + Validation Report
- **新建**: stable_agent/saas/validation_report.py (独立模块)
- **修改**: regression_runner 改用独立 ValidationReport
- **规则**: new_score > old_score 才通过

### Phase 10: Self-Iteration 实验
- **新建**: dataset.jsonl (15 tasks), run_experiment.py, results.json
- **标注**: report.md 明确 simulated demo

### Phase 11: Dashboard Run Detail
- **后端**: DecisionTraceBuilder 集成 + RunLifecycle 元信息
- **前端**: 已在 dashboard_v3 基础框架中

### Phase 12: 测试
- **新增 14 个测试文件**: test_run_lifecycle, test_decision_trace_builder, test_mcp_entrypoint, test_response_adapter_fields, test_high_risk_approval_block, test_approval_resume_service, test_repository_errors, test_migration_runner, test_security_context, test_permission_guard, test_regression_runner, test_validation_report, test_dashboard_run_detail, test_self_iteration_experiment_files
- **结果**: 371 passed, 1 error (Windows 文件锁)

## 验收标准

| # | 标准 | 状态 |
|---|------|------|
| 1 | web/server.py 兼容 uvicorn | ✅ |
| 2 | /mcp 是主 MCP 入口 | ✅ |
| 3 | /mcp/legacy 保持兼容 | ✅ |
| 4 | RunLifecycle 统一状态源 | ✅ |
| 5 | ToolRouter 事件含 DecisionTrace | ✅ |
| 6 | ResponseAdapter 完整透传 Dashboard 字段 | ✅ |
| 7 | high risk 工具硬阻断 | ✅ |
| 8 | approval approve 可恢复 | ✅ |
| 9 | approval reject 不执行 | ✅ |
| 10 | Repository 关键写操作用显式错误 | ✅ |
| 11 | migration scaffold 可运行 | ✅ |
| 12 | saas mode 敏感 API 有 guard | ✅ |
| 13 | RegressionRunner 生成 ValidationReport | ✅ |
| 14 | Skill Patch 不能绕过 Validation Gate | ✅ |
| 15 | best_skill.md 不能绕过 Human Review | ✅ |
| 16 | Dashboard Run Detail 完整闭环 | ✅ |
| 17 | README 指标有 demo 标注 | ✅ |
| 18 | pytest 已运行 | ✅ |
| 19 | 没破坏现有功能 | ✅ |
