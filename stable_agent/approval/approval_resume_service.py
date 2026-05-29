"""ApprovalResumeService — 审批通过后恢复执行被阻断的工具调用。

核心闭环：
1. 高风险工具被阻断 → PendingToolCall 保存
2. 用户在 Review 面板 approve → ApprovalResumeService.approve_and_resume()
3. 恢复原始 handler 执行 → 返回真实结果
4. 用户 reject → 标记为 rejected，不执行
"""

from __future__ import annotations

import logging
from typing import Any

from stable_agent.approval.pending_tool_store import PendingToolCall, PendingToolStore
from stable_agent.gateway.tool_router import StableAgentToolResult

logger = logging.getLogger(__name__)


class ApprovalResumeService:
    """审批恢复服务：approve 后恢复执行，reject 后拒绝。"""

    def __init__(
        self,
        store: PendingToolStore | None = None,
        tool_router: Any = None,
    ) -> None:
        self._store: PendingToolStore = store or PendingToolStore()
        self._tool_router: Any = tool_router

    def approve_and_resume(
        self,
        approval_id: str,
        reviewer: str = "admin",
    ) -> dict[str, Any]:
        """审批通过：恢复执行原始工具调用。

        Returns:
            dict 含 {ok, status, approval_id, result} 供 MCP 工具返回。
        """
        call = self._store.get(approval_id)
        if call is None:
            return {
                "ok": False,
                "status": "not_found",
                "approval_id": approval_id,
                "error": f"审批 ID {approval_id} 不存在或已过期",
            }

        if call.status == "approved":
            return {
                "ok": False,
                "status": "already_approved",
                "approval_id": approval_id,
                "error": f"审批 {approval_id} 已通过，不能重复执行",
            }

        if call.status == "rejected":
            return {
                "ok": False,
                "status": "already_rejected",
                "approval_id": approval_id,
                "error": f"审批 {approval_id} 已被拒绝，不能执行",
            }

        # 标记为 approved
        self._store.mark_approved(approval_id)

        # 恢复执行原始工具
        if self._tool_router is None:
            return {
                "ok": True,
                "status": "approved_no_resume",
                "approval_id": approval_id,
                "warning": "ToolRouter 未连接，审批已通过但无法恢复执行",
            }

        try:
            # 重新调用工具（绕过审批检查）
            result: StableAgentToolResult = self._tool_router.route_resume(
                tool_name=call.tool_name,
                args=call.args,
                run_id=call.run_id,
                workspace_id=call.workspace_id,
                project_id=call.project_id,
                approval_id=approval_id,
            )
            return {
                "ok": True,
                "status": "executed",
                "approval_id": approval_id,
                "tool_name": call.tool_name,
                "result": {
                    "ok": result.ok,
                    "plain_text_zh": result.plain_text_zh or result.plain_text,
                    "data": result.data,
                    "run_id": result.run_id,
                },
            }
        except Exception as exc:
            logger.exception("审批恢复执行失败: %s", exc)
            return {
                "ok": False,
                "status": "execution_failed",
                "approval_id": approval_id,
                "error": f"恢复执行失败: {exc}",
            }

    def reject(
        self,
        approval_id: str,
        reason: str = "",
        reviewer: str = "admin",
    ) -> dict[str, Any]:
        """审批拒绝：永久拒绝，不执行。"""
        call = self._store.get(approval_id)
        if call is None:
            return {
                "ok": False,
                "status": "not_found",
                "approval_id": approval_id,
                "error": f"审批 ID {approval_id} 不存在或已过期",
            }

        self._store.mark_rejected(approval_id)
        return {
            "ok": True,
            "status": "rejected",
            "approval_id": approval_id,
            "tool_name": call.tool_name,
            "reason": reason or "已被审核拒绝",
        }
