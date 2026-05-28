"""Billing 计费管理模块。

管理 workspace 的计费套餐和用量配额。

套餐设计：
- Free: 1 workspace, 1 project, 100 runs/month, 7天trace
- Pro: 3 projects, 2000 runs/month, 30天trace, skill validation
- Team: 多成员, 20000 runs/month, 90天trace, human review, API key
- Enterprise: 私有部署, SSO, 审计日志, 自定义保留

本轮只实现数据结构和用量限制检查，不接支付。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from stable_agent.saas.models import BillingPlanRecord, BillingTier

logger = logging.getLogger(__name__)

# ============================================================================
# 套餐默认配置
# ============================================================================

TIER_DEFAULTS: dict[str, dict[str, Any]] = {
    BillingTier.FREE.value: {
        "max_projects": 1,
        "max_runs_per_month": 100,
        "max_members": 1,
        "trace_retention_days": 7,
        "features": ["local_mcp", "basic_dashboard", "skill_library"],
    },
    BillingTier.PRO.value: {
        "max_projects": 3,
        "max_runs_per_month": 2000,
        "max_members": 5,
        "trace_retention_days": 30,
        "features": [
            "local_mcp", "basic_dashboard", "skill_library",
            "skill_validation", "export_report", "regression_suite",
        ],
    },
    BillingTier.TEAM.value: {
        "max_projects": 10,
        "max_runs_per_month": 20000,
        "max_members": 20,
        "trace_retention_days": 90,
        "features": [
            "local_mcp", "advanced_dashboard", "skill_library",
            "skill_validation", "export_report", "regression_suite",
            "human_review", "api_keys", "audit_log",
        ],
    },
    BillingTier.ENTERPRISE.value: {
        "max_projects": -1,  # 无限制
        "max_runs_per_month": -1,  # 无限制
        "max_members": -1,  # 无限制
        "trace_retention_days": 365,
        "features": [
            "local_mcp", "advanced_dashboard", "skill_library",
            "skill_validation", "export_report", "regression_suite",
            "human_review", "api_keys", "audit_log",
            "sso", "custom_retention", "private_deploy",
            "priority_support", "dedicated_security",
        ],
    },
}


# ============================================================================
# BillingManager
# ============================================================================


class BillingManager:
    """计费套餐管理器。

    管理 workspace 的计费计划，检查用量配额。

    Attributes:
        repository: SaasRepository 实例。
    """

    def __init__(self, repository: Any = None) -> None:
        self._repo = repository

    # ------------------------------------------------------------------
    # 套餐管理
    # ------------------------------------------------------------------

    def get_default_plan(self, tier: str = BillingTier.FREE.value) -> BillingPlanRecord:
        """获取指定套餐的默认配置。"""
        defaults = TIER_DEFAULTS.get(tier, TIER_DEFAULTS[BillingTier.FREE.value])
        return BillingPlanRecord(
            tier=tier,
            max_projects=defaults["max_projects"],
            max_runs_per_month=defaults["max_runs_per_month"],
            max_members=defaults["max_members"],
            trace_retention_days=defaults["trace_retention_days"],
            features=defaults["features"],
        )

    def get_plan_for_workspace(self, workspace_id: str) -> BillingPlanRecord:
        """获取 workspace 的当前计费套餐。"""
        if self._repo is None:
            return self.get_default_plan()
        try:
            result = self._repo.get_billing_plan(workspace_id)
            if result is None:
                return self.get_default_plan()
            return result
        except Exception as e:
            logger.warning("get_plan_for_workspace failed: %s", e)
            return self.get_default_plan()

    def save_plan(self, plan: BillingPlanRecord) -> bool:
        """保存计费套餐。"""
        if self._repo is None:
            return False
        try:
            return self._repo.save_billing_plan(plan)
        except Exception as e:
            logger.warning("save_plan failed: %s", e)
            return False

    # ------------------------------------------------------------------
    # 配额检查
    # ------------------------------------------------------------------

    def check_project_limit(self, workspace_id: str) -> tuple[bool, str]:
        """检查是否已超过项目数量限制。

        Returns:
            (是否通过, 原因描述)
        """
        plan = self.get_plan_for_workspace(workspace_id)
        if plan.max_projects < 0:  # 无限制
            return True, "无限制"

        if self._repo is None:
            return True, "local 模式无限制"

        try:
            projects = self._repo.list_projects(workspace_id)
            if len(projects) >= plan.max_projects:
                return False, (
                    f"已达到项目数量上限 ({plan.max_projects})。"
                    f"请升级套餐或删除不需要的项目。"
                )
            return True, ""
        except Exception as e:
            logger.warning("check_project_limit failed: %s", e)
            return True, ""  # 宽松策略

    def check_run_limit(self, workspace_id: str, current_month_count: int = 0) -> tuple[bool, str]:
        """检查是否已超过当月运行次数限制。

        Returns:
            (是否通过, 原因描述)
        """
        plan = self.get_plan_for_workspace(workspace_id)
        if plan.max_runs_per_month < 0:  # 无限制
            return True, "无限制"

        if current_month_count >= plan.max_runs_per_month:
            return False, (
                f"已达到当月运行次数上限 ({plan.max_runs_per_month})。"
                f"请升级套餐或等待下月重置。"
            )
        return True, ""

    def check_member_limit(self, workspace_id: str) -> tuple[bool, str]:
        """检查是否已超过成员数量限制。"""
        plan = self.get_plan_for_workspace(workspace_id)
        if plan.max_members < 0:
            return True, "无限制"

        if self._repo is None:
            return True, "local 模式无限制"

        try:
            members = self._repo.list_workspace_members(workspace_id)
            if len(members) >= plan.max_members:
                return False, (
                    f"已达到成员数量上限 ({plan.max_members})。"
                    f"请升级套餐或移除不需要的成员。"
                )
            return True, ""
        except Exception as e:
            logger.warning("check_member_limit failed: %s", e)
            return True, ""

    def check_feature(self, workspace_id: str, feature: str) -> bool:
        """检查 workspace 是否启用某功能。"""
        plan = self.get_plan_for_workspace(workspace_id)
        return feature in plan.features
