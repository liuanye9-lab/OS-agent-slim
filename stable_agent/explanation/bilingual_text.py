"""V5.5 双语文本系统。BilingualText 数据类 + I18nManager 全局翻译管理器。"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Literal


@dataclass
class BilingualText:
    """中英双语文本。前端按 locale 参数渲染。"""
    zh: str = ""
    en: str = ""

    def get(self, locale: str = "zh") -> str:
        return self.zh if locale == "zh" else self.en


_TRANSLATIONS: dict[str, dict[str, str]] = {
    "zh": {
        "stage.task_intake": "接收任务",
        "stage.intent_parse": "理解意图",
        "stage.context_budget": "Token 预算",
        "stage.memory_retrieval": "检索记忆",
        "stage.rag_retrieval": "搜索资料",
        "stage.context_build": "构建上下文",
        "stage.planning": "制定计划",
        "stage.tool_call": "调用工具",
        "stage.security_check": "安全检查",
        "stage.approval_waiting": "等待审批",
        "stage.execution": "执行任务",
        "stage.evaluation": "评测结果",
        "stage.badcase_record": "记录失败案例",
        "stage.skill_learning": "技能学习",
        "stage.skill_validation": "技能验证",
        "stage.skill_export": "导出技能",
        "stage.completed": "已完成",
        "stage.failed": "失败",
        "btn.submit": "发起任务",
        "btn.approve": "批准",
        "btn.reject": "拒绝",
        "btn.details": "查看详情",
        "btn.close": "关闭",
        "btn.switch_zh": "中文",
        "btn.switch_en": "English",
        "btn.switch_both": "中英双语",
        "label.risk_none": "无风险",
        "label.risk_low": "低风险",
        "label.risk_medium": "中风险",
        "label.risk_high": "高风险",
        "label.importance_debug": "调试",
        "label.importance_normal": "正常",
        "label.importance_important": "重要",
        "label.importance_critical": "关键",
        "label.in_progress": "进行中",
        "label.completed": "已完成",
        "label.waiting": "等待中",
        "label.failed": "失败",
        "label.no_learning": "本轮未触发学习",
        "label.yes": "是",
        "label.no": "否",
    },
    "en": {
        "stage.task_intake": "Task Intake",
        "stage.intent_parse": "Intent Parsing",
        "stage.context_budget": "Token Budgeting",
        "stage.memory_retrieval": "Memory Retrieval",
        "stage.rag_retrieval": "Knowledge Search",
        "stage.context_build": "Context Assembly",
        "stage.planning": "Planning",
        "stage.tool_call": "Tool Call",
        "stage.security_check": "Security Check",
        "stage.approval_waiting": "Awaiting Approval",
        "stage.execution": "Execution",
        "stage.evaluation": "Evaluation",
        "stage.badcase_record": "Bad Case Recording",
        "stage.skill_learning": "Skill Learning",
        "stage.skill_validation": "Skill Validation",
        "stage.skill_export": "Skill Export",
        "stage.completed": "Completed",
        "stage.failed": "Failed",
        "btn.submit": "Submit",
        "btn.approve": "Approve",
        "btn.reject": "Reject",
        "btn.details": "Details",
        "btn.close": "Close",
        "btn.switch_zh": "中文",
        "btn.switch_en": "English",
        "btn.switch_both": "Bilingual",
        "label.risk_none": "No Risk",
        "label.risk_low": "Low Risk",
        "label.risk_medium": "Medium Risk",
        "label.risk_high": "High Risk",
        "label.importance_debug": "Debug",
        "label.importance_normal": "Normal",
        "label.importance_important": "Important",
        "label.importance_critical": "Critical",
        "label.in_progress": "In Progress",
        "label.completed": "Completed",
        "label.waiting": "Waiting",
        "label.failed": "Failed",
        "label.no_learning": "No learning triggered",
        "label.yes": "Yes",
        "label.no": "No",
    },
}


class I18nManager:
    """全局翻译管理器。"""
    _instance: I18nManager | None = None

    # ------------------------------------------------------------------
    # 语义阶段 → 中英双语映射（与前端 AVATAR_STATE_MAP 的 14 个阶段对齐）
    # ------------------------------------------------------------------
    _STAGE_TRANSLATIONS: dict[str, dict[str, str]] = {
        "listening":        {"zh": "正在接收任务",          "en": "Receiving task"},
        "thinking":         {"zh": "正在理解你的需求",       "en": "Understanding your intent"},
        "reading_notes":    {"zh": "正在找以前的经验",       "en": "Retrieving prior memory"},
        "searching_books":  {"zh": "正在查找项目资料",       "en": "Searching project knowledge"},
        "calculating":      {"zh": "正在计算 token 成本",    "en": "Estimating token budget"},
        "planning":         {"zh": "正在规划执行步骤",       "en": "Planning execution steps"},
        "tooling":          {"zh": "正在调用工具",           "en": "Calling a tool"},
        "safety_check":     {"zh": "正在做安全检查",         "en": "Running safety check"},
        "waiting_approval": {"zh": "等待你确认",             "en": "Waiting for approval"},
        "grading":          {"zh": "正在评估结果",           "en": "Evaluating output"},
        "learning":         {"zh": "正在总结经验",           "en": "Learning from this run"},
        "archiving":        {"zh": "正在更新 best_skill.md", "en": "Updating best_skill.md"},
        "done":             {"zh": "任务完成",               "en": "Task completed"},
        "failed":           {"zh": "任务失败，正在记录原因",  "en": "Task failed, recording reason"},
    }

    @classmethod
    def translate_stage(cls, stage: str, locale: str = "zh") -> str:
        """将 AVATAR_STATE_MAP 中的语义阶段翻译为中/英文。

        Args:
            stage: 阶段 key，如 "listening"、"thinking" 等。
            locale: 目标语言，"zh" 或 "en"。

        Returns:
            翻译后的字符串；若 stage 未注册则原样返回 stage。
        """
        info = cls._STAGE_TRANSLATIONS.get(stage, {})
        return info.get(locale, stage)

    def __init__(self, default_locale: str = "zh") -> None:
        self._locale: Literal["zh", "en", "both"] = default_locale

    def t(self, key: str, locale: str = "zh", **kwargs) -> str:
        return _TRANSLATIONS.get(locale, {}).get(key, key).format(**kwargs)

    def set_locale(self, locale: Literal["zh", "en", "both"]) -> None:
        self._locale = locale

    @property
    def locale(self) -> str:
        return self._locale
