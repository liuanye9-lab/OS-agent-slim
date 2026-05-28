"""V5.5 DecisionTrace 数据模型 — 可解释决策轨迹。"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

DecisionStage = Literal[
    "task_intake", "intent_parse", "context_budget", "memory_retrieval",
    "rag_retrieval", "context_build", "planning", "tool_call",
    "security_check", "approval_waiting", "execution", "evaluation",
    "badcase_record", "skill_learning", "skill_validation", "skill_export",
    "completed", "failed",
]

EventImportance = Literal["debug", "normal", "important", "critical"]


@dataclass
class DecisionEvidence:
    """决策依据。每条 evidence 是一条 Agent 使用的信息片段。"""
    evidence_type: str = ""
    title: str = ""
    summary_zh: str = ""
    summary_en: str = ""
    source: str | None = None
    confidence: float = 0.0
    selected: bool = True
    reason_zh: str = ""
    reason_en: str = ""


@dataclass
class DecisionTrace:
    """单条决策轨迹。一条 trace 对应一个关键决策节点。"""
    run_id: str = ""
    span_id: str = ""
    stage: DecisionStage = "execution"
    title_zh: str = ""
    title_en: str = ""
    what_happened_zh: str = ""
    what_happened_en: str = ""
    why_zh: str = ""
    why_en: str = ""
    evidence: list[DecisionEvidence] = field(default_factory=list)
    discarded_evidence: list[DecisionEvidence] = field(default_factory=list)
    decision_zh: str = ""
    decision_en: str = ""
    next_step_zh: str = ""
    next_step_en: str = ""
    risk_level: Literal["none", "low", "medium", "high"] = "none"
    confidence: float = 0.0
    importance: EventImportance = "normal"
    token_used: int = 0
    token_budget: int = 0
    quality_score: float | None = None
    avatar_state: str = "idle"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunInsight:
    """任务完成后生成的用户可读总结。"""
    run_id: str = ""
    task_summary_zh: str = ""
    task_summary_en: str = ""
    final_result_zh: str = ""
    final_result_en: str = ""
    quality_score: float = 0.0
    intent_alignment_score: float = 0.0
    token_roi: float = 0.0
    memory_hit_rate: float = 0.0
    learning_triggered: bool = False
    skill_updated: bool = False
    improvement_summary_zh: str = ""
    improvement_summary_en: str = ""
    failure_reason_zh: str | None = None
    failure_reason_en: str | None = None
    next_time_rule_zh: str | None = None
    next_time_rule_en: str | None = None
