"""Skill 文档存储管理器。

管理 current_skill / best_skill 的生命周期，版本化存储，diff 生成。
所有文件操作基于 pathlib.Path，版本号格式为 "v{major}.{minor}"。
"""

from __future__ import annotations

import difflib
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from stable_agent.skill_optimizer.models import SkillDocument

logger = logging.getLogger(__name__)

# 版本号内嵌在文件首行的注释中
_VERSION_PATTERN = re.compile(r"^<!--\s*skill_version:\s*(v\d+\.\d+)\s*-->\s*\n?")


class SkillDocumentStore:
    """Skill 文档存储管理器。

    管理 current_skill / best_skill 的生命周期，版本化存储，diff 生成。
    版本号格式为 "v{major}.{minor}"，存储在文件首行 HTML 注释中。

    Attributes:
        skills_dir: skills 根目录路径。
        skill_versions_dir: 版本化存储目录路径。
    """

    def __init__(
        self,
        skills_dir: str = "skills",
        skill_versions_dir: str = "skills/skill_versions",
    ) -> None:
        """初始化路径，自动创建目录。

        Args:
            skills_dir: skills 根目录的相对或绝对路径。
            skill_versions_dir: 版本化 skill 文件的存储目录。
        """
        self.skills_dir = Path(skills_dir).resolve()
        self.skill_versions_dir = Path(skill_versions_dir).resolve()
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.skill_versions_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 加载
    # ------------------------------------------------------------------

    def load_current_skill(self) -> SkillDocument:
        """加载 skills/current_skill.md。

        如果 current_skill.md 不存在，则从 initial_skill.md 复制创建，
        版本号设为 "v1.0"。

        Returns:
            当前活跃的 SkillDocument。

        Raises:
            FileNotFoundError: initial_skill.md 也不存在时抛出。
        """
        current_path = self.skills_dir / "current_skill.md"

        if not current_path.exists():
            initial_path = self.skills_dir / "initial_skill.md"
            if not initial_path.exists():
                raise FileNotFoundError(
                    f"初始 skill 文件不存在: {initial_path}"
                )
            # 首次创建：复制 initial_skill.md 到 current_skill.md
            content = initial_path.read_text(encoding="utf-8")
            self._write_skill_file(current_path, content, "v1.0")
            logger.info("从 initial_skill.md 创建 current_skill.md (v1.0)")

        content, version = self._read_skill_file(current_path)
        return SkillDocument(
            id=f"current-{version}",
            version=version,
            content=content,
            source="manual",
            status="current",
        )

    def load_best_skill(self) -> SkillDocument | None:
        """加载 skills/best_skill.md。

        Returns:
            SkillDocument 如果文件存在，否则 None。
        """
        best_path = self.skills_dir / "best_skill.md"
        if not best_path.exists():
            return None

        content, version = self._read_skill_file(best_path)
        return SkillDocument(
            id=f"best-{version}",
            version=version,
            content=content,
            source="auto-optimize",
            status="best",
        )

    # ------------------------------------------------------------------
    # 保存
    # ------------------------------------------------------------------

    def save_candidate_skill(self, skill: SkillDocument) -> None:
        """保存候选版本到 skills/skill_versions/<version>.md。

        不更新 current_skill.md。如果 skill 没有版本号则自动分配。

        Args:
            skill: 要保存的候选 SkillDocument。
        """
        version = skill.version if skill.version else self._next_version()
        candidate_path = self.skill_versions_dir / f"{version}.md"
        skill.version = version
        skill.status = "draft"
        skill.updated_at = datetime.now()
        self._write_skill_file(candidate_path, skill.content, version)
        logger.info("候选版本已保存: %s", candidate_path)

    def promote_to_current(self, skill_version: str) -> None:
        """将指定版本提升为 current_skill.md。

        如果当前已有 current_skill.md，先将旧版本备份到 skill_versions/ 目录。

        Args:
            skill_version: 要提升的版本号字符串（如 "v1.2"）。

        Raises:
            FileNotFoundError: 指定版本文件不存在。
        """
        candidate_path = self.skill_versions_dir / f"{skill_version}.md"
        if not candidate_path.exists():
            raise FileNotFoundError(f"候选版本文件不存在: {candidate_path}")

        current_path = self.skills_dir / "current_skill.md"

        # 备份旧 current 到 skill_versions
        if current_path.exists():
            old_content, old_version = self._read_skill_file(current_path)
            backup_path = self.skill_versions_dir / f"{old_version}.md"
            self._write_skill_file(backup_path, old_content, old_version)
            logger.info("旧 current_skill 已备份到 %s", backup_path)

        # 读取候选版本内容
        candidate_content, _ = self._read_skill_file(candidate_path)

        # 写入新的 current_skill.md
        self._write_skill_file(current_path, candidate_content, skill_version)
        logger.info("已提升 %s 为 current_skill.md", skill_version)

    def promote_to_best(self, skill_version: str) -> None:
        """将指定版本提升为 best_skill.md。

        只能由 Validation Gate 通过后调用。写入前验证 skill 的 status。

        Args:
            skill_version: 要提升的版本号字符串（如 "v1.2"）。

        Raises:
            FileNotFoundError: 指定版本文件不存在。
            ValueError: 如果 skill 的状态不是 "best"（运行时验证）。
        """
        candidate_path = self.skill_versions_dir / f"{skill_version}.md"
        if not candidate_path.exists():
            raise FileNotFoundError(f"候选版本文件不存在: {candidate_path}")

        candidate_content, candidate_file_version = self._read_skill_file(
            candidate_path
        )

        # 构造 SkillDocument 用于状态检查
        # 标记为 best：只有在 Validation Gate 确认后才应调用此方法
        skill = SkillDocument(
            id=f"best-{candidate_file_version}",
            version=candidate_file_version,
            content=candidate_content,
            source="auto-optimize",
            status="best",
        )

        # 运行时验证：确保状态是 "best"
        if skill.status != "best":
            raise ValueError(
                f"无法提升为 best：skill 状态为 '{skill.status}'，需要 'best'。"
                f"请确保 Validation Gate 已通过。"
            )

        best_path = self.skills_dir / "best_skill.md"
        self._write_skill_file(best_path, candidate_content, skill_version)
        logger.info("已提升 %s 为 best_skill.md", skill_version)

    # ------------------------------------------------------------------
    # 版本管理
    # ------------------------------------------------------------------

    def list_versions(self) -> list[SkillDocument]:
        """列出 skills/skill_versions/ 下所有版本。

        Returns:
            按 updated_at 降序排列的 SkillDocument 列表。
        """
        versions: list[SkillDocument] = []
        version_pattern = re.compile(r"^v\d+\.\d+\.md$")

        for file_path in sorted(
            self.skill_versions_dir.glob("*.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            if not version_pattern.match(file_path.name):
                continue

            content, version = self._read_skill_file(file_path)
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            versions.append(
                SkillDocument(
                    id=f"version-{version}",
                    version=version,
                    content=content,
                    created_at=mtime,
                    updated_at=mtime,
                    source="auto-optimize",
                    status="draft",
                )
            )

        return versions

    def diff_versions(self, old_version: str, new_version: str) -> str:
        """使用 difflib.unified_diff 生成两个版本的差异。

        Args:
            old_version: 旧版本号字符串（如 "v1.0"）。
            new_version: 新版本号字符串（如 "v1.1"）。

        Returns:
            统一 diff 格式的差异文本。

        Raises:
            FileNotFoundError: 任一版本文件不存在。
        """
        old_path = self.skill_versions_dir / f"{old_version}.md"
        new_path = self.skill_versions_dir / f"{new_version}.md"

        if not old_path.exists():
            raise FileNotFoundError(f"旧版本文件不存在: {old_path}")
        if not new_path.exists():
            raise FileNotFoundError(f"新版本文件不存在: {new_path}")

        old_content, _ = self._read_skill_file(old_path)
        new_content, _ = self._read_skill_file(new_path)

        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"skills/skill_versions/{old_version}.md",
            tofile=f"skills/skill_versions/{new_version}.md",
        )
        return "".join(diff)

    # ------------------------------------------------------------------
    # 内部辅助方法
    # ------------------------------------------------------------------

    @staticmethod
    def _read_skill_file(file_path: Path) -> tuple[str, str]:
        """从文件中读取 skill 内容和版本号。

        版本号存储在文件第一行的 HTML 注释中：
        <!-- skill_version: vX.Y -->

        Args:
            file_path: skill 文件路径。

        Returns:
            (content, version) 元组。

        Raises:
            FileNotFoundError: 文件不存在。
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Skill 文件不存在: {file_path}")

        raw_text = file_path.read_text(encoding="utf-8")
        match = _VERSION_PATTERN.match(raw_text)

        if match:
            version = match.group(1)
            content = raw_text[match.end():]
        else:
            # 兼容旧文件（无版本注释）：从文件名推断
            logger.warning("文件 %s 缺少版本注释，从文件名推断", file_path)
            stem = file_path.stem
            if re.match(r"^v\d+\.\d+$", stem):
                version = stem
            else:
                # 特殊文件名如 current_skill / best_skill / initial_skill
                version = "v1.0"
            content = raw_text

        return content, version

    @staticmethod
    def _write_skill_file(file_path: Path, content: str, version: str) -> None:
        """将 skill 内容和版本号写入文件。

        版本号以 HTML 注释形式写入文件首行。

        Args:
            file_path: 目标文件路径。
            content: skill 的 markdown 内容（不含版本注释）。
            version: 版本号字符串（如 "v1.0"）。
        """
        file_path.parent.mkdir(parents=True, exist_ok=True)
        version_line = f"<!-- skill_version: {version} -->\n"
        file_path.write_text(version_line + content, encoding="utf-8")

    def _next_version(self) -> str:
        """自动生成下一个版本号。

        扫描 skill_versions 目录中已有的版本文件，
        返回 "v{major}.{minor+1}"。如果没有版本文件，返回 "v1.0"。

        Returns:
            下一个可用的版本号字符串。
        """
        version_pattern = re.compile(r"^v(\d+)\.(\d+)\.md$")
        max_major = 0
        max_minor = 0

        for file_path in self.skill_versions_dir.glob("v*.md"):
            match = version_pattern.match(file_path.name)
            if match:
                major = int(match.group(1))
                minor = int(match.group(2))
                if major > max_major or (major == max_major and minor > max_minor):
                    max_major = major
                    max_minor = minor

        # 也检查 current_skill.md 和 best_skill.md 的版本
        for special_file in ("current_skill.md", "best_skill.md"):
            special_path = self.skills_dir / special_file
            if special_path.exists():
                try:
                    _, special_version = self._read_skill_file(special_path)
                    match = re.match(r"^v(\d+)\.(\d+)$", special_version)
                    if match:
                        major = int(match.group(1))
                        minor = int(match.group(2))
                        if major > max_major or (
                            major == max_major and minor > max_minor
                        ):
                            max_major = major
                            max_minor = minor
                except Exception as e:
                    logger.debug("读取版本号失败，跳过: %s", e)
                    pass

        if max_major == 0 and max_minor == 0:
            return "v1.0"

        return f"v{max_major}.{max_minor + 1}"
