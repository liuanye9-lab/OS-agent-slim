"""测试用量计数器。"""

from stable_agent.saas.repository import SaasRepository
from stable_agent.saas.usage import UsageCounter, UsageEventType


class TestUsageCounter:
    """测试 UsageCounter 记录和查询。"""

    def test_record_mcp_tool_called(self):
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        counter = UsageCounter(repo)

        evt = counter.record_mcp_tool_called(
            workspace_id="ws_1",
            project_id="proj_1",
            run_id="run_001",
            tool_name="stableagent.task.os_agent",
        )
        assert evt is not None
        assert evt.event_type == "mcp_tool_called"
        assert evt.metadata["tool_name"] == "stableagent.task.os_agent"

    def test_record_run_created(self):
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        counter = UsageCounter(repo)

        evt = counter.record_run_created("ws_1", "proj_1", "run_001")
        assert evt is not None
        assert evt.event_type == UsageEventType.RUN_CREATED

    def test_record_eval_executed(self):
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        counter = UsageCounter(repo)

        evt = counter.record_eval_executed("ws_1", "proj_1", "run_001", tokens_used=500)
        assert evt is not None
        assert evt.tokens_used == 500
        assert evt.event_type == UsageEventType.EVAL_EXECUTED

    def test_record_token_used(self):
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        counter = UsageCounter(repo)

        evt = counter.record_token_used("ws_1", "proj_1", "run_001", tokens_used=2000)
        assert evt is not None
        assert evt.tokens_used == 2000
        # cost should be auto-calculated
        assert evt.cost_estimate > 0

    def test_record_skill_validation(self):
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        counter = UsageCounter(repo)

        evt = counter.record_skill_validation("ws_1", "proj_1", "run_001")
        assert evt is not None
        assert evt.event_type == UsageEventType.SKILL_VALIDATION_RUN

    def test_record_skill_exported(self):
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        counter = UsageCounter(repo)

        evt = counter.record_skill_exported("ws_1", "proj_1", "run_001")
        assert evt is not None
        assert evt.event_type == UsageEventType.SKILL_EXPORTED

    def test_get_summary(self):
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        counter = UsageCounter(repo)

        counter.record_token_used("ws_1", "proj_1", "run_001", tokens_used=1000)
        counter.record_token_used("ws_1", "proj_1", "run_001", tokens_used=500)

        summary = counter.get_summary("proj_1")
        assert summary["total_events"] == 2
        assert summary["total_tokens"] == 1500

    def test_estimate_cost(self):
        cost = UsageCounter.estimate_cost(UsageEventType.TOKEN_USED, 1000)
        assert cost > 0
        # ~0.0006 per 1K tokens output rate
        assert 0.0003 <= cost <= 0.001
