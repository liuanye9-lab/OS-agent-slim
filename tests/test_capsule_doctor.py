"""tests/test_capsule_doctor.py — CapsuleDoctor 健康检查测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from stable_agent.capsule.capsule_doctor import CapsuleDoctor
from stable_agent.capsule.capsule_manager import CapsuleManager


@pytest.fixture
def healthy_capsule(tmp_path: Path) -> str:
    """创建一个健康的胶囊目录。"""
    capsule_path = str(tmp_path / "healthy_capsule")
    CapsuleManager.create_capsule(capsule_path)
    return capsule_path


class TestCapsuleDoctor:
    """CapsuleDoctor 健康检查测试。"""

    def test_healthy_capsule(self, healthy_capsule: str) -> None:
        """健康胶囊应通过检查。"""
        report = CapsuleDoctor.check(healthy_capsule)
        assert report.ok is True
        assert report.health_score >= 0.9
        assert report.errors == []

    def test_missing_manifest(self, tmp_path: Path) -> None:
        """缺失 manifest 应报错。"""
        capsule = tmp_path / "bad_capsule"
        capsule.mkdir()
        report = CapsuleDoctor.check(str(capsule))
        assert report.ok is False
        assert any("manifest" in e.lower() for e in report.errors)

    def test_incompatible_schema(self, tmp_path: Path) -> None:
        """不兼容版本应报错。"""
        capsule = tmp_path / "old_capsule"
        capsule.mkdir()
        manifest = {
            "capsule_id": "cap_test",
            "schema_version": "v99",
            "created_at": 0,
            "updated_at": 0,
        }
        (capsule / "capsule_manifest.json").write_text(json.dumps(manifest))
        report = CapsuleDoctor.check(str(capsule))
        assert report.ok is False
        assert any("不兼容" in e for e in report.errors)

    def test_missing_dirs_warning(self, healthy_capsule: str) -> None:
        """缺失目录应产生警告。"""
        import shutil
        shutil.rmtree(Path(healthy_capsule) / "bad_cases")
        report = CapsuleDoctor.check(healthy_capsule)
        assert any("bad_cases" in w for w in report.warnings)

    def test_invalid_jsonl_warning(self, healthy_capsule: str) -> None:
        """无效 JSONL 应产生警告。"""
        bad_jsonl = Path(healthy_capsule) / "memory" / "raw_episodes.jsonl"
        bad_jsonl.write_text("this is not valid json\n")
        report = CapsuleDoctor.check(healthy_capsule)
        assert any("jsonl" in w.lower() for w in report.warnings)

    def test_sensitive_info_detection(self, healthy_capsule: str) -> None:
        """敏感信息应被检测到。"""
        bad_file = Path(healthy_capsule) / "profile" / "user_profile.json"
        bad_file.write_text(json.dumps({"key": "sk-abc123456789012345678901"}))
        report = CapsuleDoctor.check(healthy_capsule)
        assert report.ok is False
        assert any("敏感" in e for e in report.errors)

    def test_nonexistent_dir(self, tmp_path: Path) -> None:
        """不存在的目录应报错。"""
        report = CapsuleDoctor.check(str(tmp_path / "nonexistent"))
        assert report.ok is False
        assert report.health_score == 0.0

    def test_report_json_serializable(self, healthy_capsule: str) -> None:
        """报告应可 JSON 序列化。"""
        report = CapsuleDoctor.check(healthy_capsule)
        s = json.dumps(report.to_dict())
        assert isinstance(s, str)
        assert len(s) > 0

    def test_stats_in_report(self, healthy_capsule: str) -> None:
        """报告应包含统计信息。"""
        report = CapsuleDoctor.check(healthy_capsule)
        assert "total_files" in report.stats
        assert "error_count" in report.stats
