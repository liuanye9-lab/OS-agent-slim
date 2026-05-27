"""PatchApplier 单元测试。

测试 patch 应用的四种操作、保护区保护和边界情况。
"""

from __future__ import annotations

from datetime import datetime

import pytest

from stable_agent.skill_optimizer.models import (
    SkillDocument,
    SkillEdit,
    SkillPatch,
)
from stable_agent.skill_optimizer.patch_applier import PatchApplier


# ============================================================================
# Helpers
# ============================================================================


def make_skill(content: str = "# Test Skill\n\nSome content.") -> SkillDocument:
    """创建测试用 SkillDocument。"""
    return SkillDocument(
        id="test-skill",
        version="v1.0",
        content=content,
        status="current",
    )


def make_patch(*edits: SkillEdit, patch_id: str = "p-test") -> SkillPatch:
    """创建测试用 SkillPatch。"""
    return SkillPatch(id=patch_id, edits=list(edits))


def make_edit(
    edit_id: str = "e-1",
    op: str = "append",
    target: str | None = None,
    content: str | None = None,
    source_type: str = "failure",
) -> SkillEdit:
    """创建测试用 SkillEdit。"""
    return SkillEdit(
        id=edit_id,
        op=op,
        target=target,
        content=content,
        source_type=source_type,
    )


# ============================================================================
# Tests
# ============================================================================


class TestAppendEdit:
    """测试 append 操作。"""

    def test_append_edit(self):
        """追加内容到文档末尾。"""
        applier = PatchApplier()
        skill = make_skill("Line 1\nLine 2")
        edit = make_edit(op="append", content="Line 3\nLine 4")
        patch = make_patch(edit)

        result = applier.apply(skill, patch)

        assert "Line 1" in result.content
        assert "Line 2" in result.content
        assert "Line 3" in result.content
        assert "Line 4" in result.content
        assert result.content.endswith("Line 4")

    def test_append_to_empty_content(self):
        """追加到空内容。"""
        applier = PatchApplier()
        skill = make_skill("")
        edit = make_edit(op="append", content="New content")
        patch = make_patch(edit)

        result = applier.apply(skill, patch)
        assert result.content == "New content"

    def test_append_edit_no_content(self):
        """append 编辑没有 content 时跳过。"""
        applier = PatchApplier()
        skill = make_skill("Original")
        edit = make_edit(op="append", content=None)
        patch = make_patch(edit)

        result = applier.apply(skill, patch)
        assert result.content == "Original"


class TestInsertAfterEdit:
    """测试 insert_after 操作。"""

    def test_insert_after_edit(self):
        """在匹配行后插入内容。"""
        applier = PatchApplier()
        skill = make_skill("Line A\nLine B\nLine C")
        edit = make_edit(
            op="insert_after",
            target="Line A",
            content="Inserted Line",
        )
        patch = make_patch(edit)

        result = applier.apply(skill, patch)

        assert "Line A" in result.content
        assert "Inserted Line" in result.content
        # 验证插入位置：Inserted Line 应在 Line A 之后
        idx_a = result.content.index("Line A")
        idx_inserted = result.content.index("Inserted Line")
        assert idx_inserted > idx_a

    def test_insert_after_target_not_found(self):
        """target 未找到时跳过并保持原内容。"""
        applier = PatchApplier()
        skill = make_skill("Line 1\nLine 2")
        edit = make_edit(
            op="insert_after",
            target="Non-existent",
            content="Should not appear",
        )
        patch = make_patch(edit)

        result = applier.apply(skill, patch)
        assert result.content == "Line 1\nLine 2"
        assert "Should not appear" not in result.content

    def test_insert_after_no_target(self):
        """缺少 target 时跳过。"""
        applier = PatchApplier()
        skill = make_skill("Content")
        edit = make_edit(
            op="insert_after",
            target=None,
            content="Should not appear",
        )
        patch = make_patch(edit)

        result = applier.apply(skill, patch)
        assert result.content == "Content"


class TestReplaceEdit:
    """测试 replace 操作。"""

    def test_replace_edit(self):
        """精确替换匹配文本。"""
        applier = PatchApplier()
        skill = make_skill("Hello World")
        edit = make_edit(
            op="replace",
            target="World",
            content="Universe",
        )
        patch = make_patch(edit)

        result = applier.apply(skill, patch)
        assert result.content == "Hello Universe"
        assert "World" not in result.content

    def test_replace_not_found_skipped(self):
        """target 未找到时跳过。"""
        applier = PatchApplier()
        skill = make_skill("Hello World")
        edit = make_edit(
            op="replace",
            target="Mars",
            content="Venus",
        )
        patch = make_patch(edit)

        result = applier.apply(skill, patch)
        assert result.content == "Hello World"

    def test_replace_only_first_occurrence(self):
        """只替换第一个匹配项。"""
        applier = PatchApplier()
        skill = make_skill("dup dup dup")
        edit = make_edit(
            op="replace",
            target="dup",
            content="DUP",
        )
        patch = make_patch(edit)

        result = applier.apply(skill, patch)
        # 只替换第一个
        assert result.content == "DUP dup dup"


