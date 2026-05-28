"""StableAgent SaaS 模块。

提供多租户数据模型、权限校验、API Key 管理、用量计数、
回归用例管理、Skill 审核服务、审计日志和计费管理。

模块结构：
- models.py: SaaS 数据模型 (18 个 dataclass + 枚举)
- repository.py: 数据访问层 (SQLite)
- service.py: 业务逻辑层
- usage.py: 用量计数器
- permissions.py: 权限校验（含角色层级）
- api_keys.py: API Key 管理
- billing.py: 计费套餐管理
- audit_log.py: 审计日志服务
- regression_service.py: 回归用例服务
- skill_review_service.py: Skill 审核服务
- workspace_service.py: Workspace 业务逻辑
- project_service.py: Project 业务逻辑
- run_service.py: Run 业务逻辑
"""

from stable_agent.saas.models import (
    AgentProfile,
    AgentRun,
    ApiKeyRecord,
    AuditEventType,
    AuditLogRecord,
    BadCaseRecord,
    BillingPlanRecord,
    BillingTier,
    EvalResultRecord,
    HumanReviewRecord,
    MemberRole,
    PatchStatus,
    Project,
    RegressionCaseRecord,
    RegressionStatus,
    ReviewStatus,
    RunStatus,
    SaasMode,
    SkillPatchRecord,
    SkillRecord,
    SkillVersionRecord,
    TraceEventRecord,
    UsageEventRecord,
    UsageEventType,
    ValidationRunRecord,
    Workspace,
    WorkspaceMember,
)
from stable_agent.saas.repository import SaasRepository
from stable_agent.saas.service import SaasService
from stable_agent.saas.usage import UsageCounter
from stable_agent.saas.billing import BillingManager
from stable_agent.saas.audit_log import AuditLogger
from stable_agent.saas.permissions import PermissionChecker
from stable_agent.saas.api_keys import ApiKeyManager
from stable_agent.saas.regression_service import RegressionService
from stable_agent.saas.skill_review_service import SkillReviewService
from stable_agent.saas.workspace_service import WorkspaceService
from stable_agent.saas.project_service import ProjectService
from stable_agent.saas.run_service import RunService

__all__ = [
    # Models
    "Workspace",
    "WorkspaceMember",
    "Project",
    "AgentProfile",
    "AgentRun",
    "TraceEventRecord",
    "EvalResultRecord",
    "BadCaseRecord",
    "RegressionCaseRecord",
    "SkillRecord",
    "SkillVersionRecord",
    "SkillPatchRecord",
    "ValidationRunRecord",
    "HumanReviewRecord",
    "ApiKeyRecord",
    "UsageEventRecord",
    "BillingPlanRecord",
    "AuditLogRecord",
    # Enums
    "SaasMode",
    "MemberRole",
    "BillingTier",
    "RunStatus",
    "RegressionStatus",
    "PatchStatus",
    "ReviewStatus",
    "UsageEventType",
    "AuditEventType",
    # Services
    "SaasRepository",
    "SaasService",
    "UsageCounter",
    "BillingManager",
    "AuditLogger",
    "PermissionChecker",
    "ApiKeyManager",
    "RegressionService",
    "SkillReviewService",
    "WorkspaceService",
    "ProjectService",
    "RunService",
]
