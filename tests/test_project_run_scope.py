"""测试 Run 必须归属 Project 的约束。"""

from stable_agent.saas.repository import SaasRepository
from stable_agent.saas.service import SaasService
from stable_agent.saas.models import Workspace, Project, AgentRun


class TestProjectRunScope:
    """测试 run 归属 project 的完整链路。"""

    def test_associate_run_to_project(self):
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        ws = Workspace(name="team")
        repo.create_workspace(ws)
        proj = Project(workspace_id=ws.id, name="app")
        repo.create_project(proj)

        svc = SaasService(repo=repo, mode="local")
        run = svc.associate_run(
            run_id="run_test_001",
            project_id=proj.id,
            user_task="测试任务",
        )

        assert run.run_id == "run_test_001"
        assert run.project_id == proj.id
        assert run.workspace_id == ws.id

    def test_get_runs_by_project(self):
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        ws = Workspace(name="team")
        repo.create_workspace(ws)
        proj = Project(workspace_id=ws.id, name="app")
        repo.create_project(proj)

        svc = SaasService(repo=repo, mode="local")
        svc.associate_run("run_001", proj.id, user_task="task 1")
        svc.associate_run("run_002", proj.id, user_task="task 2")
        svc.associate_run("run_003", proj.id, user_task="task 3")

        runs = svc.get_runs_by_project(proj.id)
        assert len(runs) == 3

    def test_run_has_all_saas_fields(self):
        run = AgentRun(
            run_id="run_xyz",
            workspace_id="ws_xyz",
            project_id="proj_xyz",
            agent_id="agent_xyz",
            user_task="hello",
        )
        assert run.workspace_id == "ws_xyz"
        assert run.project_id == "proj_xyz"
        assert run.agent_id == "agent_xyz"

    def test_runs_list_by_project_isolation(self):
        """不同 project 的 runs 应该隔离。"""
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        ws = Workspace(name="team")
        repo.create_workspace(ws)
        proj_a = Project(workspace_id=ws.id, name="project-a")
        proj_b = Project(workspace_id=ws.id, name="project-b")
        repo.create_project(proj_a)
        repo.create_project(proj_b)

        svc = SaasService(repo=repo, mode="local")
        svc.associate_run("run_a1", proj_a.id, user_task="a task")
        svc.associate_run("run_b1", proj_b.id, user_task="b task")

        runs_a = svc.get_runs_by_project(proj_a.id)
        runs_b = svc.get_runs_by_project(proj_b.id)

        assert len(runs_a) == 1
        assert runs_a[0].project_id == proj_a.id
        assert len(runs_b) == 1
        assert runs_b[0].project_id == proj_b.id
