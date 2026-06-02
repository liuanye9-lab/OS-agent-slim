"""tests/test_observer_replay_api.py — Observer Replay API 测试。

验证 RunStore 持久化和事件回放。
"""

from __future__ import annotations

import os
import tempfile
import pytest

from stable_agent.observation.run_store import RunStore


@pytest.fixture
def store_with_db(tmp_path):
    """创建带 SQLite 持久化的 RunStore。"""
    db_path = str(tmp_path / "test_runs.sqlite")
    return RunStore(db_path=db_path)


@pytest.fixture
def store_memory_only():
    """创建纯内存 RunStore。"""
    return RunStore()


class TestRunStorePersistence:
    """RunStore 持久化测试。"""

    def test_create_run_persists(self, store_with_db):
        """创建 run 后持久化到 SQLite。"""
        store_with_db.create_run("run_001")
        # 从 SQLite 验证
        run_meta = store_with_db._load_run_from_db("run_001")
        assert run_meta is not None
        assert run_meta["status"] == "running"

    def test_append_event_persists(self, store_with_db):
        """追加事件后持久化到 SQLite。"""
        store_with_db.create_run("run_001")
        store_with_db.append_event("run_001", {
            "event_type": "task.received",
            "timestamp": 1000.0,
        })
        # 从 SQLite 验证
        events = store_with_db._load_events_from_db("run_001")
        assert len(events) == 1
        assert events[0]["event_type"] == "task.received"

    def test_mark_completed_persists(self, store_with_db):
        """标记完成后持久化到 SQLite。"""
        store_with_db.create_run("run_001")
        store_with_db.mark_completed("run_001")
        run_meta = store_with_db._load_run_from_db("run_001")
        assert run_meta["status"] == "completed"

    def test_get_events_from_db(self, store_with_db):
        """从 SQLite 回放事件。"""
        store_with_db.create_run("run_001")
        store_with_db.append_event("run_001", {"event_type": "task.received", "timestamp": 1000.0})
        store_with_db.append_event("run_001", {"event_type": "task.completed", "timestamp": 2000.0})

        # 清空内存缓存
        store_with_db._runs.clear()

        # 从 SQLite 回放
        events = store_with_db.get_events("run_001")
        assert len(events) == 2
        assert events[0]["event_type"] == "task.received"
        assert events[1]["event_type"] == "task.completed"

    def test_get_events_empty_when_not_exists(self, store_with_db):
        """不存在的 run 返回空列表。"""
        events = store_with_db.get_events("run_nonexistent")
        assert events == []


class TestRunStoreMemoryOnly:
    """纯内存 RunStore 测试。"""

    def test_create_run(self, store_memory_only):
        """创建 run。"""
        store_memory_only.create_run("run_001")
        assert "run_001" in store_memory_only._runs

    def test_append_event(self, store_memory_only):
        """追加事件。"""
        store_memory_only.create_run("run_001")
        store_memory_only.append_event("run_001", {"event_type": "task.received"})
        events = store_memory_only.get_events("run_001")
        assert len(events) == 1

    def test_mark_completed(self, store_memory_only):
        """标记完成。"""
        store_memory_only.create_run("run_001")
        store_memory_only.mark_completed("run_001")
        status = store_memory_only.get_run_status("run_001")
        assert status["status"] == "completed"


class TestObserverReplayScenario:
    """Observer 回放场景测试。"""

    def test_completed_run_can_be_replayed(self, store_with_db):
        """已完成的 run 可以被回放。"""
        # 模拟 run 执行
        store_with_db.create_run("run_001")
        store_with_db.append_event("run_001", {"event_type": "task.received", "progress_pct": 0})
        store_with_db.append_event("run_001", {"event_type": "intent.parsed", "progress_pct": 10})
        store_with_db.append_event("run_001", {"event_type": "context.budgeted", "progress_pct": 20})
        store_with_db.append_event("run_001", {"event_type": "eval.completed", "progress_pct": 80})
        store_with_db.append_event("run_001", {"event_type": "task.completed", "progress_pct": 100})
        store_with_db.mark_completed("run_001")

        # 清空内存 (模拟页面刷新)
        store_with_db._runs.clear()

        # 回放
        events = store_with_db.get_events("run_001")
        assert len(events) == 5
        assert events[-1]["event_type"] == "task.completed"
        assert events[-1]["progress_pct"] == 100

        # 状态
        status = store_with_db.get_run_status("run_001")
        assert status is not None
        assert status["status"] == "completed"
        assert status["event_count"] == 5
