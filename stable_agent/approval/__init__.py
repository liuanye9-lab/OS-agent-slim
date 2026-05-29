"""StableAgent Approval Module — 高风险工具审批与恢复执行。"""

import sys
import os

# Production Hardening: Approval Resume 模块
from stable_agent.approval.pending_tool_store import PendingToolCall, PendingToolStore
from stable_agent.approval.approval_resume_service import ApprovalResumeService

# Backward compat: 旧审批管理器 (approval.py → 当前包)
# Python 的模块查找机制：stable_agent.approval 目录优先于 approval.py
# 我们将旧模块的类重新导出，保持 orchestrator 兼容
_old_approval_path = os.path.join(os.path.dirname(__file__), "..", "approval.py")
if os.path.exists(_old_approval_path):
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "stable_agent.approval._legacy", _old_approval_path
        )
        if spec and spec.loader:
            _legacy = importlib.util.module_from_spec(spec)
            sys.modules["stable_agent.approval._legacy"] = _legacy
            spec.loader.exec_module(_legacy)
            ApprovalManager = _legacy.ApprovalManager
            ApprovalRequest = _legacy.ApprovalRequest
            ApprovalStatus = _legacy.ApprovalStatus
            RiskLevel = _legacy.RiskLevel
    except Exception:
        # Fallback: 创建占位 ApprovalManager
        from dataclasses import dataclass
        from typing import Optional

        @dataclass
        class _PlaceholderRequest:
            request_id: str = ""
            status: str = "pending"
            resolved_at: float = 0.0

        class ApprovalManager:
            def create_request(self, **kw) -> _PlaceholderRequest:
                import uuid
                return _PlaceholderRequest(request_id=uuid.uuid4().hex[:12])

            def approve(self, request_id: str) -> _PlaceholderRequest:
                return _PlaceholderRequest(request_id=request_id, status="approved", resolved_at=0.0)

            def reject(self, request_id: str, reason: str = "") -> _PlaceholderRequest:
                return _PlaceholderRequest(request_id=request_id, status="rejected", resolved_at=0.0)

        ApprovalRequest = _PlaceholderRequest
        ApprovalStatus = None
        RiskLevel = None

__all__ = [
    "PendingToolCall", "PendingToolStore", "ApprovalResumeService",
    "ApprovalManager", "ApprovalRequest",
]
