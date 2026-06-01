"""test_mcp_tools_input_schema_compat — MCP tools/list inputSchema 兼容性测试。

验证 Claude Code MCP 客户端要求的 inputSchema (camelCase) 字段在所有返回路径中存在。
覆盖 tools/list JSON-RPC 和 GET /tools 两个端点。
"""

from __future__ import annotations

import pytest
from stable_agent.gateway.unified_tool_registry import UnifiedToolRegistry
from stable_agent.gateway.response_adapter import ResponseAdapter
from stable_agent.gateway.jsonrpc_handler import JSONRPCHandler
from stable_agent.gateway.mcp_gateway import MCPGateway


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def registry() -> UnifiedToolRegistry:
    return UnifiedToolRegistry()


@pytest.fixture
def adapter() -> ResponseAdapter:
    return ResponseAdapter()


@pytest.fixture
def handler(registry: UnifiedToolRegistry, adapter: ResponseAdapter) -> JSONRPCHandler:
    return JSONRPCHandler(registry, router=None, adapter=adapter)


# ---------------------------------------------------------------------------
# 1. tools/list 返回 55 个工具
# ---------------------------------------------------------------------------

def test_tools_list_returns_55_tools(handler: JSONRPCHandler) -> None:
    resp = handler.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    tools = resp["result"]["tools"]
    assert len(tools) == 55, f"期望 55 个工具，实际 {len(tools)}"


# ---------------------------------------------------------------------------
# 2. 每个 tool 都有 inputSchema
# ---------------------------------------------------------------------------

def test_every_tool_has_input_schema_field(handler: JSONRPCHandler) -> None:
    resp = handler.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    tools = resp["result"]["tools"]
    missing = [t["name"] for t in tools if "inputSchema" not in t]
    assert not missing, f"以下工具缺少 inputSchema: {missing}"


# ---------------------------------------------------------------------------
# 3. 每个 inputSchema 都是 dict/object
# ---------------------------------------------------------------------------

def test_every_input_schema_is_dict(handler: JSONRPCHandler) -> None:
    resp = handler.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    tools = resp["result"]["tools"]
    non_dict = [t["name"] for t in tools if not isinstance(t.get("inputSchema"), dict)]
    assert not non_dict, f"以下工具的 inputSchema 不是 dict: {non_dict}"


# ---------------------------------------------------------------------------
# 4. stableagent.task.os_agent 存在
# ---------------------------------------------------------------------------

def test_os_agent_tool_exists(handler: JSONRPCHandler) -> None:
    resp = handler.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    tools = resp["result"]["tools"]
    names = [t["name"] for t in tools]
    assert "stableagent.task.os_agent" in names, "stableagent.task.os_agent 未注册"


# ---------------------------------------------------------------------------
# 5. os_agent.inputSchema.properties 包含 task_input
# ---------------------------------------------------------------------------

def test_os_agent_schema_has_task_input_property(handler: JSONRPCHandler) -> None:
    resp = handler.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    tools = resp["result"]["tools"]
    os_agent = next(t for t in tools if t["name"] == "stableagent.task.os_agent")
    properties = os_agent["inputSchema"].get("properties", {})
    assert "task_input" in properties, (
        f"os_agent.inputSchema.properties 缺少 task_input，实际 keys: {list(properties)}"
    )


# ---------------------------------------------------------------------------
# 6. 不应只存在 input_schema 而没有 inputSchema
# ---------------------------------------------------------------------------

def test_no_tool_has_only_input_schema_without_inputSchema(handler: JSONRPCHandler) -> None:
    resp = handler.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    tools = resp["result"]["tools"]
    bad = [
        t["name"]
        for t in tools
        if "input_schema" in t and "inputSchema" not in t
    ]
    assert not bad, f"以下工具只有 input_schema 没有 inputSchema: {bad}"


# ---------------------------------------------------------------------------
# 7. GET /tools (registry.list_tools 直接输出) 也返回 inputSchema
# ---------------------------------------------------------------------------

def test_registry_list_tools_returns_input_schema(registry: UnifiedToolRegistry) -> None:
    tools = registry.list_tools()
    missing = [t["name"] for t in tools if "inputSchema" not in t]
    assert not missing, f"registry.list_tools() 以下工具缺少 inputSchema: {missing}"


def test_registry_list_tools_input_schema_is_dict(registry: UnifiedToolRegistry) -> None:
    tools = registry.list_tools()
    non_dict = [t["name"] for t in tools if not isinstance(t.get("inputSchema"), dict)]
    assert not non_dict, f"registry.list_tools() 以下工具的 inputSchema 不是 dict: {non_dict}"
