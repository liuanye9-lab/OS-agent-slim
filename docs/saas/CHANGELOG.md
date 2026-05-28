# CHANGELOG.md — StableAgent OS SaaS v1.0

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
