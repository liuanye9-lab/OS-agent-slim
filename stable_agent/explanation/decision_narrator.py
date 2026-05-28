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
    # V5.5 新增方法 — explain_why + summarize_discarded
    # ------------------------------------------------------------------

    def explain_why(
        self,
        event_type: str,
        payload: dict[str, Any],
        locale: str = "zh",
    ) -> str:
        """解释为什么做了这个决定。

        根据事件类型返回预设的、用户可理解的原因说明，
        帮助用户理解 Agent 决策背后的逻辑。

        Args:
            event_type: 事件类型字符串。
            payload: 事件携带的原始数据（保留扩展位）。
            locale: 输出语言，"zh" 或 "en"。

        Returns:
            对应语言的解释文本。
        """
        explanations: dict[str, dict[str, str]] = {
            "context.budgeted": {
                "zh": "根据任务复杂度分配 token 预算，确保在有限上下文窗口中高效执行",
                "en": "Allocated token budget based on task complexity for efficient execution",
            },
            "memory.retrieved": {
                "zh": "从历史经验中检索相关记忆，避免重复犯错",
                "en": "Retrieved relevant memories to avoid repeating past mistakes",
            },
            "context.compressed": {
                "zh": "上下文接近预算上限，压缩非关键信息以保留核心任务空间",
                "en": "Context approaching budget limit, compressing non-critical info",
            },
            "tool.call.completed": {
                "zh": "工具调用成功完成，结果已纳入当前上下文",
                "en": "Tool call completed successfully, result integrated into context",
            },
            "approval.required": {
                "zh": "检测到高风险操作，需要人工确认以确保安全",
                "en": "High-risk operation detected, human approval required",
            },
            "eval.completed": {
                "zh": "评估输出质量，作为后续优化和改进的依据",
                "en": "Evaluated output quality for future optimization",
            },
            "task.completed": {
                "zh": "所有步骤执行完毕，任务目标已达成",
                "en": "All steps completed, task goal achieved",
            },
            "task.failed": {
                "zh": "任务执行失败，记录原因以便分析和改进",
                "en": "Task failed, recording reason for analysis",
            },
        }
        info: dict[str, str] = explanations.get(event_type, {
            "zh": "系统根据预设规则自动做出此决策",
            "en": "System made this decision based on preset rules",
        })
        return info.get(locale, info["zh"])

    def summarize_discarded(
        self,
        payload: dict[str, Any],
        locale: str = "zh",
    ) -> list[dict[str, Any]]:
        """总结被丢弃的上下文/证据及其原因。

        从 payload 中提取 discarded 列表，生成简洁的摘要字典列表，
        用于前端展示被过滤掉的信息及原因。

        Args:
            payload: 事件数据，需包含 "discarded" 键。
            locale: 输出语言（保留扩展位，目前 reason 已预设双语）。

        Returns:
            清理后的丢弃项字典列表，每项包含 evidence_type, title,
            summary_zh, summary_en, confidence, selected=False,
            reason_zh, reason_en。
        """
        discarded: list[dict[str, Any]] = payload.get("discarded", [])
        if not discarded:
            return []

        result: list[dict[str, Any]] = []
        for item in discarded:
            result.append({
                "evidence_type": item.get("type", "unknown"),
                "title": item.get("title", ""),
                "summary_zh": item.get(
                    "reason_zh", "因预算或相关性限制被丢弃"
                ),
                "summary_en": item.get(
                    "reason_en", "Discarded due to budget or relevance constraint"
                ),
                "confidence": item.get("confidence", 0.0),
                "selected": False,
                "reason_zh": item.get("reason_zh", ""),
                "reason_en": item.get("reason_en", ""),
            })
        return result

    # V6.5: narrate() — 大白话决策解释
    def narrate(
        self,
        event_type: str,
        stage: str,
        payload: dict[str, Any],
        locale: str = "zh",
    ) -> dict[str, str]:
        """为 22 种事件类型生成大白话双语解释。

        返回 dict: status_text_zh/en, decision_summary_zh/en, why_zh/en, next_step_zh/en。
        不含 chain_of_thought — 只展示可观察决策摘要。
        """
        templates = {
            "mcp.call.received": {
                "status_text_zh": "接收任务", "status_text_en": "Receiving task",
                "decision_summary_zh": "它收到了一个新任务，开始准备处理。",
                "decision_summary_en": "It received a new task and is preparing to handle it.",
                "why_zh": "这是 OS Agent 自优化工作流的起点。", "why_en": "This is the entry point of the OS Agent workflow.",
                "next_step_zh": "接下来会分析任务类型。", "next_step_en": "Next, it will classify the task.",
            },
            "task.classified": {
                "status_text_zh": "分析任务", "status_text_en": "Classifying task",
                "decision_summary_zh": "它正在判断这个任务属于哪种类型。",
                "decision_summary_en": "It's determining what type of task this is.",
                "why_zh": "不同类型的任务需要不同的处理策略和预算分配。", "why_en": "Different task types need different strategies.",
                "next_step_zh": "接下来会理解具体意图。", "next_step_en": "Next, it will parse the intent.",
            },
            "intent.parsed": {
                "status_text_zh": "理解意图", "status_text_en": "Understanding intent",
                "decision_summary_zh": "它正在判断你真正想要什么结果。",
                "decision_summary_en": "It's figuring out what result you really want.",
                "why_zh": "只有理解了真实意图，才不会跑偏。", "why_en": "Understanding intent prevents going off track.",
                "next_step_zh": "接下来会估算 token 预算。", "next_step_en": "Next, it will estimate the token budget.",
            },
            "context.budgeted": {
                "status_text_zh": "计算预算", "status_text_en": "Estimating budget",
                "decision_summary_zh": "它正在根据任务复杂度分配 token 预算。",
                "decision_summary_en": "It's allocating token budget based on task complexity.",
                "why_zh": "确保在有限的上下文窗口中高效执行。", "why_en": "To execute efficiently within the context window.",
                "next_step_zh": "接下来会查找相关记忆。", "next_step_en": "Next, it will retrieve relevant memories.",
            },
            "memory.retrieved": {
                "status_text_zh": "查找记忆", "status_text_en": "Retrieving memory",
                "decision_summary_zh": "它正在从历史经验中找和这个任务相关的记忆。",
                "decision_summary_en": "It's finding prior experiences related to this task.",
                "why_zh": "避免每次都从零开始，也能更贴近你的偏好。", "why_en": "This avoids starting from scratch each time.",
                "next_step_zh": "接下来会搜索项目资料。", "next_step_en": "Next, it will search project knowledge.",
            },
            "rag.retrieved": {
                "status_text_zh": "查找资料", "status_text_en": "Searching knowledge",
                "decision_summary_zh": "它正在从项目资料和文档中找有用的内容。",
                "decision_summary_en": "It's finding useful content from project docs.",
                "why_zh": "项目特有的知识无法从通用记忆中获取。", "why_en": "Project-specific knowledge can't come from general memory.",
                "next_step_zh": "接下来会整理上下文包。", "next_step_en": "Next, it will build the context pack.",
            },
            "context.compressed": {
                "status_text_zh": "压缩上下文", "status_text_en": "Compressing context",
                "decision_summary_zh": "上下文太多，它在压缩非关键信息以保留核心空间。",
                "decision_summary_en": "Context is large, it's compressing non-critical info.",
                "why_zh": "确保最重要的信息不会被 token 限制截断。", "why_en": "To ensure critical info isn't truncated by token limits.",
                "next_step_zh": "接下来会构建最终上下文。", "next_step_en": "Next, it will build the final context.",
            },
            "context.built": {
                "status_text_zh": "整理上下文", "status_text_en": "Building context",
                "decision_summary_zh": "它正在把记忆、资料和任务需求打包成一个精简的上下文。",
                "decision_summary_en": "It's packing memories, docs and task into a concise context.",
                "why_zh": "一个高质量的上下文包能显著提升模型输出质量。", "why_en": "A high-quality context pack improves model output.",
                "next_step_zh": "接下来会制定执行计划。", "next_step_en": "Next, it will create an execution plan.",
            },
            "workflow.plan.created": {
                "status_text_zh": "规划步骤", "status_text_en": "Planning steps",
                "decision_summary_zh": "它正在决定先做什么、后做什么、用什么工具。",
                "decision_summary_en": "It's deciding what to do first and which tools to use.",
                "why_zh": "有序执行比随机尝试效率高得多。", "why_en": "Ordered execution is more efficient than random attempts.",
                "next_step_zh": "接下来会开始调用工具。", "next_step_en": "Next, it will start calling tools.",
            },
            "tool.call.started": {
                "status_text_zh": "调用工具", "status_text_en": "Calling tool",
                "decision_summary_zh": "它正在调用外部工具来执行具体操作。",
                "decision_summary_en": "It's calling an external tool to execute.",
                "why_zh": "复杂任务需要借助专业工具来完成。", "why_en": "Complex tasks need specialized tools.",
                "next_step_zh": "等待工具返回结果。", "next_step_en": "Waiting for tool result.",
            },
            "tool.call.completed": {
                "status_text_zh": "工具完成", "status_text_en": "Tool completed",
                "decision_summary_zh": "工具调用成功，结果已纳入当前上下文。",
                "decision_summary_en": "Tool call succeeded, result integrated.",
                "why_zh": "工具的结果会帮助后续步骤做出更好的决策。", "why_en": "Tool results inform better decisions in later steps.",
                "next_step_zh": "接下来会继续执行下一步。", "next_step_en": "Next, it will proceed to the next step.",
            },
            "security.checked": {
                "status_text_zh": "安全检查", "status_text_en": "Security check",
                "decision_summary_zh": "它正在检查当前操作是否存在安全风险。",
                "decision_summary_en": "It's checking for security risks.",
                "why_zh": "高风险操作必须经过验证才能继续。", "why_en": "High-risk operations must be verified.",
                "next_step_zh": "如果需要会请求人工确认。", "next_step_en": "If needed, it will request human approval.",
            },
            "approval.required": {
                "status_text_zh": "等待确认", "status_text_en": "Waiting for approval",
                "decision_summary_zh": "检测到高风险操作，需要你确认是否继续。",
                "decision_summary_en": "High-risk operation detected, needs your approval.",
                "why_zh": "保护你的项目安全是最优先的。", "why_en": "Project safety is the top priority.",
                "next_step_zh": "请确认是否继续执行。", "next_step_en": "Please confirm whether to proceed.",
            },
            "eval.completed": {
                "status_text_zh": "评估结果", "status_text_en": "Evaluating",
                "decision_summary_zh": "它正在检查当前输出是否达到质量标准。",
                "decision_summary_en": "It's checking if the output meets quality standards.",
                "why_zh": "评估结果是后续自我优化的关键依据。", "why_en": "Evaluation results are key for self-optimization.",
                "next_step_zh": "如果达标就完成任务，否则记录改进点。", "next_step_en": "If passed, done. Otherwise, record improvements.",
            },
            "badcase.recorded": {
                "status_text_zh": "记录案例", "status_text_en": "Recording case",
                "decision_summary_zh": "它正在记录这次失败的原因，作为未来改进的基础。",
                "decision_summary_en": "It's recording why this failed for future improvement.",
                "why_zh": "只有知道哪里失败，下次才能不再犯同样的错误。", "why_en": "Recording failures prevents repeating mistakes.",
                "next_step_zh": "这些案例会进入 SkillOpt 优化循环。", "next_step_en": "These cases will feed into SkillOpt.",
            },
            "skillopt.rollout.collected": {
                "status_text_zh": "收集数据", "status_text_en": "Collecting rollout",
                "decision_summary_zh": "它正在收集这次执行的所有数据作为学习材料。",
                "decision_summary_en": "It's collecting execution data as learning material.",
                "why_zh": "足够的数据是自我优化的基础。", "why_en": "Sufficient data is the foundation of self-optimization.",
                "next_step_zh": "接下来会分析成功和失败的模式。", "next_step_en": "Next, it will analyze success and failure patterns.",
            },
            "skillopt.pattern.found": {
                "status_text_zh": "发现规律", "status_text_en": "Pattern found",
                "decision_summary_zh": "它从历史数据中发现了一些成功或失败的模式。",
                "decision_summary_en": "It found some success or failure patterns in the data.",
                "why_zh": "这些规律可以转化为具体的 skill 改进规则。", "why_en": "These patterns can become skill improvement rules.",
                "next_step_zh": "接下来会提出 skill 改进方案。", "next_step_en": "Next, it will propose skill patches.",
            },
            "skillopt.patch.proposed": {
                "status_text_zh": "提出改进", "status_text_en": "Patch proposed",
                "decision_summary_zh": "它正在生成具体的 skill 文档修改方案。",
                "decision_summary_en": "It's generating specific skill doc modifications.",
                "why_zh": "只有把经验写进 skill 文档，下次才能真正用上。", "why_en": "Only written rules can be used next time.",
                "next_step_zh": "接下来会验证改进是否有效。", "next_step_en": "Next, it will validate the improvement.",
            },
            "skillopt.validation.completed": {
                "status_text_zh": "验证通过", "status_text_en": "Validation passed",
                "decision_summary_zh": "改进方案通过了验证，确认确实比之前更好。",
                "decision_summary_en": "The improvement passed validation, confirmed better.",
                "why_zh": "只有经过验证的改进才会真正生效。", "why_en": "Only validated improvements are applied.",
                "next_step_zh": "接下来会导出更新后的 skill。", "next_step_en": "Next, it will export the updated skill.",
            },
            "skillopt.exported": {
                "status_text_zh": "导出技能", "status_text_en": "Skill exported",
                "decision_summary_zh": "更新的 skill 文档已保存，下次执行会自动使用新规则。",
                "decision_summary_en": "Updated skill doc saved, will be used next time.",
                "why_zh": "持久化 skill 文档让优化效果可以跨会话保持。", "why_en": "Persisted skills maintain improvement across sessions.",
                "next_step_zh": "任务已完成。", "next_step_en": "Task completed.",
            },
            "task.completed": {
                "status_text_zh": "任务完成", "status_text_en": "Completed",
                "decision_summary_zh": "所有步骤执行完毕，任务目标已达成。",
                "decision_summary_en": "All steps done, task goal achieved.",
                "why_zh": "它按照规划顺利完成了整个工作流。", "why_en": "It followed the plan and completed the workflow.",
                "next_step_zh": "你可以查看 Dashboard 了解详情。", "next_step_en": "Check the Dashboard for details.",
            },
            "task.failed": {
                "status_text_zh": "任务失败", "status_text_en": "Failed",
                "decision_summary_zh": "任务执行失败，正在记录失败原因。",
                "decision_summary_en": "Task failed, recording the reason.",
                "why_zh": "失败信息会被用于后续改进和避免重复错误。", "why_en": "Failure info will be used for future improvement.",
                "next_step_zh": "你可以查看 Dashboard 了解失败原因。", "next_step_en": "Check the Dashboard for failure details.",
            },
        }

        info = templates.get(event_type, {
            "status_text_zh": "处理中", "status_text_en": "Processing",
            "decision_summary_zh": "系统正在根据预设规则执行操作。",
            "decision_summary_en": "System is executing based on preset rules.",
            "why_zh": "这是自动化流程的一部分。", "why_en": "This is part of the automated workflow.",
            "next_step_zh": "等待下一步。", "next_step_en": "Awaiting next step.",
        })

        if locale == "en":
            return {k: v for k, v in info.items() if k.endswith("_en") or k == "status_text_en"}
        return info

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
