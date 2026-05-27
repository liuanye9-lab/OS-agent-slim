"""验证门（Validation Gate）。

用验证集测试候选 skill，只有变好才接受。核心规则：
- candidate_score > baseline_score 才通过
- 平分不通过（必须严格更好）
- 关键任务类型回归不通过
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from stable_agent.skill_optimizer.models import (
    SkillDocument,
    ValidationResult,
)

if TYPE_CHECKING:
    from stable_agent.evals.regression_suite import RegressionSuite
    from stable_agent.evals.rubric_judge import RubricJudge
    from stable_agent.evals.validation_dataset import ValidationDataset

logger = logging.getLogger(__name__)


class ValidationGate:
    """验证门：用验证集测试候选 skill，只有变好才接受。

    规则：
    - candidate_score > baseline_score 才通过
    - 平分不通过（score_delta <= 0 都不通过）
    - 关键任务类型回归不通过

    Attributes:
        rubric_judge: 评分准则评判器。
        regression_suite: 回归检测套件。
        validation_dataset: 验证数据集。
    """

    def __init__(
        self,
        rubric_judge: RubricJudge | None = None,
        regression_suite: RegressionSuite | None = None,
        validation_dataset: ValidationDataset | None = None,
    ) -> None:
        """注入评测组件。None 时自动创建默认实例。

        Args:
            rubric_judge: RubricJudge 实例，None 自动创建。
            regression_suite: RegressionSuite 实例，None 自动创建。
            validation_dataset: ValidationDataset 实例，None 自动创建。
        """
        # 延迟导入避免循环依赖
        if rubric_judge is None:
            from stable_agent.evals.rubric_judge import RubricJudge
            rubric_judge = RubricJudge()
        if regression_suite is None:
            from stable_agent.evals.regression_suite import RegressionSuite
            regression_suite = RegressionSuite()
        if validation_dataset is None:
            from stable_agent.evals.validation_dataset import ValidationDataset
            validation_dataset = ValidationDataset()

        self.rubric_judge: RubricJudge = rubric_judge
        self.regression_suite: RegressionSuite = regression_suite
        self.validation_dataset: ValidationDataset = validation_dataset

    # ------------------------------------------------------------------
    # 核心验证
    # ------------------------------------------------------------------

    def validate(
        self,
        baseline_skill: SkillDocument,
        candidate_skill: SkillDocument,
        validation_cases: list[dict] | None = None,
    ) -> ValidationResult:
        """核心验证方法。

        流程：
        1. 加载验证用例（未提供则从 ValidationDataset 加载）
        2. 用 baseline skill 对每条用例模拟执行，计算平均分
        3. 用 candidate skill 对每条用例模拟执行，计算平均分
        4. 检查回归
        5. 返回 ValidationResult

        Args:
            baseline_skill: 基线 SkillDocument（当前 BEST）。
            candidate_skill: 候选 SkillDocument。
            validation_cases: 验证用例列表，None 则自动加载。

        Returns:
            ValidationResult 实例。
        """
        # 步骤 1: 加载验证用例
        if validation_cases is None:
            validation_cases = self.validation_dataset.load_cases()

        if not validation_cases:
            logger.warning("验证数据集为空，无法执行验证")
            return ValidationResult(
                candidate_skill_version=candidate_skill.version,
                baseline_skill_version=baseline_skill.version,
                baseline_score=0.0,
                candidate_score=0.0,
                passed=False,
                score_delta=0.0,
                regression_cases=[],
                explanation="验证数据集为空，无法执行验证。",
            )

        # 步骤 2: baseline 评分
        baseline_scores = self._evaluate_skill(
            baseline_skill, validation_cases
        )
        baseline_avg = self._calculate_average_score(baseline_scores)

        # 步骤 3: candidate 评分
        candidate_scores = self._evaluate_skill(
            candidate_skill, validation_cases
        )
        candidate_avg = self._calculate_average_score(candidate_scores)

        # 步骤 4: 检查回归
        baseline_by_type = self._group_scores_by_type(
            validation_cases, baseline_scores
        )
        candidate_by_type = self._group_scores_by_type(
            validation_cases, candidate_scores
        )
        regression_cases = self.regression_suite.check_regression(
            baseline_by_type, candidate_by_type
        )

        # 步骤 5: 判断通过
        score_delta = candidate_avg - baseline_avg

        # 必须严格大于基线
        passed = score_delta > 0

        # 关键任务类型回归 → 不通过
        if passed and self.regression_suite.has_critical_regression(
            regression_cases
        ):
            passed = False
            logger.warning(
                "候选版本 %s 存在关键任务回归，验证不通过",
                candidate_skill.version,
            )

        # 生成解释
        if passed:
            explanation = (
                f"验证通过：候选得分 {candidate_avg:.4f} > "
                f"基线得分 {baseline_avg:.4f}，提升 {score_delta:.4f}。"
            )
        elif score_delta <= 0:
            explanation = (
                f"验证不通过：候选得分 {candidate_avg:.4f} <= "
                f"基线得分 {baseline_avg:.4f}（差值 {score_delta:.4f}）。"
                f"必须严格大于基线才通过。"
            )
        else:
            explanation = (
                f"验证不通过：候选得分 {candidate_avg:.4f} > "
                f"基线得分 {baseline_avg:.4f}，但存在关键任务回归: "
                f"{regression_cases}。"
            )

        return ValidationResult(
            candidate_skill_version=candidate_skill.version,
            baseline_skill_version=baseline_skill.version,
            baseline_score=round(baseline_avg, 4),
            candidate_score=round(candidate_avg, 4),
            passed=passed,
            score_delta=round(score_delta, 4),
            regression_cases=regression_cases,
            explanation=explanation,
        )

    # ------------------------------------------------------------------
    # 模拟执行
    # ------------------------------------------------------------------

    def _simulate_execution(
        self, task_input: str, skill_content: str
    ) -> str:
        """模拟执行：用 skill 指导生成模拟输出。

        基于 task_input 和 skill_content 的规则组合生成一个模拟响应。
        不是真正调用 LLM，而是根据 skill 中的规则 + task 关键词
        生成确定性输出。用于验证 gate 的快速判断。

        策略：
        1. 从 skill_content 中提取 Section 标题作为规则
        2. 根据 task_input 的关键词匹配规则
        3. 生成包含规则引用的模拟输出文本（约 200-500 字）

        Args:
            task_input: 用户任务输入。
            skill_content: skill 文档内容。

        Returns:
            模拟的模型输出文本。
        """
        # 提取 skill 中的 Section 标题作为"规则"
        section_rules = self._extract_section_rules(skill_content)

        # 从 task_input 提取关键词
        import re
        cleaned = re.sub(r"[^\w\u4e00-\u9fff\s]", " ", task_input)
        task_keywords = [
            w for w in cleaned.lower().split()
            if len(w) >= 2
        ][:8]

        # 匹配规则：检查哪些规则的关键词出现在 task 中
        matched_rules: list[str] = []
        for rule_title in section_rules:
            rule_lower = rule_title.lower()
            # 如果规则标题与任务关键词有交集
            if any(kw in rule_lower or rule_lower in kw
                   for kw in task_keywords):
                matched_rules.append(rule_title)

        # 如果没匹配，用前几条规则
        if not matched_rules:
            matched_rules = section_rules[:3]

        # 构建模拟输出
        output_parts: list[str] = []
        output_parts.append(f"# 关于: {task_input[:80]}...")
        output_parts.append("")

        for i, rule in enumerate(matched_rules[:4]):
            if "explain" in rule.lower() or "解释" in rule:
                output_parts.append(
                    f"## 解释\n根据「{rule}」规则，让我从第一性原理来解释..."
                )
            elif "code" in rule.lower() or "代码" in rule or "编程" in rule:
                output_parts.append(
                    f"## 代码实现\n遵循「{rule}」，以下是具体实现：\n```python\n"
                    f"def example():\n    # 基于 {rule}\n    pass\n```"
                )
            elif "structure" in rule.lower() or "结构" in rule:
                output_parts.append(
                    f"## 结构化方案\n按「{rule}」组织，以下是系统化的方案：\n"
                    f"1. 第一步：分析需求\n2. 第二步：设计方案\n"
                    f"3. 第三步：实施验证"
                )
            elif "prefer" in rule.lower() or "偏好" in rule or "风格" in rule:
                output_parts.append(
                    f"根据用户偏好「{rule}」，我将采用结构化、"
                    f"模块化的方式进行回复。"
                )
            else:
                output_parts.append(
                    f"## {rule}\n"
                    f"根据 skill 中的规则「{rule}」，以下是相关指导：\n"
                    f"- 要点一：遵循{rule}的核心原则\n"
                    f"- 要点二：保持模块化和可维护\n"
                )

        # 确保总字数在 200-500 之间
        result = "\n\n".join(output_parts)
        if len(result) < 200:
            result += (
                "\n\n## 补充说明\n"
                "以上方案已覆盖核心要点，如果需要更详细的解释，"
                "请告知具体关注的方面。"
            )

        return result[:800]  # 截断防止过长

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    @staticmethod
    def _calculate_average_score(scores: list[dict]) -> float:
        """计算加权平均分。

        Args:
            scores: judge() 返回的评分字典列表。

        Returns:
            平均综合得分（0.0~1.0）。
        """
        if not scores:
            return 0.0

        total = sum(s.get("overall", 0.0) for s in scores)
        return round(total / len(scores), 4)

    def _evaluate_skill(
        self,
        skill: SkillDocument,
        cases: list[dict],
    ) -> list[dict]:
        """对 skill 在所有用例上进行评估。

        对每条用例：
        1. 用 _simulate_execution 生成模拟输出
        2. 用 rubric_judge.judge() 评分

        Args:
            skill: 要评估的 SkillDocument。
            cases: 验证用例列表。

        Returns:
            每条用例的评分结果列表。
        """
        results: list[dict] = []
        for case in cases:
            task_input = case.get("task_input", "")
            expected_intent = case.get("expected_intent", "")
            rubric = case.get("rubric")

            # 模拟执行
            simulated_output = self._simulate_execution(
                task_input, skill.content
            )

            # 评分
            score = self.rubric_judge.judge(
                task_input=task_input,
                model_output=simulated_output,
                expected_intent=expected_intent,
                rubric=rubric,
            )
            results.append(score)

        return results

    @staticmethod
    def _extract_section_rules(content: str) -> list[str]:
        """从 skill 内容中提取 Section 标题作为规则。

        提取所有 ## 和 ### 标题行（去除标记符号）。

        Args:
            content: skill 文档内容。

        Returns:
            Section 标题列表。
        """
        import re
        rules: list[str] = []
        # 匹配 ## Section Title 或 ### Subsection Title
        pattern = re.compile(r"^#{2,3}\s+(.+)$", re.MULTILINE)
        for match in pattern.finditer(content):
            title = match.group(1).strip()
            if title and len(title) > 2:
                rules.append(title)
        return rules

    @staticmethod
    def _group_scores_by_type(
        cases: list[dict],
        scores: list[dict],
    ) -> dict[str, float]:
        """按任务类型分组计算平均分。

        从用例 id 的前缀推断类型：case_001~002→implementation,
        case_003→diagnosis, case_006→learning, case_005→design。

        实际使用 case id 中编码的类型信息，如果没有则统一归为 "general"。

        Args:
            cases: 验证用例列表。
            scores: 对应的评分结果列表。

        Returns:
            {type_name: average_score} 映射。
        """
        # 用例 id 到任务类型的映射（基于内置用例的场景）
        type_map: dict[str, str] = {
            "case_001": "implementation",  # Codex 代码生成
            "case_003": "diagnosis",       # Bug 诊断
            "case_005": "design",          # 架构设计
            "case_006": "learning",        # 学习入门
            "case_007": "implementation",  # MCP 接入/代码
            "case_009": "design",          # 项目开发/设计
            "case_010": "implementation",  # 代码审查
        }

        type_scores: dict[str, list[float]] = {}

        for i, case in enumerate(cases):
            if i >= len(scores):
                break
            case_id = case.get("id", "")
            task_type = type_map.get(case_id, "general")
            overall = scores[i].get("overall", 0.0)

            if task_type not in type_scores:
                type_scores[task_type] = []
            type_scores[task_type].append(overall)

        # 计算每类平均分
        result: dict[str, float] = {}
        for task_type, score_list in type_scores.items():
            result[task_type] = round(
                sum(score_list) / len(score_list), 4
            )

        return result
