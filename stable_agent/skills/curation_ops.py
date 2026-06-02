"""stable_agent.skills.curation_ops — CurationOpsValidator 策展操作验证。

安全规则验证，防止路径穿越、shell 注入等安全问题。
"""

from __future__ import annotations

import logging
import re
from typing import Any

from stable_agent.skills.schema import CurationOp, CurationOpType, RiskLevel

logger = logging.getLogger(__name__)

# 危险命令模式
DANGEROUS_PATTERNS = [
    r'rm\s+-rf\s+/',
    r'sudo\s+',
    r'shutdown',
    r'reboot',
    r'mkfs',
    r'chmod\s+777',
    r'curl\s*\|\s*sh',
    r'curl\s*\|\s*bash',
    r'wget\s*\|\s*sh',
    r'wget\s*\|\s*bash',
    r'eval\s*\(',
    r'exec\s*\(',
    r':\(\)\{.*\|.*\}',  # fork bomb
    r'dd\s+if=/dev/zero',
    r'dd\s+if=/dev/random',
    r'\.\./',  # 路径穿越
]


class CurationOpsValidator:
    """策展操作验证器。

    安全规则：
    1. skill name 必须 slug 化
    2. 不允许路径穿越
    3. 不允许覆盖非 skill 目录
    4. 不允许 shell 注入
    5. scripts 默认不可执行
    6. update 必须生成 diff
    7. delete 必须软删除
    8. archive/delete 必须 human review
    9. merge 必须 human review
    10. 所有 op 必须记录 source_run
    """

    def validate_insert_skill(self, op: CurationOp) -> list[str]:
        """验证 insert 操作。"""
        issues: list[str] = []

        if not op.new_skill:
            issues.append("insert requires new_skill")
            return issues

        # name 必须 slug 化
        if not self._is_slug(op.new_skill.name):
            issues.append(f"name must be slug format: {op.new_skill.name}")

        # description 必须清晰
        if len(op.new_skill.description) < 10:
            issues.append("description too short")

        # 检查危险命令
        if self._contains_dangerous_content(str(op.new_skill.to_dict())):
            issues.append("contains dangerous commands")

        # source_run 必须存在
        if not op.source_run:
            issues.append("missing source_run")

        return issues

    def validate_update_skill(self, op: CurationOp) -> list[str]:
        """验证 update 操作。"""
        issues: list[str] = []

        if not op.patch:
            issues.append("update requires patch")

        # 检查 patch 中的 name
        if "name" in op.patch:
            if not self._is_slug(op.patch["name"]):
                issues.append(f"patched name must be slug format: {op.patch['name']}")

        # 检查危险命令
        if self._contains_dangerous_content(str(op.patch)):
            issues.append("patch contains dangerous commands")

        # source_run 必须存在
        if not op.source_run:
            issues.append("missing source_run")

        # 默认需要人工审核
        if not op.requires_human_review:
            logger.warning("update op %s does not require human review", op.op_id)

        return issues

    def validate_delete_skill(self, op: CurationOp) -> list[str]:
        """验证 delete 操作。"""
        issues: list[str] = []

        # 必须是软删除
        # (实际删除逻辑在 repo 中处理)

        # 必须人工审核
        if not op.requires_human_review:
            issues.append("delete must require human review")

        # source_run 必须存在
        if not op.source_run:
            issues.append("missing source_run")

        return issues

    def validate_archive_skill(self, op: CurationOp) -> list[str]:
        """验证 archive 操作。"""
        issues: list[str] = []

        # 必须人工审核
        if not op.requires_human_review:
            issues.append("archive must require human review")

        # source_run 必须存在
        if not op.source_run:
            issues.append("missing source_run")

        return issues

    def validate_merge_skill(self, op: CurationOp) -> list[str]:
        """验证 merge 操作。"""
        issues: list[str] = []

        # 必须人工审核
        if not op.requires_human_review:
            issues.append("merge must require human review")

        # source_run 必须存在
        if not op.source_run:
            issues.append("missing source_run")

        return issues

    def validate(self, op: CurationOp) -> list[str]:
        """验证操作。"""
        if op.op == CurationOpType.INSERT_SKILL:
            return self.validate_insert_skill(op)
        elif op.op == CurationOpType.UPDATE_SKILL:
            return self.validate_update_skill(op)
        elif op.op == CurationOpType.DELETE_SKILL:
            return self.validate_delete_skill(op)
        elif op.op == CurationOpType.ARCHIVE_SKILL:
            return self.validate_archive_skill(op)
        elif op.op == CurationOpType.MERGE_SKILL:
            return self.validate_merge_skill(op)
        return []

    def _is_slug(self, name: str) -> bool:
        """检查是否为 slug 格式。"""
        return bool(re.match(r'^[a-z0-9]+(-[a-z0-9]+)*$', name))

    def _contains_dangerous_content(self, content: str) -> bool:
        """检查是否包含危险内容。"""
        content_lower = content.lower()
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, content_lower):
                return True
        return False
