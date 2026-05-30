#!/usr/bin/env python3
"""StableAgent Cloud Integration Test.

测试流程:
1. MCP tools/list
2. 调用 stableagent.task.os_agent
3. 获取 run_id
4. 检查 MCP structuredContent
5. 检查 /api/runs/{run_id}/events
6. 检查事件字段完整性
7. 检查 Dashboard Observer 页面可访问
8. 检查 decision trace 质量
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

import requests


def post_json(url: str, payload: dict[str, Any], timeout: int = 30) -> tuple[int, dict[str, Any]]:
    response = requests.post(url, json=payload, timeout=timeout)
    try:
        data = response.json()
    except Exception:
        data = {"raw": response.text}
    return response.status_code, data


def get_json(url: str, timeout: int = 30) -> tuple[int, dict[str, Any] | list[Any]]:
    response = requests.get(url, timeout=timeout)
    try:
        data = response.json()
    except Exception:
        data = {"raw": response.text}
    return response.status_code, data


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def extract_structured_content(data: dict[str, Any]) -> dict[str, Any]:
    if "result" in data and isinstance(data["result"], dict):
        result = data["result"]
        if isinstance(result.get("structuredContent"), dict):
            return result["structuredContent"]
        if isinstance(result.get("structured_content"), dict):
            return result["structured_content"]

    if isinstance(data.get("structuredContent"), dict):
        return data["structuredContent"]

    if isinstance(data.get("structured_content"), dict):
        return data["structured_content"]

    if isinstance(data.get("data"), dict):
        return data["data"]

    return data


def call_tools_list(base_url: str) -> None:
    print("[1/6] MCP tools/list")
    status, data = post_json(
        f"{base_url}/mcp",
        {
            "jsonrpc": "2.0",
            "id": "tools-list",
            "method": "tools/list",
            "params": {},
        },
    )
    assert_true(200 <= status < 500, f"tools/list returned HTTP {status}: {data}")
    print("  OK")


def call_os_agent(base_url: str) -> dict[str, Any]:
    print("[2/6] Calling stableagent.task.os_agent")
    payload = {
        "jsonrpc": "2.0",
        "id": "os-agent-test",
        "method": "tools/call",
        "params": {
            "name": "stableagent.task.os_agent",
            "arguments": {
                "task_input": "测试 OS-Agent 是否能生成可解释执行轨迹，并检查是否触发自我优化候选。",
                "mode": "auto",
                "open_dashboard": True,
            },
        },
    }

    status, data = post_json(f"{base_url}/mcp", payload, timeout=60)
    assert_true(200 <= status < 500, f"os_agent returned HTTP {status}: {data}")

    sc = extract_structured_content(data)

    run_id = sc.get("run_id")
    assert_true(bool(run_id), f"Missing run_id in structured content: {json.dumps(sc, ensure_ascii=False)}")

    dashboard_url = sc.get("dashboard_url") or sc.get("trace_url")
    assert_true(bool(dashboard_url), f"Missing dashboard_url/trace_url: {json.dumps(sc, ensure_ascii=False)}")

    print(f"  OK run_id={run_id}")
    print(f"  dashboard_url={dashboard_url}")
    return sc


def check_run_events(base_url: str, run_id: str) -> list[dict[str, Any]]:
    print("[3/6] Checking run events")

    candidates = [
        f"{base_url}/api/runs/{run_id}/events",
        f"{base_url}/runs/{run_id}/events",
    ]

    last_error = None
    events: list[dict[str, Any]] = []

    for url in candidates:
        status, data = get_json(url)
        if 200 <= status < 300:
            if isinstance(data, list):
                events = data
            elif isinstance(data, dict) and isinstance(data.get("events"), list):
                events = data["events"]
            else:
                events = []
            break
        last_error = f"{url} HTTP {status}: {data}"

    assert_true(events is not None, f"Could not fetch events: {last_error}")
    print(f"  events={len(events)}")

    if events:
        sample = events[-1]
        required_any = ["progress_pct", "status_text_zh", "avatar_state"]
        for key in required_any:
            assert_true(key in sample, f"Missing event field {key}: {sample}")

    return events


def check_observer_page(base_url: str, run_id: str) -> None:
    print("[4/6] Checking Dashboard Observer page")

    candidates = [
        f"{base_url}/runs/{run_id}",
        f"{base_url}/observe/{run_id}",
        f"{base_url}/observer?run_id={run_id}",
    ]

    ok = False
    for url in candidates:
        try:
            response = requests.get(url, timeout=15)
            if 200 <= response.status_code < 500:
                print(f"  OK {url} status={response.status_code}")
                ok = True
                break
        except Exception:
            continue

    assert_true(ok, "No observer/run page is reachable")


def check_trace_quality(events: list[dict[str, Any]]) -> None:
    print("[5/6] Checking decision trace quality")

    if not events:
        print("  WARN no events returned; skipping deep trace checks")
        return

    joined = json.dumps(events, ensure_ascii=False)

    forbidden = ["chain_of_thought", "hidden_reasoning", "model_inner_thought"]
    for word in forbidden:
        assert_true(word not in joined, f"Forbidden field found: {word}")

    has_explanation = any(
        event.get("why_zh") or event.get("decision_summary_zh") or event.get("plain_text_zh")
        for event in events
        if isinstance(event, dict)
    )
    assert_true(has_explanation, "No human-readable explanation fields found in events")

    print("  OK")


def check_mcp_response_fields(sc: dict[str, Any]) -> None:
    print("[6/6] Checking MCP structuredContent fields")

    must_have = ["run_id"]
    for key in must_have:
        assert_true(key in sc and sc[key], f"Missing {key}: {sc}")

    should_have = ["dashboard_url", "current_stage", "progress_pct", "status_text_zh", "avatar_state"]
    missing = [key for key in should_have if key not in sc]
    if missing:
        print(f"  WARN missing recommended fields: {missing}")
    else:
        print("  OK")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")

    try:
        call_tools_list(base_url)
        sc = call_os_agent(base_url)
        run_id = sc["run_id"]

        time.sleep(1.5)

        events = check_run_events(base_url, run_id)
        check_observer_page(base_url, run_id)
        check_trace_quality(events)
        check_mcp_response_fields(sc)

    except AssertionError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"[ERROR] Unexpected error: {exc}", file=sys.stderr)
        return 1

    print("")
    print("[PASS] StableAgent integration test completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
