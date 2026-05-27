"""上下文预算管理器 — Token 预算分配、文档压缩、记忆剪枝、模型路由。

本模块负责在所有 Pipeline 阶段间合理分配 token 预算，确保
不会被单个阶段耗尽上下文窗口。同时提供文档压缩和记忆剪枝策略，
以及根据任务复杂度选择合适的模型路由。

模块职责：
- compute_budget: 按任务类型分配各阶段 token 子预算
- allocate_budget: 动态预算分配（带复杂度/风险/bad_case 调整）
- compress_documents: 对超预算文档集进行截断压缩
- prune_memory: 按优先级和预算裁剪记忆条目
- route_model: 根据任务复杂度选择模型规格
- calculate_token_roi: 计算 Token 投资回报率
- split_cacheable_and_volatile: 分离稳定前缀和动态上下文
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from stable_agent.models import MemoryItem, TaskType, TokenBudget

if TYPE_CHECKING:
    from stable_agent.token_meter import TokenMeter
    from stable_agent.models import ContextPack, EvaluationResult


class ContextBudgetManager:
    """上下文预算管理器。

    管理 token 预算的分配、文档压缩、记忆剪枝和模型路由决策。

    Attributes:
        _budget_ratios: 各任务类型对应的子预算比例配置。
        token_meter: Token 计量器实例（可选）。
    """

    # 各任务类型的基础预算（TokenBudget 参数）
    _base_budgets: dict[TaskType, dict[str, int]] = {
        TaskType.BUG_FIX: {"memory_budget": 2000, "rag_budget": 3000, "prompt_budget": 6000, "output_budget": 2000},
        TaskType.ARCH_REFACTOR: {"memory_budget": 3000, "rag_budget": 5000, "prompt_budget": 8000, "output_budget": 3000},
        TaskType.UI_DESIGN: {"memory_budget": 1500, "rag_budget": 2000, "prompt_budget": 5000, "output_budget": 1500},
        TaskType.CODE_GENERATION: {"memory_budget": 2000, "rag_budget": 4000, "prompt_budget": 8000, "output_budget": 2500},
        TaskType.EVAL_TASK: {"memory_budget": 1500, "rag_budget": 1500, "prompt_budget": 4000, "output_budget": 1000},
        TaskType.PROMPT_OPTIMIZATION: {"memory_budget": 1000, "rag_budget": 1000, "prompt_budget": 4000, "output_budget": 1000},
    }

    _default_base: dict[str, int] = {
        "memory_budget": 2000, "rag_budget": 2000, "prompt_budget": 6000, "output_budget": 1500,
    }

    def __init__(self, token_meter: Optional[TokenMeter] = None) -> None:
        """初始化预算管理器。

        配置各任务类型的子预算分配比例表。比例值会在 compute_budget
        中直接返回为 token 数量（预计算值，非比率）。

        Args:
            token_meter: 可选的 TokenMeter 实例，用于精确 token 估算。
                         None 时自动创建默认实例。
        """
        from stable_agent.token_meter import TokenMeter

        self.token_meter = token_meter or TokenMeter()
        # 各任务类型 → {子预算分类: token数}
        self._budget_ratios: dict[TaskType, dict[str, int]] = {
            TaskType.BUG_FIX: {
                "memory": 2000, "rag": 3000, "prompt": 1500, "output": 1500,
            },
            TaskType.ARCH_REFACTOR: {
                "memory": 3000, "rag": 5000, "prompt": 2000, "output": 2000,
            },
            TaskType.UI_DESIGN: {
                "memory": 1500, "rag": 2000, "prompt": 1000, "output": 1500,
            },
            TaskType.CODE_GENERATION: {
                "memory": 2000, "rag": 4000, "prompt": 2500, "output": 1500,
            },
            TaskType.EVAL_TASK: {
                "memory": 1500, "rag": 1500, "prompt": 1000, "output": 1000,
            },
            TaskType.PROMPT_OPTIMIZATION: {
                "memory": 1000, "rag": 1000, "prompt": 1000, "output": 1000,
            },
        }
        # 默认预算配置
        self._default_budget: dict[str, int] = {
            "memory": 2000, "rag": 2000, "prompt": 1500, "output": 1500,
        }
        # 跟踪最近的 bad_case 数量（用于动态预算调整）
        self._bad_case_count: int = 0

    # ------------------------------------------------------------------
    # 公共方法
    # ------------------------------------------------------------------

    def compute_budget(self, task: TaskType) -> dict[str, int]:
        """根据任务类型计算各阶段的 token 子预算。

        Args:
            task: 任务类型。

        Returns:
            包含 memory / rag / prompt / output 四个键的字典，
            值为对应阶段的 token 预算上限。

        Examples:
            >>> mgr = ContextBudgetManager()
            >>> mgr.compute_budget(TaskType.BUG_FIX)
            {'memory': 2000, 'rag': 3000, 'prompt': 1500, 'output': 1500}
        """
        return dict(self._budget_ratios.get(task, self._default_budget))

    def allocate_budget(
        self,
        task_type: TaskType,
        complexity: int = 1,
        risk_level: str = "low",
    ) -> TokenBudget:
        """动态预算分配。

        根据复杂度(1~5)、风险等级和最近 bad_case 数量调整预算：
        - 高风险 → 预算 * 1.3
        - 复杂度 >= 3 → 预算 * 1.2
        - bad_case 多（>=3）→ 预算 * 0.9（收紧，更谨慎）

        Args:
            task_type: 任务类型。
            complexity: 复杂度，1~5，默认 1。
            risk_level: 风险等级，"high"/"medium"/"low"，默认 "low"。

        Returns:
            调整后的 TokenBudget 对象。

        Examples:
            >>> mgr = ContextBudgetManager()
            >>> budget = mgr.allocate_budget(TaskType.BUG_FIX, complexity=1)
            >>> budget.memory_budget
            2000
            >>> budget = mgr.allocate_budget(TaskType.ARCH_REFACTOR, complexity=4, risk_level="high")
            >>> budget.memory_budget > 2000
            True
        """
        base: dict[str, int] = self._base_budgets.get(task_type, self._default_base)
        budget: dict[str, int] = dict(base)

        # 高风险 → 预算 * 1.3
        if risk_level == "high":
            for key in budget:
                budget[key] = int(budget[key] * 1.3)

        # 复杂度 >= 3 → 预算 * 1.2
        if complexity >= 3:
            for key in budget:
                budget[key] = int(budget[key] * 1.2)

        # bad_case 多 → 预算 * 0.9（收紧）
        if self._bad_case_count >= 3:
            for key in budget:
                budget[key] = int(budget[key] * 0.9)

        return TokenBudget(
            memory_budget=budget["memory_budget"],
            rag_budget=budget["rag_budget"],
            prompt_budget=budget["prompt_budget"],
            output_budget=budget["output_budget"],
        )

    def calculate_token_roi(
        self, evaluation: "EvaluationResult", total_tokens: int
    ) -> float:
        """Token 投资回报率。

        计算公式：overall_score / (total_tokens / 1000 + 1)
        越高越好。+1 防止除以零。

        Args:
            evaluation: 评估结果。
            total_tokens: 总共消耗的 token 数。

        Returns:
            ROI 分数，可超过 1.0。

        Examples:
            >>> mgr = ContextBudgetManager()
            >>> from stable_agent.models import EvaluationResult
            >>> result = EvaluationResult(overall_score=0.85)
            >>> roi = mgr.calculate_token_roi(result, 5000)
            >>> roi > 0
            True
        """
        denominator: float = (total_tokens / 1000.0) + 1.0
        if denominator <= 0:
            return 0.0
        return round(evaluation.overall_score / denominator, 4)

    def split_cacheable_and_volatile(
        self, context_pack: "ContextPack"
    ) -> tuple[str, str]:
        """分离稳定前缀和动态上下文。

        cacheable: context_pack.cacheable_prefix
        volatile: context_pack.volatile_context

        Args:
            context_pack: 上下文包。

        Returns:
            (cacheable_prefix, volatile_context) 元组。

        Examples:
            >>> mgr = ContextBudgetManager()
            >>> from stable_agent.models import ContextPack
            >>> pack = ContextPack(cacheable_prefix="系统规则", volatile_context="用户任务")
            >>> cacheable, volatile = mgr.split_cacheable_and_volatile(pack)
            >>> cacheable
            '系统规则'
            >>> volatile
            '用户任务'
        """
        return (
            context_pack.cacheable_prefix,
            context_pack.volatile_context,
        )

    def compress_documents(
        self,
        docs: list[str],
        budget: int,
    ) -> list[str]:
        """对文档列表进行截断压缩以适应 token 预算。

        策略（简单截断）：
        1. 将 budget 按文档数量均分
        2. 每个文档保留前 60% 和后 20% 的字符（保留开头和结尾信息）
        3. 中间部分丢弃以节省 token

        # STUB: 可替换为调用 LLM 摘要或 LangChain summarizer 进行
        #   语义级压缩。当前实现为字符级截断。

        Args:
            docs: 原始文档字符串列表。
            budget: 可用于文档的总字符数预算。

        Returns:
            压缩后的文档列表。若 docs 为空，返回空列表。

        Examples:
            >>> mgr = ContextBudgetManager()
            >>> docs = ["abcdefghij", "klmnopqrst"]
            >>> compressed = mgr.compress_documents(docs, budget=8)
            >>> len(compressed)
            2
        """
        if not docs or budget <= 0:
            return []

        per_doc: int = budget // len(docs)
        if per_doc <= 0:
            return [""] * len(docs)

        compressed: list[str] = []
        # 前 60% 和后 20% 的字符数
        head_ratio: float = 0.6
        tail_ratio: float = 0.2
        head_chars: int = max(1, int(per_doc * head_ratio))
        tail_chars: int = max(1, int(per_doc * tail_ratio))

        for doc in docs:
            if len(doc) <= per_doc:
                compressed.append(doc)
            else:
                head: str = doc[:head_chars]
                tail: str = doc[-tail_chars:] if tail_chars > 0 else ""
                compressed.append(f"{head}...{tail}")

        return compressed

    def prune_memory(
        self,
        memory: list[MemoryItem],
        budget: int,
    ) -> list[MemoryItem]:
        """按优先级和 token 预算裁剪记忆条目。

        策略：
        1. 仅保留 status == "active" 的条目
        2. 按 priority 降序排序
        3. 估算每个条目的 token 数（content 长度 / 4）
        4. 累计选取，直到总 token 超过 budget

        Args:
            memory: 记忆条目列表。
            budget: token 预算上限。

        Returns:
            裁剪后的记忆条目列表。若 budget <= 0，返回空列表。

        Examples:
            >>> mgr = ContextBudgetManager()
            >>> items = [MemoryItem(id="1", content="a"*100, type="test", priority=0.9)]
            >>> pruned = mgr.prune_memory(items, budget=10)
            >>> len(pruned) <= 1
            True
        """
        if budget <= 0:
            return []

        # 过滤 + 排序
        active: list[MemoryItem] = sorted(
            [m for m in memory if m.status == "active"],
            key=lambda m: m.priority,
            reverse=True,
        )

        result: list[MemoryItem] = []
        total_tokens: int = 0

        for item in active:
            # 估算 token 数：英文约 4 字符/token，中文约 2 字符/token
            # 此处取保守估计 4 字符/token
            est_tokens: int = max(1, len(item.content) // 4)
            if total_tokens + est_tokens > budget:
                break
            result.append(item)
            total_tokens += est_tokens

        return result

    def route_model(self, task: TaskType) -> str:
        """根据任务复杂度选择模型规格。

        架构重构和代码生成任务通常需要更强的推理能力，
        路由到 large 模型；其他任务使用 small 模型以节省成本。

        # STUB: 真实集成时需对接 LLM 网关，根据模型可用性和成本
        #   动态选择。当前返回逻辑标识符。

        Args:
            task: 任务类型。

        Returns:
            模型规格标识符，"large" 或 "small"。
        """
        if task in (TaskType.ARCH_REFACTOR, TaskType.CODE_GENERATION):
            return "large"
        return "small"

    def set_bad_case_count(self, count: int) -> None:
        """设置最近 bad_case 数量，用于动态预算调整。

        Args:
            count: bad_case 数量。
        """
        self._bad_case_count = max(0, count)
