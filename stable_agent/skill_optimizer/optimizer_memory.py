"""优化器的自省记忆（OptimizerMemory）。

记录"什么类型的编辑容易有用，什么类型容易有害"。
仅在优化器内部使用，不注入用户任务上下文。
通过分析接受/拒绝的补丁来更新元技能文档。
"""

from __future__ import annotations

import logging
import os
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from stable_agent.skill_optimizer.models import SkillPatch

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# 默认元技能模板
_DEFAULT_META_SKILL_TEMPLATE: str = """# Optimizer Meta-Skill

## 编辑策略元知识

本文档记录优化器自身的编辑策略经验，由 OptimizerMemory 自动更新。
不要手动修改此文档。

### 通过率统计

暂无数据。

### 高效编辑模式

暂无数据。

### 应避免的编辑模式

暂无数据。
"""


class OptimizerMemory:
    """优化器的自省记忆。

    记录编辑策略元知识——什么类型的编辑容易有用，什么类型容易有害。
    仅在优化器内部使用，不注入用户任务上下文。

    Attributes:
        meta_skill_path: 元技能文档的存储路径。
    """

    def __init__(
        self, meta_skill_path: str = "skills/optimizer_meta_skill.md"
    ) -> None:
        """初始化 OptimizerMemory。

        自动创建文件所在目录。如果元技能文档不存在，创建默认空模板。

        Args:
            meta_skill_path: 元技能文档的路径。
        """
        self.meta_skill_path: str = meta_skill_path
        # 确保目录存在
        parent_dir = os.path.dirname(self.meta_skill_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)

        # 如果文件不存在，写入默认模板
        if not os.path.exists(self.meta_skill_path):
            self._write_default_meta_skill()

    # ------------------------------------------------------------------
    # 加载
    # ------------------------------------------------------------------

    def load_meta_skill(self) -> str:
        """加载元技能文档。

        如果文件不存在，返回默认空模板。

        Returns:
            元技能文档内容。
        """
        if not os.path.exists(self.meta_skill_path):
            return _DEFAULT_META_SKILL_TEMPLATE

        try:
            return Path(self.meta_skill_path).read_text(encoding="utf-8")
        except Exception as e:
            logger.error("加载元技能文档失败: %s", e)
            return _DEFAULT_META_SKILL_TEMPLATE

    # ------------------------------------------------------------------
    # 更新
    # ------------------------------------------------------------------

    def update_meta_skill(
        self,
        accepted_patches: list[SkillPatch],
        rejected_patches: list[SkillPatch],
    ) -> str:
        """根据接受/拒绝的补丁更新元技能。

        分析：
        - 哪种 source_type 的 edit 通过率高？
        - 哪种 risk_level 的 edit 通过率高？
        - 哪种 op 类型最常被接受？

        Args:
            accepted_patches: 被接受的 SkillPatch 列表。
            rejected_patches: 被拒绝的 SkillPatch 列表。

        Returns:
            更新后的元技能内容。
        """
        # 收集所有编辑
        accepted_edits = [
            e for p in accepted_patches for e in p.edits
        ]
        rejected_edits = [
            e for p in rejected_patches for e in p.edits
        ]

        # 分析
        source_stats = self._analyze_source_type(accepted_edits, rejected_edits)
        risk_stats = self._analyze_risk_level(accepted_edits, rejected_edits)
        op_stats = self._analyze_op_type(accepted_edits, rejected_edits)
        top_patterns = self._extract_top_patterns(
            accepted_edits, rejected_edits, top_n=3
        )

        # 构建新文档
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        content = f"""# Optimizer Meta-Skill

## 编辑策略元知识

本文档记录优化器自身的编辑策略经验，由 OptimizerMemory 自动更新。
最后更新: {now_str}
不要手动修改此文档。

### 通过率统计

- 总接受编辑: {len(accepted_edits)}
- 总拒绝编辑: {len(rejected_edits)}
- 总体通过率: {self._format_rate(accepted_edits, rejected_edits)}

#### 按来源类型

{source_stats}

#### 按风险等级

{risk_stats}

#### 按操作类型

{op_stats}

### 高效编辑模式

{top_patterns if top_patterns else '暂无数据。'}

### 应避免的编辑模式

{self._format_avoid_patterns(rejected_edits)}
"""

        # 写入文件
        try:
            Path(self.meta_skill_path).write_text(content, encoding="utf-8")
            logger.info("元技能文档已更新: %s", self.meta_skill_path)
        except Exception as e:
            logger.error("写入元技能文档失败: %s", e)

        return content

    # ------------------------------------------------------------------
    # 内部分析
    # ------------------------------------------------------------------

    @staticmethod
    def _analyze_source_type(
        accepted_edits: list,
        rejected_edits: list,
    ) -> str:
        """按 source_type 分析通过率。

        Args:
            accepted_edits: 被接受的编辑列表。
            rejected_edits: 被拒绝的编辑列表。

        Returns:
            格式化的 Markdown 统计文本。
        """
        sources = set()
        for e in accepted_edits + rejected_edits:
            sources.add(e.source_type)

        lines: list[str] = []
        for src in sorted(sources):
            a_count = sum(1 for e in accepted_edits if e.source_type == src)
            r_count = sum(1 for e in rejected_edits if e.source_type == src)
            total = a_count + r_count
            rate = f"{a_count / total * 100:.1f}%" if total > 0 else "N/A"
            lines.append(f"- {src}: {a_count}/{total} 通过 ({rate})")

        return "\n".join(lines) if lines else "暂无数据。"

    @staticmethod
    def _analyze_risk_level(
        accepted_edits: list,
        rejected_edits: list,
    ) -> str:
        """按 risk_level 分析通过率。

        Args:
            accepted_edits: 被接受的编辑列表。
            rejected_edits: 被拒绝的编辑列表。

        Returns:
            格式化的 Markdown 统计文本。
        """
        risks = set()
        for e in accepted_edits + rejected_edits:
            risks.add(e.risk_level)

        lines: list[str] = []
        for risk in sorted(risks):
            a_count = sum(1 for e in accepted_edits if e.risk_level == risk)
            r_count = sum(1 for e in rejected_edits if e.risk_level == risk)
            total = a_count + r_count
            rate = f"{a_count / total * 100:.1f}%" if total > 0 else "N/A"
            lines.append(f"- {risk}: {a_count}/{total} 通过 ({rate})")

        return "\n".join(lines) if lines else "暂无数据。"

    @staticmethod
    def _analyze_op_type(
        accepted_edits: list,
        rejected_edits: list,
    ) -> str:
        """按 op 类型分析通过率。

        Args:
            accepted_edits: 被接受的编辑列表。
            rejected_edits: 被拒绝的编辑列表。

        Returns:
            格式化的 Markdown 统计文本。
        """
        ops = set()
        for e in accepted_edits + rejected_edits:
            ops.add(e.op)

        lines: list[str] = []
        for op in sorted(ops):
            a_count = sum(1 for e in accepted_edits if e.op == op)
            r_count = sum(1 for e in rejected_edits if e.op == op)
            total = a_count + r_count
            rate = f"{a_count / total * 100:.1f}%" if total > 0 else "N/A"
            lines.append(f"- {op}: {a_count}/{total} 通过 ({rate})")

        return "\n".join(lines) if lines else "暂无数据。"

    @staticmethod
    def _extract_top_patterns(
        accepted_edits: list,
        rejected_edits: list,
        top_n: int = 3,
    ) -> str:
        """从接受编辑中提取高效模式。

        取 reason 中最常出现的关键词组合。

        Args:
            accepted_edits: 被接受的编辑列表。
            rejected_edits: 被拒绝的编辑列表。
            top_n: 返回的模式数。

        Returns:
            格式化的模式描述。
        """
        if not accepted_edits:
            return "暂无数据。"

        # 统计 accepted 中 reason 的常见词汇
        reason_words: Counter = Counter()
        import re
        for e in accepted_edits:
            words = re.findall(r"[\w\u4e00-\u9fff]{2,}", e.reason.lower())
            reason_words.update(words)

        # 获取 top 词汇
        top_words = reason_words.most_common(top_n * 3)

        lines: list[str] = []
        for word, count in top_words[:top_n]:
            if count >= 2:
                lines.append(
                    f"- 关键词「{word}」出现 {count} 次，"
                    f"相关编辑倾向于被接受。"
                )

        return "\n".join(lines) if lines else "暂无数据。"

    @staticmethod
    def _format_avoid_patterns(rejected_edits: list) -> str:
        """从拒绝编辑中提取应避免的模式。

        Args:
            rejected_edits: 被拒绝的编辑列表。

        Returns:
            格式化的避免建议。
        """
        if not rejected_edits:
            return "暂无数据。"

        # 统计 rejected 中的 source_type 分布
        source_counter = Counter(
            e.source_type for e in rejected_edits
        )
        risk_counter = Counter(
            e.risk_level for e in rejected_edits
        )
        op_counter = Counter(
            e.op for e in rejected_edits
        )

        lines: list[str] = []

        # 最常见被拒绝的 source_type
        if source_counter:
            top_source = source_counter.most_common(1)[0]
            lines.append(
                f"- {top_source[0]} 类型的编辑被拒绝 {top_source[1]} 次，"
                f"需检查此类信号的质量。"
            )

        # 最常见被拒绝的 risk_level
        if risk_counter:
            top_risk = risk_counter.most_common(1)[0]
            lines.append(
                f"- {top_risk[0]} 风险等级的编辑最常被拒绝（{top_risk[1]} 次）。"
            )

        # 最常见被拒绝的 op
        if op_counter:
            top_op = op_counter.most_common(1)[0]
            lines.append(
                f"- {top_op[0]} 操作最常被拒绝（{top_op[1]} 次）。"
            )

        return "\n".join(lines) if lines else "暂无数据。"

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    @staticmethod
    def _format_rate(accepted: list, rejected: list) -> str:
        """计算并格式化通过率。

        Args:
            accepted: 接受列表。
            rejected: 拒绝列表。

        Returns:
            格式化的通过率字符串。
        """
        total = len(accepted) + len(rejected)
        if total == 0:
            return "N/A"
        return f"{len(accepted) / total * 100:.1f}%"

    def _write_default_meta_skill(self) -> None:
        """写入默认元技能模板。"""
        try:
            Path(self.meta_skill_path).write_text(
                _DEFAULT_META_SKILL_TEMPLATE, encoding="utf-8"
            )
            logger.info("已创建默认元技能文档: %s", self.meta_skill_path)
        except Exception as e:
            logger.error("创建默认元技能文档失败: %s", e)
