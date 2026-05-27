"""PatchMerger 单元测试。

测试 patch 合并的去重、冲突解决、排序和已拒绝过滤功能。
"""

from __future__ import annotations

import pytest

from stable_agent.skill_optimizer.models import (
    SkillEdit,
    SkillPatch,
)
from stable_agent.skill_optimizer.patch_merger import PatchMerger


# ============================================================================
# Helpers
# ============================================================================


def make_edit(
    edit_id: str = "e-1",
    op: str = "append",
    target: str | None = None,
    content: str | None = None,
    source_type: str = "failure",
    support_count: int = 0,
) -> SkillEdit:
    """创建测试用 SkillEdit。"""
    return SkillEdit(
        id=edit_id,
        op=op,
        target=target,
        content=content,
        source_type=source_type,
        support_count=support_count,
    )


def make_patch(
    patch_id: str = "p-1",
    edits: list[SkillEdit] | None = None,
    source_rollout_ids: list[str] | None = None,
) -> SkillPatch:
    """创建测试用 SkillPatch。"""
    return SkillPatch(
        id=patch_id,
        edits=edits or [],
        source_rollout_ids=source_rollout_ids or [],
    )


# ============================================================================
# Tests
# ============================================================================


class TestMergeDeduplicates:
    """测试去重功能。"""

    def test_merge_deduplicates(self):
        """相同 op+target 的编辑去重，保留 support_count 最高的。"""
        merger = PatchMerger()

        e1 = make_edit("e1", op="replace", target="old", content="new1", support_count=3)
        e2 = make_edit("e2", op="replace", target="old", content="new2", support_count=1)
        # e1 和 e2 相同 op+target → 去重保留 support_count 高的 e1

        failure = make_patch("pf", edits=[e1])
        success = make_patch("ps", edits=[e2])

        result = merger.merge(failure, success)
        # 应该只有 1 条（去重后）
        assert len(result.edits) == 1
        assert result.edits[0].id == "e1"
        assert result.edits[0].support_count == 3

    def test_merge_append_dedup_by_content(self):
        """append 编辑用 content 前 50 字符去重。"""
        merger = PatchMerger()

        # 内容需超过 50 字符，使截断后前 50 字符一致
        shared_prefix = "Same prefix for dedup test - this content exceeds 50 chars to ensure truncation works properly"
        e1 = make_edit("e1", op="append", content=shared_prefix, support_count=2)
        e2 = make_edit("e2", op="append", content=shared_prefix + " with additional trailing text", support_count=1)

        failure = make_patch("pf", edits=[e1])
        success = make_patch("ps", edits=[e2])

        result = merger.merge(failure, success)
        assert len(result.edits) == 1
        assert result.edits[0].id == "e1"  # 保留 support_count 高的


class TestMergeConflictResolution:
    """测试冲突解决。"""

    def test_merge_conflict_resolution(self):
        """同一 target 有 replace + 其他操作 → 保留 replace。"""
        merger = PatchMerger()

        e1 = make_edit("e1", op="replace", target="same target", content="replaced")
        e2 = make_edit("e2", op="delete", target="same target")

        failure = make_patch("pf", edits=[e1])
        success = make_patch("ps", edits=[e2])

        result = merger.merge(failure, success)
        # 同一 target，replace 优先
        assert len(result.edits) == 1
        assert result.edits[0].op == "replace"

    def test_merge_different_targets_no_conflict(self):
        """不同 target 的编辑都保留。"""
        merger = PatchMerger()

        e1 = make_edit("e1", op="replace", target="target A", content="new A")
        e2 = make_edit("e2", op="replace", target="target B", content="new B")

        failure = make_patch("pf", edits=[e1])
        success = make_patch("ps", edits=[e2])

        result = merger.merge(failure, success)
        assert len(result.edits) == 2


class TestMergeFailureBeforeSuccess:
    """测试 failure 编辑排在 success 前面。"""

    def test_merge_failure_before_success(self):
        """failure 来源的编辑排在 success 前面。"""
        merger = PatchMerger()

        e_success = make_edit("e-s", op="append", content="Success edit", source_type="success")
        e_failure = make_edit("e-f", op="append", content="Failure edit", source_type="failure")

        failure = make_patch("pf", edits=[e_failure])
        success = make_patch("ps", edits=[e_success])

        result = merger.merge(failure, success)
        assert len(result.edits) == 2
        # failure 应排在 success 前面
        assert result.edits[0].source_type == "failure"
        assert result.edits[1].source_type == "success"


class TestMergeFiltersRejected:
    """测试过滤已拒绝编辑。"""

    def test_merge_filters_rejected(self):
        """与已拒绝编辑相似的编辑被过滤。"""
        # 构造一个简单的 mock rejected buffer
        class MockRejectedBuffer:
            def is_similar_to_rejected(self, edit):
                # 拒绝 id 为 "e-bad" 的编辑
                return edit.id == "e-bad"

        mock_buffer = MockRejectedBuffer()
        merger = PatchMerger(rejected_buffer=mock_buffer)

        e_good = make_edit("e-good", op="append", content="Good edit")
        e_bad = make_edit("e-bad", op="append", content="Bad edit")

        failure = make_patch("pf", edits=[e_bad])
        success = make_patch("ps", edits=[e_good])

        result = merger.merge(failure, success)
        assert len(result.edits) == 1
        assert result.edits[0].id == "e-good"


class TestMergeEdgeCases:
    """测试边界情况。"""

    def test_merge_empty_patches(self):
        """两个 patch 都为空时返回空结果。"""
        merger = PatchMerger()
        result = merger.merge(None, None)
        assert len(result.edits) == 0
        assert "为空" in result.reasoning

    def test_merge_single_patch(self):
        """只有 failure patch 时直接返回。"""
        merger = PatchMerger()

        e1 = make_edit("e1", op="append", content="Only edit")
        failure = make_patch("pf", edits=[e1])

        result = merger.merge(failure, None)
        assert len(result.edits) == 1
        assert result.edits[0].id == "e1"

    def test_merge_only_success_patch(self):
        """只有 success patch 时直接返回。"""
        merger = PatchMerger()

        e1 = make_edit("e1", op="append", content="Success only")
        success = make_patch("ps", edits=[e1])

        result = merger.merge(None, success)
        assert len(result.edits) == 1
        assert result.edits[0].id == "e1"

    def test_merge_preserves_source_rollout_ids(self):
        """合并后保留源 rollout ID。"""
        merger = PatchMerger()

        e1 = make_edit("e1", op="append", content="test")
        failure = make_patch("pf", edits=[e1], source_rollout_ids=["r1", "r2"])
        success = make_patch("ps", edits=[], source_rollout_ids=["r3"])

        result = merger.merge(failure, success)
        assert "r1" in result.source_rollout_ids
        assert "r2" in result.source_rollout_ids
        assert "r3" in result.source_rollout_ids


class TestDedupInternals:
    """测试去重内部逻辑。"""

    def test_compute_support_count(self):
        """验证 support_count 计算正确。"""
        merger = PatchMerger()
        all_edits = [
            make_edit("e1", op="replace", target="X", content="a"),
            make_edit("e2", op="replace", target="X", content="b"),
            make_edit("e3", op="replace", target="Y", content="c"),
        ]

        # e1 和 e2 有相同 target "X"，所以 e1 的支持数为 2
        count = merger._compute_support_count(all_edits[0], all_edits)
        assert count == 2

        # e3 的 target "Y" 是唯一的
        count = merger._compute_support_count(all_edits[2], all_edits)
        assert count == 1
