"""stable_agent.capsule.manifest — 胶囊清单文件管理。

负责 capsule_manifest.json 的创建、加载、保存。
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from stable_agent.capsule.schemas import CapsuleManifest, CapsuleStats, _new_id

MANIFEST_FILENAME = "capsule_manifest.json"
SCHEMA_VERSION = "v11"


class ManifestManager:
    """胶囊清单文件管理器。

    负责 capsule_manifest.json 的创建、加载、保存。
    """

    @staticmethod
    def create(capsule_path: str | Path) -> CapsuleManifest:
        """创建新的胶囊清单。

        Args:
            capsule_path: 胶囊根目录路径。

        Returns:
            创建的 CapsuleManifest 实例。
        """
        capsule_path = Path(capsule_path)
        now = time.time()
        manifest = CapsuleManifest(
            capsule_id=_new_id("cap"),
            schema_version=SCHEMA_VERSION,
            created_at=now,
            updated_at=now,
            owner_label="local-user",
            project_scope="global",
            storage_mode="local-first",
            stats=CapsuleStats(),
        )
        manifest_path = capsule_path / MANIFEST_FILENAME
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        ManifestManager.save(manifest, manifest_path)
        return manifest

    @staticmethod
    def load(capsule_path: str | Path) -> CapsuleManifest:
        """加载胶囊清单。

        Args:
            capsule_path: 胶囊根目录路径或 manifest 文件路径。

        Returns:
            CapsuleManifest 实例。

        Raises:
            FileNotFoundError: manifest 文件不存在。
            ValueError: manifest 格式错误。
        """
        path = Path(capsule_path)
        if path.is_file():
            manifest_path = path
        else:
            manifest_path = path / MANIFEST_FILENAME

        if not manifest_path.exists():
            raise FileNotFoundError(f"manifest 不存在: {manifest_path}")

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"manifest JSON 格式错误: {e}") from e

        return CapsuleManifest.from_dict(data)

    @staticmethod
    def save(manifest: CapsuleManifest, manifest_path: str | Path) -> None:
        """保存胶囊清单到文件。

        Args:
            manifest: CapsuleManifest 实例。
            manifest_path: 保存路径。
        """
        manifest_path = Path(manifest_path)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest.to_dict(), f, ensure_ascii=False, indent=2)

    @staticmethod
    def update_timestamp(manifest: CapsuleManifest) -> CapsuleManifest:
        """更新 manifest 的 updated_at 时间戳。

        Args:
            manifest: 需要更新的 manifest。

        Returns:
            更新后的 manifest（原地修改）。
        """
        manifest.updated_at = time.time()
        return manifest

    @staticmethod
    def is_compatible(manifest: CapsuleManifest) -> bool:
        """检查 manifest 版本是否兼容。

        当前仅接受 v11。

        Args:
            manifest: 要检查的 manifest。

        Returns:
            True 表示兼容。
        """
        return manifest.schema_version == SCHEMA_VERSION
