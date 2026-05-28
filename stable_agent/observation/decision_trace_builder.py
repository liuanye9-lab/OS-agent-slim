"""DecisionTraceBuilder — 从 event payload 构建 DecisionTrace。

封装 DecisionNarrator，提供简化的构建接口。
用法::

    narrator = DecisionNarrator()
    builder = DecisionTraceBuilder(narrator)
    trace = builder.build("memory.retrieved", payload, run_id="run-001")
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from stable_agent.observation.decision_trace import DecisionTrace

if TYPE_CHECKING:
    from stable_agent.explanation.decision_narrator import DecisionNarrator


class DecisionTraceBuilder:
    """从 event payload 构建 DecisionTrace。

    封装 DecisionNarrator，在一次调用中完成叙述 + 证据提取。

    Attributes:
        _narrator: 内部的 DecisionNarrator 实例。
    """

    def __init__(self, narrator: DecisionNarrator | None = None) -> None:
        """初始化 DecisionTraceBuilder。

        Args:
            narrator: DecisionNarrator 实例。如果为 None，则自动创建一个。
        """
        if narrator is None:
            from stable_agent.explanation.decision_narrator import DecisionNarrator as _DN
            self._narrator: DecisionNarrator = _DN()
        else:
            self._narrator: DecisionNarrator = narrator

    def build(
        self,
        event_type: str,
        payload: dict[str, Any],
        run_id: str = "",
        span_id: str = "",
    ) -> DecisionTrace:
        """根据事件类型和 payload 构建 DecisionTrace。

        Args:
            event_type: 事件类型字符串，如 "memory.retrieved"。
            payload: 事件携带的原始数据字典。
            run_id: 关联的运行 ID。
            span_id: 关联的 span ID；如果 payload 中已有则优先生效。

        Returns:
            填充完整的 DecisionTrace 实例。
        """
        # 如果 payload 中已有 span_id，则优先使用
        effective_span = payload.get("span_id", span_id)

        # 通过 narrator 生成 DecisionTrace
        trace = self._narrator.narrate_event(
            event_type=event_type,
            payload=payload,
            run_id=run_id,
        )

        # 确保 span_id 正确设置
        if effective_span:
            trace.span_id = effective_span

        return trace

    def build_batch(
        self,
        events: list[tuple[str, dict[str, Any]]],
        run_id: str = "",
    ) -> list[DecisionTrace]:
        """批量构建 DecisionTrace 列表。

        Args:
            events: (event_type, payload) 元组列表。
            run_id: 关联的运行 ID。

        Returns:
            DecisionTrace 列表。
        """
        traces: list[DecisionTrace] = []
        for event_type, payload in events:
            traces.append(self.build(event_type, payload, run_id=run_id))
        return traces

    @property
    def narrator(self) -> DecisionNarrator:
        """获取内部的 DecisionNarrator 实例。"""
        return self._narrator
