"""Audit Log 审计日志模块。

记录所有高风险操作的不可变审计轨迹。

记录的事件类型：
- api_key_created / api_key_revoked
- mcp_tool_called / high_risk_tool_blocked
- approval_requested / approved / rejected
- skill_patch_created / validated / reviewed
- best_skill_exported
- project_deleted
- member_invited

约束：
- 所有高风险操作必须有 audit log
- 所有 skill 发布相关操作必须有 audit log
- audit log 不可被普通删除
"""

from __future__ import annotations

import logging
from typing import Any

from stable_agent.saas.models import (
    AuditEventType,
    AuditLogRecord,
    _new_id,
    _now,
)

logger = logging.getLogger(__name__)


class AuditLogger:
    """审计日志记录器。

    记录不可变的审计事件，用于合规和安全审计。

    Attributes:
        repository: SaasRepository 实例。
        actor: 默认执行者标识。
    """

    def __init__(self, repository: Any = None, actor: str = "system") -> None:
        self._repo = repository
        self.actor: str = actor

    # ------------------------------------------------------------------
    # 通用记录
    # ------------------------------------------------------------------

    def log(
        self,
        event_type: str,
        workspace_id: str = "",
        project_id: str = "",
        target: str = "",
        details: dict[str, Any] | None = None,
        severity: str = "info",
        actor: str | None = None,
    ) -> AuditLogRecord:
        """记录一条审计事件。

        Args:
            event_type: 事件类型（使用 AuditEventType 枚举值）。
            workspace_id: 所属工作空间 ID。
            project_id: 关联项目 ID。
            target: 操作目标。
            details: 事件详情。
            severity: 严重级别。
            actor: 执行者（默认使用实例 actor）。

        Returns:
            创建的 AuditLogRecord。
        """
        record = AuditLogRecord(
            id=_new_id("al"),
            workspace_id=workspace_id,
            project_id=project_id,
            event_type=event_type,
            actor=actor or self.actor,
            target=target,
            details=details or {},
            severity=severity,
            created_at=_now(),
        )

        if self._repo is not None:
            try:
                self._repo.save_audit_log(record)
            except Exception as e:
                logger.warning("Failed to persist audit log: %s", e)

        return record

    # ------------------------------------------------------------------
    # 便捷方法
    # ------------------------------------------------------------------

    def log_api_key_created(
        self, workspace_id: str, key_name: str, key_id: str, scopes: list[str],
    ) -> AuditLogRecord:
        return self.log(
            event_type=AuditEventType.API_KEY_CREATED.value,
            workspace_id=workspace_id,
            target=f"api_key:{key_id}",
            details={"key_name": key_name, "scopes": scopes},
        )

    def log_api_key_revoked(
        self, workspace_id: str, key_id: str,
    ) -> AuditLogRecord:
        return self.log(
            event_type=AuditEventType.API_KEY_REVOKED.value,
            workspace_id=workspace_id,
            target=f"api_key:{key_id}",
            severity="warning",
        )

    def log_mcp_tool_called(
        self, workspace_id: str, project_id: str, tool_name: str, run_id: str,
    ) -> AuditLogRecord:
        return self.log(
            event_type=AuditEventType.MCP_TOOL_CALLED.value,
            workspace_id=workspace_id,
            project_id=project_id,
            target=f"tool:{tool_name}",
            details={"run_id": run_id},
        )

    def log_high_risk_tool_blocked(
        self, workspace_id: str, project_id: str, tool_name: str, reason: str,
    ) -> AuditLogRecord:
        return self.log(
            event_type=AuditEventType.HIGH_RISK_TOOL_BLOCKED.value,
            workspace_id=workspace_id,
            project_id=project_id,
            target=f"tool:{tool_name}",
            details={"reason": reason},
            severity="critical",
        )

    def log_skill_patch_created(
        self, workspace_id: str, project_id: str, patch_id: str, skill_id: str,
    ) -> AuditLogRecord:
        return self.log(
            event_type=AuditEventType.SKILL_PATCH_CREATED.value,
            workspace_id=workspace_id,
            project_id=project_id,
            target=f"skill_patch:{patch_id}",
            details={"skill_id": skill_id},
        )

    def log_skill_patch_validated(
        self, workspace_id: str, project_id: str, patch_id: str, passed: bool, score_delta: float,
    ) -> AuditLogRecord:
        return self.log(
            event_type=AuditEventType.SKILL_PATCH_VALIDATED.value,
            workspace_id=workspace_id,
            project_id=project_id,
            target=f"skill_patch:{patch_id}",
            details={"passed": passed, "score_delta": score_delta},
        )

    def log_skill_patch_reviewed(
        self, workspace_id: str, project_id: str, patch_id: str, approved: bool, reviewer: str,
    ) -> AuditLogRecord:
        return self.log(
            event_type=AuditEventType.SKILL_PATCH_REVIEWED.value,
            workspace_id=workspace_id,
            project_id=project_id,
            target=f"skill_patch:{patch_id}",
            details={"approved": approved, "reviewer": reviewer},
            actor=reviewer,
        )

    def log_best_skill_exported(
        self, workspace_id: str, project_id: str, skill_id: str, version: str,
    ) -> AuditLogRecord:
        return self.log(
            event_type=AuditEventType.BEST_SKILL_EXPORTED.value,
            workspace_id=workspace_id,
            project_id=project_id,
            target=f"skill:{skill_id}",
            details={"version": version},
            severity="warning",  # 高风险：skill 发布到生产
        )

    def log_project_deleted(
        self, workspace_id: str, project_id: str, project_name: str,
    ) -> AuditLogRecord:
        return self.log(
            event_type=AuditEventType.PROJECT_DELETED.value,
            workspace_id=workspace_id,
            project_id=project_id,
            target=f"project:{project_id}",
            details={"project_name": project_name},
            severity="critical",
        )

    def log_member_invited(
        self, workspace_id: str, email: str, role: str,
    ) -> AuditLogRecord:
        return self.log(
            event_type=AuditEventType.MEMBER_INVITED.value,
            workspace_id=workspace_id,
            target=f"member:{email}",
            details={"role": role},
        )

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def list_recent(self, workspace_id: str, limit: int = 50) -> list[AuditLogRecord]:
        """获取最近的审计日志。"""
        if self._repo is None:
            return []
        try:
            return self._repo.list_audit_logs(workspace_id, limit)
        except Exception as e:
            logger.warning("list_recent failed: %s", e)
            return []
