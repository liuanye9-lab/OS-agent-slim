"""tests.test_cloud_task_queue — 任务队列测试。"""

import os
import pytest
from stable_agent.cloud.task_queue import TaskQueue, TaskRecord


class TestTaskQueue:
    """任务队列测试。"""

    def setup_method(self):
        self.db_path = "/tmp/test_task_queue.sqlite"
        self.queue = TaskQueue(db_path=self.db_path, max_logs_per_task=10)

    def teardown_method(self):
        self.queue.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_create_task(self):
        """可以创建任务。"""
        task = self.queue.create_task(task_input="test task", title="Test")
        assert task.task_id.startswith("task_")
        assert task.run_id.startswith("run_")
        assert task.status == "queued"
        assert task.task_input == "test task"

    def test_get_task(self):
        """可以获取任务。"""
        task = self.queue.create_task(task_input="get test")
        retrieved = self.queue.get_task(task.task_id)
        assert retrieved is not None
        assert retrieved.task_id == task.task_id
        assert retrieved.task_input == "get test"

    def test_list_tasks(self):
        """可以列出任务。"""
        for i in range(5):
            self.queue.create_task(task_input=f"task {i}")
        tasks = self.queue.list_tasks(limit=10)
        assert len(tasks) == 5

    def test_update_status(self):
        """可以更新任务状态。"""
        task = self.queue.create_task(task_input="status test")
        self.queue.update_status(task.task_id, "running")
        updated = self.queue.get_task(task.task_id)
        assert updated.status == "running"

    def test_assign_task(self):
        """可以分配任务。"""
        task = self.queue.create_task(task_input="assign test")
        self.queue.assign_task(task.task_id, "worker_1")
        updated = self.queue.get_task(task.task_id)
        assert updated.status == "assigned"
        assert updated.assigned_worker_id == "worker_1"

    def test_append_log(self):
        """可以追加日志。"""
        task = self.queue.create_task(task_input="log test")
        self.queue.append_log(task.task_id, "log entry 1")
        self.queue.append_log(task.task_id, "log entry 2")
        retrieved = self.queue.get_task(task.task_id)
        assert len(retrieved.logs) == 2

    def test_log_truncation(self):
        """日志超过限制时自动裁剪。"""
        task = self.queue.create_task(task_input="trunc test")
        for i in range(20):
            self.queue.append_log(task.task_id, f"log {i}")
        retrieved = self.queue.get_task(task.task_id)
        assert len(retrieved.logs) <= 10  # max_logs_per_task=10

    def test_get_queued_tasks(self):
        """可以获取待分配任务。"""
        self.queue.create_task(task_input="q1")
        task2 = self.queue.create_task(task_input="q2")
        self.queue.assign_task(task2.task_id, "w1")
        queued = self.queue.get_queued_tasks()
        assert len(queued) == 1
        assert queued[0].task_input == "q1"

    def test_to_dict(self):
        """to_dict 返回正确结构。"""
        task = self.queue.create_task(task_input="dict test")
        d = task.to_dict()
        assert "task_id" in d
        assert "run_id" in d
        assert "status" in d
        assert "priority" in d
