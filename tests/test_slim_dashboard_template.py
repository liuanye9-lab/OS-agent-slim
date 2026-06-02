"""tests.test_slim_dashboard_template — Dashboard 模板测试。"""

import os
import pytest


class TestSlimDashboardTemplate:
    """Dashboard 模板测试。"""

    def test_template_exists(self):
        """模板文件存在。"""
        template = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "web", "templates", "slim_dashboard.html"
        )
        assert os.path.exists(template), f"Template not found: {template}"

    def test_template_contains_title(self):
        """模板包含标题。"""
        template = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "web", "templates", "slim_dashboard.html"
        )
        with open(template, "r", encoding="utf-8") as f:
            content = f.read()
        assert "StableAgent" in content
        assert "Slim" in content

    def test_template_contains_sections(self):
        """模板包含所有必要 section。"""
        template = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "web", "templates", "slim_dashboard.html"
        )
        with open(template, "r", encoding="utf-8") as f:
            content = f.read()
        assert "system-status" in content
        assert "worker-panel" in content
        assert "task-queue" in content
        assert "run-timeline" in content
        assert "capsule-summary" in content
        assert "submit-task" in content
        assert "feedback" in content

    def test_css_exists(self):
        """CSS 文件存在。"""
        css = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "web", "static", "slim_dashboard.css"
        )
        assert os.path.exists(css), f"CSS not found: {css}"

    def test_js_exists(self):
        """JS 文件存在。"""
        js = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "web", "static", "slim_dashboard.js"
        )
        assert os.path.exists(js), f"JS not found: {js}"

    def test_template_references_static(self):
        """模板引用静态文件。"""
        template = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "web", "templates", "slim_dashboard.html"
        )
        with open(template, "r", encoding="utf-8") as f:
            content = f.read()
        assert "slim_dashboard.css" in content
        assert "slim_dashboard.js" in content
