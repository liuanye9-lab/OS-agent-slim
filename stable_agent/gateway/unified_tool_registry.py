"""UnifiedToolRegistry — V5 统一工具注册中心。

管理 14 个 namespaced 工具的定义和 handler 绑定。所有 handler
接收 (RunContext, dict) 参数并返回 StableAgentToolResult。

用法::

    registry = UnifiedToolRegistry(orchestrator)
    handler = registry.get_handler("stableagent.memory.retrieve")
    result = handler(ctx, {"task_input": "..."})
"""

from __future__ import annotations

import time
from typing import Any, Callable, TYPE_CHECKING

from stable_agent.gateway.run_context import RunContext
from stable_agent.gateway.tool_schemas import TOOLS
from stable_agent.models import StableAgentToolResult, TaskType, EvaluationResult

if TYPE_CHECKING:
    pass


class UnifiedToolRegistry:
    """V5 统一工具注册中心。管理 14 个 namespaced 工具的定义和 handler 绑定。

    每个工具对应一个 handler 方法，handler 接收 RunContext 和参数字典，
    返回 StableAgentToolResult。通过 orchestrator 引用访问后端服务。

    Attributes:
        _handlers: 工具名 → handler 可调用对象的映射。
        _orchestrator: StableAgentOrchestrator 引用（延迟绑定）。
    """

    def __init__(self, orchestrator: Any = None) -> None:
        """初始化注册中心并注册所有 14 个工具 handler。

        Args:
            orchestrator: StableAgentOrchestrator 实例，用于访问各后端模块。
                          None 时 handler 返回占位结果。
        """
        self._orchestrator: Any = orchestrator
        self._handlers: dict[str, Callable[[RunContext, dict[str, Any]], StableAgentToolResult]] = {}
        self._register_all()

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    def get_handler(self, name: str) -> Callable[[RunContext, dict[str, Any]], StableAgentToolResult] | None:
        """获取指定工具的 handler。

        Args:
            name: 工具完整名称，如 "stableagent.memory.retrieve"。

        Returns:
            Handler 可调用对象，未注册时返回 None。
        """
        return self._handlers.get(name)

    def list_tools(self) -> list[dict[str, Any]]:
        """返回所有 14 个注册工具的 MCP 格式列表。

        每个工具条目包含 name、title、description 和 input_schema。

        Returns:
            MCP 格式工具定义列表。
        """
        result: list[dict[str, Any]] = []
        for tool_name, tool_def in TOOLS.items():
            result.append({
                "name": tool_def["name"],
                "title": tool_def.get("title", ""),
                "description": tool_def.get("description", ""),
                "input_schema": tool_def.get("input_schema", {}),
            })
        return result

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _register(self, name: str, handler: Callable[[RunContext, dict[str, Any]], StableAgentToolResult]) -> None:
        """注册单个工具的 handler。

        Args:
            name: 工具完整名称。
            handler: 处理函数，签名为 (RunContext, dict) -> StableAgentToolResult。
        """
        self._handlers[name] = handler

    def _register_all(self) -> None:
        """注册所有 14 个工具及其 handler。"""
        self._register("stableagent.task.process", self._h_task_process)
        self._register("stableagent.context.build", self._h_context_build)
        self._register("stableagent.context.estimate_budget", self._h_estimate_budget)
        self._register("stableagent.memory.retrieve", self._h_memory_retrieve)
        self._register("stableagent.memory.write_candidate", self._h_memory_write)
        self._register("stableagent.rag.retrieve", self._h_rag_retrieve)
        self._register("stableagent.eval.evaluate", self._h_eval_evaluate)
        self._register("stableagent.badcase.record", self._h_badcase_record)
        self._register("stableagent.skillopt.status", self._h_skillopt_status)
        self._register("stableagent.skillopt.get_current_skill", self._h_skillopt_current)
        self._register("stableagent.skillopt.run_epoch", self._h_skillopt_epoch)
        self._register("stableagent.skillopt.export_best", self._h_skillopt_export)
        self._register("stableagent.trace.get_run", self._h_trace_get_run)
        self._register("stableagent.approval.respond", self._h_approval_respond)
        self._register("stableagent.task.os_agent", self._h_task_os_agent)  # V6.5: /os-agent

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _make_result(
        self,
        ctx: RunContext,
        tool_name: str,
        ok: bool = True,
        data: dict[str, Any] | None = None,
        plain_text: str = "",
        plain_text_zh: str = "",
        plain_text_en: str = "",
        dashboard_url: str = "",
        warnings: list[str] | None = None,
        next_actions: list[str] | None = None,
        is_error: bool = False,
    ) -> StableAgentToolResult:
        """创建标准 StableAgentToolResult。

        Args:
            ctx: 当前 RunContext。
            tool_name: 工具名。
            ok: 执行是否成功。
            data: 结构化返回数据。
            plain_text: 人类可读结果文本。
            plain_text_zh: 中文结果描述（未提供时回退到 plain_text）。
            plain_text_en: 英文结果描述（未提供时回退到 plain_text）。
            dashboard_url: Dashboard 链接（未提供时使用默认 /dashboard/{run_id}）。
            warnings: 警告信息列表。
            next_actions: 建议后续操作。
            is_error: 是否为错误返回。

        Returns:
            填充好的 StableAgentToolResult 实例。
        """
        return StableAgentToolResult(
            ok=ok,
            run_id=ctx.run_id,
            tool_call_id=ctx.tool_call_id,
            tool_name=tool_name,
            data=data or {},
            plain_text=plain_text,
            plain_text_zh=plain_text_zh or plain_text,
            plain_text_en=plain_text_en or plain_text,
            dashboard_url=dashboard_url or f"/dashboard/{ctx.run_id}",
            warnings=warnings or [],
            next_actions=next_actions or [],
            trace_url=f"/runs/{ctx.run_id}",
            is_error=is_error,
        )

    # ------------------------------------------------------------------
    # Handler 实现 —— 14 个工具
    # ------------------------------------------------------------------

    def _h_task_process(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.task.process — 端到端任务处理。

        委托给 orchestrator.process_task() 执行完整工作流。

        Args:
            ctx: RunContext。
            args: 包含 task_input 的参数字典。

        Returns:
            包含任务处理结果的 StableAgentToolResult。
        """
        tool_name = "stableagent.task.process"
        task_input: str = args.get("task_input", "")

        if self._orchestrator is None:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text="Orchestrator 未注入，无法处理任务",
            )

        try:
            result: dict[str, Any] = self._orchestrator.process_task(task_input)
            return self._make_result(
                ctx, tool_name,
                ok=True,
                data=result,
                plain_text=f"任务处理完成：{task_input[:80]}",
                next_actions=["查看结果详情", "评估输出质量"],
            )
        except Exception as exc:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text=f"任务处理失败：{exc}",
            )

    def _h_context_build(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.context.build — 构建上下文包。

        委托给 orchestrator.build_context_pack_api()。

        Args:
            ctx: RunContext。
            args: 包含 task_input 的参数字典。

        Returns:
            包含 ContextPack 信息的 StableAgentToolResult。
        """
        tool_name = "stableagent.context.build"
        task_input: str = args.get("task_input", "")

        if self._orchestrator is None:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text="Orchestrator 未注入，无法构建上下文包",
            )

        try:
            pack = self._orchestrator.build_context_pack_api(task_input)
            pack_data: dict[str, Any] = {
                "pack_id": pack.pack_id,
                "run_id": pack.run_id,
                "task_type": pack.task_type.value if isinstance(pack.task_type, TaskType) else str(pack.task_type),
                "item_count": len(pack.items),
                "total_tokens": pack.total_tokens,
                "budget_limit": pack.budget_limit,
                "critical_reminders": pack.critical_reminders,
            }
            return self._make_result(
                ctx, tool_name,
                ok=True,
                data=pack_data,
                plain_text=f"上下文包构建完成，包含 {len(pack.items)} 个条目，共 {pack.total_tokens} tokens",
                next_actions=["估算预算", "检索记忆"],
            )
        except Exception as exc:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text=f"上下文包构建失败：{exc}",
            )

    def _h_estimate_budget(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.context.estimate_budget — 估算 Token 预算。

        先通过决策引擎分类任务类型，再计算预算。

        Args:
            ctx: RunContext。
            args: 包含 task_input 的参数字典。

        Returns:
            包含预算信息的 StableAgentToolResult。
        """
        tool_name = "stableagent.context.estimate_budget"
        task_input: str = args.get("task_input", "")

        if self._orchestrator is None:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text="Orchestrator 未注入，无法估算预算",
            )

        try:
            task_type = self._orchestrator.decision_engine.classify_task(task_input)
            budget: dict[str, int] = self._orchestrator.budget_manager.compute_budget(task_type)
            budget_data: dict[str, Any] = {
                "task_type": task_type.value if isinstance(task_type, TaskType) else str(task_type),
                "budget": budget,
                "total_budget": sum(budget.values()),
            }
            return self._make_result(
                ctx, tool_name,
                ok=True,
                data=budget_data,
                plain_text=f"预算估算完成，类型={task_type.value if isinstance(task_type, TaskType) else task_type}，"
                           f"总预算={sum(budget.values())} tokens",
                next_actions=["构建上下文包", "检索记忆"],
            )
        except Exception as exc:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text=f"预算估算失败：{exc}",
            )

    def _h_memory_retrieve(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.memory.retrieve — 检索相关记忆。

        委托给 orchestrator.memory_router.query_for_task()。

        Args:
            ctx: RunContext。
            args: 包含 task_input 和可选 top_k 的参数字典。

        Returns:
            包含记忆条目列表的 StableAgentToolResult。
        """
        tool_name = "stableagent.memory.retrieve"
        task_input: str = args.get("task_input", "")
        top_k: int = args.get("top_k", 5)

        if self._orchestrator is None:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text="Orchestrator 未注入，无法检索记忆",
            )

        try:
            # query_for_task 需要 task_type，先分类
            task_type = self._orchestrator.decision_engine.classify_task(task_input)
            memories = self._orchestrator.memory_router.query_for_task(
                task_input, task_type, top_k=top_k,
            )
            memory_list: list[dict[str, Any]] = [
                {
                    "id": m.id,
                    "content": m.content,
                    "type": m.type,
                    "priority": m.priority,
                    "source": m.source,
                    "layer": m.layer,
                }
                for m in memories
            ]
            return self._make_result(
                ctx, tool_name,
                ok=True,
                data={"memories": memory_list, "count": len(memory_list)},
                plain_text=f"记忆检索完成，命中 {len(memory_list)} 条相关记忆",
                next_actions=["写入候选记忆", "构建上下文包"],
            )
        except Exception as exc:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text=f"记忆检索失败：{exc}",
            )

    def _h_memory_write(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.memory.write_candidate — 写入候选记忆。

        委托给 orchestrator.memory_router.add_memory_candidate()。

        Args:
            ctx: RunContext。
            args: 包含 content、item_type、source 的参数字典。

        Returns:
            确认写入结果的 StableAgentToolResult。
        """
        tool_name = "stableagent.memory.write_candidate"
        content: str = args.get("content", "")
        item_type: str = args.get("item_type", "success_case")
        source: str = args.get("source", "")

        if self._orchestrator is None:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text="Orchestrator 未注入，无法写入候选记忆",
            )

        try:
            memory_item = self._orchestrator.memory_router.add_memory_candidate(
                content=content,
                item_type=item_type,
                source=source,
            )
            return self._make_result(
                ctx, tool_name,
                ok=True,
                data={
                    "memory_id": memory_item.id,
                    "type": memory_item.type,
                    "status": memory_item.status,
                },
                plain_text=f"候选记忆已写入（ID: {memory_item.id}），类型={item_type}",
                next_actions=["检索记忆", "运行优化回合"],
            )
        except Exception as exc:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text=f"候选记忆写入失败：{exc}",
            )

    def _h_rag_retrieve(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.rag.retrieve — RAG 检索。

        委托给 orchestrator.rag_manager.retrieve()。

        Args:
            ctx: RunContext。
            args: 包含 query 和可选 top_k 的参数字典。

        Returns:
            包含检索文档列表的 StableAgentToolResult。
        """
        tool_name = "stableagent.rag.retrieve"
        query: str = args.get("query", "")
        top_k: int = args.get("top_k", 5)

        if self._orchestrator is None:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text="Orchestrator 未注入，无法执行 RAG 检索",
            )

        try:
            docs: list[str] = self._orchestrator.rag_manager.retrieve(query, top_k=top_k)
            return self._make_result(
                ctx, tool_name,
                ok=True,
                data={"documents": docs, "count": len(docs)},
                plain_text=f"RAG 检索完成，返回 {len(docs)} 条文档",
                next_actions=["构建上下文包", "处理任务"],
            )
        except Exception as exc:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text=f"RAG 检索失败：{exc}",
            )

    def _h_eval_evaluate(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.eval.evaluate — 评测输出质量。

        委托给 orchestrator.evaluator.evaluate()。

        Args:
            ctx: RunContext。
            args: 包含 task_input、input_context、output 的参数字典。

        Returns:
            包含评测结果的 StableAgentToolResult。
        """
        tool_name = "stableagent.eval.evaluate"
        task_input: str = args.get("task_input", "")
        input_context: str = args.get("input_context", "")
        output: str = args.get("output", "")

        if self._orchestrator is None:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text="Orchestrator 未注入，无法执行评测",
            )

        try:
            eval_result: EvaluationResult = self._orchestrator.evaluator.evaluate(
                task_input, input_context, output,
            )
            eval_data: dict[str, Any] = {
                "overall_score": eval_result.overall_score,
                "completion_rate": eval_result.completion_rate,
                "context_hit_rate": eval_result.context_hit_rate,
                "token_efficiency": eval_result.token_efficiency,
                "hallucination_score": eval_result.hallucination_score,
                "user_preference_score": eval_result.user_preference_score,
                "safety_score": eval_result.safety_score,
                "token_roi": eval_result.token_roi,
                "failure_reasons": eval_result.failure_reasons,
                "improvement_rules": eval_result.improvement_rules,
            }
            summary: str = (
                f"评测完成，综合评分={eval_result.overall_score:.2f}，"
                f"完成率={eval_result.completion_rate:.2f}"
            )
            return self._make_result(
                ctx, tool_name,
                ok=True,
                data=eval_data,
                plain_text=summary,
                next_actions=["记录失败案例"] if eval_result.overall_score < 0.6 else [],
            )
        except Exception as exc:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text=f"评测执行失败：{exc}",
            )

    def _h_badcase_record(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.badcase.record — 记录失败案例。

        委托给 orchestrator.bad_case_manager.record_case()。

        Args:
            ctx: RunContext。
            args: 包含 task_input、input_context、output 和可选 evaluation 的参数字典。

        Returns:
            确认记录结果的 StableAgentToolResult。
        """
        tool_name = "stableagent.badcase.record"
        task_input: str = args.get("task_input", "")
        input_context: str = args.get("input_context", "")
        output: str = args.get("output", "")
        evaluation_dict: dict[str, Any] = args.get("evaluation", {})

        if self._orchestrator is None:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text="Orchestrator 未注入，无法记录失败案例",
            )

        try:
            # 如果提供了 evaluation 字典，构造 EvaluationResult；否则执行评测
            if evaluation_dict:
                eval_result = EvaluationResult(
                    overall_score=evaluation_dict.get("overall_score", 0.0),
                    completion_rate=evaluation_dict.get("completion_rate", 0.0),
                    context_hit_rate=evaluation_dict.get("context_hit_rate", 0.0),
                    token_efficiency=evaluation_dict.get("token_efficiency", 0.0),
                    hallucination_score=evaluation_dict.get("hallucination_score", 0.0),
                    user_preference_score=evaluation_dict.get("user_preference_score", 0.0),
                    failure_reasons=evaluation_dict.get("failure_reasons", []),
                    improvement_rules=evaluation_dict.get("improvement_rules", []),
                    safety_score=evaluation_dict.get("safety_score", 1.0),
                )
            else:
                eval_result = self._orchestrator.evaluator.evaluate(
                    task_input, input_context, output,
                )

            bad_case = self._orchestrator.bad_case_manager.record_case(
                task_input, input_context, output, eval_result,
            )
            return self._make_result(
                ctx, tool_name,
                ok=True,
                data={
                    "case_recorded": True,
                    "failure_reason": bad_case.failure_reason,
                    "timestamp": bad_case.timestamp,
                },
                plain_text=f"失败案例已记录，综合评分={eval_result.overall_score:.2f}",
                next_actions=["运行优化回合", "导出最优技能"],
            )
        except Exception as exc:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text=f"失败案例记录失败：{exc}",
            )

    def _h_skillopt_status(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.skillopt.status — 获取 SkillOpt 引擎状态。

        委托给 orchestrator.skillopt_engine（如果可用）。

        Args:
            ctx: RunContext。
            args: 参数字典（当前无参数）。

        Returns:
            包含引擎状态信息的 StableAgentToolResult。
        """
        tool_name = "stableagent.skillopt.status"
        engine = getattr(self._orchestrator, 'skillopt_engine', None) if self._orchestrator else None

        if engine is None:
            return self._make_result(
                ctx, tool_name,
                ok=True,
                data={"status": "not_configured", "message": "SkillOpt engine 未配置"},
                plain_text="SkillOpt 引擎未配置，请先初始化 SkillOptimizationEngine",
            )

        try:
            # 收集引擎状态信息
            status_data: dict[str, Any] = {
                "status": "active",
                "epoch_count": len(getattr(engine, '_longitudinal_results', [])),
                "current_version": getattr(
                    getattr(engine, 'doc_store', None), 'current_version', 'unknown'
                ),
                "best_version": getattr(
                    getattr(engine, 'doc_store', None), 'best_version', 'unknown'
                ),
            }
            return self._make_result(
                ctx, tool_name,
                ok=True,
                data=status_data,
                plain_text=f"SkillOpt 引擎状态：已完成 {status_data['epoch_count']} 个优化回合",
                next_actions=["获取当前技能", "运行优化回合"],
            )
        except Exception as exc:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text=f"获取 SkillOpt 状态失败：{exc}",
            )

    def _h_skillopt_current(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.skillopt.get_current_skill — 获取当前技能文档。

        委托给 orchestrator.skillopt_engine.doc_store（如果可用）。

        Args:
            ctx: RunContext。
            args: 参数字典（当前无参数）。

        Returns:
            包含当前技能文档信息的 StableAgentToolResult。
        """
        tool_name = "stableagent.skillopt.get_current_skill"
        engine = getattr(self._orchestrator, 'skillopt_engine', None) if self._orchestrator else None

        if engine is None:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text="SkillOpt engine 未配置",
            )

        try:
            doc_store = getattr(engine, 'doc_store', None)
            if doc_store is None:
                return self._make_result(
                    ctx, tool_name,
                    ok=False, is_error=True,
                    plain_text="SkillDocumentStore 未配置",
                )

            skill = doc_store.load_current_skill()
            skill_data: dict[str, Any] = {
                "version": getattr(skill, 'version', 'unknown'),
                "content_preview": getattr(skill, 'content', '')[:500] if hasattr(skill, 'content') else '',
                "updated_at": getattr(skill, 'updated_at', None),
            }
            return self._make_result(
                ctx, tool_name,
                ok=True,
                data=skill_data,
                plain_text=f"当前技能版本：{skill_data['version']}",
                next_actions=["运行优化回合", "导出最优技能"],
            )
        except Exception as exc:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text=f"获取当前技能失败：{exc}",
            )

    def _h_skillopt_epoch(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.skillopt.run_epoch — 运行一轮优化。

        委托给 orchestrator.skillopt_engine.run_epoch()。

        Args:
            ctx: RunContext。
            args: 包含可选 max_rollouts 的参数字典。

        Returns:
            包含优化回合结果的 StableAgentToolResult。
        """
        tool_name = "stableagent.skillopt.run_epoch"
        max_rollouts: int = args.get("max_rollouts", 40)
        engine = getattr(self._orchestrator, 'skillopt_engine', None) if self._orchestrator else None

        if engine is None:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text="SkillOpt engine 未配置",
            )

        try:
            result = engine.run_epoch(max_rollouts=max_rollouts)
            return self._make_result(
                ctx, tool_name,
                ok=True,
                data={"epoch_result": str(result) if result is not None else None},
                plain_text=f"优化回合已完成（max_rollouts={max_rollouts}）",
                next_actions=["获取 SkillOpt 状态", "导出最优技能"],
            )
        except Exception as exc:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text=f"优化回合执行失败：{exc}",
            )

    def _h_skillopt_export(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.skillopt.export_best — 导出最优技能。

        委托给 orchestrator.skillopt_engine.export_best_skill()。

        Args:
            ctx: RunContext。
            args: 参数字典（当前无参数）。

        Returns:
            包含导出文件路径的 StableAgentToolResult。
        """
        tool_name = "stableagent.skillopt.export_best"
        engine = getattr(self._orchestrator, 'skillopt_engine', None) if self._orchestrator else None

        if engine is None:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text="SkillOpt engine 未配置",
            )

        try:
            export_path = engine.export_best_skill()
            export_path_str: str = export_path if isinstance(export_path, str) else str(export_path or "")
            return self._make_result(
                ctx, tool_name,
                ok=True,
                data={"export_path": export_path_str},
                plain_text=f"最优技能已导出到：{export_path_str}" if export_path_str else "最优技能导出完成",
                next_actions=["获取 SkillOpt 状态"],
            )
        except Exception as exc:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text=f"导出最优技能失败：{exc}",
            )

    def _h_trace_get_run(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.trace.get_run — 获取运行轨迹。

        委托给 orchestrator.event_bus.get_spans_by_run()。

        Args:
            ctx: RunContext。
            args: 包含 run_id 的参数字典。

        Returns:
            包含 Span 列表的 StableAgentToolResult。
        """
        tool_name = "stableagent.trace.get_run"
        run_id: str = args.get("run_id", ctx.run_id)

        if self._orchestrator is None:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text="Orchestrator 未注入，无法获取 trace",
            )

        try:
            spans = self._orchestrator.event_bus.get_spans_by_run(run_id)
            span_list: list[dict[str, Any]] = [
                {
                    "span_id": s.span_id,
                    "name": s.name,
                    "type": s.type,
                    "status": s.status,
                    "parent_span_id": s.parent_span_id,
                    "latency_ms": s.latency_ms,
                    "input_tokens": s.input_tokens,
                    "output_tokens": s.output_tokens,
                    "plain_text": s.plain_text,
                }
                for s in spans
            ]
            return self._make_result(
                ctx, tool_name,
                ok=True,
                data={"run_id": run_id, "spans": span_list, "span_count": len(span_list)},
                plain_text=f"运行 {run_id} 共有 {len(span_list)} 个 span",
            )
        except Exception as exc:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text=f"获取运行轨迹失败：{exc}",
            )

    def _h_approval_respond(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.approval.respond — 响应审批。

        委托给 orchestrator.approval_manager.approve() 或 reject()。

        Args:
            ctx: RunContext。
            args: 包含 request_id、action（approve/reject）和可选 reason 的参数字典。

        Returns:
            确认审批结果的 StableAgentToolResult。
        """
        tool_name = "stableagent.approval.respond"
        request_id: str = args.get("request_id", "")
        action: str = args.get("action", "approve")
        reason: str = args.get("reason", "")

        if self._orchestrator is None:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text="Orchestrator 未注入，无法响应审批",
            )

        try:
            if action == "approve":
                req = self._orchestrator.approval_manager.approve(request_id)
                plain = f"审批请求 {request_id} 已批准"
            elif action == "reject":
                req = self._orchestrator.approval_manager.reject(request_id, reason)
                plain = f"审批请求 {request_id} 已拒绝" + (f"（原因：{reason}）" if reason else "")
            else:
                return self._make_result(
                    ctx, tool_name,
                    ok=False, is_error=True,
                    plain_text=f"无效的审批操作：{action}，仅支持 approve/reject",
                )

            return self._make_result(
                ctx, tool_name,
                ok=True,
                data={
                    "request_id": request_id,
                    "action": action,
                    "status": req.status,
                    "resolved_at": req.resolved_at,
                },
                plain_text=plain,
            )
        except Exception as exc:
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text=f"审批响应失败：{exc}",
            )

    # V6.5: /os-agent 快捷入口
    def _h_task_os_agent(self, ctx: RunContext, args: dict[str, Any]) -> StableAgentToolResult:
        """处理 stableagent.task.os_agent — OS Agent 自优化工作流。

        启动完整自优化链路（Context → Memory → RAG → Budget → Workflow →
        Eval → SkillOpt），每阶段发布 TraceEvent 供 Dashboard 实时订阅。

        Args:
            ctx: RunContext。
            args: 包含 task_input、mode 等参数字典。

        Returns:
            包含 run_id / dashboard_url / progress_pct 的 StableAgentToolResult。
        """
        tool_name = "stableagent.task.os_agent"
        task_input: str = args.get("task_input", "")
        mode: str = args.get("mode", "auto")
        open_dashboard: bool = args.get("open_dashboard", True)

        if self._orchestrator is None:
            return self._make_result(
                ctx, tool_name, ok=False, is_error=True,
                plain_text="Orchestrator 未注入",
                plain_text_zh="Orchestrator 未注入，无法启动 OS Agent",
                plain_text_en="Orchestrator not injected, cannot start OS Agent",
            )

        try:
            from stable_agent.observation.progress_model import ProgressTracker
            tracker = ProgressTracker()

            # 阶段 1: 接收任务
            stage = tracker.get_stage("mcp_received")
            ctx.current_stage = stage.label_zh
            ctx.progress_pct = stage.pct

            # 阶段 2: 执行任务
            raw_result: Any = self._orchestrator.process_task(task_input)
            # 确保可 JSON 序列化
            import dataclasses
            if dataclasses.is_dataclass(raw_result):
                result = dataclasses.asdict(raw_result)  # type: ignore[arg-type]
            elif isinstance(raw_result, dict):
                result = raw_result
            else:
                result = {"output": str(raw_result)}

            # 阶段 3: 完成
            stage = tracker.get_stage("completed")
            ctx.current_stage = stage.label_zh
            ctx.progress_pct = stage.pct

            return self._make_result(
                ctx, tool_name,
                ok=True,
                data={
                    "run_id": ctx.run_id,
                    "dashboard_url": f"/runs/{ctx.run_id}" if open_dashboard else "",
                    "current_stage": stage.label_zh,
                    "progress_pct": stage.pct,
                    "status_text_zh": stage.status_text_zh,
                    "status_text_en": stage.status_text_en,
                    "task_output": result,
                    "mode": mode,
                    "next_actions": ["查看 Dashboard", "查看决策时间线"],
                },
                plain_text=f"OS Agent 任务完成：{task_input[:80]}",
                plain_text_zh=f"OS Agent 任务完成：{task_input[:80]}",
                plain_text_en=f"OS Agent task completed: {task_input[:80]}",
                dashboard_url=f"/runs/{ctx.run_id}" if open_dashboard else "",
                next_actions=["查看 Dashboard", "查看决策时间线"],
            )
        except Exception as exc:
            import logging
            logger = logging.getLogger(__name__)
            logger.exception("os_agent 执行失败: %s", exc)
            return self._make_result(
                ctx, tool_name,
                ok=False, is_error=True,
                plain_text=f"OS Agent 执行失败：{exc}",
                plain_text_zh=f"OS Agent 任务失败：{exc}",
                plain_text_en=f"OS Agent task failed: {exc}",
                dashboard_url=f"/runs/{ctx.run_id}" if open_dashboard else "",
            )
