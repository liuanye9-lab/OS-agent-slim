"""测试 Workspace 和 Project 的创建和归属。"""

from stable_agent.saas.repository import SaasRepository
from stable_agent.saas.service import SaasService
from stable_agent.saas.models import Workspace, Project


class TestWorkspaceProjectCreation:
    """测试 workspace 和 project 的创建与查询。"""

    def test_create_workspace(self):
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        ws = Workspace(name="my-team")
        ok = repo.create_workspace(ws)
        assert ok

        fetched = repo.get_workspace(ws.id)
        assert fetched is not None
        assert fetched.name == "my-team"

    def test_create_project(self):
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        # 先创建 workspace
        ws = Workspace(name="team")
        repo.create_workspace(ws)

        proj = Project(workspace_id=ws.id, name="web-app")
        ok = repo.create_project(proj)
        assert ok

        fetched = repo.get_project(proj.id)
        assert fetched is not None
        assert fetched.workspace_id == ws.id
        assert fetched.name == "web-app"

    def test_list_projects_empty(self):
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        projects = repo.list_projects("nonexistent")
        assert len(projects) == 0

    def test_list_projects_by_workspace(self):
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        ws = Workspace(name="team")
        repo.create_workspace(ws)
        repo.create_project(Project(workspace_id=ws.id, name="p1"))
        repo.create_project(Project(workspace_id=ws.id, name="p2"))

        projects = repo.list_projects(ws.id)
        assert len(projects) == 2

    def test_list_workspaces(self):
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        repo.create_workspace(Workspace(name="w1"))
        repo.create_workspace(Workspace(name="w2"))

        workspaces = repo.list_workspaces()
        assert len(workspaces) >= 2


class TestSaasServiceLocalMode:
    """测试 SaasService local 模式。"""

    def test_service_initialization(self):
        svc = SaasService(repo=SaasRepository(db_path=":memory:"), mode="local")
        svc.initialize()

        # 应自动创建 default project
        assert svc.default_project_id != ""
        assert svc.default_workspace_id != ""

    def test_default_project_id(self):
        svc = SaasService(repo=SaasRepository(db_path=":memory:"), mode="local")
        svc.initialize()
        proj_id = svc.default_project_id
        assert proj_id.startswith("proj_")

    def test_validate_project_id_local(self):
        """local 模式：空 project_id fallback 到 default。"""
        svc = SaasService(repo=SaasRepository(db_path=":memory:"), mode="local")
        svc.initialize()
        result = svc.validate_project_id("")
        assert result == svc.default_project_id

    def test_create_and_get_project(self):
        svc = SaasService(repo=SaasRepository(db_path=":memory:"), mode="local")
        svc.initialize()
        proj = svc.create_project(svc.default_workspace_id, "my-project")
        assert proj.name == "my-project"

        fetched = svc.get_project(proj.id)
        assert fetched is not None
        assert fetched.id == proj.id


class TestSaasServiceSaasMode:
    """测试 SaasService saas 模式。"""

    def test_validate_project_id_saas_mode_requires_id(self):
        """SaaS 模式：空 project_id 应抛异常。"""
        svc = SaasService(repo=SaasRepository(db_path=":memory:"), mode="saas")
        svc.initialize()
        try:
            svc.validate_project_id("")
            assert False, "Should have raised ValueError"
        except ValueError:
            pass  # expected

    def test_validate_project_id_saas_valid(self):
        """SaaS 模式：有效 project_id 应通过。"""
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        ws = Workspace(name="team")
        repo.create_workspace(ws)
        proj = Project(workspace_id=ws.id, name="app")
        repo.create_project(proj)

        svc = SaasService(repo=repo, mode="saas")
        result = svc.validate_project_id(proj.id)
        assert result == proj.id
