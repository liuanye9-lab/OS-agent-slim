"""api — V11.2 API 路由。

V11.2: Feedback 端点接入真实 FeedbackLearningService 闭环。
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, Request

from stable_agent.capsule.memory_lifecycle import MemoryLifecycleManager

logger = logging.getLogger(__name__)

router = APIRouter()

# ===================================================================
# Health
# ===================================================================

@router.get("/api/health")
async def health():
    """服务健康检查。"""
    return {"ok": True, "service": "StableAgent OS", "version": "v11.2"}

# ===================================================================
# Usage
# ===================================================================

@router.get("/api/usage")
async def usage(workspace_id: str | None = None):
    """查询用量摘要。V11.2: 读取 BudgetLedger 真实数据。"""
    try:
        from stable_agent.token.budget_ledger import BudgetLedger
        from stable_agent.capsule import ensure_capsule
        capsule_path = ensure_capsule()
        db_path = str(capsule_path / "token_ledger" / "usage.sqlite")
        ledger = BudgetLedger(db_path=db_path)
        summary = ledger.summarize_period(days=30)
        return {"ok": True, "workspace_id": workspace_id, **summary}
    except Exception as exc:
        logger.warning("usage endpoint failed: %s", exc)
        return {"ok": False, "workspace_id": workspace_id, "errors": [str(exc)]}

# Dependencies injected by register_api_routes
_dash_sync = None
_gateway_run_store = None
_feedback_service = None

# V11.1 state for bad cases and learning outcomes
_bad_cases: dict[str, dict] = {}
_learning_outcomes: dict[str, dict] = {}


def register_api_routes(
    app,
    dash_sync=None,
    gateway_run_store=None,
    feedback_service=None,
):
    """注册 API 路由。

    Args:
        app: FastAPI 实例。
        dash_sync: Dashboard 同步引擎 (可选)。
        gateway_run_store: GatewayRunStore 实例 (可选, V11.2 新增)。
        feedback_service: FeedbackLearningService 实例 (可选, V11.2 新增)。
    """
    global _dash_sync, _gateway_run_store, _feedback_service
    _dash_sync = dash_sync
    _gateway_run_store = gateway_run_store
    _feedback_service = feedback_service
    app.include_router(router)


# ... existing endpoints (tool-stats, graph, token-summary, capsule-status) unchanged ...

@router.get("/api/tool/stats")
async def tool_stats():
    """Tool 执行统计。"""
    return {
        "total_executions": 1289,
        "success_rate": 0.92,
        "tools": {},
    }


@router.get("/api/graph")
async def graph():
    """因果图。"""
    return {"nodes": [], "edges": []}


@router.get("/api/token/summary")
async def token_summary():
    """Token 总消耗 — 读取 BudgetLedger 真实数据。"""
    try:
        from stable_agent.token.budget_ledger import BudgetLedger
        from stable_agent.capsule import ensure_capsule
        capsule_path = ensure_capsule()
        db_path = str(capsule_path / "token_ledger" / "usage.sqlite")
        ledger = BudgetLedger(db_path=db_path)
        days = 7
        summary = ledger.summarize_period(days=days)
        return {"ok": True, **summary}
    except Exception as exc:
        logger.warning("token_summary failed: %s", exc)
        return {"ok": False, "errors": [{"stage": "token_summary", "error": str(exc)}]}


@router.get("/api/capsule/status")
async def capsule_status():
    """Capsule 状态 — 读取胶囊目录真实数据。"""
    try:
        from stable_agent.capsule import ensure_capsule
        from pathlib import Path
        import json

        capsule_path = ensure_capsule()
        manifest_path = capsule_path / "manifest.json"
        manifest = {}
        if manifest_path.exists():
            try:
                with open(manifest_path, encoding="utf-8") as f:
                    manifest = json.load(f)
            except Exception as exc:
                logger.debug("Failed to load capsule manifest: %s", exc)

        # 统计各项数据
        stats = {
            "memory_count": 0,
            "skill_count": 0,
            "bad_case_count": 0,
            "eval_case_count": 0,
            "expression_rules": 0,
        }

        # 统计 expression rules
        expr_path = capsule_path / "profile" / "expressions.json"
        if expr_path.exists():
            try:
                with open(expr_path, encoding="utf-8") as f:
                    expr_data = json.load(f)
                    if isinstance(expr_data, list):
                        stats["expression_rules"] = len(expr_data)
            except Exception as exc:
                logger.debug("Failed to load capsule manifest: %s", exc)

        # 统计 bad cases
        bc_path = capsule_path / "bad_cases.jsonl"
        if bc_path.exists():
            try:
                with open(bc_path, encoding="utf-8") as f:
                    stats["bad_case_count"] = sum(1 for _ in f)
            except Exception as exc:
                logger.debug("Failed to load capsule manifest: %s", exc)

        # 统计 eval cases
        eval_path = capsule_path / "evals" / "personal_eval_cases.jsonl"
        if eval_path.exists():
            try:
                with open(eval_path, encoding="utf-8") as f:
                    stats["eval_case_count"] = sum(1 for _ in f)
            except Exception as exc:
                logger.debug("Failed to load capsule manifest: %s", exc)

        return {
            "ok": True,
            "exists": True,
            "path": str(capsule_path),
            "schema_version": manifest.get("version", "v11"),
            "stats": stats,
        }
    except Exception as exc:
        logger.warning("capsule_status failed: %s", exc)
        return {"ok": False, "errors": [{"stage": "capsule_status", "error": str(exc)}]}


@router.get("/api/memory/health")
async def memory_health():
    """记忆健康状态 — 读取 MemoryLifecycleManager 真实数据。"""
    try:
        from stable_agent.capsule import ensure_capsule
        from stable_agent.capsule.memory_lifecycle import MemoryLifecycleManager
        capsule_path = ensure_capsule()
        manager = MemoryLifecycleManager(capsule_path=capsule_path)
        stats = manager.generate_memory_health_report()
        return {"ok": True, "data": stats}
    except Exception as exc:
        logger.warning("memory_health failed: %s", exc)
        return {"ok": False, "data": {}, "errors": [{"stage": "memory_health", "error": str(exc)}]}


# ---- V11.1: Feedback endpoints ----

def _append_run_event(event_type: str, payload: dict | None = None):
    """向 gateway_run_store 追加事件（如果可用）。

    事件格式：所有 payload 字段展开到顶层，保证 Dashboard 和 /learning API 都能读到。
    """
    if _gateway_run_store is None:
        return
    try:
        import time
        run_id = (payload or {}).get("run_id", "feedback")
        event_data = {
            "event_type": event_type,
            "run_id": run_id,
            "timestamp": time.time(),
        }
        # 展开 payload 字段到顶层
        if payload:
            for k, v in payload.items():
                if k != "run_id":
                    event_data[k] = v
            event_data["payload"] = payload
        _gateway_run_store.append_event(run_id, event_data)
    except Exception as exc:
        logger.warning("Failed to append run event %s: %s", event_type, exc)


@router.post("/api/feedback/remember")
async def feedback_remember(request: Request):
    """记住这个：创建 MemoryUpdateCandidate。"""
    try:
        body = await request.json()
    except Exception as exc:
        logger.warning("feedback_remember: failed to parse request body: %s", exc)
        body = {}

    run_id = body.get("run_id", str(uuid.uuid4())[:8])
    user_note = body.get("note", body.get("user_note", ""))
    context = body.get("context", {})

    if _feedback_service is not None:
        result = _feedback_service.handle_remember(
            run_id=run_id, user_note=user_note, context=context
        )
        _append_run_event("feedback.received", {"action": "remember", "run_id": run_id})
        if result.get("generated", {}).get("memory_update_candidate"):
            _append_run_event("memory.update.candidate", {"run_id": run_id})
        return result

    # Fallback: 无 service 时降级
    logger.warning("feedback_remember: no feedback_service, returning degraded response")
    return {
        "ok": True,
        "action": "remember",
        "run_id": run_id,
        "generated": {"memory_update_candidate": False},
        "ids": {"memory_candidate_id": None},
        "summary_zh": "反馈已接收，但 FeedbackLearningService 未注入，未创建真实产物。",
        "errors": [{"stage": "service", "error": "FeedbackLearningService not injected"}],
    }


@router.post("/api/feedback/dont-do-this-again")
async def feedback_dont_do_this_again(request: Request):
    """下次别这样：真实闭环 BadCase → EvalCase → SkillPatch → Validation → HumanReview。"""
    try:
        body = await request.json()
    except Exception as exc:
        logger.warning("feedback_dont_do_this_again: failed to parse body: %s", exc)
        body = {}

    run_id = body.get("run_id", str(uuid.uuid4())[:8])
    user_note = body.get("note", body.get("user_note", ""))
    context = body.get("context", {})

    if _feedback_service is not None:
        result = _feedback_service.handle_dont_do_this_again(
            run_id=run_id, user_note=user_note, context=context
        )
        # 广播 feedback 事件到 Dashboard
        _append_run_event("feedback.received", {"action": "dont_do_this_again", "run_id": run_id})
        gen = result.get("generated", {})
        if gen.get("bad_case"):
            _append_run_event("bad_case.recorded", {"run_id": run_id, "bad_case_id": result.get("ids", {}).get("bad_case_id")})
        if gen.get("eval_case"):
            _append_run_event("eval_case.generated", {"run_id": run_id, "eval_case_id": result.get("ids", {}).get("eval_case_id")})
        if gen.get("skill_patch_candidate"):
            _append_run_event("skill.patch.proposed", {"run_id": run_id, "patch_id": result.get("ids", {}).get("patch_id")})
        if gen.get("validation_report"):
            _append_run_event("validation.checked", {"run_id": run_id, "passed": result.get("validation", {}).get("passed")})
        if gen.get("human_review_required"):
            _append_run_event("human_review.required", {"run_id": run_id, "review_id": result.get("ids", {}).get("review_id")})
        return result

    # Fallback: 无 service 时返回 degraded（不虚假标记）
    logger.warning("feedback_dont_do_this_again: no feedback_service, returning degraded response")
    return {
        "ok": True,
        "action": "dont_do_this_again",
        "run_id": run_id,
        "generated": {
            "bad_case": False,
            "eval_case": False,
            "skill_patch_candidate": False,
            "validation_report": False,
            "human_review_required": False,
        },
        "ids": {
            "bad_case_id": None,
            "eval_case_id": None,
            "patch_id": None,
            "validation_report_id": None,
            "review_id": None,
        },
        "validation": {"passed": False, "reason_zh": "FeedbackLearningService 未注入，无法执行验证。"},
        "summary_zh": "反馈已接收，但 FeedbackLearningService 未注入，未创建真实产物。",
        "errors": [{"stage": "service", "error": "FeedbackLearningService not injected"}],
    }


@router.post("/api/feedback/correct-and-remember")
async def feedback_correct_and_remember(request: Request):
    """纠正并记住：写入 ExpressionProfileManager candidate 规则。"""
    try:
        body = await request.json()
    except Exception as exc:
        logger.warning("feedback_correct_and_remember: failed to parse body: %s", exc)
        body = {}

    run_id = body.get("run_id", str(uuid.uuid4())[:8])
    user_note = body.get("note", body.get("user_note", ""))
    context = body.get("context", {})

    if _feedback_service is not None:
        result = _feedback_service.handle_correct_and_remember(
            run_id=run_id, user_note=user_note, context=context
        )
        _append_run_event("feedback.received", {"action": "correct_and_remember", "run_id": run_id})
        if result.get("generated", {}).get("expression_rule_candidate"):
            _append_run_event("expression.rule.candidate", {
                "run_id": run_id,
                "rule_id": result.get("ids", {}).get("expression_rule_id"),
            })
        return result

    # Fallback
    logger.warning("feedback_correct_and_remember: no feedback_service, returning degraded response")
    return {
        "ok": True,
        "action": "correct_and_remember",
        "run_id": run_id,
        "generated": {"expression_profile": False, "expression_rule_candidate": False},
        "ids": {"expression_rule_id": None},
        "summary_zh": "反馈已接收，但 FeedbackLearningService 未注入，未创建真实产物。",
        "errors": [{"stage": "service", "error": "FeedbackLearningService not injected"}],
    }
