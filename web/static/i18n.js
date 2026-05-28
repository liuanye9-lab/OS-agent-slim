/**
 * StableAgent OS V5.5 — 前端 i18n
 * 支持中文 / English / 双语 三种模式
 */

const I18N_DATA = {
    zh: {
        // 顶部栏
        status_idle: "待命中",
        status_running: "运行中",
        status_paused: "已暂停",
        status_completed: "已完成",
        status_failed: "失败",

        // Agent 场景
        panel_agent_theater: "Agent 状态剧场",
        scene_idle: "待命中",
        scene_memory_wall: "记忆墙 · 翻卡片",
        scene_bookshelf: "书架 · 知识检索",
        scene_calculator: "算盘 · 预算分配",
        scene_map_table: "地图 · 路线规划",
        scene_tool_bench: "工具台 · 工具调用",
        scene_exam_desk: "考试台 · 评测中",
        scene_archive_room: "档案柜 · 技能导出",
        avatar_waiting: "等待任务开始...",
        avatar_working: "正在处理中...",

        // 决策卡片
        label_what: "当前阶段",
        label_why: "为什么这样做",
        label_evidence: "依据",
        label_discarded: "丢弃",
        label_next: "下一步",
        stage_idle: "待命中",
        stage_task_intake: "任务理解",
        stage_intent_parse: "意图解析",
        stage_context_budget: "上下文预算",
        stage_memory_retrieval: "记忆检索",
        stage_rag_retrieval: "知识库检索",
        stage_context_build: "上下文构建",
        stage_planning: "规划中",
        stage_tool_call: "工具调用",
        stage_security_check: "安全检查",
        stage_approval_waiting: "等待审批",
        stage_execution: "执行中",
        stage_evaluation: "评测中",
        stage_badcase_record: "Bad Case 记录",
        stage_skill_learning: "技能学习",
        stage_skill_validation: "技能验证",
        stage_skill_export: "技能导出",
        stage_completed: "已完成",
        stage_failed: "失败",

        // 时间线
        panel_timeline: "决策时间线",
        timeline_waiting: "等待决策事件...",

        // 学习面板
        panel_learning: "自我优化证据",
        learning_triggered: "是否学习",
        learning_reason: "发现规律",
        learning_diff: "Patch Diff",
        learning_no_data: "暂无学习数据",
        learning_rollouts: "Rollout 数量",
        learning_pattern: "成功/失败规律",
        verdict_pending: "等待中",
        verdict_passed: "✅ 通过",
        verdict_rejected: "❌ 拒绝",

        // 底部状态
        metric_token: "Token",
        metric_quality: "Quality",
        metric_intent: "意图对齐",
        metric_memory: "记忆命中",

        // 风险
        risk_none: "🟢 无风险",
        risk_low: "🟡 低风险",
        risk_medium: "🟠 中风险",
        risk_high: "🔴 高风险",

        // 置信度
        confidence_format: "置信度 {0}%",
    },

    en: {
        // Top bar
        status_idle: "Idle",
        status_running: "Running",
        status_paused: "Paused",
        status_completed: "Completed",
        status_failed: "Failed",

        // Agent scenes
        panel_agent_theater: "Agent Theater",
        scene_idle: "Idle",
        scene_memory_wall: "Memory Wall · Flipping",
        scene_bookshelf: "Bookshelf · RAG Search",
        scene_calculator: "Calculator · Budget",
        scene_map_table: "Map · Planning Route",
        scene_tool_bench: "Tool Bench · Calling",
        scene_exam_desk: "Exam Desk · Evaluating",
        scene_archive_room: "Archive · Skill Export",
        avatar_waiting: "Waiting for task...",
        avatar_working: "Working...",

        // Decision card
        label_what: "Current Stage",
        label_why: "Why",
        label_evidence: "Evidence",
        label_discarded: "Discarded",
        label_next: "Next Step",
        stage_idle: "Idle",
        stage_task_intake: "Task Intake",
        stage_intent_parse: "Intent Parsing",
        stage_context_budget: "Context Budget",
        stage_memory_retrieval: "Memory Retrieval",
        stage_rag_retrieval: "RAG Retrieval",
        stage_context_build: "Context Build",
        stage_planning: "Planning",
        stage_tool_call: "Tool Call",
        stage_security_check: "Security Check",
        stage_approval_waiting: "Awaiting Approval",
        stage_execution: "Executing",
        stage_evaluation: "Evaluating",
        stage_badcase_record: "Bad Case Record",
        stage_skill_learning: "Skill Learning",
        stage_skill_validation: "Skill Validation",
        stage_skill_export: "Skill Export",
        stage_completed: "Completed",
        stage_failed: "Failed",

        // Timeline
        panel_timeline: "Decision Timeline",
        timeline_waiting: "Waiting for decisions...",

        // Learning panel
        panel_learning: "Self-Optimization Evidence",
        learning_triggered: "Learning Triggered",
        learning_reason: "Pattern Found",
        learning_diff: "Patch Diff",
        learning_no_data: "No learning data",
        learning_rollouts: "Rollouts",
        learning_pattern: "Pattern",
        verdict_pending: "Pending",
        verdict_passed: "✅ Passed",
        verdict_rejected: "❌ Rejected",

        // Status bar
        metric_token: "Token",
        metric_quality: "Quality",
        metric_intent: "Intent Align",
        metric_memory: "Memory Hit",

        // Risk
        risk_none: "🟢 None",
        risk_low: "🟡 Low",
        risk_medium: "🟠 Medium",
        risk_high: "🔴 High",

        // Confidence
        confidence_format: "Confidence {0}%",
    },
};

