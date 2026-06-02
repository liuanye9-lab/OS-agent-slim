"""stable_agent.skills.rollback — SkillRollbackManager 版本回滚管理。

管理技能版本回滚，支持回滚到任意历史版本。
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from stable_agent.skills.repo import SkillRepo
from stable_agent.skills.schema import SkillMetadata, SkillVersion

logger = logging.getLogger(__name__)


class SkillRollbackManager:
    """技能回滚管理器。

    支持：
    - 查看版本历史
    - 回滚到指定版本
    - 比较版本差异

    Attributes:
        repo: SkillRepo 实例。
    """

    def __init__(self, repo: SkillRepo) -> None:
        """初始化回滚管理器。

        Args:
            repo: SkillRepo 实例。
        """
        self.repo = repo

    def get_version_history(self, skill_id: str) -> list[dict[str, Any]]:
        """获取技能版本历史。

        Args:
            skill_id: 技能 ID。

        Returns:
            版本历史列表。
        """
        versions = self.repo.get_versions(skill_id)
        return [v.to_dict() for v in versions]

    def rollback(
        self,
        skill_id: str,
        target_version: int,
        source_run: str = "",
        reason: str = "",
    ) -> Optional[SkillMetadata]:
        """回滚技能到指定版本。

        Args:
            skill_id: 技能 ID。
            target_version: 目标版本号。
            source_run: 来源运行 ID。
            reason: 回滚原因。

        Returns:
            回滚后的技能元数据，失败返回 None。
        """
        # 检查目标版本是否存在
        versions = self.repo.get_versions(skill_id)
        target = None
        for v in versions:
            if v.version == target_version:
                target = v
                break

        if target is None:
            logger.warning("Version %d not found for skill %s", target_version, skill_id)
            return None

        # 执行回滚
        result = self.repo.rollback(
            skill_id=skill_id,
            target_version=target_version,
            source_run=source_run,
            reason=reason,
        )

        if result:
            logger.info(
                "Rolled back skill %s to v%d (new version: v%d)",
                skill_id, target_version, result.version,
            )

        return result

    def compare_versions(
        self,
        skill_id: str,
        version_a: int,
        version_b: int,
    ) -> dict[str, Any]:
        """比较两个版本的差异。

        Args:
            skill_id: 技能 ID。
            version_a: 版本 A。
            version_b: 版本 B。

        Returns:
            差异信息。
        """
        versions = self.repo.get_versions(skill_id)
        va = None
        vb = None
        for v in versions:
            if v.version == version_a:
                va = v
            if v.version == version_b:
                vb = v

        if va is None or vb is None:
            return {"ok": False, "error": "version not found"}

        # 比较快照
        snap_a = va.metadata_snapshot
        snap_b = vb.metadata_snapshot

        diff: dict[str, Any] = {}
        all_keys = set(snap_a.keys()) | set(snap_b.keys())
        for key in all_keys:
            val_a = snap_a.get(key)
            val_b = snap_b.get(key)
            if val_a != val_b:
                diff[key] = {"old": val_a, "new": val_b}

        return {
            "ok": True,
            "skill_id": skill_id,
            "version_a": version_a,
            "version_b": version_b,
            "diff": diff,
            "hash_a": va.content_hash,
            "hash_b": vb.content_hash,
        }

    def get_diff_from_current(
        self,
        skill_id: str,
        target_version: int,
    ) -> dict[str, Any]:
        """获取当前版本与目标版本的差异。

        Args:
            skill_id: 技能 ID。
            target_version: 目标版本号。

        Returns:
            差异信息。
        """
        current = self.repo.get_skill(skill_id)
        if current is None:
            return {"ok": False, "error": "skill not found"}

        return self.compare_versions(skill_id, current.version, target_version)
