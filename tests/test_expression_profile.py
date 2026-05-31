"""test_expression_profile.py — 表达习惯管理器测试。

测试覆盖:
- 添加/删除/列出表达习惯
- 匹配文本中的已知表达
- 持久化可读回
- 同类表达下次能命中 expression profile
"""

from __future__ import annotations

import json
import os
import tempfile

from stable_agent.understanding.expression_profile import ExpressionProfileManager


class TestExpressionProfileManager:
    """表达习惯管理器测试。"""

    def setup_method(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.tmpdir, "expressions.json")

    def teardown_method(self) -> None:
        if os.path.exists(self.storage_path):
            os.remove(self.storage_path)
        os.rmdir(self.tmpdir)

    # ------------------------------------------------------------------
    # 添加和列出
    # ------------------------------------------------------------------

    def test_add_expression(self) -> None:
        """测试添加表达习惯。"""
        mgr = ExpressionProfileManager(storage_path=self.storage_path)
        profile = mgr.add_expression(
            phrase="继续优化",
            meaning=["需要项目上下文继续改进"],
            scope="global",
        )
        assert profile.phrase == "继续优化"
        assert profile.normalized_meaning == ["需要项目上下文继续改进"]

    def test_list_expressions(self) -> None:
        """测试列出所有表达习惯。"""
        mgr = ExpressionProfileManager(storage_path=self.storage_path)
        mgr.add_expression("继续优化", ["继续改进"])
        mgr.add_expression("不要跑偏", ["保持原有风格"])

        profiles = mgr.list_expressions()
        assert len(profiles) == 2

    def test_list_expressions_by_scope(self) -> None:
        """测试按作用域过滤。"""
        mgr = ExpressionProfileManager(storage_path=self.storage_path)
        mgr.add_expression("继续优化", ["继续改进"], scope="global")
        mgr.add_expression("重构代码", ["重构"], scope="coding")

        global_profiles = mgr.list_expressions(scope="global")
        assert len(global_profiles) == 1
        assert global_profiles[0].phrase == "继续优化"

        coding_profiles = mgr.list_expressions(scope="coding")
        assert len(coding_profiles) == 1

    # ------------------------------------------------------------------
    # 删除
    # ------------------------------------------------------------------

    def test_delete_expression(self) -> None:
        """测试删除表达习惯。"""
        mgr = ExpressionProfileManager(storage_path=self.storage_path)
        mgr.add_expression("继续优化", ["继续改进"])

        deleted = mgr.delete_expression("继续优化")
        assert deleted is True
        assert len(mgr.list_expressions()) == 0

    def test_delete_nonexistent(self) -> None:
        """测试删除不存在的表达习惯。"""
        mgr = ExpressionProfileManager(storage_path=self.storage_path)
        deleted = mgr.delete_expression("不存在的短语")
        assert deleted is False

    # ------------------------------------------------------------------
    # 匹配
    # ------------------------------------------------------------------

    def test_match_expressions(self) -> None:
        """测试匹配文本中的已知表达。"""
        mgr = ExpressionProfileManager(storage_path=self.storage_path)
        mgr.add_expression("继续优化", ["需要项目上下文继续改进"])
        mgr.add_expression("不要跑偏", ["保持原有风格"])

        matches = mgr.match_expressions("继续优化这个项目")
        assert len(matches) == 1
        assert matches[0].phrase == "继续优化"

    def test_match_multiple_expressions(self) -> None:
        """测试同时匹配多个表达。"""
        mgr = ExpressionProfileManager(storage_path=self.storage_path)
        mgr.add_expression("继续优化", ["继续改进"])
        mgr.add_expression("这个项目", ["当前项目"])

        matches = mgr.match_expressions("继续优化这个项目")
        assert len(matches) == 2

    def test_match_no_expressions(self) -> None:
        """测试无匹配。"""
        mgr = ExpressionProfileManager(storage_path=self.storage_path)
        mgr.add_expression("继续优化", ["继续改进"])

        matches = mgr.match_expressions("实现新功能")
        assert len(matches) == 0

    def test_same_expression_hits_next_time(self) -> None:
        """测试同类表达下次能命中 expression profile。"""
        mgr = ExpressionProfileManager(storage_path=self.storage_path)
        mgr.add_expression("别 AI 味", ["保持自然风格"])

        # 第一次匹配
        matches1 = mgr.match_expressions("改一下文案，别 AI 味")
        assert len(matches1) == 1

        # 创建新管理器实例 (模拟下次会话)
        mgr2 = ExpressionProfileManager(storage_path=self.storage_path)
        matches2 = mgr2.match_expressions("这次输出别 AI 味")
        assert len(matches2) == 1
        assert matches2[0].phrase == "别 AI 味"

    # ------------------------------------------------------------------
    # 持久化
    # ------------------------------------------------------------------

    def test_persistence(self) -> None:
        """测试持久化可读回。"""
        mgr = ExpressionProfileManager(storage_path=self.storage_path)
        mgr.add_expression(
            phrase="继续优化",
            meaning=["需要项目上下文继续改进"],
            scope="global",
            confirmed=True,
            confidence=0.8,
            examples=["继续优化这个项目"],
        )

        # 重新加载
        mgr2 = ExpressionProfileManager(storage_path=self.storage_path)
        profiles = mgr2.list_expressions()
        assert len(profiles) == 1
        assert profiles[0].phrase == "继续优化"
        assert profiles[0].normalized_meaning == ["需要项目上下文继续改进"]
        assert profiles[0].confirmed_by_user is True
        assert profiles[0].confidence == 0.8
        assert profiles[0].examples == ["继续优化这个项目"]

    def test_persistence_json_valid(self) -> None:
        """测试持久化文件是有效 JSON。"""
        mgr = ExpressionProfileManager(storage_path=self.storage_path)
        mgr.add_expression("测试", ["测试含义"])

        with open(self.storage_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["phrase"] == "测试"

    # ------------------------------------------------------------------
    # 更新已有记录
    # ------------------------------------------------------------------

    def test_update_existing_expression(self) -> None:
        """测试更新已有的表达习惯。"""
        mgr = ExpressionProfileManager(storage_path=self.storage_path)
        mgr.add_expression("继续优化", ["旧含义"])
        mgr.add_expression("继续优化", ["新含义"], confidence=0.9)

        profiles = mgr.list_expressions()
        assert len(profiles) == 1
        assert profiles[0].normalized_meaning == ["新含义"]
        assert profiles[0].confidence == 0.9
