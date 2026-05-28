"""test_mcp_response_adapter.py — ResponseAdapter 单元测试。

测试覆盖：
- to_mcp_content: 完整结果、错误结果、structuredContent 字段
- to_error_response: 错误响应格式
- to_tools_list_response: tools/list 响应格式
- 边界情况：None data、空 warnings
"""

from __future__ import annotations

import pytest

from stable_agent.gateway.response_adapter import ResponseAdapter
from stable_agent.models import StableAgentToolResult


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def adapter() -> ResponseAdapter:
    """创建响应适配器。"""
    return ResponseAdapter()


@pytest.fixture
def success_result() -> StableAgentToolResult:
    """创建一个成功的工具调用结果。"""
    return StableAgentToolResult(
        ok=True,
        run_id="run-001",
        tool_call_id="tc-001",
        tool_name="stableagent.memory.retrieve",
        data={"memories": [{"id": 1, "content": "test memory"}]},
        plain_text="成功检索到 1 条记忆",
        warnings=[],
        next_actions=[],
        trace_url="/runs/run-001",
        is_error=False,
    )


@pytest.fixture
def error_result() -> StableAgentToolResult:
    """创建一个错误的工具调用结果。"""
    return StableAgentToolResult(
        ok=False,
        run_id="run-002",
        tool_call_id="tc-002",
        tool_name="stableagent.task.process",
        data={},
        plain_text="任务处理失败：参数无效",
        warnings=["参数 task_input 为空"],
        next_actions=[],
        trace_url="/runs/run-002",
        is_error=True,
    )


# ============================================================================
# to_mcp_content — 完整结果
# ============================================================================


class TestToMcpContentFullResult:
    """测试 to_mcp_content 对完整成功结果的转换。"""

    def test_content_array_has_text_type(self, adapter: ResponseAdapter, success_result: StableAgentToolResult) -> None:
        """content 数组应包含 type=text 的条目。"""
        result: dict = adapter.to_mcp_content(success_result)
        assert "content" in result
        assert len(result["content"]) >= 1
        assert result["content"][0]["type"] == "text"

    def test_content_text_matches_plain_text(self, adapter: ResponseAdapter, success_result: StableAgentToolResult) -> None:
        """content.text 应与 plain_text 一致。"""
        result: dict = adapter.to_mcp_content(success_result)
        assert result["content"][0]["text"] == success_result.plain_text

    def test_structured_content_has_ok(self, adapter: ResponseAdapter, success_result: StableAgentToolResult) -> None:
        """structuredContent.ok 应为 True。"""
        result: dict = adapter.to_mcp_content(success_result)
        assert result["structuredContent"]["ok"] is True

    def test_structured_content_has_run_id(self, adapter: ResponseAdapter, success_result: StableAgentToolResult) -> None:
        """structuredContent.run_id 应与输入一致。"""
        result: dict = adapter.to_mcp_content(success_result)
        assert result["structuredContent"]["run_id"] == "run-001"

    def test_structured_content_has_data(self, adapter: ResponseAdapter, success_result: StableAgentToolResult) -> None:
        """structuredContent.data 应包含原始数据。"""
        result: dict = adapter.to_mcp_content(success_result)
        assert "memories" in result["structuredContent"]["data"]

    def test_is_error_flag_false_on_success(self, adapter: ResponseAdapter, success_result: StableAgentToolResult) -> None:
        """成功结果的 isError 应为 False。"""
        result: dict = adapter.to_mcp_content(success_result)
        assert result["isError"] is False


# ============================================================================
# to_mcp_content — 错误结果
# ============================================================================


class TestToMcpContentErrorResult:
    """测试 to_mcp_content 对错误结果的转换。"""

    def test_is_error_flag_true_on_error(self, adapter: ResponseAdapter, error_result: StableAgentToolResult) -> None:
        """错误结果的 isError 应为 True。"""
        result: dict = adapter.to_mcp_content(error_result)
        assert result["isError"] is True

    def test_structured_content_ok_false_on_error(self, adapter: ResponseAdapter, error_result: StableAgentToolResult) -> None:
        """错误结果的 structuredContent.ok 应为 False。"""
        result: dict = adapter.to_mcp_content(error_result)
        assert result["structuredContent"]["ok"] is False

    def test_warnings_in_structured_content(self, adapter: ResponseAdapter, error_result: StableAgentToolResult) -> None:
        """structuredContent.warnings 应包含警告信息。"""
        result: dict = adapter.to_mcp_content(error_result)
        assert len(result["structuredContent"]["warnings"]) >= 1


# ============================================================================
# structuredContent 完整字段验证
# ============================================================================


