"""StableAgent OS MCP 工具注册与调用层模块。
# frozen: V5.6 — 仅允许崩溃级 bug fix，严禁新增业务路由/工具

本模块提供与 REST API 解耦的 MCP 工具定义层，管理所有
StableAgent MCP 工具的定义和调用。每个工具返回统一结构：
  {"ok": bool, "data": Any, "plain_text": str, "warnings": list[str]}

模块职责：
- 注册和管理所有 MCP 工具
- 提供统一调用接口 call_tool
- 使用 PlainLanguageExplainer 生成中文摘要
- 延迟绑定 orchestrator 避免循环导入
"""

from __future__ import annotations

import time
from typing import Any, Callable, Optional


class MCPToolRegistry:
    """MCP 工具注册中心。

    管理所有 StableAgent MCP 工具的定义和调用。通过延迟绑定
    注入 orchestrator 引用，避免循环导入。

    Attributes:
        _orchestrator: orchestrator 引用（延迟绑定）。
        _tools: 工具名 → 工具定义映射。
    """

    def __init__(self, orchestrator: Optional[Any] = None) -> None:
        """初始化 MCP 工具注册中心。

        Args:
            orchestrator: orchestrator 引用，None 时延迟绑定。
        """
        self._orchestrator: Optional[Any] = orchestrator
        self._tools: dict[str, dict] = {}
        self._register_all()

    # ------------------------------------------------------------------
    # 工具注册
    # ------------------------------------------------------------------

    def _register(
        self,
        name: str,
        handler: Callable,
        description: str,
        input_schema: Optional[dict] = None,
    ) -> None:
        """注册单个 MCP 工具。

        Args:
            name: 工具名称（如 "stableagent_build_context_pack"）。
            handler: 工具处理函数，接收 dict 参数，返回 dict。
            description: 工具描述。
            input_schema: JSON Schema 格式的输入定义，None 时使用默认。
        """
        if input_schema is None:
            input_schema = {
                "type": "object",
                "properties": {
                    "task_input": {
                        "type": "string",
                        "description": "用户任务输入文本",
                    },
                },
                "required": ["task_input"],
            }

        self._tools[name] = {
            "name": name,
            "description": description,
            "input_schema": input_schema,
            "handler": handler,
        }

    def _register_all(self) -> None:
        """注册所有 12 个 MCP 工具。"""
        self._register(
            "stableagent_build_context_pack",
            self._handle_build_context_pack,
            "构建上下文包：整合记忆+RAG+规则，生成 ContextPack",
        )
        self._register(
            "stableagent_retrieve_memory",
            self._handle_retrieve_memory,
            "检索相关记忆条目",
        )
        self._register(
            "stableagent_retrieve_knowledge",
            self._handle_retrieve_knowledge,
            "检索项目知识库",
        )
        self._register(
            "stableagent_estimate_budget",
            self._handle_estimate_budget,
            "估算任务所需 token 预算",
        )
        self._register(
            "stableagent_start_workflow",
            self._handle_start_workflow,
            "启动工作流处理任务",
        )
        self._register(
            "stableagent_get_workflow_status",
            self._handle_get_workflow_status,
            "查询工作流当前状态",
        )
        self._register(
            "stableagent_evaluate_output",
            self._handle_evaluate_output,
            "评测模型输出质量",
        )
        self._register(
            "stableagent_record_bad_case",
            self._handle_record_bad_case,
            "记录失败案例",
        )
        self._register(
            "stableagent_get_trace",
            self._handle_get_trace,
            "获取任务 trace",
        )
        self._register(
            "stableagent_list_pending_approvals",
            self._handle_list_approvals,
            "列出待审批的操作",
        )
        self._register(
            "stableagent_approve_action",
            self._handle_approve,
            "批准操作",
        )
        self._register(
            "stableagent_reject_action",
            self._handle_reject,
            "拒绝操作",
        )

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    def call_tool(self, name: str, args: dict) -> dict:
        """调用指定工具。

        Args:
            name: 工具名称。
            args: 工具参数字典。

        Returns:
            统一结构 {"ok": bool, "data": Any, "plain_text": str, "warnings": list[str]}。
        """
        if name not in self._tools:
            return {
                "ok": False,
                "data": None,
                "plain_text": f"未知工具: {name}",
                "warnings": [f"Tool '{name}' not found in registry"],
            }

        handler = self._tools[name]["handler"]

        try:
            result = handler(args)
            # Ensure result has all required fields
            if not isinstance(result, dict):
                result = {"data": result, "plain_text": "", "warnings": []}
            result.setdefault("ok", True)
            result.setdefault("data", None)
            result.setdefault("plain_text", "")
            result.setdefault("warnings", [])
            return result
        except Exception as e:
            return {
                "ok": False,
                "data": None,
                "plain_text": f"工具执行出错: {str(e)}",
                "warnings": [str(e)],
            }

    def list_tools(self) -> list[dict]:
        """返回所有已注册工具列表。

        Returns:
            [{"name": str, "description": str, "input_schema": dict}, ...]。
        """
        return [
            {
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": tool["input_schema"],
            }
            for tool in self._tools.values()
        ]

    # ------------------------------------------------------------------
    # 工具 Handler 实现
    # ------------------------------------------------------------------

    def _get_orchestrator(self) -> Optional[Any]:
        """获取 orchestrator 引用（安全访问）。"""
        return self._orchestrator

    def _get_explainer(self):
        """获取 PlainLanguageExplainer 实例。"""
        orch = self._get_orchestrator()
        if orch is not None:
            try:
                return orch.plain_language
            except AttributeError:
                pass
        # Fallback: create standalone explainer
        from stable_agent.plain_language import PlainLanguageExplainer
        return PlainLanguageExplainer()

    # ---- 上下文包构建 ----
    def _handle_build_context_pack(self, args: dict) -> dict:
        """处理 stableagent_build_context_pack 调用。"""
        warnings: list[str] = []
        task_input: str = args.get("task_input", "")
        if not task_input:
            return {
                "ok": False,
                "data": None,
                "plain_text": "缺少 task_input 参数",
                "warnings": ["task_input is required"],
            }

        orch = self._get_orchestrator()
        if orch is None:
            return {
                "ok": False,
                "data": None,
                "plain_text": "Orchestrator 未初始化，无法构建上下文包",
                "warnings": ["orchestrator is None"],
            }

        try:
            # 任务分类
            task_type = orch.decision_engine.classify_task(task_input)
            # 记忆检索
            memories = orch.memory_router.query_for_task(
                task_input=task_input, task_type=task_type
            )
            # RAG 检索
            rag_chunks = orch.rag_manager.build_context_pack(task_type, 5)
            # 上下文包构建
            pack = orch.context_triage.build_context_pack(
                task_input=task_input,
                task_type=task_type,
                memories=memories,
                rag_chunks=rag_chunks if isinstance(rag_chunks, list) else [],
                budget=8000,
            )

            explainer = self._get_explainer()
            plain_text = explainer.explain("context:built")
            if pack.total_tokens > 0:
                plain_text += f"（包含 {len(pack.items)} 条上下文，共 {pack.total_tokens} tokens）"

            return {
                "ok": True,
                "data": {
                    "pack_id": pack.pack_id,
                    "task_type": task_type.value,
                    "total_tokens": pack.total_tokens,
                    "item_count": len(pack.items),
                    "budget_limit": pack.budget_limit,
                },
                "plain_text": plain_text,
                "warnings": warnings,
            }
        except Exception as e:
            warnings.append(str(e))
            return {
                "ok": False,
                "data": None,
                "plain_text": f"构建上下文包失败: {str(e)}",
                "warnings": warnings,
            }

    # ---- 记忆检索 ----
    def _handle_retrieve_memory(self, args: dict) -> dict:
        """处理 stableagent_retrieve_memory 调用。"""
        warnings: list[str] = []
        task_input: str = args.get("task_input", "")
        top_k: int = args.get("top_k", 5)

        if not task_input:
            return {
                "ok": False,
                "data": None,
                "plain_text": "缺少 task_input 参数",
                "warnings": ["task_input is required"],
            }

        orch = self._get_orchestrator()
        if orch is None:
            return {
                "ok": False,
                "data": None,
                "plain_text": "Orchestrator 未初始化",
                "warnings": ["orchestrator is None"],
            }

        try:
            task_type = orch.decision_engine.classify_task(task_input)
            memories = orch.memory_router.query_for_task(
                task_input=task_input, task_type=task_type, top_k=top_k
            )

            explainer = self._get_explainer()
            plain_text = (
                f"找到了 {len(memories)} 条相关记忆"
                if memories
                else "未找到相关记忆"
            )

            return {
                "ok": True,
                "data": {
                    "memories": [
                        {
                            "id": m.id,
                            "content": m.content,
                            "type": m.type,
                            "priority": m.priority,
                        }
                        for m in memories
                    ],
                    "count": len(memories),
                },
                "plain_text": plain_text,
                "warnings": warnings,
            }
        except Exception as e:
            warnings.append(str(e))
            return {
                "ok": False,
                "data": None,
                "plain_text": f"记忆检索失败: {str(e)}",
                "warnings": warnings,
            }

    # ---- 知识检索 ----
    def _handle_retrieve_knowledge(self, args: dict) -> dict:
        """处理 stableagent_retrieve_knowledge 调用。"""
        warnings: list[str] = []
        task_input: str = args.get("task_input", "")

        if not task_input:
            return {
                "ok": False,
                "data": None,
                "plain_text": "缺少 task_input 参数",
                "warnings": ["task_input is required"],
            }

        orch = self._get_orchestrator()
        if orch is None:
            return {
                "ok": False,
                "data": None,
                "plain_text": "Orchestrator 未初始化",
                "warnings": ["orchestrator is None"],
            }

        try:
            task_type = orch.decision_engine.classify_task(task_input)
            # 使用 retrieve_rich 获取结构化检索结果
            try:
                rag_chunks = orch.rag_manager.retrieve_rich(task_input)
            except AttributeError:
                rag_chunks = orch.rag_manager.build_context_pack(task_type, 5)

            explainer = self._get_explainer()
            chunk_count = len(rag_chunks) if isinstance(rag_chunks, list) else 0
            plain_text = (
                f"检索到 {chunk_count} 篇相关文档"
                if chunk_count
                else "未检索到相关文档"
            )

            return {
                "ok": True,
                "data": {
                    "chunks": rag_chunks if isinstance(rag_chunks, list) else [],
                    "count": chunk_count,
                },
                "plain_text": plain_text,
                "warnings": warnings,
            }
        except Exception as e:
            warnings.append(str(e))
            return {
                "ok": False,
                "data": None,
                "plain_text": f"知识检索失败: {str(e)}",
                "warnings": warnings,
            }

    # ---- 预算估算 ----
    def _handle_estimate_budget(self, args: dict) -> dict:
        """处理 stableagent_estimate_budget 调用。"""
        warnings: list[str] = []
        task_input: str = args.get("task_input", "")

        orch = self._get_orchestrator()
        if orch is None:
            return {
                "ok": False,
                "data": None,
                "plain_text": "Orchestrator 未初始化",
                "warnings": ["orchestrator is None"],
            }

        try:
            task_type = orch.decision_engine.classify_task(task_input)
            budget_dict = orch.budget_manager.compute_budget(task_type)
            model = orch.budget_manager.route_model(task_type)

            total = sum(budget_dict.values())
            explainer = self._get_explainer()
            plain_text = f"预估需要 {total} tokens，建议使用 {model} 模型"

            return {
                "ok": True,
                "data": {
                    "budget": budget_dict,
                    "model": model,
                    "task_type": task_type.value,
                },
                "plain_text": plain_text,
                "warnings": warnings,
            }
        except Exception as e:
            warnings.append(str(e))
            return {
                "ok": False,
                "data": None,
                "plain_text": f"预算估算失败: {str(e)}",
                "warnings": warnings,
            }

    # ---- 工作流启动 ----
    def _handle_start_workflow(self, args: dict) -> dict:
        """处理 stableagent_start_workflow 调用。"""
        warnings: list[str] = []
        task_input: str = args.get("task_input", "")

        if not task_input:
            return {
                "ok": False,
                "data": None,
                "plain_text": "缺少 task_input 参数",
                "warnings": ["task_input is required"],
            }

        orch = self._get_orchestrator()
        if orch is None:
            return {
                "ok": False,
                "data": None,
                "plain_text": "Orchestrator 未初始化",
                "warnings": ["orchestrator is None"],
            }

        try:
            workflow = orch.workflow_engine.start_workflow(task_input)
            explainer = self._get_explainer()
            plain_text = explainer.explain("workflow:started")

            return {
                "ok": True,
                "data": {
                    "task_type": workflow.task_type.value,
                    "current_state": workflow.current_state.value,
                    "history_count": len(workflow.history),
                },
                "plain_text": plain_text,
                "warnings": warnings,
            }
        except Exception as e:
            warnings.append(str(e))
            return {
                "ok": False,
                "data": None,
                "plain_text": f"启动工作流失败: {str(e)}",
                "warnings": warnings,
            }

    # ---- 工作流状态查询 ----
    def _handle_get_workflow_status(self, args: dict) -> dict:
        """处理 stableagent_get_workflow_status 调用。"""
        warnings: list[str] = []
        orch = self._get_orchestrator()

        if orch is None:
            return {
                "ok": False,
                "data": None,
                "plain_text": "Orchestrator 未初始化",
                "warnings": ["orchestrator is None"],
            }

        try:
            summary = orch.get_summary()
            explainer = self._get_explainer()
            plain_text = (
                f"当前系统状态：{summary['memory_count']} 条记忆, "
                f"{summary['event_count']} 条事件, "
                f"{summary['bad_case_count']} 条 bad case, "
                f"{summary['tool_count']} 个工具"
            )

            return {
                "ok": True,
                "data": summary,
                "plain_text": plain_text,
                "warnings": warnings,
            }
        except Exception as e:
            warnings.append(str(e))
            return {
                "ok": False,
                "data": None,
                "plain_text": f"查询状态失败: {str(e)}",
                "warnings": warnings,
            }

    # ---- 输出评估 ----
    def _handle_evaluate_output(self, args: dict) -> dict:
        """处理 stableagent_evaluate_output 调用。"""
        warnings: list[str] = []
        task_input: str = args.get("task_input", "")
        output: str = args.get("output", "")
        input_context: str = args.get("input_context", "")

        if not task_input or not output:
            return {
                "ok": False,
                "data": None,
                "plain_text": "缺少 task_input 或 output 参数",
                "warnings": ["task_input and output are required"],
            }

        orch = self._get_orchestrator()
        if orch is None:
            return {
                "ok": False,
                "data": None,
                "plain_text": "Orchestrator 未初始化",
                "warnings": ["orchestrator is None"],
            }

        try:
            task_type = orch.decision_engine.classify_task(task_input)
            evaluation = orch.evaluator.evaluate(
                task=task_type,
                input_context=input_context or task_input,
                model_output=output,
            )
            feedback = orch.evaluator.generate_feedback(evaluation)

            explainer = self._get_explainer()
            plain_text = (
                f"综合评分: {evaluation.overall_score:.2f}, "
                f"完成率: {evaluation.completion_rate:.2f}, "
                f"幻觉评分: {evaluation.hallucination_score:.2f}"
            )

            return {
                "ok": True,
                "data": {
                    "completion_rate": evaluation.completion_rate,
                    "context_hit_rate": evaluation.context_hit_rate,
                    "token_efficiency": evaluation.token_efficiency,
                    "hallucination_score": evaluation.hallucination_score,
                    "user_preference_score": evaluation.user_preference_score,
                    "overall_score": evaluation.overall_score,
                    "feedback": feedback,
                },
                "plain_text": plain_text,
                "warnings": warnings,
            }
        except Exception as e:
            warnings.append(str(e))
            return {
                "ok": False,
                "data": None,
                "plain_text": f"评估失败: {str(e)}",
                "warnings": warnings,
            }

    # ---- Bad Case 记录 ----
    def _handle_record_bad_case(self, args: dict) -> dict:
        """处理 stableagent_record_bad_case 调用。"""
        warnings: list[str] = []
        task_input: str = args.get("task_input", "")
        output: str = args.get("output", "")

        if not task_input or not output:
            return {
                "ok": False,
                "data": None,
                "plain_text": "缺少 task_input 或 output 参数",
                "warnings": ["task_input and output are required"],
            }

        orch = self._get_orchestrator()
        if orch is None:
            return {
                "ok": False,
                "data": None,
                "plain_text": "Orchestrator 未初始化",
                "warnings": ["orchestrator is None"],
            }

        try:
            from stable_agent.models import EvaluationResult

            eval_data = args.get("evaluation", {})
            task_type = orch.decision_engine.classify_task(task_input)

            evaluation = EvaluationResult(
                completion_rate=eval_data.get("completion_rate", 0.0),
                context_hit_rate=eval_data.get("context_hit_rate", 0.0),
                token_efficiency=eval_data.get("token_efficiency", 0.0),
                hallucination_score=eval_data.get("hallucination_score", 0.0),
                user_preference_score=eval_data.get("user_preference_score", 0.0),
                overall_score=eval_data.get("overall_score", 0.0),
            )

            orch.bad_case_manager.record_case(
                task=task_type,
                input_context=task_input,
                output=output,
                evaluation=evaluation,
            )

            explainer = self._get_explainer()
            plain_text = f"已记录 bad case（评分: {evaluation.overall_score:.2f}）"

            return {
                "ok": True,
                "data": {"recorded": True},
                "plain_text": plain_text,
                "warnings": warnings,
            }
        except Exception as e:
            warnings.append(str(e))
            return {
                "ok": False,
                "data": None,
                "plain_text": f"记录 bad case 失败: {str(e)}",
                "warnings": warnings,
            }

    # ---- Trace 获取 ----
    def _handle_get_trace(self, args: dict) -> dict:
        """处理 stableagent_get_trace 调用。"""
        warnings: list[str] = []
        run_id: str = args.get("run_id", "")

        orch = self._get_orchestrator()
        if orch is None:
            return {
                "ok": False,
                "data": None,
                "plain_text": "Orchestrator 未初始化",
                "warnings": ["orchestrator is None"],
            }

        try:
            if run_id and hasattr(orch, 'storage'):
                spans = orch.storage.load_spans(run_id)
                explainer = self._get_explainer()
                plain_text = (
                    f"获取到 {len(spans)} 条 trace span"
                    if spans
                    else "未找到 trace 数据"
                )
                return {
                    "ok": True,
                    "data": {
                        "spans": [
                            {
                                "span_id": s.span_id,
                                "name": s.name,
                                "type": s.type,
                                "status": s.status,
                                "latency_ms": s.latency_ms,
                            }
                            for s in spans
                        ],
                        "count": len(spans),
                    },
                    "plain_text": plain_text,
                    "warnings": warnings,
                }
            else:
                return {
                    "ok": False,
                    "data": None,
                    "plain_text": "需要提供 run_id 参数",
                    "warnings": ["run_id is required"],
                }
        except Exception as e:
            warnings.append(str(e))
            return {
                "ok": False,
                "data": None,
                "plain_text": f"获取 trace 失败: {str(e)}",
                "warnings": warnings,
            }

    # ---- 审批列表 ----
    def _handle_list_approvals(self, args: dict) -> dict:
        """处理 stableagent_list_pending_approvals 调用。"""
        warnings: list[str] = []
        orch = self._get_orchestrator()

        if orch is None:
            return {
                "ok": False,
                "data": None,
                "plain_text": "Orchestrator 未初始化",
                "warnings": ["orchestrator is None"],
            }

        try:
            approvals = orch.approval_manager.list_pending()
            explainer = self._get_explainer()
            plain_text = (
                f"有 {len(approvals)} 条待审批操作"
                if approvals
                else "没有待审批的操作"
            )

            return {
                "ok": True,
                "data": {
                    "approvals": [
                        {
                            "request_id": a.request_id,
                            "action": a.action,
                            "risk": a.risk,
                            "reason": a.reason,
                            "status": a.status,
                        }
                        for a in approvals
                    ],
                    "count": len(approvals),
                },
                "plain_text": plain_text,
                "warnings": warnings,
            }
        except Exception as e:
            warnings.append(str(e))
            return {
                "ok": False,
                "data": None,
                "plain_text": f"查询审批列表失败: {str(e)}",
                "warnings": warnings,
            }

    # ---- 批准操作 ----
    def _handle_approve(self, args: dict) -> dict:
        """处理 stableagent_approve_action 调用。"""
        warnings: list[str] = []
        request_id: str = args.get("request_id", "")

        if not request_id:
            return {
                "ok": False,
                "data": None,
                "plain_text": "缺少 request_id 参数",
                "warnings": ["request_id is required"],
            }

        orch = self._get_orchestrator()
        if orch is None:
            return {
                "ok": False,
                "data": None,
                "plain_text": "Orchestrator 未初始化",
                "warnings": ["orchestrator is None"],
            }

        try:
            req = orch.approval_manager.approve(request_id)
            explainer = self._get_explainer()
            plain_text = f"已批准操作: {req.action}"

            return {
                "ok": True,
                "data": {
                    "request_id": req.request_id,
                    "status": req.status,
                },
                "plain_text": plain_text,
                "warnings": warnings,
            }
        except Exception as e:
            warnings.append(str(e))
            return {
                "ok": False,
                "data": None,
                "plain_text": f"批准失败: {str(e)}",
                "warnings": warnings,
            }

    # ---- 拒绝操作 ----
    def _handle_reject(self, args: dict) -> dict:
        """处理 stableagent_reject_action 调用。"""
        warnings: list[str] = []
        request_id: str = args.get("request_id", "")
        reason: str = args.get("reason", "")

        if not request_id:
            return {
                "ok": False,
                "data": None,
                "plain_text": "缺少 request_id 参数",
                "warnings": ["request_id is required"],
            }

        orch = self._get_orchestrator()
        if orch is None:
            return {
                "ok": False,
                "data": None,
                "plain_text": "Orchestrator 未初始化",
                "warnings": ["orchestrator is None"],
            }

        try:
            req = orch.approval_manager.reject(request_id, reason)
            explainer = self._get_explainer()
            plain_text = f"已拒绝操作: {req.action}"

            return {
                "ok": True,
                "data": {
                    "request_id": req.request_id,
                    "status": req.status,
                },
                "plain_text": plain_text,
                "warnings": warnings,
            }
        except Exception as e:
            warnings.append(str(e))
            return {
                "ok": False,
                "data": None,
                "plain_text": f"拒绝失败: {str(e)}",
                "warnings": warnings,
            }
