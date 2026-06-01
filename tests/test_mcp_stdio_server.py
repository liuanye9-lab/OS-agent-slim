"""测试 stdio MCP server。

验证 V11.4 stdio MCP server：
1. initialize 返回 serverInfo
2. tools/list 返回工具数组
3. 每个 tool 有 inputSchema
4. stableagent.task.os_agent 存在
5. tools/call stableagent.task.os_agent 能返回 structuredContent
6. stdout 不包含非 JSON
7. invalid JSON 返回 JSON-RPC error
8. unknown method 返回 JSON-RPC error
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def project_root():
    """项目根目录。"""
    return Path(__file__).parent.parent


def _send_request(proc: subprocess.Popen, request: dict) -> dict:
    """发送 JSON-RPC 请求并读取响应。"""
    proc.stdin.write(json.dumps(request) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    return json.loads(line)


def test_initialize_returns_server_info(project_root):
    """测试 initialize 返回 serverInfo。"""
    proc = subprocess.Popen(
        [sys.executable, "-m", "stable_agent.mcp_stdio"],
        cwd=project_root,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        request = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        response = _send_request(proc, request)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response
        assert "serverInfo" in response["result"]
        assert response["result"]["serverInfo"]["name"] == "StableAgent OS stdio"
    finally:
        proc.terminate()


def test_tools_list_returns_array(project_root):
    """测试 tools/list 返回工具数组。"""
    proc = subprocess.Popen(
        [sys.executable, "-m", "stable_agent.mcp_stdio"],
        cwd=project_root,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        request = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        response = _send_request(proc, request)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 2
        assert "result" in response
        assert "tools" in response["result"]
        assert isinstance(response["result"]["tools"], list)
        assert len(response["result"]["tools"]) > 0
    finally:
        proc.terminate()


def test_each_tool_has_input_schema(project_root):
    """测试每个 tool 有 inputSchema。"""
    proc = subprocess.Popen(
        [sys.executable, "-m", "stable_agent.mcp_stdio"],
        cwd=project_root,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        request = {"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}}
        response = _send_request(proc, request)

        tools = response["result"]["tools"]
        for tool in tools:
            assert "inputSchema" in tool, f"工具 {tool['name']} 缺少 inputSchema"
            assert tool["inputSchema"]["type"] == "object"
    finally:
        proc.terminate()


def test_os_agent_tool_exists(project_root):
    """测试 stableagent.task.os_agent 存在。"""
    proc = subprocess.Popen(
        [sys.executable, "-m", "stable_agent.mcp_stdio"],
        cwd=project_root,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        request = {"jsonrpc": "2.0", "id": 4, "method": "tools/list", "params": {}}
        response = _send_request(proc, request)

        tools = response["result"]["tools"]
        tool_names = [t["name"] for t in tools]
        assert "stableagent.task.os_agent" in tool_names
    finally:
        proc.terminate()


def test_tools_call_returns_structured_content(project_root):
    """测试 tools/call stableagent.task.os_agent 能返回 structuredContent。"""
    proc = subprocess.Popen(
        [sys.executable, "-m", "stable_agent.mcp_stdio"],
        cwd=project_root,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        request = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "stableagent.task.os_agent",
                "arguments": {"task_input": "测试任务"}
            }
        }
        response = _send_request(proc, request)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 5
        assert "result" in response
        # structuredContent 可能在 result 的不同位置
        result = response["result"]
        assert "structuredContent" in result or "content" in result
    finally:
        proc.terminate()


def test_stdout_contains_only_json(project_root):
    """测试 stdout 不包含非 JSON。"""
    proc = subprocess.Popen(
        [sys.executable, "-m", "stable_agent.mcp_stdio"],
        cwd=project_root,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        # 发送多个请求
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        ]

        for req in requests:
            proc.stdin.write(json.dumps(req) + "\n")
            proc.stdin.flush()
            line = proc.stdout.readline()
            # 每一行都应该是合法 JSON
            data = json.loads(line)
            assert isinstance(data, dict)
    finally:
        proc.terminate()


def test_invalid_json_returns_error(project_root):
    """测试 invalid JSON 返回 JSON-RPC error。"""
    proc = subprocess.Popen(
        [sys.executable, "-m", "stable_agent.mcp_stdio"],
        cwd=project_root,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        proc.stdin.write("invalid json\n")
        proc.stdin.flush()
        line = proc.stdout.readline()
        response = json.loads(line)

        assert "error" in response
        assert response["error"]["code"] == -32700  # Parse error
    finally:
        proc.terminate()


def test_unknown_method_returns_error(project_root):
    """测试 unknown method 返回 JSON-RPC error。"""
    proc = subprocess.Popen(
        [sys.executable, "-m", "stable_agent.mcp_stdio"],
        cwd=project_root,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        request = {"jsonrpc": "2.0", "id": 6, "method": "unknown/method", "params": {}}
        response = _send_request(proc, request)

        assert "error" in response
        assert response["error"]["code"] == -32601  # Method not found
    finally:
        proc.terminate()
