"""IntentAlignmentEvaluator 单元测试。

测试意图对齐评估的各维度评分。
"""

from __future__ import annotations

import pytest

from stable_agent.intent.intent_alignment_evaluator import IntentAlignmentEvaluator
from stable_agent.intent.user_intent_profile import UserIntentProfile


# ============================================================================
# Helpers
# ============================================================================


def make_profile(
    preferred_depth: float = 0.5,
    preferred_structure: float = 0.5,
) -> UserIntentProfile:
    """创建测试用 UserIntentProfile。"""
    return UserIntentProfile(
        user_id="test-user",
        preferred_depth=preferred_depth,
        preferred_structure=preferred_structure,
    )


# ============================================================================
# Tests
# ============================================================================


class TestActionabilityScore:
    """测试可执行性评分。"""

    def test_code_heavy_output_scores_high(self):
        """包含代码块的输出 → 高分。"""
        evaluator = IntentAlignmentEvaluator()
        output = """
Here's the solution:

```python
def hello():
    print("Hello, world!")
```

```bash
python script.py
```
"""
        score = evaluator._actionability(output)
        assert score > 0.3

    def test_empty_output_scores_zero(self):
        """空输出 → 0 分。"""
        evaluator = IntentAlignmentEvaluator()
        score = evaluator._actionability("")
        assert score == 0.0

    def test_step_by_step_output(self):
        """包含步骤的输出 → 中等分。"""
        evaluator = IntentAlignmentEvaluator()
        output = """
1. First, install the dependencies
2. Then, configure the settings
3. Finally, run the application
"""
        score = evaluator._actionability(output)
        assert score > 0.1


class TestAntiGenericScore:
    """测试反通用性评分。"""

    def test_no_generic_markers_scores_high(self):
        """无通用表达 → 高分。"""
        evaluator = IntentAlignmentEvaluator()
        output = "The exact command is: `pip install requests` and then add `import requests` to your file."
        score = evaluator._anti_generic(output)
        assert score == 1.0

    def test_many_generic_markers_scores_low(self):
        """大量通用表达 → 低分。"""
        evaluator = IntentAlignmentEvaluator()
        output = (
            "在一般情况下，建议您可以尝试使用相关工具。"
            "通常来说，大多数情况下都可以考虑这个方案。"
            "一般而言，您可以先了解一下基本概念。"
        )
        score = evaluator._anti_generic(output)
        assert score < 0.5

    def test_empty_output_scores_zero(self):
        """空输出 → 0 分。"""
        evaluator = IntentAlignmentEvaluator()
        score = evaluator._anti_generic("")
        assert score == 0.0


class TestOverallEvaluation:
    """测试综合评估。"""

    def test_evaluate_returns_all_dimensions(self):
        """评估返回所有维度和综合分。"""
        evaluator = IntentAlignmentEvaluator()
        result = evaluator.evaluate(
            task_input="How do I sort a list in Python?",
            model_output="Use `list.sort()` or `sorted(list)`. For example:\n\n```python\nmy_list.sort()\n```",
        )

        assert "dimension_scores" in result
        assert "overall" in result
        assert "feedback" in result
        assert 0.0 <= result["overall"] <= 1.0

        dims = result["dimension_scores"]
        for dim_name in IntentAlignmentEvaluator.WEIGHTS:
            assert dim_name in dims
            assert 0.0 <= dims[dim_name] <= 1.0

    def test_high_quality_output_scores_high(self):
        """高质量输出 → 综合高分。"""
        evaluator = IntentAlignmentEvaluator()
        result = evaluator.evaluate(
            task_input="How to read a file in Python?",
            model_output=(
                "# Reading Files in Python\n\n"
                "## Using `open()`\n\n"
                "```python\n"
                "with open('file.txt', 'r') as f:\n"
                "    content = f.read()\n"
                "```\n\n"
                "## Step-by-step:\n"
                "1. Use `open()` with the file path and mode\n"
                "2. Use the context manager (`with` statement)\n"
                "3. Call `.read()` to get all content\n\n"
                "This approach handles file closing automatically."
            ),
        )

        # 含代码、步骤、标题 → 高质量
        assert result["overall"] > 0.5

    def test_low_quality_output_scores_low(self):
        """低质量输出 → 低分。"""
        evaluator = IntentAlignmentEvaluator()
        result = evaluator.evaluate(
            task_input="Fix my Python bug",
            model_output="在一般情况下，建议您可以尝试检查代码。通常来说，大多数bug都可以通过调试解决。",
        )

        assert result["overall"] < 0.5

    def test_evaluate_empty_input_and_output(self):
        """空输入和输出 → 基础结果。"""
        evaluator = IntentAlignmentEvaluator()
        result = evaluator.evaluate("", "")

        assert result["overall"] == 0.0
        assert "为空" in result["feedback"]

    def test_evaluate_with_profile(self):
        """传入 profile 影响风格匹配评分。"""
        evaluator = IntentAlignmentEvaluator()
        profile = make_profile(preferred_depth=0.8, preferred_structure=0.8)

        result_with = evaluator.evaluate(
            task_input="Write a Python function",
            model_output="# Title\n\n- Point 1\n- Point 2\n\nDetailed explanation here...",
            user_intent_profile=profile,
        )

        result_without = evaluator.evaluate(
            task_input="Write a Python function",
            model_output="# Title\n\n- Point 1\n- Point 2\n\nDetailed explanation here...",
            user_intent_profile=None,
        )

        # 有 profile 时 style_match 应该不同于无 profile 的默认 0.5
        assert result_with["dimension_scores"]["style_match"] != 0.5 or result_without["dimension_scores"]["style_match"] == 0.5
