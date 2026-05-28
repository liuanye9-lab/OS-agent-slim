"""SaaS 数据模型。

定义 Workspace、Project、AgentRun、TraceEvent、EvalResult、
BadCase、RegressionCase、Skill、HumanReview、ApiKey、UsageEvent
等16个核心实体的 dataclass。

约定：
- 所有实体必须有 id 和 created_at
- 归属实体必须有 workspace_id 和 project_id（如适用）
- 使用 uuid 生成 id（hex 格式，带前缀便于识别）
- 所有时间戳使用 time.time() float 格式（与现有 models.py 一致）
"""

from __future__ import annotations

import time
import uuid as _uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


# ============================================================================
# 枚举定义
# ============================================================================


class SaasMode(StrEnum):
    """SaaS 运行模式。"""

    LOCAL = "local"  # 本地开发模式，project_id 可选
    SAAS = "saas"  # SaaS 模式，project_id 强制校验


class MemberRole(StrEnum):
    """工作空间成员角色。"""

    OWNER = "owner"
    ADMIN = "admin"
    DEVELOPER = "developer"
    REVIEWER = "reviewer"
    VIEWER = "viewer"


class BillingTier(StrEnum):
    """计费套餐层级。"""

    FREE = "free"
    PRO = "pro"
    TEAM = "team"
    ENTERPRISE = "enterprise"


class RunStatus(StrEnum):
    """Agent 运行状态。"""

    CREATED = "created"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    EVALUATING = "evaluating"
    LEARNING = "learning"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RegressionStatus(StrEnum):
    """回归用例状态。"""

    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class PatchStatus(StrEnum):
    """Skill Patch 状态。"""

    CANDIDATE = "candidate"
    VALIDATING = "validating"
    VALIDATION_PASSED = "validation_passed"
    VALIDATION_FAILED = "validation_failed"
    WAITING_REVIEW = "waiting_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPORTED = "exported"


class AuditEventType(StrEnum):
    """审计事件类型。"""

    API_KEY_CREATED = "api_key_created"
    API_KEY_REVOKED = "api_key_revoked"
    MCP_TOOL_CALLED = "mcp_tool_called"
    HIGH_RISK_TOOL_BLOCKED = "high_risk_tool_blocked"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_APPROVED = "approval_approved"
    APPROVAL_REJECTED = "approval_rejected"
    SKILL_PATCH_CREATED = "skill_patch_created"
    SKILL_PATCH_VALIDATED = "skill_patch_validated"
    SKILL_PATCH_REVIEWED = "skill_patch_reviewed"
    BEST_SKILL_EXPORTED = "best_skill_exported"
    PROJECT_DELETED = "project_deleted"
    MEMBER_INVITED = "member_invited"


class ReviewStatus(StrEnum):
    """审核状态。"""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class UsageEventType(StrEnum):
    """用量事件类型。"""

    RUN_CREATED = "run_created"
    MCP_TOOL_CALLED = "mcp_tool_called"
    TRACE_EVENT_WRITTEN = "trace_event_written"
    EVAL_EXECUTED = "eval_executed"
    SKILL_VALIDATION_RUN = "skill_validation_run"
    SKILL_EXPORTED = "skill_exported"
    TOKEN_USED = "token_used"


# ============================================================================
# 工具函数
# ============================================================================


def _new_id(prefix: str) -> str:
    """生成带前缀的唯一 ID。"""
    return f"{prefix}_{_uuid.uuid4().hex[:12]}"


def _now() -> float:
    """当前 UTC 时间戳。"""
    return time.time()


# ============================================================================
# SaaS 数据模型 — 16个核心实体
# ============================================================================


