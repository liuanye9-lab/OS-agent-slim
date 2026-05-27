"""上下文决策引擎 — 任务分类、预算估算、记忆选择、评估协议选择。

本模块是 StableAgent OS 的"大脑"，负责根据用户输入推断任务类型，
并为下游模块提供决策依据。所有决策逻辑基于规则（关键词匹配），
不依赖外部 API 调用。

模块职责：
- classify_task: 基于关键词的快速任务分类
- classify_task_multi: 多标签分类 + 置信度
- estimate_token_budget: 根据任务类型和上下文长度估算所需 token
- select_memory_keys: 从可用记忆中按策略选择相关条目
- select_rag_sources: 根据任务类型推荐知识库来源
- choose_evaluation_protocol: 选择最适合任务的评估协议
- detect_risk_level: 检测任务风险等级
- should_require_approval: 综合判断是否需要审批
"""

from __future__ import annotations

import re
from typing import ClassVar

from stable_agent.models import MemoryItem, TaskType


class ContextDecisionEngine:
    """上下文决策引擎。

    提供任务分类、预算估算、记忆选择、RAG 来源选择和评估协议选择
    五项核心决策能力。所有方法均为纯函数式的规则匹配，
    不修改外部状态。

    Attributes:
        _task_keywords: 任务类型 → 触发关键词列表的映射。
    """

    # ------------------------------------------------------------------
    # 任务类型关键词映射表
    # ------------------------------------------------------------------
    _task_keywords: ClassVar[dict[TaskType, list[str]]] = {
        TaskType.BUG_FIX: ["bug", "修复", "报错", "崩溃", "异常", "缺陷", "补丁"],
        TaskType.UI_DESIGN: [
            "UI", "界面", "样式", "布局", "设计", "CSS", "组件",
            "颜色", "字体", "按钮", "图标", "页面", "动效",
        ],
        TaskType.ARCH_REFACTOR: [
            "架构", "重构", "模块", "结构", "设计模式", "解耦",
            "依赖", "抽象", "分层", "接口",
        ],
        TaskType.PROMPT_OPTIMIZATION: [
            "prompt", "提示词", "优化输出", "生成质量", "指令",
            "few-shot", "chain-of-thought",
        ],
        TaskType.EVAL_TASK: [
            "评估", "评测", "打分", "测试用例", "benchmark", "衡量",
            "对比", "排名",
        ],
        TaskType.CODE_GENERATION: [
            "实现", "开发", "写代码", "新增功能", "feature", "编码",
            "添加", "增加", "创建类", "创建函数",
        ],
    }

    # 高风险关键词
    _high_risk_keywords: ClassVar[list[str]] = [
        "删除", "清空", "格式化", "覆盖",
        "rm ", "drop ", "truncate", "format",
    ]

    # 中风险关键词
    _medium_risk_keywords: ClassVar[list[str]] = [
        "修改", "重构", "迁移", "更新",
        "调整", "替换", "变更",
    ]

    # ------------------------------------------------------------------
    # 公共方法
    # ------------------------------------------------------------------

    def classify_task(self, task_input: str) -> TaskType:
        """基于关键词匹配对任务输入进行分类。

        遍历所有 TaskType 及其关联关键词，统计每种类型的关键词命中数。
        选择命中数最多的类型；平局时按关键词表定义顺序取第一个。
        若所有类型均未命中，返回 GENERAL_QA。

        Args:
            task_input: 用户的自然语言任务描述。

        Returns:
            匹配到的 TaskType。

        Examples:
            >>> engine = ContextDecisionEngine()
            >>> engine.classify_task("修复登录页面的崩溃问题")
            <TaskType.BUG_FIX: 'bug_fix'>
            >>> engine.classify_task("今天天气怎么样")
            <TaskType.GENERAL_QA: 'general_qa'>
        """
        normalized: str = task_input.lower()
        scores: dict[TaskType, int] = {}

        for task_type, keywords in self._task_keywords.items():
            count: int = sum(
                1 for kw in keywords if kw.lower() in normalized
            )
            if count > 0:
                scores[task_type] = count

        if not scores:
            return TaskType.GENERAL_QA

        # 按命中数降序、关键词表顺序（即字典插入顺序）打破平局
        return max(scores, key=lambda t: (scores[t], -list(self._task_keywords).index(t)))

    def classify_task_multi(self, task_input: str) -> dict[TaskType, float]:
        """多标签分类 + 置信度。

        统计每种任务类型的关键词命中数，归一化为 confidence (0~1)。

        策略：对每种 TaskType 统计关键词命中数，除以该类型关键词总数，
        得到该类型的置信度。

        Args:
            task_input: 用户的自然语言任务描述。

        Returns:
            {TaskType: confidence_score} 字典。置信度为 0.0~1.0。

        Examples:
            >>> engine = ContextDecisionEngine()
            >>> scores = engine.classify_task_multi("修复登录页面的样式错位")
            >>> scores[TaskType.BUG_FIX] > 0
            True
            >>> scores[TaskType.UI_DESIGN] > 0
            True
        """
        normalized: str = task_input.lower()
        result: dict[TaskType, float] = {}

        for task_type, keywords in self._task_keywords.items():
            hit_count: int = sum(
                1 for kw in keywords if kw.lower() in normalized
            )
            total_keywords: int = len(keywords)
            if total_keywords > 0 and hit_count > 0:
                # 归一化：命中数 / 关键词总数，限制在 [0, 1]
                confidence: float = min(1.0, hit_count / max(3, total_keywords))
                result[task_type] = round(confidence, 4)

        # 若没有任何关键词命中，返回 GENERAL_QA 低置信度
        if not result:
            result[TaskType.GENERAL_QA] = 0.5

        return result

    def get_primary_task(self, scores: dict[TaskType, float]) -> TaskType:
        """从多标签结果中取最高置信度的主任务。

        Args:
            scores: classify_task_multi 的返回值。

        Returns:
            置信度最高的 TaskType。若 scores 为空，返回 GENERAL_QA。

        Examples:
            >>> engine = ContextDecisionEngine()
            >>> scores = {TaskType.BUG_FIX: 0.6, TaskType.UI_DESIGN: 0.8}
            >>> engine.get_primary_task(scores)
            <TaskType.UI_DESIGN: 'ui_design'>
        """
        if not scores:
            return TaskType.GENERAL_QA

        return max(scores, key=lambda t: scores[t])

    def detect_risk_level(self, task_input: str) -> str:
        """检测任务风险等级。

        规则：
        - 包含"删除/清空/格式化/覆盖"等 → HIGH
        - 包含"修改/重构/迁移"等 → MEDIUM
        - 默认 → LOW

        Args:
            task_input: 用户的自然语言任务描述。

        Returns:
            风险等级字符串："high"、"medium" 或 "low"。

        Examples:
            >>> engine = ContextDecisionEngine()
            >>> engine.detect_risk_level("删除所有用户数据")
            'high'
            >>> engine.detect_risk_level("修改登录页面的样式")
            'medium'
            >>> engine.detect_risk_level("查看天气")
            'low'
        """
        normalized: str = task_input.lower()

        # 先检查高风险
        for kw in self._high_risk_keywords:
            if kw.lower() in normalized:
                return "high"

        # 再检查中风险
        for kw in self._medium_risk_keywords:
            if kw.lower() in normalized:
                return "medium"

        return "low"

    def should_require_approval(self, task_input: str, task_type: TaskType) -> bool:
        """综合判断是否需要审批。

        HIGH 风险 + ARCH_REFACTOR 类型 → True。
        其他情况 → False。

        Args:
            task_input: 用户的自然语言任务描述。
            task_type: 任务类型。

        Returns:
            True 表示需要审批，False 表示不需要。

        Examples:
            >>> engine = ContextDecisionEngine()
            >>> engine.should_require_approval("删除并重构架构", TaskType.ARCH_REFACTOR)
            True
            >>> engine.should_require_approval("修复小bug", TaskType.BUG_FIX)
            False
        """
        risk_level: str = self.detect_risk_level(task_input)

        # HIGH 风险 + ARCH_REFACTOR → 需要审批
        if risk_level == "high" and task_type == TaskType.ARCH_REFACTOR:
            return True

        return False

    def estimate_token_budget(
        self,
        task: TaskType,
        context_length: int,
        urgency: int = 1,
    ) -> int:
        """估算任务执行所需的 token 预算。

        基础预算由任务类型决定，然后根据紧急程度和上下文长度进行调整：
        - urgency >= 3 时，预算增加 20%（高优先级任务需要更多上下文）
        - context_length > 10000 时，预算减少 10%（已有大量上下文，压缩输出）

        Args:
            task: 任务类型。
            context_length: 当前上下文字符数。
            urgency: 紧急程度，1~5，默认 1。

        Returns:
            估算的 token 预算（整数）。

        Examples:
            >>> engine = ContextDecisionEngine()
            >>> engine.estimate_token_budget(TaskType.BUG_FIX, 5000)
            8000
            >>> engine.estimate_token_budget(TaskType.BUG_FIX, 5000, urgency=3)
            9600
        """
        # 各任务类型的基础预算表
        base_budgets: dict[TaskType, int] = {
            TaskType.BUG_FIX: 8000,
            TaskType.UI_DESIGN: 6000,
            TaskType.ARCH_REFACTOR: 12000,
            TaskType.PROMPT_OPTIMIZATION: 4000,
            TaskType.EVAL_TASK: 5000,
            TaskType.CODE_GENERATION: 10000,
            TaskType.GENERAL_QA: 4000,
        }

        budget: int = base_budgets.get(task, 4000)

        # 紧急任务增加预算
        if urgency >= 3:
            budget = int(budget * 1.2)

        # 长上下文压缩预算
        if context_length > 10000:
            budget = int(budget * 0.9)

        return budget

    def select_memory_keys(
        self,
        task: TaskType,
        available_memory: list[MemoryItem],
    ) -> list[MemoryItem]:
        """从可用记忆中选择与当前任务最相关的条目。

        选择策略：
        1. 过滤 status == "active" 的条目
        2. 按 priority 降序排序
        3. 根据任务类型加权：
           - BUG_FIX / ARCH_REFACTOR: bad_case 排序权重 +0.3
           - UI_DESIGN / PROMPT_OPTIMIZATION: success_case 排序权重 +0.3

        Args:
            task: 当前任务类型。
            available_memory: 可用记忆列表。

        Returns:
            排序后的记忆条目列表（原列表不变，返回新列表）。
        """
        # 过滤 active
        active: list[MemoryItem] = [
            m for m in available_memory if m.status == "active"
        ]

        # 定义排序键：priority + type 加权
        def sort_key(item: MemoryItem) -> float:
            base: float = item.priority
            # BUG_FIX / ARCH_REFACTOR 优先 bad_case
            if task in (TaskType.BUG_FIX, TaskType.ARCH_REFACTOR):
                if item.type == "bad_case":
                    base += 0.3
            # UI_DESIGN / PROMPT_OPTIMIZATION 优先 success_case
            elif task in (TaskType.UI_DESIGN, TaskType.PROMPT_OPTIMIZATION):
                if item.type == "success_case":
                    base += 0.3
            return base

        return sorted(active, key=sort_key, reverse=True)

    def select_rag_sources(self, task: TaskType) -> list[str]:
        """根据任务类型推荐知识库检索来源。

        不同的任务类型需要不同领域的知识库支持。

        Args:
            task: 任务类型。

        Returns:
            知识库来源名称列表。

        Examples:
            >>> engine = ContextDecisionEngine()
            >>> engine.select_rag_sources(TaskType.BUG_FIX)
            ['代码结构说明', 'API文档', '测试用例']
        """
        rag_map: dict[TaskType, list[str]] = {
            TaskType.BUG_FIX: ["代码结构说明", "API文档", "测试用例"],
            TaskType.UI_DESIGN: ["UI设计规范", "组件库文档"],
            TaskType.ARCH_REFACTOR: ["架构文档", "模块依赖图", "代码结构说明"],
            TaskType.CODE_GENERATION: ["API文档", "代码示例", "最佳实践"],
            TaskType.EVAL_TASK: ["评估标准", "测试用例模板"],
            TaskType.PROMPT_OPTIMIZATION: ["Prompt工程指南", "模板库"],
        }
        return rag_map.get(task, ["需求文档", "通用知识库"])

    def choose_evaluation_protocol(self, task: TaskType) -> str:
        """选择最适合任务的评估协议。

        评估协议决定了 EVALUATE 阶段使用的评分策略：
        - BUG_FIX / CODE_GENERATION: 使用 LLM Judge v1，侧重功能正确性
        - UI_DESIGN: 使用启发式检查，侧重视觉规范
        - 其他: 使用简单规则评估

        Args:
            task: 任务类型。

        Returns:
            评估协议标识字符串。
        """
        if task in (TaskType.BUG_FIX, TaskType.CODE_GENERATION):
            return "llm_judge_v1"
        if task == TaskType.UI_DESIGN:
            return "heuristic_check"
        return "simple_rule_based"
