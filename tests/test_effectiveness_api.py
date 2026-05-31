"""Tests for effectiveness API routes — {ok, data/error} contract and V11.3 fields."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
import tempfile

from stable_agent.effectiveness.experiment_store import ExperimentStore
from stable_agent.effectiveness.schemas import EffectivenessTask, EffectivenessRun
from web.routes.effectiveness import register_effectiveness_routes


@pytest.fixture()
def client():
    """Create a FastAPI test client with effectiveness routes registered."""
    with tempfile.TemporaryDirectory() as tmp:
        store = ExperimentStore(data_dir=tmp)
        app = FastAPI()
        register_effectiveness_routes(app, store)
        yield TestClient(app), store


class TestEffectivenessAPI:
    """Verify API routes follow {ok, data/error} contract."""

    def test_list_tasks_empty(self, client):
        c, _ = client
        resp = c.get("/api/effectiveness/tasks")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["data"]["tasks"] == []
        assert body["data"]["total"] == 0

    def test_create_task(self, client):
        c, _ = client
        resp = c.post("/api/effectiveness/task", json={
            "task_id": "t1",
            "description": "Test task",
            "category": "general",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["data"]["task_id"] == "t1"

    def test_list_tasks_after_create(self, client):
        c, _ = client
        c.post("/api/effectiveness/task", json={"task_id": "t1", "description": "Test"})
        resp = c.get("/api/effectiveness/tasks")
        body = resp.json()
        assert body["ok"] is True
        assert body["data"]["total"] == 1

    def test_record_run_v113_fields(self, client):
        """record_run should accept V11.3 new fields and persist them."""
        c, _ = client
        c.post("/api/effectiveness/task", json={"task_id": "t1", "description": "Test"})
        resp = c.post("/api/effectiveness/run", json={
            "task_id": "t1",
            "mode": "stableagent",
            "model": "qwen-plus",
            "stableagent_run_id": "sa-001",
            "test_passed": True,
            "over_editing": False,
            "rework_count": 2,
            "user_satisfaction": 4.5,
            "constraint_preservation": 0.95,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        data = body["data"]
        assert data["model"] == "qwen-plus"
        assert data["stableagent_run_id"] == "sa-001"
        assert data["test_passed"] is True
        assert data["over_editing"] is False
        assert data["rework_count"] == 2
        assert data["user_satisfaction"] == 4.5
        assert data["constraint_preservation"] == 0.95

    def test_record_run_missing_task_id_returns_400(self, client):
        """Missing required task_id should return 400 with {ok: false}."""
        c, _ = client
        resp = c.post("/api/effectiveness/run", json={"mode": "baseline"})
        assert resp.status_code == 400
        body = resp.json()
        assert body["ok"] is False
        assert "error" in body

    def test_list_runs_empty(self, client):
        c, _ = client
        resp = c.get("/api/effectiveness/runs")
        body = resp.json()
        assert body["ok"] is True
        assert body["data"]["runs"] == []
        assert body["data"]["total"] == 0

    def test_get_summary_empty(self, client):
        c, _ = client
        resp = c.get("/api/effectiveness/summary")
        body = resp.json()
        assert body["ok"] is True
        assert body["data"]["summaries"] == []
        assert body["data"]["total"] == 0

    def test_get_task_not_found_returns_404(self, client):
        c, _ = client
        resp = c.get("/api/effectiveness/task/nonexistent")
        assert resp.status_code == 404
        body = resp.json()
        assert body["ok"] is False
        assert "error" in body

    def test_get_task_detail_with_runs(self, client):
        c, _ = client
        c.post("/api/effectiveness/task", json={"task_id": "t1", "description": "Test"})
        c.post("/api/effectiveness/run", json={"task_id": "t1", "mode": "baseline"})
        c.post("/api/effectiveness/run", json={"task_id": "t1", "mode": "stableagent"})
        resp = c.get("/api/effectiveness/task/t1")
        body = resp.json()
        assert body["ok"] is True
        data = body["data"]
        assert data["task_id"] == "t1"
        assert len(data["runs"]) == 2
        assert "summary" in data
        assert "verdict" in data["summary"]

    def test_all_endpoints_return_ok_field(self, client):
        """All GET endpoints should include 'ok' field in response."""
        c, _ = client
        endpoints = [
            "/api/effectiveness/tasks",
            "/api/effectiveness/runs",
            "/api/effectiveness/summary",
        ]
        for endpoint in endpoints:
            resp = c.get(endpoint)
            body = resp.json()
            assert "ok" in body, f"{endpoint} missing 'ok' field"

    def test_get_summary_by_run_id(self, client):
        """GET /summary?run_id=X should return summary for the task containing that run."""
        c, store = client
        c.post("/api/effectiveness/task", json={"task_id": "t1", "description": "Test"})
        c.post("/api/effectiveness/run", json={"task_id": "t1", "run_id": "b1", "mode": "baseline", "success": False})
        c.post("/api/effectiveness/run", json={"task_id": "t1", "run_id": "s1", "mode": "stableagent", "success": True})

        resp = c.get("/api/effectiveness/summary?run_id=s1")
        body = resp.json()
        assert body["ok"] is True
        assert body["data"]["task_id"] == "t1"
        assert body["data"]["baseline_count"] == 1
        assert body["data"]["stableagent_count"] == 1

    def test_get_summary_by_run_id_not_found(self, client):
        """GET /summary?run_id=nonexistent should return {ok: false}."""
        c, _ = client
        resp = c.get("/api/effectiveness/summary?run_id=nonexistent")
        body = resp.json()
        assert body["ok"] is False
        assert "error" in body