@dataclass
class Workspace:
    """工作空间（团队空间）。

    多租户隔离的顶层容器。所有 Project、Run、Skill 等资源均归属
    于某个 Workspace。

    Attributes:
        id: 唯一标识，如 "ws_a1b2c3d4e5f6"。
        name: 工作空间名称。
        slug: URL 友好的短标识。
        owner_user_id: 创建者用户 ID。
        billing_plan: 计费套餐（free/pro/team/enterprise）。
        created_at: 创建时间戳。
        updated_at: 最后更新时间戳。
        settings: 工作空间设置（JSON字典）。
    """

    id: str = field(default_factory=lambda: _new_id("ws"))
    name: str = ""
    slug: str = ""
    owner_user_id: str = ""
    billing_plan: str = BillingTier.FREE.value
    created_at: float = field(default_factory=_now)
    updated_at: float = field(default_factory=_now)
    settings: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkspaceMember:
    """工作空间成员。

    Attributes:
        id: 唯一标识。
        workspace_id: 所属工作空间 ID。
        user_id: 用户标识。
        email: 成员邮箱。
        role: 成员角色（owner/admin/developer/reviewer/viewer）。
        joined_at: 加入时间戳。
        created_at: 创建时间戳。
        updated_at: 最后更新时间戳。
    """

    id: str = field(default_factory=lambda: _new_id("wm"))
    workspace_id: str = ""
    user_id: str = ""
    email: str = ""
    role: str = MemberRole.DEVELOPER.value
    joined_at: float = field(default_factory=_now)
    created_at: float = field(default_factory=_now)
    updated_at: float = field(default_factory=_now)


@dataclass
class Project:
    """项目。

    工作空间下的次级容器，所有 Run 归属于 Project。

    说明：Project 必须有 workspace_id，因为它是 workspace 的子资源。
    Project 自身没有 project_id（它是 project 层级的顶层）。

    Attributes:
        id: 唯一标识，如 "proj_a1b2c3d4e5f6"。
        workspace_id: 所属工作空间 ID。
        name: 项目名称。
        description: 项目描述。
        default_agent_id: 默认 Agent ID。
        environment: 运行环境（local/dev/staging/prod）。
        created_at: 创建时间戳。
        updated_at: 最后更新时间戳。
    """

    id: str = field(default_factory=lambda: _new_id("proj"))
    workspace_id: str = ""
    name: str = ""
    description: str = ""
    default_agent_id: str = ""
    environment: str = "local"
    created_at: float = field(default_factory=_now)
    updated_at: float = field(default_factory=_now)


@dataclass
class AgentProfile:
    """Agent 配置档案。

    描述一个 AI Agent 的身份和配置。属于 workspace + project。

    Attributes:
        id: 唯一标识。
        workspace_id: 所属工作空间 ID。
        project_id: 所属项目 ID。
        name: Agent 名称。
        description: Agent 描述。
        agent_type: Agent 类型（如 "codex", "claude_code", "cursor"）。
        default_skill_id: 默认 Skill ID。
        default_model: 默认模型名称。
        mcp_endpoint: MCP 端点 URL。
        created_at: 创建时间戳。
        updated_at: 最后更新时间戳。
    """

    id: str = field(default_factory=lambda: _new_id("agent"))
    workspace_id: str = ""
    project_id: str = ""
    name: str = ""
    description: str = ""
    agent_type: str = "general"
    default_skill_id: str = ""
    default_model: str = ""
    mcp_endpoint: str = ""
    created_at: float = field(default_factory=_now)
    updated_at: float = field(default_factory=_now)


@dataclass
class AgentRun:
    """Agent 运行记录（SaaS 包装）。

    扩展原有 RunRecord 的归属信息。run_id 对应 RunRecord.run_id。

    Attributes:
        run_id: 运行唯一标识（对应 RunRecord.run_id）。
        workspace_id: 所属工作空间 ID。
        project_id: 所属项目 ID。
        agent_id: Agent 配置 ID。
        status: 运行状态（created/running/waiting_approval 等）。
        user_task: 用户任务描述。
        task_type: 任务类型。
        progress_pct: 进度百分比（0-100）。
        overall_score: 综合评分。
        intent_alignment_score: 意图对齐评分。
        token_used: 消耗 token 数。
        cost_estimate: 预估成本（美元）。
        learning_triggered: 是否触发了学习。
        skill_updated: 是否更新了 skill。
        dashboard_url: Dashboard URL。
        trace_url: Trace URL。
        failure_attribution: 失败归因（JSON 字典）。
        metadata: 附加元数据。
        started_at: 开始时间戳。
        ended_at: 结束时间戳。
        created_at: 创建时间戳。
        updated_at: 最后更新时间戳。
    """

    run_id: str = ""
    workspace_id: str = ""
    project_id: str = ""
    agent_id: str = ""
    status: str = RunStatus.CREATED.value
    user_task: str = ""
    task_type: str = "general_qa"
    progress_pct: int = 0
    overall_score: float | None = None
    intent_alignment_score: float | None = None
    token_used: int = 0
    cost_estimate: float = 0.0
    learning_triggered: bool = False
    skill_updated: bool = False
    dashboard_url: str = ""
    trace_url: str = ""
    failure_attribution: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    started_at: float = field(default_factory=_now)
    ended_at: float | None = None
    created_at: float = field(default_factory=_now)
    updated_at: float = field(default_factory=_now)


