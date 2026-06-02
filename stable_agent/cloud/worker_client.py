"""stable_agent.cloud.worker_client — 本地 Worker Agent 客户端。

运行在用户本地电脑上，向云端 Control Center 注册、心跳、拉取任务。
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
import urllib.request
from typing import Any, Optional

logger = logging.getLogger(__name__)

# 安全 Shell 命令白名单
SAFE_SHELL_COMMANDS = {
    "pwd", "ls", "cat", "echo", "date", "whoami", "hostname",
    "git status", "git diff", "git log", "git branch",
    "npm test", "npm run build",
    "python -m pytest", "pytest",
    "node -v", "python --version", "python3 --version",
}

# 危险命令黑名单
DANGEROUS_PATTERNS = [
    "rm -rf", "rm -rf /", "sudo", "shutdown", "reboot", "mkfs",
    "chmod -R 777", "curl | sh", "curl|sh", "wget | sh", "> /dev/",
    "dd if=", ":(){ :|:& };:", "mv / ", "rm -f /",
]


class WorkerClient:
    """本地 Worker Agent。"""

    def __init__(self, server_url: str, worker_id: str,
                 name: str = "", machine_type: str = "macos",
                 capabilities: list[str] | None = None,
                 poll_interval: int = 5,
                 allow_shell: bool = False,
                 token: str = "") -> None:
        self.server_url = server_url.rstrip("/")
        self.worker_id = worker_id
        self.name = name or worker_id
        self.machine_type = machine_type
        self.capabilities = capabilities or ["coding", "shell"]
        self.poll_interval = poll_interval
        self.allow_shell = allow_shell
        self.token = token
        self._running = False

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _http_post(self, path: str, body: dict) -> dict:
        url = f"{self.server_url}{path}"
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, method="POST", headers=self._headers(),
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _http_get(self, path: str) -> dict:
        url = f"{self.server_url}{path}"
        req = urllib.request.Request(url, headers=self._headers())
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def register(self) -> bool:
        """向云端注册。"""
        try:
            result = self._http_post("/api/workers/register", {
                "worker_id": self.worker_id,
                "name": self.name,
                "machine_type": self.machine_type,
                "capabilities": self.capabilities,
            })
            logger.info("Registered: %s", result.get("ok", False))
            return result.get("ok", False)
        except Exception as exc:
            logger.error("Registration failed: %s", exc)
            return False

    def heartbeat(self) -> bool:
        """发送心跳。"""
        try:
            result = self._http_post(
                f"/api/workers/{self.worker_id}/heartbeat", {}
            )
            return result.get("ok", False)
        except Exception as exc:
            logger.warning("Heartbeat failed: %s", exc)
            return False

    def poll_task(self) -> Optional[dict]:
        """拉取下一个任务。"""
        try:
            result = self._http_get(
                f"/api/workers/{self.worker_id}/next-task"
            )
            if result.get("ok") and result.get("task"):
                return result["task"]
            return None
        except Exception as exc:
            logger.warning("Poll failed: %s", exc)
            return None

    def report_started(self, task_id: str) -> bool:
        try:
            result = self._http_post(
                f"/api/workers/{self.worker_id}/task/{task_id}/started", {}
            )
            return result.get("ok", False)
        except Exception:
            return False

    def report_log(self, task_id: str, message: str) -> bool:
        try:
            result = self._http_post(
                f"/api/workers/{self.worker_id}/task/{task_id}/log",
                {"message": message},
            )
            return result.get("ok", False)
        except Exception:
            return False

    def report_completed(self, task_id: str, result_text: str = "") -> bool:
        try:
            result = self._http_post(
                f"/api/workers/{self.worker_id}/task/{task_id}/completed",
                {"result": result_text},
            )
            return result.get("ok", False)
        except Exception:
            return False

    def report_failed(self, task_id: str, error: str = "") -> bool:
        try:
            result = self._http_post(
                f"/api/workers/{self.worker_id}/task/{task_id}/failed",
                {"error": error},
            )
            return result.get("ok", False)
        except Exception:
            return False

    def execute_task(self, task: dict) -> tuple[bool, str]:
        """执行任务。默认 dry-run 模式。"""
        task_id = task.get("task_id", "")
        task_input = task.get("task_input", "")

        self.report_started(task_id)
        self.report_log(task_id, f"开始执行: {task_input[:200]}")

        # 检查是否为 shell 命令
        if task_input.strip().startswith("shell:"):
            cmd = task_input.strip()[6:].strip()
            if not self.allow_shell:
                self.report_log(task_id, f"[安全] Shell 执行未启用 (STABLEAGENT_WORKER_ALLOW_SHELL=1)")
                self.report_completed(task_id, f"[dry-run] Shell 命令已记录但未执行: {cmd}")
                return True, f"[dry-run] {cmd}"

            if not is_safe_command(cmd):
                self.report_failed(task_id, f"[拒绝] 危险命令: {cmd}")
                return False, f"危险命令被拒绝: {cmd}"

            return self._execute_shell(task_id, cmd)

        # 默认 dry-run 模式
        self.report_log(task_id, f"[dry-run] 任务已接收，内容: {task_input[:500]}")
        self.report_completed(task_id, f"[dry-run] 任务已记录。本地 Worker 尚未开启实际执行。")
        return True, f"[dry-run] {task_input[:100]}"

    def _execute_shell(self, task_id: str, cmd: str) -> tuple[bool, str]:
        """安全执行 shell 命令。"""
        self.report_log(task_id, f"[shell] 执行: {cmd}")
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=30, cwd=".",
            )
            output = result.stdout + result.stderr
            if result.returncode == 0:
                self.report_log(task_id, f"[shell] stdout: {output[:1000]}")
                self.report_completed(task_id, output[:2000])
                return True, output[:2000]
            else:
                self.report_log(task_id, f"[shell] exit={result.returncode}: {output[:1000]}")
                self.report_failed(task_id, f"exit={result.returncode}: {output[:1000]}")
                return False, output[:2000]
        except subprocess.TimeoutExpired:
            self.report_failed(task_id, "命令执行超时 (30s)")
            return False, "timeout"
        except Exception as exc:
            self.report_failed(task_id, str(exc))
            return False, str(exc)

    def run(self) -> None:
        """主循环：注册 → 心跳 → 轮询 → 执行。"""
        logger.info("Worker %s starting (server=%s)", self.worker_id, self.server_url)

        if not self.register():
            logger.error("Failed to register, exiting")
            return

        self._running = True
        while self._running:
            try:
                self.heartbeat()
                task = self.poll_task()
                if task:
                    logger.info("Got task: %s", task.get("task_id"))
                    self.execute_task(task)
                else:
                    time.sleep(self.poll_interval)
            except KeyboardInterrupt:
                logger.info("Worker interrupted")
                break
            except Exception as exc:
                logger.error("Worker error: %s", exc)
                time.sleep(self.poll_interval)

        logger.info("Worker %s stopped", self.worker_id)

    def stop(self) -> None:
        self._running = False


def is_safe_command(cmd: str) -> bool:
    """检查命令是否在安全白名单中。"""
    cmd_lower = cmd.strip().lower()
    # 检查危险模式
    for pattern in DANGEROUS_PATTERNS:
        if pattern in cmd_lower:
            return False
    # 检查白名单前缀
    for safe in SAFE_SHELL_COMMANDS:
        if cmd_lower.startswith(safe.lower()):
            return True
    return False
