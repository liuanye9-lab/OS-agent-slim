"""Patch 应用引擎。

将 SkillPatch 中的编辑操作应用到 SkillDocument 上，生成候选版本。
支持 4 种原子操作，包含保护区保护和编辑目标精确匹配。
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from stable_agent.skill_optimizer.models import (
    SkillDocument,
    SkillEdit,
    SkillPatch,
)
from stable_agent.skill_optimizer.prompt_contracts import PromptContracts

logger = logging.getLogger(__name__)


class PatchApplier:
    """将 SkillPatch 应用到 SkillDocument，生成候选版本。

    支持 4 种操作：append / insert_after / replace / delete。
    - replace 和 delete 必须精确匹配 target 文本才执行
    - 保护 SLOW_UPDATE_START 与 SLOW_UPDATE_END 之间的区域不被普通 patch 修改
    """

    def apply(self, skill: SkillDocument, patch: SkillPatch) -> SkillDocument:
        """应用 patch 生成新的 candidate SkillDocument。

        对原 SkillDocument 做深拷贝（复制其 content），
        依次应用 patch 中的每条编辑，返回全新的 SkillDocument。

        Args:
            skill: 原始 SkillDocument（不会被修改）。
            patch: 要应用的 SkillPatch。

        Returns:
            新的 SkillDocument：id 不变，version 不变，
            content 已修改，status="draft"。
        """
        content = skill.content

        for edit in patch.edits:
            content = self._apply_edit(content, edit)

        return SkillDocument(
            id=skill.id,
            version=skill.version,
            content=content,
            source="auto-optimize",
            parent_version=skill.version,
            status="draft",
        )

    def _apply_edit(self, content: str, edit: SkillEdit) -> str:
        """应用单条编辑到 content。

        根据 edit.op 分发到对应的处理方法。

        Args:
            content: 当前文档内容。
            edit: 要应用的编辑操作。

        Returns:
            修改后的文档内容。
        """
        # 保护区检查：非 slow_update 来源的编辑不能修改保护区
        if edit.source_type != "slow_update":
            if self._targets_protected_zone(content, edit):
                logger.warning(
                    "编辑 %s 的目标位于保护区内，已跳过 (source_type=%s)",
                    edit.id,
                    edit.source_type,
                )
                return content

        if edit.op == "append":
            return self._do_append(content, edit)
        elif edit.op == "insert_after":
            return self._do_insert_after(content, edit)
        elif edit.op == "replace":
            return self._do_replace(content, edit)
        elif edit.op == "delete":
            return self._do_delete(content, edit)
        else:
            logger.warning("未知编辑操作: %s，已跳过", edit.op)
            return content

    # ------------------------------------------------------------------
    # 四种原子操作
    # ------------------------------------------------------------------

    @staticmethod
    def _do_append(content: str, edit: SkillEdit) -> str:
        """在文档末尾追加内容。

        Args:
            content: 当前文档内容。
            edit: append 类型的编辑。

        Returns:
            追加后的文档内容。
        """
        if edit.content is None:
            logger.warning("append 编辑 %s 没有 content，已跳过", edit.id)
            return content
        if not content.strip():
            return edit.content
        return content.rstrip() + "\n\n" + edit.content

    @staticmethod
    def _do_insert_after(content: str, edit: SkillEdit) -> str:
        """在目标行之后插入内容。

        查找 edit.target 在 content 中出现的位置，
        在该行之后插入 edit.content。

        Args:
            content: 当前文档内容。
            edit: insert_after 类型的编辑。

        Returns:
            插入后的文档内容。如果 target 未找到则原样返回。
        """
        if edit.target is None or edit.content is None:
            logger.warning(
                "insert_after 编辑 %s 缺少 target 或 content，已跳过", edit.id
            )
            return content

        idx = content.find(edit.target)
        if idx == -1:
            logger.warning(
                "insert_after 编辑 %s：target 未找到，已跳过", edit.id
            )
            return content

        # 找到 target 所在行的结束位置
        line_end = content.find("\n", idx)
        if line_end == -1:
            line_end = len(content)

        # 在 target 所在行之后插入
        return (
            content[: line_end + 1]
            + edit.content
            + ("\n" if not content[line_end:].startswith("\n\n") else "")
            + content[line_end + 1:]
        )

    @staticmethod
    def _do_replace(content: str, edit: SkillEdit) -> str:
        """精确替换 target 文本为 content。

        Args:
            content: 当前文档内容。
            edit: replace 类型的编辑。

        Returns:
            替换后的文档内容。如果 target 未找到则原样返回并打印 warning。
        """
        if edit.target is None or edit.content is None:
            logger.warning(
                "replace 编辑 %s 缺少 target 或 content，已跳过", edit.id
            )
            return content

        if edit.target not in content:
            logger.warning(
                "replace 编辑 %s：target 未在文档中找到，已跳过", edit.id
            )
            return content

        return content.replace(edit.target, edit.content, 1)

    @staticmethod
    def _do_delete(content: str, edit: SkillEdit) -> str:
        """精确删除 target 文本。

        Args:
            content: 当前文档内容。
            edit: delete 类型的编辑。

        Returns:
            删除后的文档内容。如果 target 未找到则原样返回并打印 warning。
        """
        if edit.target is None:
            logger.warning(
                "delete 编辑 %s 缺少 target，已跳过", edit.id
            )
            return content

        if edit.target not in content:
            logger.warning(
                "delete 编辑 %s：target 未在文档中找到，已跳过", edit.id
            )
            return content

        return content.replace(edit.target, "", 1)

    # ------------------------------------------------------------------
    # 保护区检测
    # ------------------------------------------------------------------

    @staticmethod
    def _targets_protected_zone(content: str, edit: SkillEdit) -> bool:
        """检查编辑目标是否位于保护区内。

        对于 append 操作（无 target），永远不在保护区内。
        对于有 target 的操作（replace/delete/insert_after），
        检查 target 在 content 中的位置是否在保护区标记之间。

        Args:
            content: 当前文档内容。
            edit: 要检查的编辑。

        Returns:
            True 如果编辑目标在保护区内。
        """
        if edit.target is None:
            # append 操作无目标，不在保护区内
            return False

        position = content.find(edit.target)
        if position == -1:
            return False

        return PromptContracts.is_in_protected_zone(content, position)
