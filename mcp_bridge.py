#!/usr/bin/env python3
"""
StableAgent OS — MCP stdio-to-HTTP 桥接器

用于 Claude Code / OpenCode / Cursor 等不支持原生 HTTP 传输的 MCP 客户端。
从 stdin 读取 JSON-RPC 请求 → 转发到本地 HTTP MCP Gateway → stdout 返回。

用法：
    python mcp_bridge.py [--url http://localhost:8000/mcp/v5/mcp]

在 OpenCode/claude 的 mcp.json 中配置：
    {
        "stableagent": {
            "command": "python3",
            "args": ["mcp_bridge.py"],
            "cwd": "/path/to/OS-Agent"
        }
    }
"""

import sys
import json
import argparse
import http.client
from urllib.parse import urlparse


MCP_URL = "http://localhost:8000/mcp/v5/mcp"


def forward(request: dict, url: str) -> dict:
    """转发 JSON-RPC 请求到 HTTP MCP 端点。"""
    parsed = urlparse(url)
    conn = http.client.HTTPConnection(parsed.hostname, parsed.port)
    body = json.dumps(request, ensure_ascii=False)

    try:
        conn.request("POST", parsed.path, body, {"Content-Type": "application/json"})
        response = conn.getresponse()
        data = response.read().decode("utf-8")
        return json.loads(data)
    except Exception as e:
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "error": {"code": -32603, "message": f"桥接错误: {e}"},
        }
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=MCP_URL, help="MCP HTTP 端点 URL")
    args = parser.parse_args()

    url = args.url

    # 初始化握手
    init_req = {
        "jsonrpc": "2.0",
        "id": 0,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "clientInfo": {"name": "opencode-mcp-bridge", "version": "1.0.0"},
            "capabilities": {},
        },
    }
    init_resp = forward(init_req, url)
    # 写入初始化结果（可选，通常不必要）
    sys.stderr.write(f"[StableAgent MCP Bridge] 已连接 {url}\n")
    sys.stderr.write(f"[StableAgent MCP Bridge] 服务端: {init_resp.get('result', {}).get('serverInfo', {}).get('name', 'unknown')}\n")
    sys.stderr.flush()

    # 主循环：逐行读取 JSON-RPC → 转发 → 返回
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            sys.stderr.write(f"[StableAgent MCP Bridge] 无效 JSON: {line[:100]}\n")
            continue

        response = forward(request, url)
        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
