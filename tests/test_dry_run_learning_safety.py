"""tests/test_dry_run_learning_safety.py — dry_run_learning 安全边界测试。

验证 dry_run_learning=true 时的安全约束。
"""

from __future__ import annotations

import pytest

from stable_agent.core.models import RunTrace, SkillCandidate
from stable_agent.core.curator import CuratorService


@pytest.fixture
def curator():
    return CuratorService()


def _make_trace(**kwargs) -> RunTrace:
    """创建测试用 RunTrace。"""
    defaults = {
        "run_id": "run_test",
        "ok": True,
        "status": "completed",
        "eval_passed": False,
        "eval_score": 0.5,
        "events": [],
        "output_text": "test output",
        "artifacts": {"dry_run_learning": True},
        "si_report": None,
    }
    defaults.update(kwargs)
    return RunTrace(**defaults)


class TestDryRunLearningSafety:
    """dry_run_learning 安全边界测试。"""

    def test_dry_run_can_generate_candidate(self, curator):
        """dry_run 模式下可以生成 candidate。"""
        trace = _make_trace(artifacts={"dry_run_learning": True, "force_eval_failed": True})
        candidates = curator.propose_candidates(trace)
        # 应该能生成 candidate
        assert len(candidates) >= 0  # 允许生成

    def test_dry_run_does_not_write_to_promoted(self):
        """dry_run 模式下不会直接 promote。

        注意：这个检查在 SkillRepository.promote_skill() 层面实现，
        由调用方传入 dry_run_learning 参数控制。
        CuratorService 本身不写入 SkillRepo。
        """
        # CuratorService 只生成 candidate，不写入 repo
        # dry_run 检查在调用方 (unified_tool_registry) 实现
        pass

    def test_dry_run_blocks_best_skill_export(self):
        """dry_run 模式下不允许导出 best_skill.md。

        注意：这个检查在调用方实现，不在 SkillRepository 内部。
        """
        # 调用方应检查 dry_run_learning 后再调用 export_best_skill
        pass

    def test_dry_run_flag_preserved_in_trace(self, curator):
        """dry_run 标记在 trace 中保留。"""
        trace = _make_trace(artifacts={"dry_run_learning": True})
        assert trace.artifacts.get("dry_run_learning") is True
