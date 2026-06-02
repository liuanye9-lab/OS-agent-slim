"""stable_agent.skills.attribution — SkillAttribution 技能归因。

判断一个 skill 是否真的有帮助。
第一版使用弱归因，不做严格因果推断。
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from stable_agent.skills.repo import SkillRepo

logger = logging.getLogger(__name__)


@dataclass
class SkillAttributionSummary:
    """技能归因摘要。"""

    skill_id: str = ""
    skill_name: str = ""
    usage_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    success_rate: float = 0.0
    avg_token_cost: float = 0.0
    rollback_count: int = 0
    quality_score: float = 0.0
    stale_score: float = 0.0
    pollution_risk_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "skill_name": self.skill_name,
            "usage_count": self.usage_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": self.success_rate,
            "avg_token_cost": self.avg_token_cost,
            "rollback_count": self.rollback_count,
            "quality_score": self.quality_score,
            "stale_score": self.stale_score,
            "pollution_risk_score": self.pollution_risk_score,
        }


@dataclass
class RepoAttributionSummary:
    """技能库归因摘要。"""

    total_skills: int = 0
    active_skills: int = 0
    total_usage: int = 0
    avg_success_rate: float = 0.0
    avg_quality_score: float = 0.0
    skills_with_issues: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_skills": self.total_skills,
            "active_skills": self.active_skills,
            "total_usage": self.total_usage,
            "avg_success_rate": self.avg_success_rate,
            "avg_quality_score": self.avg_quality_score,
            "skills_with_issues": self.skills_with_issues,
        }


class SkillAttribution:
    """技能归因。

    弱归因：
    - run 使用了 skill
    - run 成功
    - token 降低
    - 用户无负反馈

    Attributes:
        repo: SkillRepo 实例。
    """

    def __init__(self, repo: SkillRepo) -> None:
        """初始化归因模块。

        Args:
            repo: SkillRepo 实例。
        """
        self.repo = repo

    def record_skill_usage(
        self,
        run_id: str,
        skill_id: str,
        outcome: str = "",
        token_cost: int = 0,
        steps: int = 0,
        task_id: str = "",
    ) -> None:
        """记录技能使用。

        Args:
            run_id: 运行 ID。
            skill_id: 技能 ID。
            outcome: 结果 (success/failure)。
            token_cost: Token 消耗。
            steps: 步骤数。
            task_id: 任务 ID。
        """
        # 计算归因分数（弱归因）
        attribution_score = 0.5
        if outcome == "success":
            attribution_score = 0.8
        elif outcome == "failure":
            attribution_score = 0.2

        self.repo.record_usage(
            run_id=run_id,
            skill_id=skill_id,
            outcome=outcome,
            token_cost=token_cost,
            attribution_score=attribution_score,
            task_id=task_id,
        )

    def compute_skill_summary(self, skill_id: str) -> SkillAttributionSummary:
        """计算技能归因摘要。

        Args:
            skill_id: 技能 ID。

        Returns:
            归因摘要。
        """
        skill = self.repo.get_skill(skill_id)
        if skill is None:
            return SkillAttributionSummary()

        # 计算成功率
        total = skill.success_count + skill.failure_count
        success_rate = skill.success_count / total if total > 0 else 0.0

        # 计算 stale score (越久没用越高)
        stale_score = 0.0
        if skill.last_used_at:
            days_since_use = (time.time() - skill.last_used_at) / 86400
            if days_since_use > 30:
                stale_score = min(1.0, days_since_use / 90)
        else:
            stale_score = 0.8

        # 计算 pollution risk
        pollution_risk = 0.0
        if skill.failure_count > skill.success_count * 2:
            pollution_risk = 0.8
        elif skill.failure_count > skill.success_count:
            pollution_risk = 0.5

        return SkillAttributionSummary(
            skill_id=skill.skill_id,
            skill_name=skill.name,
            usage_count=skill.usage_count,
            success_count=skill.success_count,
            failure_count=skill.failure_count,
            success_rate=success_rate,
            avg_token_cost=0.0,  # TODO: 从 usage 表计算
            rollback_count=0,  # TODO: 从 curation_events 计算
            quality_score=skill.quality_score,
            stale_score=stale_score,
            pollution_risk_score=pollution_risk,
        )

    def compute_repo_summary(self) -> RepoAttributionSummary:
        """计算技能库归因摘要。

        Returns:
            技能库归因摘要。
        """
        health = self.repo.health_check()
        skills = self.repo.list_skills(status="active", limit=10000)

        total_success = sum(s.success_count for s in skills)
        total_failure = sum(s.failure_count for s in skills)
        total = total_success + total_failure

        avg_success_rate = total_success / total if total > 0 else 0.0
        avg_quality = sum(s.quality_score for s in skills) / len(skills) if skills else 0.0

        # 有问题的技能
        issues_count = 0
        for s in skills:
            if s.failure_count > s.success_count * 2:
                issues_count += 1
            elif s.quality_score < 0.3:
                issues_count += 1

        return RepoAttributionSummary(
            total_skills=health.get("active_skills", 0) + health.get("archived_skills", 0),
            active_skills=health.get("active_skills", 0),
            total_usage=health.get("usage_records", 0),
            avg_success_rate=avg_success_rate,
            avg_quality_score=avg_quality,
            skills_with_issues=issues_count,
        )
