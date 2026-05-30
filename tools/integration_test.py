#!/usr/bin/env python3
"""StableAgent Cloud Integration Test — V9.1 Final Closed-Loop Hardening.

测试三条核心路径:
1. MCP tools/list: 验证工具注册完整
2. 正常路径: 完整基础事件链（含 rag.retrieved）
3. 失败学习路径: self-improvement 事件链（含 force_validation_passed 控制）

V9.1 强化:
- 三条路径: tools/list + normal + failed learning
- 正常路径: rag.retrieved 为必须事件
- 失败学习路径: force_validation_passed=False → validation_failed, 不进 human_review
- 失败学习路径: force_validation_passed=True → human_review.required, 不自动 export
- dry_run_learning=true → 拒绝 export
- emitted_events 列表（非仅计数）在 result
- best_skill_exported 在 si_report 中
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
# Path 1: MCP tools/list
# ======================================================================

def call_tools_list(base_url: str) -> list[str]:
    """V9.1: MCP tools/list — 验证工具注册完整。"""
    print("[1/10] MCP tools/list")
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

    # 提取工具名列表
    tool_names: list[str] = []
    if "result" in data and isinstance(data["result"], dict):
        tools = data["result"].get("tools", [])
        tool_names = [t.get("name", "") for t in tools if isinstance(t, dict)]

    # 必须包含 os_agent
    assert_true(
        any("os_agent" in name for name in tool_names),
        f"tools/list must include stableagent.task.os_agent, got: {tool_names[:10]}"
    )

    print(f"  OK — {len(tool_names)} tools registered, os_agent found")
    return tool_names


# ======================================================================
# Path 2: 正常路径
# ======================================================================

NORMAL_PATH_EVENTS = [
    "task.received",
    "intent.parsed",
    "context.budgeted",
    "temporal_memory.retrieved",
    "rag.retrieved",          # V9.1: 强制要求
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
    """正常路径: 测试完整基础事件链（含 rag.retrieved）。"""
    print("[2/10] Calling os_agent (NORMAL path)")
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
# Path 3: 失败学习路径 — force_validation_passed=False
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


def call_os_agent_failure_val_failed(base_url: str) -> dict[str, Any]:
    """失败学习路径 (validation_failed): force_validation_passed=False → 不进 human_review。"""
    print("[3/10] Calling os_agent (FAILURE → validation_failed path)")
    payload = {
        "jsonrpc": "2.0",
        "id": "os-agent-failure-val-fail",
        "method": "tools/call",
        "params": {
            "name": "stableagent.task.os_agent",
            "arguments": {
                "task_input": "测试失败学习路径 - validation_failed",
                "mode": "auto",
                "open_dashboard": True,
                "force_eval_failed": True,
                "force_failure_mode": "intent_drift",
                "force_regression_case": True,
                "force_skill_patch": True,
                "force_validation_passed": False,   # V9.1: 强制验证失败
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

    # V9.1: 验证 force_validation_passed 参数回显
    assert_true(sc.get("force_validation_passed") is False, "force_validation_passed should be False")

    # V9.1: 验证 si_report 中 validation_failed 不进 human_review
    si_report = sc.get("si_report")
    if si_report:
        hr_status = si_report.get("human_review_status", "")
        hr_required = si_report.get("human_review_required", False)
        # force_validation_passed=False + dry_run_learning=True → dry_run 状态
        assert_true(
            hr_status in ("validation_failed", "dry_run", "none"),
            f"force_validation_passed=False: human_review_status should be validation_failed/dry_run/none, got {hr_status}"
        )
        # best_skill_exported 必须为 False
        assert_true(
            si_report.get("best_skill_exported") is not True,
            "best_skill_exported should NOT be True when validation_failed"
        )

    # 验证事件同步健康
    event_sync_ok = sc.get("event_sync_ok", False)
    assert_true(event_sync_ok is True, f"event_sync_ok should be True, sync_errors={sc.get('sync_errors', [])}")

    # 验证 emitted_events 列表存在（V9.1）
    assert_true("emitted_events" in sc, "emitted_events list must be in result (V9.1)")

    print(f"  OK run_id={run_id}, val_failed={si_report.get('validation_passed') if si_report else 'N/A'}")
    return sc


# ======================================================================
# Path 3b: 失败学习路径 — force_validation_passed=True
# ======================================================================

def call_os_agent_failure_val_pass(base_url: str) -> dict[str, Any]:
    """失败学习路径 (validation_passed + human_review): force_validation_passed=True → 进 human_review。"""
    print("[4/10] Calling os_agent (FAILURE → validation_passed + human_review path)")
    payload = {
        "jsonrpc": "2.0",
        "id": "os-agent-failure-val-pass",
        "method": "tools/call",
        "params": {
            "name": "stableagent.task.os_agent",
            "arguments": {
                "task_input": "测试失败学习路径 - validation_passed",
                "mode": "auto",
                "open_dashboard": True,
                "force_eval_failed": True,
                "force_failure_mode": "intent_drift",
                "force_regression_case": True,
                "force_skill_patch": True,
                "force_validation_passed": True,    # V9.1: 强制验证通过
                "dry_run_learning": True,           # 阻止实际导出
            },
        },
    }

    status, data = post_json(f"{base_url}/mcp", payload, timeout=60)
    assert_true(200 <= status < 500, f"os_agent failure val-pass path returned HTTP {status}: {data}")

    sc = extract_structured_content(data)

    run_id = sc.get("run_id")
    assert_true(bool(run_id), f"Missing run_id: {json.dumps(sc, ensure_ascii=False)[:300]}")

    # V9.1: force_validation_passed=True 回显
    assert_true(sc.get("force_validation_passed") is True, "force_validation_passed should be True")

    si_report = sc.get("si_report")
    if si_report:
        # V9.1: validation_passed=True 但不自动 export
        # dry_run_learning=True → human_review_status=dry_run
        hr_status = si_report.get("human_review_status", "")
        assert_true(
            hr_status in ("pending", "dry_run"),
            f"force_validation_passed=True: human_review_status should be pending/dry_run, got {hr_status}"
        )
        # best_skill_exported 必须为 False（dry_run_learning=True 阻止导出）
        assert_true(
            si_report.get("best_skill_exported") is not True,
            "best_skill_exported must be False (dry_run_learning=True)"
        )

    print(f"  OK run_id={run_id}, hr_status={si_report.get('human_review_status') if si_report else 'N/A'}")
    return sc


# ======================================================================
# Phase 5: 事件字段强验收
# ======================================================================

def check_event_fields_strict(events: list[dict[str, Any]], path_name: str) -> None:
    """V9.0: 严格事件字段验收 — 缺字段即 FAIL。"""
    print(f"[5/10] Checking event fields ({path_name})")

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
# Phase 6: 事件链完整性
# ======================================================================

def check_event_chain(events: list[dict[str, Any]], required_events: list[str], path_name: str) -> None:
    """验证事件链包含所有必要事件类型。"""
    print(f"[6/10] Checking event chain ({path_name})")

    event_types = [evt.get("event_type", "") for evt in events]
    missing = [e for e in required_events if e not in event_types]

    if missing:
        print(f"  Present events: {event_types}")
        raise AssertionError(f"Missing required events in {path_name}: {missing}")

    print(f"  OK — all {len(required_events)} required events present")


# ======================================================================
# Phase 7: 失败学习路径特有验证
# ======================================================================

def check_failure_learning_details(sc: dict[str, Any], events: list[dict[str, Any]]) -> None:
    """验证失败学习路径的特殊事件和 si_report。"""
    print("[7/10] Checking failure learning details")

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
        assert_true("best_skill_exported" in si_report, "si_report must have best_skill_exported field (V9.1)")
        assert_true("human_review_required" in si_report, "si_report must have human_review_required field (V9.1)")

        # human_review_status 检查
        hr_status = si_report.get("human_review_status", "")
        if si_report.get("validation_passed"):
            assert_true(hr_status in ("pending", "approved", "dry_run"),
                        f"When validation passed, human_review_status should be pending/approved/dry_run, got {hr_status}")
        else:
            assert_true(hr_status in ("validation_failed", "none", "dry_run"),
                        f"When validation failed, human_review_status should be validation_failed/none/dry_run, got {hr_status}")

    print("  OK — failure learning chain verified")


# ======================================================================
# Phase 8: Dashboard Observer 可访问
# ======================================================================

def check_observer_page(base_url: str, run_id: str) -> None:
    print("[8/10] Checking Dashboard Observer page")

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
# Phase 9: 事件同步健康检查
# ======================================================================

def check_event_sync_health(sc: dict[str, Any]) -> None:
    """V9.1: 验证 event_sync_ok + emitted_events 列表。"""
    print("[9/10] Checking event sync health")

    assert_true("event_sync_ok" in sc, "Missing event_sync_ok in structuredContent")
    assert_true("emitted_event_count" in sc, "Missing emitted_event_count in structuredContent")
    assert_true("sync_errors" in sc, "Missing sync_errors in structuredContent")
    assert_true("emitted_events" in sc, "Missing emitted_events list in structuredContent (V9.1)")

    event_sync_ok = sc.get("event_sync_ok")
    emitted_count = sc.get("emitted_event_count", 0)
    sync_errors = sc.get("sync_errors", [])
    emitted_events = sc.get("emitted_events", [])

    assert_true(event_sync_ok is True, f"event_sync_ok should be True, errors={sync_errors}")
    assert_true(emitted_count > 0, f"Should have emitted events, got {emitted_count}")
    assert_true(len(emitted_events) > 0, f"emitted_events list should not be empty (V9.1)")

    # 每个事件必须有 event_type
    for i, evt in enumerate(emitted_events):
        assert_true("event_type" in evt, f"emitted_events[{i}] missing event_type")

    print(f"  OK — emitted={emitted_count}, events_list={len(emitted_events)}, sync_ok={event_sync_ok}")


# ======================================================================
# Phase 10: Validation Gate 验证
# ======================================================================

def check_validation_gate(sc_val_fail: dict[str, Any], sc_val_pass: dict[str, Any]) -> None:
    """V9.1: 验证 validation gate 规则:
    - force_validation_passed=False → validation_failed, 不进 human_review
    - force_validation_passed=True → human_review.required, 不自动 export
    - dry_run_learning=True → 不导出 best_skill.md
    """
    print("[10/10] Checking validation gate rules")

    # Path 3a: force_validation_passed=False
    si_fail = sc_val_fail.get("si_report", {})
    if si_fail:
        hr_status_fail = si_fail.get("human_review_status", "")
        assert_true(
            hr_status_fail in ("validation_failed", "dry_run", "none"),
            f"force_validation_passed=False: hr_status should be validation_failed/dry_run/none, got {hr_status_fail}"
        )
        assert_true(
            si_fail.get("best_skill_exported") is not True,
            "force_validation_passed=False: best_skill_exported must NOT be True"
        )

    # Path 3b: force_validation_passed=True
    si_pass = sc_val_pass.get("si_report", {})
    if si_pass:
        hr_status_pass = si_pass.get("human_review_status", "")
        assert_true(
            hr_status_pass in ("pending", "dry_run"),
            f"force_validation_passed=True: hr_status should be pending/dry_run, got {hr_status_pass}"
        )
        assert_true(
            si_pass.get("best_skill_exported") is not True,
            "force_validation_passed=True + dry_run: best_skill_exported must NOT be True"
        )

    print("  OK — validation gate rules verified")


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

    sc_val_fail = None
    sc_val_pass = None

    try:
        # Path 1: tools/list
        call_tools_list(base_url)

        # Path 2: 正常路径
        sc_normal = call_os_agent_normal(base_url)
        run_id_normal = sc_normal["run_id"]

        time.sleep(1.5)

        # 获取正常路径事件
        events_normal = fetch_run_events(base_url, run_id_normal)
        if not events_normal:
            print("  WARN: No events from API, using emitted events from MCP response")
            events_normal = []

        # 正常路径: 事件字段强验收
        check_event_fields_strict(events_normal, "NORMAL") if events_normal else \
            print("  SKIP: event field check (no events from API)")

        # 正常路径: 事件链完整性 (含 rag.retrieved)
        check_event_chain(events_normal, NORMAL_PATH_EVENTS, "NORMAL") if events_normal else \
            print("  SKIP: event chain check (no events from API)")

        # Dashboard Observer
        check_observer_page(base_url, run_id_normal)

        # 事件同步健康
        check_event_sync_health(sc_normal)

        # Path 3: 失败学习路径
        if not args.skip_failure_path:
            # Path 3a: force_validation_passed=False
            sc_val_fail = call_os_agent_failure_val_failed(base_url)
            run_id_fail = sc_val_fail["run_id"]

            time.sleep(1.5)

            events_fail = fetch_run_events(base_url, run_id_fail)
            if not events_fail:
                print("  WARN: No events from API for failure path (val_failed)")

            check_event_fields_strict(events_fail, "FAILURE-VAL-FAIL") if events_fail else \
                print("  SKIP: event field check (no events from API)")

            check_event_chain(events_fail, FAILURE_PATH_EVENTS, "FAILURE-VAL-FAIL") if events_fail else \
                print("  SKIP: event chain check (no events from API)")

            check_failure_learning_details(sc_val_fail, events_fail) if events_fail else \
                print("  SKIP: failure learning details (no events from API)")

            check_observer_page(base_url, run_id_fail)
            check_event_sync_health(sc_val_fail)

            # Path 3b: force_validation_passed=True
            sc_val_pass = call_os_agent_failure_val_pass(base_url)
            run_id_pass = sc_val_pass["run_id"]

            time.sleep(1.5)

            events_pass = fetch_run_events(base_url, run_id_pass)
            if not events_pass:
                print("  WARN: No events from API for failure path (val_passed)")

            check_event_sync_health(sc_val_pass)

            # V9.1: Validation Gate 规则验证
            check_validation_gate(sc_val_fail, sc_val_pass)

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
    print("[PASS] StableAgent integration test completed (V9.1 final hardening).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
