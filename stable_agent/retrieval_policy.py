"""StableAgent OS 检索策略模块。

本模块提供 RetrievalPolicy（检索决策）和 RetrievalCritic（检索后
二次筛选）两个类，负责判断是否需要触发 RAG 检索，以及对检索结果
进行质量评估和筛选。

模块职责：
- 根据任务类型和输入内容决定是否检索
- 对检索结果进行二次筛选和风险评估
- 标注 why_relevant 和 risk 字段
"""

from __future__ import annotations

from typing import Optional

from stable_agent.models import TaskType
from stable_agent.token_meter import TokenMeter


# ============================================================================
# RetrievalPolicy — 检索决策
# ============================================================================


class RetrievalPolicy:
    """检索策略：判断是否需要触发 RAG 检索。

    根据任务类型和输入内容的特征决定是否应该进行知识库检索。
    """

    # 需要检索的任务类型（通常需要查阅代码/文档）
    RETRIEVAL_HEAVY_TYPES: set[TaskType] = {
        TaskType.ARCH_REFACTOR,
        TaskType.CODE_GENERATION,
        TaskType.BUG_FIX,
    }

    # 可能检索的任务类型（根据关键词决定）
    OPTIONAL_RETRIEVAL_TYPES: set[TaskType] = {
        TaskType.UI_DESIGN,
        TaskType.PROMPT_OPTIMIZATION,
        TaskType.EVAL_TASK,
    }

    # 通常不需要检索的任务类型
    LIGHT_RETRIEVAL_TYPES: set[TaskType] = {
        TaskType.GENERAL_QA,
    }

    # 知识类关键词 —— 出现这些词汇意味着即使 GENERAL_QA 也可能需要检索
    KNOWLEDGE_KEYWORDS: set[str] = {
        "文档", "说明", "指南", "规范", "标准", "规则", "知识",
        "doc", "document", "guide", "spec", "规范", "协议",
        "协议", "接口", "API", "api", "配置", "config",
        "版本", "更新", "变更", "changelog", "release",
    }

    # UI 设计相关关键词 —— UI_DESIGN 类型中触发检索
    UI_KEYWORDS: set[str] = {
        "样式", "组件", "颜色", "字体", "布局", "设计", "主题",
        "style", "component", "color", "font", "layout", "design", "theme",
        "按钮", "表单", "卡片", "侧栏", "导航", "弹窗",
        "button", "form", "card", "sidebar", "nav", "modal",
    }

    # 跳过检索的关键词（纯问候/确认类）
    SKIP_KEYWORDS: set[str] = {
        "你好", "谢谢", "再见", "好的", "OK", "ok", "yes", "no",
        "hi", "hello", "thanks", "bye", "goodbye",
    }

    # 输入最短长度阈值
    MIN_INPUT_LENGTH: int = 10

    def should_retrieve(self, task_type: TaskType, task_input: str) -> bool:
        """判断是否需要 RAG 检索。

        决策规则：
        - ARCH_REFACTOR / CODE_GENERATION / BUG_FIX → 基本需要
          （但仍检查 task_input 长度）
        - task_input 少于 MIN_INPUT_LENGTH 字符 → 跳过
        - GENERAL_QA + 无关键知识词汇 → 跳过
        - UI_DESIGN → 可选（根据是否有样式/组件关键词）

        Args:
            task_type: 任务类型。
            task_input: 用户输入文本。

        Returns:
            True 表示需要检索，False 表示不需要。
        """
        # 输入太短 → 跳过
        stripped = task_input.strip()
        if len(stripped) < self.MIN_INPUT_LENGTH:
            return False

        # 检索密集型任务
        if task_type in self.RETRIEVAL_HEAVY_TYPES:
            # 即使类型匹配，输入太短仍然跳过
            if len(stripped) < self.MIN_INPUT_LENGTH:
                return False
            return True

        # 可选检索任务
        if task_type in self.OPTIONAL_RETRIEVAL_TYPES:
            return self._has_relevant_keywords(stripped, task_type)

        # 轻量检索任务（GENERAL_QA 等）
        if task_type in self.LIGHT_RETRIEVAL_TYPES:
            return self._has_relevant_keywords(stripped, task_type)

        # 默认：不检索
        return False

    def skip_retrieval(self, task_type: TaskType, task_input: str) -> bool:
        """明确跳过的场景。

        识别以下无需检索的场景：
        - 纯问候语
        - 简单确认（OK、好的等）
        - 仅有一个单词的输入

        Args:
            task_type: 任务类型。
            task_input: 用户输入文本。

        Returns:
            True 表示应跳过检索。
        """
        stripped = task_input.strip().lower()

        # 空输入
        if not stripped:
            return True

        # 单单词输入
        if len(stripped.split()) <= 1 and len(stripped) < self.MIN_INPUT_LENGTH:
            return True

        # 纯问候/确认类
        if stripped in self.SKIP_KEYWORDS:
            return True

        return False

    def _has_relevant_keywords(
        self, task_input: str, task_type: TaskType
    ) -> bool:
        """检查输入中是否包含与任务类型相关的关键词。

        Args:
            task_input: 用户输入文本。
            task_type: 任务类型。

        Returns:
            True 表示包含相关关键词。
        """
        lower_input = task_input.lower()

        if task_type == TaskType.UI_DESIGN:
            keywords = self.UI_KEYWORDS
        else:
            keywords = self.KNOWLEDGE_KEYWORDS

        for kw in keywords:
            if kw.lower() in lower_input:
                return True

        return False


