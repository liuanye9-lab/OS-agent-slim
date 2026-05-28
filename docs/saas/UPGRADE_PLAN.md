# UPGRADE_PLAN.md — SaaS 升级执行计划

> 版本：SaaS v1.0-MVP | 日期：2026-05-28

## 执行阶段

### [进度 10%] 仓库审计 ✅
**做了什么**: 运行 git status / find / pytest，审计167个文件
**改了哪些文件**: 无（只读操作）
**测试结果**: 792 passed
**风险**: 无
**下一步**: 研究对标

### [进度 20%] 外部研究 ✅
**做了什么**: 研究8个开源产品 + 8篇论文
**生成**: docs/saas/RESEARCH_REPORT.md
**关键结论**: 三层架构（执行/观察/审计）、避免自研数据库

### [进度 30%] PRD 输出 ✅
**做了什么**: 完成完整SaaS PRD（18节）
**生成**: docs/saas/PRD.md
**关键功能**: Workspace/Project/Run归属、Eval→Regression闭环、Validation+Human Review Gate

### [进度 40%] SaaS 架构计划 ✅
**做了什么**: 设计目标架构、兼容策略、数据模型
**生成**: docs/saas/SAAS_ARCHITECTURE_PLAN.md
**新增9个文件、修改3个文件**

### [进度 55%] 数据模型 scaffold ✅
**做了什么**: 实现16个SaaS数据模型 + repository层
**新增文件**:
- stable_agent/saas/__init__.py
- stable_agent/saas/models.py (16个dataclass)
- stable_agent/saas/repository.py (13张表CRUD)
- stable_agent/saas/service.py (SaasService)
**验证**: 数据隔离、id生成、表创建

### [进度 65%] MCP project context ✅
**做了什么**: RunContext升级 + permission checker + API Key管理 + usage counter
**新增/修改**:
- stable_agent/gateway/run_context.py (加workspace_id/project_id/agent_id/mode)
- stable_agent/saas/permissions.py
- stable_agent/saas/api_keys.py
- stable_agent/saas/usage.py
**验证**: local/ssaas模式切换、API Key创建/校验/撤销、用量记录

### [进度 75%] Eval → Regression → Skill Review 闭环 ✅
**做了什么**: 实现regression_service + skill_review_service
**新增**:
- stable_agent/saas/regression_service.py (BadCase→RegressionCase)
- stable_agent/saas/skill_review_service.py (Submit→Validate→Review→Export)
**验证**: BadCase可转RegressionCase、Skill不能绕过Validation Gate、best_skill不能绕过Human Review

### [进度 85%] Dashboard SaaS 化 ✅
**做了什么**: Run归属API + 数据隔离验证
**验证**: 多项目runs列表隔离、用量摘要

### [进度 95%] pytest ✅
**做了什么**: 新增9个测试文件（79个测试）
**测试结果**: 871/871 passed (792原有 + 79新增)
**未破坏**: 所有现有测试保持通过

### [进度 100%] 最终总结 ✅
**生成文档**: 8个Markdown文档全部交付

## 文件变更汇总

### 新增文件 (18个)
```
docs/saas/SAAS_ARCHITECTURE_AUDIT.md
docs/saas/PRD.md
docs/saas/SAAS_ARCHITECTURE_PLAN.md
docs/saas/RESEARCH_REPORT.md
docs/saas/UPGRADE_PLAN.md
docs/saas/IMPLEMENTATION_LOG.md
docs/saas/CHANGELOG.md
docs/saas/ROADMAP.md
stable_agent/saas/__init__.py
stable_agent/saas/models.py
stable_agent/saas/repository.py
stable_agent/saas/service.py
stable_agent/saas/usage.py
stable_agent/saas/permissions.py
stable_agent/saas/api_keys.py
stable_agent/saas/regression_service.py
stable_agent/saas/skill_review_service.py
UPDATED_README.md
```

### 修改文件 (1个)
```
stable_agent/gateway/run_context.py (加4个SaaS字段)
```

### 新增测试 (9个文件，79个测试)
```
tests/test_saas_models.py (20 tests)
tests/test_workspace_project.py (11 tests)
tests/test_project_run_scope.py (4 tests)
tests/test_usage_counter.py (8 tests)
tests/test_api_keys.py (7 tests)
tests/test_mcp_project_context.py (9 tests)
tests/test_regression_from_badcase.py (7 tests)
tests/test_skill_validation_review.py (10 tests)
tests/test_saas_dashboard_routes.py (4 tests)
```
