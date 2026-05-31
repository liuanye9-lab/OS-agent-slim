"""test_understanding_trace.py — 语义理解轨迹测试。

测试覆盖:
- "继续优化这个项目" 能识别为需要项目上下文
- "不要大范围重构" 能转成 protected constraint
- "不要跑偏" / "别 AI 味" 能识别为保持风格约束
- UnderstandingTrace JSON 可序列化
- 置信度计算
- 是否需要用户确认
"""

from __future__ import annotations

import json

from stable_agent.understanding.semantic_interpreter import SemanticInterpreter
from stable_agent.understanding.schemas import UnderstandingTrace, TaskType


class TestSemanticInterpreter:
    """语义解释器测试。"""

    def setup_method(self) -> None:
        self.interpreter = SemanticInterpreter()

    # ------------------------------------------------------------------
    # 任务类型识别
    # ------------------------------------------------------------------

    def test_classify_debugging(self) -> None:
        """测试调试类任务识别。"""
        trace = self.interpreter.interpret("修复登录页面的 bug")
        assert trace.task_type == TaskType.DEBUGGING

    def test_classify_refactor(self) -> None:
        """测试重构类任务识别。"""
        trace = self.interpreter.interpret("重构用户模块的代码结构")
        assert trace.task_type == TaskType.REFACTOR

    def test_classify_design(self) -> None:
        """测试设计类任务识别。"""
        trace = self.interpreter.interpret("设计一个新的登录界面")
        assert trace.task_type == TaskType.DESIGN

    def test_classify_coding(self) -> None:
        """测试编码类任务识别。"""
        trace = self.interpreter.interpret("实现用户注册功能")
        assert trace.task_type == TaskType.CODING

    def test_classify_unknown(self) -> None:
        """测试未知类型。"""
        trace = self.interpreter.interpret("你好")
        assert trace.task_type == TaskType.UNKNOWN

    # ------------------------------------------------------------------
    # 保护性约束提取
    # ------------------------------------------------------------------

    def test_constraint_no_refactor_large_scope(self) -> None:
        """测试: "不要大范围重构" 能转成 protected constraint。"""
        trace = self.interpreter.interpret("不要大范围重构这个模块")
        assert "限制变更范围" in trace.protected_constraints

    def test_constraint_dont_go_off_track(self) -> None:
        """测试: "不要跑偏" 能识别为保持风格约束。"""
        trace = self.interpreter.interpret("继续优化，不要跑偏")
        assert "保持原有风格" in trace.protected_constraints

    def test_constraint_no_ai_flavor(self) -> None:
        """测试: "别 AI 味" 能识别为保持风格约束。"""
        trace = self.interpreter.interpret("改一下文案，别太 AI 味")
        assert "保持原有风格" in trace.protected_constraints

    def test_constraint_minimal_changes(self) -> None:
        """测试: "只改相关文件" 能识别为最小变更约束。"""
        trace = self.interpreter.interpret("只改相关文件，不要动其他的")
        assert "最小变更" in trace.protected_constraints

    def test_constraint_keep_existing(self) -> None:
        """测试: "不要删除" 能识别为保留约束。"""
        trace = self.interpreter.interpret("优化逻辑，不要删除现有功能")
        assert "保留现有内容" in trace.protected_constraints

    # ------------------------------------------------------------------
    # 假设提取
    # ------------------------------------------------------------------

    def test_assumption_continue_optimize(self) -> None:
        """测试: "继续优化这个项目" 能识别为需要项目上下文。"""
        trace = self.interpreter.interpret("继续优化这个项目")
        assert any("项目上下文" in a for a in trace.assumptions)

    def test_assumption_this_project(self) -> None:
        """测试: "这个项目" 能识别为指向当前项目。"""
        trace = self.interpreter.interpret("检查这个项目的测试覆盖率")
        assert any("当前工作目录" in a for a in trace.assumptions)

    def test_assumption_previous(self) -> None:
        """测试: "上次" 能识别为引用历史记忆。"""
        trace = self.interpreter.interpret("上次的改进建议还有效吗")
        assert any("历史交互记忆" in a for a in trace.assumptions)

    # ------------------------------------------------------------------
    # 不确定性识别
    # ------------------------------------------------------------------

    def test_uncertainty_ambiguous_reference(self) -> None:
        """测试模糊指代识别。"""
        trace = self.interpreter.interpret("优化一下这个")
        assert any("模糊指代" in u for u in trace.uncertainties)

    def test_uncertainty_short_input(self) -> None:
        """测试短输入识别。"""
        trace = self.interpreter.interpret("改一下")
        assert any("较短" in u for u in trace.uncertainties)

    # ------------------------------------------------------------------
    # 语义风险检测
    # ------------------------------------------------------------------

    def test_risk_wide_scope(self) -> None:
        """测试大范围变更风险。"""
        trace = self.interpreter.interpret("把所有文件都改一遍")
        assert "potential_wide_scope_change" in trace.semantic_risk_flags

    def test_risk_destructive(self) -> None:
        """测试破坏性操作风险。"""
        trace = self.interpreter.interpret("删除旧的配置文件")
        assert "potential_destructive_operation" in trace.semantic_risk_flags

    # ------------------------------------------------------------------
    # 置信度和确认
    # ------------------------------------------------------------------

    def test_confidence_range(self) -> None:
        """测试置信度在合法范围内。"""
        trace = self.interpreter.interpret("实现用户注册功能")
        assert 0.0 <= trace.confidence <= 1.0

    def test_needs_confirmation_with_uncertainty(self) -> None:
        """测试有不确定性时需要确认。"""
        trace = self.interpreter.interpret("优化一下这个")
        assert trace.needs_user_confirmation is True

    def test_no_confirmation_high_confidence(self) -> None:
        """测试高置信度且无不确定性时不需要确认。"""
        trace = self.interpreter.interpret("修复登录页面的 bug，不要跑偏")
        # 有保护约束，置信度高，无不确定性
        assert trace.needs_user_confirmation is False

    # ------------------------------------------------------------------
    # JSON 序列化
    # ------------------------------------------------------------------

    def test_trace_json_serializable(self) -> None:
        """测试 UnderstandingTrace 可 JSON 序列化。"""
        trace = self.interpreter.interpret("继续优化这个项目，不要大范围重构")
        d = trace.to_dict()
        json_str = json.dumps(d, ensure_ascii=False)
        assert json_str
        # 反序列化后验证
        restored = json.loads(json_str)
        assert restored["trace_id"] == trace.trace_id
        assert restored["user_original_input"] == trace.user_original_input

    # ------------------------------------------------------------------
    # interpreted_goal
    # ------------------------------------------------------------------

    def test_goal_with_constraints(self) -> None:
        """测试有约束时目标包含约束信息。"""
        trace = self.interpreter.interpret("优化代码，不要跑偏")
        assert "保持原有风格" in trace.interpreted_goal

    def test_goal_without_constraints(self) -> None:
        """测试无约束时目标等于原始输入。"""
        trace = self.interpreter.interpret("实现用户注册功能")
        assert trace.interpreted_goal == "实现用户注册功能"
