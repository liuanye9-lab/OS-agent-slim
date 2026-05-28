"""StableAgent SaaS 模块。

提供多租户数据模型、权限校验、API Key 管理、用量计数、
回归用例管理和 Skill 审核服务。

模块结构：
- models.py: SaaS 数据模型 (dataclass)
- repository.py: 数据访问层 (SQLite)
- service.py: 业务逻辑层
- usage.py: 用量计数器
- permissions.py: 权限校验
- api_keys.py: API Key 管理
- regression_service.py: 回归用例服务
- skill_review_service.py: Skill 审核服务
"""

from stable_agent.saas.models import (
    Workspace,
    WorkspaceMember,
    Project,
    AgentProfile,
    AgentRun,
    TraceEventRecord,
    EvalResultRecord,
    BadCaseRecord,
    RegressionCaseRecord,
    SkillRecord,
    SkillVersionRecord,
    SkillPatchRecord,
    ValidationRunRecord,
    HumanReviewRecord,
    ApiKeyRecord,
    UsageEventRecord,
    SaasMode,
)
from stable_agent.saas.repository import SaasRepository
from stable_agent.saas.service import SaasService
from stable_agent.saas.usage import UsageCounter
from stable_agent.saas.permissions import PermissionChecker
from stable_agent.saas.api_keys import ApiKeyManager
from stable_agent.saas.regression_service import RegressionService
from stable_agent.saas.skill_review_service import SkillReviewService

__all__ = [
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
    "SaasMode",
    "SaasRepository",
    "SaasService",
    "UsageCounter",
    "PermissionChecker",
    "ApiKeyManager",
    "RegressionService",
    "SkillReviewService",
]
