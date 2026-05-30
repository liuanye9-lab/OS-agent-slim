"""Run Lifecycle — 向后兼容 Re-export。
# @deprecated V6.0: 主模块在 stable_agent.runtime.run_lifecycle，
#   新代码请直接导入 runtime/。此 re-export 计划在 V7.0 移除。

Production Hardening: 主模块已迁移至 stable_agent.runtime.run_lifecycle。
此文件保留向后兼容，所有导入自动转发到新位置。
"""

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
