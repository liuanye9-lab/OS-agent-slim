"""SuccessFailureAnalyzer 单元测试。

测试失败分析和成功分析的补丁生成。
"""

from __future__ import annotations

from datetime import datetime

import pytest

from stable_agent.skill_optimizer.models import (
    RolloutTrajectory,
    SkillDocument,
    SkillPatch,
)
from stable_agent.skill_optimizer.success_failure_analyzer import (
    SuccessFailureAnalyzer,
)


# ============================================================================
# Helpers
# ============================================================================


def make_trajectory(
    traj_id: str = "r1",
    task_type: str = "",
    eval_scores: dict[str, float] | None = None,
) -> RolloutTrajectory:
    """创建测试用 RolloutTrajectory。"""
    return RolloutTrajectory(
        id=traj_id,
        task_input="test input",
        task_type=task_type,
        eval_scores=eval_scores or {},
        created_at=datetime.now(),
    )


def make_skill_document(
    doc_id: str = "skill-1",
    version: str = "v1.0",
    content: str = "# Test Skill\n\nSome content.",
) -> SkillDocument:
    """创建测试用 SkillDocument。"""
    return SkillDocument(
        id=doc_id,
        version=version,
        content=content,
    )


# ============================================================================
# Tests: analyze_failures
# ============================================================================


class TestAnalyzeFailures:
    """测试失败分析。"""

    def test_empty_trajectories_returns_empty_patch(self):
        """空轨迹列表返回空 patch。"""
        analyzer = SuccessFailureAnalyzer()
        skill = make_skill_document()
        result = analyzer.analyze_failures([], skill)

        assert isinstance(result, SkillPatch)
        assert len(result.edits) == 0
        assert "无失败轨迹" in result.reasoning

    def test_single_trajectory_no_common_pattern(self):
        """单条轨迹不产生 edit（min_count=2）。"""
        analyzer = SuccessFailureAnalyzer()
        skill = make_skill_document()

        traj = make_trajectory("r1", eval_scores={"overall_score": 0.3, "completion_rate": 0.2})

        result = analyzer.analyze_failures([traj], skill)
        # 所有维度只有 1 条 → 没有共性模式
        assert len(result.edits) == 0

    def test_two_trajectories_same_low_dimension(self):
        """两条轨迹相同维度都低 → 产生 edit。"""
        analyzer = SuccessFailureAnalyzer()
        skill = make_skill_document()

        t1 = make_trajectory("r1", eval_scores={"overall_score": 0.3, "completion_rate": 0.2})
        t2 = make_trajectory("r2", eval_scores={"overall_score": 0.4, "completion_rate": 0.3})

        result = analyzer.analyze_failures([t1, t2], skill)
        assert len(result.edits) >= 1
        # 所有 edit 的 source_type 应为 failure
        for edit in result.edits:
            assert edit.source_type == "failure"

    def test_edit_budget_respected(self):
        """edit 数量不超过 edit_budget。"""
        analyzer = SuccessFailureAnalyzer()
        skill = make_skill_document()

        # 创建多条轨迹，每条有多个低分维度
        trajectories = []
        dims = [
            "completion_rate", "context_hit_rate", "token_efficiency",
            "hallucination_score", "user_preference_score", "retrieval_quality",
            "memory_quality", "tool_quality", "format_quality",
        ]
        for i in range(5):
            scores = {dim: 0.3 for dim in dims[: min(i + 2, len(dims))]}
            trajectories.append(make_trajectory(f"r{i}", eval_scores=scores))

        result = analyzer.analyze_failures(trajectories, skill, edit_budget=3)
        assert len(result.edits) <= 3

    def test_all_edits_have_reason_with_count(self):
        """每条 edit 的 reason 包含支持的轨迹数量。"""
        analyzer = SuccessFailureAnalyzer()
        skill = make_skill_document()

        t1 = make_trajectory("r1", eval_scores={"overall_score": 0.1, "completion_rate": 0.2})
        t2 = make_trajectory("r2", eval_scores={"overall_score": 0.2, "completion_rate": 0.15})
        t3 = make_trajectory("r3", eval_scores={"overall_score": 0.3, "completion_rate": 0.1})

        result = analyzer.analyze_failures([t1, t2, t3], skill)
        for edit in result.edits:
            assert edit.support_count >= 2
            assert len(edit.reason) > 0

    def test_edits_have_low_risk_level(self):
        """失败 edit 的 risk_level = "low"。"""
        analyzer = SuccessFailureAnalyzer()
        skill = make_skill_document()

        t1 = make_trajectory("r1", eval_scores={"overall_score": 0.2, "token_efficiency": 0.3})
        t2 = make_trajectory("r2", eval_scores={"overall_score": 0.3, "token_efficiency": 0.2})

        result = analyzer.analyze_failures([t1, t2], skill)
        for edit in result.edits:
            assert edit.risk_level == "low"


# ============================================================================
# Tests: analyze_successes
# ============================================================================


class TestAnalyzeSuccesses:
    """测试成功分析。"""

    def test_empty_trajectories_returns_empty_patch(self):
        """空轨迹列表返回空 patch。"""
        analyzer = SuccessFailureAnalyzer()
        skill = make_skill_document()
        result = analyzer.analyze_successes([], skill)

        assert isinstance(result, SkillPatch)
        assert len(result.edits) == 0

    def test_single_trajectory_no_common_pattern(self):
        """单条轨迹不产生 edit（min_count=2）。"""
        analyzer = SuccessFailureAnalyzer()
        skill = make_skill_document()

        traj = make_trajectory("r1", eval_scores={"overall_score": 0.95})

        result = analyzer.analyze_successes([traj], skill)
        assert len(result.edits) == 0

    def test_two_trajectories_common_high_dimension(self):
        """两条轨迹共同高分维度 → 产生 edit。"""
        analyzer = SuccessFailureAnalyzer()
        skill = make_skill_document()

        t1 = make_trajectory("r1", eval_scores={"overall_score": 0.95, "format_quality": 0.9})
        t2 = make_trajectory("r2", eval_scores={"overall_score": 0.92, "format_quality": 0.88})

        result = analyzer.analyze_successes([t1, t2], skill)
        assert len(result.edits) >= 1
        for edit in result.edits:
            assert edit.source_type == "success"
            assert edit.op == "append"

    def test_success_edit_budget_respected(self):
        """成功 edit 数量不超过 edit_budget。"""
        analyzer = SuccessFailureAnalyzer()
        skill = make_skill_document()

        trajectories = []
        for i in range(10):
            trajectories.append(make_trajectory(
                f"r{i}",
                eval_scores={
                    "overall_score": 0.9,
                    "format_quality": 0.9,
                    "safety_score": 0.95,
                    "completion_rate": 0.88,
                    "context_hit_rate": 0.87,
                },
            ))

        result = analyzer.analyze_successes(trajectories, skill, edit_budget=2)
        assert len(result.edits) <= 2