@dataclass
class TraceEventRecord:
    """追踪事件记录。

    记录一次运行中的关键事件，从原有 TraceEvent 扩展归属信息。

    Attributes:
        id: 唯一标识。
        run_id: 所属运行 ID。
        workspace_id: 所属工作空间 ID。
        project_id: 所属项目 ID。
        event_type: 事件类型。
        payload: 事件负载。
        plain_text: 人类可读文本。
        decision_trace: 决策追踪数据。
        timestamp: 事件时间戳。
    """

    id: str = field(default_factory=lambda: _new_id("te"))
    run_id: str = ""
    workspace_id: str = ""
    project_id: str = ""
    event_type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    plain_text: str = ""
    decision_trace: dict[str, Any] | None = None
    timestamp: float = field(default_factory=_now)


@dataclass
class EvalResultRecord:
    """评测结果记录。

    记录一次评测的完整结果，扩展归属信息。

    Attributes:
        id: 唯一标识。
        run_id: 所属运行 ID。
        workspace_id: 所属工作空间 ID。
        project_id: 所属项目 ID。
        scores: 各维度评分字典。
        overall_score: 综合评分。
        failure_attribution: 失败归因。
        created_at: 评测时间戳。
    """

    id: str = field(default_factory=lambda: _new_id("eval"))
    run_id: str = ""
    workspace_id: str = ""
    project_id: str = ""
    scores: dict[str, float] = field(default_factory=dict)
    overall_score: float = 0.0
    failure_attribution: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=_now)


@dataclass
class BadCaseRecord:
    """失败案例记录。

    记录一次评估不合格的案例，扩展归属信息。

    Attributes:
        id: 唯一标识。
        workspace_id: 所属工作空间 ID。
        project_id: 所属项目 ID。
        run_id: 来源运行 ID。
        task_type: 任务类型。
        input_context: 输入上下文。
        output: 模型输出。
        overall_score: 综合评分。
        failure_reason: 失败原因。
        tags: 标签列表。
        created_at: 创建时间戳。
    """

    id: str = field(default_factory=lambda: _new_id("bc"))
    workspace_id: str = ""
    project_id: str = ""
    run_id: str = ""
    task_type: str = ""
    input_context: str = ""
    output: str = ""
    overall_score: float = 0.0
    failure_reason: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=_now)


@dataclass
class RegressionCaseRecord:
    """回归用例记录。

    用于 Validation Gate 回归检测。可从 BadCase 自动生成。

    说明：RegressionCase 归属 workspace + project，
    因为回归用例是项目级别的质量保障资产。

    Attributes:
        id: 唯一标识。
        workspace_id: 所属工作空间 ID。
        project_id: 所属项目 ID。
        task_input: 输入任务描述。
        expected_behavior: 期望行为。
        failure_mode: 失败模式（如 "memory.retrieval"）。
        source_run_id: 来源运行 ID。
        source_bad_case_id: 来源 BadCase ID。
        tags: 标签列表。
        overall_score: 关联的原始评分。
        created_at: 创建时间戳。
    """

    id: str = field(default_factory=lambda: _new_id("reg"))
    workspace_id: str = ""
    project_id: str = ""
    task_input: str = ""
    expected_behavior: str = ""
    failure_mode: str = "unknown"
    source_run_id: str = ""
    source_bad_case_id: str = ""
    tags: list[str] = field(default_factory=list)
    overall_score: float = 0.0
    created_at: float = field(default_factory=_now)


@dataclass
class SkillRecord:
    """Skill 记录。

    记录一个 Skill 文档及其元信息。

    Attributes:
        id: 唯一标识。
        workspace_id: 所属工作空间 ID。
        project_id: 所属项目 ID。
        name: Skill 名称。
        current_version: 当前版本号。
        content: Skill 内容。
        score: 当前评分。
        created_at: 创建时间戳。
        updated_at: 最后更新时间戳。
    """

    id: str = field(default_factory=lambda: _new_id("skill"))
    workspace_id: str = ""
    project_id: str = ""
    name: str = ""
    current_version: str = "v1.0"
    content: str = ""
    score: float = 0.0
    created_at: float = field(default_factory=_now)
    updated_at: float = field(default_factory=_now)


