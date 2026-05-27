"""IntentSignalExtractor 单元测试。

测试意图信号提取的各个维度。
"""

from __future__ import annotations

from datetime import datetime

import pytest

from stable_agent.skill_optimizer.models import RolloutTrajectory
from stable_agent.skill_optimizer.intent_signal_extractor import IntentSignalExtractor


# ============================================================================
# Helpers
# ============================================================================


def make_trajectory(
    task_input: str = "",
    task_type: str = "",
    user_feedback: str = "unknown",
    model_output: str = "",
) -> RolloutTrajectory:
    """创建测试用 RolloutTrajectory。"""
    return RolloutTrajectory(
        id="test-1",
        task_input=task_input,
        task_type=task_type,
        user_feedback=user_feedback,  # type: ignore[arg-type]
        model_output=model_output,
        created_at=datetime.now(),
    )


# ============================================================================
# Tests
# ============================================================================


class TestExtractStructure:
    """测试 extract() 返回结构。"""

    def test_extract_returns_required_keys(self):
        """extract 返回的字典包含所有必须字段。"""
        extractor = IntentSignalExtractor()
        traj = make_trajectory(task_input="写一个排序算法")
        result = extractor.extract(traj)

        assert "explicit_intent" in result
        assert "implicit_intent" in result
        assert "output_preference" in result
        assert "rejection_signals" in result
        assert "correction_signals" in result
        assert "task_category" in result

    def test_extract_with_empty_trajectory(self):
        """空轨迹也能正常提取。"""
        extractor = IntentSignalExtractor()
        traj = make_trajectory()
        result = extractor.extract(traj)

        assert isinstance(result["explicit_intent"], str)
        assert isinstance(result["implicit_intent"], str)
        assert isinstance(result["output_preference"], dict)
        assert isinstance(result["rejection_signals"], list)
        assert isinstance(result["correction_signals"], list)


class TestExplicitIntent:
    """测试显性意图提取。"""

    def test_explicit_intent_returns_input(self):
        """显性意图返回脱敏后的 task_input。"""
        extractor = IntentSignalExtractor()
        result = extractor._extract_explicit("帮我写一个 Python 脚本")

        assert "Python 脚本" in result

    def test_explicit_intent_truncates_long_input(self):
        """超长输入被截断。"""
        extractor = IntentSignalExtractor()
        long_input = "A" * 3000
        result = extractor._extract_explicit(long_input)

        assert len(result) <= 2000
        assert result.endswith("...")

    def test_explicit_intent_empty_string(self):
        """空字符串返回空字符串。"""
        extractor = IntentSignalExtractor()
        result = extractor._extract_explicit("")
        assert result == ""


class TestImplicitIntent:
    """测试隐性意图推断。"""

    def test_infer_prompt_keyword(self):
        """"提示词" → 需要可直接执行的开发提示词。"""
        extractor = IntentSignalExtractor()
        result = extractor._infer_implicit("帮我写一个 Codex 提示词", "")
        assert "开发提示词" in result

    def test_infer_refactor_keyword(self):
        """"重构" → 需要系统化的改进方案。"""
        extractor = IntentSignalExtractor()
        result = extractor._infer_implicit("重构这个模块", "")
        assert "改进方案" in result

    def test_infer_learning_keyword(self):
        """"学习" → 需要第一性原理的深度解释。"""
        extractor = IntentSignalExtractor()
        result = extractor._infer_implicit("学习 Rust", "")
        assert "深度解释" in result

    def test_infer_design_keyword(self):
        """"UI" → 需要可落地的设计方案。"""
        extractor = IntentSignalExtractor()
        result = extractor._infer_implicit("设计一个 UI 界面", "")
        assert "设计方案" in result

    def test_infer_default(self):
        """无关键词 → 默认。"""
        extractor = IntentSignalExtractor()
        result = extractor._infer_implicit("hello", "")
        assert "AI 辅助" in result


class TestPreferenceInference:
    """测试偏好推断。"""

    def test_preference_detailed_output(self):
        """长输出 → detailed 深度偏好。"""
        extractor = IntentSignalExtractor()
        long_output = "A" * 1200
        result = extractor._infer_preference("", long_output)

        assert result["depth"] == "detailed"

    def test_preference_concise_output(self):
        """短输出 → concise 深度偏好。"""
        extractor = IntentSignalExtractor()
        short_output = "OK"
        result = extractor._infer_preference("", short_output)

        assert result["depth"] == "concise"

    def test_preference_structured_output(self):
        """含标题和列表 → structured。"""
        extractor = IntentSignalExtractor()
        structured = "# Title\n\n- item 1\n- item 2\n\nSome text"
        result = extractor._infer_preference("", structured)

        assert result["structure"] == "structured"


class TestRejectionAndCorrection:
    """测试拒绝和修正信号。"""

    def test_extract_rejection_signals(self):
        """从 rejected feedback 中提取拒绝信号。"""
        extractor = IntentSignalExtractor()
        signals = extractor._extract_rejection("这个回答不准确，太泛了没用的东西")

        assert len(signals) > 0
        # 应该包含至少一个信号
        has_signal = any(
            "不准确" in s or "太泛" in s or "没用" in s
            for s in signals
        )
        assert has_signal

    def test_extract_correction_signals(self):
        """从 edited feedback 中提取修正信号。"""
        extractor = IntentSignalExtractor()
        signals = extractor._extract_correction("请把这里改成中文，加上更多例子")

        assert len(signals) > 0

    def test_empty_feedback_no_signals(self):
        """空 feedback 不产生信号。"""
        extractor = IntentSignalExtractor()
        assert extractor._extract_rejection("") == []
        assert extractor._extract_correction("") == []
