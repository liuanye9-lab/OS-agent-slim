"""stable_agent.capsule.import_export — 胶囊导入导出。

支持将胶囊目录打包为 ZIP 文件，以及从 ZIP 文件恢复胶囊。
"""

from __future__ import annotations

import json
import logging
import os
import zipfile
from pathlib import Path
from typing import Any

from stable_agent.capsule.manifest import ManifestManager
from stable_agent.capsule.schemas import CapsuleManifest

logger = logging.getLogger(__name__)


class CapsuleImportExport:
    """胶囊导入导出管理器。

    支持将完整胶囊目录打包为 ZIP，以及从 ZIP 恢复到目标路径。
    导出时包含所有 JSON/JSONL/MD 文件和目录结构。
    """

    # 可导出的文件扩展名
    EXPORTABLE_EXTENSIONS = {".json", ".jsonl", ".md", ".yaml", ".yml", ".txt", ".sqlite"}

    @staticmethod
    def export_capsule(capsule_path: str, output_zip: str) -> str:
        """将胶囊目录导出为 ZIP 文件。

        Args:
            capsule_path: 胶囊根目录路径。
            output_zip: 输出 ZIP 文件路径。

        Returns:
            输出 ZIP 文件的路径。

        Raises:
            FileNotFoundError: 胶囊目录或 manifest 不存在。
        """
        capsule_path = Path(capsule_path)
        if not capsule_path.is_dir():
            raise FileNotFoundError(f"胶囊目录不存在: {capsule_path}")
        if not (capsule_path / "capsule_manifest.json").is_file():
            raise FileNotFoundError(f"manifest 不存在: {capsule_path / 'capsule_manifest.json'}")

        output_zip = Path(output_zip)
        output_zip.parent.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in sorted(capsule_path.rglob("*")):
                if not file_path.is_file():
                    continue
                # 跳过 __pycache__、.DS_Store 等
                if "__pycache__" in str(file_path) or file_path.name == ".DS_Store":
                    continue
                if file_path.suffix.lower() not in CapsuleImportExport.EXPORTABLE_EXTENSIONS:
                    continue
                arcname = file_path.relative_to(capsule_path)
                zf.write(file_path, arcname)

        return str(output_zip)

    @staticmethod
    def import_capsule(zip_path: str, target_path: str) -> CapsuleManifest:
        """从 ZIP 文件导入胶囊到目标路径。

        Args:
            zip_path: ZIP 文件路径。
            target_path: 目标胶囊目录路径。

        Returns:
            导入的 CapsuleManifest 实例。

        Raises:
            FileNotFoundError: ZIP 文件不存在。
            ValueError: ZIP 中不包含有效 manifest。
        """
        zip_path = Path(zip_path)
        if not zip_path.is_file():
            raise FileNotFoundError(f"ZIP 文件不存在: {zip_path}")

        target = Path(target_path)
        target.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zf:
            # 安全性检查：拒绝包含 .. 的路径
            for name in zf.namelist():
                if ".." in name:
                    raise ValueError(f"ZIP 中包含不安全路径: {name}")
            zf.extractall(target)

        # 验证 manifest
        manifest_path = target / "capsule_manifest.json"
        if not manifest_path.exists():
            raise ValueError("ZIP 中不包含 capsule_manifest.json")

        return ManifestManager.load(manifest_path)

    @staticmethod
    def validate_zip(zip_path: str) -> dict[str, Any]:
        """验证 ZIP 文件是否是有效的胶囊包。

        Args:
            zip_path: ZIP 文件路径。

        Returns:
            验证结果字典。
        """
        zip_path = Path(zip_path)
        if not zip_path.is_file():
            return {"ok": False, "error": f"文件不存在: {zip_path}"}

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
                has_manifest = "capsule_manifest.json" in names

                # 尝试解析 manifest
                manifest_valid = False
                if has_manifest:
                    try:
                        data = json.loads(zf.read("capsule_manifest.json"))
                        manifest_valid = "capsule_id" in data and "schema_version" in data
                    except Exception as e:
                        logger.debug("manifest parse failed in zip: %s", e)

                return {
                    "ok": has_manifest and manifest_valid,
                    "has_manifest": has_manifest,
                    "manifest_valid": manifest_valid,
                    "file_count": len(names),
                    "files": names[:20],  # 只返回前20个文件名
                }
        except zipfile.BadZipFile as e:
            return {"ok": False, "error": f"无效的 ZIP 文件: {e}"}
