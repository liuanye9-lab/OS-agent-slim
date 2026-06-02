"""stable_agent.skills.judges — OutcomeJudge + ContentJudge。

判断 run 是否成功，判断 skill 内容质量。
第一版用规则 judge，预留 LLM judge adapter（默认关闭）。
slim profile 下不调用重型 LLM。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

# 危险命令列表
DANGEROUS_COMMANDS = [
    "rm -rf /",
    "rm -rf /*",
    "sudo rm -rf",
    "shutdown",
    "reboot",
    "mkfs",
    "chmod -R 777",
    "curl | sh",
    "curl | bash",
    "wget | sh",
    "wget | bash",
    "eval(",
    "exec(",
    ":(){:|:&};:",  # fork bomb
    "dd if=/dev/zero",
    "dd if=/dev/random",
]


@dataclass
class OutcomeJudgeResult:
    """OutcomeJudge 输出。"""

    success: bool = False
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)
    failure_type: Optional[str] = None
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "failure_type": self.failure_type,
            "rationale": self.rationale,
        }


@dataclass
class ContentJudgeResult:
    """ContentJudge 输出。"""

    valid: bool = True
    score: float = 0.0
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "score": self.score,
            "issues": self.issues,
            "suggestions": self.suggestions,
        }


class OutcomeJudge:
    """结果评判器。

    判断 run 是否成功。
    第一版规则 judge，预留 LLM adapter（默认关闭）。
    """

    def judge(
        self,
        run_id: str = "",
        task_input: str = "",
        events: list[dict[str, Any]] | None = None,
        final_result: str = "",
        user_feedback: str = "",
    ) -> OutcomeJudgeResult:
        """判断 run 结果。

        规则：
        - task.completed 且 tests passed -> success
        - task.failed -> failure
        - user negative feedback -> failure/uncertain
        - missing_required_events 非空 -> confidence 降低
        - 没有 final result -> uncertain

        Args:
            run_id: 运行 ID。
            task_input: 任务输入。
            events: 事件列表。
            final_result: 最终结果。
            user_feedback: 用户反馈。

        Returns:
            判断结果。
        """
        events = events or []
        evidence: list[str] = []
        success = False
        confidence = 0.5
        failure_type = None
        rationale = ""

        # 检查事件
        has_completed = False
        has_failed = False
        tests_passed = False
        missing_events = []

        for event in events:
            event_type = event.get("type", "")
            if event_type == "task.completed":
                has_completed = True
                evidence.append("task.completed event found")
            elif event_type == "task.failed":
                has_failed = True
                evidence.append("task.failed event found")
                failure_type = event.get("failure_type", "unknown")
            elif event_type == "tests.passed":
                tests_passed = True
                evidence.append("tests.passed event found")
            elif event_type == "tests.failed":
                evidence.append("tests.failed event found")
            elif event_type == "missing_required_events":
                missing = event.get("missing", [])
                missing_events.extend(missing)

        # 判断逻辑
        if has_failed:
            success = False
            confidence = 0.8
            rationale = "task failed"
        elif has_completed and tests_passed:
            success = True
            confidence = 0.9
            rationale = "task completed with tests passed"
        elif has_completed:
            success = True
            confidence = 0.7
            rationale = "task completed (no test result)"
        elif final_result:
            success = True
            confidence = 0.6
            rationale = "has final result"
        else:
            success = False
            confidence = 0.3
            rationale = "no completion signal"

        # 用户反馈调整
        if user_feedback:
            feedback_lower = user_feedback.lower()
            negative_keywords = ["fail", "wrong", "bad", "error", "错", "失败", "不对"]
            for kw in negative_keywords:
                if kw in feedback_lower:
                    success = False
                    confidence = max(confidence, 0.7)
                    rationale = f"user negative feedback: {user_feedback}"
                    evidence.append(f"user feedback: {user_feedback}")
                    break

        # missing events 降低 confidence
        if missing_events:
            confidence *= 0.8
            evidence.append(f"missing events: {missing_events}")

        return OutcomeJudgeResult(
            success=success,
            confidence=confidence,
            evidence=evidence,
            failure_type=failure_type,
            rationale=rationale,
        )


class ContentJudge:
    """内容评判器。

    判断 skill 内容质量。
    评分维度：
    - abstractness: 是否过度绑定单个案例
    - reusability: 是否可复用
    - executability: 是否有明确步骤
    - faithfulness: 是否忠实于 source_run
    - compression: 是否比原始轨迹更短
    - safety: 是否包含危险命令
    """

    def judge(
        self,
        skill_doc: str = "",
        source_run: str = "",
        curation_op: dict[str, Any] | None = None,
    ) -> ContentJudgeResult:
        """判断 skill 内容质量。

        Args:
            skill_doc: SKILL.md 内容。
            source_run: 来源运行 ID。
            curation_op: 策展操作。

        Returns:
            判断结果。
        """
        issues: list[str] = []
        suggestions: list[str] = []
        scores: list[float] = []

        if not skill_doc:
            return ContentJudgeResult(
                valid=False,
                score=0.0,
                issues=["empty skill document"],
                suggestions=["add SKILL.md content"],
            )

        # 1. Safety check
        safety_score = self._check_safety(skill_doc)
        scores.append(safety_score)
        if safety_score < 1.0:
            issues.append("contains dangerous commands")
            suggestions.append("remove dangerous commands from skill")

        # 2. Abstractness check
        abstractness_score = self._check_abstractness(skill_doc)
        scores.append(abstractness_score)
        if abstractness_score < 0.3:
            issues.append("too specific to single case")
            suggestions.append("generalize the skill for broader use")

        # 3. Reusability check
        reusability_score = self._check_reusability(skill_doc)
        scores.append(reusability_score)
        if reusability_score < 0.3:
            issues.append("low reusability")
            suggestions.append("add more general patterns")

        # 4. Executability check
        executability_score = self._check_executability(skill_doc)
        scores.append(executability_score)
        if executability_score < 0.3:
            issues.append("lacks clear procedure")
            suggestions.append("add step-by-step procedure")

        # 5. Compression check
        compression_score = self._check_compression(skill_doc)
        scores.append(compression_score)
        if compression_score < 0.3:
            issues.append("too long or verbose")
            suggestions.append("compress the skill content")

        # 计算总分
        final_score = sum(scores) / len(scores) if scores else 0.0

        return ContentJudgeResult(
            valid=len(issues) == 0,
            score=final_score,
            issues=issues,
            suggestions=suggestions,
        )

    def _check_safety(self, doc: str) -> float:
        """检查安全性。"""
        doc_lower = doc.lower()
        for cmd in DANGEROUS_COMMANDS:
            if cmd.lower() in doc_lower:
                logger.warning("Dangerous command found: %s", cmd)
                return 0.0
        return 1.0

    def _check_abstractness(self, doc: str) -> float:
        """检查抽象度。

        过度绑定单个案例的特征：
        - 包含具体文件路径
        - 包含具体 run_id
        - 包含具体时间戳
        """
        score = 1.0

        # 检查具体路径
        path_patterns = [
            r'/Users/\w+/',
            r'/home/\w+/',
            r'C:\\Users\\',
            r'run_[a-f0-9]{12}',
        ]
        for pattern in path_patterns:
            if re.search(pattern, doc):
                score -= 0.3

        # 检查过长的代码块（可能是具体实现而非通用模式）
        code_blocks = re.findall(r'```[\s\S]*?```', doc)
        for block in code_blocks:
            if len(block) > 500:
                score -= 0.2

        return max(0.0, min(1.0, score))

    def _check_reusability(self, doc: str) -> float:
        """检查可复用性。

        好的技能应该：
        - 有明确的 "When to use" 或使用场景
        - 有通用的步骤
        - 不依赖特定环境
        """
        score = 0.5

        # 检查是否有使用场景
        use_indicators = ["when to use", "use when", "适用场景", "使用场景"]
        for indicator in use_indicators:
            if indicator in doc.lower():
                score += 0.2
                break

        # 检查是否有步骤
        step_indicators = ["## procedure", "## steps", "## 步骤", "## 流程"]
        for indicator in step_indicators:
            if indicator in doc.lower():
                score += 0.2
                break

        # 检查是否有验证
        verify_indicators = ["## verification", "## 验证", "## check"]
        for indicator in verify_indicators:
            if indicator in doc.lower():
                score += 0.1
                break

        return min(1.0, score)

    def _check_executability(self, doc: str) -> float:
        """检查可执行性。

        好的技能应该有明确的步骤。
        """
        score = 0.3

        # 检查是否有编号步骤
        numbered_steps = re.findall(r'^\d+\.\s', doc, re.MULTILINE)
        if len(numbered_steps) >= 2:
            score += 0.4
        elif len(numbered_steps) >= 1:
            score += 0.2

        # 检查是否有列表步骤
        list_steps = re.findall(r'^[-*]\s', doc, re.MULTILINE)
        if len(list_steps) >= 2:
            score += 0.3

        return min(1.0, score)

    def _check_compression(self, doc: str) -> float:
        """检查压缩度。

        太长的技能不适合快速检索和注入。
        """
        word_count = len(doc.split())
        if word_count <= 200:
            return 1.0
        elif word_count <= 500:
            return 0.8
        elif word_count <= 1000:
            return 0.6
        elif word_count <= 1500:
            return 0.4
        else:
            return 0.2
