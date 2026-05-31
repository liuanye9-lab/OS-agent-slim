"""tests/test_capsule_import_export.py — 胶囊导入导出测试。"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from stable_agent.capsule.capsule_manager import CapsuleManager
from stable_agent.capsule.import_export import CapsuleImportExport


@pytest.fixture
def created_capsule(tmp_path: Path) -> str:
    """创建一个完整的胶囊目录。"""
    capsule_path = str(tmp_path / "capsule_src")
    CapsuleManager.create_capsule(capsule_path)
    return capsule_path


class TestCapsuleExport:
    """胶囊导出测试。"""

    def test_export_creates_zip(self, created_capsule: str, tmp_path: Path) -> None:
        """导出应生成有效的 ZIP 文件。"""
        output_zip = str(tmp_path / "test_export.zip")
        result = CapsuleImportExport.export_capsule(created_capsule, output_zip)
        assert result == output_zip
        assert Path(output_zip).is_file()

    def test_export_zip_contains_manifest(
        self, created_capsule: str, tmp_path: Path
    ) -> None:
        """导出的 ZIP 应包含 capsule_manifest.json。"""
        output_zip = str(tmp_path / "test_export.zip")
        CapsuleImportExport.export_capsule(created_capsule, output_zip)
        with zipfile.ZipFile(output_zip, "r") as zf:
            assert "capsule_manifest.json" in zf.namelist()

    def test_export_zip_contains_dirs(
        self, created_capsule: str, tmp_path: Path
    ) -> None:
        """导出的 ZIP 应包含核心目录中的文件。"""
        output_zip = str(tmp_path / "test_export.zip")
        CapsuleImportExport.export_capsule(created_capsule, output_zip)
        with zipfile.ZipFile(output_zip, "r") as zf:
            names = zf.namelist()
            assert any("profile/" in n for n in names)
            assert any("skills/" in n for n in names)

    def test_export_nonexistent_raises(self, tmp_path: Path) -> None:
        """导出不存在的胶囊应抛出异常。"""
        with pytest.raises(FileNotFoundError):
            CapsuleImportExport.export_capsule(
                str(tmp_path / "nonexistent"), str(tmp_path / "out.zip")
            )


class TestCapsuleImport:
    """胶囊导入测试。"""

    def test_import_restores_capsule(
        self, created_capsule: str, tmp_path: Path
    ) -> None:
        """导入应恢复完整胶囊。"""
        output_zip = str(tmp_path / "test_export.zip")
        CapsuleImportExport.export_capsule(created_capsule, output_zip)

        target = str(tmp_path / "capsule_restored")
        manifest = CapsuleImportExport.import_capsule(output_zip, target)
        assert manifest.capsule_id.startswith("cap_")
        assert Path(target, "capsule_manifest.json").is_file()

    def test_import_preserves_data(self, created_capsule: str, tmp_path: Path) -> None:
        """导入后数据应与原始一致。"""
        output_zip = str(tmp_path / "test_export.zip")
        CapsuleImportExport.export_capsule(created_capsule, output_zip)

        target = str(tmp_path / "capsule_restored")
        manifest_imported = CapsuleImportExport.import_capsule(output_zip, target)
        manifest_original = CapsuleManager.load_capsule(created_capsule)
        assert manifest_imported.capsule_id == manifest_original.capsule_id

    def test_import_nonexistent_zip_raises(self, tmp_path: Path) -> None:
        """导入不存在的 ZIP 应抛出异常。"""
        with pytest.raises(FileNotFoundError):
            CapsuleImportExport.import_capsule(
                str(tmp_path / "nonexistent.zip"), str(tmp_path / "target")
            )


class TestCapsuleValidateZip:
    """ZIP 验证测试。"""

    def test_validate_valid_zip(
        self, created_capsule: str, tmp_path: Path
    ) -> None:
        """验证有效 ZIP 应通过。"""
        output_zip = str(tmp_path / "test_export.zip")
        CapsuleImportExport.export_capsule(created_capsule, output_zip)
        result = CapsuleImportExport.validate_zip(output_zip)
        assert result["ok"] is True
        assert result["has_manifest"] is True
        assert result["manifest_valid"] is True

    def test_validate_nonexistent(self, tmp_path: Path) -> None:
        """验证不存在文件应返回 ok=False。"""
        result = CapsuleImportExport.validate_zip(str(tmp_path / "nonexistent.zip"))
        assert result["ok"] is False
