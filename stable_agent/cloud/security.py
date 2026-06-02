"""stable_agent.cloud.security — 最小 API Token 验证。

通过 STABLEAGENT_CLOUD_TOKEN 环境变量启用 Bearer Token 认证。
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def create_auth_dependency(token: str):
    """创建 FastAPI 依赖项，用于验证 Bearer Token。

    如果 token 为空字符串，则跳过验证。
    """
    async def verify_token(request: Request) -> None:
        if not token:
            return  # 未设置 token，跳过验证
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing Authorization header")
        provided = auth[7:].strip()
        if provided != token:
            raise HTTPException(status_code=403, detail="Invalid token")

    return verify_token


def create_auth_middleware(token: str):
    """创建中间件用于 worker API 路径验证。"""
    # 返回一个简单的验证函数供路由使用
    async def check_auth(request: Request) -> None:
        if not token:
            return
        # Dashboard 页面不强制验证
        path = request.url.path
        if path.startswith("/slim") or path == "/":
            return
        if path.startswith("/api/"):
            auth = request.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                raise HTTPException(status_code=401, detail="Missing Authorization header")
            provided = auth[7:].strip()
            if provided != token:
                raise HTTPException(status_code=403, detail="Invalid token")

    return check_auth
