"""MCP Server — 将 StableAgent 核心能力暴露为 REST API。

本模块是 StableAgent OS 的 HTTP 集成层，通过 FastAPI 将上下文构建、
记忆检索、预算估算、输出评估等核心能力暴露为标准化 REST 端点，
供 Claude Code、Cursor 等 MCP（Model Context Protocol）客户端调用。

V3 升级：
- 新增 MCP tools 端点组 (挂载在 /mcp/tools/)
- 新增 mcp_tools 可选依赖注入

统一响应格式：
  {"code": 0, "data": {...}, "message": "success"}

模块职责：
- 创建和配置 FastAPI app
- 注册所有 REST 路由
- 将核心模块的方法封装为 HTTP 端点
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from stable_agent.models import MemoryItem, TaskType

if TYPE_CHECKING:
    from stable_agent.context_budget_manager import ContextBudgetManager
    from stable_agent.context_decision_engine import ContextDecisionEngine
    from stable_agent.eval_and_bad_case import BadCaseManager, Evaluator
    from stable_agent.memory_router import MemoryRouter
    from stable_agent.trace_event_bus import EventBus
    from stable_agent.workflow_state_machine import WorkflowEngine
    from stable_agent.mcp_tools import MCPToolRegistry
    from stable_agent.mcp.skillopt_tools import SkillOptMCPTools


# ============================================================================
# 辅助函数
# ============================================================================


def _memory_item_to_dict(item: MemoryItem) -> dict:
    """将 MemoryItem 转换为 JSON 可序列化的字典。

    Args:
        item: MemoryItem 实例。

    Returns:
        包含所有字段的字典。
    """
    return {
        "id": item.id,
        "content": item.content,
        "type": item.type,
        "timestamp": item.timestamp,
        "priority": item.priority,
        "source": item.source,
        "status": item.status,
    }


def _ok_response(data: object = None, message: str = "success") -> JSONResponse:
    """构建统一成功响应。

    Args:
        data: 响应数据负载。
        message: 响应消息。

    Returns:
        JSONResponse 实例。
    """
    return JSONResponse(content={"code": 0, "data": data, "message": message})


def _err_response(message: str, code: int = 1) -> JSONResponse:
    """构建统一错误响应。

    Args:
        message: 错误描述。
        code: 错误码，默认 1。

    Returns:
        JSONResponse 实例。
    """
    return JSONResponse(content={"code": code, "data": None, "message": message})


# ============================================================================
# MCPServer — MCP HTTP API 服务
# ============================================================================


class MCPServer:
    """MCP Server — FastAPI HTTP API 服务。

    将 StableAgent 核心能力暴露为 REST API，供 MCP 客户端调用。
    通过构造函数注入所有核心模块，实现松耦合。

    V3 新增：
    - mcp_tools: MCP 工具注册中心（可选依赖）
    - /tools/list 和 /tools/call 端点

    Attributes:
        app: FastAPI 应用实例。
        decision_engine: 上下文决策引擎。
        budget_manager: 上下文预算管理器。
        memory_router: 记忆路由模块。
        evaluator: 评估器。
        bad_case_manager: 负面案例管理器。
        workflow_engine: 工作流引擎。
        event_bus: 事件总线。
        mcp_tools: MCP 工具注册中心（可选）。
    """

    def __init__(
        self,
        decision_engine: ContextDecisionEngine,
        budget_manager: ContextBudgetManager,
        memory_router: MemoryRouter,
        evaluator: Evaluator,
        bad_case_manager: BadCaseManager,
        workflow_engine: WorkflowEngine,
        event_bus: EventBus,
        mcp_tools: Optional[MCPToolRegistry] = None,
        skillopt_tools: Optional[SkillOptMCPTools] = None,
    ) -> None:
        """初始化 MCP Server 并注册所有路由。

        通过构造函数注入所有依赖，创建 FastAPI app 实例，
        并调用 _register_routes 注册所有 API 端点。

        Args:
            decision_engine: 上下文决策引擎实例。
            budget_manager: 上下文预算管理器实例。
            memory_router: 记忆路由模块实例。
            evaluator: 评估器实例。
            bad_case_manager: 负面案例管理器实例。
            workflow_engine: 工作流引擎实例。
            event_bus: 事件总线实例。
            mcp_tools: MCP 工具注册中心实例（可选）。
            skillopt_tools: V4 SkillOpt MCP 工具实例（可选）。
        """
        self.decision_engine: ContextDecisionEngine = decision_engine
        self.budget_manager: ContextBudgetManager = budget_manager
        self.memory_router: MemoryRouter = memory_router
        self.evaluator: Evaluator = evaluator
        self.bad_case_manager: BadCaseManager = bad_case_manager
        self.workflow_engine: WorkflowEngine = workflow_engine
        self.event_bus: EventBus = event_bus
        self.mcp_tools: Optional[MCPToolRegistry] = mcp_tools
        self.skillopt_tools: Optional[SkillOptMCPTools] = skillopt_tools

        # 创建 FastAPI app
        self.app: FastAPI = FastAPI(title="StableAgent MCP Server", version="0.2.0")

        # 注册路由
        self._register_routes()

    def _register_routes(self) -> None:
        """注册所有 REST API 路由。

        将每个端点绑定到对应的处理方法。使用闭包捕获 self 引用，
        确保方法内的 self 指向 MCPServer 实例。
        """
        app: FastAPI = self.app

        # ----- POST /api/build_context_pack -----
        @app.post("/api/build_context_pack")
        async def build_context_pack(request: dict) -> JSONResponse:
            """构建上下文包。

            调用 budget_manager 和 memory_router 生成包含记忆和
            预算信息的完整上下文数据包。

            请求体：{"task_input": "..."}

            Returns:
                JSONResponse 包含 memory_items 和 budget。
            """
            task_input: str = request.get("task_input", "")

            if not task_input:
                return _err_response("task_input is required")

            try:
                # 任务分类
                task_type: TaskType = self.decision_engine.classify_task(task_input)

                # 检索记忆
                memory_items: list[MemoryItem] = self.memory_router.query_for_task(
                    task_input=task_input,
                    task_type=task_type,
                )

                # 计算预算
                budget: dict[str, int] = self.budget_manager.compute_budget(task_type)

                # 构建上下文包
                context_pack: dict = {
                    "memory_items": [_memory_item_to_dict(m) for m in memory_items],
                    "budget": budget,
                    "task_type": task_type.value,
                }

                return _ok_response(data=context_pack)
            except Exception as e:
                return _err_response(str(e))

        # ----- POST /api/retrieve_memory -----
        @app.post("/api/retrieve_memory")
        async def retrieve_memory(request: dict) -> JSONResponse:
            """检索相关记忆。

            请求体：{"task_input": "...", "top_k": 5}

            Returns:
                JSONResponse 包含 memories 列表。
            """
            task_input: str = request.get("task_input", "")
            top_k: int = request.get("top_k", 5)

            if not task_input:
                return _err_response("task_input is required")

            try:
                # 任务分类
                task_type: TaskType = self.decision_engine.classify_task(task_input)

                # 检索记忆
                memories: list[MemoryItem] = self.memory_router.query_for_task(
                    task_input=task_input,
                    task_type=task_type,
                    top_k=top_k,
                )

                return _ok_response(
                    data={"memories": [_memory_item_to_dict(m) for m in memories]}
                )
            except Exception as e:
                return _err_response(str(e))

        # ----- POST /api/estimate_budget -----
        @app.post("/api/estimate_budget")
        async def estimate_budget(request: dict) -> JSONResponse:
            """估算 token 预算建议。

            请求体：{"task_input": "..."}

            Returns:
                JSONResponse 包含 budget 和 model 建议。
            """
            task_input: str = request.get("task_input", "")

            if not task_input:
                return _err_response("task_input is required")

            try:
                # 任务分类
                task_type: TaskType = self.decision_engine.classify_task(task_input)

                # 计算预算
                budget: dict[str, int] = self.budget_manager.compute_budget(task_type)

                # 模型路由
                model: str = self.budget_manager.route_model(task_type)

                return _ok_response(
                    data={
                        "budget": budget,
                        "model": model,
                        "task_type": task_type.value,
                    }
                )
            except Exception as e:
                return _err_response(str(e))

        # ----- POST /api/evaluate_output -----
        @app.post("/api/evaluate_output")
        async def evaluate_output(request: dict) -> JSONResponse:
            """评测模型输出。

            请求体：
            {
                "task_input": "...",
                "input_context": "...",
                "output": "..."
            }

            Returns:
                JSONResponse 包含 evaluation 和 feedback。
            """
            task_input: str = request.get("task_input", "")
            input_context: str = request.get("input_context", "")
            output: str = request.get("output", "")

            if not task_input or not output:
                return _err_response("task_input and output are required")

            try:
                # 任务分类
                task_type: TaskType = self.decision_engine.classify_task(task_input)

                # 执行评估
                from stable_agent.models import EvaluationResult

                evaluation = self.evaluator.evaluate(
                    task=task_type,
                    input_context=input_context or task_input,
                    model_output=output,
                )

                # 生成反馈
                feedback: str = self.evaluator.generate_feedback(evaluation)

                eval_dict: dict = {
                    "completion_rate": evaluation.completion_rate,
                    "context_hit_rate": evaluation.context_hit_rate,
                    "token_efficiency": evaluation.token_efficiency,
                    "hallucination_score": evaluation.hallucination_score,
                    "user_preference_score": evaluation.user_preference_score,
                    "overall_score": evaluation.overall_score,
                }

                return _ok_response(
                    data={"evaluation": eval_dict, "feedback": feedback}
                )
            except Exception as e:
                return _err_response(str(e))

        # ----- POST /api/record_bad_case -----
        @app.post("/api/record_bad_case")
        async def record_bad_case(request: dict) -> JSONResponse:
            """记录失败案例。

            请求体：
            {
                "task_input": "...",
                "input_context": "...",
                "output": "...",
                "evaluation": {...}
            }

            Returns:
                JSONResponse 确认消息。
            """
            task_input: str = request.get("task_input", "")
            input_context: str = request.get("input_context", "")
            output: str = request.get("output", "")
            eval_data: dict = request.get("evaluation", {})

            if not task_input or not output:
                return _err_response("task_input and output are required")

            try:
                from stable_agent.models import EvaluationResult

                # 按收到的方式使用评估数据
                task_type: TaskType = self.decision_engine.classify_task(task_input)

                # 构建 EvaluationResult
                evaluation: EvaluationResult = EvaluationResult(
                    completion_rate=eval_data.get("completion_rate", 0.0),
                    context_hit_rate=eval_data.get("context_hit_rate", 0.0),
                    token_efficiency=eval_data.get("token_efficiency", 0.0),
                    hallucination_score=eval_data.get("hallucination_score", 0.0),
                    user_preference_score=eval_data.get("user_preference_score", 0.0),
                    overall_score=eval_data.get("overall_score", 0.0),
                )

                # 记录 bad case
                self.bad_case_manager.record_case(
                    task=task_type,
                    input_context=input_context or task_input,
                    output=output,
                    evaluation=evaluation,
                )

                return _ok_response(data=None, message="bad case recorded")
            except Exception as e:
                return _err_response(str(e))

        # ----- POST /api/process_task -----
        @app.post("/api/process_task")
        async def process_task(request: dict) -> JSONResponse:
            """端到端处理任务（演示用）。

            启动完整的 WorkflowEngine 流水线，从分类到评估。
            请求体：{"task_input": "..."}

            Returns:
                JSONResponse 包含 workflow context_pack 和 evaluation。
            """
            task_input: str = request.get("task_input", "")

            if not task_input:
                return _err_response("task_input is required")

            try:
                # 启动工作流
                workflow = self.workflow_engine.start_workflow(task_input)

                # 推进到 COMPLETE 状态
                from stable_agent.models import WorkflowState

                while workflow.current_state != WorkflowState.COMPLETE:
                    self.workflow_engine.next_step(workflow)

                return _ok_response(
                    data={
                        "workflow": workflow.context_pack,
                        "evaluation": workflow.context_pack.get("evaluation", {}),
                        "task_type": workflow.task_type.value,
                    },
                    message="task processed",
                )
            except Exception as e:
                return _err_response(str(e))

        # ----- GET /api/health -----
        @app.get("/api/health")
        async def health_check() -> JSONResponse:
            """健康检查端点。

            Returns:
                JSONResponse 包含服务状态。
            """
            return _ok_response(
                data={"status": "healthy", "service": "StableAgent MCP Server V3"}
            )

        # ==================================================================
        # V3 新增：MCP Tools 端点组
        # ==================================================================

        # ----- POST /tools/list -----
        @app.post("/tools/list")
        async def mcp_list_tools() -> JSONResponse:
            """返回所有 MCP 工具列表。

            Returns:
                JSONResponse 包含 tools 列表。
            """
            if self.mcp_tools is None:
                return _err_response("MCP tools not configured")

            try:
                tools = self.mcp_tools.list_tools()
                return _ok_response(data={"tools": tools, "count": len(tools)})
            except Exception as e:
                return _err_response(str(e))

        # ----- POST /tools/call -----
        @app.post("/tools/call")
        async def mcp_call_tool(request: dict) -> JSONResponse:
            """调用指定 MCP 工具。

            请求体: {"name": "...", "arguments": {...}}

            Returns:
                JSONResponse 包含工具执行结果。
            """
            if self.mcp_tools is None:
                return _err_response("MCP tools not configured")

            tool_name: str = request.get("name", "")
            arguments: dict = request.get("arguments", {})

            if not tool_name:
                return _err_response("tool name is required")

            try:
                result = self.mcp_tools.call_tool(tool_name, arguments)
                if result.get("ok"):
                    return _ok_response(
                        data={
                            "data": result.get("data"),
                            "plain_text": result.get("plain_text", ""),
                            "warnings": result.get("warnings", []),
                        }
                    )
                else:
                    return _err_response(
                        message=result.get("plain_text", "Tool call failed"),
                    )
            except Exception as e:
                return _err_response(str(e))

        # ==================================================================
        # V4 新增：SkillOpt MCP Tools 端点组
        # ==================================================================

        @app.post("/tools/skillopt/get_current_skill")
        async def skillopt_get_current() -> JSONResponse:
            """获取当前 skill 文档内容和版本。"""
            if self.skillopt_tools is None:
                return _err_response("SkillOpt tools not configured")
            try:
                result = self.skillopt_tools.get_current_skill()
                if result.get("ok"):
                    return _ok_response(
                        data=result.get("data"),
                        message=result.get("plain_text", ""),
                    )
                return _err_response(message=result.get("plain_text", ""))
            except Exception as e:
                return _err_response(str(e))

        @app.post("/tools/skillopt/get_best_skill")
        async def skillopt_get_best() -> JSONResponse:
            """获取 best skill 文档。"""
            if self.skillopt_tools is None:
                return _err_response("SkillOpt tools not configured")
            try:
                result = self.skillopt_tools.get_best_skill()
                if result.get("ok"):
                    return _ok_response(
                        data=result.get("data"),
                        message=result.get("plain_text", ""),
                    )
                return _err_response(message=result.get("plain_text", ""))
            except Exception as e:
                return _err_response(str(e))

        @app.post("/tools/skillopt/submit_feedback")
        async def skillopt_submit_feedback(request: dict) -> JSONResponse:
            """提交用户反馈到指定 run。

            请求体: {"run_id": "...", "feedback": "accepted|edited|rejected"}
            """
            if self.skillopt_tools is None:
                return _err_response("SkillOpt tools not configured")
            run_id: str = request.get("run_id", "")
            feedback: str = request.get("feedback", "")
            try:
                result = self.skillopt_tools.submit_user_feedback(
                    run_id, feedback
                )
                if result.get("ok"):
                    return _ok_response(
                        data=result.get("data"),
                        message=result.get("plain_text", ""),
                    )
                return _err_response(message=result.get("plain_text", ""))
            except Exception as e:
                return _err_response(str(e))

        @app.post("/tools/skillopt/collect_rollout")
        async def skillopt_collect_rollout(request: dict) -> JSONResponse:
            """从指定 run 采集轨迹。

            请求体: {"run_id": "..."}
            """
            if self.skillopt_tools is None:
                return _err_response("SkillOpt tools not configured")
            run_id: str = request.get("run_id", "")
            try:
                result = self.skillopt_tools.collect_rollout(run_id)
                if result.get("ok"):
                    return _ok_response(
                        data=result.get("data"),
                        message=result.get("plain_text", ""),
                    )
                return _err_response(message=result.get("plain_text", ""))
            except Exception as e:
                return _err_response(str(e))

        @app.post("/tools/skillopt/run_epoch")
        async def skillopt_run_epoch(request: dict) -> JSONResponse:
            """运行一个完整的 Skill 优化 epoch。

            请求体: {"max_rollouts": 40}
            """
            if self.skillopt_tools is None:
                return _err_response("SkillOpt tools not configured")
            max_rollouts: int = request.get("max_rollouts", 40)
            try:
                result = self.skillopt_tools.run_skill_optimization_epoch(
                    max_rollouts=max_rollouts,
                )
                if result.get("ok"):
                    return _ok_response(
                        data=result.get("data"),
                        message=result.get("plain_text", ""),
                    )
                return _err_response(message=result.get("plain_text", ""))
            except Exception as e:
                return _err_response(str(e))

        @app.post("/tools/skillopt/validate_candidate")
        async def skillopt_validate(request: dict) -> JSONResponse:
            """验证候选 skill 版本。

            请求体: {"candidate_version": "..."}
            """
            if self.skillopt_tools is None:
                return _err_response("SkillOpt tools not configured")
            candidate_version: str = request.get("candidate_version", "")
            try:
                result = self.skillopt_tools.validate_candidate_skill(
                    candidate_version
                )
                if result.get("ok"):
                    return _ok_response(
                        data=result.get("data"),
                        message=result.get("plain_text", ""),
                    )
                return _err_response(message=result.get("plain_text", ""))
            except Exception as e:
                return _err_response(str(e))

        @app.post("/tools/skillopt/export_best")
        async def skillopt_export() -> JSONResponse:
            """导出 best_skill.md。"""
            if self.skillopt_tools is None:
                return _err_response("SkillOpt tools not configured")
            try:
                result = self.skillopt_tools.export_best_skill()
                if result.get("ok"):
                    return _ok_response(
                        data=result.get("data"),
                        message=result.get("plain_text", ""),
                    )
                return _err_response(message=result.get("plain_text", ""))
            except Exception as e:
                return _err_response(str(e))

        @app.post("/tools/skillopt/diff_versions")
        async def skillopt_diff(request: dict) -> JSONResponse:
            """获取两个版本之间的 diff。

            请求体: {"old_version": "...", "new_version": "..."}
            """
            if self.skillopt_tools is None:
                return _err_response("SkillOpt tools not configured")
            old_version: str = request.get("old_version", "")
            new_version: str = request.get("new_version", "")
            try:
                result = self.skillopt_tools.get_skill_diff(
                    old_version, new_version
                )
                if result.get("ok"):
                    return _ok_response(
                        data=result.get("data"),
                        message=result.get("plain_text", ""),
                    )
                return _err_response(message=result.get("plain_text", ""))
            except Exception as e:
                return _err_response(str(e))

        @app.post("/tools/skillopt/list_rejected")
        async def skillopt_list_rejected() -> JSONResponse:
            """列出被拒绝的编辑。"""
            if self.skillopt_tools is None:
                return _err_response("SkillOpt tools not configured")
            try:
                result = self.skillopt_tools.list_rejected_edits()
                if result.get("ok"):
                    return _ok_response(
                        data=result.get("data"),
                        message=result.get("plain_text", ""),
                    )
                return _err_response(message=result.get("plain_text", ""))
            except Exception as e:
                return _err_response(str(e))

        @app.post("/tools/skillopt/status")
        async def skillopt_status() -> JSONResponse:
            """获取优化引擎状态摘要。"""
            if self.skillopt_tools is None:
                return _err_response("SkillOpt tools not configured")
            try:
                result = self.skillopt_tools.get_optimization_status()
                if result.get("ok"):
                    return _ok_response(
                        data=result.get("data"),
                        message=result.get("plain_text", ""),
                    )
                return _err_response(message=result.get("plain_text", ""))
            except Exception as e:
                return _err_response(str(e))

    def start_server(self, host: str = "0.0.0.0", port: int = 8000) -> None:
        """启动 MCP Server（独立运行模式）。

        调用 uvicorn.run 启动 FastAPI 应用。通常不直接调用此方法，
        而是通过 web/server.py 的 create_app 挂载到主应用。

        Args:
            host: 绑定地址，默认 "0.0.0.0"。
            port: 绑定端口，默认 8000。
        """
        import uvicorn

        uvicorn.run(self.app, host=host, port=port)
