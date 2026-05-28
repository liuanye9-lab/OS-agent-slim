"""DecisionNarrator — 技术事件 → 用户可读 DecisionTrace 翻译器。

将 Agent 内部的低级别事件（如 mcp.call.received、memory.retrieved 等）
翻译为用户可理解的 DecisionTrace，隐藏内部 chain-of-thought 细节。

事件 → DecisionStage 映射:
    mcp.call.received         → task_intake
    task.classified           → intent_parse
    intent.parsed             → intent_parse
    context.budgeted          → context_budget
    memory.retrieved          → memory_retrieval
    rag.retrieved             → rag_retrieval
    context.compressed        → context_build
    context.built             → context_build
    workflow.plan.created     → planning
    tool.call.started         → tool_call
    tool.call.completed       → tool_call
    security.checked          → security_check
    approval.required         → approval_waiting
    eval.completed            → evaluation
    badcase.recorded          → badcase_record
    skillopt.rollout.collected → skill_learning
    skillopt.patch.proposed   → skill_learning
    skillopt.validation.completed → skill_validation
    skillopt.exported         → skill_export
    task.completed            → completed
    task.failed               → failed
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from stable_agent.explanation.explanation_templates import (
    TEMPLATES,
    format_template,
    get_template,
)
from stable_agent.observation.decision_trace import (
    DecisionEvidence,
    DecisionStage,
    DecisionTrace,
)

# ---------------------------------------------------------------------------
# 事件 → DecisionStage 映射表
# ---------------------------------------------------------------------------

_EVENT_STAGE_MAP: dict[str, DecisionStage] = {
    "mcp.call.received": "task_intake",
    "task.classified": "intent_parse",
    "intent.parsed": "intent_parse",
    "context.budgeted": "context_budget",
    "memory.retrieved": "memory_retrieval",
    "rag.retrieved": "rag_retrieval",
    "context.compressed": "context_build",
    "context.built": "context_build",
    "workflow.plan.created": "planning",
    "tool.call.started": "tool_call",
    "tool.call.completed": "tool_call",
    "security.checked": "security_check",
    "approval.required": "approval_waiting",
    "eval.completed": "evaluation",
    "badcase.recorded": "badcase_record",
    "skillopt.rollout.collected": "skill_learning",
    "skillopt.patch.proposed": "skill_learning",
    "skillopt.validation.completed": "skill_validation",
    "skillopt.exported": "skill_export",
    "task.completed": "completed",
    "task.failed": "failed",
}

# 阶段对应的默认标题（中/英）
_STAGE_TITLES: dict[DecisionStage, tuple[str, str]] = {
    "task_intake": ("接收任务", "Task Intake"),
    "intent_parse": ("理解意图", "Intent Parsing"),
    "context_budget": ("Token 预算", "Token Budgeting"),
    "memory_retrieval": ("检索记忆", "Memory Retrieval"),
    "rag_retrieval": ("搜索资料", "Knowledge Search"),
    "context_build": ("构建上下文", "Context Assembly"),
    "planning": ("制定计划", "Planning"),
    "tool_call": ("调用工具", "Tool Call"),
    "security_check": ("安全检查", "Security Check"),
    "approval_waiting": ("等待审批", "Awaiting Approval"),
    "execution": ("执行任务", "Execution"),
    "evaluation": ("评测结果", "Evaluation"),
    "badcase_record": ("记录失败案例", "Bad Case Recording"),
    "skill_learning": ("技能学习", "Skill Learning"),
    "skill_validation": ("技能验证", "Skill Validation"),
    "skill_export": ("导出技能", "Skill Export"),
    "completed": ("已完成", "Completed"),
    "failed": ("失败", "Failed"),
}


class DecisionNarrator:
    """技术事件 → 用户可读 DecisionTrace 翻译器。

    隐藏内部 chain-of-thought 细节，将原始事件翻译为结构化的、
    用户可理解的决策轨迹。支持 zh/en 双语输出。

    Attributes:
        _event_stage_map: 事件类型到 DecisionStage 的映射。
    """

    def __init__(self) -> None:
        """初始化 DecisionNarrator。"""
        self._event_stage_map: dict[str, DecisionStage] = dict(_EVENT_STAGE_MAP)

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    def narrate_event(
        self,
        event_type: str,
        payload: dict,
        run_id: str = "",
        locale: str = "zh",
    ) -> DecisionTrace:
        """根据事件类型分发到对应的 stage handler，生成 DecisionTrace。

        Args:
            event_type: 事件类型字符串，如 "memory.retrieved"。
            payload: 事件携带的原始数据。
            run_id: 关联的运行 ID。
            locale: 输出语言，"zh" 或 "en"。

        Returns:
            填充了中英双语文案的 DecisionTrace 实例。
        """
        stage = self._event_stage_map.get(event_type, "execution")
        narrated = self.narrate_stage(stage, payload, locale)

        # 根据事件类型确定风险等级
        risk_level = self._infer_risk(event_type, payload)
        importance = self._infer_importance(event_type, payload)
        avatar_state = self._infer_avatar(event_type)

        trace = DecisionTrace(
            run_id=run_id,
            span_id=payload.get("span_id", ""),
            stage=stage,
            title_zh=narrated.get("title_zh", _STAGE_TITLES.get(stage, ("", ""))[0]),
            title_en=narrated.get("title_en", _STAGE_TITLES.get(stage, ("", ""))[1]),
            what_happened_zh=narrated.get("what_zh", ""),
            what_happened_en=narrated.get("what_en", ""),
            why_zh=narrated.get("why_zh", ""),
            why_en=narrated.get("why_en", ""),
            evidence=self.explain_evidence(payload, locale),
            discarded_evidence=self.explain_discarded(payload, locale),
            decision_zh=narrated.get("next_zh", ""),
            decision_en=narrated.get("next_en", ""),
            next_step_zh=narrated.get("next_zh", ""),
            next_step_en=narrated.get("next_en", ""),
            risk_level=risk_level,
            confidence=payload.get("confidence", 0.0),
            importance=importance,
            token_used=payload.get("token_used", 0),
            token_budget=payload.get("token_budget", 0),
            quality_score=payload.get("quality_score"),
            avatar_state=avatar_state,
            timestamp=datetime.utcnow(),
            raw_payload=dict(payload),
        )
        return trace

    def narrate_stage(
        self,
        stage: str,
        payload: dict,
        locale: str = "zh",
    ) -> dict[str, str]:
        """根据 stage 生成叙述文本。

        注意：此方法接收 DecisionStage 字符串，而非 event_type。
        如需按 event_type 获取叙述，请使用 narrate_event。

        Args:
            stage: DecisionStage 字符串，如 "memory_retrieval"。
            payload: 事件数据，用于填充模板占位符。
            locale: 输出语言。

        Returns:
            包含 title_zh, title_en, what_zh, what_en, why_zh, why_en,
            next_zh, next_en 的字典。
        """
        # 尝试找到对应此 stage 的**主要** event_type
        event_type = self._stage_to_main_event(stage)

        title_zh, title_en = _STAGE_TITLES.get(stage, ("", ""))  # type: ignore[arg-type]

        if event_type and event_type in TEMPLATES:
            template = get_template(event_type)
            formatted = format_template(template, payload)
            return {
                "title_zh": title_zh,
                "title_en": title_en,
                "what_zh": formatted.get("what_zh", ""),
                "what_en": formatted.get("what_en", ""),
                "why_zh": formatted.get("why_zh", ""),
                "why_en": formatted.get("why_en", ""),
                "next_zh": formatted.get("next_zh", ""),
                "next_en": formatted.get("next_en", ""),
            }

        # 回退：使用 stage 名作为 key 尝试查找
        fallback = get_template(stage)
        formatted = format_template(fallback, {"event_type": stage, **payload})
        return {
            "title_zh": title_zh,
            "title_en": title_en,
            "what_zh": formatted.get("what_zh", ""),
            "what_en": formatted.get("what_en", ""),
            "why_zh": formatted.get("why_zh", ""),
            "why_en": formatted.get("why_en", ""),
            "next_zh": formatted.get("next_zh", ""),
            "next_en": formatted.get("next_en", ""),
        }

    def explain_evidence(
        self,
        payload: dict,
        locale: str = "zh",
    ) -> list[DecisionEvidence]:
        """从 payload 提取 selected evidence 列表。

        识别 payload 中的记忆、文档、上下文片段等信息，
        将它们封装为 DecisionEvidence 对象。

        Args:
            payload: 事件数据。
            locale: 输出语言。

        Returns:
            selected=True 的 DecisionEvidence 列表。
        """
        evidence_list: list[DecisionEvidence] = []

        # 从 memories 提取
        memories = payload.get("memories", []) or payload.get("selected_memories", [])
        for i, mem in enumerate(memories):
            if isinstance(mem, dict):
                evidence_list.append(DecisionEvidence(
                    evidence_type="memory",
                    title=mem.get("title", f"Memory #{i + 1}"),
                    summary_zh=mem.get("summary_zh", mem.get("content", "")),
                    summary_en=mem.get("summary_en", mem.get("content", "")),
                    source=mem.get("source", mem.get("id", "")),
                    confidence=float(mem.get("confidence", mem.get("score", 0.0))),
                    selected=True,
                    reason_zh=mem.get("reason_zh", "与当前任务高度相关"),
                    reason_en=mem.get("reason_en", "Highly relevant to current task"),
                ))

        # 从 documents/rag_results 提取
        docs = payload.get("documents", []) or payload.get("rag_results", [])
        for i, doc in enumerate(docs):
            if isinstance(doc, dict):
                evidence_list.append(DecisionEvidence(
                    evidence_type="document",
                    title=doc.get("title", f"Document #{i + 1}"),
                    summary_zh=doc.get("summary_zh", doc.get("snippet", "")),
                    summary_en=doc.get("summary_en", doc.get("snippet", "")),
                    source=doc.get("source", doc.get("url", doc.get("id", ""))),
                    confidence=float(doc.get("confidence", doc.get("score", 0.0))),
                    selected=True,
                    reason_zh=doc.get("reason_zh", "检索匹配度高"),
                    reason_en=doc.get("reason_en", "High retrieval match"),
                ))

        # 从 generic evidence 提取
        generic = payload.get("evidence", [])
        for i, ev in enumerate(generic):
            if isinstance(ev, dict) and ev.get("selected", True):
                evidence_list.append(DecisionEvidence(
                    evidence_type=ev.get("type", ev.get("evidence_type", "generic")),
                    title=ev.get("title", f"Evidence #{i + 1}"),
                    summary_zh=ev.get("summary_zh", ev.get("content", "")),
                    summary_en=ev.get("summary_en", ev.get("content", "")),
                    source=ev.get("source"),
                    confidence=float(ev.get("confidence", 0.0)),
                    selected=True,
                    reason_zh=ev.get("reason_zh", ""),
                    reason_en=ev.get("reason_en", ""),
                ))

        return evidence_list

    def explain_discarded(
        self,
        payload: dict,
        locale: str = "zh",
    ) -> list[DecisionEvidence]:
        """从 payload 提取 discarded evidence 列表。

        展示被丢弃的候选记忆、文档等，并说明丢弃原因。

        Args:
            payload: 事件数据。
            locale: 输出语言。

        Returns:
            selected=False 的 DecisionEvidence 列表。
        """
        discarded: list[DecisionEvidence] = []

        # 从 discarded_memories 提取
        disc_memories = payload.get("discarded_memories", [])
        for i, mem in enumerate(disc_memories):
            if isinstance(mem, dict):
                discarded.append(DecisionEvidence(
                    evidence_type="memory",
                    title=mem.get("title", f"Discarded Memory #{i + 1}"),
                    summary_zh=mem.get("summary_zh", mem.get("content", "")),
                    summary_en=mem.get("summary_en", mem.get("content", "")),
                    source=mem.get("source", mem.get("id", "")),
                    confidence=float(mem.get("confidence", mem.get("score", 0.0))),
                    selected=False,
                    reason_zh=mem.get("reason_zh", "与当前任务相关性不足"),
                    reason_en=mem.get("reason_en", "Insufficient relevance to current task"),
                ))

        # 从 discarded_documents 提取
        disc_docs = payload.get("discarded_documents", [])
        for i, doc in enumerate(disc_docs):
            if isinstance(doc, dict):
                discarded.append(DecisionEvidence(
                    evidence_type="document",
                    title=doc.get("title", f"Discarded Document #{i + 1}"),
                    summary_zh=doc.get("summary_zh", doc.get("snippet", "")),
                    summary_en=doc.get("summary_en", doc.get("snippet", "")),
                    source=doc.get("source", doc.get("url", doc.get("id", ""))),
                    confidence=float(doc.get("confidence", doc.get("score", 0.0))),
                    selected=False,
                    reason_zh=doc.get("reason_zh", "检索匹配度不足"),
                    reason_en=doc.get("reason_en", "Insufficient retrieval match"),
                ))

        # 从 generic discarded evidence 提取
        generic_disc = payload.get("discarded_evidence", [])
        for i, ev in enumerate(generic_disc):
            if isinstance(ev, dict):
                discarded.append(DecisionEvidence(
                    evidence_type=ev.get("type", ev.get("evidence_type", "generic")),
                    title=ev.get("title", f"Discarded #{i + 1}"),
                    summary_zh=ev.get("summary_zh", ev.get("content", "")),
                    summary_en=ev.get("summary_en", ev.get("content", "")),
                    source=ev.get("source"),
                    confidence=float(ev.get("confidence", 0.0)),
                    selected=False,
                    reason_zh=ev.get("reason_zh", "被决策引擎丢弃"),
                    reason_en=ev.get("reason_en", "Discarded by decision engine"),
                ))

        return discarded

    # ------------------------------------------------------------------
    # 内部辅助方法
    # ------------------------------------------------------------------

    def _stage_to_main_event(self, stage: str) -> str | None:
        """根据 DecisionStage 反向查找主要 event_type。

        Args:
            stage: DecisionStage 字符串。

        Returns:
            对应的主要 event_type，如果未找到返回 None。
        """
        # 某些 stage 有多个事件类型，返回主要的那个
        stage_priority: dict[str, str] = {
            "task_intake": "mcp.call.received",
            "intent_parse": "intent.parsed",
            "context_budget": "context.budgeted",
            "memory_retrieval": "memory.retrieved",
            "rag_retrieval": "rag.retrieved",
            "context_build": "context.built",
            "planning": "workflow.plan.created",
            "tool_call": "tool.call.completed",
            "security_check": "security.checked",
            "approval_waiting": "approval.required",
            "evaluation": "eval.completed",
            "badcase_record": "badcase.recorded",
            "skill_learning": "skillopt.patch.proposed",
            "skill_validation": "skillopt.validation.completed",
            "skill_export": "skillopt.exported",
            "completed": "task.completed",
            "failed": "task.failed",
        }
        return stage_priority.get(stage)

    @staticmethod
    def _infer_risk(
        event_type: str,
        payload: dict,
    ) -> str:
        """根据事件类型和 payload 推断风险等级。

        Args:
            event_type: 事件类型。
            payload: 事件数据。

        Returns:
            "none", "low", "medium", 或 "high"。
        """
        # 优先使用 payload 中的显式风险
        if "risk_level" in payload:
            risk = payload["risk_level"]
            if risk in ("none", "low", "medium", "high"):
                return risk

        # 基于事件类型推断
        high_risk_events = {
            "approval.required", "security.checked", "task.failed",
        }
        medium_risk_events = {
            "tool.call.started", "tool.call.completed", "badcase.recorded",
        }

        if event_type in high_risk_events:
            return "high"
        if event_type in medium_risk_events:
            return "medium"
        return "low"

    @staticmethod
    def _infer_importance(
        event_type: str,
        payload: dict,
    ) -> str:
        """根据事件类型和 payload 推断重要程度。

        Args:
            event_type: 事件类型。
            payload: 事件数据。

        Returns:
            "debug", "normal", "important", 或 "critical"。
        """
        if "importance" in payload:
            imp = payload["importance"]
            if imp in ("debug", "normal", "important", "critical"):
                return imp

        critical_events = {"task.failed", "approval.required"}
        important_events = {
            "task.completed", "eval.completed", "security.checked",
            "skillopt.exported", "badcase.recorded",
        }

        if event_type in critical_events:
            return "critical"
        if event_type in important_events:
            return "important"
        return "normal"

    @staticmethod
    def _infer_avatar(event_type: str) -> str:
        """根据事件类型推断头像状态。

        Args:
            event_type: 事件类型。

        Returns:
            头像状态字符串，如 "listening", "thinking", "idle" 等。
        """
        avatar_map: dict[str, str] = {
            "mcp.call.received": "listening",
            "task.classified": "thinking",
            "intent.parsed": "thinking",
            "context.budgeted": "thinking",
            "memory.retrieved": "thinking",
            "rag.retrieved": "thinking",
            "context.compressed": "thinking",
            "context.built": "thinking",
            "workflow.plan.created": "thinking",
            "tool.call.started": "working",
            "tool.call.completed": "working",
            "security.checked": "checking",
            "approval.required": "waiting",
            "eval.completed": "thinking",
            "badcase.recorded": "sweating",
            "skillopt.rollout.collected": "learning",
            "skillopt.patch.proposed": "learning",
            "skillopt.validation.completed": "learning",
            "skillopt.exported": "celebrating",
            "task.completed": "celebrating",
            "task.failed": "sweating",
        }
        return avatar_map.get(event_type, "idle")
