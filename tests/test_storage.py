"""StableAgent OS SQLite 持久化存储单元测试。

使用 tempfile.TemporaryDirectory 创建临时数据库，
测试所有 CRUD 操作、过滤查询和跨实例持久化。
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

import pytest

from stable_agent.models import (
    ApprovalRequest,
    BadCase,
    ContextItem,
    ContextPack,
    EvalCase,
    EvaluationResult,
    MemoryItem,
    RunRecord,
    TaskType,
    TraceSpan,
)
from stable_agent.storage import StableAgentStorage


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def storage() -> StableAgentStorage:
    """创建内存数据库存储实例并初始化。"""
    s = StableAgentStorage(":memory:")
    s.init_db()
    return s


@pytest.fixture
def temp_db_path() -> str:
    """创建临时文件数据库路径。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.sqlite3")
        yield db_path


# ============================================================================
# 初始化测试
# ============================================================================


class TestInitDb:
    """测试数据库初始化。"""

    def test_init_db_creates_tables(self, storage: StableAgentStorage) -> None:
        """验证 init_db 创建所有表。"""
        conn = storage._get_conn()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = {row["name"] for row in tables}
        expected = {
            "runs", "trace_spans", "memory_items", "bad_cases",
            "eval_cases", "context_packs", "approval_requests",
        }
        assert expected.issubset(table_names)

    def test_init_db_idempotent(self, storage: StableAgentStorage) -> None:
        """测试 init_db 可重复调用不报错。"""
        storage.init_db()
        storage.init_db()  # 第二次调用不应报错
        conn = storage._get_conn()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        assert len(tables) >= 7

    def test_file_db_creates_directory(self, temp_db_path: str) -> None:
        """测试文件数据库自动创建 data/ 目录。"""
        s = StableAgentStorage(temp_db_path)
        s.init_db()
        assert Path(temp_db_path).exists()
        assert Path(temp_db_path).parent.exists()


# ============================================================================
# RunRecord 测试
# ============================================================================


class TestRunRecordStorage:
    """测试 RunRecord 持久化操作。"""

    def test_save_and_get_run(self, storage: StableAgentStorage) -> None:
        """测试保存和读取 RunRecord。"""
        record = RunRecord(
            run_id="run-001",
            user_task="修复登录页面崩溃",
            task_type=TaskType.BUG_FIX,
            status="completed",
            total_input_tokens=500,
            total_output_tokens=300,
            overall_score=0.85,
        )
        assert storage.save_run(record) is True

        loaded = storage.get_run("run-001")
        assert loaded is not None
        assert loaded.run_id == "run-001"
        assert loaded.user_task == "修复登录页面崩溃"
        assert loaded.task_type == TaskType.BUG_FIX
        assert loaded.status == "completed"
        assert loaded.total_input_tokens == 500
        assert loaded.overall_score == 0.85

    def test_get_nonexistent_run(self, storage: StableAgentStorage) -> None:
        """测试读取不存在的运行记录返回 None。"""
        assert storage.get_run("nonexistent") is None

    def test_update_run(self, storage: StableAgentStorage) -> None:
        """测试更新运行记录字段。"""
        record = RunRecord(run_id="run-update", user_task="test")
        storage.save_run(record)

        assert storage.update_run("run-update", {"status": "running", "total_input_tokens": 100}) is True

        loaded = storage.get_run("run-update")
        assert loaded is not None
        assert loaded.status == "running"
        assert loaded.total_input_tokens == 100

    def test_list_runs(self, storage: StableAgentStorage) -> None:
        """测试列出运行记录。"""
        for i in range(5):
            record = RunRecord(run_id=f"run-{i:03d}", user_task=f"task {i}")
            storage.save_run(record)
            time.sleep(0.001)  # 确保时间戳不同

        runs = storage.list_runs(limit=3)
        assert len(runs) == 3
        # 应按时间降序
        for i in range(len(runs) - 1):
            assert runs[i].started_at >= runs[i + 1].started_at

    def test_list_runs_empty(self, storage: StableAgentStorage) -> None:
        """测试空数据库返回空列表。"""
        runs = storage.list_runs()
        assert runs == []


