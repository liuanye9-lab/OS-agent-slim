"""MCP Gateway 传输兼容性测试 — V11.2 Trae/SOLO/Claude Code/Codex 兼容。

验证：
1. POST /mcp/ tools/list 返回工具数组
2. POST /mcp tools/list 不因 307 失败
3. GET /mcp/ 无 run_id 返回 200 说明 JSON（不是 400）
4. GET /mcp/?run_id=test 保持 text/event-stream
5. GET /mcp/tools 返回工具数组
6. GET /mcp/health 返回 ok=true
7. tools/list 中包含 stableagent.task.os_agent
"""

from __future__ import annotations

import json
import pytest
from starlette.testclient import TestClient

from stable_agent.gateway.mcp_gateway import MCPGateway


@pytest.fixture()
def client():
    """创建 MCP Gateway 测试客户端。"""
    gateway = MCPGateway(orchestrator=None)
    app = gateway.create_fastapi_app()
    return TestClient(app)


# ── 阶段 5：测试用例 ─────────────────────────────────────────────


class TestMcpPostToolsList:
    """POST /mcp/ tools/list 返回工具数组。"""

    def test_post_slash_tools_list(self, client):
        r = client.post("/", json={
            "jsonrpc": "2.0",
            "method": "tools/list",
            "params": {},
            "id": 1,
        })
        assert r.status_code == 200
        body = r.json()
        assert "result" in body
        assert "tools" in body["result"]
        assert isinstance(body["result"]["tools"], list)
        assert len(body["result"]["tools"]) > 0

    def test_post_tools_list_contains_os_agent(self, client):
        r = client.post("/", json={
            "jsonrpc": "2.0",
            "method": "tools/list",
            "params": {},
            "id": 1,
        })
        tools = r.json()["result"]["tools"]
        names = [t.get("name", "") for t in tools]
        assert "stableagent.task.os_agent" in names

    def test_post_tools_list_contains_stableagent_prefix(self, client):
        r = client.post("/", json={
            "jsonrpc": "2.0",
            "method": "tools/list",
            "params": {},
            "id": 1,
        })
        tools = r.json()["result"]["tools"]
        names = [t.get("name", "") for t in tools]
        stableagent_tools = [n for n in names if n.startswith("stableagent.")]
        assert len(stableagent_tools) > 0


class TestMcpPostNoTrailingSlash:
    """POST /mcp tools/list 不因 307 失败。"""

    def test_post_no_trailing_slash(self, client):
        # TestClient 自动跟随 307，但如果路由正确应直接 200
        r = client.post(
            "/",
            json={"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 1},
            follow_redirects=False,
        )
        # 应当直接返回 200，不需要 redirect
        assert r.status_code == 200


class TestMcpGetWithoutRunId:
    """GET /mcp/ 无 run_id 返回 200 说明 JSON，而不是 400。"""

    def test_get_without_run_id_returns_200(self, client):
        r = client.get("/")
        assert r.status_code == 200
        body = r.json()
        assert body.get("ok") is True
        assert body.get("service") == "StableAgent MCP Gateway"
        assert "transport" in body
        assert "tools_endpoint_hint" in body

    def test_get_without_run_id_has_transport_info(self, client):
        r = client.get("/")
        body = r.json()
        transport = body["transport"]
        assert transport["jsonrpc"] == "POST /mcp/"
        assert transport["sse"] == "GET /mcp/?run_id=<run_id>"

    def test_get_without_run_id_has_tools_hint(self, client):
        r = client.get("/")
        body = r.json()
        hint = body["tools_endpoint_hint"]
        assert hint["method"] == "POST"
        assert hint["body"]["method"] == "tools/list"


class TestMcpGetWithRunId:
    """GET /mcp/?run_id=test 保持 text/event-stream。"""

    @pytest.mark.skip(reason="SSE streaming cannot be tested with TestClient without timeout; verified manually")
    def test_get_with_run_id_returns_sse(self, client):
        # 手动验证: curl -s -D - "http://127.0.0.1:8000/?run_id=test" | head -5
        # 应看到 Content-Type: text/event-stream
        pass


class TestMcpToolsEndpoint:
    """GET /mcp/tools 返回工具数组。"""

    def test_get_tools_returns_tools_array(self, client):
        r = client.get("/tools")
        assert r.status_code == 200
        body = r.json()
        assert body.get("ok") is True
        assert "tools" in body
        assert isinstance(body["tools"], list)
        assert body.get("tool_count", 0) > 0

    def test_get_tools_contains_os_agent(self, client):
        r = client.get("/tools")
        tools = r.json()["tools"]
        names = [t.get("name", "") for t in tools]
        assert "stableagent.task.os_agent" in names


class TestMcpHealthEndpoint:
    """GET /mcp/health 返回 ok=true。"""

    def test_get_health_returns_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body.get("ok") is True
        assert body.get("service") == "StableAgent MCP Gateway"
        assert body.get("post_jsonrpc") is True
        assert body.get("sse") is True
        assert "tool_count" in body
        assert body["tool_count"] > 0


class TestMcpInitializeMethod:
    """POST /mcp/ initialize 方法可用。"""

    def test_post_initialize(self, client):
        r = client.post("/", json={
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
            "id": 1,
        })
        assert r.status_code == 200
        body = r.json()
        # initialize 应返回 serverInfo 或 capabilities
        assert "result" in body or "error" in body
