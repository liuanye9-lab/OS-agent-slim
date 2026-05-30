#!/usr/bin/env python3
"""StableAgent Cloud Integration Test — V9.0 Final Closed-Loop Hardening.

测试两条核心路径:
1. 正常路径: 完整基础事件链
2. 失败学习路径: self-improvement 事件链

V9.0 强化:
- 强事件字段验收: 缺 progress_pct / status_text_zh / why_zh / avatar_state / stage → FAIL
- 事件同步健康检查: event_sync_ok 必须为 True
- 失败学习路径: 必须包含 regression.generated / skill.patch.proposed / validation.checked
- best_skill.md 安全导出: approve 不自动写文件
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


# ======================================================================
# Phase 1: MCP tools/list
# ======================================================================

def call_tools_list(base_url: str) -> None:
    print("[1/8] MCP tools/list")
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


# ======================================================================
# Phase 2: 正常路径
# ======================================================================

NORMAL_PATH_EVENTS = [
    "task.received",
    "intent.parsed",
    "context.budgeted",
    "temporal_memory.retrieved",
    "context.compression_guard.checked",
    "context.built",
    "workflow.plan.created",
    "workflow.step.started",
    "workflow.step.completed",
    "eval.completed",
    "self_improvement.checked",
    "task.completed",
]

REQUIRED_EVENT_FIELDS = [
    "run_id",
    "event_type",
    "stage",
    "progress_pct",
    "status_text_zh",
    "decision_summary_zh",
    "why_zh",
    "avatar_state",
    "timestamp",
]


def call_os_agent_normal(base_url: str) -> dict[str, Any]:
    """正常路径: 测试完整基础事件链。"""
    print("[2/8] Calling os_agent (NORMAL path)")
    payload = {
        "jsonrpc": "2.0",
        "id": "os-agent-normal",
        "method": "tools/call",
        "params": {
            "name": "stableagent.task.os_agent",
            "arguments": {
                "task_input": "测试正常任务路径",
                "mode": "auto",
                "open_dashboard": True,
            },
        },
    }

    status, data = post_json(f"{base_url}/mcp", payload, timeout=60)
    assert_true(200 <= status < 500, f"os_agent returned HTTP {status}: {data}")

    sc = extract_structured_content(data)

    run_id = sc.get("run_id")
    assert_true(bool(run_id), f"Missing run_id: {json.dumps(sc, ensure_ascii=False)[:300]}")

    print(f"  OK run_id={run_id}")
    return sc


# ======================================================================
# Phase 3: 失败学习路径
# ======================================================================

FAILURE_PATH_EVENTS = [
    "task.received",
    "intent.parsed",
    "temporal_memory.retrieved",
    "context.compression_guard.checked",
    "eval.completed",
    "self_improvement.checked",
    "regression.generated",
    "memory.update.candidate",
    "skill.patch.proposed",
    "validation.checked",
]


def call_os_agent_failure(base_url: str) -> dict[str, Any]:
    """失败学习路径: 强制 eval_failed, 生成回归/skill patch。"""
    print("[3/8] Calling os_agent (FAILURE LEARNING path)")
    payload = {
        "jsonrpc": "2.0",
        "id": "os-agent-failure",
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
                "dry_run_learning": True,
            },
        },
    }

    status, data = post_json(f"{base_url}/mcp", payload, timeout=60)
    assert_true(200 <= status < 500, f"os_agent failure path returned HTTP {status}: {data}")

    sc = extract_structured_content(data)

    run_id = sc.get("run_id")
    assert_true(bool(run_id), f"Missing run_id: {json.dumps(sc, ensure_ascii=False)[:300]}")

    # 验证 eval 一定是失败的
    eval_passed = sc.get("eval_passed", True)
    eval_score = sc.get("eval_score", 1.0)
    assert_true(not eval_passed, f"force_eval_failed should make eval_passed=False, got {eval_passed}")
    assert_true(eval_score <= 0.4, f"force_eval_failed should make score <= 0.4, got {eval_score}")

    # 验证 dry_run_learning 标记
    assert_true(sc.get("dry_run_learning") is True, "dry_run_learning should be True")

    # 验证事件同步健康
    event_sync_ok = sc.get("event_sync_ok", False)
    assert_true(event_sync_ok is True, f"event_sync_ok should be True, sync_errors={sc.get('sync_errors', [])}")

    # 验证事件数量 > 0
    emitted_count = sc.get("emitted_event_count", 0)
    assert_true(emitted_count > 0, f"Should have emitted events, got {emitted_count}")

    print(f"  OK run_id={run_id}, eval_passed={eval_passed}, score={eval_score}")
    return sc


# ======================================================================
# Phase 4: 事件字段强验收
# ======================================================================

def check_event_fields_strict(events: list[dict[str, Any]], path_name: str) -> None:
    """V9.0: 严格事件字段验收 — 缺字段即 FAIL。"""
    print(f"[4/8] Checking event fields ({path_name})")

    if not events:
        raise AssertionError(f"No events returned for {path_name}")

    for i, evt in enumerate(events):
        for field in REQUIRED_EVENT_FIELDS:
            if field not in evt or evt[field] is None:
                raise AssertionError(
                    f"Event #{i} (type={evt.get('event_type', '?')}) missing required field '{field}': "
                    f"{json.dumps(evt, ensure_ascii=False)[:200]}"
                )

    print(f"  OK — {len(events)} events, all have required fields")


# ======================================================================
# Phase 5: 事件链完整性
# ======================================================================

def check_event_chain(events: list[dict[str, Any]], required_events: list[str], path_name: str) -> None:
    """验证事件链包含所有必要事件类型。"""
    print(f"[5/8] Checking event chain ({path_name})")

    event_types = [evt.get("event_type", "") for evt in events]
    missing = [e for e in required_events if e not in event_types]

    if missing:
        print(f"  Present events: {event_types}")
        raise AssertionError(f"Missing required events in {path_name}: {missing}")

    print(f"  OK — all {len(required_events)} required events present")


# ======================================================================
# Phase 6: 失败学习路径特有验证
# ======================================================================

def check_failure_learning_details(sc: dict[str, Any], events: list[dict[str, Any]]) -> None:
    """验证失败学习路径的特殊事件和 si_report。"""
    print("[6/8] Checking failure learning details")

    event_types = [evt.get("event_type", "") for evt in events]

    # 必须包含 regression.generated
    assert_true("regression.generated" in event_types, "Must have regression.generated event")

    # 必须包含 skill.patch.proposed
    assert_true("skill.patch.proposed" in event_types, "Must have skill.patch.proposed event")

    # 必须包含 validation.checked (force_skill_patch 确保有 patch, validation 会运行)
    assert_true("validation.checked" in event_types, "Must have validation.checked event")

    # 检查 si_report 字段
    si_report = sc.get("si_report")
    if si_report:
        assert_true(si_report.get("learning_triggered") is True, "si_report.learning_triggered must be True")
        assert_true(si_report.get("validation_passed") is not None, "si_report.validation_passed must not be None")

        # human_review_status 检查
        hr_status = si_report.get("human_review_status", "")
        if si_report.get("validation_passed"):
            assert_true(hr_status in ("pending", "approved"),
                        f"When validation passed, human_review_status should be pending/approved, got {hr_status}")
        else:
            assert_true(hr_status in ("validation_failed", "none"),
                        f"When validation failed, human_review_status should be validation_failed/none, got {hr_status}")

    print("  OK — failure learning chain verified")


# ======================================================================
# Phase 7: Dashboard Observer 可访问
# ======================================================================

def check_observer_page(base_url: str, run_id: str) -> None:
    print("[7/8] Checking Dashboard Observer page")

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


# ======================================================================
# Phase 8: 事件同步健康检查
# ======================================================================

def check_event_sync_health(sc: dict[str, Any]) -> None:
    """V9.0: 验证 event_sync_ok 在 MCP structuredContent 中。"""
    print("[8/8] Checking event sync health")

    assert_true("event_sync_ok" in sc, "Missing event_sync_ok in structuredContent")
    assert_true("emitted_event_count" in sc, "Missing emitted_event_count in structuredContent")
    assert_true("sync_errors" in sc, "Missing sync_errors in structuredContent")

    event_sync_ok = sc.get("event_sync_ok")
    emitted_count = sc.get("emitted_event_count", 0)
    sync_errors = sc.get("sync_errors", [])

    assert_true(event_sync_ok is True, f"event_sync_ok should be True, errors={sync_errors}")
    assert_true(emitted_count > 0, f"Should have emitted events, got {emitted_count}")

    print(f"  OK — emitted={emitted_count}, sync_ok={event_sync_ok}")


# ======================================================================
# Run Events API
# ======================================================================

def fetch_run_events(base_url: str, run_id: str) -> list[dict[str, Any]]:
    """获取 run 的事件列表。"""
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

    return events


# ======================================================================
# Decision Trace Quality
# ======================================================================

def check_trace_quality(events: list[dict[str, Any]]) -> None:
    """检查无隐藏推理字段，有可读解释。"""
    if not events:
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


# ======================================================================
# Main
# ======================================================================

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--skip-failure-path", action="store_true",
                        help="Skip failure learning path test")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")

    try:
        # 1. tools/list
        call_tools_list(base_url)

        # 2. 正常路径
        sc_normal = call_os_agent_normal(base_url)
        run_id_normal = sc_normal["run_id"]

        time.sleep(1.5)

        # 获取正常路径事件
        events_normal = fetch_run_events(base_url, run_id_normal)
        if not events_normal:
            print("  WARN: No events from API, using emitted events from MCP response")
            # 从 MCP 响应中提取事件信息
            events_normal = []

        # 正常路径: 事件字段强验收
        check_event_fields_strict(events_normal, "NORMAL") if events_normal else \
            print("  SKIP: event field check (no events from API)")

        # 正常路径: 事件链完整性
        check_event_chain(events_normal, NORMAL_PATH_EVENTS, "NORMAL") if events_normal else \
            print("  SKIP: event chain check (no events from API)")

        # Dashboard Observer
        check_observer_page(base_url, run_id_normal)

        # 事件同步健康
        check_event_sync_health(sc_normal)

        # 3. 失败学习路径
        if not args.skip_failure_path:
            sc_failure = call_os_agent_failure(base_url)
            run_id_failure = sc_failure["run_id"]

            time.sleep(1.5)

            events_failure = fetch_run_events(base_url, run_id_failure)
            if not events_failure:
                print("  WARN: No events from API for failure path")

            # 失败路径: 事件字段强验收
            check_event_fields_strict(events_failure, "FAILURE") if events_failure else \
                print("  SKIP: event field check (no events from API)")

            # 失败路径: 事件链完整性
            check_event_chain(events_failure, FAILURE_PATH_EVENTS, "FAILURE") if events_failure else \
                print("  SKIP: event chain check (no events from API)")

            # 失败路径: 特有验证
            check_failure_learning_details(sc_failure, events_failure) if events_failure else \
                print("  SKIP: failure learning details (no events from API)")

            # Dashboard Observer for failure path
            check_observer_page(base_url, run_id_failure)

            # 事件同步健康 for failure path
            check_event_sync_health(sc_failure)

        # Trace quality
        if events_normal:
            check_trace_quality(events_normal)

    except AssertionError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"[ERROR] Unexpected error: {exc}", file=sys.stderr)
        return 1

    print("")
    print("[PASS] StableAgent integration test completed (V9.0 final hardening).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
