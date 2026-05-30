"""test_memory_update_candidate — 测试 MemoryUpdateCandidate 生命周期。"""
import pytest
from stable_agent.self_improvement.memory_update_candidate import (
    MemoryUpdateCandidate,
    MemoryUpdateStatus,
    MemoryUpdateStore,
)


class TestMemoryUpdateCandidate:
    """MemoryUpdateCandidate 核心测试。"""

    def test_cannot_promote_without_source_run_id(self):
        """缺少 source_run_id 不能晋升。"""
        cand = MemoryUpdateCandidate(
            source_run_id="",
            content="测试记忆",
        )
        can, reason = cand.can_promote()
        assert not can
        assert "source_run_id" in reason.lower()

    def test_cannot_promote_without_validation(self):
        """缺少 validation_report_id 不能晋升。"""
        cand = MemoryUpdateCandidate(
            source_run_id="run-001",
            content="测试记忆",
            failure_attribution="测试失败",
            human_review_id="review-001",
        )
        can, reason = cand.can_promote()
        assert not can
        assert "validation" in reason.lower()

    def test_cannot_promote_unless_validated(self):
        """非 validated 状态不能晋升。"""
        cand = MemoryUpdateCandidate(
            source_run_id="run-001",
            content="测试记忆",
            failure_attribution="测试失败",
            validation_report_id="val-001",
            human_review_id="review-001",
            status=MemoryUpdateStatus.CANDIDATE,
        )
        can, reason = cand.can_promote()
        assert not can
        assert "状态" in reason

    def test_can_promote_when_all_conditions_met(self):
        """所有条件满足时应可晋升。"""
        cand = MemoryUpdateCandidate(
            source_run_id="run-001",
            content="测试记忆",
            failure_attribution="测试失败",
            validation_report_id="val-001",
            human_review_id="review-001",
            status=MemoryUpdateStatus.VALIDATED,
        )
        can, reason = cand.can_promote()
        assert can
        assert reason == ""


class TestMemoryUpdateStore:
    """MemoryUpdateStore 核心测试。"""

    def setup_method(self):
        self.store = MemoryUpdateStore()

    def test_add_requires_source_run_id(self):
        """添加需要 source_run_id。"""
        cand = MemoryUpdateCandidate(source_run_id="", content="test")
        with pytest.raises(ValueError):
            self.store.add(cand)

    def test_add_requires_content(self):
        """添加需要内容。"""
        cand = MemoryUpdateCandidate(source_run_id="run-001", content="")
        with pytest.raises(ValueError):
            self.store.add(cand)

    def test_add_and_get(self):
        """添加后可获取。"""
        cand = MemoryUpdateCandidate(
            source_run_id="run-001",
            content="测试记忆",
            failure_attribution="测试",
        )
        self.store.add(cand)
        assert self.store.get(cand.update_id) is not None

    def test_lifecycle_candidate_to_promoted(self):
        """完整生命周期: candidate → validated → promoted。"""
        cand = MemoryUpdateCandidate(
            source_run_id="run-001",
            content="测试记忆",
            failure_attribution="测试失败",
            status=MemoryUpdateStatus.CANDIDATE,
        )
        self.store.add(cand)

        # validate
        self.store.validate(cand.update_id, "val-001")
        # set review
        cand = self.store.get(cand.update_id)
        cand.human_review_id = "review-001"

        # promote
        promoted = self.store.promote(cand.update_id)
        assert promoted is not None
        assert promoted.status == MemoryUpdateStatus.PROMOTED

    def test_promote_fails_before_validation(self):
        """未验证不能晋升。"""
        cand = MemoryUpdateCandidate(
            source_run_id="run-001",
            content="测试记忆",
            failure_attribution="测试",
            human_review_id="review-001",  # 缺少 validation_report_id
        )
        self.store.add(cand)
        promoted = self.store.promote(cand.update_id)
        assert promoted is None

    def test_reject(self):
        """拒绝后状态变为 rejected。"""
        cand = MemoryUpdateCandidate(
            source_run_id="run-001",
            content="测试记忆",
        )
        self.store.add(cand)
        self.store.reject(cand.update_id, "不合理")
        cand = self.store.get(cand.update_id)
        assert cand.status == MemoryUpdateStatus.REJECTED

    def test_expire_old(self):
        """过期候选应被标记。"""
        import time
        cand = MemoryUpdateCandidate(
            source_run_id="run-001",
            content="测试记忆",
            created_at=time.time() - 200 * 3600,  # 200小时前
        )
        self.store.add(cand)
        count = self.store.expire_old(max_age_hours=168)
        assert count == 1
        assert cand.status == MemoryUpdateStatus.EXPIRED

    def test_list_by_status(self):
        """按状态过滤应正确。"""
        for i in range(3):
            self.store.add(MemoryUpdateCandidate(
                source_run_id=f"run-{i}",
                content=f"记忆{i}",
            ))
        assert len(self.store.list_by_status(MemoryUpdateStatus.CANDIDATE)) == 3
