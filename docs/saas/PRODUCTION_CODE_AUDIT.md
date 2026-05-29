# Production Code Audit — StableAgent Cloud

**日期**: 2026-05-29 | **基线**: ce8bbf5 | **测试**: 949 passed, 6 skipped

---

## 1. 总体评估

| 维度 | 状态 | 评价 |
|------|------|------|
| MCP 入口收敛 | ✅ 生产级 | `/mcp` 主入口, `/mcp/legacy` 向后兼容 |
| ResponseAdapter | ✅ 生产级 | 11 关键字段透传 |
| 高风险阻断 | ⚠️ 半成品 | 阻断但无法 resume（缺 ApprovalResume） |
| Repository 错误 | ✅ 生产级 | 7 种显式错误类型 |
| RunLifecycle | ⚠️ 位置不对 | 在 gateway/ 而非 runtime/ |
| DecisionTrace | ⚠️ 浅接入 | builder 存在但 ToolRouter 未深度调用 |
| 权限 Guard | ⚠️ scaffold | security_context 存在但未接入 routes |
| 迁移系统 | ✅ 有 scaffold | migration_runner + 2 SQL |
| 测试覆盖 | ✅ 良好 | 949 测试含 E2E |
| 文档 | ✅ 良好 | CHANGELOG/ROADMAP/SECURITY/AUDIT |

**最大缺口**: **Approval Resume 闭环缺失** — 高风险工具被阻断后无法通过审批恢复执行。

---

## 2. 逐文件审计

### 2.1 web/server.py (892 行)

| 维度 | 评分 | 说明 |
|------|------|------|
| 真实实现 | ✅ | 全部真实路由 |
| 职责过重 | ⚠️ | 单文件含 44+ routes |
| 吞异常 | ⚠️ | 4 处 `except Exception: return error` 缺少 logger |
| 权限校验 | ❌ | 未接入 security_context |
| 闭环节点 | ✅ | 覆盖 SaaS CRUD + Auth + MCP |

**建议**: 拆分为 routes/ 模块化，接入 permissions guard。

### 2.2 stable_agent/gateway/tool_router.py

| 维度 | 评分 | 说明 |
|------|------|------|
| 真实实现 | ✅ | 完整 route() + 风险分级 |
| 高风险阻断 | ✅ | high risk → waiting_approval |
| Approval Resume | ❌ | 未实现 — 阻断后无恢复机制 |
| DecisionTrace 接入 | ⚠️ | 事件发布有字段，未深度调用 builder |
| 吞异常 | ✅ | 1 处 logger.warning |

**建议**: 接入 ApprovalResumeService + DecisionTraceBuilder。

### 2.3 stable_agent/saas/repository.py

| 维度 | 评分 | 说明 |
|------|------|------|
| 真实实现 | ✅ | 完整 SQLite CRUD |
| 显式错误 | ⚠️ | errors.py 定义了但 repository 未全部抛出 |
| 吞异常 | ⚠️ | `save_*` 方法仍大量 `return False` |
| 测试覆盖 | ✅ | 有 test_saas_e2e |

### 2.4 Approval 模块

| 维度 | 评分 | 说明 |
|------|------|------|
| 模块存在 | ❌ | 无 `stable_agent/approval/` 目录 |
| PendingToolStore | ❌ | 未实现 |
| ApprovalResumeService | ❌ | 未实现 |
| 工具恢复 | ❌ | 阻断后永久丢失 |

**这是本轮最关键的缺口。**

---

## 3. 闭环链路审计

```
Task ✅ → Plan ✅ → Action ✅ → Observation ✅ →
Trace ✅ → Eval ✅ → BadCase ✅ → Regression ✅ →
Skill Patch ✅ → Validation Gate ⚠️ → Human Review ✅ →
Export best_skill.md ✅ (但需审批放行)
```

| 节点 | 状态 | 缺口 |
|------|------|------|
| Task | ✅ | unified_tool_registry: task.os_agent |
| Plan | ✅ | orchestrator.process_task() |
| Action | ✅ | ToolRouter.route() |
| Observation | ✅ | EventStream.publish_sync() |
| Trace | ✅ | TraceEventRecord |
| Eval | ✅ | EvalResultRecord |
| BadCase | ✅ | BadCaseRecord |
| Regression | ✅ | RegressionCaseRecord |
| Skill Patch | ✅ | SkillPatchRecord |
| Validation Gate | ⚠️ | ValidationReport 存在但 runner 未接入 |
| Human Review | ✅ | HumanReviewRecord |
| Export | ✅ | skill.export_best (需审批) |
| **Approval Resume** | ❌ | **完全缺失** |

---

## 4. 优先级行动清单

| P | 任务 | 理由 |
|----|------|------|
| **P0** | Approval Resume 闭环 | 高风险阻断后无法恢复 = 功能残疾 |
| **P0** | fix 剩余 utcnow 弃用 | 23 warnings 中 1 个源头 |
| P1 | DecisionTraceBuilder 深度接入 | 增强 Dashboard 可解释性 |
| P1 | RunLifecycle 移至 runtime/ | 架构清晰化 |
| P1 | Repository 显式错误补齐 | save_* 方法抛异常 |
| P2 | web/server.py 拆分 | 代码组织 |
| P2 | Permission guard 接入 routes | 安全加固 |
| P2 | 补 10+ 专项测试 | 覆盖新增模块 |
