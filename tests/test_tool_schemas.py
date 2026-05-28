"""test_tool_schemas.py — 工具 Schema 定义单元测试。

测试覆盖：
- 所有工具 schema 的 name 以 stableagent. 开头
- 所有工具有 risk_level 字段
- AVATAR_STATE_MAP ≥ 13 个条目
- get_risk_level 返回合法值
- get_tool_names / get_tool_by_name / get_avatar_state 辅助函数
"""

from __future__ import annotations

import pytest

from stable_agent.gateway.tool_schemas import (
    TOOLS,
    AVATAR_STATE_MAP,
    AVATAR_SCENE_MAP,
    get_tool_names,
    get_tool_by_name,
    get_avatar_state,
    get_scene_for_state,
    get_risk_level,
)


# ============================================================================
# TOOLS Schema 测试
# ============================================================================


class TestToolSchemas:
    """工具 Schema 定义测试。"""

    # ------------------------------------------------------------------
    # 测试 1：所有工具 schema 的 name 以 stableagent. 开头
    # ------------------------------------------------------------------

    def test_all_tool_names_start_with_stableagent(self) -> None:
        """验证所有工具 schema 的 name 以 stableagent. 开头。"""
        for key, tool_def in TOOLS.items():
            name = tool_def["name"]
            assert name.startswith("stableagent."), (
                f"工具 {key} 的 name '{name}' 不以 'stableagent.' 开头"
            )

    def test_tool_key_matches_name(self) -> None:
        """验证 TOOLS 字典的 key 与内部 name 字段一致。"""
        for key, tool_def in TOOLS.items():
            assert key == tool_def["name"], (
                f"TOOLS key '{key}' 与内部 name '{tool_def['name']}' 不一致"
            )

    # ------------------------------------------------------------------
    # 测试 2：所有工具有 risk_level 字段
    # ------------------------------------------------------------------

    def test_all_tools_have_risk_level(self) -> None:
        """验证所有工具 schema 都包含 risk_level 字段。"""
        valid_levels = {"low", "medium", "high", "forbidden"}

        for key, tool_def in TOOLS.items():
            assert "risk_level" in tool_def, (
                f"工具 {key} 缺少 risk_level 字段"
            )
            risk = tool_def["risk_level"]
            assert risk in valid_levels, (
                f"工具 {key} 的 risk_level '{risk}' 不是合法值（{valid_levels}）"
            )

    def test_risk_levels_are_valid(self) -> None:
        """验证各工具的 risk_level 为预期值。"""
        # 已知风险等级分配
        expected_risks = {
            "stableagent.task.process": "medium",
            "stableagent.context.build": "low",
            "stableagent.context.estimate_budget": "low",
            "stableagent.memory.retrieve": "low",
            "stableagent.memory.write_candidate": "low",
            "stableagent.rag.retrieve": "low",
            "stableagent.eval.evaluate": "low",
            "stableagent.badcase.record": "low",
            "stableagent.skillopt.status": "low",
            "stableagent.skillopt.get_current_skill": "low",
            "stableagent.skillopt.run_epoch": "medium",
            "stableagent.skillopt.export_best": "medium",
            "stableagent.trace.get_run": "low",
            "stableagent.approval.respond": "high",
        }
        for tool_name, expected_risk in expected_risks.items():
            tool = TOOLS.get(tool_name)
            assert tool is not None, f"未找到工具：{tool_name}"
            assert tool["risk_level"] == expected_risk, (
                f"{tool_name} risk_level 期望 '{expected_risk}'，"
                f"实际 '{tool['risk_level']}'"
            )

    # ------------------------------------------------------------------
    # 测试 3：AVATAR_STATE_MAP ≥ 13 个条目
    # ------------------------------------------------------------------

    def test_avatar_state_map_has_min_13_entries(self) -> None:
        """验证 AVATAR_STATE_MAP ≥ 13 个条目（不含 default）。"""
        # 排除 default 后的实际映射条目数
        non_default_entries = {
            k: v for k, v in AVATAR_STATE_MAP.items() if k != "default"
        }
        assert len(non_default_entries) >= 13, (
            f"AVATAR_STATE_MAP 应有 ≥13 个非 default 条目，"
            f"实际 {len(non_default_entries)} 个"
        )

    def test_avatar_state_map_has_default(self) -> None:
        """验证 AVATAR_STATE_MAP 包含 default 条目。"""
        assert "default" in AVATAR_STATE_MAP, "AVATAR_STATE_MAP 缺少 'default' 条目"
        # default 映射到 "listening"（当前实现）—— 确保非空即可
        assert AVATAR_STATE_MAP["default"], "default 值不应为空"

    def test_avatar_state_values_are_nonempty(self) -> None:
        """验证所有头像状态值不为空。"""
        for event_type, state in AVATAR_STATE_MAP.items():
            assert state, f"事件 '{event_type}' 的头像状态为空"

    # ------------------------------------------------------------------
    # AVATAR_SCENE_MAP 测试
    # ------------------------------------------------------------------

    def test_avatar_scene_map_has_min_13_entries(self) -> None:
        """验证 AVATAR_SCENE_MAP ≥ 13 个条目。"""
        assert len(AVATAR_SCENE_MAP) >= 13, (
            f"AVATAR_SCENE_MAP 应有 ≥13 个条目，实际 {len(AVATAR_SCENE_MAP)} 个"
        )

    def test_avatar_scene_map_entries_have_required_fields(self) -> None:
        """验证 AVATAR_SCENE_MAP 每个条目包含 scene、prop、label_zh、label_en。"""
        required_fields = {"scene", "prop", "label_zh", "label_en"}
        for state, scene_config in AVATAR_SCENE_MAP.items():
            for field in required_fields:
                assert field in scene_config, (
                    f"AVATAR_SCENE_MAP['{state}'] 缺少 '{field}' 字段"
                )
                assert scene_config[field], (
                    f"AVATAR_SCENE_MAP['{state}'].{field} 不应为空"
                )

    def test_avatar_scene_map_covers_all_states(self) -> None:
        """验证 AVATAR_SCENE_MAP 覆盖了 AVATAR_STATE_MAP 中的所有状态值。"""
        # 收集 AVATAR_STATE_MAP 中的唯一状态值（排除 default）
        state_values = {
            v for k, v in AVATAR_STATE_MAP.items() if k != "default"
        }
        # 验证 AVATAR_SCENE_MAP 包含所有这些状态
        for state in state_values:
            assert state in AVATAR_SCENE_MAP, (
                f"AVATAR_SCENE_MAP 缺少状态 '{state}'（来自 AVATAR_STATE_MAP）"
            )

    def test_get_scene_for_state_known(self) -> None:
        """验证 get_scene_for_state 对已知状态返回正确场景。"""
        scene = get_scene_for_state("listening")
        assert scene["scene"] == "desk"
        assert scene["prop"] == "task_card"
        assert "label_zh" in scene
        assert "label_en" in scene

    def test_get_scene_for_state_unknown_falls_back(self) -> None:
        """验证 get_scene_for_state 对未知状态回退到 listening 场景。"""
        scene = get_scene_for_state("nonexistent_state")
        assert scene == AVATAR_SCENE_MAP["listening"], (
            "未知状态应回退到 listening 场景"
        )


