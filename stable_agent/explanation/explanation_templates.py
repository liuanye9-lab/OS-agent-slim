"""V5.5 Explanation Templates — 19 个事件类型的中英双语模板。

每个模板包含 what/why/next 三个维度的中英文文本，
使用 `{key}` 占位符，由 DecisionNarrator 在运行时填充。

模板 key 对应 narrate_event 接收的 event_type，而非 DecisionStage。
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# 模板数据结构
# ---------------------------------------------------------------------------

Template = dict[str, str]

TEMPLATES: dict[str, Template] = {
    # ── Task Intake ──────────────────────────────────────────────────────
    "mcp.call.received": {
        "what_zh": "Agent 收到来自 MCP 网关的新任务调用。",
        "what_en": "Agent received a new task call from the MCP gateway.",
        "why_zh": "用户或上游系统触发了新的执行请求，Agent 开始接管任务。",
        "why_en": "A user or upstream system triggered a new execution request; Agent takes over.",
        "next_zh": "接下来会解析任务内容并分类意图。",
        "next_en": "Next, the task content will be parsed and the intent classified.",
    },
    # ── Intent Parse ─────────────────────────────────────────────────────
    "task.classified": {
        "what_zh": "任务被分类为 {intent_label}（置信度 {confidence}）。",
        "what_en": "Task classified as {intent_label} (confidence {confidence}).",
        "why_zh": "分类器根据历史任务模式和输入特征，匹配到最可能的意图类别。",
        "why_en": "The classifier matched the most probable intent category based on historical patterns and input features.",
        "next_zh": "接下来会根据意图分配 Token 预算并检索相关记忆。",
        "next_en": "Next, token budget will be allocated and relevant memories retrieved.",
    },
    "intent.parsed": {
        "what_zh": "用户意图解析完成：{intent_label}，优先级 {priority}。",
        "what_en": "User intent parsed: {intent_label}, priority {priority}.",
        "why_zh": "精确的意图解析是高效执行的基础，决定了后续检索和计划的策略。",
        "why_en": "Accurate intent parsing is the foundation of efficient execution, determining retrieval and planning strategy.",
        "next_zh": "接下来会设定 Token 预算并进行记忆检索。",
        "next_en": "Next, token budget will be set and memory retrieval initiated.",
    },
    # ── Context Budget ───────────────────────────────────────────────────
    "context.budgeted": {
        "what_zh": "Token 预算已分配：{allocated} tokens，剩余 {remaining} tokens。",
        "what_en": "Token budget allocated: {allocated} tokens, {remaining} remaining.",
        "why_zh": "预算管理防止上下文无限膨胀，确保在模型窗口内完成推理。",
        "why_en": "Budget management prevents unbounded context growth, ensuring inference fits within the model window.",
        "next_zh": "接下来会按预算检索记忆和资料。",
        "next_en": "Next, memories and knowledge will be retrieved within budget.",
    },
    # ── Memory Retrieval ─────────────────────────────────────────────────
    "memory.retrieved": {
        "what_zh": "它找到了 {n_total} 条记忆，选中 {n_selected} 条最相关的。",
        "what_en": "It found {n_total} memories and selected {n_selected} most relevant ones.",
        "why_zh": "这条记忆和当前任务高度相关，会影响输出质量。{n_discarded} 条无关记忆被丢弃以节省 Token。",
        "why_en": "This memory is highly relevant to the current task and will affect output quality. {n_discarded} irrelevant memories were discarded to save tokens.",
        "next_zh": "接下来会根据选中的记忆构建上下文包。",
        "next_en": "Next, a context pack will be assembled from the selected memories.",
    },
    # ── RAG Retrieval ────────────────────────────────────────────────────
    "rag.retrieved": {
        "what_zh": "从知识库检索到 {n_total} 篇文档，选中 {n_selected} 篇（Top-{top_k}）。",
        "what_en": "Retrieved {n_total} documents from knowledge base, selected {n_selected} (Top-{top_k}).",
        "why_zh": "外部知识检索补充了模型静态训练数据的不足，{n_discarded} 篇低相关文档被丢弃。",
        "why_en": "External knowledge retrieval supplements the model's static training data; {n_discarded} low-relevance documents were discarded.",
        "next_zh": "接下来会将检索结果合并到上下文包中。",
        "next_en": "Next, retrieval results will be merged into the context pack.",
    },
    # ── Context Build ────────────────────────────────────────────────────
    "context.compressed": {
        "what_zh": "上下文已压缩：原始 {original} tokens → {compressed} tokens，压缩比 {ratio}。",
        "what_en": "Context compressed: {original} tokens → {compressed} tokens, ratio {ratio}.",
        "why_zh": "压缩确保关键信息保留的同时减少 Token 开销，特别是长对话历史。",
        "why_en": "Compression ensures key information is preserved while reducing token overhead, especially for long conversation histories.",
        "next_zh": "接下来会基于压缩后的上下文构建最终上下文包。",
        "next_en": "Next, the final context pack will be built from compressed context.",
    },
    "context.built": {
        "what_zh": "上下文包构建完成，包含 {n_memories} 条记忆、{n_docs} 篇文档，共 {tokens} tokens。",
        "what_en": "Context pack assembled with {n_memories} memories, {n_docs} documents, {tokens} tokens total.",
        "why_zh": "完善的上下文包是模型准确推理的前提，它融合了记忆、知识和预算约束。",
        "why_en": "A comprehensive context pack is the prerequisite for accurate model reasoning, integrating memories, knowledge, and budget constraints.",
        "next_zh": "接下来模型会基于上下文包制定执行计划。",
        "next_en": "Next, the model will formulate an execution plan based on the context pack.",
    },
    # ── Planning ─────────────────────────────────────────────────────────
    "workflow.plan.created": {
        "what_zh": "执行计划已制定，包含 {n_steps} 个步骤，预计耗时 {estimated_time}。",
        "what_en": "Execution plan created with {n_steps} steps, estimated time {estimated_time}.",
        "why_zh": "结构化的计划让执行路径清晰可追踪，减少盲目操作和错误。",
        "why_en": "A structured plan makes the execution path clear and traceable, reducing blind operations and errors.",
        "next_zh": "接下来会按计划逐步调用工具执行。",
        "next_en": "Next, tools will be called step by step according to the plan.",
    },
    # ── Tool Call ────────────────────────────────────────────────────────
    "tool.call.started": {
        "what_zh": "调用工具 {tool_name}，输入参数 {params_summary}。",
        "what_en": "Calling tool {tool_name} with parameters {params_summary}.",
        "why_zh": "该工具是执行计划中的一步，用于完成 {purpose}。",
        "why_en": "This tool is a step in the execution plan, used to accomplish {purpose}.",
        "next_zh": "等待工具返回结果后继续下一步。",
        "next_en": "Waiting for tool result to proceed to next step.",
    },
    "tool.call.completed": {
        "what_zh": "工具 {tool_name} 执行完成，耗时 {duration}ms，结果 {result_summary}。",
        "what_en": "Tool {tool_name} completed in {duration}ms, result: {result_summary}.",
        "why_zh": "工具执行结果是后续步骤的输入，{status}。",
        "why_en": "The tool result serves as input for subsequent steps, {status}.",
        "next_zh": "检查输出质量后继续下一个计划步骤。",
        "next_en": "After checking output quality, proceed to the next plan step.",
    },
    # ── Security Check ───────────────────────────────────────────────────
    "security.checked": {
        "what_zh": "安全检查已完成，风险等级：{risk_level}，{n_issues} 个问题。",
        "what_en": "Security check completed, risk level: {risk_level}, {n_issues} issue(s).",
        "why_zh": "安全检查防止危险操作（如删除文件、执行任意代码）在未经审批的情况下执行。",
        "why_en": "Security checks prevent dangerous operations (e.g., file deletion, arbitrary code execution) from running without approval.",
        "next_zh": "{next_action}",
        "next_en": "{next_action}",
    },
    # ── Approval Waiting ─────────────────────────────────────────────────
    "approval.required": {
        "what_zh": "操作需要用户审批：{action_summary}，风险等级 {risk_level}。",
        "what_en": "Operation requires user approval: {action_summary}, risk level {risk_level}.",
        "why_zh": "高风险操作需要人工确认，以确保 Agent 不会做出不可逆的错误操作。",
        "why_en": "High-risk operations require human confirmation to ensure the Agent does not make irreversible mistakes.",
        "next_zh": "等待用户审批后继续或中止操作。",
        "next_en": "Waiting for user approval to continue or abort the operation.",
    },
    # ── Evaluation ───────────────────────────────────────────────────────
    "eval.completed": {
        "what_zh": "评测已完成，质量评分 {quality_score}，意图对齐 {intent_score}。",
        "what_en": "Evaluation completed, quality score {quality_score}, intent alignment {intent_score}.",
        "why_zh": "自动评测提供量化的质量反馈，帮助 Agent 自我改进。",
        "why_en": "Automated evaluation provides quantitative quality feedback, helping the Agent self-improve.",
        "next_zh": "低分任务会触发学习优化流程。",
        "next_en": "Low-scoring tasks will trigger the learning optimization flow.",
    },
    # ── Bad Case Recording ───────────────────────────────────────────────
    "badcase.recorded": {
        "what_zh": "失败案例已记录：{reason}，已关联任务 {run_id}。",
        "what_en": "Bad case recorded: {reason}, linked to task {run_id}.",
        "why_zh": "失败案例记录是持续改进的基础，它们会被用于训练更好的策略。",
        "why_en": "Bad case recording is the foundation for continuous improvement; they will be used to train better strategies.",
        "next_zh": "该案例将进入学习队列等待优化。",
        "next_en": "This case will enter the learning queue for optimization.",
    },
    # ── Skill Learning ───────────────────────────────────────────────────
    "skillopt.rollout.collected": {
        "what_zh": "收集到 {n_samples} 个新 rollout 样本用于技能学习。",
        "what_en": "Collected {n_samples} new rollout samples for skill learning.",
        "why_zh": "Rollout 样本为技能优化提供了真实执行数据，反映最优策略。",
        "why_en": "Rollout samples provide real execution data for skill optimization, reflecting optimal strategies.",
        "next_zh": "接下来会分析成功/失败模式并生成优化 patch。",
        "next_en": "Next, success/failure patterns will be analyzed and optimization patches generated.",
    },
    "skillopt.patch.proposed": {
        "what_zh": "提出技能优化 patch：{patch_summary}，预计提升 {expected_gain}。",
        "what_en": "Skill optimization patch proposed: {patch_summary}, expected gain {expected_gain}.",
        "why_zh": "基于真实执行反馈的 patch 比人工调优更精准，覆盖更多边界情况。",
        "why_en": "Patches based on real execution feedback are more precise than manual tuning, covering more edge cases.",
        "next_zh": "Patch 将进入验证流程，通过后才能导出。",
        "next_en": "The patch will enter validation; export only after passing.",
    },
    # ── Skill Validation ─────────────────────────────────────────────────
    "skillopt.validation.completed": {
        "what_zh": "技能验证完成：{n_patches} 个 patch 中 {n_passed} 个通过（阈值 {threshold}）。",
        "what_en": "Skill validation completed: {n_passed}/{n_patches} patches passed (threshold {threshold}).",
        "why_zh": "验证确保优化后的技能不会引入回归，质量评分不低于基线。",
        "why_en": "Validation ensures optimized skills do not introduce regressions and quality scores stay above baseline.",
        "next_zh": "通过验证的 patch 可以导出为正式技能。",
        "next_en": "Validated patches can be exported as formal skills.",
    },
    # ── Skill Export ─────────────────────────────────────────────────────
    "skillopt.exported": {
        "what_zh": "技能已导出：{skill_name} v{version}，包含 {n_patches} 个优化。",
        "what_en": "Skill exported: {skill_name} v{version}, with {n_patches} improvements.",
        "why_zh": "导出使优化成果持久化，后续任务可直接使用最新技能版本。",
        "why_en": "Exporting makes optimization results persistent; subsequent tasks can use the latest skill version.",
        "next_zh": "下一个任务将自动使用更新后的技能。",
        "next_en": "The next task will automatically use the updated skill.",
    },
    # ── Completed ────────────────────────────────────────────────────────
    "task.completed": {
        "what_zh": "任务执行完成，总耗时 {duration}ms，共调用 {n_tools} 个工具、{n_steps} 个步骤。",
        "what_en": "Task completed in {duration}ms, {n_tools} tools called across {n_steps} steps.",
        "why_zh": "Agent 成功完成了用户请求的所有步骤，产出符合预期。",
        "why_en": "Agent successfully completed all steps requested by the user; output meets expectations.",
        "next_zh": "生成 RunInsight 总结。",
        "next_en": "Generating RunInsight summary.",
    },
    # ── Failed ───────────────────────────────────────────────────────────
    "task.failed": {
        "what_zh": "任务执行失败：{reason}，发生在步骤 {failed_step}。",
        "what_en": "Task failed: {reason}, at step {failed_step}.",
        "why_zh": "失败原因可能是工具调用错误、权限不足或输入数据异常。Agent 会尝试回退。",
        "why_en": "Failure may be due to tool call errors, insufficient permissions, or anomalous input data. Agent will attempt fallback.",
        "next_zh": "分析失败原因并记录 bad case，等待手动或自动修复。",
        "next_en": "Analyzing failure cause and recording bad case, awaiting manual or automatic fix.",
    },
}


# ---------------------------------------------------------------------------
# 用户反馈标签 — 中英双语
# ---------------------------------------------------------------------------

FEEDBACK_LABELS: dict[str, dict[str, str]] = {
    "aligned":             {"zh": "符合我的意图",       "en": "Aligned with intent"},
    "partial":             {"zh": "部分符合",           "en": "Partially aligned"},
    "off_track":           {"zh": "跑偏了",             "en": "Off track"},
    "too_technical":       {"zh": "太技术化",           "en": "Too technical"},
    "too_generic":         {"zh": "太空泛",             "en": "Too generic"},
    "not_specific":        {"zh": "不够具体",           "en": "Not specific enough"},
    "no_executable_plan":  {"zh": "没有给我可执行方案",  "en": "No executable plan"},
}


def get_template(event_type: str) -> Template:
    """获取指定事件类型的中英双语模板。

    Args:
        event_type: 事件类型字符串，如 "memory.retrieved"。

    Returns:
        模板字典，如果未找到则返回通用模板。
    """
    if event_type in TEMPLATES:
        return dict(TEMPLATES[event_type])

    # 通用回退模板
    return {
        "what_zh": "发生了事件 {event_type}。",
        "what_en": "Event {event_type} occurred.",
        "why_zh": "这是 Agent 执行流程中的自动记录事件。",
        "why_en": "This is an auto-recorded event in the Agent execution flow.",
        "next_zh": "Agent 将继续执行后续步骤。",
        "next_en": "Agent will continue with subsequent steps.",
    }


def format_template(template: Template, kwargs: dict[str, Any]) -> Template:
    """用参数填充模板中的占位符。

    Args:
        template: 原始模板字典。
        kwargs: 占位符键值对。

    Returns:
        填充后的模板字典。缺失的占位符保留原样。
    """
    result: dict[str, str] = {}
    for key, value in template.items():
        try:
            result[key] = value.format(**kwargs)
        except KeyError:
            result[key] = value
    return result
