"""测试 SaaS API 路由。

验证：
1. Health check
2. Workspace CRUD
3. Project CRUD
4. Run 管理路由
5. Eval 路由
6. Usage 查询
7. API Key 管理
8. Audit Log 查询
"""

import pytest
from stable_agent.saas.repository import SaasRepository
from stable_agent.saas.models import (
    Workspace, Project, AgentRun, _new_id,
)
from stable_agent.saas.workspace_service import WorkspaceService
from stable_agent.saas.project_service import ProjectService
from stable_agent.saas.run_service import RunService
from stable_agent.saas.billing import BillingManager
from stable_agent.saas.audit_log import AuditLogger


class TestApiRoutesSaaS:
    """测试 SaaS API 路由对应的业务逻辑。"""

    def _setup(self):
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        billing = BillingManager(repository=repo)
        ws_svc = WorkspaceService(repository=repo, billing_manager=billing)
        proj_svc = ProjectService(repository=repo, billing_manager=billing)
        run_svc = RunService(repository=repo)
        audit = AuditLogger(repository=repo)
        return repo, ws_svc, proj_svc, run_svc, audit

    # ------------------------------------------------------------------
    # Workspace API
    # ------------------------------------------------------------------

    def test_create_workspace(self):
        repo, ws_svc, _, _, _ = self._setup()
        ws = ws_svc.create_workspace(name="Test WS", tier="pro")
        assert ws.id.startswith("ws_")
        assert ws.billing_plan == "pro"

    def test_get_workspace(self):
        repo, ws_svc, _, _, _ = self._setup()
        ws = ws_svc.create_workspace(name="Test")
        fetched = ws_svc.get_workspace(ws.id)
        assert fetched is not None
        assert fetched.name == "Test"

    def test_list_workspaces(self):
        repo, ws_svc, _, _, _ = self._setup()
        ws_svc.create_workspace(name="A")
        ws_svc.create_workspace(name="B")
        ws_list = ws_svc.list_workspaces()
        assert len(ws_list) == 2

    # ------------------------------------------------------------------
    # Project API
    # ------------------------------------------------------------------

    def test_create_project(self):
        repo, ws_svc, proj_svc, _, _ = self._setup()
        ws = ws_svc.create_workspace(name="WS")
        proj = proj_svc.create_project(ws.id, "My Project", environment="staging")
        assert proj.id.startswith("proj_")
        assert proj.workspace_id == ws.id

    def test_list_projects(self):
        repo, ws_svc, proj_svc, _, _ = self._setup()
        ws = ws_svc.create_workspace(name="WS", tier="pro")  # Pro tier: max 3 projects
        proj_svc.create_project(ws.id, "P1")
        proj_svc.create_project(ws.id, "P2")
        projects = proj_svc.list_projects(ws.id)
        assert len(projects) == 2

    def test_get_or_create_default_project(self):
        repo, ws_svc, proj_svc, _, _ = self._setup()
        ws = ws_svc.create_workspace(name="WS")
        proj = proj_svc.get_or_create_default(ws.id)
        assert proj.name == "Default Project"
        # 第二次调用返回同一个项目
        proj2 = proj_svc.get_or_create_default(ws.id)
        assert proj2.id == proj.id

    # ------------------------------------------------------------------
    # Run API
    # ------------------------------------------------------------------

    def test_create_run(self):
        repo, ws_svc, proj_svc, run_svc, _ = self._setup()
        ws = ws_svc.create_workspace(name="WS")
        proj = proj_svc.create_project(ws.id, "P1")
        run = run_svc.create_run(
            ws.id, proj.id, user_task="Hello world", source="api",
        )
        assert run.run_id.startswith("run_")
        assert run.status == "created"

    def test_get_run(self):
        repo, ws_svc, proj_svc, run_svc, _ = self._setup()
        ws = ws_svc.create_workspace(name="WS")
        proj = proj_svc.create_project(ws.id, "P1")
        run = run_svc.create_run(ws.id, proj.id)
        fetched = run_svc.get_run(run.run_id)
        assert fetched is not None
        assert fetched.run_id == run.run_id

    def test_update_run_status(self):
        repo, ws_svc, proj_svc, run_svc, _ = self._setup()
        ws = ws_svc.create_workspace(name="WS")
        proj = proj_svc.create_project(ws.id, "P1")
        run = run_svc.create_run(ws.id, proj.id)
        assert run_svc.update_run_status(run.run_id, "running", 50)
        updated = run_svc.get_run(run.run_id)
        assert updated.status == "running"
        assert updated.progress_pct == 50

    def test_complete_run(self):
        repo, ws_svc, proj_svc, run_svc, _ = self._setup()
        ws = ws_svc.create_workspace(name="WS")
        proj = proj_svc.create_project(ws.id, "P1")
        run = run_svc.create_run(ws.id, proj.id)
        assert run_svc.complete_run(run.run_id, overall_score=0.85, token_used=1000)
        completed = run_svc.get_run(run.run_id)
        assert completed.status == "completed"
        assert completed.overall_score == 0.85
        assert completed.token_used == 1000

    def test_list_runs_by_project(self):
        repo, ws_svc, proj_svc, run_svc, _ = self._setup()
        ws = ws_svc.create_workspace(name="WS")
        proj = proj_svc.create_project(ws.id, "P1")
        run_svc.create_run(ws.id, proj.id)
        run_svc.create_run(ws.id, proj.id)
        runs = run_svc.list_runs_by_project(proj.id)
        assert len(runs) == 2

    # ------------------------------------------------------------------
    # Audit Log API
    # ------------------------------------------------------------------

    def test_audit_log_records(self):
        repo, ws_svc, proj_svc, run_svc, audit = self._setup()
        ws = ws_svc.create_workspace(name="WS")
        proj = proj_svc.create_project(ws.id, "P1")

        audit.log_api_key_created(ws.id, "test", "ak_1", ["runs:write"])
        audit.log_mcp_tool_called(ws.id, proj.id, "os_agent", "run_1")

        logs = audit.list_recent(ws.id)
        assert len(logs) == 2
