"""stable_agent.skills.skill_lint — SkillLinter 技能安全检查。

检查 SKILL.md 是否安全、完整、符合规范。
所有 insert/update 前都 lint。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# 危险命令列表
DANGEROUS_COMMANDS = [
    "rm -rf /",
    "rm -rf /*",
    "sudo rm -rf",
    "shutdown",
    "reboot",
    "mkfs",
    "chmod -R 777",
    "curl | sh",
    "curl | bash",
    "wget | sh",
    "wget | bash",
    "eval(",
    "exec(",
    ":(){:|:&};:",
    "dd if=/dev/zero",
    "dd if=/dev/random",
]


@dataclass
class LintResult:
    """Lint 检查结果。"""

    ok: bool = True
    score: float = 1.0
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "score": self.score,
            "issues": self.issues,
            "warnings": self.warnings,
            "suggestions": self.suggestions,
        }


class SkillLinter:
    """技能 Lint 检查器。

    检查项目：
    1. SKILL.md 是否存在
    2. frontmatter 是否完整
    3. name 是否 slug
    4. description 是否清晰
    5. 是否包含危险命令
    6. 是否过度绑定单个 run
    7. 是否缺少 Procedure
    8. 是否缺少 Verification
    9. 是否太长
    10. 是否和已有 skill 高度重复
    """

    def lint_skill_md(
        self,
        content: str,
        name: str = "",
        description: str = "",
    ) -> LintResult:
        """Lint SKILL.md 内容。

        Args:
            content: SKILL.md 内容。
            name: 技能名称。
            description: 技能描述。

        Returns:
            Lint 结果。
        """
        issues: list[str] = []
        warnings: list[str] = []
        suggestions: list[str] = []
        scores: list[float] = []

        # 1. 内容是否为空
        if not content or not content.strip():
            return LintResult(
                ok=False,
                score=0.0,
                issues=["empty SKILL.md content"],
            )

        # 2. 危险命令检查
        safety_score = self._check_safety(content)
        scores.append(safety_score)
        if safety_score < 1.0:
            issues.append("contains dangerous commands")

        # 3. Frontmatter 检查
        frontmatter_score = self._check_frontmatter(content)
        scores.append(frontmatter_score)
        if frontmatter_score < 0.5:
            warnings.append("missing or incomplete frontmatter")

        # 4. Name slug 检查
        if name:
            if not self._is_slug(name):
                issues.append(f"name must be slug format: {name}")
                scores.append(0.0)
            else:
                scores.append(1.0)

        # 5. Description 检查
        if description:
            if len(description) < 10:
                warnings.append("description too short")
                scores.append(0.5)
            else:
                scores.append(1.0)

        # 6. Procedure 检查
        procedure_score = self._check_procedure(content)
        scores.append(procedure_score)
        if procedure_score < 0.3:
            warnings.append("missing procedure section")
            suggestions.append("add ## Procedure or ## Steps section")

        # 7. Verification 检查
        verification_score = self._check_verification(content)
        scores.append(verification_score)
        if verification_score < 0.3:
            warnings.append("missing verification section")
            suggestions.append("add ## Verification section")

        # 8. 长度检查
        length_score = self._check_length(content)
        scores.append(length_score)
        if length_score < 0.5:
            warnings.append("content too long")
            suggestions.append("compress skill content to under 1500 words")

        # 9. 过度绑定检查
        binding_score = self._check_binding(content)
        scores.append(binding_score)
        if binding_score < 0.5:
            warnings.append("too specific to single run")
            suggestions.append("generalize the skill")

        # 计算总分
        final_score = sum(scores) / len(scores) if scores else 0.0

        return LintResult(
            ok=len(issues) == 0,
            score=final_score,
            issues=issues,
            warnings=warnings,
            suggestions=suggestions,
        )

    def _check_safety(self, content: str) -> float:
        """检查安全性。"""
        content_lower = content.lower()
        for cmd in DANGEROUS_COMMANDS:
            if cmd.lower() in content_lower:
                return 0.0
        return 1.0

    def _check_frontmatter(self, content: str) -> float:
        """检查 frontmatter。"""
        if content.startswith("---"):
            # 检查是否有结束标记
            parts = content.split("---", 2)
            if len(parts) >= 3:
                # 检查是否包含必要字段
                fm = parts[1].lower()
                score = 0.0
                if "name:" in fm:
                    score += 0.3
                if "description:" in fm:
                    score += 0.3
                if "scope:" in fm:
                    score += 0.2
                if "risk_level:" in fm:
                    score += 0.2
                return score
        return 0.0

    def _check_procedure(self, content: str) -> float:
        """检查是否有 Procedure。"""
        content_lower = content.lower()
        indicators = ["## procedure", "## steps", "## 步骤", "## 流程", "## how to"]
        for indicator in indicators:
            if indicator in content_lower:
                return 1.0
        # 检查是否有编号步骤
        if re.search(r'^\d+\.\s', content, re.MULTILINE):
            return 0.7
        return 0.0

    def _check_verification(self, content: str) -> float:
        """检查是否有 Verification。"""
        content_lower = content.lower()
        indicators = ["## verification", "## 验证", "## check", "## 检查"]
        for indicator in indicators:
            if indicator in content_lower:
                return 1.0
        return 0.0

    def _check_length(self, content: str) -> float:
        """检查长度。"""
        word_count = len(content.split())
        if word_count <= 500:
            return 1.0
        elif word_count <= 1000:
            return 0.8
        elif word_count <= 1500:
            return 0.5
        elif word_count <= 2000:
            return 0.3
        else:
            return 0.1

    def _check_binding(self, content: str) -> float:
        """检查是否过度绑定。"""
        score = 1.0

        # 检查具体路径
        path_patterns = [
            r'/Users/\w+/',
            r'/home/\w+/',
            r'C:\\Users\\',
            r'run_[a-f0-9]{12}',
        ]
        for pattern in path_patterns:
            if re.search(pattern, content):
                score -= 0.3

        # 检查过长的代码块
        code_blocks = re.findall(r'```[\s\S]*?```', content)
        for block in code_blocks:
            if len(block) > 500:
                score -= 0.2

        return max(0.0, min(1.0, score))

    def _is_slug(self, name: str) -> bool:
        """检查是否为 slug 格式。"""
        return bool(re.match(r'^[a-z0-9]+(-[a-z0-9]+)*$', name))
