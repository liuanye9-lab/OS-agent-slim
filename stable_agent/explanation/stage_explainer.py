"""StageExplainer — 阶段解释器，将事件阶段映射为人类可读的双语解释。"""
from __future__ import annotations

from stable_agent.explanation.bilingual_text import BilingualText


class StageExplainer:
    """根据事件阶段生成双语解释。

    将内部阶段标识符（如 "listening", "thinking", "planning"）翻译为
    面向用户的、中英双语的自然语言描述，用于前端实时状态展示。

    Attributes:
        _STAGE_I18N: 阶段到中英双语文案的静态映射表。
    """

    _STAGE_I18N: dict[str, dict[str, str]] = {
        "listening":     {"zh": "正在接收任务",       "en": "Receiving task"},
        "thinking":      {"zh": "正在理解需求",       "en": "Understanding intent"},
        "memory":        {"zh": "正在检索记忆",       "en": "Retrieving memory"},
        "rag":           {"zh": "正在搜索知识库",     "en": "Searching knowledge base"},
        "budget":        {"zh": "正在估算 Token 预算","en": "Estimating token budget"},
        "planning":      {"zh": "正在制定执行计划",   "en": "Planning execution steps"},
        "execution":     {"zh": "正在执行工具调用",   "en": "Executing tool call"},
        "safety":        {"zh": "正在安全检查",       "en": "Running safety check"},
        "approval":      {"zh": "等待人工审批",       "en": "Waiting for approval"},
        "eval":          {"zh": "正在评估输出质量",   "en": "Evaluating output quality"},
        "learning":      {"zh": "正在总结经验",       "en": "Learning from this run"},
        "done":          {"zh": "任务完成",           "en": "Task completed"},
        "failed":        {"zh": "任务失败",           "en": "Task failed"},
    }

    def explain_stage(self, stage: str) -> BilingualText:
        """将阶段标识符翻译为 BilingualText 对象。

        Args:
            stage: 阶段标识符，如 "listening", "thinking"。

        Returns:
            包含中英双语解释的 BilingualText 实例。
            未识别的阶段将原样返回 stage 字符串作为双语文案。
        """
        info: dict[str, str] = self._STAGE_I18N.get(stage, {"zh": stage, "en": stage})
        return BilingualText(zh=info["zh"], en=info["en"])

    def get_stage_i18n(self, stage: str) -> dict[str, str]:
        """获取阶段的原始 i18n 字典（不包装为 BilingualText）。

        Args:
            stage: 阶段标识符。

        Returns:
            包含 "zh" / "en" 键的字典。未识别的阶段将原样映射。
        """
        return self._STAGE_I18N.get(stage, {"zh": stage, "en": stage})
