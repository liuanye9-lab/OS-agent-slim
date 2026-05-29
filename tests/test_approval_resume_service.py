"""测试 ApprovalResumeService (Phase 5+12)。

验证:
1. approve_and_resume 恢复执行
2. reject 拒绝执行
3. 重复 approve/reject 正确处理
"""

import pytest
from stable_agent.approval.pending_tool_store import PendingToolCall, PendingToolStore
from stable_agent.approval.approval_resume_service import ApprovalResumeService


class TestApprovalResumeService:
    """审批恢复服务测试。"""

    def test_approve_not_found(self):
        """审批 ID 不存在时返回错误。"""
        service = ApprovalResumeService()
        result = service.approve_and_resume("nonexistent")
        assert result["ok"] is False
        assert result["status"] == "not_found"

    def test_reject_not_found(self):
        """拒绝不存在的审批返回错误。"""
        service = ApprovalResumeService()
        result = service.reject("nonexistent")
        assert result["ok"] is False
        assert result["status"] == "not_found"

    def test_approve_already_approved(self, tmp_path):
        """重复审批返回错误。"""
        db_path = str(tmp_path / "test.sqlite3")
        store = PendingToolStore(db_path=db_path)
        service = ApprovalResumeService(store=store)

        call = PendingToolCall(
            approval_id="approval_001",
            run_id="run-001",
            tool_name="test.tool",
            args={},
        )
        store.save(call)
        store.mark_approved("approval_001")

        result = service.approve_and_resume("approval_001")
        assert result["ok"] is False
        assert result["status"] == "already_approved"

    def test_approve_already_rejected(self, tmp_path):
        """已拒绝的审批不能 approve。"""
        db_path = str(tmp_path / "test.sqlite3")
        store = PendingToolStore(db_path=db_path)
        service = ApprovalResumeService(store=store)

        call = PendingToolCall(
            approval_id="approval_002",
            run_id="run-002",
            tool_name="test.tool",
            args={},
        )
        store.save(call)
        store.mark_rejected("approval_002")

        result = service.approve_and_resume("approval_002")
        assert result["ok"] is False
        assert result["status"] == "already_rejected"

    def test_reject_success(self, tmp_path):
        """成功拒绝审批。"""
        db_path = str(tmp_path / "test.sqlite3")
        store = PendingToolStore(db_path=db_path)
        service = ApprovalResumeService(store=store)

        call = PendingToolCall(
            approval_id="approval_003",
            run_id="run-003",
            tool_name="test.tool",
            args={},
        )
        store.save(call)

        result = service.reject("approval_003", reason="不安全操作")
        assert result["ok"] is True
        assert result["status"] == "rejected"
        assert result["tool_name"] == "test.tool"
