"""测试 HTTP MCP tools/call stableagent.task.os_agent。

验证 V11.4 连接层硬化要求：
1. tools/call stableagent.task.os_agent 返回 result
2. result.structuredContent.ok == true
3. 返回 run_id
4. 返回 dashboard_url
5. 返回 observer_url
6. 返回 missing_required_events
7. 返回 understanding_trace 字段，即使为空也必须存在
8. 返回 token_report 字段，即使为空也必须存在
9. 返回 expression_matches 字段，即使为空也必须存在
10. 异常路径返回 isError=true + error
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from stable_agent.gateway.jsonrpc_handler import JSONRPCHandler
from stable_agent.gateway.response_adapter import ResponseAdapter
from stable_agent.gateway.unified_tool_registry import UnifiedToolRegistry
from stable_agent.gateway.tool_router import ToolRouter
from stable_agent.models import StableAgentToolResult


@pytest.fixture
def mock_orchestrator():
    """创建 mock orchestrator。"""
    return MagicMock()


@pytest.fixture
def handler(mock_orchestrator):
    """创建 JSONRPCHandler 实例。"""
    registry = UnifiedToolRegistry(orchestrator=mock_orchestrator)
    router = ToolRouter(registry=registry)
    adapter = ResponseAdapter()
    return JSONRPCHandler(registry, router, adapter)


@pytest.fixture
def mock_handler_result():
    """创建 mock 工具执行结果。"""
    return StableAgentToolResult(
        ok=True,
        run_id="test_run_123",
        tool_call_id="tc_123",
        tool_name="stableagent.task.os_agent",
        plain_text="任务执行成功",
        data={
            "missing_required_events": [],
            "understanding_trace": {"task_input": "测试任务", "expressions": []},
            "token_report": {"total_tokens": 1000, "saved_tokens": 200},
            "expression_matches": [],
            "current_stage": "completed",
            "progress_pct": 100,
        },
        is_error=False,
    )


def test_tools_call_returns_result(handler, mock_handler_result):
    """测试 tools/call 返回 result。"""
    with patch.object(handler._router, 'route', return_value=mock_handler_result):
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "stableagent.task.os_agent",
                "arguments": {"task_input": "测试任务", "open_dashboard": True}
            }
        }
        response = handler.handle(request)

        assert "result" in response
        assert "structuredContent" in response["result"]
        assert response["result"]["isError"] is False


def test_structured_content_has_ok_field(handler, mock_handler_result):
    """测试 structuredContent 包含 ok 字段。"""
    with patch.object(handler._router, 'route', return_value=mock_handler_result):
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "stableagent.task.os_agent",
                "arguments": {"task_input": "测试任务"}
            }
        }
        response = handler.handle(request)
        sc = response["result"]["structuredContent"]

        assert "ok" in sc
        assert sc["ok"] is True


def test_structured_content_has_run_id(handler, mock_handler_result):
    """测试 structuredContent 包含 run_id。"""
    with patch.object(handler._router, 'route', return_value=mock_handler_result):
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "stableagent.task.os_agent",
                "arguments": {"task_input": "测试任务"}
            }
        }
        response = handler.handle(request)
        sc = response["result"]["structuredContent"]

        assert "run_id" in sc
        assert sc["run_id"] == "test_run_123"


def test_structured_content_has_dashboard_url(handler, mock_handler_result):
    """测试 structuredContent 包含 dashboard_url。"""
    with patch.object(handler._router, 'route', return_value=mock_handler_result):
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "stableagent.task.os_agent",
                "arguments": {"task_input": "测试任务"}
            }
        }
        response = handler.handle(request)
        sc = response["result"]["structuredContent"]

        assert "dashboard_url" in sc
        assert len(sc["dashboard_url"]) > 0


def test_structured_content_has_observer_url(handler, mock_handler_result):
    """测试 structuredContent 包含 observer_url。"""
    with patch.object(handler._router, 'route', return_value=mock_handler_result):
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "stableagent.task.os_agent",
                "arguments": {"task_input": "测试任务"}
            }
        }
        response = handler.handle(request)
        sc = response["result"]["structuredContent"]

        assert "observer_url" in sc
        assert "test_run_123" in sc["observer_url"]


def test_structured_content_has_missing_required_events(handler, mock_handler_result):
    """测试 structuredContent 包含 missing_required_events。"""
    with patch.object(handler._router, 'route', return_value=mock_handler_result):
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "stableagent.task.os_agent",
                "arguments": {"task_input": "测试任务"}
            }
        }
        response = handler.handle(request)
        sc = response["result"]["structuredContent"]

        assert "missing_required_events" in sc
        assert isinstance(sc["missing_required_events"], list)


def test_structured_content_has_understanding_trace(handler, mock_handler_result):
    """测试 structuredContent 包含 understanding_trace 字段，即使为空也必须存在。"""
    with patch.object(handler._router, 'route', return_value=mock_handler_result):
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "stableagent.task.os_agent",
                "arguments": {"task_input": "测试任务"}
            }
        }
        response = handler.handle(request)
        sc = response["result"]["structuredContent"]

        assert "understanding_trace" in sc


def test_structured_content_has_token_report(handler, mock_handler_result):
    """测试 structuredContent 包含 token_report 字段，即使为空也必须存在。"""
    with patch.object(handler._router, 'route', return_value=mock_handler_result):
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "stableagent.task.os_agent",
                "arguments": {"task_input": "测试任务"}
            }
        }
        response = handler.handle(request)
        sc = response["result"]["structuredContent"]

        assert "token_report" in sc


def test_structured_content_has_expression_matches(handler, mock_handler_result):
    """测试 structuredContent 包含 expression_matches 字段，即使为空也必须存在。"""
    with patch.object(handler._router, 'route', return_value=mock_handler_result):
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "stableagent.task.os_agent",
                "arguments": {"task_input": "测试任务"}
            }
        }
        response = handler.handle(request)
        sc = response["result"]["structuredContent"]

        assert "expression_matches" in sc


def test_error_path_returns_is_error_true(handler):
    """测试异常路径返回 isError=true + error。"""
    error_result = StableAgentToolResult(
        ok=False,
        run_id="error_run_123",
        tool_name="stableagent.task.os_agent",
        plain_text="工具执行失败：测试异常",
        data={"error": "测试异常"},
        is_error=True,
    )

    with patch.object(handler._router, 'route', return_value=error_result):
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "stableagent.task.os_agent",
                "arguments": {"task_input": "测试任务"}
            }
        }
        response = handler.handle(request)
        sc = response["result"]["structuredContent"]

        assert response["result"]["isError"] is True
        assert sc["ok"] is False
        assert "error" in sc
        assert sc["error"] is not None


def test_router_exception_returns_is_error_true(handler):
    """测试 router 异常时返回 isError=true + error。"""
    with patch.object(handler._router, 'route', side_effect=Exception("路由器异常")):
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "stableagent.task.os_agent",
                "arguments": {"task_input": "测试任务"}
            }
        }
        response = handler.handle(request)
        sc = response["result"]["structuredContent"]

        assert response["result"]["isError"] is True
        assert sc["ok"] is False
        assert "error" in sc
        assert "路由器异常" in sc["error"]
