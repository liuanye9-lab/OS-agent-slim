"""tests/test_skill_dashboard.py — Skill Dashboard 测试。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app():
    """创建测试应用。"""
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from web.app_slim import create_slim_app
    return create_slim_app()


@pytest.fixture
def client(app):
    """创建测试客户端。"""
    return TestClient(app)


class TestSkillDashboard:
    """Skill Dashboard 测试。"""

    def test_skills_page_returns_200(self, client):
        """/skills 返回 200。"""
        response = client.get("/skills")
        assert response.status_code == 200

    def test_skills_page_contains_title(self, client):
        """/skills 页面包含标题。"""
        response = client.get("/skills")
        assert "Skill Dashboard" in response.text

    def test_skills_api_returns_200(self, client):
        """/api/skills 返回 200。"""
        response = client.get("/api/skills")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True

    def test_skills_health_returns_200(self, client):
        """/api/skills/health 返回 200。"""
        response = client.get("/api/skills/health")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True

    def test_skills_search_returns_200(self, client):
        """/api/skills/search 返回 200。"""
        response = client.post(
            "/api/skills/search",
            json={"query": "test", "top_k": 5},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True

    def test_empty_state_not_white_screen(self, client):
        """空状态不白屏。"""
        response = client.get("/api/skills")
        data = response.json()
        assert "ok" in data
        assert "skills" in data
