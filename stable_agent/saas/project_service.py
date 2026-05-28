"""Project 业务逻辑。

管理 project 的创建、查询和基本操作。
"""

from __future__ import annotations

import logging
from typing import Any

from stable_agent.saas.models import Project, _new_id, _now

logger = logging.getLogger(__name__)


class ProjectService:
    """Project 业务逻辑层。

    Attributes:
        repository: SaasRepository 实例。
        billing_manager: BillingManager 实例（可选）。
    """

    def __init__(self, repository: Any = None, billing_manager: Any = None) -> None:
        self._repo = repository
        self._billing = billing_manager

    def create_project(
        self,
        workspace_id: str,
        name: str,
        description: str = "",
        environment: str = "local",
    ) -> Project:
        """创建新项目。

        Args:
            workspace_id: 所属工作空间 ID。
            name: 项目名称。
            description: 项目描述。
            environment: 运行环境。

        Returns:
            创建的 Project。

        Raises:
            PermissionError: 超过套餐项目数量限制时抛出。
        """
        # 检查配额
        if self._billing is not None:
            ok, reason = self._billing.check_project_limit(workspace_id)
            if not ok:
                raise PermissionError(reason)

        proj = Project(
            id=_new_id("proj"),
            workspace_id=workspace_id,
            name=name,
            description=description,
            environment=environment,
        )

        if self._repo is not None:
            self._repo.create_project(proj)

        logger.info("Created project %s in workspace %s", proj.name, workspace_id)
        return proj

    def get_project(self, project_id: str) -> Project | None:
        """获取项目。"""
        if self._repo is None:
            return None
        return self._repo.get_project(project_id)

    def list_projects(self, workspace_id: str) -> list[Project]:
        """列出工作空间下的所有项目。"""
        if self._repo is None:
            return []
        return self._repo.list_projects(workspace_id)

    def get_or_create_default(self, workspace_id: str) -> Project:
        """获取或创建默认项目（local 模式 fallback）。

        Args:
            workspace_id: 工作空间 ID。

        Returns:
            Project 实例。
        """
        if self._repo is not None:
            projects = self._repo.list_projects(workspace_id)
            if projects:
                return projects[0]

        # 创建默认项目
        return self.create_project(
            workspace_id=workspace_id,
            name="Default Project",
            description="Auto-created default project for local development.",
            environment="local",
        )
