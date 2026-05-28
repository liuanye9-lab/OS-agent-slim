"""测试 MCP project_context 注入。"""

from stable_agent.saas.repository import SaasRepository
from stable_agent.saas.service import SaasService
from stable_agent.saas.permissions import PermissionChecker
from stable_agent.saas.models import Workspace, Project, SaasMode


class TestMCPProjectContext:
    """测试 MCP tools/call 携带 project_id。"""

    def test_permission_local_mode_fallback(self):
        checker = PermissionChecker(
            mode="local",
            default_project_id="proj_default",
            default_workspace_id="ws_default",
        )
        result = checker.resolve_project_context(project_id="")
        assert result["project_id"] == "proj_default"
        assert result["mode"] == "local"

    def test_permission_local_mode_with_project(self):
        checker = PermissionChecker(
            mode="local",
            default_project_id="proj_default",
            default_workspace_id="ws_default",
        )
        result = checker.resolve_project_context(project_id="proj_custom")
        assert result["project_id"] == "proj_custom"

    def test_permission_saas_mode_no_project_fails(self):
        checker = PermissionChecker(mode="saas")
        try:
            checker.resolve_project_context(project_id="")
            assert False, "Should have raised PermissionError"
        except PermissionError:
            pass

    def test_permission_saas_mode_with_project(self):
        checker = PermissionChecker(mode="saas")
        result = checker.resolve_project_context(project_id="proj_valid")
        assert result["project_id"] == "proj_valid"
        assert result["mode"] == "saas"

    def test_is_saas_mode(self):
        checker = PermissionChecker(mode="saas")
        assert checker.is_saas_mode() is True
        assert checker.is_local_mode() is False

    def test_is_local_mode(self):
        checker = PermissionChecker(mode="local")
        assert checker.is_local_mode() is True
        assert checker.is_saas_mode() is False

    def test_service_saas_mode_enforces_project(self):
        """完整链路：SaaS 模式 + API Key → project context。"""
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        ws = Workspace(name="team")
        repo.create_workspace(ws)
        proj = Project(workspace_id=ws.id, name="app")
        repo.create_project(proj)

        svc = SaasService(repo=repo, mode="saas")
        # 有效 project_id
        result = svc.validate_project_id(proj.id)
        assert result == proj.id

        # 无效 project_id
        try:
            svc.validate_project_id("")
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

    def test_run_context_has_saas_fields(self):
        """测试 RunContext 包含 workspace_id/project_id。"""
        from stable_agent.gateway.run_context import RunContext

        ctx = RunContext.create(
            task_input="test task",
            workspace_id="ws_001",
            project_id="proj_001",
            agent_id="agent_001",
            mode="saas",
        )
        assert ctx.workspace_id == "ws_001"
        assert ctx.project_id == "proj_001"
        assert ctx.agent_id == "agent_001"
        assert ctx.mode == "saas"

    def test_run_context_child_span_inherits_saas(self):
        """子 span 应继承父级的 SaaS 字段。"""
        from stable_agent.gateway.run_context import RunContext

        parent = RunContext.create(
            task_input="parent task",
            workspace_id="ws_parent",
            project_id="proj_parent",
        )
        child = parent.child_span()

        assert child.run_id == parent.run_id
        assert child.workspace_id == parent.workspace_id
        assert child.project_id == parent.project_id
