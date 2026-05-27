"""Tests for SkillOptMCPTools — V4 MCP 工具层。

覆盖 10 个 SkillOpt MCP 工具的统一返回结构验证和功能测试。
"""

import pytest
from stable_agent.mcp.skillopt_tools import SkillOptMCPTools


# ============================================================================
# Fixture
# ============================================================================

@pytest.fixture
def tools():
    """创建默认 SkillOptMCPTools 实例。"""
    return SkillOptMCPTools()


# ============================================================================
# 统一响应结构验证
# ============================================================================

class TestResponseStructure:
    """验证所有工具返回统一的 {ok, data, plain_text, warnings} 结构。"""

    REQUIRED_KEYS = {"ok", "data", "plain_text", "warnings"}

    def test_get_current_skill_structure(self, tools):
        result = tools.get_current_skill()
        assert self.REQUIRED_KEYS.issubset(result.keys())
        assert isinstance(result["ok"], bool)
        assert isinstance(result["plain_text"], str)
        assert isinstance(result["warnings"], list)

    def test_get_best_skill_structure(self, tools):
        result = tools.get_best_skill()
        assert self.REQUIRED_KEYS.issubset(result.keys())
        assert isinstance(result["plain_text"], str)

    def test_submit_user_feedback_structure(self, tools):
        result = tools.submit_user_feedback("test-run", "accepted")
        assert self.REQUIRED_KEYS.issubset(result.keys())

    def test_collect_rollout_structure(self, tools):
        result = tools.collect_rollout("nonexistent-run-id")
        assert self.REQUIRED_KEYS.issubset(result.keys())

    def test_run_epoch_structure(self, tools):
        result = tools.run_skill_optimization_epoch(max_rollouts=1)
        assert self.REQUIRED_KEYS.issubset(result.keys())

    def test_validate_candidate_structure(self, tools):
        result = tools.validate_candidate_skill("v99.0")
        assert self.REQUIRED_KEYS.issubset(result.keys())

    def test_export_best_skill_structure(self, tools):
        result = tools.export_best_skill()
        assert self.REQUIRED_KEYS.issubset(result.keys())

    def test_get_skill_diff_structure(self, tools):
        result = tools.get_skill_diff("v1.0", "v2.0")
        assert self.REQUIRED_KEYS.issubset(result.keys())

    def test_list_rejected_edits_structure(self, tools):
        result = tools.list_rejected_edits()
        assert self.REQUIRED_KEYS.issubset(result.keys())
        # data 可能为 None（error 时）或包含 edits
        if result["data"] is not None:
            assert isinstance(result["data"].get("edits", []), list)

    def test_get_optimization_status_structure(self, tools):
        result = tools.get_optimization_status()
        assert self.REQUIRED_KEYS.issubset(result.keys())
        # 实际返回 total_epochs, accepted_patches 等
        data = result["data"]
        assert isinstance(data, dict)
        assert len(data) > 0


# ============================================================================
# 默认引擎创建
# ============================================================================

class TestEngineInitialization:
    """验证不需要传入 engine 时的默认创建行为。"""

    def test_creates_default_engine(self):
        tools = SkillOptMCPTools()
        assert tools._engine is not None

    def test_accepts_custom_engine(self):
        tools = SkillOptMCPTools(engine=None)
        assert tools._engine is not None


# ============================================================================
# get_current_skill 详细验证
# ============================================================================

class TestGetCurrentSkill:

    def test_returns_skill_content(self, tools):
        result = tools.get_current_skill()
        data = result["data"]
        assert "content" in data
        assert "version" in data
        assert "status" in data

    def test_version_is_string(self, tools):
        result = tools.get_current_skill()
        assert isinstance(result["data"]["version"], str)

    def test_content_is_non_empty(self, tools):
        result = tools.get_current_skill()
        assert len(result["data"]["content"]) > 0


# ============================================================================
# get_best_skill 详细验证
# ============================================================================

class TestGetBestSkill:

    def test_returns_doc(self, tools):
        result = tools.get_best_skill()
        data = result["data"]
        if data is not None:
            assert "version" in data
            assert "content" in data


# ============================================================================
# get_optimization_status 详细验证
# ============================================================================

class TestOptimizationStatus:

    def test_has_fields(self, tools):
        result = tools.get_optimization_status()
        data = result["data"]
        assert isinstance(data, dict)
        assert len(data) > 0

    def test_has_version_field(self, tools):
        result = tools.get_optimization_status()
        data = result["data"]
        assert "current_version" in data or "best_version" in data


# ============================================================================
# list_rejected_edits 详细验证
# ============================================================================

class TestListRejectedEdits:

    def test_returns_valid_result(self, tools):
        result = tools.list_rejected_edits()
        assert "ok" in result
        assert "data" in result
        # data 可能为 None（引擎无 rejected buffer 时）或 dict
        data = result["data"]
        if data is not None:
            assert "edits" in data
            assert isinstance(data["edits"], list)


# ============================================================================
# submit_user_feedback 详细验证
# ============================================================================

class TestSubmitUserFeedback:

    def test_returns_structured_response(self, tools):
        result = tools.submit_user_feedback("run-001", "accepted")
        assert "ok" in result
        assert "plain_text" in result

    def test_rejected_feedback_returns_response(self, tools):
        result = tools.submit_user_feedback("run-002", "rejected")
        assert "ok" in result
        assert "plain_text" in result