class TestStructuredContentFields:
    """测试 structuredContent 包含所有必需字段。"""

    REQUIRED_FIELDS: list[str] = [
        "ok", "run_id", "tool_name", "data", "warnings",
        "next_actions", "trace_url",
    ]

    def test_all_required_fields_present(self, adapter: ResponseAdapter, success_result: StableAgentToolResult) -> None:
        """structuredContent 应包含所有必需字段。"""
        result: dict = adapter.to_mcp_content(success_result)
        sc = result["structuredContent"]
        for field in self.REQUIRED_FIELDS:
            assert field in sc, f"缺少字段: {field}"

    def test_data_defaults_to_empty_dict(self, adapter: ResponseAdapter) -> None:
        """data 字段为空的工具结果仍应有空字典。"""
        result_with_empty_data = StableAgentToolResult(
            ok=True,
            run_id="r1",
            tool_name="t1",
            plain_text="ok",
            data={},
        )
        output: dict = adapter.to_mcp_content(result_with_empty_data)
        assert output["structuredContent"]["data"] == {}


# ============================================================================
# to_tools_list_response
# ============================================================================


class TestToToolsListResponse:
    """测试 to_tools_list_response 方法。"""

    def test_response_is_jsonrpc_2_0(self, adapter: ResponseAdapter) -> None:
        """响应应为 JSON-RPC 2.0 格式。"""
        tools: list[dict] = [
            {"name": "test.tool", "description": "测试工具", "input_schema": {}}
        ]
        resp: dict = adapter.to_tools_list_response(tools)
        assert resp["jsonrpc"] == "2.0"

    def test_result_contains_tools_array(self, adapter: ResponseAdapter) -> None:
        """result.tools 应为工具数组。"""
        tools: list[dict] = [
            {"name": "stableagent.memory.retrieve", "description": "检索记忆"},
            {"name": "stableagent.context.build", "description": "构建上下文包"},
        ]
        resp: dict = adapter.to_tools_list_response(tools)
        assert "result" in resp
        assert "tools" in resp["result"]
        assert len(resp["result"]["tools"]) == 2

    def test_tool_name_preserved(self, adapter: ResponseAdapter) -> None:
        """工具名称应完整保留。"""
        tools: list[dict] = [
            {"name": "stableagent.memory.retrieve", "description": "检索记忆"}
        ]
        resp: dict = adapter.to_tools_list_response(tools)
        assert resp["result"]["tools"][0]["name"] == "stableagent.memory.retrieve"

    def test_empty_tools_list(self, adapter: ResponseAdapter) -> None:
        """空工具列表应返回空数组。"""
        resp: dict = adapter.to_tools_list_response([])
        assert resp["result"]["tools"] == []


# ============================================================================
# to_error_response
# ============================================================================


class TestToErrorResponse:
    """测试 to_error_response 方法。"""

    def test_is_error_true(self, adapter: ResponseAdapter) -> None:
        """错误响应的 isError 应为 True。"""
        resp: dict = adapter.to_error_response("r1", "t1", "失败")
        assert resp["isError"] is True

    def test_content_contains_error_message(self, adapter: ResponseAdapter) -> None:
        """content 应包含错误消息文本。"""
        resp: dict = adapter.to_error_response("r1", "t1", "参数无效")
        assert resp["content"][0]["text"] == "参数无效"

    def test_structured_content_has_trace_url(self, adapter: ResponseAdapter) -> None:
        """structuredContent.trace_url 应包含 run_id。"""
        resp: dict = adapter.to_error_response("my-run", "t1", "错误")
        assert "/runs/my-run" in resp["structuredContent"]["trace_url"]

    def test_run_id_preserved(self, adapter: ResponseAdapter) -> None:
        """run_id 应正确保留。"""
        resp: dict = adapter.to_error_response("abc-123", "t1", "错误")
        assert resp["structuredContent"]["run_id"] == "abc-123"

    def test_tool_name_preserved(self, adapter: ResponseAdapter) -> None:
        """tool_name 应正确保留。"""
        resp: dict = adapter.to_error_response("r1", "stableagent.task.process", "错误")
        assert resp["structuredContent"]["tool_name"] == "stableagent.task.process"


# ============================================================================
# 边界情况
# ============================================================================


class TestEdgeCases:
    """测试边界情况。"""

    def test_fallback_when_data_none(self, adapter: ResponseAdapter) -> None:
        """data 为 None 时不会崩溃（由于 dataclass 默认值，data 始终为 dict）。"""
        # 使用默认构造，data 会自动设为 {}，不会为 None
        min_result = StableAgentToolResult(
            ok=True,
            run_id="r1",
            tool_name="test.tool",
            plain_text="ok",
        )
        result: dict = adapter.to_mcp_content(min_result)
        assert result["structuredContent"]["data"] == {}

    def test_empty_plain_text(self, adapter: ResponseAdapter) -> None:
        """plain_text 为空字符串时 content 不应崩溃。"""
        empty_result = StableAgentToolResult(
            ok=True,
            run_id="r1",
            tool_name="test.tool",
            plain_text="",
        )
        result: dict = adapter.to_mcp_content(empty_result)
        assert result["content"][0]["text"] == ""
