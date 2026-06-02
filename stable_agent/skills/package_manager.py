"""stable_agent.skills.package_manager — SkillPackageManager 技能包管理。

管理技能包目录结构，支持 SKILL.md、metadata.json、CHECKLIST.md 等文件。
支持 progressive disclosure：检索阶段只读 metadata，命中后才读 SKILL.md。
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

from stable_agent.skills.schema import SkillMetadata, SkillPackage

logger = logging.getLogger(__name__)


class SkillPackageManager:
    """技能包管理器。

    管理 .stableagent-capsule/skills/packages/ 下的技能包目录。

    Attributes:
        packages_dir: 技能包目录。
    """

    def __init__(self, packages_dir: str | None = None) -> None:
        """初始化包管理器。

        Args:
            packages_dir: 技能包目录路径。
        """
        if packages_dir is None:
            packages_dir = os.environ.get(
                "STABLEAGENT_SKILLS_PACKAGES_DIR",
                ".stableagent-capsule/skills/packages",
            )
        self.packages_dir = Path(packages_dir).resolve()
        self.packages_dir.mkdir(parents=True, exist_ok=True)

    def create_package(
        self,
        skill_id: str,
        metadata: SkillMetadata,
        skill_md: str = "",
        checklist_md: str = "",
        template_md: str = "",
        examples_md: str = "",
    ) -> SkillPackage:
        """创建技能包。

        Args:
            skill_id: 技能 ID。
            metadata: 技能元数据。
            skill_md: SKILL.md 内容。
            checklist_md: CHECKLIST.md 内容。
            template_md: TEMPLATE.md 内容。
            examples_md: examples.md 内容。

        Returns:
            技能包。
        """
        skill_dir = self.packages_dir / skill_id
        skill_dir.mkdir(parents=True, exist_ok=True)

        files: list[str] = []

        # 写入 metadata.json
        metadata_path = skill_dir / "metadata.json"
        metadata_path.write_text(
            json.dumps(metadata.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        files.append("metadata.json")

        # 写入 SKILL.md
        if skill_md:
            skill_md_path = skill_dir / "SKILL.md"
            skill_md_path.write_text(skill_md, encoding="utf-8")
            files.append("SKILL.md")

        # 写入可选文件
        if checklist_md:
            checklist_path = skill_dir / "CHECKLIST.md"
            checklist_path.write_text(checklist_md, encoding="utf-8")
            files.append("CHECKLIST.md")

        if template_md:
            template_path = skill_dir / "TEMPLATE.md"
            template_path.write_text(template_md, encoding="utf-8")
            files.append("TEMPLATE.md")

        if examples_md:
            examples_path = skill_dir / "examples.md"
            examples_path.write_text(examples_md, encoding="utf-8")
            files.append("examples.md")

        # 创建 scripts 目录（默认不自动执行）
        scripts_dir = skill_dir / "scripts"
        scripts_dir.mkdir(exist_ok=True)

        return SkillPackage(
            skill_id=skill_id,
            storage_path=str(skill_dir),
            entry_type="directory_skill",
            files=files,
            metadata=metadata,
        )

    def load_package(self, skill_id: str) -> Optional[SkillPackage]:
        """加载技能包。

        Args:
            skill_id: 技能 ID。

        Returns:
            技能包，不存在返回 None。
        """
        skill_dir = self.packages_dir / skill_id
        if not skill_dir.exists():
            return None

        files: list[str] = []
        for f in skill_dir.iterdir():
            if f.is_file():
                files.append(f.name)

        # 读取 metadata
        metadata_path = skill_dir / "metadata.json"
        metadata = SkillMetadata()
        if metadata_path.exists():
            try:
                data = json.loads(metadata_path.read_text(encoding="utf-8"))
                metadata = SkillMetadata.from_dict(data)
            except Exception as exc:
                logger.warning("Failed to load metadata for %s: %s", skill_id, exc)

        return SkillPackage(
            skill_id=skill_id,
            storage_path=str(skill_dir),
            entry_type="directory_skill",
            files=files,
            metadata=metadata,
        )

    def read_skill_md(self, skill_id: str) -> str:
        """读取 SKILL.md 内容。

        Args:
            skill_id: 技能 ID。

        Returns:
            SKILL.md 内容，不存在返回空字符串。
        """
        skill_dir = self.packages_dir / skill_id
        skill_md_path = skill_dir / "SKILL.md"
        if skill_md_path.exists():
            try:
                return skill_md_path.read_text(encoding="utf-8")
            except Exception:
                return ""
        return ""

    def read_metadata(self, skill_id: str) -> Optional[SkillMetadata]:
        """读取 metadata.json。

        Args:
            skill_id: 技能 ID。

        Returns:
            技能元数据，不存在返回 None。
        """
        skill_dir = self.packages_dir / skill_id
        metadata_path = skill_dir / "metadata.json"
        if metadata_path.exists():
            try:
                data = json.loads(metadata_path.read_text(encoding="utf-8"))
                return SkillMetadata.from_dict(data)
            except Exception:
                return None
        return None

    def list_packages(self) -> list[str]:
        """列出所有技能包 ID。

        Returns:
            技能包 ID 列表。
        """
        if not self.packages_dir.exists():
            return []
        return [
            d.name for d in self.packages_dir.iterdir()
            if d.is_dir()
        ]

    def delete_package(self, skill_id: str) -> bool:
        """删除技能包。

        Args:
            skill_id: 技能 ID。

        Returns:
            是否删除成功。
        """
        import shutil
        skill_dir = self.packages_dir / skill_id
        if skill_dir.exists():
            try:
                shutil.rmtree(skill_dir)
                return True
            except Exception as exc:
                logger.error("Failed to delete package %s: %s", skill_id, exc)
                return False
        return False
