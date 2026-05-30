"""评估与负面案例管理模块。

本模块负责两个核心功能：
- Evaluator: 对模型输出进行多维度评估，检测输出漂移
- BadCaseManager: 管理评估不合格的案例，用于后续反思学习

评估维度和权重经团队讨论确定，可通过 __init__ 参数自定义。

V3 升级：
- evaluate() 升级为三层评测：RuleEval → ComponentEval → 加权汇总
- 去掉 random 评分，所有评分可解释
- 新增 evaluate_rule 和 evaluate_component 方法
- BadCaseManager 新增 convert_to_eval_case
"""

from __future__ import annotations

import re
import time
from typing import Optional, TYPE_CHECKING

from stable_agent.models import BadCase, EvaluationResult, TaskType

if TYPE_CHECKING:
    from stable_agent.models import EvalCase


# ============================================================================
# Evaluator — 模型输出评估器
# ============================================================================


class Evaluator:
    """模型输出评估器。

    对模型输出从多个维度进行评分，生成 EvaluationResult。
    支持 drift 检测和自然语言反馈生成。

    V3 升级：三层评测（RuleEval → ComponentEval → 加权汇总），
    所有评分可解释。

    Attributes:
        _weights: 各维度评分的加权权重（内部使用，字典顺序固定）。
    """

    # 禁忌词列表（生产环境应包含更多）
    FORBIDDEN_PATTERNS: list[str] = [
        "TODO", "FIXME", "HACK", "XXX", "占位",
        "implement later", "not implemented",
    ]

    # 必须引用来源的提示词
    REFERENCE_PATTERNS: list[str] = [
        "根据", "参照", "参考", "引自", "来源",
    ]

    def __init__(self, llm_client=None) -> None:
        """初始化评估器。

        设置各评估维度的权重：
        - completion_rate: 0.25（任务完成度最重要）
        - context_hit_rate: 0.20（上下文命中率）
        - token_efficiency: 0.15（token 效率）
        - hallucination_score: 0.25（幻觉检测同等重要）
        - user_preference_score: 0.15（用户偏好）

        V3 新增维度权重：
        - format_quality: 0.10
        - safety_score: 0.10
        - retrieval_quality: 0.10

        Args:
            llm_client: 可选的 LLM 客户端，用于 AI 增强评分。
        - memory_quality: 0.10
        - tool_quality: 0.10

        注：evaluate() 的 V3 加权汇总使用 _v3_weights。
        """
        self._weights: dict[str, float] = {
            "completion_rate": 0.25,
            "context_hit_rate": 0.20,
            "token_efficiency": 0.15,
            "hallucination_score": 0.25,
            "user_preference_score": 0.15,
        }
        self._llm_client = llm_client

        # V3 三层评测权重
        self._v3_weights: dict[str, float] = {
            "completion_rate": 0.15,
            "context_hit_rate": 0.10,
            "token_efficiency": 0.10,
            "hallucination_score": 0.15,
            "user_preference_score": 0.10,
            "format_quality": 0.10,
            "safety_score": 0.10,
            "retrieval_quality": 0.05,
            "memory_quality": 0.05,
            "tool_quality": 0.05,
            "token_roi": 0.05,
        }

    # ------------------------------------------------------------------
    # V3 新增: 分层评测方法
    # ------------------------------------------------------------------

    def evaluate_rule(self, task: TaskType, model_output: str) -> dict:
        """RuleEval：格式检查、禁忌词、是否引用来源。

        不依赖外部 API，纯规则匹配。

        Args:
            task: 任务类型。
            model_output: 模型输出文本。

        Returns:
            包含以下字段的字典：
            - format_quality: 格式质量评分（0.0~1.0）
            - safety_score: 安全评分（0.0~1.0，含禁忌词则降低）
            - must_not_include_ok: 布尔值，是否通过禁忌词检查
            - details: 详细检查结果字典

        Examples:
            >>> evaluator = Evaluator()
            >>> result = evaluator.evaluate_rule(TaskType.BUG_FIX, "修复完成，TODO 优化")
            >>> result["safety_score"] < 1.0
            True
            >>> result["must_not_include_ok"]
            False
        """
        details: dict = {}
        output_lower: str = model_output.lower()

        # ---- 1. 格式质量 ----
        format_score: float = 1.0
        format_issues: list[str] = []

        # 输出为空
        if not model_output.strip():
            format_score = 0.0
            format_issues.append("输出为空")
        else:
            # 检查是否有代码块标记（对 bug_fix/code_gen 任务）
            if task in (TaskType.BUG_FIX, TaskType.CODE_GENERATION):
                if "```" not in model_output:
                    format_score -= 0.1
                    format_issues.append("缺少代码块标记")
            # 检查是否有明显的结构化输出（段落/列表）
            has_structure: bool = bool(
                re.search(r"^\d+\.", model_output, re.MULTILINE)  # 编号列表
                or re.search(r"^[-*]\s", model_output, re.MULTILINE)  # 无序列表
                or "\n\n" in model_output  # 段落分隔
            )
            if not has_structure:
                format_score -= 0.05
                format_issues.append("缺少结构化输出")

        format_quality: float = round(max(0.0, format_score), 4)
        details["format"] = {
            "score": format_quality,
            "issues": format_issues,
        }

        # ---- 2. 安全评分（禁忌词检测） ----
        safety_score: float = 1.0
        forbidden_hits: list[str] = []
        for pattern in self.FORBIDDEN_PATTERNS:
            if pattern.lower() in output_lower:
                forbidden_hits.append(pattern)
                safety_score -= 0.15  # 每个禁忌词扣 0.15

        safety_score = round(max(0.0, safety_score), 4)
        must_not_include_ok: bool = len(forbidden_hits) == 0
        details["safety"] = {
            "score": safety_score,
            "forbidden_hits": forbidden_hits,
            "ok": must_not_include_ok,
        }

        # ---- 3. 引用来源检查 ----
        has_reference: bool = any(
            pat in model_output for pat in self.REFERENCE_PATTERNS
        )
        details["reference"] = {
            "has_reference": has_reference,
        }

        return {
            "format_quality": format_quality,
            "safety_score": safety_score,
            "must_not_include_ok": must_not_include_ok,
            "details": details,
        }

    def evaluate_component(
        self,
        task: TaskType,
        input_context: str,
        model_output: str,
        memories_hit: int = 0,
        rag_chunks_hit: int = 0,
    ) -> dict:
        """ComponentEval：记忆命中、RAG 命中、工具调用正确性。

        评估各组件对最终输出的贡献质量。

        Args:
            task: 任务类型。
            input_context: 输入上下文。
            model_output: 模型输出。
            memories_hit: 命中的记忆条目数。
            rag_chunks_hit: 命中的 RAG 块数。

        Returns:
            包含以下字段的字典：
            - memory_quality: 记忆质量评分（0.0~1.0）
            - retrieval_quality: 检索质量评分（0.0~1.0）
            - tool_quality: 工具使用质量评分（0.0~1.0）
            - details: 详细检查结果字典

        Examples:
            >>> evaluator = Evaluator()
            >>> result = evaluator.evaluate_component(
            ...     TaskType.BUG_FIX, "context", "output", memories_hit=3)
            >>> result["memory_quality"] > 0
            True
        """
        details: dict = {}

        # ---- 1. 记忆质量 ----
        # 基于 memories_hit 和输出对输入上下文的利用程度
        if memories_hit > 0:
            memory_quality: float = min(1.0, memories_hit / 5.0)
        else:
            memory_quality = 0.5  # 中性值

        # 如果输出中引用了记忆中的内容，加分
        ctx_tokens: set[str] = self._tokenize(input_context)
        out_lower: str = model_output.lower()
        ctx_hits: int = sum(1 for t in ctx_tokens if len(t) >= 2 and t in out_lower)
        if ctx_tokens and ctx_hits > 0:
            memory_quality = min(1.0, memory_quality + 0.1)

        memory_quality = round(memory_quality, 4)
        details["memory"] = {"score": memory_quality, "memories_hit": memories_hit}

        # ---- 2. 检索质量 ----
        # 基于 rag_chunks_hit 和上下文命中率
        if rag_chunks_hit > 0:
            retrieval_quality: float = min(1.0, rag_chunks_hit / 5.0)
        else:
            retrieval_quality = 0.5  # 中性值

        retrieval_quality = round(retrieval_quality, 4)
        details["retrieval"] = {"score": retrieval_quality, "rag_chunks_hit": rag_chunks_hit}

        # ---- 3. 工具质量 ----
        # 检查输出中是否包含合理的工具使用痕迹
        tool_indicators: list[str] = [
            "import ", "from ", "def ", "class ",  # Python 代码
            "function ", "const ", "let ", "var ",  # JS 代码
            "```",  # 代码块
            "执行", "调用", "运行",  # 中文工具调用
        ]
        tool_hits: int = sum(
            1 for kw in tool_indicators if kw.lower() in out_lower
        )
        if tool_hits > 0:
            tool_quality: float = min(1.0, 0.5 + tool_hits * 0.1)
        else:
            tool_quality = 0.5  # 中性值

        tool_quality = round(tool_quality, 4)
        details["tool"] = {"score": tool_quality, "tool_indicators_hit": tool_hits}

        return {
            "memory_quality": memory_quality,
            "retrieval_quality": retrieval_quality,
            "tool_quality": tool_quality,
            "details": details,
        }

    # ------------------------------------------------------------------
    # 核心评估方法（V3 升级）
    # ------------------------------------------------------------------

    def evaluate(
        self,
        task: TaskType,
        input_context: str,
        model_output: str,
        memories_hit: int = 0,
        rag_chunks_hit: int = 0,
    ) -> EvaluationResult:
        """对任务执行结果进行三层评测。

        V3 升级：RuleEval → ComponentEval → 加权汇总。
        所有评分可解释，不使用 random。

        三层评测：
        1. RuleEval: 格式检查、禁忌词、引用来源
        2. ComponentEval: 记忆命中、RAG 命中、工具调用
        3. 加权汇总: 结合传统维度 + V3 新增维度

        Args:
            task: 任务类型。
            input_context: 原始输入上下文。
            model_output: 模型输出文本。
            memories_hit: 命中的记忆条目数，默认 0。
            rag_chunks_hit: 命中的 RAG 块数，默认 0。

        Returns:
            EvaluationResult 包含所有维度评分和加权总分。
        """
        # ---- Layer 1: RuleEval ----
        rule_result: dict = self.evaluate_rule(task, model_output)

        # ---- Layer 2: ComponentEval ----
        comp_result: dict = self.evaluate_component(
            task, input_context, model_output, memories_hit, rag_chunks_hit
        )

        # ---- 传统维度 ----
        # 1. 完成度：基于输出长度
        output_len: int = len(model_output)
        if output_len > 200:
            completion_rate: float = 1.0
        elif output_len > 50:
            completion_rate = 0.8
        elif output_len > 0:
            completion_rate = 0.4
        else:
            completion_rate = 0.0

        # 2. 上下文命中率
        context_hit_rate: float = self._compute_context_hit(
            input_context, model_output
        )

        # 3. Token 效率（V3: 可解释版本，不再使用 random）
        # 基于 output_len / input_context_len，输出紧凑则高效
        ctx_len: int = max(1, len(input_context))
        efficiency_ratio: float = min(1.0, (output_len / ctx_len) * 5.0)
        token_efficiency: float = round(efficiency_ratio, 4)

        # 4. 幻觉评分：启发式检测
        hallucination_score: float = self._compute_hallucination_score(
            model_output
        )

        # 5. 用户偏好评分
        user_preference_score: float = 0.7

        # ---- V3: 加权汇总 ----
        overall_score: float = round(
            self._v3_weights["completion_rate"] * completion_rate
            + self._v3_weights["context_hit_rate"] * context_hit_rate
            + self._v3_weights["token_efficiency"] * token_efficiency
            + self._v3_weights["hallucination_score"] * hallucination_score
            + self._v3_weights["user_preference_score"] * user_preference_score
            + self._v3_weights["format_quality"] * rule_result["format_quality"]
            + self._v3_weights["safety_score"] * rule_result["safety_score"]
            + self._v3_weights["retrieval_quality"] * comp_result["retrieval_quality"]
            + self._v3_weights["memory_quality"] * comp_result["memory_quality"]
            + self._v3_weights["tool_quality"] * comp_result["tool_quality"]
            # token_roi 在 evaluate() 中不计算（由 budget_manager 计算）
            + self._v3_weights["token_roi"] * 0.5,  # 默认中性值
            4,
        )

        return EvaluationResult(
            completion_rate=round(completion_rate, 4),
            context_hit_rate=round(context_hit_rate, 4),
            token_efficiency=token_efficiency,
            hallucination_score=round(hallucination_score, 4),
            user_preference_score=round(user_preference_score, 4),
            overall_score=overall_score,
            # V3 新增字段
            retrieval_quality=comp_result["retrieval_quality"],
            memory_quality=comp_result["memory_quality"],
            tool_quality=comp_result["tool_quality"],
            format_quality=rule_result["format_quality"],
            safety_score=rule_result["safety_score"],
            token_roi=0.0,  # 由 budget_manager 计算
            failure_reasons=[],
            improvement_rules=[],
        )

    def detect_drift(
        self,
        previous_outputs: list[str],
        current_output: str,
    ) -> float:
        """检测当前输出相对于历史输出的漂移程度。

        使用词级 Jaccard 相似度计算：
        - 对每条历史输出计算与 current_output 的 Jaccard 相似度
        - drift = 1 - 平均相似度
        - drift 越大表示输出偏离历史模式越严重

        Args:
            previous_outputs: 历史输出文本列表。
            current_output: 当前输出文本。

        Returns:
            漂移分数，范围 [0, 1]。无历史输出时返回 0.0。
        """
        if not previous_outputs:
            return 0.0

        current_tokens: set[str] = self._tokenize(current_output)
        if not current_tokens:
            return 0.0

        similarities: list[float] = []
        for prev in previous_outputs:
            prev_tokens: set[str] = self._tokenize(prev)
            if not prev_tokens:
                continue
            union: set[str] = current_tokens | prev_tokens
            if not union:
                similarities.append(0.0)
            else:
                similarities.append(
                    len(current_tokens & prev_tokens) / len(union)
                )

        if not similarities:
            return 0.0

        avg_similarity: float = sum(similarities) / len(similarities)
        drift: float = 1.0 - avg_similarity
        return round(drift, 4)

    def generate_feedback(self, evaluation: EvaluationResult) -> str:
        """生成中文自然语言评估反馈。

        根据各维度评分和综合评分生成结构化的反馈报告。

        Args:
            evaluation: 评估结果。

        Returns:
            中文评估报告字符串。
        """
        lines: list[str] = []

        # 各维度说明
        lines.append(
            f"✅ 完成度 {evaluation.completion_rate:.2f}："
            f"输出长度评估，反映任务是否产生了足够的内容。"
        )
        lines.append(
            f"🎯 上下文命中率 {evaluation.context_hit_rate:.2f}："
            f"衡量输出是否正确利用了输入上下文的信号。"
        )
        lines.append(
            f"⚡ Token 效率 {evaluation.token_efficiency:.2f}："
            f"评估 token 使用的经济性（基于输出/上下文长度比率）。"
        )
        lines.append(
            f"🔍 幻觉评分 {evaluation.hallucination_score:.2f}："
            f"检测模型是否产生了不确定或虚假内容（越低越差）。"
        )
        lines.append(
            f"👤 用户偏好 {evaluation.user_preference_score:.2f}："
            f"默认估计值，需用户反馈数据校准。"
        )
        # V3 新增维度
        lines.append(
            f"📋 格式质量 {evaluation.format_quality:.2f}："
            f"检查输出格式、禁忌词和引用来源。"
        )
        lines.append(
            f"🛡️ 安全评分 {evaluation.safety_score:.2f}："
            f"检测输出中的禁忌词和不安全内容。"
        )
        lines.append(
            f"🧠 记忆质量 {evaluation.memory_quality:.2f}："
            f"评估记忆对输出的贡献程度。"
        )
        lines.append(
            f"📚 检索质量 {evaluation.retrieval_quality:.2f}："
            f"评估 RAG 检索对输出的贡献程度。"
        )
        lines.append(
            f"🔧 工具质量 {evaluation.tool_quality:.2f}："
            f"评估工具调用的正确性。"
        )

        # 综合判定
        if evaluation.overall_score >= 0.8:
            lines.append("👍 整体表现优秀")
        elif evaluation.overall_score >= 0.5:
            lines.append("⚠️ 表现一般，建议优化")
        else:
            lines.append("❌ 表现不佳，已记录 bad case")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        """将文本拆分为词集合。

        Args:
            text: 输入文本。

        Returns:
            词集合。
        """

        tokens: set[str] = set()
        parts: list[str] = re.split(r"[^\w\u4e00-\u9fff]+", text.lower())
        for part in parts:
            if not part:
                continue
            if part.isascii():
                tokens.add(part)
            else:
                tokens.update(part)
        return tokens

    @staticmethod
    def _compute_context_hit(
        input_context: str,
        model_output: str,
    ) -> float:
        """计算上下文关键词在输出中的命中率。

        提取 input_context 中长度 >= 2 的关键词，
        统计这些词在 model_output 中出现的比例。

        Args:
            input_context: 输入上下文。
            model_output: 模型输出。

        Returns:
            命中率，范围 [0, 1]。
        """
        ctx_tokens: set[str] = Evaluator._tokenize(input_context)
        # 只保留长度 >= 2 的关键词
        keywords: set[str] = {t for t in ctx_tokens if len(t) >= 2}
        if not keywords:
            return 0.5  # 无关键词时返回中性值

        out_lower: str = model_output.lower()
        hits: int = sum(1 for kw in keywords if kw in out_lower)
        return round(hits / len(keywords), 4)

    def _compute_hallucination_score(self, model_output: str) -> float:
        """基于启发式规则 + AI 增强的幻觉检测。

        优先使用 LLM 客户端进行深度检查，LLM 不可用时回退到启发式规则。

        Args:
            model_output: 模型输出文本。

        Returns:
            幻觉评分，1.0 表示无幻觉。
        """
        # AI 增强路径
        if self._llm_client is not None:
            try:
                return self._ai_hallucination_check(model_output)
            except Exception:
                pass  # 降级到启发式

        # 启发式回退
        output_lower: str = model_output.lower()
        humility_keywords: list[str] = [
            "抱歉", "不知道", "不确定", "无法确认",
            "建议您", "请参考", "可能", "might",
            "不确定", "不清楚",
        ]
        for kw in humility_keywords:
            if kw in output_lower:
                return 0.95

        absolute_keywords: list[str] = [
            "绝对", "一定", "必然", "毫无疑问",
            "100%", "肯定",
        ]
        for kw in absolute_keywords:
            if kw in output_lower:
                return 0.6

        return 0.75

    def _ai_hallucination_check(self, model_output: str) -> float:
        """使用 LLM 进行幻觉检测。

        让 LLM 自己判断输出内容是否包含不确定的断言。

        Args:
            model_output: 模型输出文本。

        Returns:
            幻觉评分，1.0 表示无幻觉。
        """
        prompt = (
            "请评估以下 AI 输出是否存在幻觉（编造了不存在的事实）。"
            "只返回一个 0.0 到 1.0 之间的数字，1.0 表示完全可信，0.0 表示完全编造。\n\n"
            f"AI 输出:\n{model_output[:2000]}\n\n"
            "评分 (0.0-1.0):"
        )
        try:
            result = self._llm_client.complete(
                prompt=prompt,
                system_prompt="你是幻觉检测专家。只返回数字。",
                max_tokens=10,
                temperature=0.1,
            )
            score_text = result["text"].strip()
            # 尝试提取数字
            import re
            match = re.search(r'(0?\.?\d+)', score_text)
            if match:
                return min(1.0, max(0.0, float(match.group(1))))
        except Exception as parse_err:
            logger.warning("分数解析失败，回退默认值: %s", parse_err)
        return 0.75  # LLM 失败时回退


