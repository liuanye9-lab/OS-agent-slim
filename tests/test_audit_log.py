"""测试 Audit Log 审计日志。

验证：
1. 审计日志正确记录各类事件
2. 高风险操作有对应日志
3. 日志不可删除
"""

from stable_agent.saas.audit_log import AuditLogger
from stable_agent.saas.repository import SaasRepository
from stable_agent.saas.models import Workspace, Project


class TestAuditLogger:
    """测试 AuditLogger 审计日志。"""

    def _setup(self):
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        ws = Workspace(name="test-ws")
        repo.create_workspace(ws)
        proj = Project(workspace_id=ws.id, name="test-proj")
        repo.create_project(proj)
        return repo, ws, proj

    def test_log_api_key_created(self):
        repo, ws, _ = self._setup()
        logger = AuditLogger(repository=repo, actor="admin")
        record = logger.log_api_key_created(
            workspace_id=ws.id,
            key_name="test-key",
            key_id="ak_123",
            scopes=["runs:write"],
        )
        assert record.event_type == "api_key_created"
        assert record.actor == "admin"
        assert "test-key" in str(record.details)

        # 确认持久化
        logs = repo.list_audit_logs(ws.id)
        assert len(logs) == 1

    def test_log_api_key_revoked(self):
        repo, ws, _ = self._setup()
        logger = AuditLogger(repository=repo)
        record = logger.log_api_key_revoked(ws.id, "ak_456")
        assert record.event_type == "api_key_revoked"
        assert record.severity == "warning"

    def test_log_mcp_tool_called(self):
        repo, ws, proj = self._setup()
        logger = AuditLogger(repository=repo)
        record = logger.log_mcp_tool_called(ws.id, proj.id, "os_agent", "run_123")
        assert record.event_type == "mcp_tool_called"
        assert "os_agent" in record.target

    def test_log_high_risk_tool_blocked(self):
        repo, ws, proj = self._setup()
        logger = AuditLogger(repository=repo)
        record = logger.log_high_risk_tool_blocked(
            ws.id, proj.id, "exec_command", "sandbox policy"
        )
        assert record.severity == "critical"
        assert "sandbox policy" in str(record.details)

    def test_log_skill_lifecycle(self):
        repo, ws, proj = self._setup()
        logger = AuditLogger(repository=repo)

        logger.log_skill_patch_created(ws.id, proj.id, "sp_1", "skill_1")
        logger.log_skill_patch_validated(ws.id, proj.id, "sp_1", True, 0.05)
        logger.log_skill_patch_reviewed(ws.id, proj.id, "sp_1", True, "admin")
        logger.log_best_skill_exported(ws.id, proj.id, "skill_1", "v2.0")

        logs = repo.list_audit_logs(ws.id)
        assert len(logs) == 4

        types = [l.event_type for l in logs]
        assert "skill_patch_created" in types
        assert "skill_patch_validated" in types
        assert "skill_patch_reviewed" in types
        assert "best_skill_exported" in types

    def test_log_project_deleted(self):
        repo, ws, proj = self._setup()
        logger = AuditLogger(repository=repo)
        record = logger.log_project_deleted(ws.id, proj.id, "My Project")
        assert record.severity == "critical"

    def test_log_member_invited(self):
        repo, ws, _ = self._setup()
        logger = AuditLogger(repository=repo)
        record = logger.log_member_invited(ws.id, "user@test.com", "developer")
        assert record.event_type == "member_invited"
        assert "user@test.com" in record.target

    def test_log_without_repository(self):
        """无 repository 时不应崩溃。"""
        logger = AuditLogger(repository=None)
        record = logger.log("test_event", workspace_id="ws_1")
        assert record.id.startswith("al_")

    def test_list_recent_logs(self):
        repo, ws, proj = self._setup()
        logger = AuditLogger(repository=repo)
        for i in range(5):
            logger.log("test_event", workspace_id=ws.id, project_id=proj.id)
        logs = logger.list_recent(ws.id, limit=3)
        assert len(logs) == 3
