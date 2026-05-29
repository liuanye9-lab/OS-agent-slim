"""SaaS 错误类型 (Commercial SaaS P0)。

定义商业级异常层次，替代裸 False/None 返回值。
Repository 层关键写入操作失败必须抛显式错误。

用法::

    from stable_agent.saas.errors import RepositoryError, NotFoundError
    if not ok:
        raise RepositoryError("workspace 创建失败", details={"workspace_id": ws_id})
"""

from __future__ import annotations


class SaasError(Exception):
    """SaaS 基础异常。"""
    def __init__(self, message: str = "", details: dict | None = None) -> None:
        super().__init__(message)
        self.details: dict = details or {}


class RepositoryError(SaasError):
    """数据库写入/查询失败。"""
    pass


class NotFoundError(SaasError):
    """资源不存在。"""
    pass


class ConflictError(SaasError):
    """资源冲突（如重复创建）。"""
    pass


class PermissionDeniedError(SaasError):
    """权限不足。"""
    pass


class ValidationError(SaasError):
    """数据验证失败。"""
    pass


class ApprovalRequiredError(SaasError):
    """高风险操作需要审批。"""
    pass


class RateLimitExceededError(SaasError):
    """速率限制超限。"""
    pass
