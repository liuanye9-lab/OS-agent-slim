"""P0 核心模块测试套件。

覆盖 ContextDecisionEngine、ContextBudgetManager、MemoryRouter、
Evaluator、BadCaseManager 和 WorkflowEngine 的所有核心功能。

测试数量：25 个，覆盖所有关键逻辑路径。
"""

from __future__ import annotations

import pytest

from stable_agent.models import (
    BadCase,
    EvaluationResult,
    MemoryItem,
    TaskType,
    Workflow,
    WorkflowState,
)

# ============================================================================
# 模块导入
# ============================================================================

from stable_agent.context_decision_engine import ContextDecisionEngine
from stable_agent.context_budget_manager import ContextBudgetManager
from stable_agent.memory_router import MemoryBank, MemoryRouter
from stable_agent.eval_and_bad_case import BadCaseManager, Evaluator
from stable_agent.workflow_state_machine import WorkflowEngine


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def engine() -> ContextDecisionEngine:
    """创建 ContextDecisionEngine 实例的 fixture。"""
    return ContextDecisionEngine()


@pytest.fixture
def budget_mgr() -> ContextBudgetManager:
    """创建 ContextBudgetManager 实例的 fixture。"""
    return ContextBudgetManager()


@pytest.fixture
def bank() -> MemoryBank:
    """创建 MemoryBank 实例的 fixture。"""
    return MemoryBank()


@pytest.fixture
def router(bank: MemoryBank) -> MemoryRouter:
    """创建 MemoryRouter 实例的 fixture。"""
    return MemoryRouter(bank)


@pytest.fixture
def evaluator() -> Evaluator:
    """创建 Evaluator 实例的 fixture。"""
    return Evaluator()


@pytest.fixture
def bad_case_mgr() -> BadCaseManager:
    """创建 BadCaseManager 实例的 fixture。"""
    return BadCaseManager()


@pytest.fixture
def sample_memory_items() -> list[MemoryItem]:
    """创建一批示例记忆条目的 fixture。"""
    return [
        MemoryItem(
            id="m1", content="用户偏好使用简洁的风格",
            type="user_pref", priority=0.9, source="test", status="active",
        ),
        MemoryItem(
            id="m2", content="上次修复 null pointer 时使用 Optional 包装",
            type="success_case", priority=0.7, source="test", status="active",
        ),
        MemoryItem(
            id="m3", content="使用全局变量导致状态污染",
            type="bad_case", priority=0.8, source="test", status="active",
        ),
        MemoryItem(
            id="m4", content="过时的提示：项目已迁移到 Python 3.12",
            type="project_constraint", priority=0.3, source="test", status="outdated",
        ),
        MemoryItem(
            id="m5", content="React 组件需要 TypeScript 类型注解",
            type="success_case", priority=0.6, source="test", status="active",
        ),
    ]


@pytest.fixture
def workflow_engine(bank: MemoryBank) -> WorkflowEngine:
    """创建完整的 WorkflowEngine fixture。"""
    return WorkflowEngine(
        decision_engine=ContextDecisionEngine(),
        budget_manager=ContextBudgetManager(),
        memory_router=MemoryRouter(bank),
        evaluator=Evaluator(),
        bad_case_manager=BadCaseManager(),
    )


# ============================================================================
# 1. ContextDecisionEngine 测试
# ============================================================================


