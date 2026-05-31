"""stable_agent.capsule.memory_lifecycle — 记忆生命周期管理。

实现四层记忆结构和记忆价值评分，支持候选、晋升、冲突标记、
过期检查、健康报告生成。
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _new_id(prefix: str = "mem") -> str:
    """生成唯一 ID。"""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# 记忆类型常量
MEMORY_TYPES = [
    "raw_episode",
    "episode_summary",
    "semantic_memory",
    "skill_rule",
    "regression_case",
]

# 记忆类型默认有效期（秒）
DEFAULT_TTL = {
    "raw_episode": 30 * 86400,         # 30 天
    "episode_summary": 180 * 86400,     # 180 天
    "semantic_memory": None,            # 长期
    "skill_rule": None,                 # 长期
    "regression_case": None,            # 长期
}


@dataclass(frozen=False)
class MemoryLifecycleManager:
    """记忆生命周期管理器。

    管理四层记忆结构：
    1. raw_episode — 原始任务片段（7~30 天过期）
    2. episode_summary — 任务压缩总结（30~180 天）
    3. semantic_memory — 用户偏好、项目事实（长期，需确认）
    4. skill_rule / regression_case — 经验证的规则（长期）

    Attributes:
        capsule_path: 胶囊根目录。
        _memories: 内存缓存，memory_id → dict。
    """

    capsule_path: Path = field(default_factory=lambda: Path("."))
    _memories: dict[str, dict[str, Any]] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        """初始化后自动从磁盘加载记忆。"""
        self._load_from_disk()

    # ------------------------------------------------------------------
    # 公共方法
    # ------------------------------------------------------------------

    def add_candidate(
        self,
        content: str,
        memory_type: str = "raw_episode",
        scope: str = "global",
        source: str = "run_trace",
        source_run_id: str | None = None,
        project_id: str | None = None,
        confidence: float = 0.5,
        tags: list[str] | None = None,
        valid_until: float | None = None,
    ) -> dict[str, Any]:
        """添加候选记忆。

        Args:
            content: 记忆内容。
            memory_type: 记忆类型。
            scope: 作用范围。
            source: 来源。
            source_run_id: 来源 run ID。
            project_id: 项目 ID。
            confidence: 置信度。
            tags: 标签列表。
            valid_until: 有效截止时间（None 表示长期）。

        Returns:
            创建的记忆记录字典。
        """
        now = time.time()
        if valid_until is None and memory_type in DEFAULT_TTL:
            ttl = DEFAULT_TTL[memory_type]
            if ttl is not None:
                valid_until = now + ttl

        memory = {
            "memory_id": _new_id(),
            "content": content,
            "memory_type": memory_type,
            "scope": scope,
            "project_id": project_id,
            "source": source,
            "source_run_id": source_run_id,
            "created_at": now,
            "updated_at": now,
            "valid_from": now,
            "valid_until": valid_until,
            "confidence": confidence,
            "source_quality": 0.5,
            "reuse_count": 0,
            "last_used_at": None,
            "confirmed_by_user": False,
            "conflict_count": 0,
            "superseded_by": None,
            "tags": tags or [],
            "risk_level": "low",
            "sensitive": False,
        }

        self._memories[memory["memory_id"]] = memory
        self._save_to_disk(memory)
        return memory

    def promote_to_semantic(
        self,
        memory_id: str,
        reviewer: str = "user",
    ) -> dict[str, Any] | None:
        """将记忆晋升为 semantic_memory。

        Args:
            memory_id: 记忆 ID。
            reviewer: 审核者。

        Returns:
            晋升后的记忆字典，不存在则返回 None。
        """
        memory = self._memories.get(memory_id)
        if memory is None:
            return None

        memory["memory_type"] = "semantic_memory"
        memory["confirmed_by_user"] = reviewer == "user"
        memory["confidence"] = min(1.0, memory["confidence"] + 0.2)
        memory["updated_at"] = time.time()
        memory["valid_until"] = None  # 长期有效
        self._save_to_disk(memory)
        return memory

    def mark_used(self, memory_id: str) -> dict[str, Any] | None:
        """标记记忆被使用（增加 reuse_count）。

        Args:
            memory_id: 记忆 ID。

        Returns:
            更新后的记忆字典。
        """
        memory = self._memories.get(memory_id)
        if memory is None:
            return None

        memory["reuse_count"] += 1
        memory["last_used_at"] = time.time()
        memory["updated_at"] = time.time()
        self._save_to_disk(memory)
        return memory

    def mark_conflict(
        self,
        memory_id: str,
        conflict_with: str,
    ) -> dict[str, Any] | None:
        """标记记忆冲突。

        Args:
            memory_id: 记忆 ID。
            conflict_with: 冲突的记忆 ID。

        Returns:
            更新后的记忆字典。
        """
        memory = self._memories.get(memory_id)
        if memory is None:
            return None

        memory["conflict_count"] += 1
        memory["updated_at"] = time.time()
        if "conflicts" not in memory:
            memory["conflicts"] = []
        memory["conflicts"].append(conflict_with)
        self._save_to_disk(memory)
        return memory

    def supersede(
        self,
        old_memory_id: str,
        new_memory_id: str,
    ) -> dict[str, Any] | None:
        """标记旧记忆被新记忆取代。

        Args:
            old_memory_id: 旧记忆 ID。
            new_memory_id: 新记忆 ID。

        Returns:
            旧记忆更新后的字典。
        """
        old = self._memories.get(old_memory_id)
        if old is None:
            return None

        old["superseded_by"] = new_memory_id
        old["updated_at"] = time.time()
        self._save_to_disk(old)
        return old

    def score_memory_value(self, memory: dict[str, Any]) -> float:
        """计算记忆价值分数。

        评分公式：
        value = reuse_count * 0.25
              + recency_score * 0.20
              + confidence * 0.20
              + user_confirmed_bonus * 0.20
              + source_quality * 0.10
              - conflict_penalty
              - stale_penalty
              - sensitive_penalty

        Args:
            memory: 记忆记录字典。

        Returns:
            价值分数（0~1）。
        """
        now = time.time()

        reuse_score = min(1.0, memory.get("reuse_count", 0) / 10.0)

        # recency: 24h 内=1, 7d=0.5, 30d=0.2, 更远=0.05
        age_hours = (now - memory.get("updated_at", now)) / 3600.0
        if age_hours <= 24:
            recency_score = 1.0
        elif age_hours <= 168:
            recency_score = 0.5
        elif age_hours <= 720:
            recency_score = 0.2
        else:
            recency_score = 0.05

        confidence = memory.get("confidence", 0.5)
        confirmed_bonus = 0.3 if memory.get("confirmed_by_user") else 0.0
        source_quality = memory.get("source_quality", 0.5)

        conflict_penalty = min(0.3, memory.get("conflict_count", 0) * 0.1)
        stale_penalty = 0.0
        valid_until = memory.get("valid_until")
        if valid_until and now > valid_until:
            stale_penalty = 0.2
        sensitive_penalty = 0.1 if memory.get("sensitive") else 0.0

        value = (
            reuse_score * 0.25
            + recency_score * 0.20
            + confidence * 0.20
            + confirmed_bonus * 0.20
            + source_quality * 0.10
            - conflict_penalty
            - stale_penalty
            - sensitive_penalty
        )
        return max(0.0, min(1.0, round(value, 4)))

    def suggest_prune(self, limit: int = 50) -> list[dict[str, Any]]:
        """建议修剪的记忆。

        按价值分数排序，返回低分记忆列表。

        Args:
            limit: 最大返回数量。

        Returns:
            建议修剪的记忆列表（value 低到高）。
        """
        scored = [
            {"memory_id": mid, "value": self.score_memory_value(m), "memory_type": m.get("memory_type")}
            for mid, m in self._memories.items()
            if m.get("superseded_by") is None
        ]
        scored.sort(key=lambda x: x["value"])
        return scored[:limit]

    def suggest_merge(self) -> list[dict[str, Any]]:
        """建议合并的记忆。

        检测内容相似的记忆（通过简单关键词重叠）。

        Returns:
            建议合并的记忆对列表。
        """
        suggestions: list[dict[str, Any]] = []
        memories = list(self._memories.values())
        seen_pairs: set[tuple[str, str]] = set()

        for i, m1 in enumerate(memories):
            if m1.get("superseded_by"):
                continue
            tokens1 = set(m1.get("content", "").lower().split())
            if len(tokens1) < 3:
                continue
            for j in range(i + 1, len(memories)):
                m2 = memories[j]
                if m2.get("superseded_by"):
                    continue
                pair = tuple(sorted([m1["memory_id"], m2["memory_id"]]))
                if pair in seen_pairs:
                    continue
                tokens2 = set(m2.get("content", "").lower().split())
                if not tokens2:
                    continue
                overlap = len(tokens1 & tokens2)
                union = len(tokens1 | tokens2)
                jaccard = overlap / union if union else 0
                if jaccard > 0.4:
                    seen_pairs.add(pair)
                    suggestions.append({
                        "memory_id_1": m1["memory_id"],
                        "memory_id_2": m2["memory_id"],
                        "similarity": round(jaccard, 3),
                        "content_1_preview": m1.get("content", "")[:60],
                        "content_2_preview": m2.get("content", "")[:60],
                    })
        return suggestions

    def suggest_review(self) -> list[dict[str, Any]]:
        """建议用户审核的记忆。

        返回高价值但未被用户确认的记忆。

        Returns:
            建议审核的记忆列表。
        """
        candidates = []
        for mid, m in self._memories.items():
            if m.get("superseded_by"):
                continue
            if m.get("confirmed_by_user"):
                continue
            if m.get("memory_type") in ("semantic_memory", "skill_rule"):
                candidates.append({
                    "memory_id": mid,
                    "content_preview": m.get("content", "")[:100],
                    "memory_type": m.get("memory_type"),
                    "confidence": m.get("confidence", 0.5),
                    "value": self.score_memory_value(m),
                })
        candidates.sort(key=lambda x: x["value"], reverse=True)
        return candidates

    def generate_memory_health_report(self) -> dict[str, Any]:
        """生成记忆健康报告。

        Returns:
            健康报告字典，JSON 可序列化。
        """
        now = time.time()
        active = {
            mid: m for mid, m in self._memories.items()
            if m.get("superseded_by") is None
        }

        suggest_keep: list[str] = []
        suggest_merge_list: list[dict] = []
        suggest_delete: list[str] = []
        suggest_review_list: list[dict] = []
        conflicts: list[dict] = []
        stale_items: list[str] = []
        high_value_items: list[str] = []

        for mid, m in active.items():
            value = self.score_memory_value(m)

            # 检查过期
            valid_until = m.get("valid_until")
            if valid_until and now > valid_until:
                stale_items.append(mid)
                suggest_delete.append(mid)
                continue

            # 检查冲突
            if m.get("conflict_count", 0) > 0:
                conflicts.append({
                    "memory_id": mid,
                    "conflict_count": m["conflict_count"],
                    "content_preview": m.get("content", "")[:60],
                })

            # 按价值分类
            if value >= 0.6:
                suggest_keep.append(mid)
                if value >= 0.8:
                    high_value_items.append(mid)
            elif value >= 0.3:
                if not m.get("confirmed_by_user"):
                    suggest_review_list.append({
                        "memory_id": mid,
                        "value": value,
                        "content_preview": m.get("content", "")[:60],
                    })
            else:
                suggest_delete.append(mid)

        # 合并建议
        suggest_merge_list = self.suggest_merge()

        total = len(self._memories)
        summary_zh = (
            f"本次检查 {total} 条记忆: "
            f"建议保留 {len(suggest_keep)} 条，"
            f"合并 {len(suggest_merge_list)} 对，"
            f"删除 {len(suggest_delete)} 条，"
            f"审核 {len(suggest_review_list)} 条。"
        )

        return {
            "total_memories": total,
            "active_memories": len(active),
            "suggest_keep": suggest_keep,
            "suggest_merge": suggest_merge_list,
            "suggest_delete": suggest_delete,
            "suggest_review": suggest_review_list,
            "conflicts": conflicts,
            "stale_items": stale_items,
            "high_value_items": high_value_items,
            "summary_zh": summary_zh,
        }

    def list_memories(
        self,
        memory_type: str | None = None,
        scope: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """列出记忆。

        Args:
            memory_type: 可选记忆类型过滤。
            scope: 可选作用范围过滤。
            limit: 最大返回数量。

        Returns:
            记忆列表。
        """
        results = []
        for m in self._memories.values():
            if m.get("superseded_by"):
                continue
            if memory_type and m.get("memory_type") != memory_type:
                continue
            if scope and m.get("scope") != scope:
                continue
            results.append(m)
            if len(results) >= limit:
                break
        return results

    def get_memory(self, memory_id: str) -> dict[str, Any] | None:
        """获取单条记忆。

        Args:
            memory_id: 记忆 ID。

        Returns:
            记忆字典或 None。
        """
        return self._memories.get(memory_id)

    def delete_memory(self, memory_id: str) -> bool:
        """删除记忆。

        Args:
            memory_id: 记忆 ID。

        Returns:
            True 表示删除成功。
        """
        if memory_id in self._memories:
            del self._memories[memory_id]
            self._delete_from_disk(memory_id)
            return True
        return False

    @property
    def count(self) -> int:
        """返回记忆总数。"""
        return len(self._memories)

    # ------------------------------------------------------------------
    # 磁盘持久化
    # ------------------------------------------------------------------

    def _get_db_path(self) -> Path:
        """获取 SQLite 数据库路径。"""
        return self.capsule_path / "memory" / "memories.sqlite"

    def _ensure_db(self) -> sqlite3.Connection:
        """确保 SQLite 数据库和表存在。"""
        import sqlite3

        db_path = self._get_db_path()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                memory_id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                memory_type TEXT,
                scope TEXT,
                created_at REAL,
                updated_at REAL
            )
        """)
        conn.commit()
        return conn

    def _save_to_disk(self, memory: dict[str, Any]) -> None:
        """保存单条记忆到 SQLite。"""
        import sqlite3

        try:
            conn = self._ensure_db()
            conn.execute(
                "INSERT OR REPLACE INTO memories (memory_id, data, memory_type, scope, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    memory["memory_id"],
                    json.dumps(memory, ensure_ascii=False),
                    memory.get("memory_type"),
                    memory.get("scope"),
                    memory.get("created_at"),
                    memory.get("updated_at"),
                ),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.debug("memory save to disk failed: %s", exc)

    def _load_from_disk(self) -> None:
        """从 SQLite 加载所有记忆到内存。"""
        import sqlite3

        db_path = self._get_db_path()
        if not db_path.exists():
            return

        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute("SELECT data FROM memories")
            for row in cursor:
                try:
                    memory = json.loads(row[0])
                    self._memories[memory["memory_id"]] = memory
                except (json.JSONDecodeError, KeyError):
                    pass
            conn.close()
        except Exception as exc:
            logger.debug("memory load from disk failed: %s", exc)

    def _delete_from_disk(self, memory_id: str) -> None:
        """从 SQLite 删除单条记忆。"""
        import sqlite3

        db_path = self._get_db_path()
        if not db_path.exists():
            return

        try:
            conn = sqlite3.connect(str(db_path))
            conn.execute("DELETE FROM memories WHERE memory_id = ?", (memory_id,))
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.debug("memory delete from disk failed: %s", exc)