/** @type {'zh' | 'en' | 'both'} */
let currentLocale = 'zh';

/**
 * 获取当前语言的文本
 * @param {string} key - i18n key
 * @returns {string}
 */
function t(key) {
    const data = I18N_DATA[currentLocale === 'both' ? 'zh' : currentLocale];
    let text = data[key] || key;

    // 处理参数替换 {0}, {1}, ...
    for (let i = 1; i < arguments.length; i++) {
        text = text.replace(`{${i - 1}}`, arguments[i]);
    }

    // both 模式：追加英文
    if (currentLocale === 'both' && I18N_DATA.en[key]) {
        let enText = I18N_DATA.en[key];
        for (let i = 1; i < arguments.length; i++) {
            enText = enText.replace(`{${i - 1}}`, arguments[i]);
        }
        text = text + '\n' + enText;
    }

    return text;
}

/**
 * 切换语言
 * @param {'zh' | 'en' | 'both'} locale
 */
function setLocale(locale) {
    if (!['zh', 'en', 'both'].includes(locale)) return;
    currentLocale = locale;

    // 更新语言切换按钮
    document.querySelectorAll('.lang-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.lang === locale);
    });

    // 刷新所有 data-i18n 元素
    refreshI18n();

    // 触发全局事件
    window.dispatchEvent(new CustomEvent('localechange', { detail: { locale } }));
}

/**
 * 获取当前语言
 * @returns {'zh' | 'en' | 'both'}
 */
function getLocale() {
    return currentLocale;
}

/**
 * 刷新所有带 data-i18n 属性的元素
 */
function refreshI18n() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.dataset.i18n;
        const text = t(key);
        if (currentLocale === 'both') {
            el.innerHTML = text.replace(/\n/g, '<br>');
        } else {
            el.textContent = text;
        }
    });
}

/**
 * 根据 key 返回当前语言文本（不操作 DOM）
 * @param {string} key
 * @returns {string}
 */
function getStageName(stage) {
    const key = 'stage_' + stage;
    return t(key);
}

/**
 * 根据风险等级返回本地化标签
 * @param {string} level - 'none' | 'low' | 'medium' | 'high'
 * @returns {string}
 */
function getRiskLabel(level) {
    const key = 'risk_' + (level || 'none');
    return t(key);
}

// =========================================================================
// window.i18n 全局 API（语义阶段 + 反馈标签 + 语言切换，不刷新页面）
// =========================================================================

window.i18n = window.i18n || {};

/** @type {'zh' | 'en'} */
window.i18n.locale = 'zh';

window.i18n.translations = {
    zh: {
        // 13+1 个语义阶段
        stage_listening:        '正在接收任务',
        stage_thinking:         '正在理解你的需求',
        stage_memory:           '正在找以前的经验',
        stage_rag:              '正在查找项目资料',
        stage_budget:           '正在计算 token 成本',
        stage_planning:         '正在规划执行步骤',
        stage_tooling:          '正在调用工具',
        stage_safety:           '正在做安全检查',
        stage_approval:         '等待你确认',
        stage_eval:             '正在评估结果',
        stage_learning:         '正在总结经验',
        stage_archiving:        '正在更新 best_skill.md',
        stage_done:             '任务完成',
        stage_failed:           '任务失败',
        // 7 个反馈按钮标签
        feedback_aligned:       '符合我的意图',
        feedback_partial:       '部分符合',
        feedback_off_track:     '跑偏了',
        feedback_too_technical: '太技术化',
        feedback_too_generic:   '太空泛',
        feedback_not_specific:  '不够具体',
        feedback_no_plan:       '没有给我可执行方案',
        // 语言切换按钮
        lang_switch:            '切换到 English',
    },
    en: {
        stage_listening:        'Receiving task',
        stage_thinking:         'Understanding your intent',
        stage_memory:           'Retrieving prior memory',
        stage_rag:              'Searching project knowledge',
        stage_budget:           'Estimating token budget',
        stage_planning:         'Planning execution steps',
        stage_tooling:          'Calling a tool',
        stage_safety:           'Running safety check',
        stage_approval:         'Waiting for approval',
        stage_eval:             'Evaluating output',
        stage_learning:         'Learning from this run',
        stage_archiving:        'Updating best_skill.md',
        stage_done:             'Task completed',
        stage_failed:           'Task failed',
        feedback_aligned:       'Aligned with intent',
        feedback_partial:       'Partially aligned',
        feedback_off_track:     'Off track',
        feedback_too_technical: 'Too technical',
        feedback_too_generic:   'Too generic',
        feedback_not_specific:  'Not specific enough',
        feedback_no_plan:       'No executable plan',
        lang_switch:            '切换到中文',
    }
};

/**
 * window.i18n 取当前语言的翻译文本
 * @param {string} key
 * @returns {string}
 */
window.i18n.t = function (key) {
    const translations = this.translations[this.locale] || {};
    return translations[key] || key;
};

/**
 * 切换 window.i18n 语言（不刷新页面）
 * @param {'zh' | 'en'} locale
 */
window.i18n.setLocale = function (locale) {
    if (!['zh', 'en'].includes(locale)) return;
    this.locale = locale;

    // 更新所有 [data-i18n] 元素（window.i18n 翻译域）
    document.querySelectorAll('[data-i18n]').forEach(function (el) {
        var key = el.getAttribute('data-i18n');
        var text = window.i18n.t(key);
        if (text !== key) {
            el.textContent = text;
        }
    });

    document.documentElement.lang = locale;
};
