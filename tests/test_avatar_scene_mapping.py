"""test_avatar_scene_mapping — 测试 avatar_state 映射正确。"""
import pytest


# 模拟 RunLifecycle 的 avatar_state 映射
AVATAR_SCENE_MAP = {
    "listening": {"scene": "desk", "labelZh": "接收任务", "prop": "task_card"},
    "thinking": {"scene": "thinking_board", "labelZh": "理解需求", "prop": "magnifier"},
    "calculating": {"scene": "budget_panel", "labelZh": "计算预算", "prop": "abacus"},
    "reading_notes": {"scene": "memory_wall", "labelZh": "找时间记忆", "prop": "memory_cards"},
    "searching_books": {"scene": "library", "labelZh": "查项目资料", "prop": "books"},
    "organizing": {"scene": "context_table", "labelZh": "压缩上下文", "prop": "context_blocks"},
    "planning": {"scene": "map_table", "labelZh": "规划步骤", "prop": "route_map"},
    "tooling": {"scene": "tool_bench", "labelZh": "调用工具", "prop": "wrench"},
    "watching": {"scene": "monitor", "labelZh": "观察结果", "prop": "screen"},
    "grading": {"scene": "exam_table", "labelZh": "评估结果", "prop": "score_sheet"},
    "diagnosing": {"scene": "diagnosis_board", "labelZh": "分析失败", "prop": "warning_card"},
    "writing_case": {"scene": "case_desk", "labelZh": "生成错题", "prop": "case_file"},
    "learning": {"scene": "skill_book", "labelZh": "提出改法", "prop": "skill_patch"},
    "waiting_approval": {"scene": "approval_gate", "labelZh": "等待审核", "prop": "red_card"},
    "archiving": {"scene": "archive_cabinet", "labelZh": "导出规则", "prop": "best_skill"},
    "done": {"scene": "delivery_desk", "labelZh": "完成任务", "prop": "checkmark"},
    "failed": {"scene": "error_board", "labelZh": "任务失败", "prop": "error_sign"},
    "idle": {"scene": "desk", "labelZh": "空闲", "prop": "coffee"},
}


class TestAvatarSceneMapping:
    """Avatar 场景映射测试。"""

    def test_all_runlifecycle_states_have_mapping(self):
        """RunLifecycle 的所有 avatar_state 应有映射。"""
        try:
            from stable_agent.runtime.run_lifecycle import RUN_STAGE_META
            for stage, meta in RUN_STAGE_META.items():
                assert meta.avatar_state in AVATAR_SCENE_MAP, \
                    f"{stage} 的 avatar_state '{meta.avatar_state}' 无场景映射"
        except ImportError:
            pytest.skip("RunLifecycle 模块不可用")

    def test_every_scene_has_label(self):
        """每个场景应有中文标签。"""
        for state, info in AVATAR_SCENE_MAP.items():
            assert info["labelZh"], f"{state} 缺少 labelZh"
            assert info["scene"], f"{state} 缺少 scene"

    def test_failed_maps_to_error_board(self):
        """failed 应映射到 error_board。"""
        info = AVATAR_SCENE_MAP["failed"]
        assert info["scene"] == "error_board"
        assert info["labelZh"] == "任务失败"

    def test_done_maps_to_delivery_desk(self):
        """done 应映射到 delivery_desk。"""
        info = AVATAR_SCENE_MAP["done"]
        assert info["scene"] == "delivery_desk"
        assert info["labelZh"] == "完成任务"

    def test_listening_maps_to_desk(self):
        """listening 应映射到 desk。"""
        info = AVATAR_SCENE_MAP["listening"]
        assert info["scene"] == "desk"

    def test_waiting_approval_maps_to_approval_gate(self):
        """waiting_approval 应映射到 approval_gate。"""
        info = AVATAR_SCENE_MAP["waiting_approval"]
        assert info["scene"] == "approval_gate"

    def test_learning_maps_to_skill_book(self):
        """learning 应映射到 skill_book。"""
        info = AVATAR_SCENE_MAP["learning"]
        assert info["scene"] == "skill_book"

    def test_archiving_maps_to_archive_cabinet(self):
        """archiving 应映射到 archive_cabinet。"""
        info = AVATAR_SCENE_MAP["archiving"]
        assert info["scene"] == "archive_cabinet"

    def test_unknown_state_handled(self):
        """未知 avatar_state 应能优雅处理。"""
        unknown = AVATAR_SCENE_MAP.get("nonexistent")
        assert unknown is None
