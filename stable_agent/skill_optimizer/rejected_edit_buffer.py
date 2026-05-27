"""被拒绝编辑缓冲区。

保存被 Validation Gate 拒绝的编辑，为后续轮次提供负反馈。
持久化到 skills/rejected_edits.jsonl 文件，支持相似度检测和去重。
"""

from __future__ import annotations

import difflib
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from stable_agent.skill_optimizer.models import SkillEdit

if TYPE_CHECKING:
    from stable_agent.skill_optimizer.models import ValidationResult

logger = logging.getLogger(__name__)


class RejectedEditBuffer:
    """被拒绝编辑的缓冲区。

    保存被 Validation Gate 拒绝的编辑，为后续轮次提供负反馈。
    持久化到 skills/rejected_edits.jsonl 文件。

    JSONL 存储格式（每行一个 JSON）：
    {"id": "...", "op": "...", "target": "...", "content": "...",
     "reason": "...", "source_type": "...", "support_count": 0,
     "risk_level": "...", "created_at": "..."}

    Attributes:
        buffer_path: JSONL 文件路径。
    """

    def __init__(self, buffer_path: str = "skills/rejected_edits.jsonl") -> None:
        """初始化缓冲区路径，自动创建目录。

        Args:
            buffer_path: JSONL 持久化文件的路径。
        """
        self.buffer_path = Path(buffer_path).resolve()
        self.buffer_path.parent.mkdir(parents=True, exist_ok=True)

    def add_rejected(
        self,
        edits: list[SkillEdit],
        validation_result: ValidationResult,
    ) -> None:
        """批量添加被拒绝的编辑，持久化写入 JSONL。

        每条编辑附带 validation_result.explanation 作为 rejection_reason。

        Args:
            edits: 被拒绝的 SkillEdit 列表。
            validation_result: 导致拒绝的验证结果。
        """
        if not edits:
            return

        lines: list[str] = []
        for edit in edits:
            record = {
                "id": edit.id,
                "op": edit.op,
                "target": edit.target,
                "content": edit.content,
                "reason": validation_result.explanation or edit.reason,
                "source_type": edit.source_type,
                "support_count": edit.support_count,
                "risk_level": edit.risk_level,
                "created_at": edit.created_at.isoformat(),
            }
            lines.append(json.dumps(record, ensure_ascii=False))

        with open(self.buffer_path, "a", encoding="utf-8") as f:
            for line in lines:
                f.write(line + "\n")

        logger.info(
            "已将 %d 条被拒绝编辑写入缓冲区: %s", len(edits), self.buffer_path
        )

    def load_recent(self, limit: int = 50) -> list[SkillEdit]:
        """加载最近拒绝的编辑。

        从 JSONL 文件按行读取，返回最近 limit 条（按文件顺序取最后 limit 条）。

        Args:
            limit: 最大返回条数。

        Returns:
            最近被拒绝的 SkillEdit 列表。
        """
        if not self.buffer_path.exists():
            return []

        all_records: list[dict] = []
        with open(self.buffer_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    all_records.append(record)
                except json.JSONDecodeError:
                    logger.warning("跳过无效 JSONL 行: %s...", line[:80])
                    continue

        # 返回最后 limit 条
        recent = all_records[-limit:] if len(all_records) > limit else all_records

        edits: list[SkillEdit] = []
        for rec in recent:
            try:
                created_at = (
                    datetime.fromisoformat(rec["created_at"])
                    if rec.get("created_at")
                    else datetime.now()
                )
            except (ValueError, TypeError):
                created_at = datetime.now()

            edits.append(
                SkillEdit(
                    id=rec.get("id", str(uuid.uuid4())),
                    op=rec["op"],
                    target=rec.get("target"),
                    content=rec.get("content"),
                    reason=rec.get("reason", ""),
                    source_type=rec.get("source_type", "failure"),
                    support_count=rec.get("support_count", 0),
                    risk_level=rec.get("risk_level", "medium"),
                    created_at=created_at,
                )
            )

        return edits

    def is_similar_to_rejected(self, edit: SkillEdit) -> bool:
        """检查编辑是否与已拒绝编辑相似。

        相似度算法：
        - op 相同 + target 相同 → True（完全相同）
        - op 为 append 时：比较 content 前 60 字符的相似度
          （difflib.SequenceMatcher.ratio() > 0.7）

        Args:
            edit: 要检查的 SkillEdit。

        Returns:
            True 如果与缓冲区中任何已拒绝编辑相似。
        """
        rejected = self.load_recent(limit=200)
        if not rejected:
            return False

        for rej in rejected:
            # 相同 op + 相同 target → 完全匹配
            if edit.op == rej.op and edit.target == rej.target:
                # 对于 append（target 为 None），比较 content 相似度
                if edit.target is None:
                    return self._content_similarity(
                        edit.content or "", rej.content or "", threshold=0.7
                    )
                return True

            # append 操作：content 相似度 > 0.7
            if edit.op == "append" and rej.op == "append":
                if self._content_similarity(
                    edit.content or "", rej.content or "", threshold=0.7
                ):
                    return True

        return False

    def clear(self) -> None:
        """清空缓冲区（删除 JSONL 文件）。"""
        if self.buffer_path.exists():
            self.buffer_path.unlink()
            logger.info("已清空 rejected edits 缓冲区: %s", self.buffer_path)

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    @staticmethod
    def _content_similarity(a: str, b: str, threshold: float = 0.7) -> bool:
        """计算两个 content 的前 60 字符相似度。

        Args:
            a: 第一个字符串。
            b: 第二个字符串。
            threshold: 相似度阈值，默认 0.7。

        Returns:
            True 如果相似度 >= threshold。
        """
        if not a and not b:
            return True
        if not a or not b:
            return False

        a_prefix = a[:60]
        b_prefix = b[:60]
        ratio = difflib.SequenceMatcher(None, a_prefix, b_prefix).ratio()
        return ratio > threshold