# ============================================================================
# 辅助函数测试
# ============================================================================


class TestToolSchemaHelpers:
    """工具 Schema 辅助函数测试。"""

    # ------------------------------------------------------------------
    # get_tool_names
    # ------------------------------------------------------------------

    def test_get_tool_names_returns_14(self) -> None:
        """验证 get_tool_names 返回 14 个工具名。"""
        names = get_tool_names()
        assert len(names) == 14, f"期望 14 个工具名，实际 {len(names)} 个"
        assert all(n.startswith("stableagent.") for n in names)

    # ------------------------------------------------------------------
    # get_tool_by_name
    # ------------------------------------------------------------------

    def test_get_tool_by_name_valid(self) -> None:
        """验证 get_tool_by_name 返回正确的工具定义。"""
        tool = get_tool_by_name("stableagent.memory.retrieve")
        assert tool is not None
        assert tool["name"] == "stableagent.memory.retrieve"
        assert tool["risk_level"] == "low"

    def test_get_tool_by_name_invalid(self) -> None:
        """验证 get_tool_by_name 对无效工具名返回 None。"""
        tool = get_tool_by_name("nonexistent.tool")
        assert tool is None

    # ------------------------------------------------------------------
    # get_avatar_state
    # ------------------------------------------------------------------

    def test_get_avatar_state_known_event(self) -> None:
        """验证 get_avatar_state 对已知事件返回正确状态。"""
        assert get_avatar_state("mcp.call.received") == "listening"
        assert get_avatar_state("task.completed") == "done"
        assert get_avatar_state("tool.failed") == "failed"
        assert get_avatar_state("eval.completed") == "grading"

    def test_get_avatar_state_unknown_event_returns_default(self) -> None:
        """验证未知事件返回 default 状态（当前为 'listening'）。"""
        result = get_avatar_state("completely.unknown.event")
        expected_default = AVATAR_STATE_MAP["default"]
        assert result == expected_default, (
            f"未知事件应返回 default 状态 '{expected_default}'，实际 '{result}'"
        )
        assert get_avatar_state("") == expected_default

    # ------------------------------------------------------------------
    # 测试 4：get_risk_level 返回合法值
    # ------------------------------------------------------------------

    def test_get_risk_level_returns_valid_values(self) -> None:
        """验证 get_risk_level 对已知工具返回合法值。"""
        valid_levels = {"low", "medium", "high", "forbidden"}

        for tool_name in get_tool_names():
            risk = get_risk_level(tool_name)
            assert risk in valid_levels, (
                f"get_risk_level('{tool_name}') 返回 '{risk}'，"
                f"不是合法值（{valid_levels}）"
            )

    def test_get_risk_level_unknown_returns_low(self) -> None:
        """验证 get_risk_level 对未知工具返回 'low'。"""
        assert get_risk_level("nonexistent.tool") == "low"
        assert get_risk_level("") == "low"
