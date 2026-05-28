# CHANGELOG.md — StableAgent OS SaaS

## v1.1.0-SaaS (2026-05-29)

### 新增
- `billing.py` — BillingManager（4级套餐 + 配额检查）
- `audit_log.py` — AuditLogger（13种事件 + 不可变日志）
- `workspace_service.py` — WorkspaceService（创建/查询/成员管理）
- `project_service.py` — ProjectService（创建/查询/default项目）
- `run_service.py` — RunService（Agent 运行生命周期管理）
- `BillingPlanRecord` + `AuditLogRecord` 数据模型
- `BillingTier`、`RunStatus`、`RegressionStatus`、`PatchStatus`、`AuditEventType` 枚举
- 完整5级角色权限矩阵（owner/admin/developer/reviewer/viewer）
- `SAAS_UPGRADE_PLAN.md` + `COMMERCIALIZATION_PLAN.md`

### 变更
- models.py: 扩展16个dataclass字段（+slug/billing_plan/scopes/environment 等）
- permissions.py: +角色级权限方法 + ROLE_PERMISSIONS 矩阵
- repository.py:
  - 新增 billing_plans/audit_logs 表
  - 扩展 runs/projects/skill_patches/workspaces 表
  - ALTER TABLE 列迁移（14个新列）
  - +save_billing_plan/get_billing_plan
  - +save_audit_log/list_audit_logs
  - +save_workspace_member/list_workspace_members
- skill_review_service.py: 状态值对齐 PatchStatus 枚举
- ApiKeyRecord: +scopes/project_id/last_used_at
- AgentRun: +10个新字段
- SkillPatchRecord: +12个新字段
- 修复 progress_pct 漏传 bug

### 测试
- +46 个新测试（test_saas_repository/test_permissions/test_audit_log/test_api_routes_saas）
- 全量: **918/918 passed**

## v1.0.0-SaaS (2026-05-28)

### 新增

#### SaaS 多租户数据模型
- 新增16个dataclass: Workspace, Project, AgentRun, TraceEventRecord, EvalResultRecord, BadCaseRecord, RegressionCaseRecord, SkillRecord, SkillVersionRecord, SkillPatchRecord, ValidationRunRecord, HumanReviewRecord, ApiKeyRecord, UsageEventRecord
- 新增13张SQLite表: workspaces, projects, agent_profiles, api_keys, usage_events, regression_cases, skill_records, skill_versions, skill_patches, validation_runs, human_reviews
- 扩展现有runs表: workspace_id, project_id, agent_id列

#### SaaS 服务层
- SaasRepository: 统一数据访问层（CRUD全部13张表）
- SaasService: 业务逻辑层（project管理、run归属、权限校验）
- UsageCounter: 用量计数器（7种事件类型、成本估算）
- PermissionChecker: 权限校验（local/saas双模式）
- ApiKeyManager: API Key管理（创建、校验、撤销、SHA256存储）

#### Eval → Regression → Skill Review 闭环
- RegressionService: BadCase→RegressionCase自动转换
- SkillReviewService: Submit→Validate→Review→Export完整流程
- Validation Gate硬约束: new_score > old_score 才通过
- Human Review Gate硬约束: 未审核不允许导出

#### RunContext 升级
- 新增 workspace_id, project_id, agent_id, mode 字段
- child_span() 自动继承SaaS字段

### 测试
- 新增79个测试（871 total，全部通过）
- 覆盖: models, workspace, project, run scope, usage, api_keys, mcp context, regression, skill validation/review, dashboard routes

### 文档
- 8个Markdown文档: AUDIT, PRD, ARCHITECTURE_PLAN, RESEARCH_REPORT, UPGRADE_PLAN, IMPLEMENTATION_LOG, CHANGELOG, ROADMAP

### 向后兼容
- 所有现有API不变
- local模式: project_id可选（fallback到default）
- 现有792个测试保持通过
- 无破坏性变更
