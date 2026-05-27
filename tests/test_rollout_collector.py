"""RolloutCollector 单元测试。

测试轨迹采集、保存加载、成功/失败拆分功能。
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from stable_agent.skill_optimizer.models import RolloutTrajectory
from stable_agent.skill_optimizer.rollout_collector import RolloutCollector


# ============================================================================
# Helpers
# ============================================================================


def make_trajectory(
    traj_id: str = "r1",
    task_input: str = "test task",
    task_type: str = "general_qa",
    user_feedback: str = "unknown",
    overall_score: float | None = None,
    created_at: datetime | None = None,
) -> RolloutTrajectory:
    """创建测试用 RolloutTrajectory。"""
    eval_scores: dict[str, float] = {}
    if overall_score is not None:
        eval_scores["overall_score"] = overall_score

    return RolloutTrajectory(
        id=traj_id,
        task_input=task_input,
        task_type=task_type,
        user_feedback=user_feedback,  # type: ignore[arg-type]
        eval_scores=eval_scores,
        created_at=created_at or datetime.now(),
    )


# ============================================================================
# Test: collect_from_workflow_run
# ============================================================================


class TestCollectFromWorkflowRun:
    """测试从 workflow run 采集轨迹。"""

    def test_collect_with_none_orchestrator(self):
        """orchestrator 为 None 时返回最小轨迹。"""
        collector = RolloutCollector(storage_dir=tempfile.mkdtemp())
        result = collector.collect_from_workflow_run("run-123", orchestrator=None)

        assert result is not None
        assert result.id.startswith("minimal-")
        assert result.task_type == "general_qa"
        assert result.user_feedback == "unknown"

    def test_collect_minimal_trajectory_has_timestamp(self):
        """最小轨迹有 created_at 时间戳。"""
        collector = RolloutCollector(storage_dir=tempfile.mkdtemp())
        before = datetime.now()
        result = collector.collect_from_workflow_run("run-abc", orchestrator=None)
        after = datetime.now()

        assert result is not None
        assert before <= result.created_at <= after

    def test_collect_returns_none_on_exception(self):
        """采集异常时返回 None。"""
        collector = RolloutCollector(storage_dir=tempfile.mkdtemp())

        # 创建一个有问题的 orchestrator（缺少 storage 属性但访问会抛异常）
        class BadOrchestrator:
            @property
            def storage(self):
                raise RuntimeError("Simulated storage failure")

        result = collector.collect_from_workflow_run("run-err", orchestrator=BadOrchestrator())
        assert result is None


# ============================================================================
# Test: save / load
# ============================================================================


class TestSaveAndLoad:
    """测试轨迹保存和加载。"""

    def test_save_and_load_roundtrip(self):
        """保存后加载的轨迹与原始一致。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = RolloutCollector(storage_dir=tmpdir)

            traj = make_trajectory(
                traj_id="test-save-load",
                task_input="Write a function",
                task_type="code_generation",
                user_feedback="accepted",
                overall_score=0.9,
            )

            collector.save_rollout(traj)

            # 加载
            loaded = collector.load_recent_rollouts(limit=10)

            assert len(loaded) == 1
            assert loaded[0].id == "test-save-load"
            assert loaded[0].task_input == "Write a function"
            assert loaded[0].task_type == "code_generation"
            assert loaded[0].user_feedback == "accepted"
            assert loaded[0].eval_scores["overall_score"] == 0.9

    def test_save_creates_json_file(self):
        """保存后 JSON 文件存在。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = RolloutCollector(storage_dir=tmpdir)
            traj = make_trajectory(traj_id="file-check")

            collector.save_rollout(traj)

            file_path = Path(tmpdir) / "file-check.json"
            assert file_path.exists()

            with open(file_path) as f:
                data = json.load(f)
            assert data["id"] == "file-check"

    def test_load_from_empty_dir(self):
        """空目录加载返回空列表。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = RolloutCollector(storage_dir=tmpdir)
            result = collector.load_recent_rollouts(limit=50)
            assert result == []

    def test_load_respects_limit(self):
        """加载时尊重 limit 参数。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = RolloutCollector(storage_dir=tmpdir)
            for i in range(10):
                traj = make_trajectory(traj_id=f"r{i}")
                collector.save_rollout(traj)

            result = collector.load_recent_rollouts(limit=3)
            assert len(result) <= 3

    def test_load_skips_invalid_files(self):
        """加载时跳过无效 JSON 文件。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = RolloutCollector(storage_dir=tmpdir)

            # 写入有效轨迹
            traj = make_trajectory(traj_id="valid")
            collector.save_rollout(traj)

            # 写入无效 JSON
            invalid_path = Path(tmpdir) / "invalid.json"
            invalid_path.write_text("not valid json")

            result = collector.load_recent_rollouts(limit=50)
            assert len(result) == 1
            assert result[0].id == "valid"

    def test_load_returns_sorted_by_created_at_desc(self):
        """加载的轨迹按 created_at 降序排列。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = RolloutCollector(storage_dir=tmpdir)

            t1 = make_trajectory(traj_id="old", created_at=datetime(2024, 1, 1))
            t2 = make_trajectory(traj_id="new", created_at=datetime(2024, 6, 1))
            t3 = make_trajectory(traj_id="mid", created_at=datetime(2024, 3, 1))

            collector.save_rollout(t1)
            collector.save_rollout(t2)
            collector.save_rollout(t3)

            result = collector.load_recent_rollouts(limit=50)
            ids = [r.id for r in result]
            # newest first
            assert ids[0] == "new"
            assert ids[-1] == "old"


# ============================================================================
# Test: split_success_failure
# ============================================================================


class TestSplitSuccessFailure:
    """测试成功/失败拆分逻辑。"""

    def test_split_success_by_score(self):
        """overall_score >= 0.8 → 成功。"""
        collector = RolloutCollector()
        traj = make_trajectory(traj_id="s1", overall_score=0.85)
        successes, failures = collector.split_success_failure([traj])

        assert len(successes) == 1
        assert len(failures) == 0
        assert successes[0].id == "s1"

    def test_split_failure_by_score(self):
        """overall_score < 0.65 → 失败。"""
        collector = RolloutCollector()
        traj = make_trajectory(traj_id="f1", overall_score=0.4)
        successes, failures = collector.split_success_failure([traj])

        assert len(successes) == 0
        assert len(failures) == 1
        assert failures[0].id == "f1"

    def test_split_success_by_feedback(self):
        """user_feedback == "accepted" → 成功（优先级高于 score）。"""
        collector = RolloutCollector()
        # 即使 score 低，feedback 优先
        traj = make_trajectory(traj_id="s-fb", overall_score=0.3, user_feedback="accepted")
        successes, failures = collector.split_success_failure([traj])

        assert len(successes) == 1
        assert len(failures) == 0

    def test_split_failure_by_feedback(self):
        """user_feedback == "rejected" → 失败（优先级高于 score）。"""
        collector = RolloutCollector()
        traj = make_trajectory(traj_id="f-fb", overall_score=0.9, user_feedback="rejected")
        successes, failures = collector.split_success_failure([traj])

        assert len(successes) == 0
        assert len(failures) == 1

    def test_split_unknown_mid_range_is_neither(self):
        """中间态（0.65 <= score < 0.8, feedback=unknown）不进入任何组。"""
        collector = RolloutCollector()
        traj = make_trajectory(traj_id="mid", overall_score=0.7)
        successes, failures = collector.split_success_failure([traj])

        assert len(successes) == 0
        assert len(failures) == 0

    def test_split_empty_list(self):
        """空列表返回两个空列表。"""
        collector = RolloutCollector()
        successes, failures = collector.split_success_failure([])
        assert successes == []
        assert failures == []

    def test_split_mixed(self):
        """混合列表正确拆分。"""
        collector = RolloutCollector()
        trajectories = [
            make_trajectory("s1", overall_score=0.9),     # success
            make_trajectory("f1", overall_score=0.3),     # failure
            make_trajectory("s2", overall_score=0.85),    # success
            make_trajectory("mid", overall_score=0.7),    # neither
            make_trajectory("f2", overall_score=0.1),     # failure
        ]

        successes, failures = collector.split_success_failure(trajectories)

        assert len(successes) == 2
        assert len(failures) == 2
        success_ids = {r.id for r in successes}
        assert success_ids == {"s1", "s2"}
        failure_ids = {r.id for r in failures}
        assert failure_ids == {"f1", "f2"}
