#!/usr/bin/env python3
"""StableAgent Real LLM E2E Test — V10.

使用真实 LLM API key 跑完整端到端验证。
不打印 key，不写 key 到日志/报告。

前置条件:
- STABLE_AGENT_ENABLE_REAL_LLM=true
- OPENAI_API_KEY 存在
- 服务已启动 (uvicorn web.server:app)

用法::

    # 方式 1: 直接运行
    python tools/real_llm_e2e_test.py --base-url http://127.0.0.1:8000

    # 方式 2: 通过脚本
    bash scripts/real_llm_e2e_test.sh
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any

import requests

# 安全: 导入脱敏工具
from stable_agent.security.secret_masker import mask_secret, mask_text, is_secret_leaked


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        # 脱敏消息中可能存在的 key
        safe_msg = mask_text(message)
        raise AssertionError(safe_msg)


def post_json(url: str, payload: dict[str, Any], timeout: int = 60) -> tuple[int, dict[str, Any]]:
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


def extract_structured_content(data: dict[str, Any]) -> dict[str, Any]:
    """从 MCP 响应中提取 os_agent 的 data 字段。

    MCP 响应结构: result.structuredContent.data → 包含 run_id, event_api_ok 等
    """
    if "result" in data and isinstance(data["result"], dict):
        result = data["result"]
        sc = None
        if isinstance(result.get("structuredContent"), dict):
            sc = result["structuredContent"]
        elif isinstance(result.get("structured_content"), dict):
            sc = result["structured_content"]
        if sc is not None:
            # os_agent 的核心数据在 sc.data 里
            if isinstance(sc.get("data"), dict):
                return sc["data"]
            return sc

    if isinstance(data.get("structuredContent"), dict):
        sc = data["structuredContent"]
        if isinstance(sc.get("data"), dict):
            return sc["data"]
        return sc

    if isinstance(data.get("structured_content"), dict):
        sc = data["structured_content"]
        if isinstance(sc.get("data"), dict):
            return sc["data"]
        return sc

    if isinstance(data.get("data"), dict):
        return data["data"]

    return data


def check_no_key_leak(text: str, source: str) -> None:
    """检查文本中是否有 key 泄露。"""
    if is_secret_leaked(text):
        raise AssertionError(f"Key leak detected in {source}! Text has been masked.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")

    # 检查前置条件
    enable_real = os.environ.get("STABLE_AGENT_ENABLE_REAL_LLM", "false").lower() == "true"
    api_key = os.environ.get("OPENAI_API_KEY", "")

    if not enable_real:
        print("SKIP: STABLE_AGENT_ENABLE_REAL_LLM not set to 'true'")
        print("To run real LLM E2E test, set STABLE_AGENT_ENABLE_REAL_LLM=true and provide OPENAI_API_KEY")
        return 0

    if not api_key:
        print("SKIP: OPENAI_API_KEY not set")
        return 0

    print(f"Real LLM E2E test starting (key masked: {mask_secret(api_key)})")
    print("")

    report_lines: list[str] = []
    report_lines.append("# Real LLM E2E Test Report\n")
    report_lines.append(f"Key (masked): {mask_secret(api_key)}\n")
    report_lines.append(f"Base URL: {base_url}\n\n")

    try:
        # Test 1: tools/list
        print("[1/6] MCP tools/list")
        status, data = post_json(f"{base_url}/mcp", {
            "jsonrpc": "2.0", "id": "tools-list-real",
            "method": "tools/list", "params": {},
        })
        # 检查 key 泄露
        check_no_key_leak(json.dumps(data), "tools/list response")

        assert_true(200 <= status < 500, f"tools/list HTTP {status}")
        tool_names = []
        if "result" in data and isinstance(data["result"], dict):
            tool_names = [t.get("name", "") for t in data["result"].get("tools", [])]
        assert_true(any("os_agent" in n for n in tool_names), "os_agent not found")
        report_lines.append("1. tools/list: PASS\n")
        print("  OK")

        # Test 2: Normal path with real LLM
        print("[2/6] Normal path (real LLM)")
        status, data = post_json(f"{base_url}/mcp", {
            "jsonrpc": "2.0", "id": "real-normal",
            "method": "tools/call",
            "params": {
                "name": "stableagent.task.os_agent",
                "arguments": {
                    "task_input": "帮我检查这个 Python 函数的性能问题",
                    "mode": "auto",
                    "open_dashboard": True,
                },
            },
        }, timeout=120)
        check_no_key_leak(json.dumps(data), "normal path response")

        assert_true(200 <= status < 500, f"os_agent HTTP {status}")
        sc = extract_structured_content(data)
        run_id = sc.get("run_id")
        assert_true(bool(run_id), f"Missing run_id")
        report_lines.append(f"2. Normal path: run_id={run_id}\n")
        print(f"  OK run_id={run_id}")

        time.sleep(2)

        # Test 3: Check events API
        print("[3/6] Events API check (normal)")
        status, events_data = get_json(f"{base_url}/api/runs/{run_id}/events")
        assert_true(status == 200, f"Events API HTTP {status}")
        if isinstance(events_data, dict):
            events = events_data.get("events", [])
            event_count = events_data.get("event_count", len(events))
        else:
            events = events_data if isinstance(events_data, list) else []
            event_count = len(events)
        assert_true(event_count > 0, f"Events API returned no events (count={event_count})")
        report_lines.append(f"3. Events API: event_count={event_count}\n")
        print(f"  OK event_count={event_count}")

        # Test 4: Check event_api_ok in MCP response
        print("[4/6] event_api_ok / dashboard_replay_ok check")
        event_api_ok = sc.get("event_api_ok")
        api_event_count = sc.get("api_event_count", 0)
        dashboard_replay_ok = sc.get("dashboard_replay_ok")
        assert_true(event_api_ok is True, f"event_api_ok={event_api_ok}, api_event_count={api_event_count}")
        assert_true(dashboard_replay_ok is True, f"dashboard_replay_ok={dashboard_replay_ok}")
        report_lines.append(f"4. event_api_ok={event_api_ok}, dashboard_replay_ok={dashboard_replay_ok}\n")
        print(f"  OK event_api_ok={event_api_ok}")

        # Test 5: Failure learning path
        print("[5/6] Failure learning path (real LLM)")
        status, data = post_json(f"{base_url}/mcp", {
            "jsonrpc": "2.0", "id": "real-failure",
            "method": "tools/call",
            "params": {
                "name": "stableagent.task.os_agent",
                "arguments": {
                    "task_input": "测试失败学习路径",
                    "mode": "auto",
                    "open_dashboard": True,
                    "force_eval_failed": True,
                    "force_failure_mode": "intent_drift",
                    "force_regression_case": True,
                    "force_skill_patch": True,
                    "force_validation_passed": True,
                    "dry_run_learning": True,
                },
            },
        }, timeout=120)
        check_no_key_leak(json.dumps(data), "failure path response")

        sc_fail = extract_structured_content(data)
        run_id_fail = sc_fail.get("run_id")
        assert_true(bool(run_id_fail), f"Missing run_id in failure path")

        # 验证 best_skill_exported 不是 True
        si_report = sc_fail.get("si_report", {})
        assert_true(
            si_report.get("best_skill_exported") is not True,
            "best_skill_exported must NOT be True (dry_run_learning=True)"
        )

        time.sleep(2)

        # 验证 events API
        status2, events_data2 = get_json(f"{base_url}/api/runs/{run_id_fail}/events")
        assert_true(status2 == 200, f"Events API HTTP {status2} for failure path")
        if isinstance(events_data2, dict):
            event_count2 = events_data2.get("event_count", 0)
        else:
            event_count2 = len(events_data2) if isinstance(events_data2, list) else 0
        assert_true(event_count2 > 0, f"Failure path: events API empty (count={event_count2})")

        event_api_ok_fail = sc_fail.get("event_api_ok")
        assert_true(event_api_ok_fail is True, f"Failure path: event_api_ok={event_api_ok_fail}")

        report_lines.append(f"5. Failure path: run_id={run_id_fail}, event_count={event_count2}, event_api_ok={event_api_ok_fail}\n")
        print(f"  OK run_id={run_id_fail}")

        # Test 6: Key leak final scan
        print("[6/6] Key leak final scan")
        # 检查报告内容无泄露
        report_text = "".join(report_lines)
        check_no_key_leak(report_text, "report")
        report_lines.append("6. Key leak scan: PASS\n")
        print("  OK — no key leaks")

    except AssertionError as exc:
        safe_msg = mask_text(str(exc))
        print(f"[FAIL] {safe_msg}", file=sys.stderr)
        report_lines.append(f"\n[FAIL] {safe_msg}\n")
        # 写报告
        with open("REAL_LLM_E2E_REPORT.md", "w") as f:
            f.writelines(report_lines)
        return 1
    except Exception as exc:
        safe_msg = mask_text(str(exc))
        print(f"[ERROR] {safe_msg}", file=sys.stderr)
        report_lines.append(f"\n[ERROR] {safe_msg}\n")
        with open("REAL_LLM_E2E_REPORT.md", "w") as f:
            f.writelines(report_lines)
        return 1

    report_lines.append("\n---\n[PASS] All real LLM E2E tests passed.\n")

    # 最终 key 泄露检查
    final_text = "".join(report_lines)
    check_no_key_leak(final_text, "final report")

    with open("REAL_LLM_E2E_REPORT.md", "w") as f:
        f.writelines(report_lines)

    print("")
    print("[PASS] Real LLM E2E test completed. Report: REAL_LLM_E2E_REPORT.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
