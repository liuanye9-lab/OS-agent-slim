"""测试 Repository 显式错误 (Phase 6+12)。

验证:
1. Repository 写失败抛显式错误
2. 查询不存在返回 None
3. 不静默吞异常
"""

import pytest
from stable_agent.saas.errors import (
    SaasError, RepositoryError, NotFoundError,
    ConflictError, PermissionDeniedError, ValidationError,
)
from stable_agent.saas.models import Workspace, Project
from stable_agent.saas.repository import SaasRepository


class TestRepositoryErrors:
    """Repository 显式错误测试。"""

    def test_error_hierarchy(self):
        """验证异常层次结构。"""
        err = RepositoryError("测试错误")
        assert isinstance(err, SaasError)
        assert isinstance(err, Exception)
        assert str(err) == "测试错误"
        assert hasattr(err, "details")

    def test_not_found_error(self):
        err = NotFoundError("workspace 不存在", details={"ws_id": "ws_001"})
        assert isinstance(err, SaasError)
        assert err.details == {"ws_id": "ws_001"}

    def test_conflict_error(self):
        err = ConflictError("workspace 名称重复")
        assert isinstance(err, SaasError)

    def test_permission_denied_error(self):
        err = PermissionDeniedError("需要 admin 权限")
        assert isinstance(err, SaasError)

    def test_validation_error(self):
        err = ValidationError("name 字段不能为空")
        assert isinstance(err, SaasError)

    def test_create_workspace_raises_on_failure(self):
        """创建失败应抛 RepositoryError。"""
        repo = SaasRepository(db_path=":memory:")
        ws = Workspace(id="ws_001", name="测试")

        # 第一次应该成功
        result = repo.create_workspace(ws)
        assert result is True

        # 第二次（重复 ID）应该抛 RepositoryError
        with pytest.raises(RepositoryError) as exc:
            repo.create_workspace(ws)
        assert "创建" in str(exc.value) or "workspace" in str(exc.value).lower()

    def test_create_project_raises_on_failure(self):
        """创建项目失败应抛 RepositoryError。"""
        repo = SaasRepository(db_path=":memory:")
        proj = Project(id="proj_001", workspace_id="ws_001", name="测试项目")

        result = repo.create_project(proj)
        assert result is True

        with pytest.raises(RepositoryError):
            repo.create_project(proj)

    def test_get_workspace_returns_none_for_missing(self):
        """查询不存在返回 None。"""
        repo = SaasRepository(db_path=":memory:")
        result = repo.get_workspace("nonexistent")
        assert result is None

    def test_get_project_returns_none_for_missing(self):
        """查询不存在返回 None。"""
        repo = SaasRepository(db_path=":memory:")
        result = repo.get_project("nonexistent")
        assert result is None
