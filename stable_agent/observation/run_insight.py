"""RunInsightGenerator — 任务结束后生成用户可读总结。

聚合所有 DecisionTrace，生成包含质量评分、意图对齐度、
Token ROI、记忆命中率等关键指标的 RunInsight 总结。
"""

from __future__ import annotations

from typing import Any

from stable_agent.observation.decision_trace import (
    DecisionTrace,
    RunInsight,
)


class RunInsightGenerator:
    """任务结束后生成用户可读总结。

    聚合一次任务运行中的所有 DecisionTrace，计算关键指标，
    并生成结构化的 RunInsight 供前端 Dashboard 展示。

    Attributes:
        _quality_threshold: 质量评分阈值，低于此值视为需要改进。
    """

    def __init__(self, quality_threshold: float = 0.6) -> None:
        """初始化 RunInsightGenerator。

        Args:
            quality_threshold: 质量评分阈值，低于此值时触发改进建议。
        """
        self._quality_threshold: float = quality_threshold

    def generate(
        self,
        traces: list[DecisionTrace],
        run_id: str,
    ) -> RunInsight:
        """聚合所有 DecisionTrace，生成 RunInsight。

        Args:
            traces: 该 run 的所有 DecisionTrace 列表。
            run_id: 运行唯一标识。

        Returns:
            包含各项指标和总结的 RunInsight 实例。
        """
        if not traces:
            return RunInsight(
                run_id=run_id,
                task_summary_zh="未找到任何决策轨迹。",
                task_summary_en="No decision traces found.",
                final_result_zh="无结果",
                final_result_en="No result",
            )

        # ── 计算各项指标 ──────────────────────────────────────────────
        quality_scores = [
            t.quality_score for t in traces if t.quality_score is not None
        ]
        quality_score = (
            sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
        )

        # 意图对齐评分（基于 intent_parse 阶段的 confidence）
        intent_traces = [t for t in traces if t.stage == "intent_parse"]
        intent_alignment = (
            sum(t.confidence for t in intent_traces) / len(intent_traces)
            if intent_traces
            else 0.5
        )

        # Token ROI = (产出价值) / token_used
        total_tokens = sum(t.token_used for t in traces)
        total_budget = max(t.token_budget for t in traces) if traces else 1
        token_roi = (
            quality_score / (total_tokens / total_budget)
            if total_tokens > 0 and total_budget > 0
            else 0.0
        )

        # 记忆命中率
        memory_traces = [t for t in traces if t.stage == "memory_retrieval"]
        total_selected = sum(len(t.evidence) for t in memory_traces)
        total_discarded = sum(len(t.discarded_evidence) for t in memory_traces)
        memory_hit_rate = (
            total_selected / (total_selected + total_discarded)
            if (total_selected + total_discarded) > 0
            else 0.0
        )

        # 是否触发了学习
        learning_stages = {"skill_learning", "skill_validation", "skill_export"}
        learning_triggered = any(t.stage in learning_stages for t in traces)
        skill_updated = any(t.stage == "skill_export" for t in traces)

        # ── 生成叙述 ──────────────────────────────────────────────────
        task_summary_zh = self._build_task_summary(traces, "zh")
        task_summary_en = self._build_task_summary(traces, "en")

        final_result_zh = self._build_final_result(traces, "zh")
        final_result_en = self._build_final_result(traces, "en")

        improvement_summary_zh = self._build_improvement(traces, quality_score, "zh")
        improvement_summary_en = self._build_improvement(traces, quality_score, "en")

        # 失败原因
        failed_traces = [t for t in traces if t.stage == "failed"]
        failure_zh: str | None = None
        failure_en: str | None = None
        next_time_rule_zh: str | None = None
        next_time_rule_en: str | None = None

        if failed_traces:
            last_failure = failed_traces[-1]
            failure_zh = last_failure.what_happened_zh or "任务执行失败"
            failure_en = last_failure.what_happened_en or "Task execution failed"
            next_time_rule_zh = last_failure.decision_zh or "请检查输入后重试"
            next_time_rule_en = last_failure.decision_en or "Please check input and retry"

        return RunInsight(
            run_id=run_id,
            task_summary_zh=task_summary_zh,
            task_summary_en=task_summary_en,
            final_result_zh=final_result_zh,
            final_result_en=final_result_en,
            quality_score=round(quality_score, 4),
            intent_alignment_score=round(intent_alignment, 4),
            token_roi=round(token_roi, 4),
            memory_hit_rate=round(memory_hit_rate, 4),
            learning_triggered=learning_triggered,
            skill_updated=skill_updated,
            improvement_summary_zh=improvement_summary_zh,
            improvement_summary_en=improvement_summary_en,
            failure_reason_zh=failure_zh,
            failure_reason_en=failure_en,
            next_time_rule_zh=next_time_rule_zh,
            next_time_rule_en=next_time_rule_en,
        )

    # ------------------------------------------------------------------
    # 内部叙述生成
    # ------------------------------------------------------------------

    def _build_task_summary(
        self,
        traces: list[DecisionTrace],
        locale: str,
    ) -> str:
        """生成任务执行摘要。"""
        stages_seen: set[str] = set()
        summary_parts: list[str] = []

        stage_labels_zh: dict[str, str] = {
            "task_intake": "接收任务",
            "intent_parse": "解析意图",
            "memory_retrieval": "检索记忆",
            "rag_retrieval": "搜索资料",
            "context_build": "构建上下文",
            "planning": "制定计划",
            "tool_call": "调用工具",
            "evaluation": "评测结果",
            "completed": "任务完成",
            "failed": "任务失败",
        }
        stage_labels_en: dict[str, str] = {
            "task_intake": "received task",
            "intent_parse": "parsed intent",
            "memory_retrieval": "retrieved memories",
            "rag_retrieval": "searched knowledge",
            "context_build": "built context",
            "planning": "created plan",
            "tool_call": "called tools",
            "evaluation": "evaluated results",
            "completed": "completed",
            "failed": "failed",
        }

        labels = stage_labels_zh if locale == "zh" else stage_labels_en

        for trace in traces:
            if trace.stage not in stages_seen and trace.stage in labels:
                stages_seen.add(trace.stage)
                summary_parts.append(labels[trace.stage])

        if locale == "zh":
            return "Agent 依次执行了：" + " → ".join(summary_parts) + "。"
        else:
            return "Agent executed: " + " → ".join(summary_parts) + "."

    def _build_final_result(
        self,
        traces: list[DecisionTrace],
        locale: str,
    ) -> str:
        """生成最终结果描述。"""
        completed_traces = [t for t in traces if t.stage == "completed"]
        failed_traces = [t for t in traces if t.stage == "failed"]

        if completed_traces:
            ct = completed_traces[-1]
            return ct.what_happened_zh if locale == "zh" else ct.what_happened_en

        if failed_traces:
            ft = failed_traces[-1]
            return ft.what_happened_zh if locale == "zh" else ft.what_happened_en

        if locale == "zh":
            return "任务已执行，但未记录最终状态。"
        else:
            return "Task executed but final status was not recorded."

    def _build_improvement(
        self,
        traces: list[DecisionTrace],
        quality_score: float,
        locale: str,
    ) -> str:
        """生成改进建议。"""
        if quality_score >= self._quality_threshold:
            if locale == "zh":
                return "本次执行质量良好，无需额外改进。"
            else:
                return "Execution quality is good; no additional improvements needed."

        # 找出低置信度的阶段
        low_conf_traces = [t for t in traces if t.confidence < 0.5]
        if low_conf_traces:
            stage_names = list({t.stage for t in low_conf_traces})
            if locale == "zh":
                return f"以下阶段置信度较低，建议优化：{', '.join(stage_names)}"
            else:
                return f"Low confidence in stages: {', '.join(stage_names)}. Consider optimization."

        if locale == "zh":
            return f"质量评分 {quality_score:.2f} 低于阈值 {self._quality_threshold}，建议检查。"
        else:
            return f"Quality score {quality_score:.2f} below threshold {self._quality_threshold}. Review recommended."
