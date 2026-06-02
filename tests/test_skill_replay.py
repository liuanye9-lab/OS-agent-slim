"""tests/test_skill_replay.py — GroupedReplayLite 测试。"""

from __future__ import annotations

import pytest

from stable_agent.skills.replay import GroupedReplayLite


class TestGroupedReplayLite:
    """GroupedReplayLite 测试。"""

    def test_empty_runs(self):
        """空 runs。"""
        replay = GroupedReplayLite()
        episodes = replay.group_runs()
        assert episodes == []

    def test_group_similar_runs(self):
        """相似 run 能分组。"""
        runs = [
            {
                "run_id": "run_1",
                "task_type": "bug_fix",
                "tags": ["login", "frontend"],
                "outcome": "success",
            },
            {
                "run_id": "run_2",
                "task_type": "bug_fix",
                "tags": ["login", "backend"],
                "outcome": "success",
            },
            {
                "run_id": "run_3",
                "task_type": "bug_fix",
                "tags": ["login", "frontend"],
                "outcome": "failure",
            },
        ]
        replay = GroupedReplayLite(runs)
        episodes = replay.group_runs(min_group_size=2)
        assert len(episodes) > 0

    def test_different_task_type_not_grouped(self):
        """不同 task_type 不乱分。"""
        runs = [
            {"run_id": "run_1", "task_type": "bug_fix", "tags": ["test"]},
            {"run_id": "run_2", "task_type": "ui_design", "tags": ["test"]},
        ]
        replay = GroupedReplayLite(runs)
        episodes = replay.group_runs(min_group_size=2)
        # 不同 task_type 不应该分到一组
        for ep in episodes:
            assert len(ep.runs) < 2

    def test_grouped_episode_has_reason(self):
        """分组有 reason。"""
        runs = [
            {"run_id": "run_1", "task_type": "coding", "tags": ["test"], "outcome": "success"},
            {"run_id": "run_2", "task_type": "coding", "tags": ["test"], "outcome": "success"},
        ]
        replay = GroupedReplayLite(runs)
        episodes = replay.group_runs(min_group_size=2)
        if episodes:
            assert episodes[0].reason != ""

    def test_generate_replay_report(self):
        """生成重放报告。"""
        runs = [
            {"run_id": "run_1", "task_type": "coding", "tags": ["test"], "outcome": "success"},
            {"run_id": "run_2", "task_type": "coding", "tags": ["test"], "outcome": "success"},
        ]
        replay = GroupedReplayLite(runs)
        episodes = replay.group_runs(min_group_size=2)
        report = replay.generate_replay_report(episodes)
        assert report["ok"] is True
        assert "total_groups" in report
