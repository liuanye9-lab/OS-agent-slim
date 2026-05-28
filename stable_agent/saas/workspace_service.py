"""Workspace 业务逻辑。

管理 workspace 的创建、查询和成员管理。
"""

from __future__ import annotations

import logging
from typing import Any

from stable_agent.saas.models import (
    BillingTier,
    Workspace,
    WorkspaceMember,
    _new_id,
    _now,
)

logger = logging.getLogger(__name__)


class WorkspaceService:
    """Workspace 业务逻辑层。

    Attributes:
        repository: SaasRepository 实例。
        billing_manager: BillingManager 实例。
    """

    def __init__(self, repository: Any = None, billing_manager: Any = None) -> None:
        self._repo = repository
        self._billing = billing_manager

    def create_workspace(
        self,
        name: str,
        owner_user_id: str = "",
        slug: str = "",
        tier: str = BillingTier.FREE.value,
    ) -> Workspace:
        """创建新的工作空间。

        Args:
            name: 工作空间名称。
            owner_user_id: 创建者用户 ID。
            slug: URL 友好标识（留空自动从 name 生成）。
            tier: 计费套餐。

        Returns:
            创建的 Workspace。
        """
        if not slug:
            slug = name.lower().replace(" ", "-").replace("_", "-")

        ws = Workspace(
            id=_new_id("ws"),
            name=name,
            slug=slug,
            owner_user_id=owner_user_id,
            billing_plan=tier,
            settings={},
        )

        if self._repo is not None:
            self._repo.create_workspace(ws)

        # 创建默认计费套餐
        if self._billing is not None:
            plan = self._billing.get_default_plan(tier)
            plan.id = _new_id("bp")
            plan.workspace_id = ws.id
            self._billing.save_plan(plan)

        logger.info("Created workspace %s (%s)", ws.name, ws.id)
        return ws

    def get_workspace(self, workspace_id: str) -> Workspace | None:
        """获取工作空间。"""
        if self._repo is None:
            return None
        return self._repo.get_workspace(workspace_id)

    def list_workspaces(self) -> list[Workspace]:
        """列出所有工作空间。"""
        if self._repo is None:
            return []
        return self._repo.list_workspaces()

    def add_member(
        self, workspace_id: str, user_id: str, email: str = "", role: str = "developer",
    ) -> WorkspaceMember:
        """添加成员到工作空间。"""
        member = WorkspaceMember(
            id=_new_id("wm"),
            workspace_id=workspace_id,
            user_id=user_id,
            email=email,
            role=role,
        )

        if self._repo is not None:
            self._repo.save_workspace_member(member)

        logger.info("Added member %s to workspace %s as %s", user_id, workspace_id, role)
        return member

    def list_members(self, workspace_id: str) -> list[WorkspaceMember]:
        """列出工作空间所有成员。"""
        if self._repo is None:
            return []
        return self._repo.list_workspace_members(workspace_id)