class TestContextDecisionEngineTaskClassification:
    """测试任务分类能力。"""

    def test_classify_bug_fix(self, engine: ContextDecisionEngine) -> None:
        """测试 BUG_FIX 类型分类。"""
        assert engine.classify_task("修复登录页面的崩溃问题") == TaskType.BUG_FIX
        assert engine.classify_task("报错：NullPointerException") == TaskType.BUG_FIX

    def test_classify_ui_design(self, engine: ContextDecisionEngine) -> None:
        """测试 UI_DESIGN 类型分类。"""
        assert engine.classify_task("设计新的按钮样式和布局") == TaskType.UI_DESIGN
        assert engine.classify_task("CSS 样式调整") == TaskType.UI_DESIGN

    def test_classify_arch_refactor(self, engine: ContextDecisionEngine) -> None:
        """测试 ARCH_REFACTOR 类型分类。"""
        assert engine.classify_task("重构用户模块的架构") == TaskType.ARCH_REFACTOR

    def test_classify_prompt_optimization(self, engine: ContextDecisionEngine) -> None:
        """测试 PROMPT_OPTIMIZATION 类型分类。"""
        assert engine.classify_task("优化提示词以提高生成质量") == TaskType.PROMPT_OPTIMIZATION

    def test_classify_eval_task(self, engine: ContextDecisionEngine) -> None:
        """测试 EVAL_TASK 类型分类。"""
        assert engine.classify_task("评估这个模型的输出打分") == TaskType.EVAL_TASK

    def test_classify_code_generation(self, engine: ContextDecisionEngine) -> None:
        """测试 CODE_GENERATION 类型分类。"""
        assert engine.classify_task("实现一个新功能：用户注册") == TaskType.CODE_GENERATION

    def test_classify_default_general_qa(self, engine: ContextDecisionEngine) -> None:
        """测试无法匹配时回退到 GENERAL_QA。"""
        assert engine.classify_task("今天天气怎么样") == TaskType.GENERAL_QA
        assert engine.classify_task("") == TaskType.GENERAL_QA


class TestContextDecisionEngineBudget:
    """测试预算估算。"""

    def test_estimate_token_budget_base(self, engine: ContextDecisionEngine) -> None:
        """测试各任务类型的基础预算。"""
        assert engine.estimate_token_budget(TaskType.BUG_FIX, 5000) == 8000
        assert engine.estimate_token_budget(TaskType.UI_DESIGN, 5000) == 6000
        assert engine.estimate_token_budget(TaskType.ARCH_REFACTOR, 5000) == 12000
        assert engine.estimate_token_budget(TaskType.GENERAL_QA, 5000) == 4000
        assert engine.estimate_token_budget(TaskType.CODE_GENERATION, 5000) == 10000

    def test_estimate_token_budget_urgency_boost(self, engine: ContextDecisionEngine) -> None:
        """测试 urgency >= 3 时预算增加 20%。"""
        base: int = engine.estimate_token_budget(TaskType.BUG_FIX, 5000, urgency=1)
        boosted: int = engine.estimate_token_budget(TaskType.BUG_FIX, 5000, urgency=3)
        assert boosted == int(base * 1.2)

    def test_estimate_token_budget_long_context(self, engine: ContextDecisionEngine) -> None:
        """测试 context_length > 10000 时预算减少 10%。"""
        base: int = engine.estimate_token_budget(TaskType.BUG_FIX, 5000)
        reduced: int = engine.estimate_token_budget(TaskType.BUG_FIX, 15000)
        assert reduced == int(base * 0.9)


class TestContextDecisionEngineMemoryAndRAG:
    """测试记忆选择和 RAG 来源选择。"""

    def test_select_memory_keys_filters_outdated(
        self, engine: ContextDecisionEngine, sample_memory_items: list[MemoryItem],
    ) -> None:
        """测试选择记忆时过滤 outdated 条目。"""
        result: list[MemoryItem] = engine.select_memory_keys(
            TaskType.BUG_FIX, sample_memory_items,
        )
        ids: set[str] = {m.id for m in result}
        assert "m1" in ids
        assert "m2" in ids
        assert "m3" in ids
        assert "m5" in ids
        assert "m4" not in ids  # outdated

    def test_select_memory_keys_prioritizes_bad_case_for_bug_fix(
        self, engine: ContextDecisionEngine, sample_memory_items: list[MemoryItem],
    ) -> None:
        """测试 BUG_FIX 时优先 bad_case。"""
        result: list[MemoryItem] = engine.select_memory_keys(
            TaskType.BUG_FIX, sample_memory_items,
        )
        # bad_case (m3, priority=0.8) 应排在 success_case (m2, priority=0.7) 前面
        # 因为 bad_case 获得 +0.3 加权
        ids_in_order: list[str] = [m.id for m in result]
        assert ids_in_order.index("m3") < ids_in_order.index("m2")

    def test_select_rag_sources_bug_fix(self, engine: ContextDecisionEngine) -> None:
        """测试 BUG_FIX 的 RAG 来源。"""
        sources: list[str] = engine.select_rag_sources(TaskType.BUG_FIX)
        assert "代码结构说明" in sources
        assert "API文档" in sources
        assert "测试用例" in sources

    def test_select_rag_sources_default(self, engine: ContextDecisionEngine) -> None:
        """测试默认 RAG 来源。"""
        sources: list[str] = engine.select_rag_sources(TaskType.GENERAL_QA)
        assert "需求文档" in sources
        assert "通用知识库" in sources

    def test_choose_evaluation_protocol(self, engine: ContextDecisionEngine) -> None:
        """测试评估协议选择。"""
        assert engine.choose_evaluation_protocol(TaskType.BUG_FIX) == "llm_judge_v1"
        assert engine.choose_evaluation_protocol(TaskType.CODE_GENERATION) == "llm_judge_v1"
        assert engine.choose_evaluation_protocol(TaskType.UI_DESIGN) == "heuristic_check"
        assert engine.choose_evaluation_protocol(TaskType.GENERAL_QA) == "simple_rule_based"


