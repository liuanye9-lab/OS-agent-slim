"""测试 RunLifecycle 统一状态源 (Phase 3)。"""

from stable_agent.runtime.run_lifecycle import (
    RunStage, RunStageMeta, get_stage_meta,
    RUN_STAGE_META, STAGE_PROGRESS, STAGE_LABEL_ZH, STAGE_AVATAR,
)


class TestRunStage:
    def test_all_20_stages_defined(self):
        """验证 20 个标准阶段。"""
        assert len(RunStage) == 20
        assert RunStage.CREATED == "created"
        assert RunStage.COMPLETED == "completed"
        assert RunStage.FAILED == "failed"
        assert RunStage.CANCELLED == "cancelled"

    def test_stage_meta_includes_all_fields(self):
        """每个阶段都有完整的元信息。"""
        meta = get_stage_meta(RunStage.PLANNING)
        assert meta.stage == RunStage.PLANNING
        assert meta.progress_pct == 60
        assert meta.status_text_zh == "规划步骤"
        assert meta.status_text_en == "Planning"
        assert meta.avatar_state == "planning"
        assert meta.default_why_zh
        assert meta.default_next_step_zh

    def test_get_stage_meta_by_string(self):
        """字符串参数同样工作。"""
        meta = get_stage_meta("acting")
        assert meta.stage == RunStage.ACTING
        assert meta.progress_pct == 70

    def test_unknown_stage_fallback_to_created(self):
        """未知阶段 fallback 到 CREATED。"""
        meta = get_stage_meta("nonexistent_stage")
        assert meta.stage == RunStage.CREATED
        assert meta.progress_pct == 0

    def test_progress_pct_ranges(self):
        """进度从 0 到 100。"""
        assert STAGE_PROGRESS["created"] == 0
        assert STAGE_PROGRESS["completed"] == 100
        assert STAGE_PROGRESS["failed"] == -1

    def test_backward_compat_dicts(self):
        """向后兼容字典存在且非空。"""
        assert len(STAGE_PROGRESS) == 20
        assert len(STAGE_LABEL_ZH) == 20
        assert len(STAGE_AVATAR) == 20

    def test_each_stage_has_meta(self):
        """每个 RunStage 都有对应的 RunStageMeta。"""
        for stage in RunStage:
            assert stage in RUN_STAGE_META
            meta = RUN_STAGE_META[stage]
            assert isinstance(meta, RunStageMeta)
            assert isinstance(meta.progress_pct, int)
