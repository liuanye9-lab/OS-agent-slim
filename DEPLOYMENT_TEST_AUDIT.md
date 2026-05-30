# DEPLOYMENT_TEST_AUDIT.md — 部署与测试审计报告

**审计日期**: 2026-05-30

---

## 1. 现有部署能力

| 项目 | 状态 | 说明 |
|------|------|------|
| deploy_local.sh | ❌ 不存在 | 需新建 |
| smoke_test.sh | ❌ 不存在 | 需新建 |
| integration_test.sh | ❌ 不存在 | 需新建 |
| integration_test.py | ❌ 不存在 | 需新建 |
| check_closed_loop.py | ❌ 不存在 | 需新建 |
| install.sh | ✅ 存在 | 基础安装脚本 |
| start_opencode.sh | ✅ 存在 | OpenCode 启动脚本 |
| Dockerfile | ✅ 存在 | Docker 构建 |
| docker-compose.yml | ✅ 存在 | Docker 编排 |
| vercel.json | ✅ 存在 | Vercel 部署配置 |
| pyproject.toml | ✅ 存在 | Python 项目配置 |
| requirements.txt | ✅ 存在 | 依赖清单 |

---

## 2. 测试现状

### 2.1 全量测试

```
pytest -q --ignore=tests/test_mcp_gateway.py
→ 1083 passed, 0 failures in 23.50s
```

### 2.2 测试文件完整度

关键模块测试覆盖：

| 模块 | 测试文件 | 状态 |
|------|----------|------|
| RunLifecycle | test_run_lifecycle.py | ✅ |
| TemporalMemoryRouter | test_temporal_memory_router.py | ✅ |
| TemporalMemoryBridge | test_temporal_memory_bridge.py | ✅ |
| ContextCompressionGuard | test_context_compression_guard.py | ✅ |
| ContextCompressionBudgetEnforcement | test_context_compression_budget_enforcement.py | ✅ |
| SelfImprovementProofLoop | test_self_improvement_proof_loop.py | ✅ |
| RegressionValidationRunner | test_regression_validation_runner.py | ✅ |
| ValidationReport | test_validation_report.py | ✅ |
| DecisionTraceBuilder | test_decision_trace_builder.py | ✅ |
| DecisionTrace | test_decision_trace.py | ✅ |
| ToolRouter Events | test_tool_router_events.py | ✅ |
| ToolTraceIntegration | test_tool_trace_integration.py | ✅ |
| MCP Dashboard Sync | test_mcp_dashboard_sync.py | ✅ |
| Dashboard Run Detail | test_dashboard_run_detail.py | ✅ |
| Dashboard Projection | test_dashboard_projection.py | ✅ |
| Dashboard SkillOpt Events | test_dashboard_skillopt_events.py | ✅ |
| AvatarSceneMapping | test_avatar_scene_mapping.py | ✅ |
| SkillValidationReview | test_skill_validation_review.py | ✅ |
| RegressionFromBadCase | test_regression_from_badcase.py | ✅ |
| ApprovalResume | test_approval_resume.py | ✅ |
| HighRiskApprovalBlock | test_high_risk_approval_block.py | ✅ |

### 2.3 缺失的测试

| 测试 | 优先级 | 说明 |
|------|--------|------|
| test_deploy_scripts.py | P1 | 部署脚本测试 |
| test_integration_test_script.py | P1 | 集成测试脚本测试 |
| test_dashboard_run_observer.py | P1 | Dashboard Observer 完整测试 |
| test_temporal_memory_bridge_integration.py | P2 | Bridge 端到端测试 |

---

## 3. 环境信息

| 项目 | 值 |
|------|-----|
| Python | 3.13.12 |
| pytest | 9.0.3 |
| Git branch | main |
| Git status | clean (nothing to commit) |
| Last commit | bd3c9da (V6.3+V7.0) |

---

## 4. 需要新建的自动化脚本

| 脚本 | 路径 | 用途 |
|------|------|------|
| deploy_local.sh | scripts/deploy_local.sh | 一键部署：创建 venv、安装依赖、初始化目录、启动 uvicorn |
| smoke_test.sh | scripts/smoke_test.sh | 冒烟测试：检测 /api/health, /mcp tools/list, /runs |
| integration_test.sh | scripts/integration_test.sh | 集成测试：调用 os_agent, 检查 events, 检查 observer |
| integration_test.py | tools/integration_test.py | Python 集成测试脚本 |
| check_closed_loop.py | tools/check_closed_loop.py | 闭环结构检查 |

---

## 5. 依赖清单

从 requirements.txt 和代码分析：

核心依赖：
- fastapi + uvicorn（Web 服务）
- pydantic（数据模型）
- pytest + httpx（测试）
- websockets（WebSocket）
- python-dotenv（环境变量）
- tiktoken（Token 估算，可选）

SaaS 依赖：
- 飞书 SDK（通知）

---

## 6. 风险与建议

| 风险 | 建议 |
|------|------|
| 无自动化部署 | Phase 8 创建 deploy_local.sh |
| 无冒烟测试 | Phase 8 创建 smoke_test.sh |
| 无集成测试 | Phase 8 创建 integration_test.sh/check_closed_loop.py |
| test_mcp_gateway.py 可能挂起 | 已在 pytest 命令中忽略 |
| .venv 可能过期 | deploy_local.sh 需重建 venv |

---

## 7. 判定

✅ **测试覆盖充分**（1083 passed），但缺少自动化部署和集成测试脚本。Phase 8 需要新建 5 个脚本。
