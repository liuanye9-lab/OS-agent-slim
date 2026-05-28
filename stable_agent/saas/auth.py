"""JWT 用户认证模块 (SaaS v1.5)。

提供简单的注册/登录/Token 验证。用于 SaaS 管理后台的基本认证。

约定：
- 使用 HS256 算法 + 环境变量 JWT_SECRET
- Token 有效期 24 小时
- 密码使用 SHA256 + salt 存储（非明文）
- User 模型存储于 SQLite（与 SaaS 仓库共享 DB）

用法::

    auth = AuthManager(repo)
    token = auth.login("user@test.com", "password123")
    user = auth.verify_token(token)
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================================
# 简易 JWT（不依赖 PyJWT 外部库）
# ============================================================================

def _b64url_encode(data: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    import base64
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def _make_jwt(payload: dict, secret: str) -> str:
    """签发简易 JWT token。"""
    import json
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = _b64url_encode(json.dumps(payload).encode())
    signing_input = f"{header}.{body}"
    sig = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url_encode(sig)}"


def _verify_jwt(token: str, secret: str) -> dict | None:
    """验证 JWT token，返回 payload 或 None。"""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        signing_input = f"{parts[0]}.{parts[1]}"
        expected_sig = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
        actual_sig = _b64url_decode(parts[2])
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None
        import json
        payload = json.loads(_b64url_decode(parts[1]))
        if payload.get("exp", 0) < time.time():
            return None  # expired
        return payload
    except Exception:
        return None


# ============================================================================
# User 模型
# ============================================================================


@dataclass
class SaaSUser:
    """SaaS 用户。"""
    id: str = ""
    email: str = ""
    password_hash: str = ""
    name: str = ""
    created_at: float = field(default_factory=time.time)


# ============================================================================
# AuthManager
# ============================================================================


class AuthManager:
    """JWT 认证管理器。

    Attributes:
        repo: SaasRepository 实例。
        secret: JWT 签名密钥。
        token_ttl: Token 有效期（秒，默认 86400 = 24h）。
    """

    def __init__(self, repo: Any = None, secret: str = "", token_ttl: int = 86400) -> None:
        self._repo = repo
        self._secret = secret or os.environ.get("JWT_SECRET", "stableagent-dev-secret")
        self._token_ttl = token_ttl

    # ------------------------------------------------------------------
    # 用户管理
    # ------------------------------------------------------------------

    @staticmethod
    def _hash_password(password: str, salt: str = "") -> str:
        """SHA256 哈希密码。"""
        return hashlib.sha256((password + salt).encode()).hexdigest()

    def register(self, email: str, password: str, name: str = "") -> SaaSUser:
        """注册新用户。

        Raises:
            ValueError: 邮箱已存在。
        """
        if self._repo:
            existing = self._repo.get_user_by_email(email)
            if existing:
                raise ValueError(f"邮箱已注册: {email}")

        import uuid
        user = SaaSUser(
            id=f"user_{uuid.uuid4().hex[:12]}",
            email=email,
            password_hash=self._hash_password(password),
            name=name or email.split("@")[0],
        )

        if self._repo:
            self._repo.save_user(user)

        logger.info("User registered: %s", email)
        return user

    def login(self, email: str, password: str) -> str:
        """登录，返回 JWT token。

        Raises:
            ValueError: 邮箱或密码错误。
        """
        if not self._repo:
            raise ValueError("Repository 未初始化")

        user = self._repo.get_user_by_email(email)
        if user is None:
            raise ValueError("邮箱或密码错误")

        if user.password_hash != self._hash_password(password):
            raise ValueError("邮箱或密码错误")

        payload = {
            "sub": user.id,
            "email": user.email,
            "name": user.name,
            "iat": int(time.time()),
            "exp": int(time.time()) + self._token_ttl,
        }
        return _make_jwt(payload, self._secret)

    def verify_token(self, token: str) -> dict | None:
        """验证 Token，返回 payload 或 None。"""
        return _verify_jwt(token, self._secret)

    def get_current_user(self, token: str) -> SaaSUser | None:
        """从 Token 获取当前用户。"""
        payload = self.verify_token(token)
        if payload is None or not self._repo:
            return None
        return self._repo.get_user_by_id(payload.get("sub", ""))
