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

    def __init__(self, default_locale: str = "zh") -> None:
        self._locale: Literal["zh", "en", "both"] = default_locale

    def t(self, key: str, locale: str = "zh", **kwargs) -> str:
        return _TRANSLATIONS.get(locale, {}).get(key, key).format(**kwargs)

    def set_locale(self, locale: Literal["zh", "en", "both"]) -> None:
        self._locale = locale

    @property
    def locale(self) -> str:
        return self._locale
