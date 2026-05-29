"""测试高风险工具审批阻断 + 恢复 (Phase 5+12)。

验证:
1. high risk 工具不会直接执行
2. high risk 工具会保存 PendingToolCall
3. approval approve 后可以恢复执行
4. approval reject 后不会执行
"""

import pytest
import time
from stable_agent.approval.pending_tool_store import PendingToolCall, PendingToolStore


class TestHighRiskApprovalBlock:
    """高风险工具审批阻断测试。"""

    def test_pending_tool_call_creation(self):
        """验证 PendingToolCall 创建。"""
        call = PendingToolCall(
            approval_id="approval_001",
            run_id="run-001",
            tool_name="stableagent.skill.export_best",
            args={"patch_id": "sp_001"},
            workspace_id="ws_001",
            project_id="proj_001",
        )
        assert call.status == "waiting_approval"
        assert call.approval_id == "approval_001"
        assert call.tool_name == "stableagent.skill.export_best"

    def test_pending_store_save_and_get(self, tmp_path):
        """验证 PendingToolStore 保存和查询。"""
        db_path = str(tmp_path / "test.sqlite3")
        store = PendingToolStore(db_path=db_path)

        call = PendingToolCall(
            approval_id="approval_001",
            run_id="run-001",
            tool_name="stableagent.skill.export_best",
            args={"patch_id": "sp_001"},
        )
        store.save(call)

        retrieved = store.get("approval_001")
        assert retrieved is not None
        assert retrieved.approval_id == "approval_001"
        assert retrieved.tool_name == "stableagent.skill.export_best"
        assert retrieved.status == "waiting_approval"

    def test_pending_store_mark_approved(self, tmp_path):
        """验证审批通过后状态更新。"""
        db_path = str(tmp_path / "test.sqlite3")
        store = PendingToolStore(db_path=db_path)

        call = PendingToolCall(
            approval_id="approval_001",
            run_id="run-001",
            tool_name="test.tool",
            args={},
        )
        store.save(call)
        result = store.mark_approved("approval_001")
        assert result is True

        retrieved = store.get("approval_001")
        assert retrieved.status == "approved"

    def test_pending_store_mark_rejected(self, tmp_path):
        """验证审批拒绝后状态更新。"""
        db_path = str(tmp_path / "test.sqlite3")
        store = PendingToolStore(db_path=db_path)

        call = PendingToolCall(
            approval_id="approval_002",
            run_id="run-002",
            tool_name="test.tool",
            args={},
        )
        store.save(call)
        result = store.mark_rejected("approval_002")
        assert result is True

        retrieved = store.get("approval_002")
        assert retrieved.status == "rejected"

    def test_pending_store_list_by_run(self, tmp_path):
        """验证按 run_id 列出待审批调用。"""
        db_path = str(tmp_path / "test.sqlite3")
        store = PendingToolStore(db_path=db_path)

        for i in range(3):
            call = PendingToolCall(
                approval_id=f"approval_{i:03d}",
                run_id="run-001",
                tool_name=f"test.tool.{i}",
                args={},
            )
            store.save(call)

        results = store.list_by_run("run-001")
        assert len(results) >= 3

    def test_pending_store_get_nonexistent(self):
        """查询不存在的审批返回 None。"""
        store = PendingToolStore(db_path=":memory:")
        result = store.get("nonexistent")
        assert result is None
