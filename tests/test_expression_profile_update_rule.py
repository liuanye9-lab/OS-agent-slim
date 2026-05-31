# test_expression_profile_update_rule.py
# 阶段2: ExpressionProfileManager.update_expression_rule 测试
"""update_expression_rule 必须能创建和更新表达规则，并持久化到 storage。"""
import tempfile, os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_update_creates_new_rule():
    """update_expression_rule 能创建新表达规则。"""
    from stable_agent.understanding.expression_profile import ExpressionProfileManager

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        mgr = ExpressionProfileManager(storage_path=path)
        rule_id = mgr.update_expression_rule(
            phrase="不要AI味",
            corrected_meaning=["避免模板化表达", "保持克制"],
            source="user_correction",
            confirmed=False,
            confidence=0.8,
        )
        assert rule_id == "不要AI味", f"返回的 rule_id 不对: {rule_id}"

        # 验证持久化
        with open(path) as f:
            data = json.load(f)
        assert len(data) == 1, f"应该只有1条记录，实际: {len(data)}"
        assert data[0]["phrase"] == "不要AI味"
        assert data[0]["confirmed_by_user"] is False, "默认不 confirmed"
        assert data[0]["confidence"] == 0.8
        print("test_update_creates_new_rule PASSED")
    finally:
        os.unlink(path)

def test_update_updates_existing_rule():
    """update_expression_rule 能更新已有表达规则。"""
    from stable_agent.understanding.expression_profile import ExpressionProfileManager

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        mgr = ExpressionProfileManager(storage_path=path)
        # 先创建
        mgr.update_expression_rule("保持克制", ["避免模板化"], source="test1")
        # 再更新
        rule_id = mgr.update_expression_rule(
            phrase="保持克制",
            corrected_meaning=["更简洁", "更有力"],
            source="test2",
            confirmed=True,
            confidence=0.95,
        )
        assert rule_id == "保持克制"

        # 验证只有1条（更新而非新增）
        with open(path) as f:
            data = json.load(f)
        assert len(data) == 1, f"应该只有1条（更新），实际: {len(data)}"
        assert data[0]["confirmed_by_user"] is True, "更新后应该 confirmed"
        assert data[0]["confidence"] == 0.95
        assert "更简洁" in data[0]["normalized_meaning"]
        print("test_update_updates_existing_rule PASSED")
    finally:
        os.unlink(path)

def test_update_persists_across_reload():
    """重启后重新加载能读到 update_expression_rule 创建的记录。"""
    from stable_agent.understanding.expression_profile import ExpressionProfileManager

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        # 写入
        mgr1 = ExpressionProfileManager(storage_path=path)
        mgr1.update_expression_rule("简洁", ["去掉废话"], source="test")
        del mgr1

        # 重新加载
        mgr2 = ExpressionProfileManager(storage_path=path)
        profiles = mgr2.list_expressions()
        phrases = [p.phrase for p in profiles]
        assert "简洁" in phrases, f"重新加载后找不到 '简洁': {phrases}"
        print("test_update_persists_across_reload PASSED")
    finally:
        os.unlink(path)

def test_match_expressions_hits_updated_phrase():
    """match_expressions 能命中 update_expression_rule 创建的 phrase。"""
    from stable_agent.understanding.expression_profile import ExpressionProfileManager

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        mgr = ExpressionProfileManager(storage_path=path)
        mgr.update_expression_rule("不要AI味", ["避免模板化"], source="test")

        matches = mgr.match_expressions("这个界面不要AI味，保持高级克制")
        assert len(matches) > 0, "match_expressions 应该命中 '不要AI味'"
        assert matches[0].phrase == "不要AI味"
        print("test_match_expressions_hits_updated_phrase PASSED")
    finally:
        os.unlink(path)

if __name__ == "__main__":
    test_update_creates_new_rule()
    test_update_updates_existing_rule()
    test_update_persists_across_reload()
    test_match_expressions_hits_updated_phrase()
    print("\nAll tests passed!")
