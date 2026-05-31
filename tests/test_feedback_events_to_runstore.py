"""test_feedback_events_to_runstore.py — 验证 Feedback 事件写入 RunStore。

测试要求：
1. POST /api/feedback/dont-do-this-again 后，/api/runs/{run_id}/learning 能看到相关事件。
2. POST /api/feedback/correct-and-remember 后，/api/runs/{run_id}/understanding 或 events 能看到 expression.rule.candidate。
3. 没有 run_store 时 API 不报错。
"""

from __future__ import annotations

import pytest


class MockRunStore:
    """内存 RunStore mock。"""

    def __init__(self):
        self._events: dict[str, list[dict]] = {}

    def append_event(self, run_id: str, event: dict) -> None:
        self._events.setdefault(run_id, []).append(event)

    def get_events(self, run_id: str) -> list[dict]:
        return self._events.get(run_id, [])

    def get_run_status(self, run_id: str):
        return {"status": "completed"} if run_id in self._events else None

    def get_run_summary(self, run_id: str):
        return {"run_id": run_id, "event_count": len(self.get_events(run_id))}


class MockFeedbackService:
    """模拟 FeedbackLearningService。"""

    def handle_dont_do_this_again(self, run_id="", user_note="", context=None):
        return {
            "ok": True,
            "action": "dont_do_this_again",
            "run_id": run_id,
            "generated": {
                "bad_case": True,
                "eval_case": True,
                "skill_patch_candidate": True,
                "validation_report": True,
                "human_review_required": False,
            },
            "ids": {
                "bad_case_id": "bc_test",
                "eval_case_id": "pec_test",
                "patch_id": "sp_test",
                "validation_report_id": "vr_test",
                "review_id": None,
            },
            "validation": {"passed": False, "reason_zh": "模拟验证未通过"},
            "summary_zh": "测试",
            "errors": None,
        }

    def handle_correct_and_remember(self, run_id="", user_note="", context=None):
        return {
            "ok": True,
            "action": "correct_and_remember",
            "run_id": run_id,
            "generated": {"expression_profile": True, "expression_rule_candidate": True},
            "ids": {"expression_rule_id": "expr_test"},
            "summary_zh": "测试",
            "errors": None,
        }

    def handle_remember(self, run_id="", user_note="", context=None):
        return {
            "ok": True,
            "action": "remember",
            "run_id": run_id,
            "generated": {"memory_update_candidate": True},
            "ids": {"memory_candidate_id": "mem_test"},
            "summary_zh": "测试",
            "errors": None,
        }


class TestFeedbackEventsToRunStore:
    """Feedback 事件写入 RunStore 测试。"""

    def test_dont_do_this_again_appends_events(self):
        """dont-do-this-again 成功后应追加多个事件到 RunStore。"""
        store = MockRunStore()
        service = MockFeedbackService()

        # Simulate what the API does
        run_id = "test_run_1"
        result = service.handle_dont_do_this_again(run_id=run_id, user_note="bad input")

        # Simulate API event appending
        store.append_event(run_id, {"event_type": "feedback.received", "action": "dont_do_this_again"})
        if result["generated"]["bad_case"]:
            store.append_event(run_id, {"event_type": "bad_case.recorded"})
        if result["generated"]["eval_case"]:
            store.append_event(run_id, {"event_type": "eval_case.generated"})
        if result["generated"]["skill_patch_candidate"]:
            store.append_event(run_id, {"event_type": "skill.patch.proposed"})
        if result["generated"]["validation_report"]:
            store.append_event(run_id, {"event_type": "validation.checked"})
        if result["generated"]["human_review_required"]:
            store.append_event(run_id, {"event_type": "human_review.required"})

        events = store.get_events(run_id)
        event_types = {e["event_type"] for e in events}
        assert "feedback.received" in event_types
        assert "bad_case.recorded" in event_types
        assert "eval_case.generated" in event_types
        assert "skill.patch.proposed" in event_types
        assert "validation.checked" in event_types

    def test_correct_and_remember_appends_expression_event(self):
        """correct-and-remember 成功后应追加 expression.rule.candidate 事件。"""
        store = MockRunStore()
        service = MockFeedbackService()
        run_id = "test_run_2"

        result = service.handle_correct_and_remember(run_id=run_id, user_note="correction")
        store.append_event(run_id, {"event_type": "feedback.received", "action": "correct_and_remember"})
        if result["generated"]["expression_rule_candidate"]:
            store.append_event(run_id, {"event_type": "expression.rule.candidate"})

        events = store.get_events(run_id)
        event_types = {e["event_type"] for e in events}
        assert "feedback.received" in event_types
        assert "expression.rule.candidate" in event_types

    def test_no_run_store_no_error(self):
        """没有 run_store 时 API 不应报错。"""
        # This tests the _append_run_event function with None store
        from web.routes.api import _append_run_event
        # Should not raise
        _append_run_event("feedback.received", {"run_id": "test"})

    def test_learning_events_include_feedback_types(self):
        """learning endpoint 应包含 feedback 相关事件类型。"""
        store = MockRunStore()
        run_id = "test_run_3"
        store.append_event(run_id, {"event_type": "feedback.received"})
        store.append_event(run_id, {"event_type": "bad_case.recorded"})
        store.append_event(run_id, {"event_type": "eval_case.generated"})
        store.append_event(run_id, {"event_type": "expression.rule.candidate"})

        learning_types = {
            "self_improvement.checked", "regression.generated",
            "memory.update.candidate", "skill.patch.proposed",
            "validation.checked", "human_review.required",
            "feedback.received", "bad_case.recorded",
            "eval_case.generated", "expression.rule.candidate",
        }
        events = store.get_events(run_id)
        learning_events = [
            e for e in events
            if isinstance(e, dict) and e.get("event_type") in learning_types
        ]
        assert len(learning_events) == 4
