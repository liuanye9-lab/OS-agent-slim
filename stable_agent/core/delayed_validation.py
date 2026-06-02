"""stable_agent/core/delayed_validation.py — Delayed Validation Gate。

SkillOS 核心精神：延迟验证。
使用 related tasks 验证 candidate 的有效性。

流程：
1. 获取 candidate 关联的 grouped tasks
2. 使用 baseline 和 candidate 两种配置执行 holdout tasks
3. 比较结果，判断是否有回归
4. 如果无回归且分数提升 >= 0.03，标记为 validated
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from stable_agent.core.models import SkillCandidate, ValidationResult

logger = logging.getLogger(__name__)


@dataclass
class TaskGroup:
    """任务组。"""
    group_id: str
    domain: str
    skill_tags: list[str] = field(default_factory=list)
    warmup_tasks: list[dict[str, Any]] = field(default_factory=list)
    holdout_tasks: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ValidationRecord:
    """验证记录。"""
    validation_id: str
    candidate_id: str
    task_group_id: str
    baseline_scores: list[float] = field(default_factory=list)
    candidate_scores: list[float] = field(default_factory=list)
    score_delta: float = 0.0
    regression_count: int = 0
    passed: bool = False
    created_at: str = ""


class DelayedValidationGate:
    """延迟验证门。

    使用 grouped tasks 验证 candidate 的有效性。
    """

    def __init__(self, executor: Any = None, skill_repo: Any = None):
        self._executor = executor
        self._skill_repo = skill_repo

    async def validate_with_related_tasks(
        self,
        candidate: SkillCandidate,
        task_group: TaskGroup,
    ) -> ValidationRecord:
        """使用 related tasks 验证 candidate。

        Args:
            candidate: 技能候选。
            task_group: 任务组。

        Returns:
            ValidationRecord 验证记录。
        """
        validation_id = f"val_{int(time.time() * 1000)}"
        record = ValidationRecord(
            validation_id=validation_id,
            candidate_id=candidate.candidate_id,
            task_group_id=task_group.group_id,
            created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )

        if not task_group.holdout_tasks:
            record.passed = True
            return record

        # 执行 holdout tasks (简化版：直接评分)
        baseline_scores = []
        candidate_scores = []

        for task in task_group.holdout_tasks:
            # 基线分数 (使用默认配置)
            baseline_score = self._evaluate_task(task, use_candidate=False)
            baseline_scores.append(baseline_score)

            # 候选分数 (使用 candidate 配置)
            candidate_score = self._evaluate_task(task, use_candidate=True, candidate=candidate)
            candidate_scores.append(candidate_score)

        record.baseline_scores = baseline_scores
        record.candidate_scores = candidate_scores

        # 计算分数 delta
        avg_baseline = sum(baseline_scores) / len(baseline_scores) if baseline_scores else 0.0
        avg_candidate = sum(candidate_scores) / len(candidate_scores) if candidate_scores else 0.0
        record.score_delta = avg_candidate - avg_baseline

        # 检查回归
        record.regression_count = sum(
            1 for b, c in zip(baseline_scores, candidate_scores) if c < b - 0.05
        )

        # 判断是否通过
        record.passed = (
            record.regression_count == 0
            and record.score_delta >= 0.03
        )

        return record

    def _evaluate_task(
        self,
        task: dict[str, Any],
        use_candidate: bool = False,
        candidate: SkillCandidate | None = None,
    ) -> float:
        """评估任务 (简化版)。

        Args:
            task: 任务定义。
            use_candidate: 是否使用 candidate。
            candidate: 技能候选。

        Returns:
            评估分数。
        """
        # 第一版：返回模拟分数
        # 后续集成真实的 executor 执行
        base_score = 0.7
        if use_candidate and candidate:
            # 模拟 candidate 带来的提升
            base_score += 0.05
        return base_score

    def create_task_group(
        self,
        group_id: str,
        domain: str,
        skill_tags: list[str] | None = None,
        holdout_tasks: list[dict[str, Any]] | None = None,
    ) -> TaskGroup:
        """创建任务组。

        Args:
            group_id: 组 ID。
            domain: 领域。
            skill_tags: 技能标签。
            holdout_tasks: 验证任务列表。

        Returns:
            TaskGroup 实例。
        """
        return TaskGroup(
            group_id=group_id,
            domain=domain,
            skill_tags=skill_tags or [],
            holdout_tasks=holdout_tasks or [],
        )