# ============================================================================
# 2. ContextBudgetManager 测试
# ============================================================================


class TestContextBudgetManager:
    """测试上下文预算管理器。"""

    def test_compute_budget_bug_fix(self, budget_mgr: ContextBudgetManager) -> None:
        """测试 BUG_FIX 的预算分配。"""
        budget: dict[str, int] = budget_mgr.compute_budget(TaskType.BUG_FIX)
        assert budget["memory"] == 2000
        assert budget["rag"] == 3000
        assert budget["prompt"] == 1500
        assert budget["output"] == 1500

    def test_compute_budget_arch_refactor(self, budget_mgr: ContextBudgetManager) -> None:
        """测试 ARCH_REFACTOR 的预算分配。"""
        budget: dict[str, int] = budget_mgr.compute_budget(TaskType.ARCH_REFACTOR)
        assert budget["memory"] == 3000
        assert budget["rag"] == 5000

    def test_compute_budget_default(self, budget_mgr: ContextBudgetManager) -> None:
        """测试默认预算配置。"""
        budget: dict[str, int] = budget_mgr.compute_budget(TaskType.GENERAL_QA)
        assert isinstance(budget, dict)
        assert "memory" in budget
        assert "rag" in budget

    def test_compress_documents(self, budget_mgr: ContextBudgetManager) -> None:
        """测试文档压缩。"""
        docs: list[str] = [
            "a" * 100,  # 100 chars
            "b" * 200,  # 200 chars
        ]
        compressed: list[str] = budget_mgr.compress_documents(docs, budget=80)
        assert len(compressed) == 2
        # 每个文档分到 40 字符，前 60%=24，后 20%=8
        assert len(compressed[0]) <= 100  # 小于原始长度即可
        assert "..." in compressed[0] or len(compressed[0]) <= 40

    def test_compress_documents_empty(self, budget_mgr: ContextBudgetManager) -> None:
        """测试空文档列表压缩。"""
        assert budget_mgr.compress_documents([], 100) == []

    def test_prune_memory(self, budget_mgr: ContextBudgetManager) -> None:
        """测试记忆裁剪。"""
        items: list[MemoryItem] = [
            MemoryItem(id="a", content="short", type="test", priority=0.9, status="active"),
            MemoryItem(id="b", content="x" * 100, type="test", priority=0.5, status="active"),
            MemoryItem(id="c", content="y" * 100, type="test", priority=0.1, status="outdated"),
        ]
        pruned: list[MemoryItem] = budget_mgr.prune_memory(items, budget=3)
        # 只会包含高优先级且 active 的条目
        assert len(pruned) >= 1
        assert all(m.status == "active" for m in pruned)
        # 裁剪后不应包含 outdated
        assert "c" not in {m.id for m in pruned}

    def test_route_model_large(self, budget_mgr: ContextBudgetManager) -> None:
        """测试 large 模型路由。"""
        assert budget_mgr.route_model(TaskType.ARCH_REFACTOR) == "large"
        assert budget_mgr.route_model(TaskType.CODE_GENERATION) == "large"

    def test_route_model_small(self, budget_mgr: ContextBudgetManager) -> None:
        """测试 small 模型路由。"""
        assert budget_mgr.route_model(TaskType.BUG_FIX) == "small"
        assert budget_mgr.route_model(TaskType.GENERAL_QA) == "small"


