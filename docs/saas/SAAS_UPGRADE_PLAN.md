# SAAS_UPGRADE_PLAN.md

## 1. 本轮目标

将 StableAgent OS 从本地原型升级为具备商业化基础的 AgentOps + SkillOps SaaS 架构（local-first SaaS-ready）。

## 2. 不做什么

- 不替换整个技术栈（保持 FastAPI + SQLite + dataclass）
- 不强制 PostgreSQL、Redis、Stripe
- 不全面重写项目
- 不做完整 UI 改版
- 不自动覆盖 best_skill.md
- 不把用户隐私写入 skill

## 3. 当前架构差距

| 维度 | 当前状态 | 目标状态 |
|------|----------|----------|
| 数据归属 | 无 workspace/project | 全链路 workspace_id + project_id |
| 数据模型 | 16个基础dataclass | 18个dataclass + BillingPlan + AuditLog |
| 权限 | 仅 local/saas 双模式 | 完整5级角色矩阵 |
| API Key | 基础 SHA256 | +scopes + last_used_at + project_id |
| 用量 | UsageEvent 记录 | +BillingMeter + 配额检查 |
| 审计 | 无 | AuditLogger + 不可变日志 |
| Billing | 无 | BillingManager + 4级套餐 |
| 服务层 | - | Workspace/Project/Run service |

## 4. P0 修改清单

- [x] models.py: +BillingPlanRecord, +AuditLogRecord, 扩展16个模型字段
- [x] repository.py: +billing_plans/audit_logs 表, +save/list CRUD
- [x] permissions.py: +角色权限矩阵(owner/admin/developer/reviewer/viewer)
- [x] billing.py: +BillingManager(套餐定义+配额检查)
- [x] audit_log.py: +AuditLogger(13种事件+便捷方法)
- [x] workspace_service.py: +Workspace 创建/查询/成员管理
- [x] project_service.py: +Project 创建/查询/default项目
- [x] run_service.py: +Run 生命周期管理
- [x] RunContext: +workspace_id/project_id/agent_id/mode
- [x] SkillPatchRecord: 状态机对齐 PatchStatus 枚举
- [x] ApiKeyRecord: +scopes/project_id/last_used_at

## 5. P1 修改清单

- [ ] Dashboard SaaS 化: Workspace/Project selector + Run详情
- [ ] API Routes: RESTful SaaS API
- [ ] MCP Gateway SaaS 化: project_id 强校验
- [ ] Billing 配额检查集成到 run/project 创建
- [ ] Usage 可视化面板

## 6. 文件级修改计划

### 修改 (4个)
```
stable_agent/saas/models.py        (+70行: 新枚举+扩展字段+2新dataclass)
stable_agent/saas/repository.py    (+150行: 新表+CRUD+列迁移)
stable_agent/saas/permissions.py   (+80行: 角色矩阵)
stable_agent/saas/skill_review_service.py (状态名对齐)
```

### 新增 (7个)
```
stable_agent/saas/billing.py           (BillingManager)
stable_agent/saas/audit_log.py         (AuditLogger)
stable_agent/saas/workspace_service.py (WorkspaceService)
stable_agent/saas/project_service.py   (ProjectService)
stable_agent/saas/run_service.py       (RunService)
docs/saas/SAAS_UPGRADE_PLAN.md
docs/saas/COMMERCIALIZATION_PLAN.md
```

### 新增测试 (4个)
```
tests/test_saas_repository.py    (13 tests)
tests/test_permissions.py        (14 tests)
tests/test_audit_log.py          (10 tests)
tests/test_api_routes_saas.py    (9 tests)
```

## 7. 数据迁移策略

- 使用 ALTER TABLE ADD COLUMN（SQLite 幂等操作）
- 新列均有 DEFAULT 值，旧数据自动兼容
- 不执行破坏性 DDL
- init_db() 幂等可重复调用

## 8. 测试计划

- 原有测试：871个（零破坏）
- 新增测试：46个
- 总测试数：917个
- 覆盖率：models/repository/permissions/billing/audit/services 全覆盖

## 9. 风险控制

| 风险 | 缓解措施 |
|------|----------|
| ALTER TABLE 失败 | try/except 幂等处理 |
| 字段名变更破坏现有代码 | 向后兼容（patch_content→patch_diff 双字段） |
| 新服务未集成到主流程 | 独立模块，渐进集成 |

## 10. 回滚方案

- 所有修改均在 `stable_agent/saas/` 内部
- 不影响 `stable_agent/` 其他模块
- 如需回滚：git revert 即可

## 11. 进度百分比

```
[██████████] 100%
```
