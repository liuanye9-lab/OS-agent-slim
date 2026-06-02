"""stable_agent.cloud.control_center — OpenClaw Control Center。

核心中枢：接收任务、调度分发、记录事件、提供数据。
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from stable_agent.cloud.config import CloudConfig, get_cloud_config
from stable_agent.cloud.event_store import EventRecord, EventStore
from stable_agent.cloud.task_queue import TaskQueue, TaskRecord
from stable_agent.cloud.worker_registry import WorkerRegistry, WorkerRecord
from stable_agent.cloud.scheduler import Scheduler

logger = logging.getLogger(__name__)


class ControlCenter:
    """OpenClaw Control Center — 云端中枢。

    职责：
    1. 接收任务 (来自 MCP / CLI / Dashboard)
    2. 调度分发到 Worker
    3. 记录事件
    4. 回收结果
    5. 给 Dashboard 提供数据
    """

    def __init__(self, config: Optional[CloudConfig] = None) -> None:
        self.config = config or get_cloud_config()
        db_path = self.config.db_path

        self.event_store = EventStore(db_path=db_path, max_events=self.config.max_events)
        self.task_queue = TaskQueue(db_path=db_path, max_logs_per_task=self.config.max_task_logs)
        self.worker_registry = WorkerRegistry(db_path=db_path, worker_timeout=self.config.worker_timeout)
        self.scheduler = Scheduler(self.task_queue, self.worker_registry)

    # ------------------------------------------------------------------
    # 任务管理
    # ------------------------------------------------------------------

    def submit_task(self, task_input: str, title: str = "",
                    priority: int = 5, worker_id: Optional[str] = None,
                    source: str = "mcp", run_id: str = "") -> TaskRecord:
        """提交任务。"""
        task = self.task_queue.create_task(
            task_input=task_input, title=title,
            priority=priority, worker_id=worker_id,
            source=source, run_id=run_id,
        )
        # 记录事件
        self.event_store.append(EventRecord(
            run_id=task.run_id, task_id=task.task_id,
            event_type="task.received",
            payload={"source": source, "priority": priority},
        ))
        # 尝试调度
        self.scheduler.schedule_pending()
        return task

    def get_task(self, task_id: str) -> Optional[TaskRecord]:
        return self.task_queue.get_task(task_id)

    def list_tasks(self, status: Optional[str] = None,
                   limit: int = 50) -> list[TaskRecord]:
        return self.task_queue.list_tasks(status=status, limit=limit)

    def cancel_task(self, task_id: str) -> bool:
        task = self.task_queue.get_task(task_id)
        if not task:
            return False
        if task.status in ("completed", "failed", "cancelled"):
            return False
        self.task_queue.update_status(task_id, "cancelled")
        self.event_store.append(EventRecord(
            run_id=task.run_id, task_id=task_id,
            event_type="task.cancelled",
        ))
        return True

    # ------------------------------------------------------------------
    # Worker 管理
    # ------------------------------------------------------------------

    def register_worker(self, worker_id: str, name: str = "",
                        machine_type: str = "linux",
                        capabilities: list[str] | None = None) -> WorkerRecord:
        worker = self.worker_registry.register(
            worker_id=worker_id, name=name,
            machine_type=machine_type, capabilities=capabilities,
        )
        self.event_store.append(EventRecord(
            worker_id=worker_id, event_type="worker.registered",
            payload={"name": name, "capabilities": capabilities},
        ))
        return worker

    def worker_heartbeat(self, worker_id: str) -> bool:
        return self.worker_registry.heartbeat(worker_id)

    def list_workers(self) -> list[WorkerRecord]:
        return self.worker_registry.list_workers()

    def get_worker_status(self, worker_id: str) -> Optional[WorkerRecord]:
        return self.worker_registry.get_worker(worker_id)

    # ------------------------------------------------------------------
    # 任务执行回调
    # ------------------------------------------------------------------

    def task_started(self, worker_id: str, task_id: str) -> bool:
        task = self.task_queue.get_task(task_id)
        if not task:
            return False
        self.task_queue.update_status(task_id, "running")
        self.worker_registry.set_busy(worker_id, task_id)
        self.event_store.append(EventRecord(
            run_id=task.run_id, task_id=task_id, worker_id=worker_id,
            event_type="worker.started",
        ))
        return True

    def task_log(self, worker_id: str, task_id: str, message: str) -> bool:
        self.task_queue.append_log(task_id, message)
        task = self.task_queue.get_task(task_id)
        self.event_store.append(EventRecord(
            run_id=task.run_id if task else "", task_id=task_id,
            worker_id=worker_id, event_type="worker.log",
            payload={"message": message[:500]},
        ))
        return True

    def task_completed(self, worker_id: str, task_id: str,
                       result: str = "") -> bool:
        self.task_queue.update_status(task_id, "completed", result=result)
        self.worker_registry.set_idle(worker_id)
        task = self.task_queue.get_task(task_id)
        self.event_store.append(EventRecord(
            run_id=task.run_id if task else "", task_id=task_id,
            worker_id=worker_id, event_type="task.completed",
        ))
        # 调度下一个任务
        self.scheduler.schedule_pending()
        return True

    def task_failed(self, worker_id: str, task_id: str,
                    error: str = "") -> bool:
        self.task_queue.update_status(task_id, "failed", error=error)
        self.worker_registry.set_idle(worker_id)
        task = self.task_queue.get_task(task_id)
        self.event_store.append(EventRecord(
            run_id=task.run_id if task else "", task_id=task_id,
            worker_id=worker_id, event_type="task.failed",
            payload={"error": error[:500]},
        ))
        return True

    # ------------------------------------------------------------------
    # 数据查询
    # ------------------------------------------------------------------

    def get_events(self, run_id: str = "", task_id: str = "",
                   limit: int = 100) -> list[dict[str, Any]]:
        events = self.event_store.query(
            run_id=run_id, task_id=task_id, limit=limit,
        )
        return [e.to_dict() for e in events]

    def get_next_task(self, worker_id: str) -> Optional[TaskRecord]:
        """获取分配给 worker 的下一个任务。"""
        # 先检查已有 assigned 任务
        tasks = self.task_queue.get_worker_tasks(worker_id)
        for t in tasks:
            if t.status == "assigned":
                return t
        # 尝试调度
        self.scheduler.schedule_pending()
        tasks = self.task_queue.get_worker_tasks(worker_id)
        for t in tasks:
            if t.status == "assigned":
                return t
        return None

    def health(self) -> dict[str, Any]:
        """健康检查。"""
        online = self.worker_registry.online_count()
        queued = len(self.task_queue.list_tasks(status="queued", limit=1000))
        running = len(self.task_queue.list_tasks(status="running", limit=1000))
        return {
            "ok": True,
            "profile": self.config.profile,
            "server_role": "control_center",
            "workers_online": online,
            "queued_tasks": queued,
            "running_tasks": running,
            "total_events": self.event_store.count(),
        }

    def close(self) -> None:
        self.event_store.close()
        self.task_queue.close()
        self.worker_registry.close()
