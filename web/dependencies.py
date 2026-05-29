"""Web Dependencies — 安全上下文 & 权限 Guard。

提供请求级安全上下文提取和权限校验。
优先保护敏感 API (api-keys, reviews, approvals, projects)。

规则:
- STABLE_AGENT_MODE=local → 本地开发默认放行
- STABLE_AGENT_MODE=saas → 必须鉴权 (JWT token 或 API Key)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from fastapi import Depends, Request, HTTPException


@dataclass
class SecurityContext:
    """请求级安全上下文。"""
    user_id: str = ""
    workspace_id: str = ""
    project_id: str = ""
    role: str = "viewer"
    api_key_id: str = ""
    scopes: list[str] = field(default_factory=list)
    mode: str = "local"


def get_security_context(request: Request) -> SecurityContext:
    """从请求中提取安全上下文。

    优先级: API Key > JWT token > local fallback
    """
    mode = os.environ.get("STABLE_AGENT_MODE", "local")

    # Local mode: default access
    if mode == "local":
        return SecurityContext(mode="local", role="admin")

    # SaaS mode: extract from headers
    api_key = request.headers.get("X-API-Key", "")
    auth_header = request.headers.get("Authorization", "")

    if api_key:
        try:
            from stable_agent.saas import ApiKeyManager, SaasRepository
            mgr = ApiKeyManager(SaasRepository())
            valid = mgr.validate_key(api_key)
            if valid:
                return SecurityContext(
                    mode="saas", api_key_id=api_key[:8],
                    role="developer", scopes=["runs:write", "runs:read"],
                )
        except Exception:
            pass

    if auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "")
        try:
            from stable_agent.saas.auth import AuthManager
            from stable_agent.saas.repository import SaasRepository
            auth = AuthManager(SaasRepository())
            user = auth.get_current_user(token)
            if user:
                return SecurityContext(
                    mode="saas", user_id=user.id, role="developer",
                )
        except Exception:
            pass

    return SecurityContext(mode=os.environ.get("STABLE_AGENT_MODE", "local"), role="viewer")


def require_role(roles: list[str]):
    """权限 Guard: 要求指定角色。"""
    def _guard(ctx: SecurityContext = Depends(get_security_context)):
        if ctx.mode == "local":
            return ctx
        if ctx.role not in roles:
            raise HTTPException(status_code=403, detail=f"需要角色: {roles}")
        return ctx
    return _guard


def require_api_key_scope(scope: str):
    """权限 Guard: 要求 API Key 指定 scope。"""
    def _guard(ctx: SecurityContext = Depends(get_security_context)):
        if ctx.mode == "local":
            return ctx
        if scope not in ctx.scopes:
            raise HTTPException(status_code=403, detail=f"需要 scope: {scope}")
        return ctx
    return _guard


def require_project_access(project_id: str, ctx: SecurityContext = Depends(get_security_context)):
    """权限 Guard: 要求项目级访问权。"""
    if ctx.mode == "local":
        return ctx
    if ctx.project_id and ctx.project_id != project_id:
        raise HTTPException(status_code=403, detail="无此项目访问权限")
    return ctx


def get_current_user(ctx: SecurityContext = Depends(get_security_context)) -> SecurityContext:
    if ctx.mode == "local":
        return ctx
    if not ctx.user_id and not ctx.api_key_id:
        raise HTTPException(status_code=401, detail="未认证")
    return ctx
