"""Run 业务逻辑。

管理 Agent 运行的生命周期。
"""

from __future__ import annotations

import logging
from typing import Any

from stable_agent.saas.models import (
    AgentRun,
    RunStatus,
    _new_id,
    _now,
)

logger = logging.getLogger(__name__)


class RunService:
    """Run 业务逻辑层。

    Attributes:
        repository: SaasRepository 实例。
        permission_checker: PermissionChecker 实例。
        usage_counter: UsageCounter 实例（可选）。
    """

    def __init__(
        self,
        repository: Any = None,
        permission_checker: Any = None,
        usage_counter: Any = None,
    ) -> None:
        self._repo = repository
        self._perms = permission_checker
        self._usage = usage_counter

    def create_run(
        self,
        workspace_id: str,
        project_id: str,
        agent_id: str = "",
        user_task: str = "",
        task_type: str = "general_qa",
        source: str = "mcp",
    ) -> AgentRun:
        """创建新的 Agent 运行。

        Args:
            workspace_id: 工作空间 ID。
            project_id: 项目 ID。
            agent_id: Agent ID。
            user_task: 用户任务描述。
            task_type: 任务类型。
            source: 来源。

        Returns:
            创建的 AgentRun。
        """
        run_id = f"run_{_new_id('r').split('_')[1]}"
        run = AgentRun(
            run_id=run_id,
            workspace_id=workspace_id,
            project_id=project_id,
            agent_id=agent_id,
            user_task=user_task,
            task_type=task_type,
            status=RunStatus.CREATED.value,
            dashboard_url=f"/runs/{run_id}",
            trace_url=f"/runs/{run_id}",
        )

        if self._repo is not None:
            self._repo.save_run(run)

        # 记录用量
        if self._usage is not None:
            self._usage.record(
                workspace_id=workspace_id,
                project_id=project_id,
                run_id=run_id,
                event_type="run_created",
                metadata={"source": source, "task_type": task_type},
            )

        logger.info("Created run %s in project %s", run_id, project_id)
        return run

    def get_run(self, run_id: str) -> AgentRun | None:
        """获取运行。"""
        if self._repo is None:
            return None
        return self._repo.get_run(run_id)

    def update_run_status(
        self, run_id: str, status: str, progress_pct: int = 0,
    ) -> bool:
        """更新运行状态。"""
        if self._repo is None:
            return False
        run = self._repo.get_run(run_id)
        if run is None:
            return False
        run.status = status
        run.progress_pct = progress_pct
        run.updated_at = _now()
        return self._repo.save_run(run)

    def complete_run(
        self, run_id: str, overall_score: float | None = None,
        token_used: int = 0, cost_estimate: float = 0.0,
    ) -> bool:
        """标记运行完成。"""
        if self._repo is None:
            return False
        run = self._repo.get_run(run_id)
        if run is None:
            return False
        run.status = RunStatus.COMPLETED.value
        run.progress_pct = 100
        run.ended_at = _now()
        run.overall_score = overall_score
        run.token_used = token_used
        run.cost_estimate = cost_estimate
        run.updated_at = _now()
        return self._repo.save_run(run)

    def list_runs_by_project(self, project_id: str, limit: int = 50) -> list[AgentRun]:
        """列出项目的所有运行。"""
        if self._repo is None:
            return []
        return self._repo.list_runs_by_project(project_id, limit)
