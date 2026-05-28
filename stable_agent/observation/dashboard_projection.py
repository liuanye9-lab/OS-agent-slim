"""DashboardProjection — DecisionTrace → 前端 Dashboard V2 投影数据。

将内部的 DecisionTrace、RunInsight、LearningEvidence
转换为前端 Dashboard V2 组件可直接渲染的数据格式。
"""

from __future__ import annotations

from typing import Any

from stable_agent.gateway.tool_schemas import AVATAR_SCENE_MAP
from stable_agent.observation.decision_trace import (
    DecisionEvidence,
    DecisionTrace,
    RunInsight,
)


class DashboardProjection:
    """DecisionTrace → 前端 Dashboard V2 投影数据。

    将后端数据模型转换为前端友好的渲染结构，
    包括 timeline 时间线、洞察面板和学习面板数据。

    Attributes:
        _avatar_state_map: 决策阶段到头像状态的映射。
        _scene_map: 13 语义场景映射，来自 tool_schemas.AVATAR_SCENE_MAP。
    """

    # 风险等级图标映射
    _RISK_ICONS: dict[str, str] = {
        "none": "🟢",
        "low": "🟡",
        "medium": "🟠",
        "high": "🔴",
    }

    # 重要程度图标映射
    _IMPORTANCE_ICONS: dict[str, str] = {
        "debug": "🐛",
        "normal": "📋",
        "important": "⭐",
        "critical": "🚨",
    }

    # 阶段 → avatar 状态（13 语义场景）
    _STAGE_AVATAR: dict[str, str] = {
        "task_intake": "listening",
        "intent_parse": "thinking",
        "context_budget": "calculating",
        "memory_retrieval": "reading_notes",
        "rag_retrieval": "searching_books",
        "context_build": "thinking",
        "planning": "planning",
        "tool_call": "tooling",
        "security_check": "safety_check",
        "approval_waiting": "waiting_approval",
        "execution": "tooling",
        "evaluation": "grading",
        "badcase_record": "failed",
        "skill_learning": "learning",
        "skill_validation": "grading",
        "skill_export": "archiving",
        "completed": "done",
        "failed": "failed",
    }

    def project_trace(
        self,
        trace: DecisionTrace,
        locale: str = "zh",
    ) -> dict[str, Any]:
        """单条 trace → 前端 render 数据。

        Args:
            trace: DecisionTrace 实例。
            locale: 输出语言，"zh" 或 "en"。

        Returns:
            包含 stage_title, what, why, why_zh, why_en, evidence, discarded,
            decision_trace, decision, next, avatar, risk 等字段的字典。
        """
        is_zh = locale == "zh"

        # 阶段标题
        stage_title = trace.title_zh if is_zh else trace.title_en

        # 叙述内容
        what = trace.what_happened_zh if is_zh else trace.what_happened_en
        why = trace.why_zh if is_zh else trace.why_en
        decision = trace.decision_zh if is_zh else trace.decision_en
        next_step = trace.next_step_zh if is_zh else trace.next_step_en

        # 证据列表
        evidence = self._project_evidence_list(trace.evidence, locale)
        discarded = self._project_evidence_list(trace.discarded_evidence, locale)

        # 头像状态 → 13 语义场景
        avatar_state = self._STAGE_AVATAR.get(trace.stage, "listening")
        avatar = avatar_state
        scene = self.get_scene_for_stage(trace.stage)

        # 决策轨迹子对象（供前端 decision_timeline.js 使用）
        decision_trace: dict[str, Any] = {
            "why_zh": trace.why_zh,
            "why_en": trace.why_en,
            "discarded_evidence": discarded,
            "evidence": evidence,
            "decision_zh": trace.decision_zh,
            "decision_en": trace.decision_en,
        }

        # 风险 & 重要程度
        risk = {
            "level": trace.risk_level,
            "icon": self._RISK_ICONS.get(trace.risk_level, "⚪"),
        }

        importance = {
            "level": trace.importance,
            "icon": self._IMPORTANCE_ICONS.get(trace.importance, "📋"),
        }

        return {
            "id": f"{trace.run_id}:{trace.span_id}:{trace.stage}",
            "run_id": trace.run_id,
            "span_id": trace.span_id,
            "stage": trace.stage,
            "stage_title": stage_title,
            "what": what,
            "why": why,
            "why_zh": trace.why_zh,
            "why_en": trace.why_en,
            "evidence": evidence,
            "discarded": discarded,
            "decision_trace": decision_trace,
            "decision": decision,
            "next": next_step,
            "avatar": avatar,
            "avatar_state": avatar_state,
            "scene": scene,
            "risk": risk,
            "importance": importance,
            "confidence": trace.confidence,
            "token_used": trace.token_used,
            "token_budget": trace.token_budget,
            "quality_score": trace.quality_score,
            "timestamp": trace.timestamp.isoformat() if trace.timestamp else None,
        }

    def get_scene_for_stage(self, stage: str) -> dict[str, Any]:
        """根据决策阶段获取 13 语义场景配置。

        Args:
            stage: 决策阶段名，如 "planning"、"tool_call" 等。

        Returns:
            包含 scene, prop, label_zh, label_en, avatar_state 的字典。
        """
        avatar_state = self._STAGE_AVATAR.get(stage, "listening")
        scene_cfg: dict[str, str] = AVATAR_SCENE_MAP.get(
            avatar_state,
            AVATAR_SCENE_MAP["listening"],
        )
        return {
            "scene": scene_cfg["scene"],
            "prop": scene_cfg["prop"],
            "label_zh": scene_cfg["label_zh"],
            "label_en": scene_cfg["label_en"],
            "avatar_state": avatar_state,
        }

    def project_timeline(
        self,
        traces: list[DecisionTrace],
        locale: str = "zh",
    ) -> list[dict[str, Any]]:
        """将 trace 列表投影为时间线数据。

        Args:
            traces: DecisionTrace 列表。
            locale: 输出语言。

        Returns:
            按时间排列的投影数据列表。
        """
        # 按时间戳排序
        sorted_traces = sorted(
            traces,
            key=lambda t: t.timestamp,
        )
        return [self.project_trace(t, locale) for t in sorted_traces]

    def project_insight(
        self,
        insight: RunInsight,
        locale: str = "zh",
    ) -> dict[str, Any]:
        """将 RunInsight 投影为前端面板数据。

        Args:
            insight: RunInsight 实例。
            locale: 输出语言。

        Returns:
            前端渲染所需的面板数据字典。
        """
        is_zh = locale == "zh"

        return {
            "run_id": insight.run_id,
            "task_summary": (
                insight.task_summary_zh if is_zh else insight.task_summary_en
            ),
            "final_result": (
                insight.final_result_zh if is_zh else insight.final_result_en
            ),
            "quality_score": insight.quality_score,
            "quality_label": self._quality_label(insight.quality_score, locale),
            "intent_alignment_score": insight.intent_alignment_score,
            "token_roi": insight.token_roi,
            "token_roi_label": self._roi_label(insight.token_roi, locale),
            "memory_hit_rate": insight.memory_hit_rate,
            "learning_triggered": insight.learning_triggered,
            "skill_updated": insight.skill_updated,
            "improvement_summary": (
                insight.improvement_summary_zh
                if is_zh
                else insight.improvement_summary_en
            ),
            "failure_reason": (
                insight.failure_reason_zh if is_zh else insight.failure_reason_en
            ),
            "next_time_rule": (
                insight.next_time_rule_zh if is_zh else insight.next_time_rule_en
            ),
            "has_failure": insight.failure_reason_zh is not None,
            "has_improvement": bool(insight.improvement_summary_zh),
        }

    def project_learning(
        self,
        evidence: dict[str, Any],
        locale: str = "zh",
    ) -> dict[str, Any]:
        """将 LearningEvidence 输出投影为前端面板数据。

        Args:
            evidence: LearningEvidence.build_from_validation() 的返回值。
            locale: 输出语言。

        Returns:
            前端学习面板渲染数据。
        """
        is_zh = locale == "zh"

        patches = evidence.get("patches", [])
        projected_patches: list[dict[str, Any]] = []
        for i, patch in enumerate(patches):
            if isinstance(patch, dict):
                projected_patches.append({
                    "index": i,
                    "name": patch.get("name", f"Patch #{i + 1}"),
                    "description": patch.get("description", ""),
                    "diff": patch.get("diff", ""),
                    "before": patch.get("before", ""),
                    "after": patch.get("after", ""),
                    "score_delta": float(patch.get("score_delta", 0.0)),
                })

        return {
            "triggered": evidence.get("triggered", False),
            "reason": evidence.get("reason_zh" if is_zh else "reason_en", ""),
            "patches": projected_patches,
            "patch_count": len(projected_patches),
            "baseline_score": evidence.get("baseline_score", 0.0),
            "candidate_score": evidence.get("candidate_score", 0.0),
            "passed": evidence.get("passed", False),
            "diff_summary": evidence.get("diff_summary", ""),
            "has_patches": len(projected_patches) > 0,
            "score_delta": (
                evidence.get("candidate_score", 0.0)
                - evidence.get("baseline_score", 0.0)
            ),
        }

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _project_evidence_list(
        self,
        evidence_list: list[DecisionEvidence],
        locale: str,
    ) -> list[dict[str, Any]]:
        """投影证据列表。

        Args:
            evidence_list: DecisionEvidence 列表。
            locale: 输出语言。

        Returns:
            投影后的证据字典列表。
        """
        is_zh = locale == "zh"
        result: list[dict[str, Any]] = []
        for ev in evidence_list:
            result.append({
                "type": ev.evidence_type,
                "title": ev.title,
                "summary": ev.summary_zh if is_zh else ev.summary_en,
                "source": ev.source,
                "confidence": ev.confidence,
                "selected": ev.selected,
                "reason": ev.reason_zh if is_zh else ev.reason_en,
            })
        return result

    @staticmethod
    def _quality_label(score: float, locale: str) -> str:
        """将质量评分转换为可读标签。

        Args:
            score: 质量评分。
            locale: 输出语言。

        Returns:
            质量标签字符串。
        """
        if score >= 0.9:
            return "优秀" if locale == "zh" else "Excellent"
        if score >= 0.7:
            return "良好" if locale == "zh" else "Good"
        if score >= 0.5:
            return "一般" if locale == "zh" else "Fair"
        return "较差" if locale == "zh" else "Poor"

    @staticmethod
    def _roi_label(roi: float, locale: str) -> str:
        """将 Token ROI 转换为可读标签。

        Args:
            roi: Token ROI 值。
            locale: 输出语言。

        Returns:
            ROI 标签字符串。
        """
        if roi >= 2.0:
            return "高效" if locale == "zh" else "Efficient"
        if roi >= 1.0:
            return "正常" if locale == "zh" else "Normal"
        if roi >= 0.5:
            return "偏低" if locale == "zh" else "Low"
        return "很低" if locale == "zh" else "Very Low"
