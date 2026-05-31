"""tests/test_capsule_manager.py — CapsuleManager 测试。"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from stable_agent.capsule.capsule_manager import (
    CapsuleManager,
    REQUIRED_DIRS,
    ensure_capsule,
    get_default_capsule_path,
)
from stable_agent.capsule.manifest import ManifestManager


@pytest.fixture
def tmp_capsule(tmp_path: Path) -> str:
    """创建临时胶囊目录。"""
    return str(tmp_path / "test_capsule")


class TestCapsuleManager:
    """CapsuleManager 核心功能测试。"""

    def test_create_capsule(self, tmp_capsule: str) -> None:
        """创建胶囊应成功。"""
        manifest = CapsuleManager.create_capsule(tmp_capsule)
        assert manifest.capsule_id.startswith("cap_")
        assert manifest.schema_version == "v11"
        assert manifest.created_at > 0
        assert manifest.owner_label == "local-user"

    def test_create_capsule_creates_dirs(self, tmp_capsule: str) -> None:
        """创建胶囊应生成完整目录结构。"""
        CapsuleManager.create_capsule(tmp_capsule)
        for dir_name in REQUIRED_DIRS:
            assert (Path(tmp_capsule) / dir_name).is_dir(), f"缺失目录: {dir_name}"

    def test_create_capsule_creates_manifest(self, tmp_capsule: str) -> None:
        """创建胶囊应生成 manifest 文件。"""
        CapsuleManager.create_capsule(tmp_capsule)
        manifest_path = Path(tmp_capsule) / "capsule_manifest.json"
        assert manifest_path.is_file()
        with open(manifest_path) as f:
            data = json.load(f)
        assert "capsule_id" in data
        assert data["schema_version"] == "v11"

    def test_load_capsule(self, tmp_capsule: str) -> None:
        """加载已有胶囊应成功。"""
        created = CapsuleManager.create_capsule(tmp_capsule)
        loaded = CapsuleManager.load_capsule(tmp_capsule)
        assert loaded.capsule_id == created.capsule_id

    def test_load_capsule_not_found(self, tmp_path: Path) -> None:
        """加载不存在的胶囊应抛出异常。"""
        with pytest.raises(FileNotFoundError):
            CapsuleManager.load_capsule(str(tmp_path / "nonexistent"))

    def test_validate_capsule_structure_ok(self, tmp_capsule: str) -> None:
        """验证完整胶囊结构应通过。"""
        CapsuleManager.create_capsule(tmp_capsule)
        result = CapsuleManager.validate_capsule_structure(tmp_capsule)
        assert result["ok"] is True
        assert result["missing_dirs"] == []
        assert result["missing_files"] == []

    def test_validate_capsule_structure_missing(self, tmp_capsule: str) -> None:
        """缺失目录应被检测到。"""
        CapsuleManager.create_capsule(tmp_capsule)
        # 删除一个目录
        import shutil
        shutil.rmtree(Path(tmp_capsule) / "evals")
        result = CapsuleManager.validate_capsule_structure(tmp_capsule)
        assert result["ok"] is False
        assert "evals" in result["missing_dirs"]

    def test_get_capsule_status(self, tmp_capsule: str) -> None:
        """获取胶囊状态应返回完整信息。"""
        CapsuleManager.create_capsule(tmp_capsule)
        status = CapsuleManager.get_capsule_status(tmp_capsule)
        assert status["exists"] is True
        assert status["schema_version"] == "v11"
        assert status["structure_ok"] is True

    def test_get_capsule_status_not_exists(self, tmp_path: Path) -> None:
        """获取不存在胶囊的状态应返回 exists=False。"""
        status = CapsuleManager.get_capsule_status(str(tmp_path / "nonexistent"))
        assert status["exists"] is False

    def test_load_capsule_returns_same_id(self, tmp_capsule: str) -> None:
        """多次加载同一胶囊应返回相同 ID。"""
        CapsuleManager.create_capsule(tmp_capsule)
        m1 = CapsuleManager.load_capsule(tmp_capsule)
        m2 = CapsuleManager.load_capsule(tmp_capsule)
        assert m1.capsule_id == m2.capsule_id

    def test_create_capsule_creates_placeholder_files(self, tmp_capsule: str) -> None:
        """创建胶囊应生成占位文件。"""
        CapsuleManager.create_capsule(tmp_capsule)
        assert (Path(tmp_capsule) / "profile" / "user_profile.json").is_file()
        assert (Path(tmp_capsule) / "skills" / "global_skill.md").is_file()
        assert (Path(tmp_capsule) / "evals" / "rubrics" / "vibe_coding.json").is_file()

    def test_manifest_to_dict_json_serializable(self, tmp_capsule: str) -> None:
        """manifest.to_dict() 应可 JSON 序列化。"""
        manifest = CapsuleManager.create_capsule(tmp_capsule)
        d = manifest.to_dict()
        s = json.dumps(d)
        assert isinstance(s, str)
        assert len(s) > 0


class TestEnsureCapsule:
    """ensure_capsule 测试。"""

    def test_ensure_creates_when_missing(self, tmp_path: Path) -> None:
        """ensure_capsule 应自动创建不存在的胶囊。"""
        capsule_path = str(tmp_path / "auto_capsule")
        result = ensure_capsule(capsule_path)
        assert (result / "capsule_manifest.json").exists()

    def test_ensure_idempotent(self, tmp_path: Path) -> None:
        """多次 ensure 不应破坏已有胶囊。"""
        capsule_path = str(tmp_path / "auto_capsule")
        ensure_capsule(capsule_path)
        m1 = ManifestManager.load(capsule_path)
        ensure_capsule(capsule_path)
        m2 = ManifestManager.load(capsule_path)
        assert m1.capsule_id == m2.capsule_id
