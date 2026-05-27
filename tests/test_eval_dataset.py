"""测试 EvalDatasetManager 评估数据集管理模块。

覆盖 JSONL 读写、用例筛选、从 BadCase 生成回归用例和统计功能。
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from stable_agent.eval_dataset import EvalDatasetManager
from stable_agent.models import (
    BadCase,
    EvalCase,
    EvaluationResult,
    TaskType,
)


class TestEvalDatasetManager:
    """EvalDatasetManager 核心测试。"""

    @pytest.fixture
    def tmp_jsonl(self, tmp_path: Path) -> str:
        """使用 tmp_path fixture 创建临时 JSONL 文件路径。"""
        return str(tmp_path / "eval_dataset.jsonl")

    @pytest.fixture
    def manager(self, tmp_jsonl: str) -> EvalDatasetManager:
        """创建指向临时文件的 EvalDatasetManager。"""
        return EvalDatasetManager(dataset_path=tmp_jsonl)

    def test_load_empty_dataset(self, tmp_jsonl: str) -> None:
        """验证文件不存在时返回空列表。"""
        mgr = EvalDatasetManager(dataset_path=tmp_jsonl)
        cases = mgr.load_cases()
        assert cases == []
        assert isinstance(cases, list)

    def test_append_and_load_case(self, manager: EvalDatasetManager, tmp_jsonl: str) -> None:
        """验证追加一个用例后能正确加载。"""
        case = EvalCase(
            case_id="eval-001",
            input_task="测试任务",
            expected_behavior="期望行为",
            source="manual",
            task_type=TaskType.BUG_FIX,
        )
        manager.append_case(case)

        loaded = manager.load_cases()
        assert len(loaded) == 1
        assert loaded[0].case_id == "eval-001"
        assert loaded[0].input_task == "测试任务"
        assert loaded[0].source == "manual"
        assert loaded[0].task_type == TaskType.BUG_FIX

    def test_find_by_task_type(self, manager: EvalDatasetManager) -> None:
        """验证按任务类型筛选。"""
        # 追加不同 task_type 的用例
        case1 = EvalCase(
            case_id="eval-001", input_task="bug fix task",
            task_type=TaskType.BUG_FIX,
        )
        case2 = EvalCase(
            case_id="eval-002", input_task="refactor task",
            task_type=TaskType.ARCH_REFACTOR,
        )
        case3 = EvalCase(
            case_id="eval-003", input_task="another bug",
            task_type=TaskType.BUG_FIX,
        )
        manager.append_cases([case1, case2, case3])

        bug_fix_cases = manager.find_by_task_type(TaskType.BUG_FIX)
        assert len(bug_fix_cases) == 2
        assert all(c.task_type == TaskType.BUG_FIX for c in bug_fix_cases)

    def test_find_by_source(self, manager: EvalDatasetManager) -> None:
        """验证按来源筛选。"""
        case1 = EvalCase(
            case_id="eval-001", input_task="manual task",
            source="manual",
        )
        case2 = EvalCase(
            case_id="eval-002", input_task="auto task",
            source="auto_from_bad_case",
        )
        manager.append_cases([case1, case2])

        manual = manager.find_by_source("manual")
        auto = manager.find_by_source("auto_from_bad_case")

        assert len(manual) == 1
        assert manual[0].case_id == "eval-001"
        assert len(auto) == 1
        assert auto[0].case_id == "eval-002"

    def test_create_from_bad_case(self, manager: EvalDatasetManager) -> None:
        """验证从 BadCase 生成 EvalCase。"""
        eval_result = EvaluationResult(overall_score=0.3)
        bad_case = BadCase(
            task_type=TaskType.BUG_FIX,
            input_context="修复登录页面样式错乱",
            output="CSS 样式丢失，需要重新添加 flexbox 属性",
            evaluation=eval_result,
            failure_reason="输出缺少具体代码修改，格式错误",
        )

        eval_case = manager.create_from_bad_case(bad_case)

        assert eval_case.source == "auto_from_bad_case"
        assert eval_case.input_task == "修复登录页面样式错乱"
        assert eval_case.task_type == TaskType.BUG_FIX
        assert eval_case.created_from_bad_case_id == str(bad_case.timestamp)
        # 应包含从 failure_reason 中提取的错误模式
        assert len(eval_case.must_not_include) > 0

    def test_create_from_bad_case_no_failure_reason(self, manager: EvalDatasetManager) -> None:
        """验证 failure_reason 为空时的行为。"""
        eval_result = EvaluationResult(overall_score=0.2)
        bad_case = BadCase(
            task_type=TaskType.GENERAL_QA,
            input_context="测试问题",
            output="短",
            evaluation=eval_result,
            failure_reason="",
        )

        eval_case = manager.create_from_bad_case(bad_case)
        assert eval_case.source == "auto_from_bad_case"
        # 短输出会导致 "输出过短" 被加入
        assert "输出过短" in eval_case.must_not_include

    def test_create_from_bad_case_with_expected_behavior(self, manager: EvalDatasetManager) -> None:
        """验证自定义 expected_behavior 被保留。"""
        eval_result = EvaluationResult(overall_score=0.3)
        bad_case = BadCase(
            task_type=TaskType.BUG_FIX,
            input_context="修复问题",
            output="详细输出内容，包含正确的修复方案和代码示例",
            evaluation=eval_result,
            failure_reason="缺少单元测试",
        )

        eval_case = manager.create_from_bad_case(
            bad_case,
            expected_behavior="应包含完整的单元测试代码",
        )
        assert eval_case.expected_behavior == "应包含完整的单元测试代码"

    def test_count_by_source(self, manager: EvalDatasetManager) -> None:
        """验证按来源统计数量。"""
        cases = [
            EvalCase(case_id="e1", input_task="t1", source="manual"),
            EvalCase(case_id="e2", input_task="t2", source="manual"),
            EvalCase(case_id="e3", input_task="t3", source="auto_from_bad_case"),
        ]
        manager.append_cases(cases)

        counts = manager.count_by_source()
        assert counts["manual"] == 2
        assert counts["auto_from_bad_case"] == 1

    def test_jsonl_persistence(self, tmp_path: Path) -> None:
        """验证 JSONL 文件持久化（跨实例读写）。"""
        jsonl_path = str(tmp_path / "persist.jsonl")

        # 写入
        mgr1 = EvalDatasetManager(dataset_path=jsonl_path)
        case = EvalCase(
            case_id="persist-001",
            input_task="持久化测试",
            source="manual",
            must_include=["正确结果"],
            must_not_include=["错误模式"],
        )
        mgr1.append_case(case)

        # 验证文件存在
        assert os.path.exists(jsonl_path)

        # 读取
        mgr2 = EvalDatasetManager(dataset_path=jsonl_path)
        loaded = mgr2.load_cases()
        assert len(loaded) == 1
        assert loaded[0].case_id == "persist-001"
        assert loaded[0].input_task == "持久化测试"
        assert "正确结果" in loaded[0].must_include
        assert "错误模式" in loaded[0].must_not_include

    def test_jsonl_file_is_valid_jsonl(self, tmp_path: Path) -> None:
        """验证写入的文件是有效的 JSONL 格式。"""
        jsonl_path = str(tmp_path / "valid.jsonl")
        mgr = EvalDatasetManager(dataset_path=jsonl_path)

        cases = [
            EvalCase(case_id="v1", input_task="task1"),
            EvalCase(case_id="v2", input_task="task2"),
        ]
        mgr.append_cases(cases)

        # 逐行解析验证
        with open(jsonl_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]

        assert len(lines) == 2
        for line in lines:
            parsed = json.loads(line)
            assert "case_id" in parsed
            assert "input_task" in parsed

    def test_load_corrupted_jsonl_graceful(self, tmp_path: Path) -> None:
        """验证损坏的 JSONL 文件不会导致崩溃。"""
        jsonl_path = str(tmp_path / "corrupt.jsonl")

        # 写入有效行 + 损坏行
        with open(jsonl_path, "w", encoding="utf-8") as f:
            f.write('{"case_id": "good", "input_task": "ok", "task_type": "general_qa"}\n')
            f.write("这不是有效的 JSON\n")
            f.write('{"case_id": "also-good", "input_task": "fine", "task_type": "general_qa"}\n')

        mgr = EvalDatasetManager(dataset_path=jsonl_path)
        loaded = mgr.load_cases()
        # 应该跳过损坏行，加载两行有效数据
        assert len(loaded) == 2
        ids = {c.case_id for c in loaded}
        assert "good" in ids
        assert "also-good" in ids
