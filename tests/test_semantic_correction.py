"""test_semantic_correction.py — 纠正记录和假设追踪测试。

测试覆盖:
- "下次别这样" 能生成 correction/bad case
- 用户纠正后能生成 expression rule candidate
- 假设追踪器功能
- CorrectionStore 持久化
"""

from __future__ import annotations

import json
import os
import tempfile

from stable_agent.understanding.correction_store import CorrectionStore
from stable_agent.understanding.assumption_tracker import AssumptionTracker
from stable_agent.understanding.schemas import CorrectionRecord, AssumptionRecord


class TestCorrectionStore:
    """纠正记录存储测试。"""

    def setup_method(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.tmpdir, "corrections.jsonl")

    def teardown_method(self) -> None:
        if os.path.exists(self.storage_path):
            os.remove(self.storage_path)
        os.rmdir(self.tmpdir)

    def test_add_correction(self) -> None:
        """测试添加纠正记录。"""
        store = CorrectionStore(storage_path=self.storage_path)
        record = CorrectionRecord(
            run_id="run_001",
            wrong_interpretation="以为要重构整个模块",
            correct_interpretation="只改错误处理部分",
            trigger_phrase="下次别这样",
        )
        store.add_correction(record)

        corrections = store.get_corrections()
        assert len(corrections) == 1
        assert corrections[0].wrong_interpretation == "以为要重构整个模块"

    def test_get_corrections_by_run_id(self) -> None:
        """测试按 run_id 过滤。"""
        store = CorrectionStore(storage_path=self.storage_path)
        store.add_correction(CorrectionRecord(run_id="run_001", wrong_interpretation="A"))
        store.add_correction(CorrectionRecord(run_id="run_002", wrong_interpretation="B"))

        corrections = store.get_corrections(run_id="run_001")
        assert len(corrections) == 1
        assert corrections[0].wrong_interpretation == "A"

    def test_convert_to_expression_rule(self) -> None:
        """测试纠正记录转化为表达规则。"""
        store = CorrectionStore(storage_path=self.storage_path)
        record = CorrectionRecord(
            run_id="run_001",
            wrong_interpretation="以为要重构",
            correct_interpretation="只改错误处理",
            trigger_phrase="下次别这样",
        )
        store.add_correction(record)

        profile = store.convert_to_expression_rule(record.correction_id)
        assert profile is not None
        assert profile.phrase == "下次别这样"
        assert profile.normalized_meaning == ["只改错误处理"]
        assert profile.confirmed_by_user is True
        assert profile.confidence == 0.9

    def test_convert_already_converted(self) -> None:
        """测试重复转化返回 None。"""
        store = CorrectionStore(storage_path=self.storage_path)
        record = CorrectionRecord(
            wrong_interpretation="A",
            correct_interpretation="B",
            trigger_phrase="测试",
        )
        store.add_correction(record)

        store.convert_to_expression_rule(record.correction_id)
        result = store.convert_to_expression_rule(record.correction_id)
        assert result is None

    def test_convert_nonexistent(self) -> None:
        """测试转化不存在的记录。"""
        store = CorrectionStore(storage_path=self.storage_path)
        result = store.convert_to_expression_rule("nonexistent_id")
        assert result is None

    def test_persistence(self) -> None:
        """测试持久化可读回。"""
        store = CorrectionStore(storage_path=self.storage_path)
        store.add_correction(CorrectionRecord(
            run_id="run_001",
            wrong_interpretation="错误理解",
            correct_interpretation="正确理解",
            trigger_phrase="下次别这样",
        ))

        # 重新加载
        store2 = CorrectionStore(storage_path=self.storage_path)
        corrections = store2.get_corrections()
        assert len(corrections) == 1
        assert corrections[0].wrong_interpretation == "错误理解"
        assert corrections[0].trigger_phrase == "下次别这样"

    def test_correction_json_serializable(self) -> None:
        """测试纠正记录可 JSON 序列化。"""
        record = CorrectionRecord(
            run_id="run_001",
            wrong_interpretation="错误",
            correct_interpretation="正确",
            trigger_phrase="下次别这样",
        )
        d = record.to_dict()
        json_str = json.dumps(d, ensure_ascii=False)
        assert json_str
        restored = json.loads(json_str)
        assert restored["correction_id"] == record.correction_id


class TestAssumptionTracker:
    """假设追踪器测试。"""

    def test_track_assumption(self) -> None:
        """测试记录假设。"""
        tracker = AssumptionTracker()
        record = tracker.track_assumption("trace_001", "假设需要项目上下文", 0.8)
        assert record.trace_id == "trace_001"
        assert record.assumption == "假设需要项目上下文"
        assert record.confidence == 0.8

    def test_get_assumptions(self) -> None:
        """测试获取指定 trace 的假设。"""
        tracker = AssumptionTracker()
        tracker.track_assumption("trace_001", "假设A", 0.8)
        tracker.track_assumption("trace_001", "假设B", 0.6)
        tracker.track_assumption("trace_002", "假设C", 0.7)

        assumptions = tracker.get_assumptions("trace_001")
        assert len(assumptions) == 2

    def test_list_unconfirmed(self) -> None:
        """测试列出未确认假设。"""
        tracker = AssumptionTracker()
        r1 = tracker.track_assumption("trace_001", "假设A", 0.8)
        tracker.track_assumption("trace_001", "假设B", 0.6)

        unconfirmed = tracker.list_unconfirmed()
        assert len(unconfirmed) == 2

        tracker.confirm_assumption(r1.assumption_id)
        unconfirmed = tracker.list_unconfirmed()
        assert len(unconfirmed) == 1

    def test_confirm_assumption(self) -> None:
        """测试确认假设。"""
        tracker = AssumptionTracker()
        record = tracker.track_assumption("trace_001", "假设A", 0.8)

        result = tracker.confirm_assumption(record.assumption_id)
        assert result is True

        assumptions = tracker.get_assumptions("trace_001")
        assert assumptions[0].confirmed is True

    def test_confirm_nonexistent(self) -> None:
        """测试确认不存在的假设。"""
        tracker = AssumptionTracker()
        result = tracker.confirm_assumption("nonexistent_id")
        assert result is False
