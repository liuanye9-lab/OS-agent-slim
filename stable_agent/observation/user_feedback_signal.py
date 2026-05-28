"""UserFeedbackSignal — 用户反馈信号数据模型。

定义用户对 Agent 执行结果的反馈类型和标签，
用于驱动 SkillOpt 技能学习管道的反馈环。

用法::

    from stable_agent.observation.user_feedback_signal import (
        UserFeedbackSignal, FEEDBACK_TYPES, FEEDBACK_LABELS,
    )
    fb = UserFeedbackSignal(
        feedback_id="fb-001",
        run_id="run-001",
        signal_type="aligned",
        comment="做得不错",
    )
    print(fb.to_dict())
"""

from __future__ import annotations
from dataclasses import dataclass, field
import time

#: 支持的反馈类型列表。
FEEDBACK_TYPES: list[str] = [
    "aligned",
    "partial",
    "off_track",
    "too_technical",
    "too_generic",
    "not_specific",
    "no_executable_plan",
]

#: 反馈类型的中英文标签映射。
FEEDBACK_LABELS: dict[str, dict[str, str]] = {
    "aligned": {"zh": "符合我的意图", "en": "Aligned with intent"},
    "partial": {"zh": "部分符合", "en": "Partially aligned"},
    "off_track": {"zh": "跑偏了", "en": "Off track"},
    "too_technical": {"zh": "太技术化", "en": "Too technical"},
    "too_generic": {"zh": "太空泛", "en": "Too generic"},
    "not_specific": {"zh": "不够具体", "en": "Not specific enough"},
    "no_executable_plan": {"zh": "没有给我可执行方案", "en": "No executable plan"},
}


@dataclass
class UserFeedbackSignal:
    """用户反馈信号数据模型。

    表示用户对一次 Agent 运行的反馈。包含反馈类型、
    可选评论和时间戳。processed 标记用于追踪该反馈
    是否已被 SkillOpt 管道处理。

    Attributes:
        feedback_id: 反馈唯一标识。
        run_id: 关联的运行标识。
        signal_type: 反馈类型，必须是 FEEDBACK_TYPES 之一。
        label_zh: 中文标签（自动从 signal_type 推导）。
        label_en: 英文标签（自动从 signal_type 推导）。
        comment: 用户可选评论。
        timestamp: 反馈时间戳（Unix 秒）。
        processed: 是否已被 SkillOpt 处理。
    """

    feedback_id: str = ""
    run_id: str = ""
    signal_type: str = ""  # one of FEEDBACK_TYPES
    label_zh: str = ""
    label_en: str = ""
    comment: str = ""
    timestamp: float = field(default_factory=time.time)
    processed: bool = False

    def __post_init__(self) -> None:
        """自动从 signal_type 推导 label_zh / label_en。"""
        if self.signal_type and self.signal_type in FEEDBACK_LABELS:
            labels = FEEDBACK_LABELS[self.signal_type]
            if not self.label_zh:
                self.label_zh = labels["zh"]
            if not self.label_en:
                self.label_en = labels["en"]

    def to_dict(self) -> dict:
        """将反馈信号序列化为字典。

        Returns:
            包含所有字段的字典，适合 JSON 序列化。
        """
        return {
            "feedback_id": self.feedback_id,
            "run_id": self.run_id,
            "signal_type": self.signal_type,
            "label_zh": self.label_zh,
            "label_en": self.label_en,
            "comment": self.comment,
            "timestamp": self.timestamp,
            "processed": self.processed,
        }
