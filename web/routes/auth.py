"""Auth API 路由 — /api/auth/*"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


def register_auth_routes(app: FastAPI) -> None:
    @app.post("/api/auth/register")
    async def api_register(request: Request):
        body = await request.json()
        try:
            from stable_agent.saas.auth import AuthManager
            from stable_agent.saas.repository import SaasRepository
            auth = AuthManager(SaasRepository())
            user = auth.register(body["email"], body["password"], body.get("name", ""))
            token = auth.login(body["email"], body["password"])
            return {"user_id": user.id, "email": user.email, "token": token}
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=409)
        except Exception as e:
            return {"error": str(e)}

    @app.post("/api/auth/login")
    async def api_login(request: Request):
        body = await request.json()
        try:
            from stable_agent.saas.auth import AuthManager
            from stable_agent.saas.repository import SaasRepository
            auth = AuthManager(SaasRepository())
            token = auth.login(body["email"], body["password"])
            user = auth.get_current_user(token)
            return {"token": token, "email": user.email if user else body["email"]}
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

    @app.get("/api/auth/me")
    async def api_me(request: Request):
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if not token:
            return JSONResponse({"error": "未提供 token"}, status_code=401)
        try:
            from stable_agent.saas.auth import AuthManager
            from stable_agent.saas.repository import SaasRepository
            auth = AuthManager(SaasRepository())
            user = auth.get_current_user(token)
            if user is None:
                return JSONResponse({"error": "token 无效或已过期"}, status_code=401)
            return {"user_id": user.id, "email": user.email, "name": user.name}
        except Exception as e:
            return {"error": str(e)}