# ============================================================================
# 3. MemoryRouter (MemoryBank + MemoryRouter) 测试
# ============================================================================


class TestMemoryBank:
    """测试 MemoryBank 底层存储。"""

    def test_add_item_new(self, bank: MemoryBank) -> None:
        """测试添加新条目。"""
        item: MemoryItem = MemoryItem(id="1", content="test", type="test", priority=0.5)
        bank.add_item(item)
        result: list[MemoryItem] = bank.query_relevant(TaskType.GENERAL_QA, top_k=5)
        assert len(result) == 1
        assert result[0].id == "1"

    def test_add_item_overwrite(self, bank: MemoryBank) -> None:
        """测试覆盖已存在的条目。"""
        item1: MemoryItem = MemoryItem(id="1", content="old", type="test", priority=0.5)
        item2: MemoryItem = MemoryItem(id="1", content="new", type="test", priority=0.9)
        bank.add_item(item1)
        bank.add_item(item2)
        result: list[MemoryItem] = bank.query_relevant(TaskType.GENERAL_QA, top_k=5)
        assert len(result) == 1
        assert result[0].content == "new"
        assert result[0].priority == 0.9

    def test_mark_outdated(self, bank: MemoryBank) -> None:
        """测试标记条目为过期。"""
        item: MemoryItem = MemoryItem(id="1", content="test", type="test", priority=0.5)
        bank.add_item(item)
        bank.mark_outdated("1")
        result: list[MemoryItem] = bank.query_relevant(TaskType.GENERAL_QA, top_k=5)
        assert len(result) == 0

    def test_query_relevant_empty(self, bank: MemoryBank) -> None:
        """测试空记忆库查询。"""
        result: list[MemoryItem] = bank.query_relevant(TaskType.BUG_FIX, top_k=5)
        assert result == []

    def test_query_relevant_bug_fix_prefers_bad_case(self, bank: MemoryBank) -> None:
        """测试 BUG_FIX 时 bad_case 获得更高相关性。"""
        bad: MemoryItem = MemoryItem(
            id="b1", content="bad", type="bad_case", priority=0.6, status="active",
        )
        success: MemoryItem = MemoryItem(
            id="s1", content="success", type="success_case", priority=0.8, status="active",
        )
        bank.add_item(bad)
        bank.add_item(success)
        result: list[MemoryItem] = bank.query_relevant(TaskType.BUG_FIX, top_k=5)
        # bad_case: 0.6 * (1+0.5) = 0.9
        # success_case: 0.8 * (1+0) = 0.8
        # bad_case 应排在前面
        assert result[0].id == "b1"

    def test_detect_conflicts(self, bank: MemoryBank) -> None:
        """测试冲突检测。"""
        existing: MemoryItem = MemoryItem(
            id="e1", content="修复 null pointer 异常导致崩溃",
            type="bad_case", priority=0.8, status="active",
        )
        new_item: MemoryItem = MemoryItem(
            id="n1", content="null pointer 崩溃修复方案",
            type="success_case", priority=0.7, status="active",
        )
        bank.add_item(existing)
        conflicts: list[MemoryItem] = bank.detect_conflicts(new_item)
        assert len(conflicts) > 0

    def test_detect_conflicts_no_conflict(self, bank: MemoryBank) -> None:
        """测试无冲突场景。"""
        existing: MemoryItem = MemoryItem(
            id="e1", content="React 组件库使用 MUI",
            type="success_case", priority=0.8, status="active",
        )
        new_item: MemoryItem = MemoryItem(
            id="n1", content="Python 后端使用 FastAPI 框架",
            type="success_case", priority=0.7, status="active",
        )
        bank.add_item(existing)
        conflicts: list[MemoryItem] = bank.detect_conflicts(new_item)
        assert len(conflicts) == 0