# ============================================================================
# TraceSpan 测试
# ============================================================================


class TestTraceSpanStorage:
    """测试 TraceSpan 持久化操作。"""

    def test_save_and_load_spans(self, storage: StableAgentStorage) -> None:
        """测试保存和加载 Span。"""
        span = TraceSpan(
            span_id="span-001",
            run_id="run-001",
            name="LLM Call",
            type="llm_call",
            status="success",
            input_tokens=200,
            output_tokens=150,
            cost_estimate=0.002,
            payload={"model": "gpt-4o"},
            plain_text="Response content",
        )
        assert storage.save_span(span) is True

        spans = storage.load_spans("run-001")
        assert len(spans) == 1
        loaded = spans[0]
        assert loaded.span_id == "span-001"
        assert loaded.name == "LLM Call"
        assert loaded.type == "llm_call"
        assert loaded.status == "success"
        assert loaded.payload["model"] == "gpt-4o"
        assert loaded.plain_text == "Response content"

    def test_load_spans_multiple(self, storage: StableAgentStorage) -> None:
        """测试加载多个 Span。"""
        for i in range(3):
            span = TraceSpan(span_id=f"span-{i:03d}", run_id="run-multi")
            storage.save_span(span)

        spans = storage.load_spans("run-multi")
        assert len(spans) == 3

    def test_load_spans_empty(self, storage: StableAgentStorage) -> None:
        """测试不存在的 run 返回空列表。"""
        spans = storage.load_spans("nonexistent")
        assert spans == []


# ============================================================================
# MemoryItem 测试
# ============================================================================


class TestMemoryItemStorage:
    """测试 MemoryItem 持久化操作。"""

    def test_save_and_load_memory(self, storage: StableAgentStorage) -> None:
        """测试保存和加载记忆条目。"""
        item = MemoryItem(
            id="mem-001",
            content="用户偏好 TypeScript",
            type="user_pref",
            priority=0.9,
            status="active",
            layer="hot",
            lifecycle="active",
            confidence=0.95,
            tags=["typescript", "preference"],
        )
        assert storage.save_memory(item) is True

        results = storage.load_memory(limit=10)
        assert len(results) == 1
        loaded = results[0]
        assert loaded.id == "mem-001"
        assert loaded.layer == "hot"
        assert loaded.tags == ["typescript", "preference"]

    def test_load_memory_filter_status(self, storage: StableAgentStorage) -> None:
        """测试按 status 过滤。"""
        active = MemoryItem(id="mem-a", content="active", type="test", status="active")
        outdated = MemoryItem(id="mem-o", content="outdated", type="test", status="outdated")
        storage.save_memory(active)
        storage.save_memory(outdated)

        results = storage.load_memory(status="active")
        assert len(results) == 1
        assert results[0].id == "mem-a"

    def test_load_memory_filter_layer(self, storage: StableAgentStorage) -> None:
        """测试按 layer 过滤。"""
        hot = MemoryItem(id="mem-h", content="hot", type="test", layer="hot")
        cold = MemoryItem(id="mem-c", content="cold", type="test", layer="cold")
        storage.save_memory(hot)
        storage.save_memory(cold)

        results = storage.load_memory(layer="hot")
        assert len(results) == 1
        assert results[0].id == "mem-h"

    def test_load_memory_filter_lifecycle(self, storage: StableAgentStorage) -> None:
        """测试按 lifecycle 过滤。"""
        active = MemoryItem(id="mem-la", content="active", type="test", lifecycle="active")
        archived = MemoryItem(id="mem-lar", content="archived", type="test", lifecycle="archived")
        storage.save_memory(active)
        storage.save_memory(archived)

        results = storage.load_memory(lifecycle="archived")
        assert len(results) == 1
        assert results[0].id == "mem-lar"

    def test_update_memory_field(self, storage: StableAgentStorage) -> None:
        """测试更新记忆字段。"""
        item = MemoryItem(id="mem-upd", content="test", type="test")
        storage.save_memory(item)

        assert storage.update_memory_field("mem-upd", "priority", 0.99) is True
        assert storage.update_memory_field("mem-upd", "layer", "cold") is True

        results = storage.load_memory(limit=10)
        assert len(results) == 1
        assert results[0].priority == 0.99
        assert results[0].layer == "cold"

    def test_load_memory_empty(self, storage: StableAgentStorage) -> None:
        """测试空数据库返回空列表。"""
        results = storage.load_memory()
        assert results == []


