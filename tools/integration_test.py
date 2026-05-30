#!/usr/bin/env python3
"""StableAgent Cloud Integration Test — V10 100% Closed-Loop Verification.

测试三条核心路径:
1. MCP tools/list: 验证工具注册完整
2. 正常路径: 完整基础事件链（从 /api/runs/{run_id}/events 读取）
3. 失败学习路径: self-improvement 事件链（从 /api/runs/{run_id}/events 读取）

V10 强化:
- 禁止 fallback 到 emitted_events — 必须从 API events 验证
- event_api_ok / dashboard_replay_ok 强验证
- check_dashboard_replay_api — 事件 API 非空 + event_count > 0
- event_sync_ok 依赖 event_api_ok
- api_missing_required_events 必须为空
- emitted_events 仅用于 debug 打印
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


# ======================================================================
# Path 1: MCP tools/list
# ======================================================================

def call_tools_list(base_url: str) -> list[str]:
    """MCP tools/list — 验证工具注册完整。"""
    print("[1/12] MCP tools/list")
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

    tool_names: list[str] = []
    if "result" in data and isinstance(data["result"], dict):
        tools = data["result"].get("tools", [])
        tool_names = [t.get("name", "") for t in tools if isinstance(t, dict)]

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
    "rag.retrieved",
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
    "next_step_zh",
    "avatar_state",
    "timestamp",
]


def call_os_agent_normal(base_url: str) -> dict[str, Any]:
    """正常路径: 测试完整基础事件链。"""
    print("[2/12] Calling os_agent (NORMAL path)")
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
    print("[3/12] Calling os_agent (FAILURE → validation_failed path)")
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
                "force_validation_passed": False,
                "dry_run_learning": True,
            },
        },
    }

    status, data = post_json(f"{base_url}/mcp", payload, timeout=60)
    assert_true(200 <= status < 500, f"os_agent failure path returned HTTP {status}: {data}")

    sc = extract_structured_content(data)

    run_id = sc.get("run_id")
    assert_true(bool(run_id), f"Missing run_id: {json.dumps(sc, ensure_ascii=False)[:300]}")

    eval_passed = sc.get("eval_passed", True)
    eval_score = sc.get("eval_score", 1.0)
    assert_true(not eval_passed, f"force_eval_failed should make eval_passed=False, got {eval_passed}")
    assert_true(eval_score <= 0.4, f"force_eval_failed should make score <= 0.4, got {eval_score}")
    assert_true(sc.get("dry_run_learning") is True, "dry_run_learning should be True")
    assert_true(sc.get("force_validation_passed") is False, "force_validation_passed should be False")

    si_report = sc.get("si_report")
    if si_report:
        hr_status = si_report.get("human_review_status", "")
        assert_true(
            hr_status in ("validation_failed", "dry_run", "none"),
            f"force_validation_passed=False: human_review_status should be validation_failed/dry_run/none, got {hr_status}"
        )
        assert_true(
            si_report.get("best_skill_exported") is not True,
            "best_skill_exported should NOT be True when validation_failed"
        )

    print(f"  OK run_id={run_id}, val_failed={si_report.get('validation_passed') if si_report else 'N/A'}")
    return sc


# ======================================================================
# Path 3b: 失败学习路径 — force_validation_passed=True
# ======================================================================

def call_os_agent_failure_val_pass(base_url: str) -> dict[str, Any]:
    """失败学习路径 (validation_passed + human_review)。"""
    print("[4/12] Calling os_agent (FAILURE → validation_passed + human_review path)")
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
                "force_validation_passed": True,
                "dry_run_learning": True,
            },
        },
    }

    status, data = post_json(f"{base_url}/mcp", payload, timeout=60)
    assert_true(200 <= status < 500, f"os_agent failure val-pass path returned HTTP {status}: {data}")

    sc = extract_structured_content(data)

    run_id = sc.get("run_id")
    assert_true(bool(run_id), f"Missing run_id: {json.dumps(sc, ensure_ascii=False)[:300]}")
    assert_true(sc.get("force_validation_passed") is True, "force_validation_passed should be True")

    si_report = sc.get("si_report")
    if si_report:
        hr_status = si_report.get("human_review_status", "")
        assert_true(
            hr_status in ("pending", "dry_run"),
            f"force_validation_passed=True: human_review_status should be pending/dry_run, got {hr_status}"
        )
        assert_true(
            si_report.get("best_skill_exported") is not True,
            "best_skill_exported must be False (dry_run_learning=True)"
        )

    print(f"  OK run_id={run_id}, hr_status={si_report.get('human_review_status') if si_report else 'N/A'}")
    return sc


# ======================================================================
# Run Events API (V10: 结构化返回)
# ======================================================================

def fetch_run_events(base_url: str, run_id: str) -> list[dict[str, Any]]:
    """从 /api/runs/{run_id}/events 获取事件列表。

    V10: 不再 fallback 到 emitted_events。
    如果 API 返回空，调用方必须 fail。
    """
    url = f"{base_url}/api/runs/{run_id}/events"
    status, data = get_json(url)

    if 200 <= status < 300:
        if isinstance(data, dict) and isinstance(data.get("events"), list):
            return data["events"]
        elif isinstance(data, list):
            # 兼容旧版直接返回列表
            return data
        else:
            return []

    return []


# ======================================================================
# Phase 5: 事件字段强验收
# ======================================================================

def check_event_fields_strict(events: list[dict[str, Any]], path_name: str) -> None:
    """严格事件字段验收 — 缺字段即 FAIL。"""
    print(f"[5/12] Checking event fields ({path_name})")

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
    print(f"[6/12] Checking event chain ({path_name})")

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
    print("[7/12] Checking failure learning details")

    event_types = [evt.get("event_type", "") for evt in events]

    assert_true("regression.generated" in event_types, "Must have regression.generated event")
    assert_true("skill.patch.proposed" in event_types, "Must have skill.patch.proposed event")
    assert_true("validation.checked" in event_types, "Must have validation.checked event")

    si_report = sc.get("si_report")
    if si_report:
        assert_true(si_report.get("learning_triggered") is True, "si_report.learning_triggered must be True")
        assert_true(si_report.get("validation_passed") is not None, "si_report.validation_passed must not be None")
        assert_true("best_skill_exported" in si_report, "si_report must have best_skill_exported field")
        assert_true("human_review_required" in si_report, "si_report must have human_review_required field")

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
    print("[8/12] Checking Dashboard Observer page")

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
# Phase 9: Dashboard Replay API (V10 新增)
# ======================================================================

def check_dashboard_replay_api(base_url: str, run_id: str, path_name: str) -> None:
    """V10: 验证 /api/runs/{run_id}/events 返回非空事件。"""
    print(f"[9/12] Checking Dashboard Replay API ({path_name})")

    url = f"{base_url}/api/runs/{run_id}/events"
    status, data = get_json(url)
    assert_true(status == 200, f"{path_name}: events API HTTP {status}: {data}")

    if isinstance(data, dict):
        events = data.get("events", [])
        event_count = data.get("event_count", len(events))
    elif isinstance(data, list):
        events = data
        event_count = len(events)
    else:
        events = []
        event_count = 0

    assert_true(event_count > 0, f"{path_name}: Dashboard replay API returned no events (event_count={event_count})")
    assert_true(len(events) > 0, f"{path_name}: Dashboard replay API events list empty")

    print(f"  OK — event_count={event_count}, events_len={len(events)}")


# ======================================================================
# Phase 10: 事件同步健康检查
# ======================================================================

def check_event_sync_health(sc: dict[str, Any]) -> None:
    """V10: 验证 event_sync_ok + event_api_ok + dashboard_replay_ok + missing_required_events。"""
    print("[10/12] Checking event sync health")

    assert_true("event_sync_ok" in sc, "Missing event_sync_ok in structuredContent")
    assert_true("emitted_event_count" in sc, "Missing emitted_event_count in structuredContent")
    assert_true("sync_errors" in sc, "Missing sync_errors in structuredContent")

    event_sync_ok = sc.get("event_sync_ok")
    emitted_count = sc.get("emitted_event_count", 0)
    sync_errors = sc.get("sync_errors", [])

    # V10: event_api_ok 必须存在
    assert_true("event_api_ok" in sc, "Missing event_api_ok in structuredContent (V10)")
    assert_true("api_event_count" in sc, "Missing api_event_count in structuredContent (V10)")
    assert_true("dashboard_replay_ok" in sc, "Missing dashboard_replay_ok in structuredContent (V10)")

    event_api_ok = sc.get("event_api_ok")
    api_event_count = sc.get("api_event_count", 0)
    dashboard_replay_ok = sc.get("dashboard_replay_ok")

    # missing_required_events 必须存在且为空
    missing = sc.get("missing_required_events", None)
    assert_true(missing is not None, "Missing missing_required_events in result")

    # api_missing_required_events 必须存在且为空
    api_missing = sc.get("api_missing_required_events", None)
    assert_true(api_missing is not None, "Missing api_missing_required_events in result (V10)")

    # 强验证
    assert_true(event_sync_ok is True, f"event_sync_ok should be True, errors={sync_errors}, missing={missing}")
    assert_true(emitted_count > 0, f"Should have emitted events, got {emitted_count}")
    assert_true(len(missing) == 0, f"missing_required_events must be empty, got: {missing}")

    # V10: event_api_ok 强验证
    assert_true(event_api_ok is True, f"event_api_ok must be True, api_event_count={api_event_count}, api_missing={api_missing}")
    assert_true(api_event_count > 0, f"api_event_count must be > 0, got {api_event_count}")
    assert_true(len(api_missing) == 0, f"api_missing_required_events must be empty, got: {api_missing}")

    # V10: dashboard_replay_ok 强验证
    assert_true(dashboard_replay_ok is True, f"dashboard_replay_ok must be True")

    print(f"  OK — emitted={emitted_count}, api={api_event_count}, sync_ok={event_sync_ok}, api_ok={event_api_ok}, replay_ok={dashboard_replay_ok}")


# ======================================================================
# Phase 11: Validation Gate 验证
# ======================================================================

def check_validation_gate(sc_val_fail: dict[str, Any], sc_val_pass: dict[str, Any]) -> None:
    """V10: 验证 validation gate 规则 + event_api_ok。"""
    print("[11/12] Checking validation gate rules + event chain")

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

    missing_fail = sc_val_fail.get("missing_required_events", [])
    assert_true(
        len(missing_fail) == 0,
        f"FAILURE-VAL-FAIL path has missing required events: {missing_fail}"
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

    missing_pass = sc_val_pass.get("missing_required_events", [])
    assert_true(
        len(missing_pass) == 0,
        f"FAILURE-VAL-PASS path has missing required events: {missing_pass}"
    )

    # event_sync_ok / event_api_ok 强验证
    assert_true(
        sc_val_fail.get("event_sync_ok") is True,
        f"FAILURE-VAL-FAIL: event_sync_ok must be True, missing={sc_val_fail.get('missing_required_events', [])}"
    )
    assert_true(
        sc_val_pass.get("event_sync_ok") is True,
        f"FAILURE-VAL-PASS: event_sync_ok must be True, missing={sc_val_pass.get('missing_required_events', [])}"
    )
    assert_true(
        sc_val_fail.get("event_api_ok") is True,
        f"FAILURE-VAL-FAIL: event_api_ok must be True (V10)"
    )
    assert_true(
        sc_val_pass.get("event_api_ok") is True,
        f"FAILURE-VAL-PASS: event_api_ok must be True (V10)"
    )

    print("  OK — validation gate rules + event chain verified")


# ======================================================================
# Decision Trace Quality
# ======================================================================

def check_trace_quality(events: list[dict[str, Any]]) -> None:
    """检查无隐藏推理字段，有可读解释。"""
    print("[12/12] Checking trace quality")

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
    print("  OK — no hidden reasoning, has readable explanations")


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
        # Path 1: tools/list
        call_tools_list(base_url)

        # Path 2: 正常路径
        sc_normal = call_os_agent_normal(base_url)
        run_id_normal = sc_normal["run_id"]

        time.sleep(1.5)

        # V10: 必须从 API events 获取 — 不允许 fallback 到 emitted_events
        events_normal = fetch_run_events(base_url, run_id_normal)
        assert_true(
            bool(events_normal),
            f"NORMAL path: /api/runs/{run_id_normal}/events returned no events. "
            f"RunStore/API/Dashboard event chain is broken. "
            f"Debug: emitted_event_count={sc_normal.get('emitted_event_count', 0)}, "
            f"event_api_ok={sc_normal.get('event_api_ok')}, "
            f"api_event_count={sc_normal.get('api_event_count', 0)}"
        )

        check_event_fields_strict(events_normal, "NORMAL")
        check_event_chain(events_normal, NORMAL_PATH_EVENTS, "NORMAL")
        check_dashboard_replay_api(base_url, run_id_normal, "NORMAL")
        check_observer_page(base_url, run_id_normal)
        check_event_sync_health(sc_normal)

        # Path 3: 失败学习路径
        if not args.skip_failure_path:
            # Path 3a: force_validation_passed=False
            sc_val_fail = call_os_agent_failure_val_failed(base_url)
            run_id_fail = sc_val_fail["run_id"]

            time.sleep(1.5)

            events_fail = fetch_run_events(base_url, run_id_fail)
            assert_true(
                bool(events_fail),
                f"FAILURE-VAL-FAIL path: /api/runs/{run_id_fail}/events returned no events. "
                f"RunStore/API/Dashboard event chain is broken. "
                f"Debug: emitted_event_count={sc_val_fail.get('emitted_event_count', 0)}, "
                f"event_api_ok={sc_val_fail.get('event_api_ok')}"
            )

            check_event_fields_strict(events_fail, "FAILURE-VAL-FAIL")
            check_event_chain(events_fail, FAILURE_PATH_EVENTS, "FAILURE-VAL-FAIL")
            check_failure_learning_details(sc_val_fail, events_fail)
            check_dashboard_replay_api(base_url, run_id_fail, "FAILURE-VAL-FAIL")
            check_observer_page(base_url, run_id_fail)
            check_event_sync_health(sc_val_fail)

            # Path 3b: force_validation_passed=True
            sc_val_pass = call_os_agent_failure_val_pass(base_url)
            run_id_pass = sc_val_pass["run_id"]

            time.sleep(1.5)

            events_pass = fetch_run_events(base_url, run_id_pass)
            assert_true(
                bool(events_pass),
                f"FAILURE-VAL-PASS path: /api/runs/{run_id_pass}/events returned no events. "
                f"RunStore/API/Dashboard event chain is broken. "
                f"Debug: emitted_event_count={sc_val_pass.get('emitted_event_count', 0)}, "
                f"event_api_ok={sc_val_pass.get('event_api_ok')}"
            )

            check_event_fields_strict(events_pass, "FAILURE-VAL-PASS")
            check_event_chain(events_pass, FAILURE_PATH_EVENTS, "FAILURE-VAL-PASS")
            check_dashboard_replay_api(base_url, run_id_pass, "FAILURE-VAL-PASS")
            check_event_sync_health(sc_val_pass)

            check_validation_gate(sc_val_fail, sc_val_pass)

        # Trace quality
        check_trace_quality(events_normal)

    except AssertionError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"[ERROR] Unexpected error: {exc}", file=sys.stderr)
        return 1

    print("")
    print("[PASS] StableAgent integration test completed (V10 100% closed-loop).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