# ============================================================================
# RetrievalCritic — 检索后二次筛选
# ============================================================================


class RetrievalCritic:
    """检索后二次筛选器。

    对 RAG 检索返回的文档块进行质量评估、风险标注和重新排序。

    Attributes:
        token_meter: Token 计量器实例。
    """

    # 不确定词列表 —— 包含这些词的文档标注为 "uncertain" 风险
    UNCERTAINTY_WORDS: set[str] = {
        "可能", "也许", "或许", "大概", "应该", "估计",
        "maybe", "perhaps", "probably", "likely", "possibly",
        "might", "could", "大约", "似乎", "好像",
        "不确定", "uncertain", "不一定",
    }

    # 风险惩罚因子
    RISK_PENALTY: float = 0.2

    def __init__(self, token_meter: Optional[TokenMeter] = None) -> None:
        """初始化 RetrievalCritic。

        Args:
            token_meter: Token 计量器，None 时自动创建默认实例。
        """
        self.token_meter = token_meter if token_meter is not None else TokenMeter()

    def _compute_why_relevant(
        self, task_input: str, chunk_content: str
    ) -> str:
        """基于关键词匹配标注 why_relevant。

        查找 chunk 内容中与 task_input 重叠的关键词，
        生成相关性说明文本。

        Args:
            task_input: 用户任务输入。
            chunk_content: 检索块内容。

        Returns:
            why_relevant 说明字符串。
        """
        # 提取 task_input 中的潜在关键词（中英文）
        input_lower = task_input.lower()
        content_lower = chunk_content.lower()

        matched_keywords: list[str] = []

        # 检查中文关键词（2-3 字 ngram）
        import re
        chinese_chars = re.findall(r"[\u4e00-\u9fff]+", task_input)
        for segment in chinese_chars:
            if len(segment) >= 2 and segment in chunk_content:
                if segment not in matched_keywords:
                    matched_keywords.append(segment)

        # 检查英文关键词（长度 > 2 的单词）
        english_words = re.findall(r"[a-zA-Z]{3,}", task_input)
        for word in english_words:
            if word.lower() in content_lower and word not in matched_keywords:
                matched_keywords.append(word)

        if matched_keywords:
            return f"匹配关键词: {', '.join(matched_keywords[:5])}"
        return "与任务主题相关"

    def _detect_uncertainty_risk(self, chunk_content: str) -> Optional[str]:
        """检测文档块中的不确定性风险。

        如果内容中包含不确定词，标注为 "uncertain"。

        Args:
            chunk_content: 检索块内容。

        Returns:
            "uncertain" 如果检测到不确定词，否则 None。
        """
        content_lower = chunk_content.lower()
        for word in self.UNCERTAINTY_WORDS:
            if word.lower() in content_lower:
                return "uncertain"
        return None

    def critique(
        self,
        task_input: str,
        retrieved_chunks: list[dict],
        max_chunks: int = 5,
    ) -> list[dict]:
        """对检索结果进行二次筛选和排序。

        处理流程：
        1. 为每个 chunk 标注 why_relevant（基于关键词匹配）
        2. 标注 risk（包含不确定词 → "uncertain"）
        3. 按 score * (1 - risk_penalty) 重新排序
        4. 返回 top max_chunks

        Args:
            task_input: 用户任务输入。
            retrieved_chunks: 检索返回的 chunk 列表。
            max_chunks: 返回的最大 chunk 数，默认 5。

        Returns:
            经过筛选和排序的 chunk 列表。
        """
        if not retrieved_chunks:
            return []

        annotated: list[dict] = []

        for chunk in retrieved_chunks:
            # 创建副本以避免修改原始数据
            annotated_chunk = dict(chunk)

            content = annotated_chunk.get("content", "")

            # 1. 标注 why_relevant
            if "why_relevant" not in annotated_chunk or not annotated_chunk["why_relevant"]:
                annotated_chunk["why_relevant"] = self._compute_why_relevant(
                    task_input, content
                )

            # 2. 标注 risk
            if "risk" not in annotated_chunk or annotated_chunk["risk"] is None:
                annotated_chunk["risk"] = self._detect_uncertainty_risk(content)

            # 3. 计算 token_estimate（如果没有提供）
            if "token_estimate" not in annotated_chunk:
                annotated_chunk["token_estimate"] = self.token_meter.estimate_tokens(
                    content
                )

            annotated.append(annotated_chunk)

        # 4. 按 score * (1 - risk_penalty) 重新排序
        def _adjusted_score(chunk: dict) -> float:
            raw_score = chunk.get("score", 0.0)
            risk = chunk.get("risk")
            penalty = self.RISK_PENALTY if risk == "uncertain" else 0.0
            return raw_score * (1.0 - penalty)

        annotated.sort(key=_adjusted_score, reverse=True)

        # 5. 返回 top max_chunks
        return annotated[:max_chunks]
