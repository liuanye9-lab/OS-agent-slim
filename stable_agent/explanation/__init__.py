"""V5.5 Explanation 层 — 双语文本、国际化与事件叙述。

本包提供：
- BilingualText: 中英双语文本数据类
- I18nManager: 国际化管理器，支持 zh / en / both 三种模式
- DecisionNarrator: 技术事件 → 用户可读 DecisionTrace 翻译器
- explanation_templates: 19 种事件类型的中英双语模板
"""

from __future__ import annotations

from stable_agent.explanation.bilingual_text import BilingualText, I18nManager
from stable_agent.explanation.decision_narrator import DecisionNarrator

__all__ = [
    "BilingualText",
    "I18nManager",
    "DecisionNarrator",
]
