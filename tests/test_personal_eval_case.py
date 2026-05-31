"""测试 personal_eval.eval_case — EvalCaseManager。"""

import json
import os
import tempfile

import pytest

from stable_agent.personal_eval.eval_case import EvalCaseManager
from stable_agent.personal_eval.schemas import PersonalEvalCase


@pytest.fixture
def tmp_jsonl(tmp_path):
    """返回临时 JSONL 文件路径。"""
    return str(tmp_path / "test_cases.jsonl")


@pytest.fixture
def manager(tmp_jsonl):
    """返回使用临时路径的 EvalCaseManager。"""
    return EvalCaseManager(storage_path=tmp_jsonl)


class TestEvalCaseManager:
    def test_create_case(self, manager):
        """创建评估用例。"""
        case = manager.create_case(
            task="修复登录页面的 CSS 布局问题",
            task_type="bug_fix",
            must_keep=["登录", "CSS"],
            must_avoid=["删除整个文件"],
            success_criteria="页面正常显示",
            failure_modes=["布局错乱"],
        )
        assert case.case_id.startswith("pec_")
        assert case.task == "修复登录页面的 CSS 布局问题"
        assert case.task_type == "bug_fix"
        assert "登录" in case.must_keep
        assert "删除整个文件" in case.must_avoid

    def test_list_cases(self, manager):
        """列出评估用例。"""
        manager.create_case(task="task1", task_type="bug_fix")
        manager.create_case(task="task2", task_type="code_gen")
        manager.create_case(task="task3", task_type="bug_fix")

        all_cases = manager.list_cases()
        assert len(all_cases) == 3

        bug_fix_cases = manager.list_cases(task_type="bug_fix")
        assert len(bug_fix_cases) == 2

        code_gen_cases = manager.list_cases(task_type="code_gen")
        assert len(code_gen_cases) == 1

    def test_get_case(self, manager):
        """获取指定 ID 的评估用例。"""
        case = manager.create_case(task="test task")
        retrieved = manager.get_case(case.case_id)
        assert retrieved is not None
        assert retrieved.task == "test task"

        # 不存在的 ID
        assert manager.get_case("nonexistent") is None

    def test_persistence(self, tmp_jsonl):
        """测试 JSONL 持久化。"""
        # 创建用例
        mgr1 = EvalCaseManager(storage_path=tmp_jsonl)
        case = mgr1.create_case(task="persistent task", task_type="ui_design")

        # 重新加载
        mgr2 = EvalCaseManager(storage_path=tmp_jsonl)
        loaded = mgr2.get_case(case.case_id)
        assert loaded is not None
        assert loaded.task == "persistent task"
        assert loaded.task_type == "ui_design"

    def test_persistence_append(self, tmp_jsonl):
        """测试多次追加持久化。"""
        mgr = EvalCaseManager(storage_path=tmp_jsonl)
        mgr.create_case(task="task1")
        mgr.create_case(task="task2")

        # 重新加载应包含两条
        mgr2 = EvalCaseManager(storage_path=tmp_jsonl)
        assert len(mgr2.list_cases()) == 2

    def test_to_dict_from_dict_roundtrip(self):
        """测试序列化/反序列化往返。"""
        case = PersonalEvalCase(
            task="test",
            must_keep=["a", "b"],
            must_avoid=["c"],
        )
        d = case.to_dict()
        restored = PersonalEvalCase.from_dict(d)
        assert restored.task == "test"
        assert restored.must_keep == ["a", "b"]
        assert restored.must_avoid == ["c"]

    def test_empty_storage_path(self, tmp_path):
        """不存在的存储路径不会报错。"""
        path = str(tmp_path / "nonexistent" / "dir" / "cases.jsonl")
        mgr = EvalCaseManager(storage_path=path)
        assert len(mgr.list_cases()) == 0
