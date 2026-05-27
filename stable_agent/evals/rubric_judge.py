"""开放性任务的评分准则评判器。

基于启发式规则对模型输出进行多维度评分。所有规则完全可解释，
不依赖随机性。用于 Validation Gate 中比较候选 skill 的质量。
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


class RubricJudge:
    """开放性任务的评分准则评判器。

    评分维度：
    - intent_understanding: 是否理解用户真实意图
    - actionability: 是否可直接执行
    - user_preference_match: 是否符合用户偏好
    - information_density: 信息密度是否合适
    - drift_risk: 跑偏程度（越低越好，但评分越高表示越不跑偏）
    - token_efficiency: token 使用效率

    所有规则均为启发式、确定性、完全可解释。不依赖 LLM 或随机性。

    Attributes:
        dimensions: 所有评分维度名称列表。
        default_weights: 默认各维度权重。
    """

    def __init__(self) -> None:
        """初始化评判器，设置维度和默认权重。"""
        self.dimensions: list[str] = [
            "intent_understanding",
            "actionability",
            "user_preference_match",
            "information_density",
            "drift_risk",
            "token_efficiency",
        ]
        self.default_weights: dict[str, float] = {
            "intent_understanding": 0.25,
            "actionability": 0.20,
            "user_preference_match": 0.20,
            "information_density": 0.15,
            "drift_risk": 0.10,
            "token_efficiency": 0.10,
        }

    # ------------------------------------------------------------------
    # 评判
    # ------------------------------------------------------------------

    def judge(
        self,
        task_input: str,
        model_output: str,
        expected_intent: str = "",
        rubric: dict | None = None,
    ) -> dict:
        """基于启发式规则评判模型输出。

        对 6 个维度分别评分，计算加权综合得分，并生成解释。

        Args:
            task_input: 用户任务输入。
            model_output: 模型/系统的输出响应。
            expected_intent: 期望的用户意图（用于 intent_understanding 评分）。
            rubric: 自定义评分权重，None 使用默认权重。

        Returns:
            {
                "dimension_scores": {dim_name: score, ...},
                "overall": float (0~1),
                "explanation": str,
            }
        """
        weights = rubric if rubric else self.default_weights

        # 逐维度评分
        intent_score = self._score_intent_understanding(
            task_input, model_output, expected_intent
        )
        action_score = self._score_actionability(model_output)
        preference_score = self._score_user_preference_match(model_output)
        density_score = self._score_information_density(task_input, model_output)
        drift_score = self._score_drift_risk(task_input, model_output)
        efficiency_score = self._score_token_efficiency(model_output)

        dimension_scores: dict[str, float] = {
            "intent_understanding": intent_score,
            "actionability": action_score,
            "user_preference_match": preference_score,
            "information_density": density_score,
            "drift_risk": drift_score,
            "token_efficiency": efficiency_score,
        }

        # 加权综合得分
        overall: float = 0.0
        for dim in self.dimensions:
            weight = weights.get(dim, self.default_weights[dim])
            overall += dimension_scores[dim] * weight

        overall = round(min(overall, 1.0), 4)

        # 生成解释
        explanation = self._generate_explanation(dimension_scores, overall)

        return {
            "dimension_scores": dimension_scores,
            "overall": overall,
            "explanation": explanation,
        }

    # ------------------------------------------------------------------
    # 各维度评分（公开，可单独调用）
    # ------------------------------------------------------------------

    def _score_intent_understanding(
        self, task_input: str, model_output: str, expected_intent: str
    ) -> float:
        """意图理解评分。

        检查 output 是否包含 expected_intent 中的关键词。
        每命中一个关键词 +0.25，最高 1.0。

        Args:
            task_input: 用户输入。
            model_output: 模型输出。
            expected_intent: 期望意图描述，从中提取关键词。

        Returns:
            0.0 ~ 1.0 的评分。
        """
        if not expected_intent:
            # 没有期望意图时，从 task_input 中提取关键词作为替代
            keywords = self._extract_keywords(task_input, max_keywords=4)
        else:
            keywords = self._extract_keywords(expected_intent, max_keywords=6)

        if not keywords:
            return 0.5  # 无法提取关键词时给中等分

        output_lower = model_output.lower()
        hits = sum(1 for kw in keywords if kw.lower() in output_lower)
        score = min(hits / max(len(keywords), 1), 1.0)
        return round(score, 4)

    @staticmethod
    def _score_actionability(model_output: str) -> float:
        """可执行性评分。

        检查 output 是否包含：
        - 代码块（```）→ +0.4
        - 步骤编号（1. 2. 步骤/Step）→ +0.3
        - 命令/配置示例 → +0.2
        - 具体文件名或路径 → +0.1

        Returns:
            0.0 ~ 1.0 的评分。
        """
        score: float = 0.0

        # 代码块
        if "```" in model_output:
            score += 0.4

        # 步骤编号
        step_patterns = [
            r"\d+[\.\)]\s",  # "1." or "1)"
            r"(Step|步骤)\s*\d+",  # "Step 1" or "步骤1"
        ]
        for pat in step_patterns:
            if re.search(pat, model_output, re.IGNORECASE):
                score += 0.3
                break

        # 命令或配置
        cmd_patterns = [
            r"\b(npm|pip|docker|git|curl|python|node)\s",
            r"\b(config|yaml|json|toml|env)\b",
        ]
        cmd_hits = sum(
            1 for pat in cmd_patterns
            if re.search(pat, model_output, re.IGNORECASE)
        )
        score += min(cmd_hits * 0.1, 0.2)

        # 文件路径
        if re.search(r"/[a-zA-Z0-9_/.-]+\.[a-z]{2,4}", model_output):
            score += 0.1

        return round(min(score, 1.0), 4)

    @staticmethod
    def _score_user_preference_match(model_output: str) -> float:
        """用户偏好匹配评分。

        检查：
        - 是否有结构化标题（## 或 ###）→ 结构化倾向 +0.3
        - 是否包含中文内容 → 中文默认 +0.2
        - 是否有具体示例而非泛泛而谈 → +0.2
        - 是否过于简短（< 50 字）→ 信息不足 -0.2
        - 是否有 "这是AI" "作为AI" 等机械语 → -0.3

        Returns:
            0.0 ~ 1.0 的评分。
        """
        base: float = 0.5

        # 结构化
        if re.search(r"#{2,4}\s", model_output):
            base += 0.3

        # 中文内容
        if re.search(r"[\u4e00-\u9fff]", model_output):
            base += 0.2

        # 具体示例
        example_indicators = ["例如", "比如", "示例", "example", "e.g.", "例如："]
        if any(ind in model_output.lower() for ind in example_indicators):
            base += 0.2

        # 过于简短
        if len(model_output) < 50:
            base -= 0.2

        # 机械语
        mechanical_phrases = [
            "这是AI生成的", "作为一个AI", "作为AI", "这是由AI",
            "I am an AI", "As an AI",
        ]
        if any(phrase in model_output for phrase in mechanical_phrases):
            base -= 0.3

        return round(max(min(base, 1.0), 0.0), 4)

    @staticmethod
    def _score_information_density(task_input: str, model_output: str) -> float:
        """信息密度评分。

        理想的信息密度：output_len / input_len 在 0.8 ~ 3.0 之间。
        - 比率在 0.8~3.0 → 1.0
        - 比率 < 0.8 → 线性递减到 0.0（比率 0 时）
        - 比率 > 3.0 → 信息过多，递减

        Args:
            task_input: 用户输入。
            model_output: 模型输出。

        Returns:
            0.0 ~ 1.0 的评分。
        """
        input_len = len(task_input)
        output_len = len(model_output)

        if input_len == 0:
            return 0.5

        ratio = output_len / input_len

        if 0.8 <= ratio <= 3.0:
            return 1.0
        elif ratio < 0.8:
            # 线性从 0.8→1.0 降到 0→0.0
            return round(ratio / 0.8, 4)
        else:
            # ratio > 3.0，线性递减，ratio=6.0 时降到 0
            return round(max(0.0, 1.0 - (ratio - 3.0) / 3.0), 4)

    @staticmethod
    def _score_drift_risk(task_input: str, model_output: str) -> float:
        """跑偏风险评分（1.0 表示完全不跑偏）。

        检查 output 是否与 input 话题偏离：
        - 从 input 提取关键词
        - 检查 output 中关键词覆盖率
        - 覆盖率 > 50% → 1.0，否则按比例递减

        Args:
            task_input: 用户输入。
            model_output: 模型输出。

        Returns:
            0.0 ~ 1.0 的评分（越高越不跑偏）。
        """
        # 从 input 提取关键词
        input_keywords = RubricJudge._extract_keywords(
            task_input, max_keywords=6
        )
        if not input_keywords:
            return 0.5

        output_lower = model_output.lower()
        hits = sum(
            1 for kw in input_keywords if kw.lower() in output_lower
        )
        coverage = hits / len(input_keywords)

        if coverage >= 0.5:
            return 1.0
        else:
            return round(coverage / 0.5, 4)

    @staticmethod
    def _score_token_efficiency(model_output: str) -> float:
        """Token 使用效率评分。

        输出长度在 200~2000 字符之间视为高效。
        - < 50 字符：信息不足 → 0.4
        - 50~200 字符：较短但可能足够 → 0.7
        - 200~2000 字符：理想范围 → 1.0
        - 2000~4000 字符：稍长 → 0.7
        - > 4000 字符：过长 → 0.3

        Returns:
            0.0 ~ 1.0 的评分。
        """
        output_len = len(model_output)

        if output_len < 50:
            return 0.4
        elif output_len < 200:
            return 0.7
        elif output_len <= 2000:
            return 1.0
        elif output_len <= 4000:
            return 0.7
        else:
            return 0.3

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_keywords(text: str, max_keywords: int = 6) -> list[str]:
        """从文本中提取关键词。

        使用简单的分词和停用词过滤。

        Args:
            text: 输入文本。
            max_keywords: 最大关键词数。

        Returns:
            关键词列表（按长度降序，优先保留长词）。
        """
        # 移除标点
        cleaned = re.sub(r"[^\w\u4e00-\u9fff\s]", " ", text)

        # 停用词
        stopwords = {
            "的", "是", "在", "了", "和", "也", "就", "都", "而",
            "及", "与", "着", "或", "一个", "没有", "我们", "你们",
            "他们", "它们", "这个", "那个", "这些", "那些", "自己",
            "什么", "哪", "怎么", "如何", "为什么", "因为", "所以",
            "但是", "然而", "可以", "可能", "应该", "需要", "已经",
            "the", "a", "an", "is", "are", "was", "were", "be",
            "been", "being", "have", "has", "had", "do", "does",
            "did", "will", "would", "could", "should", "may",
            "might", "can", "shall", "to", "of", "in", "for",
            "on", "with", "at", "by", "from", "as", "into",
            "through", "during", "before", "after", "above",
            "below", "between", "under", "and", "but", "or",
            "nor", "not", "so", "yet", "both", "either", "neither",
            "each", "every", "all", "any", "few", "more", "most",
            "other", "some", "such", "no", "only", "own", "same",
            "than", "too", "very", "just", "about", "up", "out",
            "if", "then", "now", "here", "there", "when", "where",
            "why", "how", "which", "who", "whom", "this", "that",
            "these", "those", "it", "its", "my", "your", "his",
            "her", "our", "their", "me", "him", "us", "them",
        }

        # 分词
        words = cleaned.split()
        # 过滤停用词和短词
        filtered = [
            w for w in words
            if w.lower() not in stopwords and len(w) >= 2
        ]

        # 去重并保留长词优先
        seen: set[str] = set()
        unique: list[str] = []
        for w in sorted(filtered, key=len, reverse=True):
            w_lower = w.lower()
            if w_lower not in seen:
                seen.add(w_lower)
                unique.append(w)
                if len(unique) >= max_keywords:
                    break

        return unique[:max_keywords]

    @staticmethod
    def _generate_explanation(
        dimension_scores: dict[str, float], overall: float
    ) -> str:
        """生成评分解释。

        Args:
            dimension_scores: 各维度评分。
            overall: 综合得分。

        Returns:
            人类可读的评分解释。
        """
        # 找出强弱项
        best_dim = max(dimension_scores, key=lambda k: dimension_scores[k])
        worst_dim = min(dimension_scores, key=lambda k: dimension_scores[k])

        dim_labels = {
            "intent_understanding": "意图理解",
            "actionability": "可执行性",
            "user_preference_match": "用户偏好匹配",
            "information_density": "信息密度",
            "drift_risk": "跑偏控制",
            "token_efficiency": "Token效率",
        }

        return (
            f"综合评分: {overall:.2f} | "
            f"强项: {dim_labels.get(best_dim, best_dim)}({dimension_scores[best_dim]:.2f}) | "
            f"弱项: {dim_labels.get(worst_dim, worst_dim)}({dimension_scores[worst_dim]:.2f})"
        )
