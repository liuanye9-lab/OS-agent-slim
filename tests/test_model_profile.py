"""tests/test_model_profile — ModelProfile 测试用例。

覆盖：
- 能加载默认模型 profile
- 能根据 bad case 增加 risk
- JSON 可序列化
- AdapterLoader 返回可注入配置
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from stable_agent.model_profile.schemas import (
    ModelProfile,
    ContextBudgetHint,
    ToolCallingHint,
)
from stable_agent.model_profile.model_profile import ModelProfileManager
from stable_agent.model_profile.adapter_loader import AdapterLoader


@pytest.fixture
def tmp_capsule(tmp_path: Path) -> Path:
    """创建临时 capsule 目录。"""
    capsule = tmp_path / "test-capsule"
    capsule.mkdir()
    (capsule / "model_profiles").mkdir()
    return capsule


class TestModelProfileSchema:
    """ModelProfile 数据结构测试。"""

    def test_default_values(self) -> None:
        p = ModelProfile()
        assert p.model_id == "generic"
        assert p.display_name == "Generic"
        assert isinstance(p.strengths, list)
        assert isinstance(p.risks, list)
        assert isinstance(p.context_budget_hint, ContextBudgetHint)
        assert isinstance(p.tool_calling_hint, ToolCallingHint)

    def test_to_dict_json_serializable(self) -> None:
        p = ModelProfile(
            model_id="test",
            strengths=["s1"],
            risks=["r1"],
            prompt_adapter_rules=["rule1"],
        )
        d = p.to_dict()
        # 必须可 JSON 序列化
        serialized = json.dumps(d, ensure_ascii=False)
        assert "test" in serialized
        assert d["model_id"] == "test"
        assert d["strengths"] == ["s1"]

    def test_from_dict_roundtrip(self) -> None:
        p = ModelProfile(
            model_id="claude",
            display_name="Claude",
            strengths=["长上下文"],
            risks=["过度谨慎"],
            best_for=["code_generation"],
        )
        d = p.to_dict()
        p2 = ModelProfile.from_dict(d)
        assert p2.model_id == "claude"
        assert p2.strengths == ["长上下文"]
        assert p2.best_for == ["code_generation"]

    def test_context_budget_hint_roundtrip(self) -> None:
        h = ContextBudgetHint(max_injected_tokens=8000, prefer_short_context=True)
        d = h.to_dict()
        h2 = ContextBudgetHint.from_dict(d)
        assert h2.max_injected_tokens == 8000
        assert h2.prefer_short_context is True

    def test_tool_calling_hint_roundtrip(self) -> None:
        h = ToolCallingHint(requires_strict_json=False, avoid_parallel_tool_calls=True)
        d = h.to_dict()
        h2 = ToolCallingHint.from_dict(d)
        assert h2.requires_strict_json is False
        assert h2.avoid_parallel_tool_calls is True


class TestModelProfileManager:
    """ModelProfileManager 测试。"""

    def test_load_default_profiles(self, tmp_capsule: Path) -> None:
        pm = ModelProfileManager(capsule_path=tmp_capsule)
        for model_id in ("generic", "gpt", "claude", "qwen"):
            profile = pm.load_model_profile(model_id)
            assert profile.model_id == model_id
            assert profile.display_name  # 非空

    def test_list_profiles(self, tmp_capsule: Path) -> None:
        pm = ModelProfileManager(capsule_path=tmp_capsule)
        profiles = pm.list_profiles()
        model_ids = {p.model_id for p in profiles}
        assert "generic" in model_ids
        assert "gpt" in model_ids
        assert "claude" in model_ids
        assert "qwen" in model_ids

    def test_save_and_reload(self, tmp_capsule: Path) -> None:
        pm = ModelProfileManager(capsule_path=tmp_capsule)
        profile = ModelProfile(
            model_id="custom",
            display_name="Custom Model",
            strengths=["fast"],
        )
        pm.save_profile(profile)

        loaded = pm.load_model_profile("custom")
        assert loaded.model_id == "custom"
        assert loaded.strengths == ["fast"]

    def test_update_from_bad_case_adds_risk(self, tmp_capsule: Path) -> None:
        pm = ModelProfileManager(capsule_path=tmp_capsule)
        # 先加载 claude profile
        profile = pm.load_model_profile("claude")
        initial_risk_count = len(profile.risks)

        bad_case = {
            "failure_reason": "输出格式不符合要求",
            "failure_mode": "format_mismatch",
        }
        updated = pm.update_from_bad_case("claude", bad_case)

        assert "输出格式不符合要求" in updated.risks
        assert len(updated.risks) == initial_risk_count + 1
        assert "format_mismatch" in updated.avoid_for

    def test_update_from_bad_case_no_duplicate_risk(self, tmp_capsule: Path) -> None:
        pm = ModelProfileManager(capsule_path=tmp_capsule)
        bad_case = {"failure_reason": "same_reason"}
        pm.update_from_bad_case("gpt", bad_case)
        pm.update_from_bad_case("gpt", bad_case)
        # 不应重复添加
        profile = pm.load_model_profile("gpt")
        assert profile.risks.count("same_reason") == 1

    def test_load_unknown_model(self, tmp_capsule: Path) -> None:
        pm = ModelProfileManager(capsule_path=tmp_capsule)
        profile = pm.load_model_profile("unknown_model_xyz")
        assert profile.model_id == "unknown_model_xyz"
        # 应自动持久化
        assert (tmp_capsule / "model_profiles" / "unknown_model_xyz.json").exists()


class TestAdapterLoader:
    """AdapterLoader 测试。"""

    def test_load_adapter_returns_dict(self, tmp_capsule: Path) -> None:
        pm = ModelProfileManager(capsule_path=tmp_capsule)
        loader = AdapterLoader(pm)
        adapter = loader.load_adapter("claude")

        assert isinstance(adapter, dict)
        assert adapter["model_id"] == "claude"
        assert "prompt_adapter_rules" in adapter
        assert "context_budget_hint" in adapter
        assert "tool_calling_hint" in adapter

    def test_adapter_json_serializable(self, tmp_capsule: Path) -> None:
        pm = ModelProfileManager(capsule_path=tmp_capsule)
        loader = AdapterLoader(pm)
        adapter = loader.load_adapter("gpt")
        serialized = json.dumps(adapter, ensure_ascii=False)
        assert "gpt" in serialized

    def test_adapter_has_budget_hint(self, tmp_capsule: Path) -> None:
        pm = ModelProfileManager(capsule_path=tmp_capsule)
        loader = AdapterLoader(pm)
        adapter = loader.load_adapter("qwen")
        budget = adapter["context_budget_hint"]
        assert "max_injected_tokens" in budget
        assert "prefer_short_context" in budget

    def test_adapter_has_tool_hint(self, tmp_capsule: Path) -> None:
        pm = ModelProfileManager(capsule_path=tmp_capsule)
        loader = AdapterLoader(pm)
        adapter = loader.load_adapter("claude")
        tool_hint = adapter["tool_calling_hint"]
        assert "requires_strict_json" in tool_hint
        assert "avoid_parallel_tool_calls" in tool_hint
