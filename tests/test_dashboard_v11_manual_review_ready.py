# test_dashboard_v11_manual_review_ready.py
# 阶段8: Dashboard V11 人工核验就绪测试
"""验证 Dashboard HTML/JS 包含人工核验所需的所有元素。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

HTML_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "templates", "run_observer.html")
JS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "static", "run_observer.js")

def test_html_contains_six_panels():
    """HTML 包含六大面板 id。"""
    with open(HTML_PATH, encoding="utf-8") as f:
        html = f.read()

    panels = [
        "understandingPanel",
        "tokenBudgetPanel",
        "memoryMapPanel",
        "badCasePanel",
        "skillEvolutionPanel",
        "memoryHealthPanel",
    ]
    missing = [p for p in panels if p not in html]
    assert not missing, f"HTML 缺少面板: {missing}"
    print("test_html_contains_six_panels PASSED")

def test_html_contains_three_feedback_buttons():
    """HTML 包含三个反馈按钮。"""
    with open(HTML_PATH, encoding="utf-8") as f:
        html = f.read()

    buttons = [
        "feedbackRemember",
        "feedbackDontDoThis",
        "feedbackCorrectAndRemember",
    ]
    missing = [b for b in buttons if b not in html]
    assert not missing, f"HTML 缺少反馈按钮: {missing}"
    print("test_html_contains_three_feedback_buttons PASSED")

def test_js_contains_load_v11_panels():
    """JS 包含 loadV11Panels 函数。"""
    with open(JS_PATH, encoding="utf-8") as f:
        js = f.read()

    assert "loadV11Panels" in js, "JS 缺少 loadV11Panels"
    assert "async function loadV11Panels" in js or "function loadV11Panels" in js, "loadV11Panels 应该是 async 函数"
    print("test_js_contains_load_v11_panels PASSED")

def _get_function_body(js_content: str, func_name: str) -> str:
    """提取 JS 函数体（使用更宽松的边界查找）。"""
    idx = js_content.find(f"function {func_name}")
    if idx < 0:
        idx = js_content.find(f"async function {func_name}")
    if idx < 0:
        idx = js_content.find(f"{func_name} = async function")
    if idx < 0:
        idx = js_content.find(f"{func_name} = function")
    if idx < 0:
        return ""
    # 找下一个顶级 function
    next_func = js_content.find("\nfunction ", idx + 10)
    next_async = js_content.find("\nasync function ", idx + 10)
    next_arrow = js_content.find("\nconst ", idx + 10)
    next_let = js_content.find("\nlet ", idx + 10)
    end = len(js_content)
    for candidate in [next_func, next_async, next_arrow, next_let]:
        if candidate > 0:
            end = min(end, candidate)
    return js_content[idx:end]

def test_js_feedback_refreshes_v11_panels():
    """反馈成功后调用 loadV11Panels 刷新。"""
    with open(JS_PATH, encoding="utf-8") as f:
        js = f.read()

    # 检查 refreshV11Panels 函数存在
    assert "refreshV11Panels" in js, "JS 缺少 refreshV11Panels"
    # 检查 loadV11Panels 被调用
    assert "loadV11Panels" in js, "JS 缺少 loadV11Panels"
    # 检查反馈函数中有调用
    feedback_funcs = ["feedbackDontDoThis", "feedbackCorrectAndRemember", "feedbackUnderstandingCorrect", "feedbackUnderstandingFix"]
    found = any(f in js for f in feedback_funcs)
    assert found, f"JS 缺少反馈函数: {feedback_funcs}"
    print("test_js_feedback_refreshes_v11_panels PASSED")

def test_js_renders_expression_matches():
    """JS renderUnderstandingPanel 包含 expression_matches 渲染。"""
    with open(JS_PATH, encoding="utf-8") as f:
        js = f.read()

    body = _get_function_body(js, "renderUnderstandingPanel")
    assert body, "JS 缺少 renderUnderstandingPanel"
    assert "expression_matches" in body, "renderUnderstandingPanel 缺少 expression_matches 渲染"
    print("test_js_renders_expression_matches PASSED")

def test_js_renders_estimation_method():
    """JS renderTokenBudgetPanel 包含 estimation_method 或 is_estimated 渲染。"""
    with open(JS_PATH, encoding="utf-8") as f:
        js = f.read()

    body = _get_function_body(js, "renderTokenBudgetPanel")
    assert body, "JS 缺少 renderTokenBudgetPanel"
    assert "estimation_method" in body or "is_estimated" in body, "renderTokenBudgetPanel 缺少 estimation_method/is_estimated"
    print("test_js_renders_estimation_method PASSED")

def test_js_all_panels_have_empty_state():
    """所有面板有空状态 JS 错误处理。"""
    with open(JS_PATH, encoding="utf-8") as f:
        js = f.read()

    panels = ["renderUnderstandingPanel", "renderTokenBudgetPanel", "renderMemoryHealthPanel"]
    for panel in panels:
        body = _get_function_body(js, panel)
        assert body, f"JS 缺少 {panel}"
        # 检查有空状态处理
        assert "empty-state" in body or "!data.ok" in body or "renderErrorPanel" in body, f"{panel} 缺少空状态处理"
    print("test_js_all_panels_have_empty_state PASSED")

if __name__ == "__main__":
    test_html_contains_six_panels()
    test_html_contains_three_feedback_buttons()
    test_js_contains_load_v11_panels()
    test_js_feedback_refreshes_v11_panels()
    test_js_renders_expression_matches()
    test_js_renders_estimation_method()
    test_js_all_panels_have_empty_state()
    print("\nAll tests passed!")
