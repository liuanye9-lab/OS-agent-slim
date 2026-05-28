"""V5.5 Explanation 层 — 双语文本、国际化与事件叙述。

本包提供：
- BilingualText: 中英双语文本数据类
- I18nManager: 国际化管理器，支持 zh / en / both 三种模式
- DecisionNarrator: 技术事件 → 用户可读 DecisionTrace 翻译器
- StageExplainer: 阶段解释器，将事件阶段映射为人类可读的双语解释
- EvidenceSummarizer: 证据摘要器，对决策证据进行排序和摘要
- LearningExplainer: 学习解释器，将 SkillOpt 优化结果翻译为人话
- UserFriendlyFormatter: 用户友好格式化器，将内部结构转为自然语言
- explanation_templates: 19 种事件类型的中英双语模板
"""

from __future__ import annotations

from stable_agent.explanation.bilingual_text import BilingualText, I18nManager
from stable_agent.explanation.decision_narrator import DecisionNarrator
from stable_agent.explanation.evidence_summarizer import EvidenceSummarizer
from stable_agent.explanation.learning_explainer import LearningExplainer
from stable_agent.explanation.stage_explainer import StageExplainer
from stable_agent.explanation.user_friendly_formatter import UserFriendlyFormatter

__all__ = [
    "BilingualText",
    "DecisionNarrator",
    "EvidenceSummarizer",
    "I18nManager",
    "LearningExplainer",
    "StageExplainer",
    "UserFriendlyFormatter",
]