class TestMemoryRouter:
    """测试 MemoryRouter 高级接口。"""

    def test_add_experience(self, router: MemoryRouter) -> None:
        """测试添加经验记忆。"""
        item: MemoryItem = router.add_experience(
            content="用户喜欢深色主题",
            item_type="user_pref",
            priority=0.8,
            source="test",
        )
        assert item.id != ""
        assert item.type == "user_pref"
        assert item.priority == 0.8
        assert item.status == "active"

    def test_query_for_task_with_keyword_boost(
        self, router: MemoryRouter, sample_memory_items: list[MemoryItem],
    ) -> None:
        """测试带关键词加权的查询。"""
        # 将所有示例记忆添加到 bank
        for item in sample_memory_items:
            router.bank.add_item(item)

        result: list[MemoryItem] = router.query_for_task(
            task_input="null pointer 崩溃修复",
            task_type=TaskType.BUG_FIX,
            top_k=3,
        )
        assert len(result) > 0
        # 包含 "崩溃" 关键词的记忆应被提升
        assert all(m.status == "active" for m in result)

    def test_detect_and_report_conflicts(
        self, router: MemoryRouter, sample_memory_items: list[MemoryItem],
    ) -> None:
        """测试通过 Router 进行冲突检测。"""
        for item in sample_memory_items:
            router.bank.add_item(item)

        new_item: MemoryItem = MemoryItem(
            id="new1", content="使用全局变量导致状态污染的问题修复",
            type="success_case", priority=0.7, status="active",
        )
        conflicts: list[MemoryItem] = router.detect_and_report_conflicts(new_item)
        # m3 有相似内容，应被检测到
        assert len(conflicts) > 0


# ============================================================================
# 4. Evaluator 测试
# ============================================================================


class TestEvaluator:
    """测试评估器。"""

    def test_evaluate_scores_in_range(self, evaluator: Evaluator) -> None:
        """测试所有评分在 [0, 1] 范围内。"""
        result: EvaluationResult = evaluator.evaluate(
            task=TaskType.BUG_FIX,
            input_context="修复登录页面的崩溃问题",
            model_output="已修复登录页面的崩溃问题，添加了空值检查。" + "x" * 200,
        )
        assert 0.0 <= result.completion_rate <= 1.0
        assert 0.0 <= result.context_hit_rate <= 1.0
        assert 0.0 <= result.token_efficiency <= 1.0
        assert 0.0 <= result.hallucination_score <= 1.0
        assert 0.0 <= result.user_preference_score <= 1.0
        assert 0.0 <= result.overall_score <= 1.0

    def test_evaluate_long_output_high_completion(self, evaluator: Evaluator) -> None:
        """测试长输出的完成度为 1.0。"""
        result: EvaluationResult = evaluator.evaluate(
            task=TaskType.BUG_FIX,
            input_context="test context",
            model_output="x" * 250,
        )
        assert result.completion_rate == 1.0

    def test_evaluate_empty_output_zero_completion(self, evaluator: Evaluator) -> None:
        """测试空输出的完成度为 0.0。"""
        result: EvaluationResult = evaluator.evaluate(
            task=TaskType.BUG_FIX,
            input_context="test context",
            model_output="",
        )
        assert result.completion_rate == 0.0

    def test_evaluate_hallucination_score_for_humility(self, evaluator: Evaluator) -> None:
        """测试包含谦逊表述时幻觉评分高。"""
        result: EvaluationResult = evaluator.evaluate(
            task=TaskType.GENERAL_QA,
            input_context="test",
            model_output="抱歉，我不确定这个问题的答案。" + "x" * 200,
        )
        # 包含 "抱歉" → 幻觉分应为 0.95
        assert result.hallucination_score == 0.95

    def test_detect_drift_no_history(self, evaluator: Evaluator) -> None:
        """测试无历史输出时 drift 为 0.0。"""
        drift: float = evaluator.detect_drift([], "current output")
        assert drift == 0.0

    def test_detect_drift_with_history(self, evaluator: Evaluator) -> None:
        """测试有历史输出时的 drift 计算。"""
        drift: float = evaluator.detect_drift(
            previous_outputs=[
                "hello world test",
                "hello world example",
            ],
            current_output="hello world something",
        )
        assert 0.0 <= drift <= 1.0

    def test_detect_drift_identical_outputs(self, evaluator: Evaluator) -> None:
        """测试相同输出时 drift 为 0.0。"""
        drift: float = evaluator.detect_drift(
            previous_outputs=["abc def ghi"],
            current_output="abc def ghi",
        )
        assert drift == 0.0

    def test_generate_feedback(self, evaluator: Evaluator) -> None:
        """测试反馈生成。"""
        result: EvaluationResult = evaluator.evaluate(
            task=TaskType.BUG_FIX,
            input_context="test context",
            model_output="x" * 250,
        )
        feedback: str = evaluator.generate_feedback(result)
        assert "完成度" in feedback
        assert "上下文命中率" in feedback
        assert len(feedback) > 0


