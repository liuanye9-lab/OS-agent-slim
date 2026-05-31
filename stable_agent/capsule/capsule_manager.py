"""stable_agent.capsule.capsule_manager — 胶囊生命周期管理。

提供胶囊的创建、加载、验证、确保存在等核心操作。
胶囊根目录默认位于 ~/.stableagent-capsule 或用户指定路径。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from stable_agent.capsule.manifest import ManifestManager
from stable_agent.capsule.schemas import CapsuleManifest


# 默认胶囊目录结构
REQUIRED_DIRS = [
    "profile",
    "memory",
    "skills",
    "skills/model_adapters",
    "evals",
    "evals/rubrics",
    "bad_cases",
    "workflow",
    "model_profiles",
    "token_ledger",
]

REQUIRED_FILES = [
    "capsule_manifest.json",
]


def get_default_capsule_path() -> Path:
    """获取默认胶囊目录路径。

    优先使用 STABLE_AGENT_CAPSULE_PATH 环境变量，
    否则默认到项目根目录下的 .stableagent-capsule/。

    Returns:
        默认胶囊路径。
    """
    env_path = os.environ.get("STABLE_AGENT_CAPSULE_PATH")
    if env_path:
        return Path(env_path)
    return Path.cwd() / ".stableagent-capsule"


def ensure_capsule(path: str | Path | None = None) -> Path:
    """确保胶囊目录存在，不存在则创建。

    Args:
        path: 可选的胶囊路径。None 则使用默认路径。

    Returns:
        胶囊根目录路径。
    """
    capsule_path = Path(path) if path else get_default_capsule_path()
    if not (capsule_path / "capsule_manifest.json").exists():
        CapsuleManager.create_capsule(str(capsule_path))
    return capsule_path


class CapsuleManager:
    """胶囊生命周期管理器。

    提供胶囊创建、加载、验证、目录初始化等核心操作。
    """

    @staticmethod
    def create_capsule(path: str) -> CapsuleManifest:
        """创建新的胶囊目录和清单。

        创建完整的目录结构和 manifest 文件。

        Args:
            path: 胶囊根目录路径。

        Returns:
            创建的 CapsuleManifest 实例。
        """
        capsule_path = Path(path)
        capsule_path.mkdir(parents=True, exist_ok=True)

        # 创建目录结构
        for dir_name in REQUIRED_DIRS:
            (capsule_path / dir_name).mkdir(parents=True, exist_ok=True)

        # 创建 manifest
        manifest = ManifestManager.create(capsule_path)

        # 创建默认子文件（空占位）
        _create_placeholder_files(capsule_path)

        return manifest

    @staticmethod
    def load_capsule(path: str) -> CapsuleManifest:
        """加载已有胶囊。

        Args:
            path: 胶囊根目录路径。

        Returns:
            CapsuleManifest 实例。

        Raises:
            FileNotFoundError: manifest 不存在。
            ValueError: manifest 格式错误或版本不兼容。
        """
        manifest = ManifestManager.load(path)
        if not ManifestManager.is_compatible(manifest):
            raise ValueError(
                f"capsule schema 版本不兼容: {manifest.schema_version}, "
                f"期望 {ManifestManager.load.__class__.__name__}"
            )
        return manifest

    @staticmethod
    def validate_capsule_structure(path: str) -> dict[str, Any]:
        """验证胶囊目录结构完整性。

        Args:
            path: 胶囊根目录路径。

        Returns:
            包含 missing_dirs 和 missing_files 的字典。
        """
        capsule_path = Path(path)
        missing_dirs: list[str] = []
        missing_files: list[str] = []

        for dir_name in REQUIRED_DIRS:
            if not (capsule_path / dir_name).is_dir():
                missing_dirs.append(dir_name)

        for file_name in REQUIRED_FILES:
            if not (capsule_path / file_name).is_file():
                missing_files.append(file_name)

        return {
            "ok": len(missing_dirs) == 0 and len(missing_files) == 0,
            "missing_dirs": missing_dirs,
            "missing_files": missing_files,
        }

    @staticmethod
    def get_capsule_status(path: str) -> dict[str, Any]:
        """获取胶囊状态摘要。

        Args:
            path: 胶囊根目录路径。

        Returns:
            胶囊状态字典，JSON 可序列化。
        """
        capsule_path = Path(path)
        if not (capsule_path / "capsule_manifest.json").exists():
            return {
                "exists": False,
                "path": str(capsule_path),
                "message_zh": "胶囊不存在，请先运行 capsule init",
            }

        try:
            manifest = ManifestManager.load(capsule_path)
        except Exception as e:
            return {
                "exists": True,
                "path": str(capsule_path),
                "error": str(e),
                "message_zh": f"胶囊加载失败: {e}",
            }

        structure = CapsuleManager.validate_capsule_structure(path)

        return {
            "exists": True,
            "path": str(capsule_path),
            "capsule_id": manifest.capsule_id,
            "schema_version": manifest.schema_version,
            "created_at": manifest.created_at,
            "updated_at": manifest.updated_at,
            "owner_label": manifest.owner_label,
            "project_scope": manifest.project_scope,
            "stats": manifest.stats.to_dict(),
            "structure_ok": structure["ok"],
            "missing_dirs": structure["missing_dirs"],
            "missing_files": structure["missing_files"],
            "message_zh": "胶囊健康" if structure["ok"] else "胶囊结构不完整",
        }


def _create_placeholder_files(capsule_path: Path) -> None:
    """创建默认占位文件。

    Args:
        capsule_path: 胶囊根目录。
    """
    # profile 默认文件
    profile_dir = capsule_path / "profile"
    _ensure_json_file(profile_dir / "user_profile.json", {})
    _ensure_json_file(profile_dir / "language_style.json", {"rules": []})
    _ensure_json_file(profile_dir / "preference_rules.json", {"rules": []})

    # memory 默认文件
    memory_dir = capsule_path / "memory"
    _ensure_jsonl_file(memory_dir / "raw_episodes.jsonl")
    _ensure_jsonl_file(memory_dir / "episode_summaries.jsonl")

    # skills 默认文件
    skills_dir = capsule_path / "skills"
    _ensure_text_file(skills_dir / "global_skill.md", "# Global Skill\n")
    _ensure_text_file(skills_dir / "vibe_coding_skill.md", "# Vibe Coding Skill\n")

    # evals 默认文件
    evals_dir = capsule_path / "evals"
    _ensure_jsonl_file(evals_dir / "personal_eval_cases.jsonl")
    _ensure_jsonl_file(evals_dir / "regression_cases.jsonl")
    _ensure_json_file(evals_dir / "rubrics" / "vibe_coding.json", {
        "rubric_id": "vibe_coding_default",
        "dimensions": {
            "goal_alignment": 0.30,
            "minimal_change": 0.20,
            "test_passed": 0.20,
            "style_consistency": 0.10,
            "token_efficiency": 0.10,
            "user_preference_match": 0.10,
        },
    })

    # bad_cases 默认文件
    bad_cases_dir = capsule_path / "bad_cases"
    for name in ["intent_drift", "memory_loss", "over_editing", "token_waste", "semantic_misread"]:
        _ensure_jsonl_file(bad_cases_dir / f"{name}.jsonl")

    # workflow 默认文件
    workflow_dir = capsule_path / "workflow"
    _ensure_json_file(workflow_dir / "coding_workflow.json", {"steps": []})
    _ensure_json_file(workflow_dir / "review_workflow.json", {"steps": []})
    _ensure_json_file(workflow_dir / "debugging_workflow.json", {"steps": []})

    # model_profiles 默认文件
    model_profiles_dir = capsule_path / "model_profiles"
    for model_id in ["gpt", "claude", "qwen", "generic"]:
        _ensure_json_file(model_profiles_dir / f"{model_id}.json", {
            "model_id": model_id,
            "display_name": model_id.upper(),
            "strengths": [],
            "risks": [],
        })


def _ensure_json_file(path: Path, default_data: dict) -> None:
    """确保 JSON 文件存在，不存在则创建。"""
    if not path.exists():
        import json
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default_data, f, ensure_ascii=False, indent=2)


def _ensure_jsonl_file(path: Path) -> None:
    """确保 JSONL 文件存在，不存在则创建。"""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()


def _ensure_text_file(path: Path, default_content: str) -> None:
    """确保文本文件存在，不存在则创建。"""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(default_content)
