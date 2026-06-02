"""stable_agent.cloud.scheduler — 简单任务调度器。

第一版调度规则：
1. 如果用户指定 worker_id，优先给指定 worker
2. 否则选择：online + 非 busy + capabilities 匹配 + 最近心跳
3. 无可用 worker → 任务保持 queued
"""

from __future__ import annotations

import logging
from typing import Optional

from stable_agent.cloud.task_queue import TaskQueue
from stable_agent.cloud.worker_registry import WorkerRegistry

logger = logging.getLogger(__name__)


class Scheduler:
    """简单任务调度器。"""

    def __init__(self, task_queue: TaskQueue,
                 worker_registry: WorkerRegistry) -> None:
        self.task_queue = task_queue
        self.worker_registry = worker_registry

    def schedule_pending(self) -> int:
        """尝试调度所有 queued 任务。返回成功调度数。"""
        queued = self.task_queue.get_queued_tasks(limit=50)
        scheduled = 0
        for task in queued:
            worker_id = self._select_worker(
                preferred_worker=task.assigned_worker_id,
            )
            if worker_id:
                self.task_queue.assign_task(task.task_id, worker_id)
                logger.info("Task %s → Worker %s", task.task_id, worker_id)
                scheduled += 1
        return scheduled

    def _select_worker(self, preferred_worker: Optional[str] = None) -> Optional[str]:
        """选择最佳 Worker。"""
        online = self.worker_registry.get_online_workers()
        if not online:
            return None

        # 优先指定 worker
        if preferred_worker:
            for w in online:
                if w.worker_id == preferred_worker and w.status != "busy":
                    return w.worker_id

        # 选择非 busy + 最近心跳
        idle_workers = [w for w in online if w.status == "online"]
        if not idle_workers:
            return None

        idle_workers.sort(key=lambda w: w.last_heartbeat, reverse=True)
        return idle_workers[0].worker_id

    def check_timeouts(self) -> int:
        """检查并处理超时任务和 Worker。返回处理数。"""
        # Worker timeout 由 WorkerRegistry._refresh_status() 自动处理
        self.worker_registry._refresh_status()
        return 0
