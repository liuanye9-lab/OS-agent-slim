"""StableAgent OS 评估数据集管理模块。

提供 EvalCase 的 JSONL 文件读写和回归用例管理功能。
支持从 BadCase 自动生成回归测试用例，确保之前出现的问题不会再次发生。

约定：
- 数据集文件格式为 JSONL（每行一个 JSON 对象）
- 自动创建 data/ 目录
- 文件不存在时优雅处理（返回空列表而不报错）
- JSON 序列化使用 ensure_ascii=False 保留中文
"""

from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path
from typing import Optional

from stable_agent.models import BadCase, EvalCase, TaskType


class EvalDatasetManager:
    """评估数据集管理器。

    管理 JSONL 格式的评估用例数据集，支持读写、筛选和从 BadCase 自动生成
    回归测试用例。

    Attributes:
        dataset_path: JSONL 数据集文件路径。
    """

    def __init__(self, dataset_path: str = "data/eval_dataset.jsonl") -> None:
        """初始化数据集管理器，自动创建 data/ 目录。

        Args:
            dataset_path: JSONL 数据集文件路径，默认 data/eval_dataset.jsonl。
        """
        self.dataset_path: str = dataset_path

        # 确保 data/ 目录存在
        data_dir = Path(dataset_path).parent
        data_dir.mkdir(parents=True, exist_ok=True)

    def load_cases(self) -> list[EvalCase]:
        """从 JSONL 加载所有评测用例。

        文件不存在或读取失败时返回空列表，不抛出异常。

        Returns:
            EvalCase 列表，按文件中的顺序排列。

        Raises:
            无——所有异常在内部静默处理。
        """
        cases: list[EvalCase] = []

        if not os.path.exists(self.dataset_path):
            return cases

        try:
            with open(self.dataset_path, "r", encoding="utf-8") as f:
                for line_no, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        raw = json.loads(line)
                        case = self._dict_to_eval_case(raw)
                        cases.append(case)
                    except (json.JSONDecodeError, KeyError, TypeError):
                        # 跳过格式错误的行
                        continue
        except (IOError, OSError):
            return []

        return cases

    def append_case(self, case: EvalCase) -> None:
        """追加一个评测用例到 JSONL 文件。

        用例序列化为单行 JSON 并追加到文件末尾。

        Args:
            case: EvalCase 实例。
        """
        try:
            with open(self.dataset_path, "a", encoding="utf-8") as f:
                line = json.dumps(
                    self._eval_case_to_dict(case),
                    ensure_ascii=False,
                )
                f.write(line + "\n")
        except (IOError, OSError):
            pass  # 写入失败时静默处理

    def append_cases(self, cases: list[EvalCase]) -> None:
        """批量追加评测用例到 JSONL 文件。

        Args:
            cases: EvalCase 列表。
        """
        for case in cases:
            self.append_case(case)

    def find_by_task_type(self, task_type: TaskType) -> list[EvalCase]:
        """按任务类型筛选评测用例。

        Args:
            task_type: 任务类型枚举值。

        Returns:
            匹配的 EvalCase 列表。
        """
        return [
            case for case in self.load_cases() if case.task_type == task_type
        ]

    def find_by_source(self, source: str) -> list[EvalCase]:
        """按来源筛选评测用例。

        Args:
            source: 来源标识字符串（如 "manual"、"auto_from_bad_case"）。

        Returns:
            匹配的 EvalCase 列表。
        """
        return [
            case for case in self.load_cases() if case.source == source
        ]

    def create_from_bad_case(
        self,
        bad_case: BadCase,
        expected_behavior: str = "",
    ) -> EvalCase:
        """从 BadCase 生成回归评测用例。

        将失败案例转换为评估用例，以便在后续回归测试中防止相同问题再次出现。

        生成规则：
        - case_id = "eval-" + bad_case.timestamp 的十六进制字符串。
        - input_task = bad_case.input_context。
        - source = "auto_from_bad_case"。
        - created_from_bad_case_id = bad_case.timestamp 转为字符串。
        - must_not_include = 从 bad_case.failure_reason 中提取的错误模式。

        Args:
            bad_case: 负面案例实例。
            expected_behavior: 期望的正确行为描述，默认为空。

        Returns:
            生成的 EvalCase 实例。

        Examples:
            >>> from stable_agent.models import BadCase, EvaluationResult, TaskType
            >>> eval_result = EvaluationResult(overall_score=0.3)
            >>> bc = BadCase(
            ...     task_type=TaskType.BUG_FIX,
            ...     input_context="修复登录页面样式错乱",
            ...     output="已修复",
            ...     evaluation=eval_result,
            ...     failure_reason="输出缺少具体代码修改",
            ... )
            >>> mgr = EvalDatasetManager("data/test_eval.jsonl")
            >>> case = mgr.create_from_bad_case(bc)
            >>> case.source
            'auto_from_bad_case'
        """
        # case_id 基于 timestamp 生成（转为整数后取十六进制）
        case_id = f"eval-{int(bad_case.timestamp):016x}"

        # 从 failure_reason 提取错误模式作为 must_not_include
        must_not_include: list[str] = []
        if bad_case.failure_reason:
            # 提取关键词作为禁止模式
            keywords = self._extract_error_patterns(bad_case.failure_reason)
            must_not_include.extend(keywords)

        # 如果 output 中有明显问题，也加入
        if bad_case.output and len(bad_case.output) < 20:
            # 过短的输出通常是无效的
            must_not_include.append("输出过短")

        eval_case = EvalCase(
            case_id=case_id,
            input_task=bad_case.input_context,
            expected_behavior=expected_behavior,
            must_include=[],
            must_not_include=must_not_include,
            source="auto_from_bad_case",
            created_from_bad_case_id=str(bad_case.timestamp),
            task_type=bad_case.task_type,
        )

        return eval_case

    def count_by_source(self) -> dict[str, int]:
        """统计各来源的用例数量。

        Returns:
            字典，key 为来源标识，value 为数量。

        Examples:
            >>> mgr = EvalDatasetManager("data/test_count.jsonl")
            >>> counts = mgr.count_by_source()
            >>> isinstance(counts, dict)
            True
        """
        cases = self.load_cases()
        counter = Counter(case.source for case in cases)
        return dict(counter)

    # ------------------------------------------------------------------
    # 内部辅助方法
    # ------------------------------------------------------------------

    @staticmethod
    def _eval_case_to_dict(case: EvalCase) -> dict:
        """将 EvalCase 转换为可 JSON 序列化的字典。

        Args:
            case: EvalCase 实例。

        Returns:
            标准字典。
        """
        return {
            "case_id": case.case_id,
            "input_task": case.input_task,
            "expected_behavior": case.expected_behavior,
            "must_include": case.must_include,
            "must_not_include": case.must_not_include,
            "source": case.source,
            "created_from_bad_case_id": case.created_from_bad_case_id,
            "task_type": case.task_type.value,
        }

    @staticmethod
    def _dict_to_eval_case(raw: dict) -> EvalCase:
        """将字典转换为 EvalCase 实例。

        Args:
            raw: 原始字典。

        Returns:
            EvalCase 实例。

        Raises:
            KeyError: 缺少必要字段 case_id 或 input_task。
        """
        return EvalCase(
            case_id=raw["case_id"],
            input_task=raw["input_task"],
            expected_behavior=raw.get("expected_behavior", ""),
            must_include=raw.get("must_include", []),
            must_not_include=raw.get("must_not_include", []),
            source=raw.get("source", "manual"),
            created_from_bad_case_id=raw.get("created_from_bad_case_id"),
            task_type=TaskType(raw.get("task_type", "general_qa")),
        )

    @staticmethod
    def _extract_error_patterns(failure_reason: str) -> list[str]:
        """从失败原因文本中提取错误模式关键词。

        识别常见的失败模式并返回便于匹配的关键词列表。

        Args:
            failure_reason: 失败原因文本。

        Returns:
            错误模式关键词列表。
        """
        patterns: list[str] = []

        failure_lower = failure_reason.lower()

        # 常见错误模式映射
        error_patterns = {
            "缺少": "缺少",
            "缺失": "缺失",
            "遗漏": "遗漏",
            "错误": "错误",
            "不正确": "不正确",
            "无效": "无效",
            "崩溃": "崩溃",
            "超时": "超时",
            "幻觉": "幻觉",
            "token": "token",
            "溢出": "溢出",
            "过短": "过短",
            "不完整": "不完整",
            "权限": "权限",
            "格式": "格式错误",
            "编码": "编码问题",
            "中文": "中文乱码",
        }

        for key, pattern in error_patterns.items():
            if key in failure_lower:
                patterns.append(pattern)

        # 如果没有匹配到任何模式，使用原始文本的前 50 字符作为模式
        if not patterns and failure_reason.strip():
            truncated = failure_reason.strip()[:50]
            if len(failure_reason.strip()) > 50:
                truncated += "..."
            patterns.append(truncated)

        return patterns
