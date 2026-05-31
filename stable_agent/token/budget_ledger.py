"""Token Budget Ledger — 预算记账本。

提供 Token 运行记录的持久化存储、查询和汇总功能。
使用 SQLite 持久化到 token_ledger/usage.sqlite。

功能：
- record_run: 记录一次运行的 token 消耗
- get_run_record: 按 run_id 查询记录
- summarize_period: 按天汇总统计
- compare_baseline: 与基线对比
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from typing import Any

from stable_agent.token.schemas import TokenRunRecord

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = "token_ledger/usage.sqlite"


class BudgetLedger:
    """Token 预算记账本。

    使用 SQLite 持久化 TokenRunRecord，支持记录、查询和汇总。

    Attributes:
        db_path: SQLite 数据库文件路径。
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        """初始化 BudgetLedger，确保数据库表存在。

        Args:
            db_path: SQLite 数据库文件路径。
        """
        self.db_path = db_path
        self._ensure_db()

    def _ensure_db(self) -> None:
        """确保数据库目录和表结构存在。"""
        parent_dir = os.path.dirname(self.db_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS token_run_records (
                    record_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    data TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_run_id
                ON token_run_records(run_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at
                ON token_run_records(created_at)
            """)
            conn.commit()

    def record_run(self, record: TokenRunRecord) -> None:
        """记录一次运行的 token 消耗。

        Args:
            record: TokenRunRecord 实例。
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO token_run_records "
                "(record_id, run_id, created_at, data) VALUES (?, ?, ?, ?)",
                (
                    record.record_id,
                    record.run_id,
                    record.created_at,
                    json.dumps(record.to_dict(), ensure_ascii=False),
                ),
            )
            conn.commit()

    def get_run_record(self, run_id: str) -> TokenRunRecord | None:
        """按 run_id 查询最新的 token 运行记录。

        Args:
            run_id: 运行 ID。

        Returns:
            TokenRunRecord 实例，未找到返回 None。
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT data FROM token_run_records "
                "WHERE run_id = ? ORDER BY created_at DESC LIMIT 1",
                (run_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return TokenRunRecord.from_dict(json.loads(row[0]))

    def summarize_period(self, days: int = 7) -> dict[str, Any]:
        """按天汇总指定周期内的 token 消耗统计。

        Args:
            days: 统计天数，默认 7。

        Returns:
            包含汇总统计的字典。
        """
        cutoff = time.time() - days * 86400

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT data FROM token_run_records WHERE created_at >= ?",
                (cutoff,),
            )
            rows = cursor.fetchall()

        records = [TokenRunRecord.from_dict(json.loads(row[0])) for row in rows]

        if not records:
            return {
                "period_days": days,
                "total_runs": 0,
                "total_baseline_tokens": 0,
                "total_injected_tokens": 0,
                "total_saved_tokens": 0,
                "avg_saving_ratio": 0.0,
                "risk_distribution": {"low": 0, "medium": 0, "high": 0},
            }

        total_baseline = sum(r.baseline_tokens_estimated for r in records)
        total_injected = sum(r.injected_tokens for r in records)
        total_saved = sum(r.saved_tokens_estimated for r in records)
        avg_saving_ratio = sum(r.saving_ratio for r in records) / len(records)

        risk_dist: dict[str, int] = {"low": 0, "medium": 0, "high": 0}
        for r in records:
            if r.risk_level in risk_dist:
                risk_dist[r.risk_level] += 1

        return {
            "period_days": days,
            "total_runs": len(records),
            "total_baseline_tokens": total_baseline,
            "total_injected_tokens": total_injected,
            "total_saved_tokens": total_saved,
            "avg_saving_ratio": round(avg_saving_ratio, 4),
            "risk_distribution": risk_dist,
        }

    def compare_baseline(self, run_id: str) -> dict[str, Any]:
        """与基线对比指定运行的 token 消耗。

        Args:
            run_id: 运行 ID。

        Returns:
            包含基线对比数据的字典，未找到记录时返回 error。
        """
        record = self.get_run_record(run_id)
        if record is None:
            return {"error": f"未找到 run_id={run_id} 的记录"}

        return {
            "run_id": run_id,
            "baseline_tokens": record.baseline_tokens_estimated,
            "injected_tokens": record.injected_tokens,
            "saved_tokens": record.saved_tokens_estimated,
            "saving_ratio": record.saving_ratio,
            "dropped_count": len(record.dropped_items),
            "protected_count": len(record.protected_items),
            "risk_level": record.risk_level,
        }
