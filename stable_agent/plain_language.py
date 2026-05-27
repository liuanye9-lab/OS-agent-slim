"""StableAgent OS 大白话解释器模块。

本模块提供 PlainLanguageExplainer 类，将系统内部的技术事件
翻译成中文大白话解释，让非技术用户也能理解 Agent 在做什么。

模块职责：
- 事件类型 → 大白话翻译映射
- 带上下文的增强解释（记忆数、token 数、评分等）
- 未知事件的默认回退处理
"""

from __future__ import annotations

from typing import Any


class PlainLanguageExplainer:
    """大白话解释器：技术事件 → 中文大白话翻译。

    将系统内部的英文事件类型（如 "workflow:started"）翻译为
    中文大白话（如 "🧠 它刚刚接到任务，开始思考怎么处理。"）。

    Attributes:
        EXPLANATIONS: 事件类型 → 大白话解释的映射字典。
        DEFAULT_EXPLANATION: 未知事件类型的默认解释。
    """

    EXPLANATIONS: dict[str, str] = {
        # ---- 工作流事件 ----
        "workflow:started": "🧠 它刚刚接到任务，开始思考怎么处理。",
        "workflow:init": "🚀 准备工作就绪，马上开始处理任务。",
        "workflow:planned": "🗺️ 它正在规划执行路线，看看先做什么后做什么。",
        "workflow:paused": "⏸️ 工作流已暂停，等待外部输入。",
        "workflow:resumed": "▶️ 工作流已恢复，接着之前的地方继续。",
        "workflow:failed": "❌ 出错了，它摔倒了但会显示错误原因。",
        "workflow:cancelled": "🛑 任务已取消。",
        "workflow:completed": "🎉 全部完成！正在总结经验，把好的做法记录下来。",

        # ---- 记忆事件 ----
        "memory:retrieved": "🔍 它翻出了以前的记忆卡片，找到了一些相关经验。",
        "memory:retrieval": "🔍 它正在翻找以前的记忆卡片，看看有没有相似的经验。",
        "memory:stored": "💾 它把这个经验记下来了，下次就不会忘了。",
        "memory:updated": "📝 它更新了一条记忆，把新信息补充进去了。",

        # ---- RAG 检索事件 ----
        "rag:retrieved": "📚 它从项目资料库里找到了相关参考，不是凭空猜。",
        "rag:searched": "📚 它正在查阅知识库，寻找参考资料。",
        "rag:indexed": "📑 它把新文档加入索引，以后查找更快。",

        # ---- 预算事件 ----
        "budget:compact": "🧮 它正在删掉不重要的信息，避免浪费 token 和分散注意力。",
        "budget:allocated": "📐 它正在估算这次要花多少 token，选择用大模型还是小模型。",
        "budget:exceeded": "⚠️ Token 不够了，它正在精简上下文，保证最重要的信息保留。",

        # ---- 上下文事件 ----
        "context:built": "📦 上下文包组装完毕，准备开始干活。",

        # ---- 计划事件 ----
        "plan:generated": "🗺️ 执行计划已制定，知道每一步该怎么走了。",

        # ---- 执行事件 ----
        "execute:started": "⚡ 开始执行任务，正在调用工具或模型。",
        "execute:completed": "⚡ 任务执行完毕，正在检查结果质量。",
        "execute:step": "👣 它完成了一个步骤，正在继续下一步。",

        # ---- 工具事件 ----
        "tool:called": "🔧 它正在使用工具，就像拿扳手修理东西。",
        "tool:result": "🔩 工具执行完毕，它正在分析返回结果。",
        "tool:error": "🔨 工具出错了，它正在想办法处理。",

        # ---- 评估事件 ----
        "eval:completed": "📊 它正在给自己打分，看看这次做得怎么样。",
        "eval:score": "📊 评分出来了，正在分析哪里做得好、哪里需要改进。",
        "eval:failed": "📉 这次评分不太理想，它会从错误中学习。",

        # ---- 审批事件 ----
        "approval:required": "✋ 这一步可能影响文件或执行命令，需要你确认。",
        "approval:pending": "✋ 它在等待你的审批，不敢擅自行动。",
        "approval:approved": "✅ 审批通过，它继续执行任务。",
        "approval:rejected": "🚫 审批被拒绝，它需要换一种方式处理。",

        # ---- 学习事件 ----
        "learn:completed": "📝 经验已记录，下次遇到类似任务会做得更好。",
        "learn:failed": "📛 经验学习失败，但它会保留原始记录供后续分析。",

        # ---- 追踪事件 ----
        "trace:span_started": "📍 开始追踪一个新的操作步骤。",
        "trace:span_ended": "📍 操作步骤追踪完成，耗时已记录。",

        # ---- 决策事件 ----
        "decide:model": "🤔 它正在选择最适合的模型来处理这个任务。",
        "decide:strategy": "🤔 它在思考最佳的处理策略。",

        # ---- V4 SkillOpt 事件 ----
        "skillopt.epoch_started": "🔄 它开始了一轮技能学习：回顾最近的对话，找出哪里可以做得更好。",
        "skillopt.rollouts_collected": "📝 它整理完了最近的对话记录，准备从中学习。",
        "skillopt.failures_analyzed": "🔍 它正在复盘失败案例，找出用户反复不满意的地方。",
        "skillopt.successes_analyzed": "✨ 它发现了一些做得很好的模式，准备把它们固化下来。",
        "skillopt.patch_merged": "🧩 它正在把成功经验和失败教训合并成一份改进方案。",
        "skillopt.patch_ranked": "📊 它在给改进建议排序：先解决最影响体验的问题。",
        "skillopt.candidate_created": "📄 新的技能文档草案已生成，但它不会马上生效——要先通过验证。",
        "skillopt.validation_passed": "✅ 新技能文档通过了验证测试！确实比原来的更好，马上更新。",
        "skillopt.validation_failed": "❌ 这次改进在验证中表现不如预期，它把失败的尝试记录了下来，下次不会再犯同样的错误。",
        "skillopt.rejected_buffer_updated": "🗑️ 它把无效的修改放进了废纸篓，防止以后重复尝试。",
        "skillopt.slow_update_created": "🐢 它总结了一些长期稳定的规律，写进了技能文档的深层保护区。",
        "skillopt.best_skill_exported": "📦 最优技能文档已导出，可以部署给 AI 助手使用了。",
    }

    DEFAULT_EXPLANATION: str = "⏳ 它正在处理下一步。"

    def explain(self, event_type: str) -> str:
        """将事件类型翻译为中文大白话。

        如果事件类型在 EXPLANATIONS 映射中存在，返回对应的大白话解释；
        否则返回默认解释。

        Args:
            event_type: 事件类型字符串，如 "workflow:started"。

        Returns:
            中文大白话解释字符串。
        """
        return self.EXPLANATIONS.get(event_type, self.DEFAULT_EXPLANATION)

    def explain_with_context(self, event_type: str, payload: dict) -> str:
        """带上下文数据的大白话解释。

        根据 payload 中的具体数据增强解释内容：
        - 含 memory_count → "找到了 {n} 条相关记忆"
        - 含 budget → "分配了 {total} token 预算"
        - 含 score → "评分 {score}"
        - 含 chunk_count → "检索到 {n} 篇相关文档"

        Args:
            event_type: 事件类型字符串。
            payload: 事件负载数据字典。

        Returns:
            增强后的中文大白话解释。
        """
        base = self.explain(event_type)

        # 根据事件类型和 payload 中的数据增强解释
        enhancements: list[str] = []

        # 记忆检索增强
        if event_type.startswith("memory:") and "memory_count" in payload:
            count = payload["memory_count"]
            enhancements.append(f"找到了 {count} 条相关记忆")

        # 记忆详情增强
        if event_type.startswith("memory:") and "memory_best" in payload:
            best = payload["memory_best"]
            enhancements.append(f"最相关的是关于「{best}」的记忆")

        # RAG 检索增强
        if event_type.startswith("rag:") and "chunk_count" in payload:
            count = payload["chunk_count"]
            enhancements.append(f"检索到 {count} 篇相关文档")

        # RAG 详情增强
        if event_type.startswith("rag:") and "top_source" in payload:
            source = payload["top_source"]
            enhancements.append(f"最相关的资料来自「{source}」")

        # 预算增强
        if event_type.startswith("budget:") and "total" in payload:
            total = payload["total"]
            enhancements.append(f"分配了 {total} token 预算")

        # 预算详情
        if event_type.startswith("budget:") and "used" in payload:
            used = payload["used"]
            total = payload.get("total", "?")
            enhancements.append(f"已用 {used} / {total} tokens")

        # 执行增强
        if event_type.startswith("execute:") and "step_name" in payload:
            step = payload["step_name"]
            enhancements.append(f"当前步骤：{step}")

        # 评估增强
        if event_type.startswith("eval:") and "score" in payload:
            score = payload["score"]
            enhancements.append(f"评分 {score}")

        # 评估详情
        if event_type.startswith("eval:") and "overall_score" in payload:
            score = payload["overall_score"]
            enhancements.append(f"综合评分：{score}")

        # 工具调用增强
        if event_type.startswith("tool:") and "tool_name" in payload:
            name = payload["tool_name"]
            enhancements.append(f"正在使用「{name}」工具")

        # 审批增强
        if event_type == "approval:required" and "action" in payload:
            action = payload["action"]
            enhancements.append(f"需要确认的操作：{action}")

        # 错误/失败增强
        if event_type.endswith(":failed") and "error" in payload:
            error = payload["error"]
            enhancements.append(f"错误原因：{error}")

        # 通用的 score 字段
        if "score" in payload and not event_type.startswith("eval:"):
            score = payload["score"]
            enhancements.append(f"得分：{score}")

        if enhancements:
            return f"{base}（{'；'.join(enhancements)}）"

        return base
