"""SlowMetaUpdater 单元测试。

测试慢速元更新器的触发条件、稳定性检查和更新生成逻辑。
"""

from __future__ import annotations

from datetime import datetime

import pytest

from stable_agent.skill_optimizer.models import (
    SkillDocument,
    SkillEdit,
    SkillPatch,
)
from stable_agent.skill_optimizer.slow_meta_update import SlowMetaUpdater


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def updater():
    """创建 SlowMetaUpdater 实例（min_epochs=3）。"""
    return SlowMetaUpdater(min_epochs_between_updates=3)


@pytest.fixture
def updater_strict():
    """创建严格模式 SlowMetaUpdater（min_epochs=5）。"""
    return SlowMetaUpdater(min_epochs_between_updates=5)


@pytest.fixture
def base_skill():
    """创建基线 skill。"""
    return SkillDocument(
        id="base-v1.0",
        version="v1.0",
        content=(
            "# Skill v1.0\n\n"
            "## Rules\n"
            "- Rule A: Be clear\n"
            "- Rule B: Be concise\n"
        ),
        source="manual",
    )


@pytest.fixture
def improved_skill():
    """创建改进后的 skill。"""
    return SkillDocument(
        id="improved-v1.3",
        version="v1.3",
        content=(
            "# Skill v1.3\n\n"
            "## Rules\n"
            "- Rule A: Be clear and structured\n"
            "- Rule B: Be concise\n"
            "<!-- SLOW_UPDATE_START -->\n"
            "## Protected Zone\n"
            "- Long-term pattern: structured wins\n"
            "<!-- SLOW_UPDATE_END -->\n"
        ),
        source="auto-optimize",
    )


@pytest.fixture
def stable_results():
    """创建稳定的长期结果。"""
    return [
        {"epoch": 1, "accepted_count": 2, "rejected_count": 1, "avg_score": 0.75},
        {"epoch": 2, "accepted_count": 3, "rejected_count": 1, "avg_score": 0.78},
        {"epoch": 3, "accepted_count": 3, "rejected_count": 0, "avg_score": 0.80},
    ]


@pytest.fixture
def unstable_results():
    """创建不稳定的长期结果。"""
    return [
        {"epoch": 1, "accepted_count": 5, "rejected_count": 0, "avg_score": 0.90},
        {"epoch": 2, "accepted_count": 1, "rejected_count": 4, "avg_score": 0.30},
        {"epoch": 3, "accepted_count": 4, "rejected_count": 1, "avg_score": 0.85},
    ]


# ============================================================================
# 测试：不触发更新
# ============================================================================


class TestNoUpdateConditions:
    """测试不触发慢更新的条件。"""

    def test_no_update_when_insufficient_data(
        self, updater, base_skill, improved_skill
    ):
        """数据不足时不生成更新。"""
        results = [
            {"epoch": 1, "accepted_count": 2, "rejected_count": 0, "avg_score": 0.80},
        ]
        patch = updater.generate_slow_update(
            base_skill, improved_skill, results
        )
        assert patch is None

    def test_no_update_when_unstable(
        self, updater, base_skill, improved_skill, unstable_results
    ):
        """结果不稳定时不生成更新。"""
        patch = updater.generate_slow_update(
            base_skill, improved_skill, unstable_results
        )
        assert patch is None

    def test_no_update_when_strict_min_not_met(
        self, updater_strict, base_skill, improved_skill, stable_results
    ):
        """严格 min_epochs 未满足时不生成更新（只有 3 个 epoch，要求 5 个）。"""
        patch = updater_strict.generate_slow_update(
            base_skill, improved_skill, stable_results
        )
        assert patch is None


# ============================================================================
# 测试：触发更新
# ============================================================================


class TestGeneratesUpdate:
    """测试触发慢更新。"""

    def test_generates_update_when_stable(
        self, updater, base_skill, improved_skill, stable_results
    ):
        """稳定的长期结果应触发更新。"""
        patch = updater.generate_slow_update(
            base_skill, improved_skill, stable_results
        )
        assert patch is not None
        assert isinstance(patch, SkillPatch)
        assert len(patch.edits) > 0

    def test_slow_update_source_type(
        self, updater, base_skill, improved_skill, stable_results
    ):
        """慢更新的编辑应标记 source_type='slow_update'。"""
        patch = updater.generate_slow_update(
            base_skill, improved_skill, stable_results
        )
        assert patch is not None
        for edit in patch.edits:
            assert edit.source_type == "slow_update"

    def test_slow_update_risk_level_low(
        self, updater, base_skill, improved_skill, stable_results
    ):
        """慢更新的编辑应标记 risk_level='low'。"""
        patch = updater.generate_slow_update(
            base_skill, improved_skill, stable_results
        )
        assert patch is not None
        for edit in patch.edits:
            assert edit.risk_level == "low"


# ============================================================================
# 测试：稳定性检查
# ============================================================================


class TestStabilityCheck:
    """测试 _is_stable 方法。"""

    def test_is_stable_with_low_variance(self, updater):
        """低方差数据应判定为稳定。"""
        results = [
            {"epoch": 1, "accepted_count": 3, "rejected_count": 1, "avg_score": 0.80},
            {"epoch": 2, "accepted_count": 3, "rejected_count": 0, "avg_score": 0.82},
            {"epoch": 3, "accepted_count": 4, "rejected_count": 0, "avg_score": 0.81},
        ]
        assert updater._is_stable(results) is True

    def test_is_stable_with_high_variance(self, updater):
        """高方差数据应判定为不稳定。"""
        results = [
            {"epoch": 1, "accepted_count": 5, "rejected_count": 0, "avg_score": 0.95},
            {"epoch": 2, "accepted_count": 1, "rejected_count": 4, "avg_score": 0.20},
            {"epoch": 3, "accepted_count": 3, "rejected_count": 1, "avg_score": 0.60},
        ]
        assert updater._is_stable(results) is False

    def test_is_stable_insufficient_data(self, updater):
        """数据不足时无法判定稳定。"""
        results = [
            {"epoch": 1, "accepted_count": 3, "rejected_count": 0, "avg_score": 0.80},
        ]
        assert updater._is_stable(results) is False
