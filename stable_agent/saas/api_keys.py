"""API Key 管理器。

提供 API Key 的创建、校验、撤销功能。

Key 格式：sk_ + 32 位 hex（如 sk_a1b2c3d4e5f6...）
存储时只保存 SHA256 哈希值，原始 key 仅在创建时返回一次。

用法::

    mgr = ApiKeyManager(repo)
    key_data = mgr.create_key(workspace_id="ws_xxx", name="my-key")
    # key_data["raw_key"] 只在此时可用，请妥善保存

    result = mgr.validate_key("sk_a1b2c3d4e5f6...")
    # result = {"workspace_id": "ws_xxx", "key_id": "ak_xxx"}
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from typing import Any

from stable_agent.saas.models import ApiKeyRecord, _new_id, _now
from stable_agent.saas.repository import SaasRepository

logger = logging.getLogger(__name__)

KEY_PREFIX = "sk_"
KEY_BYTES = 32  # 256-bit entropy


class ApiKeyManager:
    """API Key 管理器。

    Attributes:
        repo: SaaS 数据访问层实例。
    """

    def __init__(self, repo: SaasRepository | None = None) -> None:
        self.repo: SaasRepository = repo or SaasRepository()

    # ------------------------------------------------------------------
    # 创建
    # ------------------------------------------------------------------

    def create_key(self, workspace_id: str, name: str = "") -> dict[str, str]:
        """创建一个新的 API Key。

        生成格式：sk_ + 32字节 hex（共67字符）。
        原始 key 仅在返回值中出现一次，请妥善保存。

        Args:
            workspace_id: 工作空间 ID。
            name: Key 名称（便于识别）。

        Returns:
            {"raw_key": "sk_xxx", "key_id": "ak_xxx", "workspace_id": "ws_xxx"}

        Raises:
            ValueError: workspace_id 为空。
        """
        if not workspace_id:
            raise ValueError("workspace_id 不能为空")

        # 生成随机 key
        raw_key = KEY_PREFIX + secrets.token_hex(KEY_BYTES)
        key_hash = self._hash_key(raw_key)

        # 保存到数据库
        record = ApiKeyRecord(
            workspace_id=workspace_id,
            key_hash=key_hash,
            key_prefix=KEY_PREFIX,
            name=name,
        )
        ok = self.repo.create_api_key(record)
        if not ok:
            raise RuntimeError("API Key 创建失败，数据库写入错误")

        return {
            "raw_key": raw_key,
            "key_id": record.id,
            "workspace_id": workspace_id,
        }

    # ------------------------------------------------------------------
    # 校验
    # ------------------------------------------------------------------

    def validate_key(self, raw_key: str) -> dict[str, str] | None:
        """校验 API Key 是否有效。

        流程：
        1. 对 raw_key 做 SHA256 hash
        2. 查数据库
        3. 检查是否已撤销

        Args:
            raw_key: 原始 API Key（含 "sk_" 前缀）。

        Returns:
            {"workspace_id": "...", "key_id": "..."} 或 None（无效/已撤销）。
        """
        if not raw_key or not raw_key.startswith(KEY_PREFIX):
            return None

        key_hash = self._hash_key(raw_key)
        record = self.repo.get_api_key_by_hash(key_hash)

        if record is None:
            return None
        if record.revoked_at is not None:
            return None  # 已撤销

        return {
            "workspace_id": record.workspace_id,
            "key_id": record.id,
        }

    # ------------------------------------------------------------------
    # 撤销
    # ------------------------------------------------------------------

    def revoke_key(self, key_id: str) -> bool:
        """撤销一个 API Key。

        撤销后该 key 立即失效，无法恢复。

        Args:
            key_id: API Key ID。

        Returns:
            True 表示撤销成功。
        """
        return self.repo.revoke_api_key(key_id)

    # ------------------------------------------------------------------
    # 列表
    # ------------------------------------------------------------------

    def list_keys(self, workspace_id: str) -> list[dict[str, Any]]:
        """列出工作空间的所有 API Key。

        注意：不返回原始 key（只保存 hash）。

        Args:
            workspace_id: 工作空间 ID。

        Returns:
            API Key 元信息列表（不含 raw_key）。
        """
        keys = self.repo.list_api_keys(workspace_id)
        return [
            {
                "id": k.id,
                "workspace_id": k.workspace_id,
                "name": k.name,
                "created_at": k.created_at,
                "revoked_at": k.revoked_at,
                "is_active": k.revoked_at is None,
            }
            for k in keys
        ]

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    @staticmethod
    def _hash_key(raw_key: str) -> str:
        """对原始 key 做 SHA256 哈希。"""
        return hashlib.sha256(raw_key.encode()).hexdigest()