# ============================================================================
# BadCase 测试
# ============================================================================


class TestBadCaseStorage:
    """测试 BadCase 持久化操作。"""

    def test_save_and_load_bad_cases(self, storage: StableAgentStorage) -> None:
        """测试保存和加载负面案例。"""
        evaluation = EvaluationResult(
            completion_rate=0.3,
            overall_score=0.25,
            retrieval_quality=0.4,
            memory_quality=0.5,
            failure_reasons=["insufficient_context"],
            improvement_rules=["add more context"],
        )
        case = BadCase(
            task_type=TaskType.BUG_FIX,
            input_context="修复 NPE",
            output="未能修复",
            evaluation=evaluation,
            failure_reason="上下文不足",
        )
        assert storage.save_bad_case(case) is True

        cases = storage.load_bad_cases(limit=10)
        assert len(cases) == 1
        loaded = cases[0]
        assert loaded.task_type == TaskType.BUG_FIX
        assert loaded.evaluation.overall_score == 0.25
        assert loaded.evaluation.retrieval_quality == 0.4
        assert loaded.evaluation.failure_reasons == ["insufficient_context"]
        assert loaded.evaluation.improvement_rules == ["add more context"]

    def test_load_bad_cases_empty(self, storage: StableAgentStorage) -> None:
        """测试空数据库返回空列表。"""
        cases = storage.load_bad_cases()
        assert cases == []


# ============================================================================
# EvalCase 测试
# ============================================================================


class TestEvalCaseStorage:
    """测试 EvalCase 持久化操作。"""

    def test_append_and_load_eval_cases(self, storage: StableAgentStorage) -> None:
        """测试添加和加载评估用例。"""
        case = EvalCase(
            case_id="eval-001",
            input_task="修复登录页面崩溃",
            expected_behavior="Should fix the crash",
            must_include=["null check", "Optional"],
            must_not_include=["堆栈溢出"],
            source="manual",
            task_type=TaskType.BUG_FIX,
        )
        assert storage.append_eval_case(case) is True

        cases = storage.load_eval_cases(limit=10)
        assert len(cases) == 1
        loaded = cases[0]
        assert loaded.case_id == "eval-001"
        assert loaded.must_include == ["null check", "Optional"]
        assert loaded.must_not_include == ["堆栈溢出"]
        assert loaded.source == "manual"
        assert loaded.task_type == TaskType.BUG_FIX

    def test_load_eval_cases_empty(self, storage: StableAgentStorage) -> None:
        """测试空数据库返回空列表。"""
        cases = storage.load_eval_cases()
        assert cases == []


# ============================================================================
# ContextPack 测试
# ============================================================================


