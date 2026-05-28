"""测试 SaaS Dashboard 路由。"""

from stable_agent.saas.repository import SaasRepository
from stable_agent.saas.service import SaasService
from stable_agent.saas.models import Workspace, Project


class TestSaaSDashboardRoutes:
    """测试 Dashboard 相关 API 逻辑（非 HTTP 测试）。"""

    def test_project_list_with_runs(self):
        """测试项目列表 + 运行数据。"""
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        ws = Workspace(name="team")
        repo.create_workspace(ws)
        proj = Project(workspace_id=ws.id, name="dashboard-app")
        repo.create_project(proj)

        svc = SaasService(repo=repo, mode="local")
        svc.initialize()

        # 创建几个 runs
        svc.associate_run("run_d1", proj.id, user_task="dashboard task 1")
        svc.associate_run("run_d2", proj.id, user_task="dashboard task 2")

        runs = svc.get_runs_by_project(proj.id)
        assert len(runs) == 2

    def test_run_detail_accessible(self):
        """测试 run 详情可访问。"""
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        ws = Workspace(name="team")
        repo.create_workspace(ws)
        proj = Project(workspace_id=ws.id, name="app")
        repo.create_project(proj)

        svc = SaasService(repo=repo, mode="local")
        svc.associate_run("run_detail_1", proj.id, user_task="detail test")

        run = repo.get_run("run_detail_1")
        assert run is not None
        assert run.project_id == proj.id
        assert run.user_task == "detail test"

    def test_usage_summary_for_project(self):
        """测试项目用量摘要。"""
        from stable_agent.saas.usage import UsageCounter

        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        counter = UsageCounter(repo)

        counter.record_token_used("ws_1", "proj_1", "run_1", tokens_used=3000)
        counter.record_mcp_tool_called("ws_1", "proj_1", "run_1", tool_name="test")

        summary = counter.get_summary("proj_1")
        assert summary["total_events"] == 2
        assert summary["total_tokens"] == 3000

    def test_multiple_projects_isolation(self):
        """测试多项目数据隔离。"""
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        ws = Workspace(name="team")
        repo.create_workspace(ws)
        proj_a = Project(workspace_id=ws.id, name="frontend")
        proj_b = Project(workspace_id=ws.id, name="backend")
        repo.create_project(proj_a)
        repo.create_project(proj_b)

        svc = SaasService(repo=repo, mode="local")
        svc.associate_run("r_a1", proj_a.id, user_task="FE task")
        svc.associate_run("r_a2", proj_a.id, user_task="FE task 2")
        svc.associate_run("r_b1", proj_b.id, user_task="BE task")

        assert len(svc.get_runs_by_project(proj_a.id)) == 2
        assert len(svc.get_runs_by_project(proj_b.id)) == 1

        # 验证不跨项目泄漏
        for r in svc.get_runs_by_project(proj_a.id):
            assert r.project_id == proj_a.id
        for r in svc.get_runs_by_project(proj_b.id):
            assert r.project_id == proj_b.id
