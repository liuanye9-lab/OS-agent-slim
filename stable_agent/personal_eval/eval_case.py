"""personal_eval.eval_case — 评估用例管理器。

V11 新增：管理 PersonalEvalCase 的创建、查询和持久化。
持久化到 JSONL 文件 (capsule/evals/personal_eval_cases.jsonl)。
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

from stable_agent.personal_eval.schemas import PersonalEvalCase

logger = logging.getLogger(__name__)

# 默认持久化路径
_DEFAULT_STORAGE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "capsule", "evals", "personal_eval_cases.jsonl",
)


class EvalCaseManager:
    """评估用例管理器。

    管理 PersonalEvalCase 的生命周期：创建、查询、列表。
    数据持久化到 JSONL 文件。

    Attributes:
        storage_path: JSONL 持久化文件路径。
        _cases: 内存中的用例字典。
    """

    def __init__(self, storage_path: str | None = None) -> None:
        """初始化评估用例管理器。

        Args:
            storage_path: JSONL 文件路径，默认 capsule/evals/personal_eval_cases.jsonl。
        """
        self.storage_path: str = storage_path or _DEFAULT_STORAGE_PATH
        self._cases: dict[str, PersonalEvalCase] = {}
        self._load_from_disk()

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    def create_case(
        self,
        task: str,
        task_type: str = "general",
        must_keep: list[str] | None = None,
        must_avoid: list[str] | None = None,
        success_criteria: str = "",
        failure_modes: list[str] | None = None,
        source_bad_case_id: str = "",
    ) -> PersonalEvalCase:
        """创建一个评估用例并持久化。

        Args:
            task: 任务描述文本。
            task_type: 任务类型标签。
            must_keep: 必须保留的关键词列表。
            must_avoid: 必须避免的关键词/模式列表。
            success_criteria: 成功标准描述。
            failure_modes: 失败模式列表。
            source_bad_case_id: 来源 bad case ID。

        Returns:
            创建的 PersonalEvalCase 实例。
        """
        case = PersonalEvalCase(
            task=task,
            task_type=task_type,
            must_keep=must_keep or [],
            must_avoid=must_avoid or [],
            success_criteria=success_criteria,
            failure_modes=failure_modes or [],
            source_bad_case_id=source_bad_case_id,
        )
        self._cases[case.case_id] = case
        self._append_to_disk(case)
        logger.info("Created eval case %s (task_type=%s)", case.case_id, task_type)
        return case

    def list_cases(self, task_type: str | None = None) -> list[PersonalEvalCase]:
        """列出评估用例。

        Args:
            task_type: 按任务类型过滤，None 返回全部。

        Returns:
            满足条件的 PersonalEvalCase 列表。
        """
        cases = list(self._cases.values())
        if task_type is not None:
            cases = [c for c in cases if c.task_type == task_type]
        return cases

    def get_case(self, case_id: str) -> Optional[PersonalEvalCase]:
        """获取指定 ID 的评估用例。

        Args:
            case_id: 用例 ID。

        Returns:
            PersonalEvalCase 实例，不存在时返回 None。
        """
        return self._cases.get(case_id)

    # ------------------------------------------------------------------
    # 持久化
    # ------------------------------------------------------------------

    def _load_from_disk(self) -> None:
        """从 JSONL 文件加载用例。"""
        if not os.path.exists(self.storage_path):
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        case = PersonalEvalCase.from_dict(data)
                        self._cases[case.case_id] = case
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.warning("Skip malformed eval case line: %s", e)
            logger.info("Loaded %d eval cases from %s", len(self._cases), self.storage_path)
        except Exception as e:
            logger.warning("Failed to load eval cases: %s", e)

    def _append_to_disk(self, case: PersonalEvalCase) -> None:
        """将单条用例追加到 JSONL 文件。"""
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            with open(self.storage_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(case.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning("Failed to persist eval case %s: %s", case.case_id, e)
