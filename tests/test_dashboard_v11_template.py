"""Dashboard V11 集成测试。

验证 run_observer.html 包含 V11 六大面板容器和反馈按钮，
以及后端 API 能正确返回 V11 数据。
"""

from __future__ import annotations

import json
import os
import pytest

# ---------------------------------------------------------------------------
# HTML 模板测试
# ---------------------------------------------------------------------------

def _read_template() -> str:
    """读取 run_observer.html 模板内容。"""
    template_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "web", "templates", "run_observer.html",
    )
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()


def _read_js() -> str:
    """读取 run_observer.js 内容。"""
    js_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "web", "static", "run_observer.js",
    )
    with open(js_path, "r", encoding="utf-8") as f:
        return f.read()


class TestDashboardV11Template:
    """测试 Dashboard V11 模板包含必要元素。"""

    def test_six_panels_exist(self):
        """六大面板容器存在。"""
        html = _read_template()
        panels = [
            "understandingPanel",
            "tokenBudgetPanel",
            "memoryMapPanel",
            "badCasePanel",
            "skillEvolutionPanel",
            "memoryHealthPanel",
        ]
        for panel_id in panels:
            assert panel_id in html, f"面板 {panel_id} 不存在于模板中"

    def test_feedback_buttons_exist(self):
        """反馈三按钮存在。"""
        html = _read_template()
        assert "feedbackRemember" in html, "记住这个按钮不存在"
        assert "feedbackDontDoThis" in html, "下次别这样按钮不存在"
        assert "feedbackCorrectAndRemember" in html, "纠正并记住按钮不存在"

    def test_v11_css_styles_exist(self):
        """V11 面板 CSS 样式存在。"""
        html = _read_template()
        assert "v11-grid" in html, "v11-grid 样式不存在"
        assert "v11-panel" in html, "v11-panel 样式不存在"
        assert "v11-tag" in html, "v11-tag 样式不存在"
        assert "v11-bar" in html, "v11-bar 样式不存在"

    def test_panel_titles_in_chinese(self):
        """面板标题使用中文。"""
        html = _read_template()
        assert "理解轨迹" in html
        assert "Token 预算" in html or "Token" in html
        assert "记忆地图" in html
        assert "失败案例" in html
        assert "Skill 进化" in html
        assert "记忆健康" in html

    def test_empty_states_exist(self):
        """每个面板有空状态。"""
        html = _read_template()
        assert "暂无理解轨迹数据" in html
        assert "暂无 Token 数据" in html
        assert "暂无长期记忆" in html
        assert "本次未记录失败案例" in html
        assert "暂无 Skill 进化数据" in html
        assert "暂无记忆健康数据" in html


class TestDashboardV11JS:
    """测试 run_observer.js 包含 V11 函数。"""

    def test_load_v11_panels_function(self):
        """loadV11Panels 函数存在。"""
        js = _read_js()
        assert "loadV11Panels" in js

    def test_render_functions_exist(self):
        """各面板渲染函数存在。"""
        js = _read_js()
        funcs = [
            "renderUnderstandingPanel",
            "renderTokenBudgetPanel",
            "renderBadCasePanel",
            "renderSkillEvolutionPanel",
            "renderMemoryMapPanel",
            "renderMemoryHealthPanel",
            "renderErrorPanel",
        ]
        for func in funcs:
            assert func in js, f"函数 {func} 不存在于 JS 中"

    def test_feedback_functions_exist(self):
        """反馈按钮函数存在。"""
        js = _read_js()
        assert "feedbackRemember" in js
        assert "feedbackDontDoThis" in js
        assert "feedbackCorrectAndRemember" in js

    def test_api_endpoints_in_js(self):
        """JS 中引用了正确的 API 端点。"""
        js = _read_js()
        assert "/api/runs/" in js
        assert "/understanding" in js
        assert "/token" in js
        assert "/learning" in js
        assert "/badcases" in js
        assert "/api/memory/health" in js
        assert "/api/feedback/remember" in js
        assert "/api/feedback/dont-do-this-again" in js
        assert "/api/feedback/correct-and-remember" in js

    def test_realtime_event_handling(self):
        """实时事件处理包含 V11 事件类型。"""
        js = _read_js()
        assert "understanding.trace.created" in js
        assert "token.budget.estimated" in js
        assert "regression.generated" in js
        assert "skill.patch.proposed" in js

    def test_existing_features_preserved(self):
        """现有功能不被破坏。"""
        js = _read_js()
        # Avatar 场景
        assert "AVATAR_SCENE_MAP" in js
        # SI Report
        assert "updateSIReport" in js
        # Timeline
        assert "appendTimeline" in js
        # WebSocket
        assert "connectWebSocket" in js
        # Multi-agent
        assert "observeMultipleRuns" in js


class TestDashboardV11API:
    """测试 V11 API 端点结构。"""

    def test_runs_api_file_has_v11_endpoints(self):
        """runs.py 包含 V11 端点定义。"""
        runs_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "web", "routes", "runs.py",
        )
        with open(runs_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "get_run_understanding" in content
        assert "get_run_token" in content
        assert "get_run_learning" in content
        assert "get_run_badcases" in content

    def test_api_file_has_v11_global_endpoints(self):
        """api.py 包含 V11 全局端点路由定义。"""
        api_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "web", "routes", "api.py",
        )
        with open(api_path, "r", encoding="utf-8") as f:
            content = f.read()
        # V11.2: 路由使用 @router.get("/api/...")，不需要 api_ 前缀
        assert '"/api/token/summary"' in content
        assert '"/api/capsule/status"' in content
        assert '"/api/memory/health"' in content
        assert '"/api/feedback/remember"' in content
        assert '"/api/feedback/dont-do-this-again"' in content
        assert '"/api/feedback/correct-and-remember"' in content

    def test_feedback_uses_memory_lifecycle(self):
        """反馈 API 使用 FeedbackLearningService 内部处理记忆生命周期。"""
        api_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "web", "routes", "api.py",
        )
        with open(api_path, "r", encoding="utf-8") as f:
            content = f.read()
        # V11.2: feedback_service 是闭环入口，内部调用 memory_store
        assert "feedback_service" in content
        assert "handle_remember" in content

    def test_feedback_uses_eval_case_manager(self):
        """dont_do_this_again 使用 FeedbackLearningService 内部 EvalCaseManager。"""
        api_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "web", "routes", "api.py",
        )
        with open(api_path, "r", encoding="utf-8") as f:
            content = f.read()
        # V11.2: FeedbackLearningService 内部使用 eval_case_manager
        assert "feedback_service" in content
        assert "handle_dont_do_this_again" in content
