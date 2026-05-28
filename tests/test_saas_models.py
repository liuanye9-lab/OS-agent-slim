"""测试 SaaS 数据模型。"""

from stable_agent.saas.models import (
    Workspace,
    Project,
    AgentRun,
    ApiKeyRecord,
    BadCaseRecord,
    EvalResultRecord,
    HumanReviewRecord,
    RegressionCaseRecord,
    SaasMode,
    SkillPatchRecord,
    SkillRecord,
    SkillVersionRecord,
    TraceEventRecord,
    UsageEventRecord,
    UsageEventType,
    ValidationRunRecord,
    WorkspaceMember,
    _new_id,
)


class TestWorkspaceProject:
    """测试 Workspace 和 Project 模型。"""

    def test_create_workspace(self):
        ws = Workspace(name="test-ws")
        assert ws.id.startswith("ws_")
        assert ws.name == "test-ws"
        assert ws.created_at > 0

    def test_create_project(self):
        proj = Project(workspace_id="ws_test", name="test-proj")
        assert proj.id.startswith("proj_")
        assert proj.workspace_id == "ws_test"
        assert proj.name == "test-proj"

    def test_project_belongs_to_workspace(self):
        ws = Workspace(name="team")
        proj = Project(workspace_id=ws.id, name="app")
        assert proj.workspace_id == ws.id

    def test_workspace_member_role(self):
        member = WorkspaceMember(workspace_id="ws_1", user_id="user_1", role="admin")
        assert member.role == "admin"
        assert member.workspace_id == "ws_1"


class TestAgentRun:
    """测试 AgentRun 归属。"""

    def test_agent_run_has_all_ids(self):
        run = AgentRun(
            run_id="run_001",
            workspace_id="ws_001",
            project_id="proj_001",
            agent_id="agent_001",
        )
        assert run.run_id == "run_001"
        assert run.workspace_id == "ws_001"
        assert run.project_id == "proj_001"
        assert run.agent_id == "agent_001"

    def test_agent_run_default_status_init(self):
        run = AgentRun(run_id="run_002")
        assert run.status == "init"


class TestTraceEvalBadCase:
    """测试 Trace/Eval/BadCase 归属。"""

    def test_trace_event_has_project(self):
        evt = TraceEventRecord(
            run_id="run_001",
            workspace_id="ws_1",
            project_id="proj_1",
            event_type="decision",
        )
        assert evt.run_id == "run_001"
        assert evt.project_id == "proj_1"

    def test_eval_result_has_project(self):
        result = EvalResultRecord(
            run_id="run_001",
            workspace_id="ws_1",
            project_id="proj_1",
            overall_score=0.85,
        )
        assert result.overall_score == 0.85
        assert result.project_id == "proj_1"

    def test_bad_case_has_project(self):
        bc = BadCaseRecord(
            workspace_id="ws_1",
            project_id="proj_1",
            run_id="run_001",
            task_type="bug_fix",
            input_context="fix bug",
            output="fixed",
            overall_score=0.3,
            failure_reason="low score",
        )
        assert bc.overall_score == 0.3
        assert bc.project_id == "proj_1"
        assert bc.id.startswith("bc_")


class TestRegressionCase:
    """测试 RegressionCase 模型。"""

    def test_regression_case_from_bad_case(self):
        rc = RegressionCaseRecord(
            workspace_id="ws_1",
            project_id="proj_1",
            task_input="fix login bug",
            expected_behavior="should provide complete fix",
            failure_mode="completion",
            source_run_id="run_001",
            source_bad_case_id="bc_001",
            overall_score=0.3,
        )
        assert rc.failure_mode == "completion"
        assert rc.source_bad_case_id == "bc_001"
        assert rc.id.startswith("reg_")


class TestSkillModels:
    """测试 Skill 相关模型。"""

    def test_skill_record(self):
        skill = SkillRecord(
            workspace_id="ws_1",
            project_id="proj_1",
            name="code-review",
            current_version="v2.0",
            content="# Code Review Skill\n...",
            score=0.92,
        )
        assert skill.name == "code-review"
        assert skill.score == 0.92
        assert skill.id.startswith("skill_")

    def test_skill_patch(self):
        patch = SkillPatchRecord(
            skill_id="skill_001",
            from_version="v1.0",
            to_version="v2.0",
            patch_content="+ Improved error handling",
            status="proposed",
        )
        assert patch.status == "proposed"
        assert patch.id.startswith("sp_")

    def test_skill_version(self):
        sv = SkillVersionRecord(
            skill_id="skill_001",
            version="v1.0",
            content="v1 content",
            score=0.85,
        )
        assert sv.version == "v1.0"


class TestValidationHumanReview:
    """测试 Validation 和 Human Review 模型。"""

    def test_validation_run(self):
        vr = ValidationRunRecord(
            patch_id="sp_001",
            baseline_score=0.80,
            candidate_score=0.85,
            score_delta=0.05,
            passed=True,
            explanation="Candidate is better.",
        )
        assert vr.passed is True
        assert vr.score_delta == 0.05

    def test_human_review(self):
        hr = HumanReviewRecord(
            workspace_id="ws_1",
            project_id="proj_1",
            target_type="skill_patch",
            target_id="sp_001",
            status="pending",
        )
        assert hr.target_type == "skill_patch"
        assert hr.status == "pending"


class TestApiKeyUsage:
    """测试 API Key 和 Usage 模型。"""

    def test_api_key_record(self):
        key = ApiKeyRecord(
            workspace_id="ws_1",
            key_hash="abc123hash",
            name="production-key",
        )
        assert key.key_hash == "abc123hash"
        assert key.revoked_at is None
        assert key.key_prefix == "sk_"

    def test_api_key_revoked(self):
        import time
        key = ApiKeyRecord(
            workspace_id="ws_1",
            key_hash="abc",
            revoked_at=time.time(),
        )
        assert key.revoked_at is not None

    def test_usage_event(self):
        evt = UsageEventRecord(
            workspace_id="ws_1",
            project_id="proj_1",
            run_id="run_001",
            event_type=UsageEventType.MCP_TOOL_CALLED,
            tokens_used=1500,
            cost_estimate=0.00045,
        )
        assert evt.tokens_used == 1500
        assert evt.event_type == "mcp_tool_called"
        assert evt.id.startswith("ue_")


class TestSaasMode:
    """测试 SaaS 运行模式。"""

    def test_local_mode(self):
        assert SaasMode.LOCAL == "local"

    def test_saas_mode(self):
        assert SaasMode.SAAS == "saas"

    def test_id_generation(self):
        id1 = _new_id("test")
        id2 = _new_id("test")
        assert id1.startswith("test_")
        assert id1 != id2
