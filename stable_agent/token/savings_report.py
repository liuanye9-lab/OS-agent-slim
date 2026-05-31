"""Token Budget Ledger — 节省报告生成器。

生成指定运行的 token 节省报告，包含基线对比、节省比例、
风险评估、保护/丢弃条目和中文摘要。
"""

from __future__ import annotations

from typing import Any

from stable_agent.token.budget_ledger import BudgetLedger


class SavingsReport:
    """Token 节省报告生成器。

    从 BudgetLedger 中读取运行记录，生成结构化的节省报告。
    """

    def generate(self, run_id: str, ledger: BudgetLedger) -> dict[str, Any]:
        """生成指定运行的 token 节省报告。

        Args:
            run_id: 运行 ID。
            ledger: BudgetLedger 实例。

        Returns:
            包含完整节省报告的字典，未找到记录时返回 error。
        """
        record = ledger.get_run_record(run_id)
        if record is None:
            return {"error": f"未找到 run_id={run_id} 的记录"}

        return {
            "run_id": run_id,
            "record_id": record.record_id,
            "baseline_tokens": record.baseline_tokens_estimated,
            "injected_tokens": record.injected_tokens,
            "saved_tokens": record.saved_tokens_estimated,
            "saving_ratio": record.saving_ratio,
            "risk_level": record.risk_level,
            "protected_items": record.protected_items,
            "dropped_items": record.dropped_items,
            "summary_zh": record.summary_zh,
            "raw_context_tokens": record.raw_context_tokens,
            "deduped_tokens": record.deduped_tokens,
            "retrieved_tokens": record.retrieved_tokens,
            "protected_tokens": record.protected_tokens,
            "dropped_tokens": record.dropped_tokens,
            "output_tokens_estimated": record.output_tokens_estimated,
        }