class TestContextPackStorage:
    """测试 ContextPack 持久化操作。"""

    def test_save_and_get_context_pack(self, storage: StableAgentStorage) -> None:
        """测试保存和读取上下文包。"""
        items = [
            ContextItem(
                id="ctx-1", content="Memory item content",
                source_type="memory", priority=0.9,
                relevance_score=0.85, token_estimate=50,
            ),
            ContextItem(
                id="ctx-2", content="RAG document",
                source_type="rag", priority=0.7,
                relevance_score=0.6, token_estimate=100,
            ),
        ]
        pack = ContextPack(
            pack_id="pack-001",
            run_id="run-001",
            task_input="Fix bug",
            task_type=TaskType.BUG_FIX,
            items=items,
            total_tokens=150,
            budget_limit=500,
            critical_reminders=["Check security"],
            compaction_report={"removed": 2},
        )
        assert storage.save_context_pack(pack) is True

        loaded = storage.get_context_pack("pack-001")
        assert loaded is not None
        assert loaded.pack_id == "pack-001"
        assert loaded.task_type == TaskType.BUG_FIX
        assert len(loaded.items) == 2
        assert loaded.items[0].id == "ctx-1"
        assert loaded.items[0].content == "Memory item content"
        assert loaded.items[0].source_type == "memory"
        assert loaded.items[0].relevance_score == 0.85
        assert loaded.items[1].source_type == "rag"
        assert loaded.critical_reminders == ["Check security"]
        assert loaded.compaction_report == {"removed": 2}

    def test_get_context_pack_nonexistent(self, storage: StableAgentStorage) -> None:
        """测试读取不存在的上下文包返回 None。"""
        assert storage.get_context_pack("nonexistent") is None


# ============================================================================
# ApprovalRequest 测试
# ============================================================================


class TestApprovalStorage:
    """测试 ApprovalRequest 持久化操作。"""

    def test_approval_lifecycle(self, storage: StableAgentStorage) -> None:
        """测试审批请求的完整生命周期。"""
        # 创建
        req = ApprovalRequest(
            request_id="appr-001",
            run_id="run-001",
            action="delete_data",
            risk="high",
            reason="Need to clean up",
        )
        assert storage.save_approval(req) is True

        # 列出待审批
        pending = storage.list_pending_approvals()
        assert len(pending) == 1
        assert pending[0].status == "pending"

        # 批准
        assert storage.update_approval("appr-001", "approved") is True

        pending_after = storage.list_pending_approvals()
        assert len(pending_after) == 0

    def test_approval_reject(self, storage: StableAgentStorage) -> None:
        """测试审批拒绝。"""
        req = ApprovalRequest(
            request_id="appr-rej",
            run_id="run-001",
            action="modify_config",
        )
        storage.save_approval(req)

        assert storage.update_approval("appr-rej", "rejected") is True
        pending = storage.list_pending_approvals()
        assert len(pending) == 0

    def test_list_pending_approvals_multiple(self, storage: StableAgentStorage) -> None:
        """测试多个待审批请求的列出。"""
        for i in range(3):
            req = ApprovalRequest(
                request_id=f"appr-{i:03d}",
                run_id="run-001",
                action=f"action_{i}",
            )
            storage.save_approval(req)

        pending = storage.list_pending_approvals()
        assert len(pending) == 3


# ============================================================================
# 跨实例持久化测试
# ============================================================================


class TestPersistenceAcrossInstances:
    """测试跨进程/实例的持久化。"""

    def test_persistence_across_instances(self, temp_db_path: str) -> None:
        """测试重启（新建实例）后数据不丢失。"""
        # 第一个实例写入数据
        s1 = StableAgentStorage(temp_db_path)
        s1.init_db()
        record = RunRecord(run_id="persist-001", user_task="test persistence")
        s1.save_run(record)
        # 关闭连接
        s1.conn.close()

        # 第二个实例读取数据
        s2 = StableAgentStorage(temp_db_path)
        s2.init_db()
        loaded = s2.get_run("persist-001")
        assert loaded is not None
        assert loaded.run_id == "persist-001"
        assert loaded.user_task == "test persistence"
        s2.conn.close()


# ============================================================================
# 空数据库测试
# ============================================================================


class TestEmptyDb:
    """测试空数据库行为。"""

    def test_empty_db_returns_empty(self, storage: StableAgentStorage) -> None:
        """测试空数据库各列表方法返回空。"""
        assert storage.list_runs() == []
        assert storage.load_spans("any") == []
        assert storage.load_memory() == []
        assert storage.load_bad_cases() == []
        assert storage.load_eval_cases() == []
        assert storage.list_pending_approvals() == []

    def test_empty_db_get_returns_none(self, storage: StableAgentStorage) -> None:
        """测试空数据库各 get 方法返回 None。"""
        assert storage.get_run("any") is None
        assert storage.get_context_pack("any") is None
