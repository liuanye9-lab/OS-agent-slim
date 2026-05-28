"""测试权限模型和角色层级。

验证：
1. 角色权限矩阵正确性
2. PermissionChecker 的 local/saas 模式
3. 角色级权限方法
"""

from stable_agent.saas.permissions import PermissionChecker, ROLE_PERMISSIONS
from stable_agent.saas.models import MemberRole


class TestPermissionRoles:
    """测试角色权限矩阵。"""

    def test_owner_has_full_permissions(self):
        perms = ROLE_PERMISSIONS[MemberRole.OWNER.value]
        assert "run:create" in perms
        assert "skill:export" in perms
        assert "project:create" in perms
        assert "member:invite" in perms
        assert "audit:view" in perms
        assert "apikey:create" in perms

    def test_admin_cannot_export_skill(self):
        perms = ROLE_PERMISSIONS[MemberRole.ADMIN.value]
        assert "skill:export" not in perms
        assert "skill:validate" in perms
        assert "project:manage" in perms

    def test_developer_can_create_run(self):
        perms = ROLE_PERMISSIONS[MemberRole.DEVELOPER.value]
        assert "run:create" in perms
        assert "skill:patch" in perms
        assert "skill:export" not in perms
        assert "skill:review" not in perms

    def test_reviewer_can_review_but_not_create_run(self):
        perms = ROLE_PERMISSIONS[MemberRole.REVIEWER.value]
        assert "skill:review" in perms
        assert "skill:validate" in perms
        assert "run:create" not in perms
        assert "skill:export" not in perms

    def test_viewer_is_read_only(self):
        perms = ROLE_PERMISSIONS[MemberRole.VIEWER.value]
        assert "run:view" in perms
        assert "skill:view" in perms
        assert "run:create" not in perms
        assert "skill:patch" not in perms
        assert "apikey:create" not in perms


class TestPermissionCheckerRoles:
    """测试 PermissionChecker 角色级方法。"""

    def test_can_view_project(self):
        assert PermissionChecker.can_view_project("owner")
        assert PermissionChecker.can_view_project("developer")
        assert PermissionChecker.can_view_project("viewer")

    def test_can_create_run(self):
        assert PermissionChecker.can_create_run("owner")
        assert PermissionChecker.can_create_run("developer")
        assert not PermissionChecker.can_create_run("viewer")
        assert not PermissionChecker.can_create_run("reviewer")

    def test_can_review_skill(self):
        assert PermissionChecker.can_review_skill("owner")
        assert PermissionChecker.can_review_skill("reviewer")
        assert not PermissionChecker.can_review_skill("viewer")
        assert not PermissionChecker.can_review_skill("developer")

    def test_can_export_skill(self):
        assert PermissionChecker.can_export_skill("owner")
        assert not PermissionChecker.can_export_skill("admin")
        assert not PermissionChecker.can_export_skill("developer")
        assert not PermissionChecker.can_export_skill("viewer")

    def test_can_create_project(self):
        assert PermissionChecker.can_create_project("owner")
        assert PermissionChecker.can_create_project("admin")
        assert not PermissionChecker.can_create_project("developer")
        assert not PermissionChecker.can_create_project("viewer")

    def test_can_view_audit(self):
        assert PermissionChecker.can_view_audit("owner")
        assert PermissionChecker.can_view_audit("admin")
        assert not PermissionChecker.can_view_audit("developer")


class TestPermissionCheckerModes:
    """测试 local/saas 模式切换。"""

    def test_local_mode_default_project(self):
        checker = PermissionChecker(
            mode="local",
            default_project_id="proj_default",
            default_workspace_id="ws_default",
        )
        ctx = checker.resolve_project_context()
        assert ctx["project_id"] == "proj_default"
        assert ctx["workspace_id"] == "ws_default"
        assert ctx["mode"] == "local"

    def test_local_mode_explicit_project(self):
        checker = PermissionChecker(mode="local")
        ctx = checker.resolve_project_context(project_id="proj_123")
        assert ctx["project_id"] == "proj_123"

    def test_saas_mode_rejects_empty_project(self):
        checker = PermissionChecker(mode="saas")
        try:
            checker.resolve_project_context(project_id="")
            assert False, "Should raise"
        except PermissionError:
            pass

    def test_saas_mode_accepts_project(self):
        checker = PermissionChecker(mode="saas")
        ctx = checker.resolve_project_context(project_id="proj_abc", workspace_id="ws_abc")
        assert ctx["project_id"] == "proj_abc"
        assert ctx["workspace_id"] == "ws_abc"
