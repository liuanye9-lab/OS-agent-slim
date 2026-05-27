"""验证数据集管理器。

管理验证用例的 JSONL 存储，提供加载、追加和内置默认用例。
每条用例包含任务输入、期望意图、评分准则和约束条件。
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class ValidationDataset:
    """验证数据集管理器。

    管理验证用例的 JSONL 存储。每条用例格式：
    {"id": "case_001", "task_input": "...", "expected_intent": "...",
     "rubric": {"intent_alignment": 0.3, ...}, "must_include": [...],
     "must_not_include": [...]}

    Attributes:
        dataset_path: JSONL 文件路径。
    """

    def __init__(
        self, dataset_path: str = "data/validation/user_intent_cases.jsonl"
    ) -> None:
        """初始化，自动创建目录。

        如果文件不存在，创建内置 10 条默认用例。

        Args:
            dataset_path: JSONL 文件的存储路径。
        """
        self.dataset_path: str = dataset_path
        # 确保目录存在
        parent_dir: str = os.path.dirname(self.dataset_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)

        # 如果文件不存在，写入内置用例
        if not os.path.exists(self.dataset_path):
            self._write_builtin_cases()

    # ------------------------------------------------------------------
    # 加载
    # ------------------------------------------------------------------

    def load_cases(self) -> list[dict]:
        """加载所有验证用例。

        损坏行（JSON 解析失败）会跳过并记录 warning。

        Returns:
            验证用例字典列表。
        """
        cases: list[dict] = []
        if not os.path.exists(self.dataset_path):
            return cases

        try:
            with open(self.dataset_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        case = json.loads(line)
                        cases.append(case)
                    except json.JSONDecodeError:
                        logger.warning(
                            "跳过损坏行 %d: %s...", line_num, line[:80]
                        )
                        continue
        except Exception as e:
            logger.error("加载验证数据集失败: %s", e)
            return []

        return cases

    # ------------------------------------------------------------------
    # 追加
    # ------------------------------------------------------------------

    def append_case(self, case: dict) -> None:
        """追加一条用例到 JSONL 文件。

        Args:
            case: 用例字典，应包含 id、task_input 等字段。
        """
        with open(self.dataset_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(case, ensure_ascii=False) + "\n")
        logger.info("已追加验证用例: %s", case.get("id", "unknown"))

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------

    def count(self) -> int:
        """返回用例总数。

        Returns:
            JSONL 文件中的有效行数。
        """
        return len(self.load_cases())

    # ------------------------------------------------------------------
    # 内置用例
    # ------------------------------------------------------------------

    def get_builtin_cases(self) -> list[dict]:
        """返回内置的 10 条基础用例。

        覆盖以下场景：
        1. Codex 生产提示词请求（期望：结构化、模块化、可执行）
        2. 概念解释请求（期望：第一性原理、类比、由浅入深）
        3. Bug 诊断请求（期望：症状→原因→修复）
        4. UI 优化请求（期望：具体 CSS 建议而非泛泛建议）
        5. 架构重构请求（期望：系统化方案）
        6. 学习请求（期望：简单解释先于深入）
        7. MCP 接入请求（期望：可执行的接入步骤）
        8. 快速问答（期望：简洁直接）
        9. 项目开发请求（期望：分窗口开发建议）
        10. 评估审查请求（期望：结构化评分维度）

        Returns:
            内置验证用例列表。
        """
        return [
            {
                "id": "case_001",
                "task_input": (
                    "请给我写一个 Codex 的生产提示词，用于生成高质量的 Python "
                    "后端代码，要求支持异步处理、错误重试和日志记录。"
                ),
                "expected_intent": "生成结构化、模块化、可执行的代码提示词",
                "rubric": {
                    "intent_understanding": 0.25,
                    "actionability": 0.30,
                    "user_preference_match": 0.15,
                    "information_density": 0.15,
                    "drift_risk": 0.10,
                    "token_efficiency": 0.05,
                },
                "must_include": [
                    "模块化", "可执行", "代码",
                ],
                "must_not_include": [
                    "这是AI生成的", "作为一个AI",
                ],
            },
            {
                "id": "case_002",
                "task_input": (
                    "请解释一下什么是 Transformer 架构中的自注意力机制，"
                    "我刚开始学习深度学习。"
                ),
                "expected_intent": "第一性原理、类比、由浅入深的概念解释",
                "rubric": {
                    "intent_understanding": 0.30,
                    "actionability": 0.10,
                    "user_preference_match": 0.25,
                    "information_density": 0.20,
                    "drift_risk": 0.10,
                    "token_efficiency": 0.05,
                },
                "must_include": [
                    "类比", "简单", "注意力",
                ],
                "must_not_include": [
                    "公式推导过于复杂", "论文引用",
                ],
            },
            {
                "id": "case_003",
                "task_input": (
                    "我的 Python Flask 应用在高并发下偶尔返回 500 错误，"
                    "日志里没有明显异常，请帮我诊断可能的原因。"
                ),
                "expected_intent": "症状 → 原因 → 修复的诊断流程",
                "rubric": {
                    "intent_understanding": 0.25,
                    "actionability": 0.25,
                    "user_preference_match": 0.15,
                    "information_density": 0.15,
                    "drift_risk": 0.10,
                    "token_efficiency": 0.10,
                },
                "must_include": [
                    "可能原因", "修复", "诊断",
                ],
                "must_not_include": [
                    "这是AI生成的",
                ],
            },
            {
                "id": "case_004",
                "task_input": (
                    "我的网站首页按钮颜色和整体风格不协调，"
                    "怎么调整让它们看起来更专业？"
                ),
                "expected_intent": "具体 CSS/设计建议，非泛泛而谈",
                "rubric": {
                    "intent_understanding": 0.20,
                    "actionability": 0.30,
                    "user_preference_match": 0.20,
                    "information_density": 0.15,
                    "drift_risk": 0.10,
                    "token_efficiency": 0.05,
                },
                "must_include": [
                    "CSS", "颜色", "建议",
                ],
                "must_not_include": [
                    "这是主观的", "没有标准答案",
                ],
            },
            {
                "id": "case_005",
                "task_input": (
                    "我们的单体应用正在拆分为微服务，"
                    "请给出一个系统化的架构重构方案，包括服务划分、"
                    "通信协议、数据一致性策略。"
                ),
                "expected_intent": "系统化架构重构方案，包含具体策略",
                "rubric": {
                    "intent_understanding": 0.25,
                    "actionability": 0.25,
                    "user_preference_match": 0.15,
                    "information_density": 0.20,
                    "drift_risk": 0.10,
                    "token_efficiency": 0.05,
                },
                "must_include": [
                    "服务划分", "通信", "数据一致性",
                ],
                "must_not_include": [
                    "这是AI建议",
                ],
            },
            {
                "id": "case_006",
                "task_input": (
                    "我想学习 Rust 编程语言，但之前只写过 Python，"
                    "请帮我入门，从基础讲起。"
                ),
                "expected_intent": "简单解释先于深入，对比 Python 教学",
                "rubric": {
                    "intent_understanding": 0.30,
                    "actionability": 0.15,
                    "user_preference_match": 0.25,
                    "information_density": 0.15,
                    "drift_risk": 0.10,
                    "token_efficiency": 0.05,
                },
                "must_include": [
                    "入门", "Python", "基础",
                ],
                "must_not_include": [
                    "高级特性", "底层实现",
                ],
            },
            {
                "id": "case_007",
                "task_input": (
                    "我想接入 MCP 协议让我的 AI 应用能调用外部工具，"
                    "请给出具体的接入步骤和代码示例。"
                ),
                "expected_intent": "可执行的 MCP 接入步骤和代码",
                "rubric": {
                    "intent_understanding": 0.20,
                    "actionability": 0.35,
                    "user_preference_match": 0.15,
                    "information_density": 0.15,
                    "drift_risk": 0.10,
                    "token_efficiency": 0.05,
                },
                "must_include": [
                    "步骤", "代码", "MCP",
                ],
                "must_not_include": [
                    "这是AI",
                ],
            },
            {
                "id": "case_008",
                "task_input": (
                    "Python 的 list 和 tuple 有什么区别？"
                ),
                "expected_intent": "简洁直接回答，无需长篇大论",
                "rubric": {
                    "intent_understanding": 0.20,
                    "actionability": 0.10,
                    "user_preference_match": 0.25,
                    "information_density": 0.25,
                    "drift_risk": 0.10,
                    "token_efficiency": 0.10,
                },
                "must_include": [
                    "list", "tuple", "区别",
                ],
                "must_not_include": [
                    "长篇", "深入讲解",
                ],
            },
            {
                "id": "case_009",
                "task_input": (
                    "我要开发一个实时协作编辑器，类似 Google Docs，"
                    "前后端都用 TypeScript，请给出开发建议和架构设计。"
                ),
                "expected_intent": "分阶段开发建议，前后端架构",
                "rubric": {
                    "intent_understanding": 0.25,
                    "actionability": 0.25,
                    "user_preference_match": 0.15,
                    "information_density": 0.20,
                    "drift_risk": 0.10,
                    "token_efficiency": 0.05,
                },
                "must_include": [
                    "架构", "TypeScript", "开发",
                ],
                "must_not_include": [
                    "这是AI",
                ],
            },
            {
                "id": "case_010",
                "task_input": (
                    "请评估以下代码的质量并给出改进建议：\n"
                    "```python\ndef process(data):\n"
                    "    result = []\n"
                    "    for d in data:\n"
                    "        if d['status'] == 'active':\n"
                    "            result.append(d['name'].upper())\n"
                    "    return result\n"
                    "```"
                ),
                "expected_intent": "结构化评分维度的代码审查",
                "rubric": {
                    "intent_understanding": 0.25,
                    "actionability": 0.25,
                    "user_preference_match": 0.15,
                    "information_density": 0.15,
                    "drift_risk": 0.10,
                    "token_efficiency": 0.10,
                },
                "must_include": [
                    "改进", "建议", "代码",
                ],
                "must_not_include": [
                    "这是AI",
                ],
            },
        ]

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _write_builtin_cases(self) -> None:
        """将内置用例写入 JSONL 文件。"""
        cases = self.get_builtin_cases()
        with open(self.dataset_path, "w", encoding="utf-8") as f:
            for case in cases:
                f.write(json.dumps(case, ensure_ascii=False) + "\n")
        logger.info(
            "已创建验证数据集（%d 条内置用例）: %s",
            len(cases),
            self.dataset_path,
        )