@dataclass
class SkillVersionRecord:
    """Skill 版本记录。

    记录 Skill 的某个历史版本。

    Attributes:
        id: 唯一标识。
        skill_id: 所属 Skill ID。
        version: 版本号。
        content: 版本内容。
        score: 该版本评分。
        created_at: 创建时间戳。
    """

    id: str = field(default_factory=lambda: _new_id("sv"))
    skill_id: str = ""
    version: str = "v1.0"
    content: str = ""
    score: float = 0.0
    created_at: float = field(default_factory=_now)


@dataclass
class SkillPatchRecord:
    """Skill 补丁记录。

    记录一次 Skill 优化的候选补丁。

    Attributes:
        id: 唯一标识。
        skill_id: 目标 Skill ID。
        workspace_id: 所属工作空间 ID。
        project_id: 所属项目 ID。
        source_run_id: 来源运行 ID。
        from_version: 源版本。
        to_version: 目标版本。
        patch_type: 补丁类型（"prompt", "constraint", "workflow", "memory"）。
        patch_diff: 补丁差异内容。
        reason: 修改原因。
        old_score: 旧评分。
        new_score: 新评分（候选）。
        delta: 评分变化。
        status: 补丁状态（candidate/validating/validation_passed/...）。
        validation_run_id: 验证运行 ID。
        human_review_id: 人工审核 ID。
        proposed_by: 提议者（"system" 或用户名）。
        created_at: 创建时间戳。
        updated_at: 最后更新时间戳。
    """

    id: str = field(default_factory=lambda: _new_id("sp"))
    skill_id: str = ""
    workspace_id: str = ""
    project_id: str = ""
    source_run_id: str = ""
    from_version: str = ""
    to_version: str = ""
    patch_type: str = "prompt"
    patch_diff: str = ""
    reason: str = ""
    old_score: float = 0.0
    new_score: float = 0.0
    delta: float = 0.0
    status: str = PatchStatus.CANDIDATE.value
    validation_run_id: str = ""
    human_review_id: str = ""
    proposed_by: str = "system"
    created_at: float = field(default_factory=_now)
    updated_at: float = field(default_factory=_now)


@dataclass
class ValidationRunRecord:
    """验证运行记录。

    记录一次 Validation Gate 的执行结果。

    Attributes:
        id: 唯一标识。
        patch_id: 关联的 Skill Patch ID。
        baseline_score: 基线评分。
        candidate_score: 候选评分。
        score_delta: 评分差异。
        passed: 是否通过。
        regression_cases: 回归用例列表。
        explanation: 验证解释。
        created_at: 验证时间戳。
    """

    id: str = field(default_factory=lambda: _new_id("vr"))
    patch_id: str = ""
    baseline_score: float = 0.0
    candidate_score: float = 0.0
    score_delta: float = 0.0
    passed: bool = False
    regression_cases: list[str] = field(default_factory=list)
    explanation: str = ""
    created_at: float = field(default_factory=_now)


@dataclass
class HumanReviewRecord:
    """人工审核记录。

    记录一次人工审核的决定。

    说明：HumanReview 归属 workspace + project（因为审核是项目级别的操作）。
    但 target_type 可以是 "skill_patch" 等任何需要审核的对象。

    Attributes:
        id: 唯一标识。
        workspace_id: 所属工作空间 ID。
        project_id: 所属项目 ID。
        target_type: 审核目标类型（如 "skill_patch"）。
        target_id: 审核目标 ID。
        reviewer: 审核人标识。
        status: 审核状态（pending/approved/rejected）。
        comment: 审核意见。
        created_at: 创建时间戳。
        resolved_at: 解决时间戳。
    """

    id: str = field(default_factory=lambda: _new_id("hr"))
    workspace_id: str = ""
    project_id: str = ""
    target_type: str = ""
    target_id: str = ""
    reviewer: str = ""
    status: str = "pending"  # ReviewStatus.PENDING.value
    comment: str = ""
    created_at: float = field(default_factory=_now)
    resolved_at: float | None = None