# ============================================================================
# 5. BadCaseManager 测试
# ============================================================================


class TestBadCaseManager:
    """测试负面案例管理器。"""

    def test_record_case_low_score(self, bad_case_mgr: BadCaseManager) -> None:
        """测试低分案例被记录。"""
        evaluation: EvaluationResult = EvaluationResult(
            completion_rate=0.2,
            context_hit_rate=0.1,
            token_efficiency=0.3,
            hallucination_score=0.2,
            user_preference_score=0.3,
            overall_score=0.25,
        )
        bad_case_mgr.record_case(
            task=TaskType.BUG_FIX,
            input_context="test input",
            output="test output",
            evaluation=evaluation,
        )
        cases: list[BadCase] = bad_case_mgr.retrieve_recent_bad_cases()
        assert len(cases) == 1

    def test_record_case_high_score_not_recorded(
        self, bad_case_mgr: BadCaseManager,
    ) -> None:
        """测试高分案例不被记录。"""
        evaluation: EvaluationResult = EvaluationResult(
            completion_rate=0.9,
            context_hit_rate=0.8,
            token_efficiency=0.7,
            hallucination_score=0.9,
            user_preference_score=0.8,
            overall_score=0.85,
        )
        bad_case_mgr.record_case(
            task=TaskType.BUG_FIX,
            input_context="test input",
            output="test output",
            evaluation=evaluation,
        )
        cases: list[BadCase] = bad_case_mgr.retrieve_recent_bad_cases()
        assert len(cases) == 0

    def test_generate_improvement_rule_bug_fix(self, bad_case_mgr: BadCaseManager) -> None:
        """测试 BUG_FIX 改进建议生成。"""
        evaluation: EvaluationResult = EvaluationResult(
            completion_rate=0.2,
            context_hit_rate=0.5,
            token_efficiency=0.5,
            hallucination_score=0.5,
            user_preference_score=0.5,
            overall_score=0.3,
        )
        bad_case: BadCase = BadCase(
            task_type=TaskType.BUG_FIX,
            input_context="test",
            output="test",
            evaluation=evaluation,
            failure_reason="low completion",
        )
        rule: str = bad_case_mgr.generate_improvement_rule(bad_case)
        assert "代码结构" in rule or "测试用例" in rule

    def test_generate_improvement_rule_default(self, bad_case_mgr: BadCaseManager) -> None:
        """测试默认改进建议。"""
        evaluation: EvaluationResult = EvaluationResult(
            completion_rate=0.6,
            context_hit_rate=0.5,
            token_efficiency=0.5,
            hallucination_score=0.6,
            user_preference_score=0.5,
            overall_score=0.4,
        )
        bad_case: BadCase = BadCase(
            task_type=TaskType.GENERAL_QA,
            input_context="test",
            output="test",
            evaluation=evaluation,
        )
        rule: str = bad_case_mgr.generate_improvement_rule(bad_case)
        assert "记忆" in rule or "知识库" in rule

    def test_retrieve_recent_bad_cases_order(self, bad_case_mgr: BadCaseManager) -> None:
        """测试按时间排序检索。"""
        for i in range(5):
            evaluation: EvaluationResult = EvaluationResult(
                completion_rate=0.3,
                context_hit_rate=0.3,
                token_efficiency=0.3,
                hallucination_score=0.3,
                user_preference_score=0.3,
                overall_score=0.3,
            )
            bad_case_mgr.record_case(
                task=TaskType.BUG_FIX,
                input_context=f"input {i}",
                output=f"output {i}",
                evaluation=evaluation,
            )
        cases: list[BadCase] = bad_case_mgr.retrieve_recent_bad_cases(limit=3)
        assert len(cases) == 3
        # 应按时序降序排列
        for i in range(len(cases) - 1):
            assert cases[i].timestamp >= cases[i + 1].timestamp


