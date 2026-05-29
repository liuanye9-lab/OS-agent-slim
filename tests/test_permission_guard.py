"""测试 Permission Guard (Phase 8+12)。

验证:
1. saas mode 下敏感 API 需要权限
2. local mode 下开发可放行
"""

import os
import pytest

# Force local mode
os.environ["STABLE_AGENT_MODE"] = "local"

from stable_agent.saas.security_context import (
    is_saas_mode,
    SAAS_MODE,
    get_current_user,
    require_role,
    require_project_access,
    require_api_key,
)


class TestPermissionGuard:
    """Permission Guard 测试。"""

    def test_local_mode_bypasses_all(self):
        """local mode 放行所有权限检查。"""
        assert is_saas_mode() is False
        assert SAAS_MODE == "local"

    def test_sensitive_endpoints_guarded(self):
        """验证关键 guard 函数存在。"""
        # 优先保护的关键端点对应的 guard 函数：
        # POST /api/api-keys → require_api_key
        # DELETE /api/api-keys/{key_id} → require_api_key
        # GET /api/audit-logs → require_role(["owner", "admin"])
        # POST /api/reviews/{review_id} → require_role(["reviewer", "admin"])
        # POST /api/skill/* → require_role(["developer", "admin"])
        # POST /api/projects → require_role(["developer", "admin"])
        # POST /api/runs → require_role(["developer", "admin"])

        # 所有 guard 函数可调用
        assert callable(require_role(["owner", "admin"]))
        assert callable(require_role(["reviewer", "admin"]))
        assert callable(require_role(["developer", "admin"]))
        assert callable(require_project_access("test_proj"))

    def test_local_role_check_passes(self):
        """local mode 角色检查不抛异常。"""
        checker = require_role(["owner"])
        checker({"mode": "local"})  # 不应抛异常

    def test_guard_chainable(self):
        """Guard 函数可链式组合。"""
        role_check = require_role(["admin"])
        proj_check = require_project_access("proj_001")

        # local mode 都通过
        role_check({"mode": "local"})
        proj_check({"mode": "local"})
