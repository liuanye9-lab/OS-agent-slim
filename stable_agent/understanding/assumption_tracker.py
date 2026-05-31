"""假设追踪器。

追踪 UnderstandingTrace 中产生的假设，支持查询和确认。

用法::

    tracker = AssumptionTracker()
    tracker.track_assumption("trace_001", "假设需要项目上下文", 0.8)
    assumptions = tracker.get_assumptions("trace_001")
"""

from __future__ import annotations

from stable_agent.understanding.schemas import AssumptionRecord


class AssumptionTracker:
    """假设追踪器。

    追踪语义理解过程中产生的假设，支持按 trace 查询和列出未确认假设。

    Attributes:
        _records: 假设记录列表。
    """

    def __init__(self) -> None:
        """初始化假设追踪器。"""
        self._records: list[AssumptionRecord] = []

    def track_assumption(
        self,
        trace_id: str,
        assumption: str,
        confidence: float = 0.5,
    ) -> AssumptionRecord:
        """记录假设。

        Args:
            trace_id: 关联的 trace ID。
            assumption: 假设内容。
            confidence: 置信度 0.0~1.0。

        Returns:
            创建的 AssumptionRecord。
        """
        record = AssumptionRecord(
            trace_id=trace_id,
            assumption=assumption,
            confidence=confidence,
        )
        self._records.append(record)
        return record

    def get_assumptions(self, trace_id: str) -> list[AssumptionRecord]:
        """获取指定 trace 的所有假设。

        Args:
            trace_id: trace ID。

        Returns:
            匹配的 AssumptionRecord 列表。
        """
        return [r for r in self._records if r.trace_id == trace_id]

    def list_unconfirmed(self) -> list[AssumptionRecord]:
        """列出所有未确认的假设。

        Returns:
            未确认的 AssumptionRecord 列表。
        """
        return [r for r in self._records if not r.confirmed]

    def confirm_assumption(self, assumption_id: str) -> bool:
        """确认假设。

        Args:
            assumption_id: 假设 ID。

        Returns:
            是否成功确认。
        """
        for r in self._records:
            if r.assumption_id == assumption_id:
                r.confirmed = True
                return True
        return False