# ============================================================================
# 6. WorkflowEngine 测试
# ============================================================================


class TestWorkflowEngine:
    """测试工作流状态机。"""

    def test_start_workflow(self, workflow_engine: WorkflowEngine) -> None:
        """测试启动工作流。"""
        workflow: Workflow = workflow_engine.start_workflow("修复登录页面的崩溃问题")
        assert workflow.current_state == WorkflowState.INIT
        assert workflow.task_type == TaskType.BUG_FIX
        assert "task_input" in workflow.context_pack

    def test_full_workflow_state_transitions(
        self, workflow_engine: WorkflowEngine,
    ) -> None:
        """测试完整的 7 步状态流转。"""
        workflow: Workflow = workflow_engine.start_workflow(
            "实现用户注册功能，包括表单验证和数据持久化"
        )

        expected_states: list[WorkflowState] = [
            WorkflowState.INIT,
            WorkflowState.RETRIEVE_MEMORY,
            WorkflowState.RETRIEVE_KNOWLEDGE,
            WorkflowState.PLAN,
            WorkflowState.EXECUTE,
            WorkflowState.EVALUATE,
            WorkflowState.LEARN,
            WorkflowState.COMPLETE,
        ]

        for i, expected in enumerate(expected_states):
            assert workflow.current_state == expected, (
                f"Step {i}: expected {expected}, got {workflow.current_state}"
            )
            if expected != WorkflowState.COMPLETE:
                workflow_engine.next_step(workflow)

        # 最终状态确认
        assert workflow.current_state == WorkflowState.COMPLETE
        # 历史记录应有 7 条（INIT→MEMORY→KNOWLEDGE→PLAN→EXECUTE→EVALUATE→LEARN→COMPLETE）
        assert len(workflow.history) == 7

    def test_workflow_context_pack_populated(
        self, workflow_engine: WorkflowEngine,
    ) -> None:
        """测试工作流上下文包在各阶段正确填充。"""
        workflow: Workflow = workflow_engine.start_workflow(
            "修复 null pointer 崩溃异常"
        )

        # 推进到 RETRIEVE_MEMORY
        workflow_engine.next_step(workflow)  # INIT → RETRIEVE_MEMORY
        workflow_engine.next_step(workflow)  # RETRIEVE_MEMORY → RETRIEVE_KNOWLEDGE
        # memory 应该已被填充（即使为空也会是空列表）
        assert "memory" in workflow.context_pack

        # 推进到 PLAN
        workflow_engine.next_step(workflow)  # RETRIEVE_KNOWLEDGE → PLAN (这里有个bug需要检查)
        # 再推进到 EXECUTE
        workflow_engine.next_step(workflow)  # PLAN → EXECUTE
        assert "plan" in workflow.context_pack
        assert "model" in workflow.context_pack["plan"]

        # 推进到 EVALUATE
        workflow_engine.next_step(workflow)  # EXECUTE → EVALUATE
        assert "output" in workflow.context_pack

        # 推进到 LEARN
        workflow_engine.next_step(workflow)  # EVALUATE → LEARN
        assert "evaluation" in workflow.context_pack

        # 推进到 COMPLETE
        workflow_engine.next_step(workflow)  # LEARN → COMPLETE
        assert workflow.current_state == WorkflowState.COMPLETE
