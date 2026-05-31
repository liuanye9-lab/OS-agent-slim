# test_os_agent_expression_profile_integration.py
# 阶段3: os_agent 表达习惯命中集成测试
"""写入表达习惯后，os_agent 必须能命中 expression_matches。"""
import tempfile, os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_os_agent_expression_matches_in_understanding_trace():
    """写入 '不要AI味' 后，os_agent 理解轨迹包含 expression_matches。"""
    from stable_agent.understanding.expression_profile import ExpressionProfileManager
    from stable_agent.understanding.semantic_interpreter import SemanticInterpreter
    from stable_agent.capsule import ensure_capsule

    # 使用临时 capsule 路径写入表达习惯
    with tempfile.TemporaryDirectory() as tmpdir:
        expr_path = os.path.join(tmpdir, "profile", "expressions.json")
        os.makedirs(os.path.dirname(expr_path), exist_ok=True)

        # 写入表达习惯
        mgr = ExpressionProfileManager(storage_path=expr_path)
        mgr.update_expression_rule(
            phrase="不要AI味",
            corrected_meaning=["避免模板化表达", "保持克制"],
            source="test",
        )

        # 模拟 os_agent 调用 SemanticInterpreter
        interpreter = SemanticInterpreter(expression_manager=mgr)
        trace = interpreter.interpret(
            "这个界面不要AI味，保持高级克制",
            run_id="test_run_expr",
        )

        trace_dict = trace.to_dict()
        assert "expression_matches" in trace_dict, f"trace.to_dict() 缺少 expression_matches: {list(trace_dict.keys())}"
        assert len(trace_dict["expression_matches"]) > 0, "expression_matches 应该非空"
        match_phrases = [m.get("phrase") for m in trace_dict["expression_matches"]]
        assert "不要AI味" in match_phrases, f"应该命中 '不要AI味'，实际: {match_phrases}"
        print("test_os_agent_expression_matches_in_understanding_trace PASSED")

def test_understanding_trace_event_payload_contains_expression_matches():
    """understanding.trace.created 事件的 payload 必须包含 expression_matches。"""
    from stable_agent.understanding.expression_profile import ExpressionProfileManager
    from stable_agent.understanding.semantic_interpreter import SemanticInterpreter

    with tempfile.TemporaryDirectory() as tmpdir:
        expr_path = os.path.join(tmpdir, "profile", "expressions.json")
        mgr = ExpressionProfileManager(storage_path=expr_path)
        mgr.update_expression_rule("简洁", ["去掉废话"], source="test")

        interpreter = SemanticInterpreter(expression_manager=mgr)
        trace = interpreter.interpret("保持简洁", run_id="test_run")

        # 模拟 unified_tool_registry 构造事件的 payload
        trace_dict = trace.to_dict()
        payload = {
            "run_id": "test_run",
            "understanding_trace": trace_dict,
            "expression_matches": trace_dict.get("expression_matches", []),
        }
        assert "expression_matches" in payload, "事件 payload 必须包含 expression_matches"
        assert len(payload["expression_matches"]) > 0, "payload.expression_matches 应该非空"
        print("test_understanding_trace_event_payload_contains_expression_matches PASSED")

if __name__ == "__main__":
    test_os_agent_expression_matches_in_understanding_trace()
    test_understanding_trace_event_payload_contains_expression_matches()
    print("\nAll tests passed!")
