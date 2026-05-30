"""test_approval_resume — 测试 high risk 工具审批恢复闭环。"""
import pytest

try:
    from stable_agent.approval.pending_tool_store import PendingToolCall, PendingToolStore
    from stable_agent.approval.approval_resume_service import ApprovalResumeService
    MODULE_AVAILABLE = True
except ImportError:
    MODULE_AVAILABLE = False


@pytest.mark.skipif(not MODULE_AVAILABLE, reason="Approval resume module not importable")
class TestPendingToolStore:
    """PendingToolStore 测试。"""

    def setup_method(self):
        self.store = PendingToolStore(db_path=":memory:")  # 使用内存 SQLite

    def test_save_and_get(self):
        """保存后可获取。"""
        call = PendingToolCall(
            approval_id="appr-001",
            run_id="run-001",
            tool_name="delete_file",
            args={"path": "/test"},
        )
        self.store.save(call)
        retrieved = self.store.get("appr-001")
        assert retrieved is not None
        assert retrieved.tool_name == "delete_file"

    def test_mark_approved(self):
        """标记 approved。"""
        call = PendingToolCall(
            approval_id="appr-002",
            run_id="run-001",
            tool_name="test",
            args={},
        )
        self.store.save(call)
        assert self.store.mark_approved("appr-002")
        retrieved = self.store.get("appr-002")
        assert retrieved.status == "approved"

    def test_mark_rejected(self):
        """标记 rejected。"""
        call = PendingToolCall(
            approval_id="appr-003",
            run_id="run-001",
            tool_name="test",
            args={},
        )
        self.store.save(call)
        assert self.store.mark_rejected("appr-003")
        retrieved = self.store.get("appr-003")
        assert retrieved.status == "rejected"

    def test_list_by_run(self):
        """按 run_id 过滤。"""
        self.store.save(PendingToolCall(approval_id="a1", run_id="run-A", tool_name="t1", args={}))
        self.store.save(PendingToolCall(approval_id="a2", run_id="run-B", tool_name="t2", args={}))
        results = self.store.list_by_run("run-A")
        assert len(results) >= 1
        assert results[0].approval_id == "a1"

    def test_get_nonexistent(self):
        """不存在的 ID 返回 None。"""
        assert self.store.get("nonexistent") is None


@pytest.mark.skipif(not MODULE_AVAILABLE, reason="Approval resume module not importable")
class TestApprovalResumeService:
    """ApprovalResumeService 测试。"""

    def setup_method(self):
        self.store = PendingToolStore(db_path=":memory:")
        self.service = ApprovalResumeService(store=self.store)

    def test_reject(self):
        """拒绝后不应执行。"""
        call = PendingToolCall(
            approval_id="appr-reject",
            run_id="run-001",
            tool_name="rm_file",
            args={"path": "/test"},
        )
        self.store.save(call)
        result = self.service.reject("appr-reject", reason="安全风险")
        assert result["ok"] is True
        assert result["status"] == "rejected"

    def test_approve_nonexistent(self):
        """审批不存在的 ID。"""
        result = self.service.approve_and_resume("nonexistent")
        assert result["ok"] is False
        assert result["status"] == "not_found"

    def test_approve_without_tool_router(self):
        """无 ToolRouter 时审批通过但不执行。"""
        call = PendingToolCall(
            approval_id="appr-norouter",
            run_id="run-001",
            tool_name="test",
            args={},
        )
        self.store.save(call)
        result = self.service.approve_and_resume("appr-norouter")
        assert result["ok"] is True
        assert "warning" in result
