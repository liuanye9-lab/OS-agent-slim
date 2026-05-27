"""意图分类体系。

定义意图类型层级和"泛建议"检测。
基于关键词分类和输出质量检测。
"""

from __future__ import annotations

import logging
from typing import ClassVar

logger = logging.getLogger(__name__)


class IntentTaxonomy:
    """意图分类体系。

    定义意图类型层级和"泛建议"检测。

    意图类型：
    - implementation: 需要可执行代码/提示词
    - diagnosis: 需要诊断分析
    - learning: 需要概念解释
    - design: 需要设计方案
    - evaluation: 需要评估/审查
    - qa: 需要快速问答

    Class Attributes:
        TASK_CATEGORIES: 意图类型到关键词列表的映射。
    """

    TASK_CATEGORIES: ClassVar[dict[str, list[str]]] = {
        "implementation": ["开发", "实现", "写代码", "提示词", "Codex", "生产", "构建", "创建", "编写"],
        "diagnosis": ["诊断", "修复", "bug", "报错", "崩溃", "异常", "错误", "调试", "排查"],
        "learning": ["解释", "学习", "原理", "理解", "概念", "教程", "入门", "怎么", "如何"],
        "design": ["设计", "UI", "架构", "方案", "规划", "布局", "样式", "界面"],
        "evaluation": ["评估", "审查", "测试", "打分", "检查", "审计", "评审"],
        "qa": [],  # default — 无特定关键词匹配时归入此类
    }

    # 泛泛回答的检测关键词
    GENERIC_MARKERS: ClassVar[list[str]] = [
        "在一般情况下",
        "建议您可以",
        "可以尝试",
        "可以考虑",
        "通常来说",
        "一般来讲",
        "大多数情况",
        "一般而言",
        "您可以根据",
        "常见做法是",
        "通常的做法",
    ]

    @classmethod
    def classify(cls, task_input: str) -> str:
        """基于关键词对用户输入进行意图分类。

        匹配规则：按 TASK_CATEGORIES 定义的顺序匹配，
        第一个命中即返回。无匹配时返回 "qa"。

        Args:
            task_input: 用户输入文本。

        Returns:
            意图类型字符串。
        """
        if not task_input:
            return "qa"

        input_lower = task_input.lower()

        for category, keywords in cls.TASK_CATEGORIES.items():
            if not keywords:
                continue
            for keyword in keywords:
                if keyword.lower() in input_lower:
                    logger.debug("输入分类为 '%s'（匹配关键词: '%s'）", category, keyword)
                    return category

        logger.debug("输入分类为 'qa'（无特定关键词匹配）")
        return "qa"

    @classmethod
    def is_generic_answer(cls, model_output: str) -> bool:
        """检测是否是泛泛建议。

        判断标准：
        - 输出中无代码块
        - 输出中无具体指标（数字、百分比）
        - 不引用来源
        - 包含"在一般情况下/建议/可以尝试"等通用表达
        → 很可能是泛泛建议

        Args:
            model_output: 模型输出文本。

        Returns:
            True 如果检测到泛泛回答特征。
        """
        if not model_output:
            return True

        # 检查是否有代码块
        has_code = "```" in model_output

        # 检查是否有具体指标
        import re
        has_numbers = bool(re.search(r"\d+%|\d+\.\d+|\b\d{2,}\b", model_output))

        # 检查是否引用了来源
        has_citation = bool(re.search(
            r"根据|参考|引用|来源|出自|参见|详见",
            model_output,
        ))

        # 如果包含代码、具体数字或引用，不是泛泛
        if has_code or has_numbers or has_citation:
            return False

        # 检查是否有多个通用标记
        generic_count = sum(
            1 for marker in cls.GENERIC_MARKERS if marker in model_output
        )

        return generic_count >= 2