class TestDeleteEdit:
    """测试 delete 操作。"""

    def test_delete_edit(self):
        """精确删除匹配文本。"""
        applier = PatchApplier()
        skill = make_skill("Keep this. Remove this. Keep that.")
        edit = make_edit(
            op="delete",
            target="Remove this. ",
        )
        patch = make_patch(edit)

        result = applier.apply(skill, patch)
        assert "Remove this" not in result.content
        assert "Keep this" in result.content
        assert "Keep that" in result.content

    def test_delete_not_found_skipped(self):
        """target 未找到时跳过。"""
        applier = PatchApplier()
        skill = make_skill("Hello World")
        edit = make_edit(
            op="delete",
            target="Mars",
        )
        patch = make_patch(edit)

        result = applier.apply(skill, patch)
        assert result.content == "Hello World"


class TestProtectedZone:
    """测试保护区保护。"""

    def test_protected_zone_not_modified_by_normal_patch(self):
        """普通 patch 不能修改保护区内容。"""
        applier = PatchApplier()
        skill = make_skill(
            "Before.\n"
            "<!-- SLOW_UPDATE_START -->\n"
            "Protected content.\n"
            "<!-- SLOW_UPDATE_END -->\n"
            "After."
        )
        edit = make_edit(
            op="replace",
            target="Protected content.",
            content="Modified content.",
            source_type="failure",
        )
        patch = make_patch(edit)

        result = applier.apply(skill, patch)
        assert "Protected content." in result.content
        assert "Modified content." not in result.content

    def test_slow_update_can_modify_protected_zone(self):
        """slow_update 来源的编辑可以修改保护区。"""
        applier = PatchApplier()
        skill = make_skill(
            "Before.\n"
            "<!-- SLOW_UPDATE_START -->\n"
            "Protected content.\n"
            "<!-- SLOW_UPDATE_END -->\n"
            "After."
        )
        edit = make_edit(
            op="replace",
            target="Protected content.",
            content="Slow updated content.",
            source_type="slow_update",
        )
        patch = make_patch(edit)

        result = applier.apply(skill, patch)
        assert "Slow updated content." in result.content
        assert "Protected content." not in result.content

    def test_normal_patch_can_modify_unprotected_zone(self):
        """普通 patch 可以修改非保护区内容。"""
        applier = PatchApplier()
        skill = make_skill(
            "Before.\n"
            "<!-- SLOW_UPDATE_START -->\n"
            "Protected.\n"
            "<!-- SLOW_UPDATE_END -->\n"
            "After - can modify this."
        )
        edit = make_edit(
            op="replace",
            target="After - can modify this.",
            content="Modified after.",
            source_type="failure",
        )
        patch = make_patch(edit)

        result = applier.apply(skill, patch)
        assert "Modified after." in result.content


class TestMultipleEdits:
    """测试多编辑批量应用。"""

    def test_multiple_edits_in_patch(self):
        """一次应用多条编辑。"""
        applier = PatchApplier()
        skill = make_skill("Line 1\nLine 2\nLine 3")
        edit1 = make_edit("e1", op="append", content="Line 4")
        edit2 = make_edit("e2", op="replace", target="Line 2", content="Line 2 modified")
        patch = make_patch(edit1, edit2)

        result = applier.apply(skill, patch)
        assert "Line 1" in result.content
        assert "Line 2 modified" in result.content
        assert "Line 3" in result.content
        assert "Line 4" in result.content

    def test_apply_returns_new_document(self):
        """apply 返回新的 SkillDocument，不修改原文档。"""
        applier = PatchApplier()
        original_content = "Original content."
        skill = make_skill(original_content)
        edit = make_edit(op="append", content="New content")
        patch = make_patch(edit)

        result = applier.apply(skill, patch)

        # 原文档不变
        assert skill.content == original_content
        # 新文档已修改
        assert result.content != original_content
        assert "New content" in result.content
        # 新文档状态为 draft
        assert result.status == "draft"
        # id 和 version 不变
        assert result.id == skill.id
        assert result.version == skill.version

    def test_apply_with_different_source_types(self):
        """不同 source_type 均可正常应用。"""
        applier = PatchApplier()
        skill = make_skill("Start\nMiddle\nEnd")
        e1 = make_edit("e1", op="append", content="Extra", source_type="success")
        e2 = make_edit("e2", op="replace", target="Middle", content="Center", source_type="failure")
        e3 = make_edit("e3", op="insert_after", target="Start", content="After Start", source_type="manual")
        patch = make_patch(e1, e2, e3)

        result = applier.apply(skill, patch)
        assert "Center" in result.content
        assert "After Start" in result.content
        assert "Extra" in result.content
