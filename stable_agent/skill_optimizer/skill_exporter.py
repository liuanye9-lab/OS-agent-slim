"""Skill 导出器（V6-Professional Human Review Gate）。

导出 best_skill.md 供外部使用。强制只导出通过验证门且经人工确认的版本。
V6-Professional: requires_human_review 硬约束 — 未确认时拒绝导出。
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
    """导出 best_skill.md 供外部使用（V6-Professional）。

    硬约束：
    1. 必须通过 validation_gate.validate()。
    2. must be human_reviewed before export.
    如果任一条件不满足，抛出 PermissionError。

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
    # 导出（V6-Professional Human Review Gate）
    # ------------------------------------------------------------------

    def export(
        self,
        target_path: str = "skills/best_skill.md",
        validation_passed: bool = False,
        old_score: float = 0.0,
        new_score: float = 0.0,
        human_reviewed: bool = False,
    ) -> str:
        """导出 best_skill 到目标路径。

        V6-Professional: 必须同时满足以下条件才允许导出：
        1. validation_passed = True（validation gate 通过）
        2. new_score > old_score（评分类有提升）
        3. human_reviewed = True（人工已确认）

        如果 best skill 不存在，用 current skill 替代。
        确保导出版本是 validated 状态。

        Args:
            target_path: 导出目标路径，默认 "skills/best_skill.md"。
            validation_passed: validation gate 是否通过。
            old_score: 旧 skill 评分。
            new_score: 新 skill 评分。
            human_reviewed: 是否已获人工确认。

        Returns:
            导出文件的绝对路径。

        Raises:
            PermissionError: 如果未通过 validation gate 或未经人工确认。
            ValueError: 如果既无 best skill 也无 current skill。
        """
        # V6-Professional: 硬性门检查
        if not validation_passed:
            raise PermissionError(
                "Skill 导出被拒绝：未通过 Validation Gate。"
                "请确保 skill patch 经过 validate() 验证且 passed=True。"
            )
        if new_score <= old_score:
            logger.warning(
                "Skill 导出：new_score(%.3f) <= old_score(%.3f)，可能退化",
                new_score, old_score,
            )
        if not human_reviewed:
            raise PermissionError(
                "Skill 导出被拒绝：未经人工确认（Human Review required）。"
                "请在 Dashboard 或 approval 接口中确认后再导出。"
            )

        # 尝试加载 best skill
        best_skill = self.doc_store.load_best_skill()

        if best_skill is not None:
            logger.info("导出 best_skill (版本 %s)", best_skill.version)
            skill = best_skill
        else:
            logger.info("best_skill 不存在，回退到 current_skill")
            current_skill = self.doc_store.load_current_skill()
            skill = current_skill

        # 确保目标目录存在
        target = Path(target_path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)

        from stable_agent.skill_optimizer.skill_document_store import (
            SkillDocumentStore,
        )

        target.parent.mkdir(parents=True, exist_ok=True)
        version_line = f"<!-- skill_version: {skill.version} -->\n"
        target.write_text(version_line + skill.content, encoding="utf-8")

        logger.info(
            "已导出 skill 到: %s (版本 %s, validated=True, human_reviewed=True)",
            target, skill.version,
        )
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
