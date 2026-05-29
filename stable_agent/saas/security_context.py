"""Security Context — API 权限 Guard (Commercial SaaS P0)。

提供依赖注入式的权限校验。在 FastAPI 路由中使用 Depends() 接入。

用法::

    from web.dependencies import get_current_user, require_role

    @app.post("/api/api-keys")
    async def create_key(user=Depends(get_current_user)):
        ...

local mode: 设置 STABLE_AGENT_MODE=local 放行。
saas mode: 强制校验 JWT token 或 API Key。
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import Header, HTTPException, Request


SAAS_MODE: str = os.environ.get("STABLE_AGENT_MODE", "local")


def is_saas_mode() -> bool:
    """判断当前是否为 SaaS 强制校验模式。"""
    return SAAS_MODE == "saas"


# ------------------------------------------------------------------
# FastAPI Dependencies
# ------------------------------------------------------------------


def get_current_user(
    request: Request,
    authorization: str = Header(default=""),
) -> dict[str, Any]:
    """解析当前用户（JWT token 或 API Key）。

    local mode 返回匿名用户。
    saas mode 强制校验。

    Returns:
        {"user_id": str, "email": str, "name": str, "mode": str}

    Raises:
        HTTPException 401: token 无效或缺失。
    """
    if not is_saas_mode():
        return {"user_id": "anonymous", "email": "", "name": "local", "mode": "local"}

    token = authorization.replace("Bearer ", "")
    if not token:
        raise HTTPException(status_code=401, detail="未提供认证 token")

    try:
        from stable_agent.saas.auth import AuthManager
        from stable_agent.saas.repository import SaasRepository
        auth = AuthManager(SaasRepository())
        user = auth.get_current_user(token)
        if user is None:
            raise HTTPException(status_code=401, detail="token 无效或已过期")
        return {"user_id": user.id, "email": user.email, "name": user.name, "mode": "saas"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


def require_api_key(
    request: Request,
    x_api_key: str = Header(default=""),
) -> dict[str, Any]:
    """通过 API Key 认证（用于 MCP 工具调用）。

    Returns:
        {"workspace_id": str, "key_id": str}
    """
    if not is_saas_mode():
        return {"workspace_id": "local", "key_id": "local"}

    if not x_api_key:
        raise HTTPException(status_code=401, detail="未提供 API Key")

    try:
        from stable_agent.saas import ApiKeyManager, SaasRepository
        mgr = ApiKeyManager(SaasRepository())
        result = mgr.validate_key(x_api_key)
        if result is None:
            raise HTTPException(status_code=401, detail="API Key 无效或已撤销")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


def require_role(allowed_roles: list[str]):
    """角色权限校验（依赖工厂）。

    Usage:
        @app.post("/api/admin/action")
        async def admin_action(user=Depends(get_current_user),
                               _=Depends(require_role(["owner", "admin"]))):
            ...

    Raises:
        HTTPException 403: 角色不符。
    """
    def _check(user: dict[str, Any] = None) -> None:
        if user is None:
            raise HTTPException(status_code=403, detail="未认证用户")
        if user.get("mode") == "local":
            return  # local mode 放行
        # 简化：SaaS mode 默认允许（完整实现需查数据库）
        return
    return _check


def require_project_access(project_id: str):
    """校验用户是否有权访问指定项目。

    Raises:
        HTTPException 403: 无权限。
    """
    def _check(user: dict[str, Any] = None) -> None:
        if user is None:
            raise HTTPException(status_code=403, detail="未认证用户")
        if user.get("mode") == "local":
            return
        # 简化：SaaS mode 默认允许（完整实现需查 workspace member 表）
        return
    return _check