# ============================================================================
# BadCaseManager — 负面案例管理
# ============================================================================


class BadCaseManager:
    """负面案例管理器。

    收集、存储评估不合格的案例，并支持基于案例的改进建议生成。

    Attributes:
        storage_path: JSON 持久化文件路径。
        _cases: 内存中的 BadCase 列表。
    """

    def __init__(self, storage_path: str = "data/bad_cases.json") -> None:
        """初始化负面案例管理器。

        Args:
            storage_path: JSON 文件持久化路径，默认 "data/bad_cases.json"。
        """
        self.storage_path: str = storage_path
        self._cases: list[BadCase] = []

    # ------------------------------------------------------------------
    # 公共方法
    # ------------------------------------------------------------------

    def record_case(
        self,
        task: TaskType,
        input_context: str,
        output: str,
        evaluation: EvaluationResult,
    ) -> None:
        """记录一个评估不合格的案例。

        仅在 evaluation.overall_score < 0.5 时记录。
        自动生成失败原因描述。

        # STUB: 持久化到 JSON 文件。当前仅追加到内存列表。

        Args:
            task: 任务类型。
            input_context: 输入上下文。
            output: 模型输出。
            evaluation: 评估结果。
        """
        if evaluation.overall_score >= 0.5:
            return  # 不记录合格案例

        # 生成失败原因
        reason: str = self._infer_failure_reason(task, evaluation)

        case: BadCase = BadCase(
            task_type=task,
            input_context=input_context,
            output=output,
            evaluation=evaluation,
            timestamp=time.time(),
            failure_reason=reason,
        )
        self._cases.append(case)

    def generate_improvement_rule(self, bad_case: BadCase) -> str:
        """根据负面案例生成改进建议规则。

        基于 task_type 和 evaluation 各维度得分给出针对性的改进方向。

        Args:
            bad_case: 负面案例。

        Returns:
            中文改进建议字符串。
        """
        # 根据任务类型和失败维度生成建议
        if bad_case.task_type in (TaskType.BUG_FIX,):
            if bad_case.evaluation.completion_rate < 0.5:
                return "修复类任务必须先加载相关代码结构和测试用例"

        if bad_case.task_type == TaskType.CODE_GENERATION:
            if bad_case.evaluation.context_hit_rate < 0.3:
                return "代码生成任务应优先检索 API 文档和代码示例"

        if bad_case.task_type == TaskType.UI_DESIGN:
            if bad_case.evaluation.hallucination_score < 0.5:
                return "UI 设计任务应严格遵循设计规范的约束，避免自由发挥"

        if bad_case.evaluation.hallucination_score < 0.4:
            return "检测到高幻觉风险，建议增加事实核查步骤"

        if bad_case.evaluation.completion_rate < 0.3:
            return "输出长度严重不足，可能模型提前终止，建议检查 max_tokens 设置"

        return "增加相关记忆条目和知识库检索"

    def retrieve_recent_bad_cases(
        self,
        limit: int = 10,
    ) -> list[BadCase]:
        """检索最近的负面案例。

        按 timestamp 降序返回最近 limit 条案例。

        Args:
            limit: 返回的最大案例数，默认 10。

        Returns:
            按时间降序排列的 BadCase 列表。
        """
        sorted_cases: list[BadCase] = sorted(
            self._cases,
            key=lambda c: c.timestamp,
            reverse=True,
        )
        return sorted_cases[:limit]

    def convert_to_eval_case(
        self,
        bad_case: BadCase,
        expected_behavior: str = "",
    ) -> "EvalCase":
        """将 BadCase 自动转换为回归评测用例。

        must_not_include 从 failure_reason 中提取错误模式。
        source = "auto_from_bad_case"。

        Args:
            bad_case: 负面案例。
            expected_behavior: 期望行为描述，空字符串时自动生成。

        Returns:
            转换后的 EvalCase 实例。

        Examples:
            >>> mgr = BadCaseManager()
            >>> from stable_agent.models import BadCase, EvaluationResult
            >>> eval_result = EvaluationResult(overall_score=0.3)
            >>> bc = BadCase(
            ...     task_type=TaskType.BUG_FIX,
            ...     input_context="修复登录bug",
            ...     output="TODO: 待修复",
            ...     evaluation=eval_result,
            ...     failure_reason="完成度不足"
            ... )
            >>> ec = mgr.convert_to_eval_case(bc, "应该提供完整的修复代码")
            >>> ec.source
            'auto_from_bad_case'
            >>> ec.case_id.startswith("eval_")
            True
        """
        import uuid

        from stable_agent.models import EvalCase

        # 从 failure_reason 中提取 must_not_include 模式
        must_not_list: list[str] = []
        failure_reason_lower: str = bad_case.failure_reason.lower()

        # 根据失败原因添加 must_not_include 规则
        if "完成度不足" in failure_reason_lower or "completion" in failure_reason_lower:
            must_not_list.append("TODO")
            must_not_list.append("占位")
        if "幻觉" in failure_reason_lower or "hallucination" in failure_reason_lower:
            must_not_list.append("绝对")
            must_not_list.append("一定")
        if "格式" in failure_reason_lower or "format" in failure_reason_lower:
            must_not_list.append("FIXME")

        # 从输出中提取错误模式关键词
        output_lower: str = bad_case.output.lower()
        for fp in Evaluator.FORBIDDEN_PATTERNS:
            if fp.lower() in output_lower and fp not in must_not_list:
                must_not_list.append(fp)

        # 生成期望行为
        if not expected_behavior:
            expected_behavior = (
                f"应该正确完成 {bad_case.task_type.value} 类型的任务，"
                f"避免以下问题：{bad_case.failure_reason}"
            )

        # 从内容提取 must_include（输入关键词）
        must_include_list: list[str] = []
        input_tokens: set[str] = Evaluator._tokenize(bad_case.input_context)
        for t in sorted(input_tokens):
            if len(t) >= 3 and t.isascii():
                must_include_list.append(t)
                if len(must_include_list) >= 3:
                    break

        case_id: str = f"eval_{uuid.uuid4().hex[:8]}"

        return EvalCase(
            case_id=case_id,
            input_task=bad_case.input_context,
            expected_behavior=expected_behavior,
            must_include=must_include_list,
            must_not_include=must_not_list,
            source="auto_from_bad_case",
            created_from_bad_case_id=bad_case.evaluation.overall_score,  # 通过此字段传递标记
            task_type=bad_case.task_type,
        )

    # ------------------------------------------------------------------
    # V4 新增: BadCase → RolloutTrajectory 转换
    # ------------------------------------------------------------------

    def to_rollout_trajectory(
        self, bad_case: BadCase
    ) -> "RolloutTrajectory":
        """将 BadCase 转换为 V4 RolloutTrajectory（供 SkillOpt 使用）。

        映射规则：
        - task_input = bad_case.input_context[:500]
        - task_type = bad_case.task_type.value
        - model_output = bad_case.output[:1000]
        - user_feedback = "rejected"
        - eval_scores = {"overall_score": bad_case.evaluation.overall_score}
        - created_at = datetime.fromtimestamp(bad_case.timestamp)

        Args:
            bad_case: 要转换的 BadCase 实例。

        Returns:
            转换后的 RolloutTrajectory 实例。

        Examples:
            >>> mgr = BadCaseManager()
            >>> from stable_agent.models import BadCase, EvaluationResult, TaskType
            >>> eval_result = EvaluationResult(overall_score=0.3)
            >>> bc = BadCase(
            ...     task_type=TaskType.BUG_FIX,
            ...     input_context="修复登录bug",
            ...     output="TODO: 待修复",
            ...     evaluation=eval_result,
            ...     failure_reason="完成度不足",
            ... )
            >>> traj = mgr.to_rollout_trajectory(bc)
            >>> traj.user_feedback
            'rejected'
            >>> traj.task_input
            '修复登录bug'
        """
        import uuid
        from datetime import datetime

        from stable_agent.skill_optimizer.models import RolloutTrajectory

        return RolloutTrajectory(
            id=str(uuid.uuid4()),
            task_input=bad_case.input_context[:500],
            task_type=bad_case.task_type.value,
            user_intent_guess="",
            context_pack=bad_case.input_context[:500],
            skill_version="",
            model_output=bad_case.output[:1000],
            user_feedback="rejected",
            eval_scores={
                "overall_score": bad_case.evaluation.overall_score,
            },
            trace_events=[],
            token_usage={},
            created_at=datetime.fromtimestamp(bad_case.timestamp),
        )

    # ------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------

    @staticmethod
    def _infer_failure_reason(
        task: TaskType,
        evaluation: EvaluationResult,
    ) -> str:
        """根据评估结果推断失败原因。

        Args:
            task: 任务类型。
            evaluation: 评估结果。

        Returns:
            失败原因描述字符串。
        """
        reasons: list[str] = []

        if evaluation.completion_rate < 0.5:
            reasons.append(f"完成度不足 ({evaluation.completion_rate:.2f})")
        if evaluation.context_hit_rate < 0.3:
            reasons.append(f"上下文命中率低 ({evaluation.context_hit_rate:.2f})")
        if evaluation.hallucination_score < 0.5:
            reasons.append(f"幻觉风险高 ({evaluation.hallucination_score:.2f})")
        if evaluation.token_efficiency < 0.3:
            reasons.append(f"Token 效率低 ({evaluation.token_efficiency:.2f})")
        # V3: 检查新增维度
        if evaluation.format_quality < 0.4:
            reasons.append(f"格式质量差 ({evaluation.format_quality:.2f})")
        if evaluation.safety_score < 0.5:
            reasons.append(f"安全评分低 ({evaluation.safety_score:.2f})")

        if reasons:
            return "；".join(reasons)
        return f"{task.value} 任务综合评分不达标 ({evaluation.overall_score:.2f})"

    @staticmethod
    def convert_to_regression_case(bad_case: BadCase) -> dict[str, Any]:
        """将 BadCase 转为可用于 ValidationGate 的 regression case。

        V6-Professional 新增：失败案例必须可被复测，形成 regression_cases.jsonl。

        Args:
            bad_case: BadCase 实例。

        Returns:
            标准 regression case 字典，含 id / task_input / expected_behavior /
            failure_mode / source_run_id / tags / created_at。
        """
        failure_attribution = bad_case.evaluation.failure_attribution
        failure_mode = failure_attribution.get("failed_stage", "unknown")
        reason = failure_attribution.get("reason", bad_case.failure_reason)

        return {
            "id": bad_case.id,
            "task_input": bad_case.input_context,
            "expected_behavior": f"应当避免 {failure_mode} 阶段的失败：{reason}",
            "failure_mode": failure_mode,
            "source_run_id": bad_case.source_run_id,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(bad_case.timestamp)),
            "tags": bad_case.tags or ["eval", "skillopt"],
            "overall_score": bad_case.evaluation.overall_score,
        }
