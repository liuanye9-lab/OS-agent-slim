"""权限校验模块。

根据 SaaS 模式决定 project_id 是否必填。

local 模式：project_id 可选，fallback 到 default project
saas 模式：project_id 必填，且需验证 API Key
"""

from __future__ import annotations

import logging
from typing import Any

from stable_agent.saas.models import SaasMode

logger = logging.getLogger(__name__)


class PermissionChecker:
    """权限校验器。

    根据 SaaS 运行模式决定权限校验策略。

    Attributes:
        mode: SaaS 运行模式。
        default_project_id: local 模式下的 fallback project_id。
        default_workspace_id: local 模式下的 fallback workspace_id。
    """

    def __init__(
        self,
        mode: str = "local",
        default_project_id: str = "",
        default_workspace_id: str = "",
    ) -> None:
        self.mode: str = mode
        self.default_project_id: str = default_project_id
        self.default_workspace_id: str = default_workspace_id

    # ------------------------------------------------------------------
    # project_id 校验
    # ------------------------------------------------------------------

    def resolve_project_context(
        self,
        project_id: str = "",
        workspace_id: str = "",
    ) -> dict[str, str]:
        """解析并校验 project context。

        Args:
            project_id: 项目 ID。
            workspace_id: 工作空间 ID。

        Returns:
            {"project_id": "...", "workspace_id": "...", "mode": "..."}

        Raises:
            PermissionError: SaaS 模式且 project_id 无效时抛出。
        """
        result: dict[str, str] = {"mode": self.mode}

        if self.mode == SaasMode.LOCAL:
            # local 模式：fallback 到 default
            result["project_id"] = project_id or self.default_project_id
            result["workspace_id"] = workspace_id or self.default_workspace_id
            return result

        # SaaS 模式：project_id 强校验
        if not project_id:
            raise PermissionError(
                "SaaS 模式下 project_id 为必填参数。"
                "请在 tools/call 请求中提供有效的 project_id。"
            )
        result["project_id"] = project_id
        result["workspace_id"] = workspace_id
        return result

    # ------------------------------------------------------------------
    # API Key 校验
    # ------------------------------------------------------------------

    def check_api_key(
        self,
        api_key: str | None = None,
        api_key_manager: Any = None,
    ) -> str:
        """校验 API Key 并返回对应的 workspace_id。

        local 模式：跳过校验
        saas 模式：必须有有效 API Key

        Args:
            api_key: API Key 字符串（已含前缀如 "sk_"）。
            api_key_manager: ApiKeyManager 实例。

        Returns:
            对应的 workspace_id。

        Raises:
            PermissionError: API Key 无效。
        """
        if self.mode == SaasMode.LOCAL:
            return self.default_workspace_id

        if not api_key:
            raise PermissionError("SaaS 模式下需要 API Key。请在请求头中提供 X-API-Key。")

        if api_key_manager is None:
            raise PermissionError("API Key 管理器未初始化。")

        result = api_key_manager.validate_key(api_key)
        if result is None:
            raise PermissionError("API Key 无效或已撤销。")

        return result["workspace_id"]

    # ------------------------------------------------------------------
    # 模式查询
    # ------------------------------------------------------------------

    def is_saas_mode(self) -> bool:
        """是否为 SaaS 模式。"""
        return self.mode == SaasMode.SAAS

    def is_local_mode(self) -> bool:
        """是否为 local 模式。"""
        return self.mode == SaasMode.LOCAL
