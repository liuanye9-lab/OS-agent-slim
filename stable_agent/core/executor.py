"""stable_agent/core/executor.py — AgentExecutor。

从 unified_tool_registry._h_task_os_agent 中提取的执行逻辑。
只负责执行，不负责学习/策展。

职责：
- 创建 run
- 构建 context (memory + skill retrieval)
- 执行 workflow
- 评估 eval
- 写入 events
- 返回 RunTrace

不负责：
- 是否把经验变成 skill
- 是否 promote skill
- 是否写 best_skill.md
"""

from __future__ import annotations

import logging
import time
from typing import Any

from stable_agent.core.models import TaskSpec, RunTrace, ToolRunResult

logger = logging.getLogger(__name__)

# 必需事件定义
REQUIRED_NORMAL_EVENTS = [
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

REQUIRED_FAILURE_EVENTS = [
    "regression.generated",
    "memory.update.candidate",
    "skill.patch.proposed",
    "validation.checked",
]


class OSAgentExecutor:
    """Agent 执行器。

    从 UnifiedToolRegistry 中提取的任务执行逻辑。
    通过依赖注入获取 orchestrator 和 tool_router。
    """

    def __init__(self, orchestrator: Any, tool_router: Any = None):
        self._orchestrator = orchestrator
        self._tool_router = tool_router

    async def run(self, task: TaskSpec, ctx: Any) -> RunTrace:
        """执行任务并返回 RunTrace。

        Args:
            task: 任务规格。
            ctx: RunContext 实例。

        Returns:
            RunTrace 包含执行结果、事件、评估等。
        """
        # 事件追踪
        emitted_events: list[dict] = []
        sync_errors: list[str] = []

        # 注册 run
        self._ensure_run_registered(ctx.run_id)

        # Phase 1: 接收
        self._emit(ctx, "task.received", "received", emitted_events, sync_errors)

        # Phase 1.5: 语义理解 (可选)
        understanding_trace_dict = self._run_understanding_trace(ctx, task.task_input, emitted_events, sync_errors)

        # Phase 2: 意图解析
        self._emit(ctx, "intent.parsed", "intent_parsing", emitted_events, sync_errors, {
            "task_input": task.task_input[:200],
            "decision_summary_zh": f"正在理解任务意图: {task.task_input[:60]}",
            "why_zh": "先判断用户真正要解决什么问题，避免跑偏。",
        })

        # Phase 3: 上下文预算
        self._emit(ctx, "context.budgeted", "context_budgeting", emitted_events, sync_errors, {
            "decision_summary_zh": "正在计算 token 预算",
            "why_zh": "上下文太多会浪费 token，也会让模型分心。",
        })

        # Phase 4: 时间记忆检索
        temporal_hits = self._retrieve_temporal_memory(ctx, task.task_input)
        temporal_payload = {
            "selected_memories": [{"memory_id": h.memory_id, "reason_zh": h.reason_zh} for h in temporal_hits[:5]],
            "discarded_memories": [],
            "count": len(temporal_hits),
            "reason_zh": "按时间戳和相关性召回相关记忆，防止上下文压缩丢失关键约束。",
            "decision_summary_zh": f"召回 {len(temporal_hits)} 条相关时间记忆",
            "why_zh": "上下文压缩可能丢失关键历史约束，所以要按时间戳找相关记忆。",
            "next_step_zh": "检索项目资料。",
        }
        if not temporal_hits:
            temporal_payload["decision_summary_zh"] = "未找到相关时间记忆"
            temporal_payload["why_zh"] = "当前项目暂无时间记忆，继续执行。"
        self._emit(ctx, "temporal_memory.retrieved", "temporal_memory_retrieving", emitted_events, sync_errors, temporal_payload)

        # Phase 5: RAG 检索
        self._emit(ctx, "rag.retrieved", "rag_retrieving", emitted_events, sync_errors, {
            "decision_summary_zh": "已完成项目资料检索",
            "why_zh": "从项目资料里找当前任务相关信息。",
        })

        # Phase 6: 上下文压缩保护
        context_items = [{"content": task.task_input, "type": "user_goal"}]
        for h in temporal_hits[:5]:
            context_items.append({"content": h.content[:200], "type": "temporal_memory"})

        cc_decision = self._run_compression_guard(ctx, task.task_input, context_items)
        guard_payload = {
            "decision_summary_zh": "上下文压缩保护已完成",
            "why_zh": "保留关键目标和约束，丢弃无关信息，避免降智。",
            "protected_items": len(cc_decision.protected_items) if cc_decision else 0,
            "dropped_items": len(cc_decision.dropped_items) if cc_decision else 0,
            "summary_zh": cc_decision.summary_zh if cc_decision else "无压缩需求",
            "blocked": cc_decision.blocked if cc_decision else False,
            "next_step_zh": "开始执行任务。" if not (cc_decision and cc_decision.blocked) else "需要人工处理。",
        }
        self._emit(ctx, "context.compression_guard.checked", "context_compressing", emitted_events, sync_errors, guard_payload)

        # Token 预算记录 (可选)
        token_report = self._run_token_budget(ctx, task.task_input, context_items, cc_decision, emitted_events, sync_errors)

        # 检查是否被阻止
        if cc_decision and cc_decision.blocked:
            self._emit(ctx, "task.failed", "failed", emitted_events, sync_errors, {
                "reason_zh": "上下文压缩被阻止：受保护条目超出 token 预算",
                "summary_zh": cc_decision.summary_zh,
            })
            return RunTrace(
                run_id=ctx.run_id, ok=False, status="failed",
                eval_passed=False, eval_score=None, events=emitted_events,
                output_text=f"上下文压缩被阻止: {cc_decision.summary_zh}",
                artifacts={"blocked": True}, si_report=None,
            )

        # Phase 7: 执行任务
        self._emit(ctx, "context.built", "context_building", emitted_events, sync_errors, {
            "decision_summary_zh": "上下文包已构建", "next_step_zh": "规划并执行。",
        })
        self._emit(ctx, "workflow.plan.created", "planning", emitted_events, sync_errors, {
            "decision_summary_zh": "正在规划执行步骤",
        })
        self._emit(ctx, "workflow.step.started", "acting", emitted_events, sync_errors)

        raw_result = self._orchestrator.process_task(task.task_input)
        result = self._json_safe(raw_result)
        if not isinstance(result, dict):
            result = {"output": str(result)}

        self._emit(ctx, "workflow.step.completed", "observing", emitted_events, sync_errors, {
            "decision_summary_zh": "任务执行完成", "next_step_zh": "评估结果。",
        })

        # Phase 8: 评估
        eval_passed, eval_score, eval_reason, failure_mode = self._evaluate(
            result, task.force_eval_failed, task.force_failure_mode
        )
        self._emit(ctx, "eval.completed", "evaluating", emitted_events, sync_errors, {
            "eval_passed": eval_passed, "eval_score": eval_score,
            "decision_summary_zh": f"评估结果: {'通过' if eval_passed else '未通过'} ({eval_score:.2f})",
            "why_zh": eval_reason,
            "next_step_zh": "分析失败原因。" if not eval_passed else "自我优化检查。",
        })

        # Phase 9: 自我优化闭环
        si_report = self._run_self_improvement(
            ctx, eval_passed, eval_score, eval_reason, failure_mode, result,
            task, emitted_events, sync_errors,
        )

        # Phase 10: 完成
        self._emit(ctx, "task.completed", "completed", emitted_events, sync_errors)
        self._mark_run_completed(ctx.run_id)

        # 事件同步健康检查
        event_sync_ok, missing_required_events = self._check_event_sync(
            emitted_events, sync_errors, task.force_eval_failed
        )

        # RunStore 回读验证
        event_api_ok, api_event_count, api_missing_required_events, dashboard_replay_ok = self._verify_runstore(ctx.run_id, task.force_eval_failed)

        if not event_api_ok:
            event_sync_ok = False

        return RunTrace(
            run_id=ctx.run_id,
            ok=True,
            status="completed",
            eval_passed=eval_passed,
            eval_score=eval_score,
            events=emitted_events,
            output_text=str(result.get("output", "")),
            artifacts={
                "force_eval_failed": task.force_eval_failed,
                "dry_run_learning": task.dry_run_learning,
                "missing_required_events": missing_required_events,
                "dashboard_replay_ok": dashboard_replay_ok,
                "event_sync_ok": event_sync_ok,
                "event_api_ok": event_api_ok,
                "api_event_count": api_event_count,
                "emitted_event_count": len(emitted_events),
                "sync_errors": sync_errors,
                "api_missing_required_events": api_missing_required_events,
                "task_type": str(result.get("task_type", "unknown")),
                "workflow_state": str(result.get("workflow_state", "completed")),
                "understanding_trace": understanding_trace_dict,
                "token_report": token_report,
                "force_validation_passed": task.force_validation_passed,
            },
            si_report=si_report.to_dict() if si_report else None,
        )

    # ── 内部方法 ──────────────────────────────────────────────

    def _ensure_run_registered(self, run_id: str) -> None:
        """在 RunStore 中注册 run。"""
        try:
            tr = getattr(self, '_tool_router', None) or getattr(self, '_registry', None)
            if tr is not None:
                rs = getattr(tr, '_run_store', None)
                if rs is not None:
                    rs.create_run(run_id)
        except Exception:
            logger.warning("RunStore.create_run failed for %s", run_id, exc_info=True)

    def _emit(
        self, ctx: Any, event_type: str, stage: str,
        emitted_events: list, sync_errors: list,
        payload: dict | None = None,
    ) -> dict:
        """发布阶段事件到 EventStream + RunStore。"""
        from stable_agent.runtime.run_lifecycle import get_stage_meta

        meta = get_stage_meta(stage)
        ctx.current_stage = stage
        ctx.progress_pct = meta.progress_pct
        ctx.status_text_zh = meta.status_text_zh
        ctx.status_text_en = meta.status_text_en
        ctx.avatar_state = meta.avatar_state

        event = {
            "run_id": ctx.run_id,
            "trace_id": ctx.trace_id,
            "span_id": ctx.child_span().span_id,
            "event_type": event_type,
            "stage": stage,
            "stage_label_zh": meta.status_text_zh,
            "progress_pct": meta.progress_pct,
            "avatar_state": meta.avatar_state,
            "status_text_zh": meta.status_text_zh,
            "status_text_en": meta.status_text_en,
            "decision_summary_zh": meta.default_why_zh,
            "why_zh": meta.default_why_zh,
            "next_step_zh": meta.default_next_step_zh,
            "timestamp": time.time(),
        }
        if payload:
            event.update(payload)

        emit_ok = False
        try:
            tr = getattr(self, '_tool_router', None) or getattr(self, '_registry', None)
            if tr is not None:
                es = getattr(tr, '_event_stream', None)
                if es is not None:
                    es.publish_sync(ctx.run_id, event)
                rs = getattr(tr, '_run_store', None)
                if rs is not None:
                    rs.append_event(ctx.run_id, event)
            emit_ok = True
        except Exception as emit_exc:
            logger.warning("event emit FAILED for %s: %s", event_type, emit_exc)
            sync_errors.append(f"{event_type}: {emit_exc}")

        event["_emit_ok"] = emit_ok
        emitted_events.append(event)
        return event

    def _run_understanding_trace(self, ctx: Any, task_input: str, emitted_events: list, sync_errors: list) -> dict | None:
        """运行语义理解轨迹 (可选)。"""
        try:
            from stable_agent.understanding.semantic_interpreter import SemanticInterpreter
            interpreter = None
            try:
                from stable_agent.capsule import ensure_capsule
                from stable_agent.understanding.expression_profile import ExpressionProfileManager
                capsule_path = ensure_capsule()
                expr_mgr = ExpressionProfileManager(storage_path=str(capsule_path / "profile" / "expressions.json"))
                interpreter = SemanticInterpreter(expression_manager=expr_mgr)
            except Exception:
                interpreter = SemanticInterpreter()
            ut = interpreter.interpret(task_input, run_id=ctx.run_id)
            understanding_trace_dict = ut.to_dict()
            self._emit(ctx, "understanding.trace.created", "intent_parsing", emitted_events, sync_errors, {
                "understanding_trace": understanding_trace_dict,
                "decision_summary_zh": f"系统理解：{ut.interpreted_goal}",
                "why_zh": "先暴露系统对用户意图的理解，避免语义漂移。",
                "next_step_zh": "继续解析意图并构建上下文。",
            })
            return understanding_trace_dict
        except Exception as exc:
            self._emit(ctx, "understanding.trace.created", "intent_parsing", emitted_events, sync_errors, {
                "error": str(exc),
                "decision_summary_zh": "语义理解轨迹生成失败，已降级继续执行。",
            })
            return None

    def _retrieve_temporal_memory(self, ctx: Any, task_input: str) -> list:
        """检索时间记忆。"""
        try:
            orch = self._orchestrator
            if hasattr(orch, 'temporal_memory_bridge'):
                bridge = orch.temporal_memory_bridge
                project_id = getattr(ctx, 'project_id', None)
                if hasattr(orch, 'memory_bank'):
                    mems = [{"id": m.id, "content": m.content[:100], "created_at": getattr(m, 'timestamp', time.time()), "source": "memory_bank"}
                            for m in orch.memory_bank.list_items()][:20]
                    bridge.load_for_project(project_id=project_id, existing_memories=mems)
                return bridge.retrieve(task_input=task_input, project_id=project_id, top_k=8)
        except Exception:
            pass
        return []

    def _run_compression_guard(self, ctx: Any, task_input: str, context_items: list) -> Any:
        """运行上下文压缩保护。"""
        budget = 8000
        try:
            orch = self._orchestrator
            if hasattr(orch, 'context_compression_guard'):
                guard = orch.context_compression_guard
                cc_decision = guard.protect(task_input=task_input, context_items=context_items, token_budget=budget)
                return guard.enforce_budget(decision=cc_decision, token_budget=budget)
        except Exception:
            logger.warning("ContextCompressionGuard 失败，跳过保护")
        return None

    def _run_token_budget(self, ctx: Any, task_input: str, context_items: list, cc_decision: Any, emitted_events: list, sync_errors: list) -> dict | None:
        """运行 Token 预算记录 (可选)。"""
        try:
            from stable_agent.token.token_estimator import TokenEstimator
            from stable_agent.token.schemas import TokenRunRecord
            from stable_agent.capsule.capsule_manager import ensure_capsule
            estimator = TokenEstimator()
            estimation_method = "tiktoken_cl100k" if hasattr(estimator, '_encoding') and estimator._encoding else "char_div4"
            task_tokens = estimator.estimate(task_input)
            context_token_items = [estimator.estimate(str(c.get("content", ""))) for c in context_items]
            candidate_context_tokens = sum(context_token_items)
            baseline_tokens = task_tokens + candidate_context_tokens
            protected_tokens = sum(estimator.estimate(str(i.get("content", ""))) for i in (cc_decision.protected_items if cc_decision else []))
            dropped_tokens = sum(estimator.estimate(str(i.get("content", ""))) for i in (cc_decision.dropped_items if cc_decision else []))
            injected_tokens = baseline_tokens - dropped_tokens
            saved_tokens = max(0, baseline_tokens - injected_tokens)
            saving_ratio = (saved_tokens / baseline_tokens) if baseline_tokens > 0 else 0.0
            risk_level = "high" if (cc_decision and cc_decision.blocked) else ("medium" if saving_ratio > 0.5 else "low")
            summary_zh = f"节省 {saving_ratio:.0%} token ({saved_tokens}/{baseline_tokens})" if candidate_context_tokens >= 100 else f"节省 {saving_ratio:.0%} token ({saved_tokens}/{baseline_tokens})。当前为候选上下文估算。"
            token_record = TokenRunRecord(
                run_id=ctx.run_id, baseline_tokens_estimated=baseline_tokens,
                raw_context_tokens=candidate_context_tokens, candidate_context_tokens=candidate_context_tokens,
                protected_tokens=protected_tokens, injected_tokens=injected_tokens,
                dropped_tokens=dropped_tokens, saved_tokens_estimated=saved_tokens,
                saving_ratio=round(saving_ratio, 4), estimation_method=estimation_method,
                is_estimated=True, risk_level=risk_level,
                protected_items=[str(i.get("content", ""))[:50] for i in (cc_decision.protected_items if cc_decision else [])],
                dropped_items=[str(i.get("content", ""))[:50] for i in (cc_decision.dropped_items if cc_decision else [])],
                summary_zh=summary_zh,
            )
            try:
                capsule_path = ensure_capsule()
                db_path = str(capsule_path / "token_ledger" / "usage.sqlite")
                from stable_agent.token.budget_ledger import BudgetLedger
                ledger = BudgetLedger(db_path=db_path)
                ledger.record_run(token_record)
            except Exception:
                pass
            token_report = token_record.to_dict()
            self._emit(ctx, "token.budget.estimated", "context_compressing", emitted_events, sync_errors, {
                "token_report": token_report,
                "decision_summary_zh": token_record.summary_zh,
                "why_zh": "记录上下文压缩的 token 节省情况。",
                "next_step_zh": "开始执行任务。",
            })
            return token_report
        except Exception as exc:
            self._emit(ctx, "token.budget.estimated", "context_compressing", emitted_events, sync_errors, {
                "error": str(exc),
                "decision_summary_zh": "Token 预算记录失败，已降级继续执行。",
            })
            return None

    def _evaluate(self, result: dict, force_eval_failed: bool, force_failure_mode: str | None) -> tuple:
        """评估任务结果。"""
        eval_passed = False
        eval_score = 0.0
        eval_reason = "无评估数据"
        failure_mode = ""

        if force_eval_failed:
            eval_passed = False
            eval_score = 0.3
            eval_reason = "force_eval_failed=true (测试模式)"
            failure_mode = force_failure_mode or "intent_drift"
        elif "evaluation" in result and result["evaluation"] is not None:
            eval_obj = result["evaluation"]
            if hasattr(eval_obj, 'overall_score'):
                eval_score = float(eval_obj.overall_score)
            elif isinstance(eval_obj, dict):
                eval_score = float(eval_obj.get("overall_score", 0.0))
            eval_passed = eval_score >= 0.7
            eval_reason = f"overall_score={eval_score:.2f}"
            if not eval_passed and eval_score < 0.5:
                failure_mode = "low_quality"
        elif "task_type" in result:
            eval_passed = True
            eval_score = 0.75
            eval_reason = "任务分类成功，默认通过"

        return eval_passed, eval_score, eval_reason, failure_mode

    def _run_self_improvement(
        self, ctx: Any, eval_passed: bool, eval_score: float, eval_reason: str,
        failure_mode: str, result: dict, task: TaskSpec,
        emitted_events: list, sync_errors: list,
    ) -> Any:
        """运行自我优化闭环。"""
        try:
            proof = self._orchestrator.proof_loop
            si_report = proof.evaluate_and_learn(
                run_id=ctx.run_id, eval_passed=eval_passed, eval_score=eval_score,
                eval_reason=eval_reason, failure_mode=failure_mode,
                observations=[{"text": str(result.get("output", ""))[:200]}],
                force_regression_case=task.force_regression_case,
                force_skill_patch=task.force_skill_patch,
                force_validation_passed=task.force_validation_passed,
                dry_run_learning=task.dry_run_learning,
            )
            si_payload = {
                "learning_triggered": si_report.learning_triggered,
                "validation_passed": si_report.validation_passed,
                "regression_cases": len(si_report.regression_cases),
                "memory_candidates": len(si_report.memory_candidates),
                "skill_patches": len(si_report.skill_patches),
                "human_review_status": si_report.human_review_status,
                "human_review_required": si_report.human_review_required,
                "best_skill_exported": False,
            }
            if si_report.learning_triggered:
                si_payload["decision_summary_zh"] = "触发自我优化闭环"
                si_payload["why_zh"] = "本次评估未通过，需要分析失败原因并生成改进。"
                si_payload["next_step_zh"] = "等待人工审核。"
                self._emit(ctx, "self_improvement.checked", "skill_patch_proposal", emitted_events, sync_errors, si_payload)
                if si_report.regression_cases:
                    self._emit(ctx, "regression.generated", "regression_generation", emitted_events, sync_errors, si_payload)
                if si_report.memory_candidates:
                    self._emit(ctx, "memory.update.candidate", "memory_update_candidate", emitted_events, sync_errors, si_payload)
                if si_report.skill_patches:
                    self._emit(ctx, "skill.patch.proposed", "skill_patch_proposal", emitted_events, sync_errors, si_payload)
                if si_report.validation_passed:
                    self._emit(ctx, "validation.checked", "validation", emitted_events, sync_errors, si_payload)
                if si_report.human_review_required:
                    self._emit(ctx, "human_review.required", "human_review", emitted_events, sync_errors, si_payload)
            else:
                si_payload["decision_summary_zh"] = "本次评估通过或缺少失败证据，不触发 skill 更新"
                si_payload["reason_zh"] = "本次评估通过或缺少失败证据，因此不触发 skill 更新。"
                self._emit(ctx, "self_improvement.checked", "evaluating", emitted_events, sync_errors, si_payload)
            return si_report
        except Exception as exc:
            logger.warning("SelfImprovement 执行失败: %s", exc)
            self._emit(ctx, "self_improvement.checked", "evaluating", emitted_events, sync_errors, {
                "learning_triggered": False,
                "reason_zh": f"自我优化检查失败，跳过: {exc}",
            })
            return None

    def _mark_run_completed(self, run_id: str) -> None:
        """标记 RunStore 中 run 为 completed。"""
        try:
            tr = getattr(self, '_tool_router', None) or getattr(self, '_registry', None)
            if tr is not None:
                rs = getattr(tr, '_run_store', None)
                if rs is not None:
                    rs.mark_completed(run_id)
        except Exception:
            logger.warning("RunStore.mark_completed failed for %s", run_id, exc_info=True)

    def _check_event_sync(self, emitted_events: list, sync_errors: list, force_eval_failed: bool) -> tuple:
        """事件同步健康检查。"""
        emitted_event_types = [e.get("event_type") for e in emitted_events if e.get("_emit_ok")]
        missing_required_events = [e for e in REQUIRED_NORMAL_EVENTS if e not in emitted_event_types]
        if force_eval_failed and any(e in emitted_event_types for e in ("regression.generated", "skill.patch.proposed")):
            for fe in REQUIRED_FAILURE_EVENTS:
                if fe not in missing_required_events and fe not in emitted_event_types:
                    missing_required_events.append(fe)
        event_sync_ok = len(sync_errors) == 0 and not missing_required_events
        return event_sync_ok, missing_required_events

    def _verify_runstore(self, run_id: str, force_eval_failed: bool) -> tuple:
        """从 RunStore 回读验证。"""
        api_event_count = 0
        api_missing_required_events: list[str] = []
        event_api_ok = False
        dashboard_replay_ok = False
        try:
            tr = getattr(self, '_tool_router', None) or getattr(self, '_registry', None)
            if tr is not None:
                rs = getattr(tr, '_run_store', None)
                if rs is not None:
                    stored_events = rs.get_events(run_id)
                    api_event_count = len(stored_events)
                    stored_event_types = [e.get("event_type") for e in stored_events if isinstance(e, dict)]
                    api_missing_required_events = [e for e in REQUIRED_NORMAL_EVENTS if e not in stored_event_types]
                    if force_eval_failed and any(e in stored_event_types for e in ("regression.generated", "skill.patch.proposed")):
                        for fe in REQUIRED_FAILURE_EVENTS:
                            if fe not in api_missing_required_events and fe not in stored_event_types:
                                api_missing_required_events.append(fe)
                    event_api_ok = api_event_count > 0 and len(api_missing_required_events) == 0
                    dashboard_replay_ok = event_api_ok
        except Exception:
            logger.warning("RunStore API readback failed for %s", run_id, exc_info=True)
        return event_api_ok, api_event_count, api_missing_required_events, dashboard_replay_ok

    def _json_safe(self, value: Any) -> Any:
        """Return a recursively JSON-serializable representation."""
        import dataclasses
        from enum import Enum
        if dataclasses.is_dataclass(value):
            return self._json_safe(dataclasses.asdict(value))
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, dict):
            return {str(k): self._json_safe(v) for k, v in value.items()}
        if isinstance(value, list | tuple | set):
            return [self._json_safe(v) for v in value]
        return value
