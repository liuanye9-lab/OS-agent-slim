"""权限校验模块。

根据 SaaS 模式决定 project_id 是否必填，并提供角色级权限矩阵。

local 模式：project_id 可选，fallback 到 default project
saas 模式：project_id 必填，且需验证 API Key

角色权限矩阵：
- owner: 全部权限
- admin: 管理项目和成员
- developer: 创建 run / 调试 / eval
- reviewer: 审批 skill patch
- viewer: 只读
"""

from __future__ import annotations

import logging
from typing import Any

from stable_agent.saas.models import MemberRole, SaasMode

logger = logging.getLogger(__name__)

# ============================================================================
# 角色权限矩阵
# ============================================================================

ROLE_PERMISSIONS: dict[str, set[str]] = {
    MemberRole.OWNER.value: {
        "workspace:manage", "project:create", "project:delete",
        "project:manage", "member:invite", "member:remove",
        "run:create", "run:view", "run:delete",
        "trace:view", "eval:run", "eval:view",
        "skill:view", "skill:patch", "skill:review",
        "skill:validate", "skill:export",
        "apikey:create", "apikey:revoke",
        "usage:view", "billing:manage",
        "audit:view",
    },
    MemberRole.ADMIN.value: {
        "project:create", "project:manage",
        "member:invite",
        "run:create", "run:view",
        "trace:view", "eval:run", "eval:view",
        "skill:view", "skill:patch", "skill:validate",
        "apikey:create", "usage:view",
        "audit:view",
    },
    MemberRole.DEVELOPER.value: {
        "run:create", "run:view",
        "trace:view", "eval:run", "eval:view",
        "skill:view", "skill:patch",
        "usage:view",
    },
    MemberRole.REVIEWER.value: {
        "run:view", "trace:view", "eval:view",
        "skill:view", "skill:review",
        "skill:validate",
        "usage:view",
    },
    MemberRole.VIEWER.value: {
        "run:view", "trace:view",
        "skill:view", "usage:view",
    },
}


class PermissionChecker:
    """权限校验器。

    根据 SaaS 运行模式决定权限校验策略。

    Attributes:
        mode: SaaS 运行模式。
        default_project_id: local 模式下的 fallback project_id。
        default_workspace_id: local 模式下的 fallback workspace_id。
    """

    def __init__(
        self,
        mode: str = "local",
        default_project_id: str = "",
        default_workspace_id: str = "",
    ) -> None:
        self.mode: str = mode
        self.default_project_id: str = default_project_id
        self.default_workspace_id: str = default_workspace_id

    # ------------------------------------------------------------------
    # project_id 校验
    # ------------------------------------------------------------------

    def resolve_project_context(
        self,
        project_id: str = "",
        workspace_id: str = "",
    ) -> dict[str, str]:
        """解析并校验 project context。

        Args:
            project_id: 项目 ID。
            workspace_id: 工作空间 ID。

        Returns:
            {"project_id": "...", "workspace_id": "...", "mode": "..."}

        Raises:
            PermissionError: SaaS 模式且 project_id 无效时抛出。
        """
        result: dict[str, str] = {"mode": self.mode}

        if self.mode == SaasMode.LOCAL:
            # local 模式：fallback 到 default
            result["project_id"] = project_id or self.default_project_id
            result["workspace_id"] = workspace_id or self.default_workspace_id
            return result

        # SaaS 模式：project_id 强校验
        if not project_id:
            raise PermissionError(
                "SaaS 模式下 project_id 为必填参数。"
                "请在 tools/call 请求中提供有效的 project_id。"
            )
        result["project_id"] = project_id
        result["workspace_id"] = workspace_id
        return result

    # ------------------------------------------------------------------
    # API Key 校验
    # ------------------------------------------------------------------

    def check_api_key(
        self,
        api_key: str | None = None,
        api_key_manager: Any = None,
    ) -> str:
        """校验 API Key 并返回对应的 workspace_id。"""
        if self.mode == SaasMode.LOCAL:
            return self.default_workspace_id

        if not api_key:
            raise PermissionError("SaaS 模式下需要 API Key。请在请求头中提供 X-API-Key。")

        if api_key_manager is None:
            raise PermissionError("API Key 管理器未初始化。")

        result = api_key_manager.validate_key(api_key)
        if result is None:
            raise PermissionError("API Key 无效或已撤销。")

        return result["workspace_id"]

    # ------------------------------------------------------------------
    # 角色权限方法
    # ------------------------------------------------------------------

    @staticmethod
    def get_permissions(role: str) -> set[str]:
        """获取角色的权限列表。"""
        return ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS[MemberRole.VIEWER.value])

    @staticmethod
    def has_permission(role: str, permission: str) -> bool:
        """检查角色是否拥有指定权限。"""
        return permission in PermissionChecker.get_permissions(role)

    @staticmethod
    def can_view_project(role: str) -> bool:
        """是否可以查看项目。"""
        return PermissionChecker.has_permission(role, "run:view")

    @staticmethod
    def can_create_run(role: str) -> bool:
        """是否可以创建运行。"""
        return PermissionChecker.has_permission(role, "run:create")

    @staticmethod
    def can_review_skill(role: str) -> bool:
        """是否可以审核 Skill。"""
        return PermissionChecker.has_permission(role, "skill:review")

    @staticmethod
    def can_export_skill(role: str) -> bool:
        """是否可以导出 Skill。"""
        return PermissionChecker.has_permission(role, "skill:export")

    @staticmethod
    def can_create_project(role: str) -> bool:
        """是否可以创建项目。"""
        return PermissionChecker.has_permission(role, "project:create")

    @staticmethod
    def can_view_audit(role: str) -> bool:
        """是否可以查看审计日志。"""
        return PermissionChecker.has_permission(role, "audit:view")

    # ------------------------------------------------------------------
    # 模式查询
    # ------------------------------------------------------------------

    def is_saas_mode(self) -> bool:
        """是否为 SaaS 模式。"""
        return self.mode == SaasMode.SAAS

    def is_local_mode(self) -> bool:
        """是否为 local 模式。"""
        return self.mode == SaasMode.LOCAL
