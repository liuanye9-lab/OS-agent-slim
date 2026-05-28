"""ToolRouter — 工具路由器。

负责 MCP tools/call 的完整执行流程：安全审批、事件发布、handler 路由、
结果收集。每次调用 route() 创建一个新的 RunContext 并贯穿整个生命周期。

流程：
1. 创建 RunContext
2. 查找工具定义
3. 发布 mcp.call.received 事件
4. 风险评估（forbidden → 拒绝，high → 审批）
5. 发布 tool.risk_checked 事件
6. handler 查找
7. 发布 tool.started 事件
8. 执行 handler
9. 成功 → tool.completed，失败 → tool.failed
10. 追加事件到 RunStore
11. 发布事件到 EventStream

用法::

    router = ToolRouter(registry, run_store=store, event_stream=stream)
    result = router.route("stableagent.memory.retrieve", {"task_input": "..."})
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

logger = logging.getLogger(__name__)

from stable_agent.gateway.run_context import RunContext
from stable_agent.gateway.tool_schemas import get_tool_by_name, get_risk_level, get_avatar_state
from stable_agent.models import StableAgentToolResult


class ToolRouter:
    """工具路由器。

    负责执行前审批检查、事件发布、执行和结果收集。
    每个 route() 调用创建一个独立的 RunContext 实例。

    Attributes:
        _registry: UnifiedToolRegistry 实例。
        _security_policy: SecurityPolicy 实例（可选）。
        _approval_manager: ApprovalManager 实例（可选）。
        _run_store: RunStore 实例（可选）。
        _event_stream: EventStream 实例（可选）。
        _event_bus: EventBus 实例（可选）。
    """

    def __init__(
        self,
        registry: Any,
        security_policy: Any = None,
        approval_manager: Any = None,
        run_store: Any = None,
        event_stream: Any = None,
        event_bus: Any = None,
    ) -> None:
        """初始化 ToolRouter。

        Args:
            registry: UnifiedToolRegistry 实例。
            security_policy: SecurityPolicy 实例，用于风险评估。None 则跳过安全检查。
            approval_manager: ApprovalManager 实例，用于高风险操作审批。
            run_store: RunStore 实例，用于事件持久化。
            event_stream: EventStream 实例，用于异步事件广播。
            event_bus: EventBus 实例，用于事件发布。
        """
        self._registry = registry
        self._security_policy = security_policy
        self._approval_manager = approval_manager
        self._run_store = run_store
        self._event_stream = event_stream
        self._event_bus = event_bus

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    def route(self, tool_name: str, args: dict[str, Any]) -> StableAgentToolResult:
        """主路由方法。接收工具名和参数，返回统一结果。

        完整流程：上下文创建 → 工具查找 → 安全检查 → handler 执行 → 事件发布。

        Args:
            tool_name: 工具完整名称，如 "stableagent.memory.retrieve"。
            args: 工具参数字典。

        Returns:
            StableAgentToolResult 包含执行结果、事件和元数据。

        Raises:
            不抛出异常 —— 所有错误均包装为 StableAgentToolResult(is_error=True)。
        """
        # 1. 创建 RunContext
        ctx = RunContext()

        # 2. 查找工具定义
        tool_def: dict[str, Any] | None = get_tool_by_name(tool_name)
        if tool_def is None:
            return StableAgentToolResult(
                ok=False,
                run_id=ctx.run_id,
                tool_call_id=ctx.tool_call_id,
                tool_name=tool_name,
                plain_text=f"未知工具：{tool_name}",
                trace_url=f"/runs/{ctx.run_id}",
                is_error=True,
            )

        # 3. 发布 mcp.call.received 事件
        received_event: dict[str, Any] = self._make_event_dict(
            ctx, "mcp.call.received",
            payload={"tool_name": tool_name, "args": args},
            plain_text=f"收到工具调用：{tool_name}",
        )
        self._publish_event(received_event)

        # 4. 风险评估
        risk_level: str = get_risk_level(tool_name)
        if self._security_policy is not None:
            risk_level = self._assess_risk(tool_name, args)

        if risk_level == "forbidden":
            forbidden_result = StableAgentToolResult(
                ok=False,
                run_id=ctx.run_id,
                tool_call_id=ctx.tool_call_id,
                tool_name=tool_name,
                plain_text=f"禁止执行：工具 {tool_name} 被安全策略标记为 forbidden",
                trace_url=f"/runs/{ctx.run_id}",
                is_error=True,
            )
            # 发布 tool.failed 事件
            failed_event: dict[str, Any] = self._make_event_dict(
                ctx, "tool.failed",
                payload={"tool_name": tool_name, "reason": "forbidden"},
                plain_text=f"工具执行被禁止：{tool_name}",
            )
            self._publish_event(failed_event)
            self._append_to_store(ctx.run_id, failed_event)
            return forbidden_result

        # 高风险 → 创建审批请求（STUB：简化处理，标记需要审批但继续执行）
        needs_approval: bool = risk_level == "high"
        if needs_approval and self._approval_manager is not None:
            try:
                approval_req = self._approval_manager.create_request(
                    run_id=ctx.run_id,
                    action=f"执行高风险工具 {tool_name}",
                    risk=risk_level,
                    reason=f"工具 {tool_name} 被风险评估为高风险",
                    details={"tool_name": tool_name, "args": args},
                )
                # 发布审批事件
                approval_event: dict[str, Any] = self._make_event_dict(
                    ctx, "approval.required",
                    payload={
                        "tool_name": tool_name,
                        "request_id": approval_req.request_id,
                        "risk": risk_level,
                    },
                    plain_text=f"高风险工具 {tool_name} 需要审批（request_id={approval_req.request_id}）",
                )
                self._publish_event(approval_event)
                self._append_to_store(ctx.run_id, approval_event)
            except Exception as e:
                # 审批创建失败不阻塞执行
                logger.warning("审批请求创建失败，继续执行: %s", e)

        # 5. 发布 tool.risk_checked 事件
        risk_checked_event: dict[str, Any] = self._make_event_dict(
            ctx, "tool.risk_checked",
            payload={"tool_name": tool_name, "risk_level": risk_level, "needs_approval": needs_approval},
            plain_text=f"工具 {tool_name} 风险评估完成：{risk_level}",
        )
        self._publish_event(risk_checked_event)

        # 6. 查找 handler
        handler = self._registry.get_handler(tool_name)
        if handler is None:
            missing_result = StableAgentToolResult(
                ok=False,
                run_id=ctx.run_id,
                tool_call_id=ctx.tool_call_id,
                tool_name=tool_name,
                plain_text=f"工具 {tool_name} 已注册但无 handler",
                trace_url=f"/runs/{ctx.run_id}",
                is_error=True,
            )
            failed_event2: dict[str, Any] = self._make_event_dict(
                ctx, "tool.failed",
                payload={"tool_name": tool_name, "reason": "no_handler"},
                plain_text=f"工具 {tool_name} 无 handler",
            )
            self._publish_event(failed_event2)
            self._append_to_store(ctx.run_id, failed_event2)
            return missing_result

        # 7. 发布 tool.started 事件
        started_event: dict[str, Any] = self._make_event_dict(
            ctx, "tool.started",
            payload={"tool_name": tool_name},
            plain_text=f"开始执行工具：{tool_name}",
        )
        self._publish_event(started_event)

        # 8. 执行 handler
        try:
            result: StableAgentToolResult = handler(ctx, args)

            # 9. 成功 → 发布 tool.completed
            completed_event: dict[str, Any] = self._make_event_dict(
                ctx, "tool.completed",
                payload={"tool_name": tool_name, "ok": result.ok},
                plain_text=result.plain_text,
            )
            self._publish_event(completed_event)
            self._append_to_store(ctx.run_id, completed_event)

            # 如果任务完成，发布 task.completed
            if tool_name == "stableagent.task.process" and result.ok:
                task_completed_event: dict[str, Any] = self._make_event_dict(
                    ctx, "task.completed",
                    payload={"tool_name": tool_name, "run_id": ctx.run_id},
                    plain_text="任务处理完成",
                )
                self._publish_event(task_completed_event)
                self._append_to_store(ctx.run_id, task_completed_event)

            return result

        except Exception as exc:
            # 9. 失败 → 发布 tool.failed
            failed_event3: dict[str, Any] = self._make_event_dict(
                ctx, "tool.failed",
                payload={"tool_name": tool_name, "error": str(exc)},
                plain_text=f"工具执行失败：{exc}",
            )
            self._publish_event(failed_event3)
            self._append_to_store(ctx.run_id, failed_event3)

            return StableAgentToolResult(
                ok=False,
                run_id=ctx.run_id,
                tool_call_id=ctx.tool_call_id,
                tool_name=tool_name,
                plain_text=f"工具执行异常：{exc}",
                trace_url=f"/runs/{ctx.run_id}",
                is_error=True,
            )

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _assess_risk(self, tool_name: str, args: dict[str, Any]) -> str:
        """使用安全策略评估工具调用风险。

        优先使用工具 schema 中定义的 risk_level，然后通过
        security_policy 进行二次确认。

        Args:
            tool_name: 工具名称。
            args: 工具参数。

        Returns:
            风险等级字符串（"low"/"medium"/"high"/"forbidden"）。
        """
        schema_risk: str = get_risk_level(tool_name)

        # 如果安全策略可用，使用它进行更细粒度的评估
        if self._security_policy is not None:
            # 构造命令列表用于风险评估（模拟命令方式）
            command_parts: list[str] = [tool_name.replace("stableagent.", "")]
            for key, value in args.items():
                if isinstance(value, str):
                    command_parts.append(value[:50])
            try:
                policy_risk = self._security_policy.classify_command(command_parts)
                # 取更严格的风险等级
                risk_order: dict[str, int] = {"low": 0, "medium": 1, "high": 2, "forbidden": 3}
                if risk_order.get(policy_risk, 0) > risk_order.get(schema_risk, 0):
                    return policy_risk
            except Exception as e:
                logger.warning("安全策略风险评估失败，使用 schema 默认风险等级: %s", e)

        return schema_risk

    # V5.5: 事件 → 重要程度映射
    _IMPORTANCE_MAP: dict[str, str] = {
        "mcp.call.received": "normal",
        "tool.started": "important",
        "tool.completed": "important",
        "tool.failed": "critical",
    }

    # V5.5: 事件 → 阶段映射
    _STAGE_MAP: dict[str, str] = {
        "mcp.call.received": "execution",
        "tool.risk_checked": "execution",
        "tool.started": "execution",
        "tool.completed": "execution",
        "tool.failed": "execution",
        "task.completed": "execution",
        "approval.required": "approval",
    }

    @staticmethod
    def _get_importance(event_type: str) -> str:
        """根据事件类型返回重要程度等级。

        V5.5 新增：事件分级（debug/normal/important/critical）。

        Args:
            event_type: 事件类型字符串。

        Returns:
            importance 等级字符串。
        """
        return ToolRouter._IMPORTANCE_MAP.get(event_type, "normal")

    @staticmethod
    def _get_stage(event_type: str) -> str:
        """根据事件类型返回当前阶段名称。

        V5.5 新增：阶段追踪。

        Args:
            event_type: 事件类型字符串。

        Returns:
            阶段名称字符串。
        """
        return ToolRouter._STAGE_MAP.get(event_type, "execution")

    def _make_event_dict(
        self,
        ctx: RunContext,
        event_type: str,
        payload: dict[str, Any] | None = None,
        plain_text: str = "",
    ) -> dict[str, Any]:
        """构建标准化事件字典。

        Args:
            ctx: RunContext 实例。
            event_type: 事件类型字符串。
            payload: 事件负载数据。
            plain_text: 人类可读文本。

        Returns:
            包含所有标准字段的事件字典。
        """
        child = ctx.child_span()
        return {
            "run_id": ctx.run_id,
            "tool_call_id": ctx.tool_call_id,
            "trace_id": ctx.trace_id,
            "span_id": child.span_id,
            "parent_span_id": ctx.span_id,
            "event_type": event_type,
            "timestamp": time.time(),
            "payload": payload or {},
            "plain_text": plain_text,
            "avatar_state": get_avatar_state(event_type),
            "importance": self._get_importance(event_type),
            "stage": self._get_stage(event_type),
        }

    def _publish_event(self, event_dict: dict[str, Any]) -> None:
        """通过 EventBus 和 EventStream 发布事件。

        Args:
            event_dict: 事件字典。
        """
        # 通过 EventBus 发布
        if self._event_bus is not None:
            try:
                from stable_agent.models import Event
                evt = Event(
                    timestamp=event_dict["timestamp"],
                    type=event_dict["event_type"],
                    payload=event_dict,
                )
                self._event_bus.publish(evt)
            except Exception as e:
                logger.warning("EventBus 发布事件失败: %s", e)

        # 通过 EventStream 发布（使用 publish_sync 线程安全）
        if self._event_stream is not None:
            run_id: str = event_dict.get("run_id", "")
            if run_id:
                try:
                    self._event_stream.publish_sync(run_id, event_dict)
                except Exception as e:
                    logger.exception("事件发布失败: %s", e)

    def _append_to_store(self, run_id: str, event_dict: dict[str, Any]) -> None:
        """将事件追加到 RunStore。

        Args:
            run_id: 运行 ID。
            event_dict: 事件字典。
        """
        if self._run_store is not None:
            try:
                self._run_store.append_event(run_id, event_dict)
            except Exception as e:
                logger.warning("追加事件到 RunStore 失败: %s", e)
