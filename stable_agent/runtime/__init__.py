"""Runtime package — 统一运行时抽象。"""

from stable_agent.runtime.run_lifecycle import (
    RunStage,
    RunStageMeta,
    RUN_STAGE_META,
    get_stage_meta,
    STAGE_PROGRESS,
    STAGE_LABEL_ZH,
    STAGE_AVATAR,
)

__all__ = [
    "RunStage", "RunStageMeta", "RUN_STAGE_META",
    "get_stage_meta", "STAGE_PROGRESS", "STAGE_LABEL_ZH", "STAGE_AVATAR",
]
