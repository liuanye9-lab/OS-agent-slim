"""tests/test_model_router — ModelRouter 测试用例。

覆盖：
- 能根据 task_type 给出建议
- 能输出 adapter prompt
- best_for 匹配的模型应被优先推荐
- avoid_for 匹配的模型应被降权
"""

from __future__ import annotations

from pathlib import Path

import pytest

from stable_agent.model_profile.model_profile import ModelProfileManager
from stable_agent.model_profile.model_router import ModelRouter


@pytest.fixture
def tmp_capsule(tmp_path: Path) -> Path:
    """创建临时 capsule 目录。"""
    capsule = tmp_path / "test-capsule"
    capsule.mkdir()
    (capsule / "model_profiles").mkdir()
    return capsule


class TestModelRouter:
    """ModelRouter 测试。"""

    def test_suggest_returns_one_of_available(self, tmp_capsule: Path) -> None:
        pm = ModelProfileManager(capsule_path=tmp_capsule)
        router = ModelRouter(pm)
        suggested = router.suggest_model_for_task(
            "code_generation", ["gpt", "claude", "qwen"]
        )
        assert suggested in ("gpt", "claude", "qwen")

    def test_suggest_prefers_best_for(self, tmp_capsule: Path) -> None:
        pm = ModelProfileManager(capsule_path=tmp_capsule)
        router = ModelRouter(pm)
        # code_generation 在 gpt 和 claude 的 best_for 中
        # 但 claude 有更多 strengths（默认 profile 中）
        suggested = router.suggest_model_for_task(
            "code_generation", ["gpt", "claude", "qwen"]
        )
        # 应该是 gpt 或 claude（都在 best_for 中），不应该是 qwen（不在 best_for 中）
        assert suggested in ("gpt", "claude")

    def test_suggest_avoids_avoid_for(self, tmp_capsule: Path) -> None:
        pm = ModelProfileManager(capsule_path=tmp_capsule)
        # 手动创建一个 profile，arch_refactor 在 avoid_for 中
        from stable_agent.model_profile.schemas import ModelProfile
        bad_model = ModelProfile(
            model_id="bad_model",
            display_name="Bad Model",
            strengths=["fast"],
            avoid_for=["arch_refactor"],
        )
        pm.save_profile(bad_model)

        router = ModelRouter(pm)
        suggested = router.suggest_model_for_task(
            "arch_refactor", ["bad_model", "claude"]
        )
        # claude 在 best_for 中有 arch_refactor，应该被优先推荐
        assert suggested == "claude"

    def test_suggest_empty_available_returns_generic(self, tmp_capsule: Path) -> None:
        pm = ModelProfileManager(capsule_path=tmp_capsule)
        router = ModelRouter(pm)
        suggested = router.suggest_model_for_task("code_generation", [])
        assert suggested == "generic"

    def test_build_adapter_prompt_contains_model_name(self, tmp_capsule: Path) -> None:
        pm = ModelProfileManager(capsule_path=tmp_capsule)
        router = ModelRouter(pm)
        prompt = router.build_model_adapter_prompt("claude", "code_generation")
        assert "Claude" in prompt
        assert "Model Adapter" in prompt

    def test_build_adapter_prompt_contains_rules(self, tmp_capsule: Path) -> None:
        pm = ModelProfileManager(capsule_path=tmp_capsule)
        router = ModelRouter(pm)
        prompt = router.build_model_adapter_prompt("gpt", "code_generation")
        # gpt 默认有 prompt_adapter_rules
        assert "适配规则" in prompt or "system message" in prompt

    def test_build_adapter_prompt_mentions_best_for(self, tmp_capsule: Path) -> None:
        pm = ModelProfileManager(capsule_path=tmp_capsule)
        router = ModelRouter(pm)
        # code_generation 在 gpt 的 best_for 中
        prompt = router.build_model_adapter_prompt("gpt", "code_generation")
        assert "擅长" in prompt

    def test_build_adapter_prompt_mentions_avoid_for(self, tmp_capsule: Path) -> None:
        pm = ModelProfileManager(capsule_path=tmp_capsule)
        from stable_agent.model_profile.schemas import ModelProfile
        test_model = ModelProfile(
            model_id="test_avoid",
            display_name="Test",
            avoid_for=["bug_fix"],
        )
        pm.save_profile(test_model)

        router = ModelRouter(pm)
        prompt = router.build_model_adapter_prompt("test_avoid", "bug_fix")
        assert "较弱" in prompt or "注意" in prompt

    def test_build_adapter_prompt_contains_budget_hint(self, tmp_capsule: Path) -> None:
        pm = ModelProfileManager(capsule_path=tmp_capsule)
        router = ModelRouter(pm)
        prompt = router.build_model_adapter_prompt("claude", "general_qa")
        assert "上下文预算" in prompt
        assert "tokens" in prompt

    def test_build_adapter_prompt_contains_tool_hint(self, tmp_capsule: Path) -> None:
        pm = ModelProfileManager(capsule_path=tmp_capsule)
        router = ModelRouter(pm)
        prompt = router.build_model_adapter_prompt("claude", "general_qa")
        assert "JSON schema" in prompt
