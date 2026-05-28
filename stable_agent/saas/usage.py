"""用量计数器。

记录 MCP 工具调用、token 消耗、评测执行等事件。
为未来 billing 做准备。本轮不接 Stripe。

用法::

    counter = UsageCounter(repo)
    counter.record(workspace_id="ws_xxx", project_id="proj_xxx",
                   event_type="mcp_tool_called", tokens_used=1500)
"""

from __future__ import annotations

import logging
from typing import Any

from stable_agent.saas.models import UsageEventRecord, UsageEventType, _new_id, _now
from stable_agent.saas.repository import SaasRepository

logger = logging.getLogger(__name__)

# 成本估算常量（美元/1K tokens）
COST_PER_1K_INPUT = 0.00015   # ~GPT-4o-mini input price
COST_PER_1K_OUTPUT = 0.0006   # ~GPT-4o-mini output price
COST_PER_1K_DEFAULT = 0.0003  # 默认估算


class UsageCounter:
    """用量计数器。

    记录 MCP 工具调用、token 消耗等事件到 usage_events 表。

    Attributes:
        repo: SaaS 数据访问层实例。
    """

    def __init__(self, repo: SaasRepository | None = None) -> None:
        self.repo: SaasRepository = repo or SaasRepository()

    # ------------------------------------------------------------------
    # 记录用量
    # ------------------------------------------------------------------

    def record(
        self,
        workspace_id: str,
        project_id: str,
        event_type: str,
        run_id: str = "",
        tokens_used: int = 0,
        cost_estimate: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> UsageEventRecord | None:
        """记录一次用量事件。

        Args:
            workspace_id: 工作空间 ID。
            project_id: 项目 ID。
            event_type: 事件类型（见 UsageEventType）。
            run_id: 关联的运行 ID。
            tokens_used: 消耗 token 数。
            cost_estimate: 预估成本。
            metadata: 附加元数据。

        Returns:
            创建的 UsageEventRecord，失败返回 None。
        """
        if cost_estimate == 0.0 and tokens_used > 0:
            cost_estimate = self.estimate_cost(event_type, tokens_used)

        evt = UsageEventRecord(
            workspace_id=workspace_id,
            project_id=project_id,
            run_id=run_id,
            event_type=event_type,
            tokens_used=tokens_used,
            cost_estimate=round(cost_estimate, 8),
            metadata=metadata or {},
        )
        ok = self.repo.save_usage_event(evt)
        if not ok:
            logger.warning("Failed to record usage event: %s", event_type)
            return None
        return evt

    # ------------------------------------------------------------------
    # 快捷方法
    # ------------------------------------------------------------------

    def record_run_created(
        self,
        workspace_id: str,
        project_id: str,
        run_id: str,
    ) -> UsageEventRecord | None:
        return self.record(
            workspace_id=workspace_id,
            project_id=project_id,
            event_type=UsageEventType.RUN_CREATED,
            run_id=run_id,
        )

    def record_mcp_tool_called(
        self,
        workspace_id: str,
        project_id: str,
        run_id: str,
        tool_name: str = "",
    ) -> UsageEventRecord | None:
        return self.record(
            workspace_id=workspace_id,
            project_id=project_id,
            event_type=UsageEventType.MCP_TOOL_CALLED,
            run_id=run_id,
            metadata={"tool_name": tool_name},
        )

    def record_eval_executed(
        self,
        workspace_id: str,
        project_id: str,
        run_id: str,
        tokens_used: int = 0,
    ) -> UsageEventRecord | None:
        return self.record(
            workspace_id=workspace_id,
            project_id=project_id,
            event_type=UsageEventType.EVAL_EXECUTED,
            run_id=run_id,
            tokens_used=tokens_used,
        )

    def record_skill_validation(
        self,
        workspace_id: str,
        project_id: str,
        run_id: str,
    ) -> UsageEventRecord | None:
        return self.record(
            workspace_id=workspace_id,
            project_id=project_id,
            event_type=UsageEventType.SKILL_VALIDATION_RUN,
            run_id=run_id,
        )

    def record_skill_exported(
        self,
        workspace_id: str,
        project_id: str,
        run_id: str,
    ) -> UsageEventRecord | None:
        return self.record(
            workspace_id=workspace_id,
            project_id=project_id,
            event_type=UsageEventType.SKILL_EXPORTED,
            run_id=run_id,
        )

    def record_token_used(
        self,
        workspace_id: str,
        project_id: str,
        run_id: str,
        tokens_used: int,
    ) -> UsageEventRecord | None:
        return self.record(
            workspace_id=workspace_id,
            project_id=project_id,
            event_type=UsageEventType.TOKEN_USED,
            run_id=run_id,
            tokens_used=tokens_used,
        )

    # ------------------------------------------------------------------
    # 成本估算
    # ------------------------------------------------------------------

    @staticmethod
    def estimate_cost(event_type: str, tokens_used: int) -> float:
        """根据事件类型和 token 数估算成本。

        使用 GPT-4o-mini 级别价格作为基准。

        Args:
            event_type: 事件类型。
            tokens_used: 消耗的 token 数。

        Returns:
            预估成本（美元）。
        """
        if event_type in (UsageEventType.TOKEN_USED,):
            rate = COST_PER_1K_OUTPUT
        elif event_type in (UsageEventType.EVAL_EXECUTED,):
            rate = COST_PER_1K_INPUT
        else:
            rate = COST_PER_1K_DEFAULT

        return round((tokens_used / 1000) * rate, 8)

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def get_summary(self, project_id: str) -> dict[str, Any]:
        """获取项目用量摘要。"""
        return self.repo.get_project_usage_summary(project_id)

    def list_events(self, project_id: str, limit: int = 100) -> list[UsageEventRecord]:
        """列出项目用量事件。"""
        return self.repo.list_usage_events(project_id, limit)