@dataclass
class ApiKeyRecord:
    """API Key 记录。

    记录一个 API Key 的元信息。key_hash 存储 SHA256 哈希值。

    Attributes:
        id: 唯一标识。
        workspace_id: 所属工作空间 ID。
        project_id: 关联项目 ID（可选，None 表示 workspace 级别）。
        name: Key 名称。
        key_hash: API Key 的 SHA256 哈希。
        key_prefix: Key 前缀（如 "sk_"），便于识别。
        scopes: 权限范围列表（如 ["runs:write", "runs:read"]）。
        status: Key 状态（"active"/"revoked"）。
        last_used_at: 最后使用时间戳。
        created_at: 创建时间戳。
        revoked_at: 撤销时间戳（None 表示仍有效）。
    """

    id: str = field(default_factory=lambda: _new_id("ak"))
    workspace_id: str = ""
    project_id: str | None = None
    name: str = ""
    key_hash: str = ""
    key_prefix: str = "sk_"
    scopes: list[str] = field(default_factory=list)
    status: str = "active"
    last_used_at: float | None = None
    created_at: float = field(default_factory=_now)
    revoked_at: float | None = None


@dataclass
class UsageEventRecord:
    """用量事件记录。

    记录一次用量事件，为 billing 做准备。

    Attributes:
        id: 唯一标识。
        workspace_id: 所属工作空间 ID。
        project_id: 所属项目 ID。
        run_id: 关联的运行 ID（可选）。
        event_type: 事件类型。
        quantity: 数量。
        unit: 单位（"count", "token", "usd"）。
        tokens_used: 消耗 token 数。
        cost_estimate: 预估成本（美元）。
        metadata: 附加元数据。
        created_at: 时间戳。
    """

    id: str = field(default_factory=lambda: _new_id("ue"))
    workspace_id: str = ""
    project_id: str = ""
    run_id: str = ""
    event_type: str = ""
    quantity: float = 1.0
    unit: str = "count"
    tokens_used: int = 0
    cost_estimate: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=_now)


# ============================================================================
# SaaS 数据模型 — 本轮新增：Billing + Audit
# ============================================================================


@dataclass
class BillingPlanRecord:
    """计费套餐记录。

    描述一个 workspace 的计费计划和限制。

    说明：BillingPlan 归属 workspace（不需要 project_id，
    因为计费是 workspace 级别的）。

    Attributes:
        id: 唯一标识。
        workspace_id: 所属工作空间 ID。
        tier: 套餐层级（free/pro/team/enterprise）。
        max_projects: 最大项目数。
        max_runs_per_month: 每月最大运行次数。
        max_members: 最大成员数。
        trace_retention_days: Trace 保留天数。
        features: 启用的功能列表。
        is_active: 是否激活。
        created_at: 创建时间戳。
        updated_at: 最后更新时间戳。
    """

    id: str = field(default_factory=lambda: _new_id("bp"))
    workspace_id: str = ""
    tier: str = BillingTier.FREE.value
    max_projects: int = 1
    max_runs_per_month: int = 100
    max_members: int = 1
    trace_retention_days: int = 7
    features: list[str] = field(default_factory=list)
    is_active: bool = True
    created_at: float = field(default_factory=_now)
    updated_at: float = field(default_factory=_now)


@dataclass
class AuditLogRecord:
    """审计日志记录。

    记录所有高风险操作的不可变审计轨迹。

    说明：AuditLog 归属 workspace + project（可选，有些事件
    是 workspace 级别的，如 api_key_created）。

    Attributes:
        id: 唯一标识。
        workspace_id: 所属工作空间 ID。
        project_id: 关联项目 ID（可选）。
        event_type: 事件类型（api_key_created, mcp_tool_called 等）。
        actor: 执行者标识（用户 ID 或 "system"）。
        target: 操作目标（如 "skill_patch:sp_xxx"）。
        details: 事件详情（JSON 字典）。
        ip_address: 来源 IP（可选）。
        user_agent: User-Agent（可选）。
        severity: 严重级别（"info", "warning", "critical"）。
        created_at: 事件时间戳。
    """

    id: str = field(default_factory=lambda: _new_id("al"))
    workspace_id: str = ""
    project_id: str = ""
    event_type: str = ""
    actor: str = ""
    target: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    ip_address: str = ""
    user_agent: str = ""
    severity: str = "info"
    created_at: float = field(default_factory=_now)
