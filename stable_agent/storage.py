"""StableAgent OS SQLite 持久化存储模块。

使用 Python 标准库 sqlite3 提供轻量级、零依赖的数据持久化。
支持 runs、trace_spans、memory_items、bad_cases、eval_cases、
context_packs、approval_requests 七张表的 CRUD 操作。

约定：
- 所有复杂字段（list、dict）使用 JSON 序列化存储
- 所有方法包含 try/except 错误处理
- 使用 row_factory = sqlite3.Row 获取字典式结果
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Optional

from stable_agent.models import (
    ApprovalRequest,
    BadCase,
    ContextItem,
    ContextPack,
    EvalCase,
    MemoryItem,
    RunRecord,
    TraceSpan,
)


class StableAgentStorage:
    """SQLite 持久化存储层。

    管理七张持久化表：runs, trace_spans, memory_items, bad_cases,
    eval_cases, context_packs, approval_requests。

    所有写操作自动提交，读操作使用 WAL 模式提升并发性能。

    Attributes:
        db_path: 数据库文件路径。
        conn: sqlite3 连接对象（延迟初始化）。
    """

    def __init__(self, db_path: str = "data/stable_agent.sqlite3") -> None:
        """初始化存储层，自动创建 data/ 目录和所有表。

        Args:
            db_path: 数据库文件路径，使用 :memory: 可创建内存数据库。
        """
        self.db_path: str = db_path
        self.conn: Optional[sqlite3.Connection] = None

        # 文件型数据库需要确保目录存在
        if db_path != ":memory:":
            db_dir = Path(db_path).parent
            db_dir.mkdir(parents=True, exist_ok=True)

    def _get_conn(self) -> sqlite3.Connection:
        """获取数据库连接（延迟初始化）。

        Returns:
            sqlite3 连接对象，已配置 row_factory 和 WAL 模式。
        """
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            # WAL 模式提升并发读性能
            self.conn.execute("PRAGMA journal_mode=WAL")
        return self.conn

    def init_db(self) -> None:
        """创建所有表（幂等，使用 IF NOT EXISTS）。"""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                user_task TEXT NOT NULL,
                task_type TEXT NOT NULL DEFAULT 'general_qa',
                status TEXT NOT NULL DEFAULT 'init',
                started_at REAL NOT NULL,
                ended_at REAL,
                total_input_tokens INTEGER NOT NULL DEFAULT 0,
                total_output_tokens INTEGER NOT NULL DEFAULT 0,
                total_cost_estimate REAL NOT NULL DEFAULT 0.0,
                overall_score REAL
            );

            CREATE TABLE IF NOT EXISTS trace_spans (
                span_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                parent_span_id TEXT,
                name TEXT NOT NULL DEFAULT '',
                type TEXT NOT NULL DEFAULT 'execute',
                status TEXT NOT NULL DEFAULT 'started',
                started_at REAL NOT NULL,
                ended_at REAL,
                latency_ms INTEGER,
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                cost_estimate REAL NOT NULL DEFAULT 0.0,
                payload TEXT NOT NULL DEFAULT '{}',
                plain_text TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            );

            CREATE TABLE IF NOT EXISTS memory_items (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                type TEXT NOT NULL,
                timestamp REAL NOT NULL,
                priority REAL NOT NULL DEFAULT 0.5,
                source TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'active',
                layer TEXT NOT NULL DEFAULT 'warm',
                lifecycle TEXT NOT NULL DEFAULT 'active',
                valid_at REAL,
                invalid_at REAL,
                confidence REAL NOT NULL DEFAULT 0.7,
                last_used_at REAL,
                usage_count INTEGER NOT NULL DEFAULT 0,
                tags TEXT NOT NULL DEFAULT '[]'
            );

            CREATE TABLE IF NOT EXISTS bad_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_type TEXT NOT NULL,
                input_context TEXT NOT NULL,
                output TEXT NOT NULL,
                evaluation TEXT NOT NULL DEFAULT '{}',
                timestamp REAL NOT NULL,
                failure_reason TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS eval_cases (
                case_id TEXT PRIMARY KEY,
                input_task TEXT NOT NULL,
                expected_behavior TEXT NOT NULL DEFAULT '',
                must_include TEXT NOT NULL DEFAULT '[]',
                must_not_include TEXT NOT NULL DEFAULT '[]',
                source TEXT NOT NULL DEFAULT 'manual',
                created_from_bad_case_id TEXT,
                task_type TEXT NOT NULL DEFAULT 'general_qa'
            );

            CREATE TABLE IF NOT EXISTS context_packs (
                pack_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL DEFAULT '',
                task_input TEXT NOT NULL DEFAULT '',
                task_type TEXT NOT NULL DEFAULT 'general_qa',
                items TEXT NOT NULL DEFAULT '[]',
                total_tokens INTEGER NOT NULL DEFAULT 0,
                budget_limit INTEGER NOT NULL DEFAULT 0,
                cacheable_prefix TEXT NOT NULL DEFAULT '',
                volatile_context TEXT NOT NULL DEFAULT '',
                critical_reminders TEXT NOT NULL DEFAULT '[]',
                compaction_report TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS approval_requests (
                request_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                action TEXT NOT NULL,
                risk TEXT NOT NULL DEFAULT 'medium',
                reason TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                created_at REAL NOT NULL,
                resolved_at REAL,
                details TEXT NOT NULL DEFAULT '{}'
            );

            CREATE INDEX IF NOT EXISTS idx_spans_run_id ON trace_spans(run_id);
            CREATE INDEX IF NOT EXISTS idx_memory_status ON memory_items(status);
            CREATE INDEX IF NOT EXISTS idx_memory_layer ON memory_items(layer);
            CREATE INDEX IF NOT EXISTS idx_memory_lifecycle ON memory_items(lifecycle);
            CREATE INDEX IF NOT EXISTS idx_approval_status ON approval_requests(status);
        """)
        conn.commit()

    # ------------------------------------------------------------------
    # Run 操作
    # ------------------------------------------------------------------

    def save_run(self, record: RunRecord) -> bool:
        """保存运行记录。

        Args:
            record: RunRecord 实例。

        Returns:
            True 表示保存成功，False 表示失败。
        """
        try:
            conn = self._get_conn()
            conn.execute(
                """INSERT OR REPLACE INTO runs
                   (run_id, user_task, task_type, status, started_at, ended_at,
                    total_input_tokens, total_output_tokens, total_cost_estimate,
                    overall_score)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.run_id,
                    record.user_task,
                    record.task_type.value,
                    record.status,
                    record.started_at,
                    record.ended_at,
                    record.total_input_tokens,
                    record.total_output_tokens,
                    record.total_cost_estimate,
                    record.overall_score,
                ),
            )
            conn.commit()
            return True
        except Exception:
            return False

    def update_run(self, run_id: str, fields: dict[str, Any]) -> bool:
        """更新运行记录的部分字段。

        Args:
            run_id: 运行 ID。
            fields: 要更新的字段字典。

        Returns:
            True 表示更新成功，False 表示失败。
        """
        try:
            if not fields:
                return True
            conn = self._get_conn()
            set_clause = ", ".join(f"{k} = ?" for k in fields)
            values = list(fields.values()) + [run_id]
            conn.execute(
                f"UPDATE runs SET {set_clause} WHERE run_id = ?",
                values,
            )
            conn.commit()
            return True
        except Exception:
            return False

    def get_run(self, run_id: str) -> Optional[RunRecord]:
        """获取单条运行记录。

        Args:
            run_id: 运行 ID。

        Returns:
            RunRecord 实例，未找到返回 None。
        """
        try:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT * FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if row is None:
                return None
            return self._row_to_run_record(row)
        except Exception:
            return None

    def list_runs(self, limit: int = 20) -> list[RunRecord]:
        """列出最近的运行记录。

        Args:
            limit: 返回数量上限。

        Returns:
            RunRecord 列表，按 started_at 降序排列。
        """
        try:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [self._row_to_run_record(r) for r in rows]
        except Exception:
            return []

    @staticmethod
    def _row_to_run_record(row: sqlite3.Row) -> RunRecord:
        """将数据库行转换为 RunRecord。"""
        from stable_agent.models import TaskType

        return RunRecord(
            run_id=row["run_id"],
            user_task=row["user_task"],
            task_type=TaskType(row["task_type"]),
            status=row["status"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            total_input_tokens=row["total_input_tokens"],
            total_output_tokens=row["total_output_tokens"],
            total_cost_estimate=row["total_cost_estimate"],
            overall_score=row["overall_score"],
        )

    # ------------------------------------------------------------------
    # TraceSpan 操作
    # ------------------------------------------------------------------

    def save_span(self, span: TraceSpan) -> bool:
        """保存追踪 Span。

        Args:
            span: TraceSpan 实例。

        Returns:
            True 表示保存成功，False 表示失败。
        """
        try:
            conn = self._get_conn()
            conn.execute(
                """INSERT OR REPLACE INTO trace_spans
                   (span_id, run_id, parent_span_id, name, type, status,
                    started_at, ended_at, latency_ms, input_tokens,
                    output_tokens, cost_estimate, payload, plain_text)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    span.span_id,
                    span.run_id,
                    span.parent_span_id,
                    span.name,
                    span.type,
                    span.status,
                    span.started_at,
                    span.ended_at,
                    span.latency_ms,
                    span.input_tokens,
                    span.output_tokens,
                    span.cost_estimate,
                    json.dumps(span.payload, ensure_ascii=False),
                    span.plain_text,
                ),
            )
            conn.commit()
            return True
        except Exception:
            return False

    def load_spans(self, run_id: str) -> list[TraceSpan]:
        """加载指定运行的所有 Span。

        Args:
            run_id: 运行 ID。

        Returns:
            TraceSpan 列表。
        """
        try:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT * FROM trace_spans WHERE run_id = ? ORDER BY started_at ASC",
                (run_id,),
            ).fetchall()
            return [self._row_to_trace_span(r) for r in rows]
        except Exception:
            return []

    @staticmethod
    def _row_to_trace_span(row: sqlite3.Row) -> TraceSpan:
        """将数据库行转换为 TraceSpan。"""
        return TraceSpan(
            span_id=row["span_id"],
            run_id=row["run_id"],
            parent_span_id=row["parent_span_id"],
            name=row["name"],
            type=row["type"],
            status=row["status"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            latency_ms=row["latency_ms"],
            input_tokens=row["input_tokens"],
            output_tokens=row["output_tokens"],
            cost_estimate=row["cost_estimate"],
            payload=json.loads(row["payload"]),
            plain_text=row["plain_text"],
        )

    # ------------------------------------------------------------------
    # MemoryItem 操作
    # ------------------------------------------------------------------

    def save_memory(self, item: MemoryItem) -> bool:
        """保存记忆条目。

        Args:
            item: MemoryItem 实例。

        Returns:
            True 表示保存成功，False 表示失败。
        """
        try:
            conn = self._get_conn()
            conn.execute(
                """INSERT OR REPLACE INTO memory_items
                   (id, content, type, timestamp, priority, source, status,
                    layer, lifecycle, valid_at, invalid_at, confidence,
                    last_used_at, usage_count, tags)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    item.id,
                    item.content,
                    item.type,
                    item.timestamp,
                    item.priority,
                    item.source,
                    item.status,
                    item.layer,
                    item.lifecycle,
                    item.valid_at,
                    item.invalid_at,
                    item.confidence,
                    item.last_used_at,
                    item.usage_count,
                    json.dumps(item.tags, ensure_ascii=False),
                ),
            )
            conn.commit()
            return True
        except Exception:
            return False

    def load_memory(
        self,
        status: Optional[str] = None,
        layer: Optional[str] = None,
        lifecycle: Optional[str] = None,
        limit: int = 100,
    ) -> list[MemoryItem]:
        """加载记忆条目，支持按状态、分层、生命周期过滤。

        Args:
            status: 过滤状态（active/outdated），None 表示不过滤。
            layer: 过滤分层（hot/warm/cold），None 表示不过滤。
            lifecycle: 过滤生命周期（candidate/active/outdated/archived），None 表示不过滤。
            limit: 返回数量上限。

        Returns:
            MemoryItem 列表，按 priority 降序排列。
        """
        try:
            conn = self._get_conn()
            query = "SELECT * FROM memory_items WHERE 1=1"
            params: list[Any] = []

            if status is not None:
                query += " AND status = ?"
                params.append(status)
            if layer is not None:
                query += " AND layer = ?"
                params.append(layer)
            if lifecycle is not None:
                query += " AND lifecycle = ?"
                params.append(lifecycle)

            query += " ORDER BY priority DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(query, params).fetchall()
            return [self._row_to_memory_item(r) for r in rows]
        except Exception:
            return []

    def update_memory_field(self, memory_id: str, field: str, value: Any) -> bool:
        """更新记忆条目的单个字段。

        Args:
            memory_id: 记忆 ID。
            field: 字段名。
            value: 新值。

        Returns:
            True 表示更新成功，False 表示失败。
        """
        try:
            conn = self._get_conn()
            conn.execute(
                f"UPDATE memory_items SET {field} = ? WHERE id = ?",
                (value, memory_id),
            )
            conn.commit()
            return True
        except Exception:
            return False

    @staticmethod
    def _row_to_memory_item(row: sqlite3.Row) -> MemoryItem:
        """将数据库行转换为 MemoryItem。"""
        return MemoryItem(
            id=row["id"],
            content=row["content"],
            type=row["type"],
            timestamp=row["timestamp"],
            priority=row["priority"],
            source=row["source"],
            status=row["status"],
            layer=row["layer"],
            lifecycle=row["lifecycle"],
            valid_at=row["valid_at"],
            invalid_at=row["invalid_at"],
            confidence=row["confidence"],
            last_used_at=row["last_used_at"],
            usage_count=row["usage_count"],
            tags=json.loads(row["tags"]),
        )

    # ------------------------------------------------------------------
    # BadCase 操作
    # ------------------------------------------------------------------

    def save_bad_case(self, case: BadCase) -> bool:
        """保存负面案例。

        Args:
            case: BadCase 实例。

        Returns:
            True 表示保存成功，False 表示失败。
        """
        try:
            conn = self._get_conn()
            evaluation_json = json.dumps(
                {
                    "completion_rate": case.evaluation.completion_rate,
                    "context_hit_rate": case.evaluation.context_hit_rate,
                    "token_efficiency": case.evaluation.token_efficiency,
                    "hallucination_score": case.evaluation.hallucination_score,
                    "user_preference_score": case.evaluation.user_preference_score,
                    "overall_score": case.evaluation.overall_score,
                    "retrieval_quality": case.evaluation.retrieval_quality,
                    "memory_quality": case.evaluation.memory_quality,
                    "tool_quality": case.evaluation.tool_quality,
                    "format_quality": case.evaluation.format_quality,
                    "safety_score": case.evaluation.safety_score,
                    "token_roi": case.evaluation.token_roi,
                    "failure_reasons": case.evaluation.failure_reasons,
                    "improvement_rules": case.evaluation.improvement_rules,
                },
                ensure_ascii=False,
            )
            conn.execute(
                """INSERT INTO bad_cases
                   (task_type, input_context, output, evaluation, timestamp,
                    failure_reason)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    case.task_type.value,
                    case.input_context,
                    case.output,
                    evaluation_json,
                    case.timestamp,
                    case.failure_reason,
                ),
            )
            conn.commit()
            return True
        except Exception:
            return False

    def load_bad_cases(self, limit: int = 50) -> list[BadCase]:
        """加载最近的负面案例。

        Args:
            limit: 返回数量上限。

        Returns:
            BadCase 列表，按 timestamp 降序排列。
        """
        try:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT * FROM bad_cases ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [self._row_to_bad_case(r) for r in rows]
        except Exception:
            return []

    @staticmethod
    def _row_to_bad_case(row: sqlite3.Row) -> BadCase:
        """将数据库行转换为 BadCase。"""
        from stable_agent.models import EvaluationResult, TaskType

        eval_dict = json.loads(row["evaluation"])
        evaluation = EvaluationResult(
            completion_rate=eval_dict.get("completion_rate", 0.0),
            context_hit_rate=eval_dict.get("context_hit_rate", 0.0),
            token_efficiency=eval_dict.get("token_efficiency", 0.0),
            hallucination_score=eval_dict.get("hallucination_score", 0.0),
            user_preference_score=eval_dict.get("user_preference_score", 0.0),
            overall_score=eval_dict.get("overall_score", 0.0),
            retrieval_quality=eval_dict.get("retrieval_quality", 0.0),
            memory_quality=eval_dict.get("memory_quality", 0.0),
            tool_quality=eval_dict.get("tool_quality", 0.0),
            format_quality=eval_dict.get("format_quality", 0.0),
            safety_score=eval_dict.get("safety_score", 1.0),
            token_roi=eval_dict.get("token_roi", 0.0),
            failure_reasons=eval_dict.get("failure_reasons", []),
            improvement_rules=eval_dict.get("improvement_rules", []),
        )
        return BadCase(
            task_type=TaskType(row["task_type"]),
            input_context=row["input_context"],
            output=row["output"],
            evaluation=evaluation,
            timestamp=row["timestamp"],
            failure_reason=row["failure_reason"],
        )

    # ------------------------------------------------------------------
    # EvalCase 操作
    # ------------------------------------------------------------------

    def append_eval_case(self, case: EvalCase) -> bool:
        """添加评估用例。

        Args:
            case: EvalCase 实例。

        Returns:
            True 表示添加成功，False 表示失败。
        """
        try:
            conn = self._get_conn()
            conn.execute(
                """INSERT OR REPLACE INTO eval_cases
                   (case_id, input_task, expected_behavior, must_include,
                    must_not_include, source, created_from_bad_case_id, task_type)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    case.case_id,
                    case.input_task,
                    case.expected_behavior,
                    json.dumps(case.must_include, ensure_ascii=False),
                    json.dumps(case.must_not_include, ensure_ascii=False),
                    case.source,
                    case.created_from_bad_case_id,
                    case.task_type.value,
                ),
            )
            conn.commit()
            return True
        except Exception:
            return False

    def load_eval_cases(self, limit: int = 100) -> list[EvalCase]:
        """加载评估用例。

        Args:
            limit: 返回数量上限。

        Returns:
            EvalCase 列表。
        """
        try:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT * FROM eval_cases LIMIT ?", (limit,)
            ).fetchall()
            return [self._row_to_eval_case(r) for r in rows]
        except Exception:
            return []

    @staticmethod
    def _row_to_eval_case(row: sqlite3.Row) -> EvalCase:
        """将数据库行转换为 EvalCase。"""
        from stable_agent.models import TaskType

        return EvalCase(
            case_id=row["case_id"],
            input_task=row["input_task"],
            expected_behavior=row["expected_behavior"],
            must_include=json.loads(row["must_include"]),
            must_not_include=json.loads(row["must_not_include"]),
            source=row["source"],
            created_from_bad_case_id=row["created_from_bad_case_id"],
            task_type=TaskType(row["task_type"]),
        )

    # ------------------------------------------------------------------
    # ContextPack 操作
    # ------------------------------------------------------------------

    def save_context_pack(self, pack: ContextPack) -> bool:
        """保存上下文包。

        Args:
            pack: ContextPack 实例。

        Returns:
            True 表示保存成功，False 表示失败。
        """
        try:
            conn = self._get_conn()
            items_json = json.dumps(
                [
                    {
                        "id": item.id,
                        "content": item.content,
                        "source_type": item.source_type,
                        "source_id": item.source_id,
                        "priority": item.priority,
                        "relevance_score": item.relevance_score,
                        "token_estimate": item.token_estimate,
                        "reason": item.reason,
                        "risk": item.risk,
                        "placement": item.placement,
                    }
                    for item in pack.items
                ],
                ensure_ascii=False,
            )
            conn.execute(
                """INSERT OR REPLACE INTO context_packs
                   (pack_id, run_id, task_input, task_type, items, total_tokens,
                    budget_limit, cacheable_prefix, volatile_context,
                    critical_reminders, compaction_report)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    pack.pack_id,
                    pack.run_id,
                    pack.task_input,
                    pack.task_type.value,
                    items_json,
                    pack.total_tokens,
                    pack.budget_limit,
                    pack.cacheable_prefix,
                    pack.volatile_context,
                    json.dumps(pack.critical_reminders, ensure_ascii=False),
                    json.dumps(pack.compaction_report, ensure_ascii=False),
                ),
            )
            conn.commit()
            return True
        except Exception:
            return False

    def get_context_pack(self, pack_id: str) -> Optional[ContextPack]:
        """获取上下文包。

        Args:
            pack_id: 上下文包 ID。

        Returns:
            ContextPack 实例，未找到返回 None。
        """
        try:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT * FROM context_packs WHERE pack_id = ?", (pack_id,)
            ).fetchone()
            if row is None:
                return None
            return self._row_to_context_pack(row)
        except Exception:
            return None

    @staticmethod
    def _row_to_context_pack(row: sqlite3.Row) -> ContextPack:
        """将数据库行转换为 ContextPack。"""
        from stable_agent.models import TaskType

        items_raw = json.loads(row["items"])
        items = [
            ContextItem(
                id=it["id"],
                content=it["content"],
                source_type=it.get("source_type", ""),
                source_id=it.get("source_id", ""),
                priority=it.get("priority", 0.5),
                relevance_score=it.get("relevance_score", 0.0),
                token_estimate=it.get("token_estimate", 0),
                reason=it.get("reason", ""),
                risk=it.get("risk"),
                placement=it.get("placement", "middle"),
            )
            for it in items_raw
        ]
        return ContextPack(
            pack_id=row["pack_id"],
            run_id=row["run_id"],
            task_input=row["task_input"],
            task_type=TaskType(row["task_type"]),
            items=items,
            total_tokens=row["total_tokens"],
            budget_limit=row["budget_limit"],
            cacheable_prefix=row["cacheable_prefix"],
            volatile_context=row["volatile_context"],
            critical_reminders=json.loads(row["critical_reminders"]),
            compaction_report=json.loads(row["compaction_report"]),
        )

    # ------------------------------------------------------------------
    # ApprovalRequest 操作
    # ------------------------------------------------------------------

    def save_approval(self, req: ApprovalRequest) -> bool:
        """保存审批请求。

        Args:
            req: ApprovalRequest 实例。

        Returns:
            True 表示保存成功，False 表示失败。
        """
        try:
            conn = self._get_conn()
            conn.execute(
                """INSERT OR REPLACE INTO approval_requests
                   (request_id, run_id, action, risk, reason, status,
                    created_at, resolved_at, details)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    req.request_id,
                    req.run_id,
                    req.action,
                    req.risk,
                    req.reason,
                    req.status,
                    req.created_at,
                    req.resolved_at,
                    json.dumps(req.details, ensure_ascii=False),
                ),
            )
            conn.commit()
            return True
        except Exception:
            return False

    def update_approval(
        self,
        request_id: str,
        status: str,
        resolved_at: Optional[float] = None,
    ) -> bool:
        """更新审批请求的状态。

        Args:
            request_id: 请求 ID。
            status: 新状态（approved/rejected）。
            resolved_at: 解决时间戳，None 使用当前时间。

        Returns:
            True 表示更新成功，False 表示失败。
        """
        try:
            import time

            conn = self._get_conn()
            if resolved_at is None:
                resolved_at = time.time()
            conn.execute(
                "UPDATE approval_requests SET status = ?, resolved_at = ? "
                "WHERE request_id = ?",
                (status, resolved_at, request_id),
            )
            conn.commit()
            return True
        except Exception:
            return False

    def list_pending_approvals(self) -> list[ApprovalRequest]:
        """列出所有待审批的请求。

        Returns:
            ApprovalRequest 列表，按 created_at 升序排列。
        """
        try:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT * FROM approval_requests WHERE status = 'pending' "
                "ORDER BY created_at ASC"
            ).fetchall()
            return [self._row_to_approval_request(r) for r in rows]
        except Exception:
            return []

    @staticmethod
    def _row_to_approval_request(row: sqlite3.Row) -> ApprovalRequest:
        """将数据库行转换为 ApprovalRequest。"""
        return ApprovalRequest(
            request_id=row["request_id"],
            run_id=row["run_id"],
            action=row["action"],
            risk=row["risk"],
            reason=row["reason"],
            status=row["status"],
            created_at=row["created_at"],
            resolved_at=row["resolved_at"],
            details=json.loads(row["details"]),
        )
