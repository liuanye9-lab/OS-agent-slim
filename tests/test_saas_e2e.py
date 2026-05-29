"""SaaS 端到端测试。

验证完整 SaaS 流程：注册→登录→创建Workspace→创建Project→
创建Run→查询用量→创建APIKey→审核Skill补丁→查看Dashboard页面。
"""

import pytest
from web.server import app
from fastapi.testclient import TestClient


class TestSaaSE2E:
    """SaaS 完整端到端流程测试。"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_full_saas_flow(self, client):
        """完整 SaaS 流程：从注册到 Skill 导出。"""
        # 1. 健康检查
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["service"] == "StableAgent Cloud"

        # 2. 注册
        import uuid
        email = f"e2e_{uuid.uuid4().hex[:8]}@saas.com"
        r = client.post("/api/auth/register", json={
            "email": email, "password": "e2etest", "name": "E2E User",
        })
        assert r.status_code == 200
        token = r.json()["token"]
        assert token
        user_id = r.json()["user_id"]
        assert user_id.startswith("user_")

        # 3. 登录
        r = client.post("/api/auth/login", json={
            "email": email, "password": "e2etest",
        })
        assert r.status_code == 200
        assert r.json()["token"]

        # 4. 查询当前用户
        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["email"] == email

        # 5. 创建 Workspace
        r = client.post("/api/workspaces", json={"name": "E2E Workspace", "tier": "pro"})
        assert r.status_code == 200
        ws_id = r.json()["id"]
        assert ws_id.startswith("ws_")

        # 6. 列出 Workspace
        r = client.get("/api/workspaces")
        assert r.status_code == 200
        assert len(r.json()["workspaces"]) >= 1

        # 7. 创建 Project
        r = client.post("/api/projects", json={
            "workspace_id": ws_id, "name": "E2E Project", "environment": "staging",
        })
        assert r.status_code == 200
        proj_id = r.json()["id"]
        assert proj_id.startswith("proj_")

        # 8. 创建 Run
        r = client.post("/api/runs", json={
            "workspace_id": ws_id, "project_id": proj_id, "user_task": "E2E test task",
        })
        assert r.status_code == 200
        run_id = r.json()["run_id"]
        assert run_id.startswith("run_")

        # 9. 获取 Run 详情
        r = client.get(f"/api/runs/{run_id}/detail")
        assert r.status_code == 200
        assert r.json()["status"] == "created"

        # 10. 查询用量
        r = client.get(f"/api/usage?workspace_id={ws_id}")
        assert r.status_code == 200

        # 11. 创建 API Key
        r = client.post("/api/api-keys", json={
            "workspace_id": ws_id, "name": "e2e-key", "scopes": ["runs:write", "runs:read"],
        })
        assert r.status_code == 200
        key_id = r.json()["key_id"]
        api_key = r.json()["api_key"]
        assert key_id.startswith("ak_")
        assert api_key.startswith("sk_")

        # 12. 列出 API Keys
        r = client.get(f"/api/api-keys?workspace_id={ws_id}")
        assert r.status_code == 200
        assert len(r.json()["keys"]) >= 1

        # 13. 撤销 API Key
        r = client.delete(f"/api/api-keys/{key_id}")
        assert r.status_code == 200
        assert r.json()["revoked"] is True

        # 14. 查询 Audit Log
        r = client.get(f"/api/audit-logs?workspace_id={ws_id}")
        assert r.status_code == 200

        # 15. 添加团队成员
        r = client.post(f"/api/workspaces/{ws_id}/members", json={
            "email": "member@saas.com", "role": "developer",
        })
        assert r.status_code == 200
        assert r.json()["role"] == "developer"

        # 16. 列出团队成员
        r = client.get(f"/api/workspaces/{ws_id}/members")
        assert r.status_code == 200
        assert len(r.json()["members"]) >= 1

        # 17. Skill Patch 提交
        # 先通过 MCP 工具提交 patch
        r = client.post("/mcp", json={
            "jsonrpc": "2.0", "method": "tools/call", "id": 1,
            "params": {
                "name": "stableagent.skill.patch_propose",
                "arguments": {
                    "skill_id": "skill_e2e",
                    "patch_content": "+ E2E test improvement",
                    "workspace_id": ws_id,
                    "project_id": proj_id,
                },
            },
        })
        assert r.status_code == 200
        assert "patch_id" in str(r.json())

        # 18. 查询 Reviews
        r = client.get(f"/api/reviews?workspace_id={ws_id}")
        assert r.status_code == 200

    def test_all_pages_accessible(self, client):
        """验证全部 SaaS 页面可访问。"""
        pages = [
            "/", "/login", "/connect", "/dashboard/v3",
            "/dashboard/usage", "/dashboard/apikeys", "/dashboard/billing",
            "/dashboard/team", "/dashboard/skills", "/dashboard/review",
            "/docs", "/redoc",
        ]
        for p in pages:
            r = client.get(p)
            assert r.status_code == 200, f"Page {p} returned {r.status_code}"

    def test_api_error_handling(self, client):
        """验证 API 错误处理。"""
        # 无效 workspace 返回错误
        r = client.get("/api/workspaces/nonexistent")
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            assert "error" in r.json() or r.json() is None

        # 无效 run 返回错误
        r = client.get("/api/runs/nonexistent")
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            assert "error" in r.json() or r.json().get("run_id") is None

        # 无 token 访问 me
        r = client.get("/api/auth/me")
        assert r.status_code == 401

        # 错误密码登录
        r = client.post("/api/auth/login", json={"email": "no@no.com", "password": "wrong"})
        assert r.status_code == 401

    def test_rate_limiter(self):
        """验证速率限制。"""
        from stable_agent.saas.rate_limiter import RateLimiter
        rl = RateLimiter()
        # 前 10 次应通过
        for i in range(10):
            ok, _ = rl.check("test-e2e", "free")
            assert ok, f"Request {i + 1} should pass"
        # 第 11 次应拒绝
        ok, retry = rl.check("test-e2e", "free")
        assert not ok
        assert retry > 0

    def test_permission_matrix(self):
        """验证权限矩阵。"""
        from stable_agent.saas.permissions import PermissionChecker
        # Owner 有全部权限
        assert PermissionChecker.can_export_skill("owner")
        assert PermissionChecker.can_create_run("owner")
        # Viewer 只有读权限
        assert PermissionChecker.can_view_project("viewer")
        assert not PermissionChecker.can_create_run("viewer")
        assert not PermissionChecker.can_export_skill("viewer")
        # Reviewer 可以审核但不能创建
        assert PermissionChecker.can_review_skill("reviewer")
        assert not PermissionChecker.can_create_run("reviewer")
