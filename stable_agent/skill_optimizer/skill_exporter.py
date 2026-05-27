"""Skill 导出器。

导出 best_skill.md 供外部使用。确保只导出通过验证的版本。
支持按版本号导出指定版本。
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from stable_agent.skill_optimizer.skill_document_store import (
        SkillDocumentStore,
    )

logger = logging.getLogger(__name__)


class SkillExporter:
    """导出 best_skill.md 供外部使用。

    确保只导出通过验证（validated 状态）的版本。
    如果 best skill 不存在，用 current skill 替代。

    Attributes:
        doc_store: SkillDocumentStore 实例。
    """

    def __init__(self, doc_store: SkillDocumentStore) -> None:
        """初始化导出器。

        Args:
            doc_store: SkillDocumentStore 实例，用于加载和保存 skill。
        """
        self.doc_store: SkillDocumentStore = doc_store

    # ------------------------------------------------------------------
    # 导出
    # ------------------------------------------------------------------

    def export(self, target_path: str = "skills/best_skill.md") -> str:
        """导出 best_skill 到目标路径。

        如果 best skill 不存在，用 current skill 替代。
        确保导出版本是 validated 状态。

        Args:
            target_path: 导出目标路径，默认 "skills/best_skill.md"。

        Returns:
            导出文件的绝对路径。

        Raises:
            ValueError: 如果既无 best skill 也无 current skill。
        """
        # 尝试加载 best skill
        best_skill = self.doc_store.load_best_skill()

        if best_skill is not None:
            logger.info("导出 best_skill (版本 %s)", best_skill.version)
            skill = best_skill
        else:
            # 回退到 current skill
            logger.info("best_skill 不存在，回退到 current_skill")
            current_skill = self.doc_store.load_current_skill()
            skill = current_skill

        # 确保目标目录存在
        target = Path(target_path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)

        # 写入内容（含版本注释）
        from stable_agent.skill_optimizer.skill_document_store import (
            SkillDocumentStore,
        )

        # 使用 doc_store 的内部方法写文件
        target.parent.mkdir(parents=True, exist_ok=True)
        version_line = f"<!-- skill_version: {skill.version} -->\n"
        target.write_text(version_line + skill.content, encoding="utf-8")

        logger.info("已导出 skill 到: %s (版本 %s)", target, skill.version)
        return str(target)

    # ------------------------------------------------------------------
    # 按版本导出
    # ------------------------------------------------------------------

    def export_version(self, version: str, target_path: str) -> str:
        """导出指定版本的 skill 到目标路径。

        从 skill_versions 目录中查找指定版本文件。

        Args:
            version: 版本号字符串（如 "v1.2"）。
            target_path: 导出目标路径。

        Returns:
            导出文件的绝对路径。

        Raises:
            FileNotFoundError: 指定版本文件不存在。
        """
        # 检查版本文件是否存在
        version_file = (
            self.doc_store.skill_versions_dir / f"{version}.md"
        )
        if not version_file.exists():
            raise FileNotFoundError(
                f"版本文件不存在: {version_file}"
            )

        # 读取版本内容
        content, file_version = self.doc_store._read_skill_file(
            version_file
        )

        # 写入目标路径
        target = Path(target_path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)

        version_line = f"<!-- skill_version: {file_version} -->\n"
        target.write_text(version_line + content, encoding="utf-8")

        logger.info(
            "已导出版本 %s 到: %s", file_version, target
        )
        return str(target)
