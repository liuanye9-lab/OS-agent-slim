"""tests.test_worker_registry — Worker 注册表测试。"""

import os
import time
import pytest
from stable_agent.cloud.worker_registry import WorkerRegistry, WorkerRecord


class TestWorkerRegistry:
    """Worker 注册表测试。"""

    def setup_method(self):
        self.db_path = "/tmp/test_worker_registry.sqlite"
        self.registry = WorkerRegistry(db_path=self.db_path, worker_timeout=5)

    def teardown_method(self):
        self.registry.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_register_worker(self):
        """可以注册 Worker。"""
        worker = self.registry.register(
            worker_id="macbook_pro",
            name="MacBook Pro",
            machine_type="macos",
            capabilities=["coding", "shell"],
        )
        assert worker.worker_id == "macbook_pro"
        assert worker.name == "MacBook Pro"
        assert worker.status == "online"
        assert "coding" in worker.capabilities

    def test_heartbeat(self):
        """可以更新心跳。"""
        self.registry.register(worker_id="w1", name="W1")
        ok = self.registry.heartbeat("w1")
        assert ok is True

    def test_get_worker(self):
        """可以获取 Worker。"""
        self.registry.register(worker_id="w2", name="W2")
        worker = self.registry.get_worker("w2")
        assert worker is not None
        assert worker.worker_id == "w2"

    def test_list_workers(self):
        """可以列出 Workers。"""
        self.registry.register(worker_id="w3", name="W3")
        self.registry.register(worker_id="w4", name="W4")
        workers = self.registry.list_workers()
        assert len(workers) == 2

    def test_set_busy(self):
        """可以设置忙碌状态。"""
        self.registry.register(worker_id="w5", name="W5")
        self.registry.set_busy("w5", "task_1")
        worker = self.registry.get_worker("w5")
        assert worker.status == "busy"
        assert worker.current_task_id == "task_1"

    def test_set_idle(self):
        """可以设置空闲状态。"""
        self.registry.register(worker_id="w6", name="W6")
        self.registry.set_busy("w6", "task_2")
        self.registry.set_idle("w6")
        worker = self.registry.get_worker("w6")
        assert worker.status == "online"
        assert worker.current_task_id is None

    def test_worker_timeout(self):
        """超时后 Worker 变为 offline。"""
        self.registry.register(worker_id="w7", name="W7")
        # 伪造旧心跳
        conn = self.registry._get_conn()
        conn.execute(
            "UPDATE cloud_workers SET last_heartbeat = ? WHERE worker_id = ?",
            (time.time() - 100, "w7"),
        )
        conn.commit()
        # 刷新状态
        self.registry._refresh_status()
        worker = self.registry.get_worker("w7")
        assert worker.status == "offline"

    def test_online_count(self):
        """在线计数正确。"""
        self.registry.register(worker_id="w8", name="W8")
        self.registry.register(worker_id="w9", name="W9")
        assert self.registry.online_count() == 2
