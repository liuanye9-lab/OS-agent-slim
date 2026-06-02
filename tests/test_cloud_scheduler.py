"""tests.test_cloud_scheduler — 调度器测试。"""

import os
import time
import pytest
from stable_agent.cloud.task_queue import TaskQueue
from stable_agent.cloud.worker_registry import WorkerRegistry
from stable_agent.cloud.scheduler import Scheduler


class TestScheduler:
    """调度器测试。"""

    def setup_method(self):
        self.db_path = "/tmp/test_scheduler.sqlite"
        self.tq = TaskQueue(db_path=self.db_path)
        self.wr = WorkerRegistry(db_path=self.db_path, worker_timeout=60)
        self.scheduler = Scheduler(self.tq, self.wr)

    def teardown_method(self):
        self.tq.close()
        self.wr.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_schedule_to_online_worker(self):
        """有在线 Worker 时，任务自动分配。"""
        self.wr.register(worker_id="w1", name="W1")
        task = self.tq.create_task(task_input="test")
        scheduled = self.scheduler.schedule_pending()
        assert scheduled == 1
        updated = self.tq.get_task(task.task_id)
        assert updated.status == "assigned"
        assert updated.assigned_worker_id == "w1"

    def test_no_worker_keeps_queued(self):
        """无可用 Worker 时，任务保持 queued。"""
        task = self.tq.create_task(task_input="test")
        scheduled = self.scheduler.schedule_pending()
        assert scheduled == 0
        updated = self.tq.get_task(task.task_id)
        assert updated.status == "queued"

    def test_preferred_worker(self):
        """优先使用指定 Worker。"""
        self.wr.register(worker_id="w1", name="W1")
        self.wr.register(worker_id="w2", name="W2")
        task = self.tq.create_task(task_input="test", worker_id="w2")
        self.scheduler.schedule_pending()
        updated = self.tq.get_task(task.task_id)
        assert updated.assigned_worker_id == "w2"

    def test_busy_worker_skipped(self):
        """忙碌 Worker 被跳过。"""
        self.wr.register(worker_id="w1", name="W1")
        self.wr.set_busy("w1", "other_task")
        task = self.tq.create_task(task_input="test")
        scheduled = self.scheduler.schedule_pending()
        assert scheduled == 0

    def test_schedule_multiple_tasks(self):
        """多个任务依次分配。"""
        self.wr.register(worker_id="w1", name="W1")
        t1 = self.tq.create_task(task_input="t1")
        t2 = self.tq.create_task(task_input="t2")
        # 第一个任务分配后 w1 变 busy，第二个保持 queued
        scheduled = self.scheduler.schedule_pending()
        assert scheduled >= 1

    def test_check_timeouts(self):
        """check_timeouts 不会抛异常。"""
        result = self.scheduler.check_timeouts()
        assert isinstance(result, int)
