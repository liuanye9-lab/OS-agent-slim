"""纠正记录存储。

记录用户对系统理解的纠正，支持转化为 ExpressionProfile。
持久化到 JSONL 文件。

用法::

    store = CorrectionStore("/path/to/corrections.jsonl")
    record = CorrectionRecord(run_id="run_001", wrong_interpretation="...", ...)
    store.add_correction(record)
    profile = store.convert_to_expression_rule(record.correction_id)
"""

from __future__ import annotations

import json
import os
from typing import Optional

from stable_agent.understanding.schemas import (
    CorrectionRecord,
    ExpressionProfile,
    ExpressionScope,
)


class CorrectionStore:
    """纠正记录存储。

    管理纠正记录，支持持久化到 JSONL 文件和转化为表达规则。

    Attributes:
        _storage_path: 持久化文件路径。
        _records: 纠正记录列表。
    """

    def __init__(self, storage_path: str = "") -> None:
        """初始化纠正记录存储。

        Args:
            storage_path: 持久化 JSONL 文件路径。为空则仅内存存储。
        """
        self._storage_path = storage_path
        self._records: list[CorrectionRecord] = []
        self._load()

    def add_correction(self, correction: CorrectionRecord) -> CorrectionRecord:
        """添加纠正记录。

        Args:
            correction: 纠正记录。

        Returns:
            存储的 CorrectionRecord。
        """
        self._records.append(correction)
        self._save()
        return correction

    def get_corrections(self, run_id: str | None = None) -> list[CorrectionRecord]:
        """获取纠正记录。

        Args:
            run_id: 按 run_id 过滤 (可选)。

        Returns:
            匹配的 CorrectionRecord 列表。
        """
        if run_id is None:
            return list(self._records)
        return [r for r in self._records if r.run_id == run_id]

    def convert_to_expression_rule(self, correction_id: str) -> Optional[ExpressionProfile]:
        """将纠正记录转化为表达规则。

        Args:
            correction_id: 纠正记录 ID。

        Returns:
            生成的 ExpressionProfile，如果未找到则返回 None。
        """
        for record in self._records:
            if record.correction_id == correction_id:
                if record.converted_to_expression_rule:
                    return None  # 已转化

                profile = ExpressionProfile(
                    phrase=record.trigger_phrase,
                    normalized_meaning=[record.correct_interpretation],
                    scope=ExpressionScope.GLOBAL,
                    confirmed_by_user=True,
                    confidence=0.9,
                    examples=[
                        f"错误理解: {record.wrong_interpretation}",
                        f"正确理解: {record.correct_interpretation}",
                    ],
                )
                record.converted_to_expression_rule = True
                self._save()
                return profile

        return None

    def _load(self) -> None:
        """从 JSONL 文件加载。"""
        if not self._storage_path or not os.path.exists(self._storage_path):
            return

        try:
            with open(self._storage_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    self._records.append(CorrectionRecord(
                        correction_id=data.get("correction_id", ""),
                        run_id=data.get("run_id", ""),
                        wrong_interpretation=data.get("wrong_interpretation", ""),
                        correct_interpretation=data.get("correct_interpretation", ""),
                        trigger_phrase=data.get("trigger_phrase", ""),
                        created_at=data.get("created_at", 0),
                        converted_to_expression_rule=data.get("converted_to_expression_rule", False),
                    ))
        except (json.JSONDecodeError, OSError):
            self._records = []

    def _save(self) -> None:
        """保存到 JSONL 文件。"""
        if not self._storage_path:
            return

        os.makedirs(os.path.dirname(self._storage_path) or ".", exist_ok=True)
        with open(self._storage_path, "w", encoding="utf-8") as f:
            for record in self._records:
                f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
