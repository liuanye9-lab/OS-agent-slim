"""Tests for BilingualText + I18nManager — V5.5."""
import pytest
from stable_agent.explanation.bilingual_text import BilingualText, I18nManager


class TestBilingualText:
    def test_defaults(self):
        bt = BilingualText()
        assert bt.zh == ""
        assert bt.en == ""

    def test_get_zh(self):
        bt = BilingualText(zh="你好", en="Hello")
        assert bt.get("zh") == "你好"

    def test_get_en(self):
        bt = BilingualText(zh="你好", en="Hello")
        assert bt.get("en") == "Hello"


class TestI18nManager:
    def test_default_locale(self):
        i18n = I18nManager()
        assert i18n.locale == "zh"

    def test_set_locale(self):
        i18n = I18nManager()
        i18n.set_locale("en")
        assert i18n.locale == "en"
        i18n.set_locale("both")
        assert i18n.locale == "both"

    def test_t_zh_stage(self):
        i18n = I18nManager()
        result = i18n.t("stage.memory_retrieval", "zh")
        assert "检索记忆" == result

    def test_t_en_stage(self):
        i18n = I18nManager()
        result = i18n.t("stage.memory_retrieval", "en")
        assert "Memory Retrieval" == result

    def test_t_unknown_key_returns_key(self):
        i18n = I18nManager()
        assert i18n.t("nonexistent.key") == "nonexistent.key"

    def test_t_btn_labels(self):
        i18n = I18nManager()
        assert i18n.t("btn.approve", "zh") == "批准"
        assert i18n.t("btn.approve", "en") == "Approve"

    def test_t_risk_labels(self):
        i18n = I18nManager()
        assert i18n.t("label.risk_high", "zh") == "高风险"
        assert i18n.t("label.risk_high", "en") == "High Risk"

    def test_t_importance_labels(self):
        i18n = I18nManager()
        assert i18n.t("label.importance_critical", "zh") == "关键"
        assert i18n.t("label.importance_critical", "en") == "Critical"
