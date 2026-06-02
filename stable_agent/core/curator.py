"""stable_agent/core/curator.py — CuratorService。

SkillOS-inspired 规则型 Curator v1。
从 RunTrace 中提炼经验，生成 SkillCandidate。

职责：
- 分析 trace，判断是否 learning-worthy
- 提取 failure_mode + evidence
- 生成 SkillCandidate
- 计算 reward proxy score
- 压缩约束检查

不负责：
- 直接写入 SkillRepo
- Promote / Reject 决策
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any

from stable_agent.core.models import RunTrace, SkillCandidate

logger = logging.getLogger(__name__)


# ── Reward Proxy 权重 ──────────────────────────────────────────
REWARD_WEIGHTS = {
    "task_outcome": 0.35,
    "event_completeness": 0.20,
    "content_quality": 0.15,
    "compression": 0.15,
    "token_efficiency": 0.10,
    "latency": 0.05,
    "regression_penalty": 0.30,
}


class CuratorService:
    """技能策展器。

    从 RunTrace 中提炼经验，生成 SkillCandidate。
    第一版使用规则判断，不做 RL 训练。
    """

    def __init__(self, skill_repo: Any = None, validator: Any = None):
        self._skill_repo = skill_repo
        self._validator = validator

    def analyze_trace(self, trace: RunTrace) -> dict:
        """分析 trace，返回分析结果。

        Args:
            trace: 运行轨迹。

        Returns:
            分析结果字典，包含 is_learning_worthy, failure_mode, reward_proxy 等。
        """
        is_worthy = self._is_learning_worthy(trace)
        failure_mode = self._extract_failure_mode(trace)
        reward_proxy = self._compute_reward_proxy(trace)

        return {
            "is_learning_worthy": is_worthy,
            "failure_mode": failure_mode,
            "reward_proxy": reward_proxy,
            "eval_score": trace.eval_score,
            "event_completeness": self._compute_event_completeness(trace),
        }

    def propose_candidates(self, trace: RunTrace) -> list[SkillCandidate]:
        """从 trace 中生成 skill 候选。

        Args:
            trace: 运行轨迹。

        Returns:
            SkillCandidate 列表 (可能为空)。
        """
        if not self._is_learning_worthy(trace):
            return []

        failure_mode = self._extract_failure_mode(trace)
        if not failure_mode:
            return []

        candidate_id = self._generate_candidate_id(trace.run_id, failure_mode)
        reward_proxy = self._compute_reward_proxy(trace)

        candidate = SkillCandidate(
            candidate_id=candidate_id,
            source_run_id=trace.run_id,
            failure_mode=failure_mode,
            evidence_events=self._extract_evidence_events(trace),
            proposed_rule=self._generate_proposed_rule(trace, failure_mode),
            when_to_use=self._generate_when_to_use(trace, failure_mode),
            do_not_use_when=self._generate_do_not_use_when(trace),
            validation_plan=self._generate_validation_plan(trace),
            risk_level=self._assess_risk_level(trace),
            status="candidate",
            domain=self._extract_domain(trace),
            created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            reward_proxy_score=reward_proxy,
        )

        return [candidate]

    def ingest_feedback(self, run_id: str, feedback: str, feedback_type: str) -> list[SkillCandidate]:
        """从用户反馈中生成 skill 候选。

        Args:
            run_id: 运行 ID。
            feedback: 用户反馈文本。
            feedback_type: 反馈类型 (remember/dont_do_this/correct)。

        Returns:
            SkillCandidate 列表。
        """
        if feedback_type == "dont_do_this":
            candidate = SkillCandidate(
                candidate_id=self._generate_candidate_id(run_id, "user_feedback"),
                source_run_id=run_id,
                failure_mode="user_feedback",
                evidence_events=[],
                proposed_rule=feedback[:500],
                when_to_use="",
                do_not_use_when=feedback[:500],
                validation_plan="验证规则不会导致相同问题",
                risk_level="low",
                status="candidate",
                domain="general",
                created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            )
            return [candidate]
        return []

    # ── Learning-worthy 判断 ──────────────────────────────────

    def _is_learning_worthy(self, trace: RunTrace) -> bool:
        """判断是否值得学习。"""
        if trace.eval_score is not None and trace.eval_score < 0.75:
            return True
        if trace.artifacts.get("force_eval_failed"):
            return True
        if trace.artifacts.get("user_feedback"):
            return True
        if trace.artifacts.get("missing_required_events"):
            return True
        if trace.artifacts.get("dashboard_replay_ok") is False:
            return True
        return False

    # ── Failure Mode 提取 ─────────────────────────────────────

    def _extract_failure_mode(self, trace: RunTrace) -> str:
        """从 trace 中提取失败模式。"""
        if trace.artifacts.get("force_eval_failed"):
            return trace.artifacts.get("force_failure_mode", "intent_drift")
        if trace.eval_score is not None and trace.eval_score < 0.5:
            return "low_quality"
        if trace.eval_score is not None and trace.eval_score < 0.75:
            return "below_threshold"
        if trace.artifacts.get("missing_required_events"):
            return "incomplete_events"
        if trace.artifacts.get("dashboard_replay_ok") is False:
            return "replay_failure"
        return ""

    # ── Reward Proxy 计算 ─────────────────────────────────────

    def _compute_reward_proxy(self, trace: RunTrace) -> float:
        """计算轻量 reward proxy。

        工程推断，不声称复现 SkillOS 论文公式。
        """
        task_outcome = self._compute_task_outcome(trace)
        event_completeness = self._compute_event_completeness(trace)
        content_quality = self._compute_content_quality(trace)
        compression = self._compute_compression(trace)
        token_efficiency = self._compute_token_efficiency(trace)
        latency = self._compute_latency(trace)
        regression_penalty = self._compute_regression_penalty(trace)

        reward = (
            REWARD_WEIGHTS["task_outcome"] * task_outcome
            + REWARD_WEIGHTS["event_completeness"] * event_completeness
            + REWARD_WEIGHTS["content_quality"] * content_quality
            + REWARD_WEIGHTS["compression"] * compression
            + REWARD_WEIGHTS["token_efficiency"] * token_efficiency
            + REWARD_WEIGHTS["latency"] * latency
            - REWARD_WEIGHTS["regression_penalty"] * regression_penalty
        )
        return round(max(0.0, min(1.0, reward)), 4)

    def _compute_task_outcome(self, trace: RunTrace) -> float:
        """任务结果分数。"""
        if trace.eval_score is not None:
            return trace.eval_score
        return 0.5

    def _compute_event_completeness(self, trace: RunTrace) -> float:
        """事件完整性分数。"""
        required = [
            "task.received", "intent.parsed", "context.budgeted",
            "temporal_memory.retrieved", "rag.retrieved",
            "context.compression_guard.checked", "context.built",
            "workflow.plan.created", "workflow.step.started",
            "workflow.step.completed", "eval.completed",
            "self_improvement.checked", "task.completed",
        ]
        emitted = [e.get("event_type") for e in trace.events if e.get("_emit_ok")]
        if not required:
            return 1.0
        matched = sum(1 for r in required if r in emitted)
        return matched / len(required)

    def _compute_content_quality(self, trace: RunTrace) -> float:
        """内容质量分数。"""
        if trace.output_text and len(trace.output_text) > 50:
            return 0.7
        return 0.3

    def _compute_compression(self, trace: RunTrace) -> float:
        """压缩效率分数。"""
        token_report = trace.artifacts.get("token_report")
        if token_report and isinstance(token_report, dict):
            saving_ratio = token_report.get("saving_ratio", 0.0)
            return min(1.0, saving_ratio * 2)
        return 0.5

    def _compute_token_efficiency(self, trace: RunTrace) -> float:
        """Token 效率分数。"""
        token_report = trace.artifacts.get("token_report")
        if token_report and isinstance(token_report, dict):
            saved = token_report.get("saved_tokens_estimated", 0)
            baseline = token_report.get("baseline_tokens_estimated", 1)
            if baseline > 0:
                return min(1.0, saved / baseline)
        return 0.5

    def _compute_latency(self, trace: RunTrace) -> float:
        """延迟分数。"""
        return 0.5

    def _compute_regression_penalty(self, trace: RunTrace) -> float:
        """回归惩罚。"""
        si_report = trace.si_report
        if si_report and isinstance(si_report, dict):
            regression_count = si_report.get("regression_cases", 0)
            if regression_count > 0:
                return min(1.0, regression_count * 0.3)
        return 0.0

    # ── 辅助方法 ──────────────────────────────────────────────

    def _generate_candidate_id(self, run_id: str, failure_mode: str) -> str:
        """生成候选 ID。"""
        raw = f"{run_id}:{failure_mode}:{time.time()}"
        return f"sk_{hashlib.sha256(raw.encode()).hexdigest()[:12]}"

    def _extract_evidence_events(self, trace: RunTrace) -> list[str]:
        """提取证据事件。"""
        return [e.get("event_type", "") for e in trace.events[-5:] if e.get("event_type")]

    def _generate_proposed_rule(self, trace: RunTrace, failure_mode: str) -> str:
        """生成建议规则。"""
        if failure_mode == "low_quality":
            return "当任务输出质量低于阈值时，应增加上下文检索深度。"
        if failure_mode == "intent_drift":
            return "当检测到意图漂移时，应重新确认用户目标。"
        if failure_mode == "incomplete_events":
            return "当事件链不完整时，应检查事件发布逻辑。"
        return f"针对 {failure_mode} 模式的改进规则。"

    def _generate_when_to_use(self, trace: RunTrace, failure_mode: str) -> str:
        """生成使用场景。"""
        return f"当遇到 {failure_mode} 类型的失败时使用。"

    def _generate_do_not_use_when(self, trace: RunTrace) -> str:
        """生成不使用场景。"""
        return "当任务类型不匹配时不要使用。"

    def _generate_validation_plan(self, trace: RunTrace) -> str:
        """生成验证计划。"""
        return "使用 related task 验证改进效果，确保无回归。"

    def _assess_risk_level(self, trace: RunTrace) -> str:
        """评估风险等级。"""
        if trace.eval_score is not None and trace.eval_score < 0.3:
            return "high"
        if trace.eval_score is not None and trace.eval_score < 0.6:
            return "medium"
        return "low"

    def _extract_domain(self, trace: RunTrace) -> str:
        """提取领域。"""
        task_type = trace.artifacts.get("task_type", "unknown")
        if task_type and task_type != "unknown":
            return task_type
        return "general"
