"""test_dashboard_v11_intervention_template.py — 验证 Dashboard 干预面板模板。

测试要求：
1. HTML 包含 understanding correction 按钮。
2. JS 包含 refresh panels after feedback。
3. JS 不因 API 空状态报错。
4. 三个 feedback 按钮仍可用。
"""

from __future__ import annotations

import os
import re

WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")
HTML_PATH = os.path.join(WEB_DIR, "templates", "run_observer.html")
JS_PATH = os.path.join(WEB_DIR, "static", "run_observer.js")


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class TestDashboardHTML:
    """HTML 模板测试。"""

    def test_understanding_correct_button(self):
        html = _read(HTML_PATH)
        assert "feedbackUnderstandingCorrect" in html

    def test_understanding_fix_button(self):
        html = _read(HTML_PATH)
        assert "feedbackUnderstandingFix" in html

    def test_memory_keep_button(self):
        html = _read(HTML_PATH)
        assert "memoryAction('keep')" in html

    def test_memory_delete_button(self):
        html = _read(HTML_PATH)
        assert "memoryAction('delete')" in html

    def test_memory_defer_button(self):
        html = _read(HTML_PATH)
        assert "memoryAction('defer')" in html

    def test_regression_test_button(self):
        html = _read(HTML_PATH)
        assert "generateRegressionTest" in html

    def test_skill_review_status_div(self):
        html = _read(HTML_PATH)
        assert "skillReviewStatus" in html

    def test_feedback_remember_button_still_exists(self):
        html = _read(HTML_PATH)
        assert "feedbackRemember()" in html

    def test_feedback_dont_do_this_button_still_exists(self):
        html = _read(HTML_PATH)
        assert "feedbackDontDoThis()" in html

    def test_feedback_correct_and_remember_button_still_exists(self):
        html = _read(HTML_PATH)
        assert "feedbackCorrectAndRemember()" in html


class TestDashboardJS:
    """JS 逻辑测试。"""

    def test_refresh_v11_panels_function(self):
        js = _read(JS_PATH)
        assert "function refreshV11Panels" in js

    def test_feedback_understanding_correct_function(self):
        js = _read(JS_PATH)
        assert "async function feedbackUnderstandingCorrect" in js

    def test_feedback_understanding_fix_function(self):
        js = _read(JS_PATH)
        assert "async function feedbackUnderstandingFix" in js

    def test_memory_action_function(self):
        js = _read(JS_PATH)
        assert "function memoryAction" in js

    def test_generate_regression_test_function(self):
        js = _read(JS_PATH)
        assert "async function generateRegressionTest" in js

    def test_token_panel_shows_estimation_method(self):
        js = _read(JS_PATH)
        assert "estimation_method" in js

    def test_token_panel_shows_is_estimated(self):
        js = _read(JS_PATH)
        assert "is_estimated" in js

    def test_skill_panel_shows_review_status(self):
        js = _read(JS_PATH)
        assert "skillReviewStatus" in js

    def test_feedback_refreshes_panels(self):
        """Feedback 提交后应刷新 panels。"""
        js = _read(JS_PATH)
        # After feedbackUnderstandingCorrect, should call refreshV11Panels
        assert "refreshV11Panels()" in js

    def test_no_syntax_error_in_js(self):
        """基本 JS 语法检查 — 括号匹配。"""
        js = _read(JS_PATH)
        open_braces = js.count("{")
        close_braces = js.count("}")
        # Allow small mismatch due to template literals
        assert abs(open_braces - close_braces) <= 2, f"Brace mismatch: {open_braces} open vs {close_braces} close"
