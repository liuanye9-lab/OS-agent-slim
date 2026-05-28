"""Tests for user feedback signal — V5.5."""
import pytest
from stable_agent.skill_optimizer.intent_signal_extractor import IntentSignalExtractor
from stable_agent.skill_optimizer.models import RolloutTrajectory


class TestUserFeedbackSignal:
    @pytest.fixture
    def extractor(self):
        return IntentSignalExtractor()

    def test_extract_signals_from_accepted(self, extractor):
        t = RolloutTrajectory(
            id="t1", task_input="生成Codex提示词",
            model_output="这是结构化的开发提示词...",
            user_feedback="accepted",
        )
        signals = extractor.extract(t)
        assert "explicit_intent" in signals
        assert "implicit_intent" in signals
        assert len(signals.get("rejection_signals", [])) == 0

    def test_extract_signals_from_rejected(self, extractor):
        t = RolloutTrajectory(
            id="t2", task_input="解释概念",
            model_output="泛泛而谈的解释...",
            user_feedback="rejected",
        )
        signals = extractor.extract(t)
        # rejected反馈应出现在signals中
        assert "explicit_intent" in signals
        assert "rejection_signals" in signals

    def test_extract_signals_from_edited(self, extractor):
        t = RolloutTrajectory(
            id="t3", task_input="分析代码",
            model_output="简单的代码分析",
            user_feedback="edited",
        )
        signals = extractor.extract(t)
        assert "correction_signals" in signals

    def test_extract_output_preference(self, extractor):
        t = RolloutTrajectory(
            id="t4", task_input="生成开发提示词",
            model_output="# 标题\n## 模块\n- 列表项\n```代码块```\n详细说明...",
            user_feedback="accepted",
        )
        signals = extractor.extract(t)
        pref = signals.get("output_preference", {})
        assert isinstance(pref, dict)

    def test_extract_task_category(self, extractor):
        t = RolloutTrajectory(
            id="t5", task_input="开发一个登录功能",
            task_type="code_generation",
        )
        signals = extractor.extract(t)
        assert "task_category" in signals

    def test_extract_handles_unknown_feedback(self, extractor):
        t = RolloutTrajectory(
            id="t6", task_input="test",
            user_feedback="unknown",
        )
        signals = extractor.extract(t)
        assert "explicit_intent" in signals
        assert "rejection_signals" in signals
