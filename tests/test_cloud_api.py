"""tests.test_cloud_api — Cloud API 测试。"""

import os
import uuid
import pytest

from fastapi.testclient import TestClient


class TestCloudAPI:
    """Cloud API 测试。"""

    def setup_method(self):
        self._db_path = f"/tmp/test_cloud_api_{uuid.uuid4().hex[:8]}.sqlite"
        os.environ["STABLEAGENT_PROFILE"] = "slim"
        os.environ["STABLEAGENT_CLOUD_DB"] = self._db_path
        # 清理全局单例
        self._reset_singleton()

    def teardown_method(self):
        os.environ.pop("STABLEAGENT_PROFILE", None)
        os.environ.pop("STABLEAGENT_CLOUD_DB", None)
        self._reset_singleton()
        # 清理 SQLite 文件
        for suffix in ["", "-wal", "-shm"]:
            path = self._db_path + suffix
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass

    def _reset_singleton(self):
        """重置 ControlCenter 单例。"""
        import web.routes.cloud as cloud_module
        if cloud_module._control_center:
            try:
                cloud_module._control_center.close()
            except Exception:
                pass
        cloud_module._control_center = None

    def _get_app(self):
        """创建新的 app 实例。"""
        self._reset_singleton()
        from web.app_slim import create_slim_app
        return create_slim_app()

    def test_cloud_health(self):
        """GET /api/cloud/health 返回 ok=true。"""
        app = self._get_app()
        client = TestClient(app)
        resp = client.get("/api/cloud/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["profile"] == "slim"
        assert data["server_role"] == "control_center"

    def test_create_task(self):
        """POST /api/tasks 可以创建任务。"""
        app = self._get_app()
        client = TestClient(app)
        resp = client.post("/api/tasks", json={
            "task_input": "test task",
            "title": "Test",
            "priority": 5,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["task"]["task_input"] == "test task"

    def test_list_tasks(self):
        """GET /api/tasks 可以列出任务。"""
        app = self._get_app()
        client = TestClient(app)
        client.post("/api/tasks", json={"task_input": "t1"})
        client.post("/api/tasks", json={"task_input": "t2"})
        resp = client.get("/api/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["count"] >= 2  # 至少 2 个

    def test_register_worker(self):
        """POST /api/workers/register 可以注册 Worker。"""
        app = self._get_app()
        client = TestClient(app)
        resp = client.post("/api/workers/register", json={
            "worker_id": "macbook_pro",
            "name": "MacBook Pro",
            "machine_type": "macos",
            "capabilities": ["coding", "shell"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["worker"]["worker_id"] == "macbook_pro"

    def test_list_workers(self):
        """GET /api/workers 可以列出 Workers。"""
        app = self._get_app()
        client = TestClient(app)
        client.post("/api/workers/register", json={
            "worker_id": "w1", "name": "W1",
        })
        resp = client.get("/api/workers")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1  # 至少 1 个

    def test_slim_dashboard(self):
        """GET /slim 返回 200。"""
        app = self._get_app()
        client = TestClient(app)
        resp = client.get("/slim")
        assert resp.status_code == 200
        assert "StableAgent" in resp.text

    def test_slim_status(self):
        """GET /api/slim/status 返回聚合数据。"""
        app = self._get_app()
        client = TestClient(app)
        resp = client.get("/api/slim/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "health" in data
        assert "workers" in data
        assert "tasks" in data
