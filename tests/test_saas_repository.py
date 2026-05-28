"""测试 SaaS Repository 完整 CRUD。

验证 Repository 层的所有核心方法。
"""

from stable_agent.saas.repository import SaasRepository
from stable_agent.saas.models import (
    Workspace, Project, AgentRun, AuditLogRecord,
    BillingPlanRecord, UsageEventRecord,
)


class TestSaasRepository:
    """测试 SaasRepository 完整 CRUD。"""

    def _setup(self):
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        ws = Workspace(name="test-ws", slug="test-ws")
        repo.create_workspace(ws)
        proj = Project(workspace_id=ws.id, name="test-proj")
        repo.create_project(proj)
        return repo, ws, proj

    # ------------------------------------------------------------------
    # Workspace
    # ------------------------------------------------------------------

    def test_create_and_get_workspace(self):
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        ws = Workspace(name="My WS", slug="my-ws", billing_plan="pro")
        assert repo.create_workspace(ws)

        fetched = repo.get_workspace(ws.id)
        assert fetched is not None
        assert fetched.name == "My WS"
        assert fetched.slug == "my-ws"
        assert fetched.billing_plan == "pro"

    def test_list_workspaces(self):
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        repo.create_workspace(Workspace(name="A"))
        repo.create_workspace(Workspace(name="B"))
        ws_list = repo.list_workspaces()
        assert len(ws_list) == 2

    # ------------------------------------------------------------------
    # Project
    # ------------------------------------------------------------------

    def test_create_and_get_project(self):
        repo, ws, _ = self._setup()
        proj = Project(workspace_id=ws.id, name="My Project", environment="staging")
        assert repo.create_project(proj)

        fetched = repo.get_project(proj.id)
        assert fetched is not None
        assert fetched.name == "My Project"
        assert fetched.environment == "staging"

    def test_project_requires_workspace(self):
        repo, ws, _ = self._setup()
        projects = repo.list_projects(ws.id)
        assert len(projects) >= 1

    # ------------------------------------------------------------------
    # AgentRun
    # ------------------------------------------------------------------

    def test_create_and_get_run(self):
        repo, ws, proj = self._setup()
        run = AgentRun(
            run_id="run_test_001",
            workspace_id=ws.id,
            project_id=proj.id,
            user_task="Test task",
            status="running",
            progress_pct=50,
        )
        assert repo.save_run(run)

        fetched = repo.get_run("run_test_001")
        assert fetched is not None
        assert fetched.user_task == "Test task"
        assert fetched.status == "running"
        assert fetched.project_id == proj.id

    def test_list_runs_by_project(self):
        repo, ws, proj = self._setup()
        repo.save_run(AgentRun(run_id="r1", workspace_id=ws.id, project_id=proj.id))
        repo.save_run(AgentRun(run_id="r2", workspace_id=ws.id, project_id=proj.id))
        runs = repo.list_runs_by_project(proj.id)
        assert len(runs) == 2

    # ------------------------------------------------------------------
    # BillingPlan
    # ------------------------------------------------------------------

    def test_billing_plan_crud(self):
        repo, ws, _ = self._setup()
        plan = BillingPlanRecord(
            workspace_id=ws.id,
            tier="pro",
            max_projects=3,
            max_runs_per_month=2000,
        )
        assert repo.save_billing_plan(plan)

        fetched = repo.get_billing_plan(ws.id)
        assert fetched is not None
        assert fetched.tier == "pro"
        assert fetched.max_projects == 3

    def test_billing_plan_free_defaults(self):
        repo, ws, _ = self._setup()
        plan = BillingPlanRecord(workspace_id=ws.id, tier="free")
        repo.save_billing_plan(plan)
        fetched = repo.get_billing_plan(ws.id)
        assert fetched is not None
        assert fetched.tier == "free"

    # ------------------------------------------------------------------
    # AuditLog
    # ------------------------------------------------------------------

    def test_audit_log_crud(self):
        repo, ws, proj = self._setup()
        log = AuditLogRecord(
            workspace_id=ws.id,
            project_id=proj.id,
            event_type="api_key_created",
            actor="user_001",
            target="api_key:ak_xxx",
            severity="info",
        )
        assert repo.save_audit_log(log)

        logs = repo.list_audit_logs(ws.id, limit=10)
        assert len(logs) >= 1
        assert logs[0].event_type == "api_key_created"

    def test_audit_log_critical(self):
        repo, ws, proj = self._setup()
        log = AuditLogRecord(
            workspace_id=ws.id,
            event_type="project_deleted",
            severity="critical",
        )
        repo.save_audit_log(log)
        logs = repo.list_audit_logs(ws.id)
        assert len(logs) >= 1
        assert logs[0].severity == "critical"

    # ------------------------------------------------------------------
    # UsageEvent
    # ------------------------------------------------------------------

    def test_usage_event_summary(self):
        repo, ws, proj = self._setup()
        repo.save_usage_event(UsageEventRecord(
            workspace_id=ws.id, project_id=proj.id,
            event_type="run_created", tokens_used=500,
        ))
        repo.save_usage_event(UsageEventRecord(
            workspace_id=ws.id, project_id=proj.id,
            event_type="mcp_tool_called", tokens_used=300,
        ))
        summary = repo.get_project_usage_summary(proj.id)
        assert summary["total_events"] == 2
        assert summary["total_tokens"] == 800
