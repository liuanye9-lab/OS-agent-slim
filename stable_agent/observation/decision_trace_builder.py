"""DecisionTraceBuilder — 从 event payload 构建 DecisionTrace。

封装 DecisionNarrator，提供简化的构建接口。
用法::

    narrator = DecisionNarrator()
    builder = DecisionTraceBuilder(narrator)
    trace = builder.build("memory.retrieved", payload, run_id="run-001")
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from stable_agent.observation.decision_trace import DecisionTrace

logger = logging.getLogger(__name__)

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
        stage: str = "",
    ) -> DecisionTrace:
        """根据事件类型和 payload 构建 DecisionTrace。

        Production Hardening: 集成 RunLifecycle 为每个阶段自动添加
        decision_summary_zh / why_zh / next_step_zh。

        Args:
            event_type: 事件类型字符串，如 "memory.retrieved"。
            payload: 事件携带的原始数据字典。
            run_id: 关联的运行 ID。
            span_id: 关联的 span ID。
            stage: 当前 RunStage（用于 RunLifecycle 元信息注入）。

        Returns:
            填充完整的 DecisionTrace 实例。
        """
        effective_span = payload.get("span_id", span_id)

        trace = self._narrator.narrate_event(
            event_type=event_type,
            payload=payload,
            run_id=run_id,
        )

        if effective_span:
            trace.span_id = effective_span

        # Production Hardening: RunLifecycle 元信息注入
        if stage and not trace.decision_summary_zh:
            try:
                from stable_agent.runtime.run_lifecycle import get_stage_meta
                meta = get_stage_meta(stage)
                trace.decision_summary_zh = meta.default_why_zh
                trace.decision_summary_en = meta.status_text_en
                trace.why_zh = meta.default_why_zh
                trace.why_en = meta.status_text_en
                trace.avatar_state = meta.avatar_state
                trace.progress_pct = meta.progress_pct
            except Exception:
                logger.exception("RunLifecycle meta injection failed for stage=%s", stage)

        # Payload 中的显式字段优先
        if payload.get("decision_summary_zh"):
            trace.decision_summary_zh = payload["decision_summary_zh"]
        if payload.get("why_zh"):
            trace.why_zh = payload["why_zh"]
        if payload.get("avatar_state"):
            trace.avatar_state = payload["avatar_state"]
        if payload.get("progress_pct") is not None:
            trace.progress_pct = int(payload["progress_pct"])

        return trace

    def build_for_dashboard(
        self,
        *,
        run_id: str,
        stage: str,
        event_type: str,
        payload: dict[str, Any],
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """为 Dashboard 构建简化的 DecisionTrace 字典。

        Returns:
            包含 decision_summary_zh/why_zh/next_step_zh/progress_pct/avatar_state
            等 Dashboard 前端直接可用的字段。
        """
        from stable_agent.runtime.run_lifecycle import get_stage_meta
        meta = get_stage_meta(stage)

        result: dict[str, Any] = {
            "run_id": run_id,
            "stage": stage,
            "stage_label_zh": meta.status_text_zh,
            "stage_label_en": meta.status_text_en,
            "progress_pct": payload.get("progress_pct", meta.progress_pct),
            "avatar_state": payload.get("avatar_state", meta.avatar_state),
            "decision_summary_zh": payload.get("decision_summary_zh", meta.default_why_zh),
            "decision_summary_en": payload.get("decision_summary_en", meta.status_text_en),
            "why_zh": payload.get("why_zh", meta.default_why_zh),
            "why_en": payload.get("why_en", meta.status_text_en),
            "next_step_zh": payload.get("next_step_zh", meta.default_next_step_zh),
            "next_step_en": payload.get("next_step_en", ""),
            "evidence": payload.get("evidence", []),
            "discarded_evidence": payload.get("discarded_evidence", []),
            "risk_level": payload.get("risk_level", "low"),
            "event_type": event_type,
        }
        if extra:
            result.update(extra)
        return result

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
