"""测试 BadCase → RegressionCase 转换。"""

from stable_agent.models import BadCase, EvaluationResult, TaskType
from stable_agent.saas.repository import SaasRepository
from stable_agent.saas.regression_service import RegressionService


class TestRegressionFromBadCase:
    """测试 BadCase → RegressionCase 完整链路。"""

    def test_create_regression_from_bad_case_object(self):
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        svc = RegressionService(repo)

        eval_result = EvaluationResult(
            overall_score=0.3,
            failure_attribution={
                "failed_stage": "memory.retrieval",
                "reason": "检索到无关记忆",
                "step_index": 3,
            },
        )
        bad_case = BadCase(
            id="bc_test_001",
            task_type=TaskType.BUG_FIX,
            input_context="修复登录页面的Bug",
            output="TODO: 待修复",
            evaluation=eval_result,
            failure_reason="完成度不足",
            tags=["eval", "bug"],
            source_run_id="run_001",
        )

        reg_case = svc.create_from_bad_case(
            bad_case,
            workspace_id="ws_1",
            project_id="proj_1",
        )

        assert reg_case.id.startswith("reg_")
        assert reg_case.failure_mode == "memory.retrieval"
        assert reg_case.source_bad_case_id == "bc_test_001"
        assert reg_case.source_run_id == "run_001"
        assert reg_case.project_id == "proj_1"
        assert "修复登录页面" in reg_case.task_input

    def test_create_regression_from_bad_case_dict(self):
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        svc = RegressionService(repo)

        bad_case_dict = {
            "id": "bc_dict_001",
            "workspace_id": "ws_1",
            "project_id": "proj_1",
            "input_context": "fix navbar CSS",
            "failure_reason": "format quality low",
            "source_run_id": "run_002",
            "tags": ["css", "ui"],
            "overall_score": 0.25,
            "failure_attribution": {"failed_stage": "plan", "reason": "no design"},
        }

        reg_case = svc.create_from_bad_case_dict(bad_case_dict)
        assert reg_case is not None
        assert reg_case.failure_mode == "plan"
        assert reg_case.source_bad_case_id == "bc_dict_001"

    def test_list_regression_cases(self):
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        svc = RegressionService(repo)

        eval_result = EvaluationResult(overall_score=0.2)
        bc1 = BadCase(
            id="bc_list_1",
            task_type=TaskType.CODE_GENERATION,
            input_context="task 1",
            output="bad",
            evaluation=eval_result,
            tags=["tag1"],
        )
        bc2 = BadCase(
            id="bc_list_2",
            task_type=TaskType.UI_DESIGN,
            input_context="task 2",
            output="bad",
            evaluation=eval_result,
            tags=["tag2"],
        )

        svc.create_from_bad_case(bc1, workspace_id="ws_1", project_id="proj_1")
        svc.create_from_bad_case(bc2, workspace_id="ws_1", project_id="proj_1")

        cases = svc.list_cases("proj_1")
        assert len(cases) == 2

    def test_regression_case_has_expected_behavior(self):
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        svc = RegressionService(repo)

        eval_result = EvaluationResult(
            overall_score=0.3,
            failure_attribution={"failed_stage": "execute", "reason": "tool error"},
        )
        bc = BadCase(
            id="bc_expected",
            task_type=TaskType.BUG_FIX,
            input_context="生产环境数据库连接失败",
            output="error",
            evaluation=eval_result,
            failure_reason="执行阶段工具错误",
        )

        reg = svc.create_from_bad_case(bc, workspace_id="ws_1", project_id="proj_1")
        assert "execute" in reg.expected_behavior
        assert "tool error" in reg.expected_behavior or "工具错误" in reg.expected_behavior

    def test_to_validation_cases(self):
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        svc = RegressionService(repo)

        eval_result = EvaluationResult(overall_score=0.2)
        bc = BadCase(
            id="bc_val_1",
            task_type=TaskType.GENERAL_QA,
            input_context="what is Python?",
            output="bad answer",
            evaluation=eval_result,
        )
        svc.create_from_bad_case(bc, workspace_id="ws_1", project_id="proj_1")

        val_cases = svc.to_validation_cases("proj_1")
        assert len(val_cases) == 1
        assert "id" in val_cases[0]
        assert "task_input" in val_cases[0]
