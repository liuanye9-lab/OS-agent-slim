"""语义解释器 (规则版)。

基于规则的 SemanticInterpreter，不依赖真实 LLM。
识别用户输入中的任务类型、保护约束、假设和不确定性。

用法::

    interpreter = SemanticInterpreter()
    trace = interpreter.interpret("继续优化这个项目", run_id="run_001")
"""

from __future__ import annotations

import re
from typing import Any

from stable_agent.understanding.schemas import (
    UnderstandingTrace,
    ExpressionProfile,
    TaskType,
    ExpressionScope,
)


class SemanticInterpreter:
    """语义解释器 (规则版)。

    基于规则识别用户输入的语义意图:
    - 任务类型分类
    - 保护性约束提取
    - 假设和不确定性识别
    - 表达习惯匹配
    - 置信度计算

    Attributes:
        expression_manager: 表达习惯管理器 (可选注入)。
    """

    def __init__(self, expression_manager: Any = None) -> None:
        """初始化语义解释器。

        Args:
            expression_manager: ExpressionProfileManager 实例 (可选)。
        """
        self._expression_manager = expression_manager

    def interpret(
        self,
        task_input: str,
        run_id: str = "",
        capsule_memory: list[dict] | None = None,
    ) -> UnderstandingTrace:
        """解析用户输入并生成 UnderstandingTrace。

        Args:
            task_input: 用户输入文本。
            run_id: 关联的运行 ID。
            capsule_memory: Capsule 记忆列表 (可选)。

        Returns:
            UnderstandingTrace 实例。
        """
        trace = UnderstandingTrace(
            run_id=run_id,
            user_original_input=task_input,
        )

        # 1. 识别任务类型
        trace.task_type = self._classify_task_type(task_input)

        # 2. 提取保护性约束
        trace.protected_constraints = self._extract_protected_constraints(task_input)

        # 3. 识别假设
        trace.assumptions = self._extract_assumptions(task_input)

        # 4. 识别不确定性
        trace.uncertainties = self._extract_uncertainties(task_input)

        # 5. 匹配表达习惯
        if self._expression_manager is not None:
            trace.expression_matches = self._match_expressions(task_input)

        # 6. 检测语义风险
        trace.semantic_risk_flags = self._detect_risk_flags(task_input)

        # 7. 计算置信度
        trace.confidence = self._compute_confidence(trace)

        # 8. 判断是否需要用户确认
        trace.needs_user_confirmation = self._needs_confirmation(trace)

        # 9. 生成解读目标
        trace.interpreted_goal = self._generate_goal(task_input, trace)

        return trace

    def _classify_task_type(self, text: str) -> str:
        """识别任务类型。"""
        text_lower = text.lower()

        # 调试类
        if any(kw in text_lower for kw in ["bug", "错误", "报错", "异常", "崩溃", "修复", "fix", "debug"]):
            return TaskType.DEBUGGING

        # 代码审查
        if any(kw in text_lower for kw in ["审查", "review", "代码审查", "检查代码"]):
            return TaskType.REVIEW

        # 重构
        if any(kw in text_lower for kw in ["重构", "refactor", "优化代码结构", "重写"]):
            return TaskType.REFACTOR

        # 设计
        if any(kw in text_lower for kw in ["设计", "design", "ui", "界面", "交互"]):
            return TaskType.DESIGN

        # 编码 (优先于产品，因为"实现功能"更偏向编码)
        if any(kw in text_lower for kw in ["实现", "编写", "代码", "code", "implement", "开发", "添加"]):
            return TaskType.CODING

        # 产品
        if any(kw in text_lower for kw in ["需求", "产品", "product", "功能", "feature", "用户故事"]):
            return TaskType.PRODUCT

        return TaskType.UNKNOWN

    def _extract_protected_constraints(self, text: str) -> list[str]:
        """提取保护性约束 — 用户明确要求不可违反的规则。"""
        constraints = []

        # "不要跑偏" / "别 AI 味" → 保持原有风格
        if re.search(r"不要跑偏|别.*ai.*味|不要.*ai|保持.*风格|保持.*原有", text, re.IGNORECASE):
            constraints.append("保持原有风格")

        # "只改相关文件" / "不要重构" → 最小变更
        if re.search(r"只改.*相关|不要.*重构|最小.*变更|不要.*动.*其他", text, re.IGNORECASE):
            constraints.append("最小变更")

        # "不要大范围重构" → 限制变更范围
        if re.search(r"不要.*大范围|不要.*大改|限制.*范围|不要.*大规模", text, re.IGNORECASE):
            constraints.append("限制变更范围")

        # "不要删除" / "保留" → 保留现有内容
        if re.search(r"不要.*删除|保留.*现有|不要.*删|保留.*不变", text, re.IGNORECASE):
            constraints.append("保留现有内容")

        # "兼容" / "向后兼容" → 保持兼容性
        if re.search(r"兼容|向后兼容|backward.*compat", text, re.IGNORECASE):
            constraints.append("保持兼容性")

        return constraints

    def _extract_assumptions(self, text: str) -> list[str]:
        """提取假设 — 系统需要理解但用户未明确说明的内容。"""
        assumptions = []

        # "继续优化" → 需要项目上下文
        if re.search(r"继续.*优化|继续.*改进|接着.*做", text, re.IGNORECASE):
            assumptions.append("假设需要项目上下文才能继续")

        # "这个项目" / "当前项目" → 指向当前工作目录
        if re.search(r"这个项目|当前项目|本项目|此项目", text, re.IGNORECASE):
            assumptions.append("假设指向当前工作目录中的项目")

        # "之前" / "上次" → 引用历史记忆
        if re.search(r"之前|上次|以前|上次的", text, re.IGNORECASE):
            assumptions.append("假设引用了历史交互记忆")

        # "测试" / "测试一下" → 需要运行测试
        if re.search(r"测试一下|跑.*测试|运行.*测试|test", text, re.IGNORECASE):
            assumptions.append("假设需要执行测试验证")

        return assumptions

    def _extract_uncertainties(self, text: str) -> list[str]:
        """识别不确定性 — 系统不确定用户意图的方面。"""
        uncertainties = []

        # 模糊指代
        if re.search(r"这个|那个|它|它们", text):
            uncertainties.append("存在模糊指代，可能需要澄清具体对象")

        # 缺少具体目标
        if len(text.strip()) < 10:
            uncertainties.append("输入较短，可能缺少具体目标描述")

        # 多义表达
        if re.search(r"优化|改进|提升|完善", text) and not re.search(r"具体|明确|详细", text):
            uncertainties.append("'优化'类表述可能有多种理解方向")

        return uncertainties

    def _match_expressions(self, text: str) -> list[dict]:
        """匹配已知表达习惯。"""
        if self._expression_manager is None:
            return []

        matches = self._expression_manager.match_expressions(text)
        return [m.to_dict() for m in matches]

    def _detect_risk_flags(self, text: str) -> list[str]:
        """检测语义风险标记。"""
        flags = []

        # "全部" / "所有" → 可能大范围变更
        if re.search(r"全部|所有|所有文件|整个项目", text, re.IGNORECASE):
            flags.append("potential_wide_scope_change")

        # "删除" / "移除" → 破坏性操作
        if re.search(r"删除|移除|删掉|remove|delete", text, re.IGNORECASE):
            flags.append("potential_destructive_operation")

        # "重写" / "推翻" → 大规模变更
        if re.search(r"重写|推翻|从头开始|推倒重来", text, re.IGNORECASE):
            flags.append("potential_major_rewrite")

        return flags

    def _compute_confidence(self, trace: UnderstandingTrace) -> float:
        """计算整体置信度。"""
        confidence = 0.7  # 基础置信度

        # 任务类型明确 → +0.1
        if trace.task_type != TaskType.UNKNOWN:
            confidence += 0.1

        # 有保护约束 → +0.1 (用户意图明确)
        if trace.protected_constraints:
            confidence += 0.1

        # 有不确定性 → -0.1 每个
        confidence -= len(trace.uncertainties) * 0.1

        # 有语义风险 → -0.05 每个
        confidence -= len(trace.semantic_risk_flags) * 0.05

        # 有表达习惯匹配 → +0.05
        if trace.expression_matches:
            confidence += 0.05

        return max(0.1, min(1.0, confidence))

    def _needs_confirmation(self, trace: UnderstandingTrace) -> bool:
        """判断是否需要用户确认。"""
        # 置信度过低
        if trace.confidence < 0.5:
            return True

        # 有不确定性
        if trace.uncertainties:
            return True

        # 有高风险标记
        if "potential_major_rewrite" in trace.semantic_risk_flags:
            return True

        return False

    def _generate_goal(self, text: str, trace: UnderstandingTrace) -> str:
        """生成解读目标。"""
        if trace.protected_constraints:
            constraints_str = "，".join(trace.protected_constraints)
            return f"在约束 [{constraints_str}] 下完成: {text}"
        return text
