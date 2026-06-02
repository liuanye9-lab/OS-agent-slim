"""stable_agent/skills/repository.py — SkillRepository。

文件 + SQLite 双层 Skill 存储。
支持完整生命周期管理。
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from stable_agent.skills.models import (
    SkillRecord, SkillStatus, PromotionLogEntry,
    VALID_TRANSITIONS,
)
from stable_agent.skills.markdown import parse_skill_markdown, render_skill_markdown
from stable_agent.skills.index_store import SkillIndexStore

logger = logging.getLogger(__name__)


class SkillRepository:
    """Skill 仓库。

    文件 + SQLite 双层存储。
    - 文件层: .skills/skills/ 目录下的 markdown 文件
    - 索引层: .skills/index.sqlite
    """

    def __init__(self, base_path: str | Path | None = None):
        """初始化 SkillRepository。

        Args:
            base_path: .skills 目录路径。默认为当前工作目录下的 .skills。
        """
        if base_path is None:
            base_path = Path.cwd() / ".skills"
        self._base_path = Path(base_path)
        self._skills_dir = self._base_path / "skills"
        self._candidates_dir = self._base_path / "candidates"
        self._validation_dir = self._base_path / "validation"

        # 确保目录存在
        self._skills_dir.mkdir(parents=True, exist_ok=True)
        self._candidates_dir.mkdir(parents=True, exist_ok=True)
        self._validation_dir.mkdir(parents=True, exist_ok=True)

        # SQLite 索引
        db_path = self._base_path / "index.sqlite"
        self._index = SkillIndexStore(str(db_path))

    def create_candidate(
        self,
        skill_id: str,
        proposed_rule: str,
        when_to_use: str = "",
        do_not_use_when: str = "",
        validation_plan: str = "",
        domain: str = "general",
        risk_level: str = "low",
        source_run_id: str = "",
        retrieval_tags: list[str] | None = None,
    ) -> SkillRecord:
        """创建 skill candidate。

        Args:
            skill_id: 技能 ID。
            proposed_rule: 建议规则。
            when_to_use: 使用场景。
            do_not_use_when: 不使用场景。
            validation_plan: 验证计划。
            domain: 领域。
            risk_level: 风险等级。
            source_run_id: 来源运行 ID。
            retrieval_tags: 检索标签。

        Returns:
            创建的 SkillRecord。
        """
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        record = SkillRecord(
            skill_id=skill_id,
            version=1,
            status=SkillStatus.CANDIDATE,
            domain=domain,
            owner="curator_v1",
            created_at=now,
            updated_at=now,
            retrieval_tags=retrieval_tags or [],
            risk_level=risk_level,
            source_runs=[source_run_id] if source_run_id else [],
            intent=proposed_rule,
            procedure=when_to_use,
            guardrails=do_not_use_when,
            positive_examples="",
            negative_examples="",
            patch_history="",
        )

        # 写入文件
        file_path = self._candidates_dir / f"{skill_id}.md"
        content = render_skill_markdown(record)
        file_path.write_text(content, encoding="utf-8")
        record.path = str(file_path)

        # 写入索引
        self._index.upsert_skill(record)

        # 写入晋升日志
        self._append_promotion_log(skill_id, "", "candidate", "created by curator")

        logger.info("Created candidate skill: %s", skill_id)
        return record

    def list_skills(self, status: str | None = None) -> list[SkillRecord]:
        """列出 skills。

        Args:
            status: 过滤状态 (可选)。

        Returns:
            SkillRecord 列表。
        """
        if status:
            try:
                status_enum = SkillStatus(status)
            except ValueError:
                return []
            rows = self._index.list_by_status(status_enum.value)
        else:
            rows = self._index.list_all()

        records = []
        for row in rows:
            record = self._row_to_record(row)
            if record and os.path.exists(record.path):
                records.append(record)
        return records

    def get_skill(self, skill_id: str) -> SkillRecord | None:
        """获取 skill。

        Args:
            skill_id: 技能 ID。

        Returns:
            SkillRecord 或 None。
        """
        row = self._index.get_skill(skill_id)
        if not row:
            return None
        record = self._row_to_record(row)
        if record and os.path.exists(record.path):
            return record
        return None

    def update_skill(self, skill_id: str, patch: dict[str, Any]) -> SkillRecord | None:
        """更新 skill。

        Args:
            skill_id: 技能 ID。
            patch: 更新字段。

        Returns:
            更新后的 SkillRecord 或 None。
        """
        record = self.get_skill(skill_id)
        if not record:
            return None

        # 应用 patch
        for key, value in patch.items():
            if hasattr(record, key):
                setattr(record, key, value)

        record.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # 写入文件
        content = render_skill_markdown(record)
        Path(record.path).write_text(content, encoding="utf-8")

        # 更新索引
        self._index.upsert_skill(record)

        return record

    def validate_skill(self, skill_id: str, validation_record: dict[str, Any]) -> bool:
        """记录 skill 验证结果。

        Args:
            skill_id: 技能 ID。
            validation_record: 验证记录。

        Returns:
            是否成功。
        """
        record = self.get_skill(skill_id)
        if not record:
            return False

        # 更新 metrics
        record.metrics["validations"] = record.metrics.get("validations", 0) + 1
        record.metrics["last_validation_score"] = validation_record.get("score_delta", 0.0)
        record.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # 写入验证记录
        validation_path = self._validation_dir / f"{skill_id}_v{record.metrics['validations']}.json"
        validation_path.write_text(json.dumps(validation_record, indent=2), encoding="utf-8")

        # 更新文件和索引
        content = render_skill_markdown(record)
        Path(record.path).write_text(content, encoding="utf-8")
        self._index.upsert_skill(record)

        return True

    def promote_skill(self, skill_id: str, reason: str = "") -> bool:
        """晋升 skill。

        Args:
            skill_id: 技能 ID。
            reason: 晋升原因。

        Returns:
            是否成功。
        """
        record = self.get_skill(skill_id)
        if not record:
            return False

        # 检查状态转换是否合法
        if SkillStatus.PROMOTED not in VALID_TRANSITIONS.get(record.status, set()):
            logger.warning("Cannot promote skill %s from status %s", skill_id, record.status)
            return False

        old_status = record.status
        record.status = SkillStatus.PROMOTED
        record.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # 移动到 skills 目录
        old_path = Path(record.path)
        new_path = self._skills_dir / f"{skill_id}.md"
        if old_path != new_path:
            content = render_skill_markdown(record)
            new_path.write_text(content, encoding="utf-8")
            if old_path.exists():
                old_path.unlink()
            record.path = str(new_path)

        # 更新索引
        self._index.upsert_skill(record)

        # 写入晋升日志
        self._append_promotion_log(skill_id, old_status.value, "promoted", reason)

        logger.info("Promoted skill %s: %s → promoted", skill_id, old_status.value)
        return True

    def deprecate_skill(self, skill_id: str, reason: str = "") -> bool:
        """废弃 skill。

        Args:
            skill_id: 技能 ID。
            reason: 废弃原因。

        Returns:
            是否成功。
        """
        record = self.get_skill(skill_id)
        if not record:
            return False

        if SkillStatus.DEPRECATED not in VALID_TRANSITIONS.get(record.status, set()):
            logger.warning("Cannot deprecate skill %s from status %s", skill_id, record.status)
            return False

        old_status = record.status
        record.status = SkillStatus.DEPRECATED
        record.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # 更新文件和索引
        content = render_skill_markdown(record)
        Path(record.path).write_text(content, encoding="utf-8")
        self._index.upsert_skill(record)

        # 写入晋升日志
        self._append_promotion_log(skill_id, old_status.value, "deprecated", reason)

        logger.info("Deprecated skill %s: %s → deprecated", skill_id, old_status.value)
        return True

    def retrieve_for_task(
        self,
        task_input: str,
        task_type: str | None = None,
        limit: int = 5,
    ) -> list[SkillRecord]:
        """为任务检索相关 skills。

        只检索 promoted skills (默认检索策略)。

        Args:
            task_input: 任务输入。
            task_type: 任务类型 (可选)。
            limit: 最大返回数量。

        Returns:
            相关 SkillRecord 列表。
        """
        # 简单的关键词匹配 (第一版)
        promoted = self.list_skills(status=SkillStatus.PROMOTED.value)

        if not promoted:
            return []

        # 简单评分
        scored = []
        for record in promoted:
            score = self._compute_relevance(record, task_input, task_type)
            if score > 0:
                scored.append((score, record))

        # 按分数排序
        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored[:limit]]

    def export_best_skill(self, path: str = "best_skill.md") -> str:
        """导出最佳 skills 汇总。

        只导出 promoted skills。
        dry_run_learning=true 时不允许导出。

        Args:
            path: 导出路径。

        Returns:
            导出文件路径。
        """
        promoted = self.list_skills(status=SkillStatus.PROMOTED.value)

        lines = [
            "# Best Skills (Auto-Generated)",
            "",
            f"Generated at: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
            f"Total promoted skills: {len(promoted)}",
            "",
        ]

        for record in promoted:
            lines.append(f"## {record.skill_id}")
            lines.append(f"- Domain: {record.domain}")
            lines.append(f"- Risk: {record.risk_level}")
            lines.append(f"- Intent: {record.intent[:200]}")
            lines.append("")

        content = '\n'.join(lines)
        export_path = Path(path)
        export_path.write_text(content, encoding="utf-8")

        logger.info("Exported best_skill.md with %d promoted skills", len(promoted))
        return str(export_path)

    # ── 内部方法 ──────────────────────────────────────────────

    def _row_to_record(self, row: dict[str, Any]) -> SkillRecord | None:
        """将数据库行转换为 SkillRecord。"""
        try:
            return SkillRecord(
                skill_id=row["skill_id"],
                version=row.get("version", 1),
                status=SkillStatus(row.get("status", "draft")),
                domain=row.get("domain", "general"),
                owner=row.get("owner", ""),
                created_at=row.get("created_at", ""),
                updated_at=row.get("updated_at", ""),
                risk_level=row.get("risk_level", "low"),
                path=row.get("path", ""),
                metrics={
                    "validations": row.get("validations", 0),
                    "win_rate": row.get("win_rate", 0.0),
                    "avg_token_delta": row.get("avg_token_delta", 0.0),
                    "avg_latency_delta": row.get("avg_latency_delta", 0.0),
                    "last_validation_score": row.get("last_validation_score", 0.0),
                },
            )
        except Exception:
            return None

    def _compute_relevance(self, record: SkillRecord, task_input: str, task_type: str | None) -> float:
        """计算 skill 与任务的相关性。"""
        score = 0.0
        task_lower = task_input.lower()

        # 检索标签匹配
        for tag in record.retrieval_tags:
            if tag.lower() in task_lower:
                score += 0.3

        # 领域匹配
        if record.domain and record.domain.lower() in task_lower:
            score += 0.2

        # 任务类型匹配
        if task_type and task_type in record.task_types:
            score += 0.3

        # Intent 匹配
        if record.intent and any(word in task_lower for word in record.intent.lower().split()[:5]):
            score += 0.2

        return min(1.0, score)

    def _append_promotion_log(self, skill_id: str, from_status: str, to_status: str, reason: str) -> None:
        """追加晋升日志。"""
        log_path = self._base_path / "promotion_log.jsonl"
        entry = {
            "id": f"log_{int(time.time() * 1000)}",
            "skill_id": skill_id,
            "from_status": from_status,
            "to_status": to_status,
            "reason": reason,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
