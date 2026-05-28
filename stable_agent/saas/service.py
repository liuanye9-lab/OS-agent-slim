"""SaaS 业务逻辑层。

封装跨实体操作，如：
- 创建 workspace + default project
- 为 run 关联 project
- 项目级查询
"""

from __future__ import annotations

import logging
from typing import Any

from stable_agent.saas.models import (
    AgentRun,
    Project,
    SaasMode,
    Workspace,
    _new_id,
    _now,
)
from stable_agent.saas.repository import SaasRepository

logger = logging.getLogger(__name__)


class SaasService:
    """SaaS 业务逻辑层。

    Attributes:
        repo: SaaS 数据访问层实例。
        mode: SaaS 运行模式。
    """

    def __init__(
        self,
        repo: SaasRepository | None = None,
        mode: str = "local",
    ) -> None:
        self.repo: SaasRepository = repo or SaasRepository()
        self.mode: str = mode  # SaasMode.LOCAL or SaasMode.SAAS
        self._default_project: Project | None = None

    # ------------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """初始化 SaaS 层（建表 + 创建 default workspace/project）。"""
        self.repo.init_db()
        # 在 local 模式下自动创建 default project
        if self.mode == SaasMode.LOCAL:
            self._ensure_default_project()

    def _ensure_default_project(self) -> Project:
        """确保 default project 存在。"""
        if self._default_project:
            return self._default_project

        # 检查已有 workspace
        workspaces = self.repo.list_workspaces()
        if workspaces:
            ws = workspaces[0]
        else:
            ws = Workspace(name="default")
            self.repo.create_workspace(ws)

        projects = self.repo.list_projects(ws.id)
        if projects:
            self._default_project = projects[0]
        else:
            proj = Project(workspace_id=ws.id, name="default")
            self.repo.create_project(proj)
            self._default_project = proj

        return self._default_project

    @property
    def default_project_id(self) -> str:
        """获取 default project ID。"""
        proj = self._ensure_default_project()
        return proj.id

    @property
    def default_workspace_id(self) -> str:
        """获取 default workspace ID。"""
        proj = self._ensure_default_project()
        return proj.workspace_id

    # ------------------------------------------------------------------
    # Project CRUD
    # ------------------------------------------------------------------

    def create_project(self, workspace_id: str, name: str, description: str = "") -> Project:
        proj = Project(
            workspace_id=workspace_id,
            name=name,
            description=description,
        )
        self.repo.create_project(proj)
        return proj

    def get_project(self, project_id: str) -> Project | None:
        return self.repo.get_project(project_id)

    def list_projects(self, workspace_id: str = "") -> list[Project]:
        if workspace_id:
            return self.repo.list_projects(workspace_id)
        # fallback: return all projects from default workspace
        workspaces = self.repo.list_workspaces()
        if not workspaces:
            return []
        return self.repo.list_projects(workspaces[0].id)

    # ------------------------------------------------------------------
    # Run 归属
    # ------------------------------------------------------------------

    def validate_project_id(self, project_id: str) -> str:
        """校验 project_id。

        local 模式：无 project_id 时 fallback 到 default project
        saas 模式：无 project_id 时抛出 ValueError

        Args:
            project_id: 传入的 project_id。

        Returns:
            有效的 project_id。

        Raises:
            ValueError: SaaS 模式且 project_id 无效时抛出。
        """
        if not project_id and self.mode == SaasMode.LOCAL:
            return self.default_project_id
        if not project_id:
            raise ValueError(
                "SaaS 模式下 project_id 为必填参数。"
                "请先创建项目或使用 default project。"
            )
        # 验证 project 存在
        proj = self.repo.get_project(project_id)
        if proj is None and self.mode == SaasMode.SAAS:
            raise ValueError(f"项目不存在: {project_id}")
        return project_id

    def associate_run(
        self,
        run_id: str,
        project_id: str,
        workspace_id: str = "",
        agent_id: str = "",
        user_task: str = "",
    ) -> AgentRun:
        """将 run 关联到 project。

        Args:
            run_id: 运行 ID。
            project_id: 项目 ID。
            workspace_id: 工作空间 ID（可选，从 project 推导）。
            agent_id: Agent ID（可选）。
            user_task: 用户任务（可选）。

        Returns:
            创建的 AgentRun 记录。
        """
        if not workspace_id:
            proj = self.repo.get_project(project_id)
            if proj:
                workspace_id = proj.workspace_id

        run = AgentRun(
            run_id=run_id,
            workspace_id=workspace_id or self.default_workspace_id,
            project_id=project_id,
            agent_id=agent_id,
            user_task=user_task,
            status="init",
        )
        self.repo.save_run(run)
        return run

    def get_runs_by_project(self, project_id: str, limit: int = 50) -> list[AgentRun]:
        return self.repo.list_runs_by_project(project_id, limit)

    # ------------------------------------------------------------------
    # Usage 查询
    # ------------------------------------------------------------------

    def get_project_usage_summary(self, project_id: str) -> dict[str, Any]:
        return self.repo.get_project_usage_summary(project_id)
