"""stable_agent.model_profile.model_profile — 模型画像管理器。

管理模型画像的加载、保存、列表和更新。默认内嵌 4 个 profile
（generic / gpt / claude / qwen），持久化到 capsule 的 model_profiles/ 目录。
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from stable_agent.capsule.capsule_manager import get_default_capsule_path
from stable_agent.model_profile.schemas import ModelProfile

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 内嵌默认 profiles（首次加载时写入 capsule）
# ---------------------------------------------------------------------------

_DEFAULT_PROFILES: dict[str, dict[str, Any]] = {
    "generic": {
        "model_id": "generic",
        "display_name": "Generic",
        "strengths": ["通用能力"],
        "risks": [],
        "best_for": ["general_qa"],
        "avoid_for": [],
        "prompt_adapter_rules": [],
        "context_budget_hint": {
            "max_injected_tokens": 12000,
            "prefer_short_context": False,
        },
        "tool_calling_hint": {
            "requires_strict_json": True,
            "avoid_parallel_tool_calls": False,
        },
    },
    "gpt": {
        "model_id": "gpt",
        "display_name": "GPT",
        "strengths": ["指令遵循", "函数调用", "JSON 输出"],
        "risks": ["长上下文注意力衰减"],
        "best_for": ["code_generation", "bug_fix", "eval_task"],
        "avoid_for": [],
        "prompt_adapter_rules": [
            "使用 system message 明确角色",
            "工具调用需严格 JSON schema",
        ],
        "context_budget_hint": {
            "max_injected_tokens": 16000,
            "prefer_short_context": False,
        },
        "tool_calling_hint": {
            "requires_strict_json": True,
            "avoid_parallel_tool_calls": False,
        },
    },
    "claude": {
        "model_id": "claude",
        "display_name": "Claude",
        "strengths": ["长上下文处理", "指令遵循", "代码理解"],
        "risks": ["过度谨慎拒绝"],
        "best_for": ["arch_refactor", "code_generation", "ui_design"],
        "avoid_for": [],
        "prompt_adapter_rules": [
            "XML tag 结构化提示效果更佳",
            "避免同时传入过多工具",
        ],
        "context_budget_hint": {
            "max_injected_tokens": 20000,
            "prefer_short_context": False,
        },
        "tool_calling_hint": {
            "requires_strict_json": True,
            "avoid_parallel_tool_calls": True,
        },
    },
    "qwen": {
        "model_id": "qwen",
        "display_name": "Qwen",
        "strengths": ["中文理解", "本地化部署"],
        "risks": ["复杂推理稳定性", "工具调用格式偶有偏差"],
        "best_for": ["general_qa", "prompt_optimization"],
        "avoid_for": ["arch_refactor"],
        "prompt_adapter_rules": [
            "prompt 中明确指定输出格式",
            "简化工具调用数量",
        ],
        "context_budget_hint": {
            "max_injected_tokens": 8000,
            "prefer_short_context": True,
        },
        "tool_calling_hint": {
            "requires_strict_json": True,
            "avoid_parallel_tool_calls": True,
        },
    },
}


class ModelProfileManager:
    """模型画像管理器。

    负责从 capsule 的 model_profiles/ 目录加载和保存 ModelProfile。
    首次访问时自动写入默认 profiles。

    Args:
        capsule_path: capsule 根目录路径，None 则使用默认路径。
    """

    def __init__(self, capsule_path: str | Path | None = None) -> None:
        self._capsule_path: Path = Path(capsule_path) if capsule_path else get_default_capsule_path()
        self._profiles_dir: Path = self._capsule_path / "model_profiles"
        self._profiles_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    def load_model_profile(self, model_id: str) -> ModelProfile:
        """加载指定模型的画像。

        优先从 capsule 磁盘文件加载；若文件不存在，使用内嵌默认值
        并自动持久化到磁盘。

        Args:
            model_id: 模型标识，如 "claude" / "gpt" / "qwen" / "generic"。

        Returns:
            ModelProfile 实例。
        """
        profile_path = self._profiles_dir / f"{model_id}.json"
        if profile_path.exists():
            return self._load_from_file(profile_path)

        # 文件不存在 → 使用内嵌默认值（若存在）
        if model_id in _DEFAULT_PROFILES:
            profile = ModelProfile.from_dict(_DEFAULT_PROFILES[model_id])
            self.save_profile(profile)
            return profile

        # 未知 model_id → 返回空 generic
        profile = ModelProfile(model_id=model_id, display_name=model_id.upper())
        self.save_profile(profile)
        return profile

    def list_profiles(self) -> list[ModelProfile]:
        """列出所有已知模型画像。

        扫描 capsule model_profiles/ 目录下的 .json 文件，
        同时补充内嵌默认中尚未持久化的 profile。

        Returns:
            ModelProfile 列表。
        """
        result: list[ModelProfile] = []
        seen: set[str] = set()

        # 1. 从磁盘加载
        for f in sorted(self._profiles_dir.glob("*.json")):
            try:
                profile = self._load_from_file(f)
                result.append(profile)
                seen.add(profile.model_id)
            except Exception as exc:
                logger.warning("Failed to load profile %s: %s", f.name, exc)

        # 2. 补充内嵌默认
        for model_id, data in _DEFAULT_PROFILES.items():
            if model_id not in seen:
                profile = ModelProfile.from_dict(data)
                self.save_profile(profile)
                result.append(profile)

        return result

    def save_profile(self, profile: ModelProfile) -> None:
        """持久化一个 ModelProfile 到 capsule 磁盘。

        Args:
            profile: 要保存的 ModelProfile 实例。
        """
        profile.updated_at = time.time()
        profile_path = self._profiles_dir / f"{profile.model_id}.json"
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(profile.to_dict(), f, ensure_ascii=False, indent=2)

    def update_from_bad_case(self, model_id: str, bad_case: dict[str, Any]) -> ModelProfile:
        """根据失败案例更新模型画像的风险列表。

        从 bad_case 中提取 failure_reason，如果不在现有 risks 中则追加。
        同时根据 failure_mode 更新 avoid_for。

        Args:
            model_id: 模型标识。
            bad_case: 失败案例字典，需包含 failure_reason 和可选 failure_mode。

        Returns:
            更新后的 ModelProfile 实例。
        """
        profile = self.load_model_profile(model_id)

        # 提取失败原因
        failure_reason = bad_case.get("failure_reason", "")
        if failure_reason and failure_reason not in profile.risks:
            profile.risks.append(failure_reason)
            logger.info("Added risk to %s: %s", model_id, failure_reason)

        # 提取失败模式 → 更新 avoid_for
        failure_mode = bad_case.get("failure_mode", "")
        if failure_mode and failure_mode not in profile.avoid_for:
            profile.avoid_for.append(failure_mode)
            logger.info("Added avoid_for to %s: %s", model_id, failure_mode)

        self.save_profile(profile)
        return profile

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _load_from_file(self, path: Path) -> ModelProfile:
        """从 JSON 文件加载 ModelProfile。"""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return ModelProfile.from_dict(data)
