/**
 * StableAgent OS V5.5 — Dashboard V2 主控制器
 * WebSocket 连接、事件分发、面板更新。
 */

/** @type {WebSocket | null} */
let wsV2 = null;

/** @type {string | null} */
let currentRunId = null;

/** @type {boolean} */
let dashboardInitialized = false;

/** @type {string | null} */
window._currentRunId = null;

/** @type {string | null} */
window._pendingFeedback = null;

/**
 * 初始化 Dashboard V2
 */
function initDashboardV2() {
    if (dashboardInitialized) return;
    dashboardInitialized = true;

    // 初始化子组件
    initTimeline('timeline-list-v2');
    initLearningPanel('learning-panel');

    // 默认语言
    setLocale('zh');

    // 启动 avatar 动画
    startAvatarLoop();

    // 加载 run
    loadRunFromQuery();
}

/**
 * 从 URL 提取 run_id
 */
function loadRunFromQuery() {
    const urlParams = new URLSearchParams(window.location.search);
    const runId = urlParams.get('run_id');

    // 也尝试从路径提取 /runs/{run_id}
    const pathMatch = window.location.pathname.match(/\/runs\/([^/]+)/);

    if (runId) {
        currentRunId = runId;
    } else if (pathMatch) {
        currentRunId = pathMatch[1];
    }

    if (currentRunId) {
        window._currentRunId = currentRunId;
        connectWebSocketV2(currentRunId);
        updateRunStatus('running');
    } else {
        // 尝试从 HTML 中的占位符获取
        checkPlaceholder();
    }
}

/**
 * 检查 HTML 中的 RUN_ID_PLACEHOLDER（由服务器替换）
 */
function checkPlaceholder() {
    // 如果 HTML 中 RUN_ID_PLACEHOLDER 被替换为实际值，则从页面元素中提取
    const metaEl = document.querySelector('meta[name="run-id"]');
    if (metaEl && metaEl.content && metaEl.content !== 'RUN_ID_PLACEHOLDER') {
        currentRunId = metaEl.content;
        window._currentRunId = currentRunId;
        connectWebSocketV2(currentRunId);
        updateRunStatus('running');
    } else {
        updateRunStatus('idle');
    }
}

/**
 * WebSocket 连接
 * @param {string} runId
 */
function connectWebSocketV2(runId) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/dashboard-sync/ws/runs/${runId}`;

    wsV2 = new WebSocket(wsUrl);

    wsV2.onopen = () => {
        console.log('[Dashboard V2] WebSocket connected for run:', runId);
        updateRunStatus('running');
    };

    wsV2.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            handleEvent(msg);
        } catch (err) {
            console.error('[Dashboard V2] Parse error:', err);
        }
    };

    wsV2.onclose = () => {
        console.log('[Dashboard V2] WebSocket closed');
        updateRunStatus('completed');
    };

    wsV2.onerror = (err) => {
        console.error('[Dashboard V2] WebSocket error:', err);
        updateRunStatus('error');
    };
}

/**
 * 处理事件分发
 * @param {Object} msg - 事件消息
 */
function handleEvent(msg) {
    // 事件可能是直接 trace 数据，也可能是包装过的 {type: "event", data: {...}}
    let data = msg;
    if (msg.type === 'event' && msg.data) {
        data = msg.data;
    }
    if (msg.type === 'trace' && msg.data) {
        data = msg.data;
    }
    if (msg.type === 'user_feedback' && msg.data) {
        // 用户反馈事件 — 更新学习面板
        if (msg.data.learning_evidence) {
            updateLearningPanel(msg.data.learning_evidence);
        }
        return;
    }
    if (msg.type === 'run_insight' && msg.data) {
        // RunInsight 总结事件
        updateRunInsightCard(msg.data);
        return;
    }

    // 根据数据类型分发
    if (data.stage) {
        // DecisionTrace 数据
        updateDecisionCard(data);
        handleTrace(data);
        setSceneByStage(data.stage);
        updateStatusBar(data);
        updateAvatarStatus(data);
    }

    if (data.triggered !== undefined || data.patches !== undefined) {
        // LearningEvidence 数据
        updateLearningPanel(data);
    }

    if (data.quality_score !== undefined && data.intent_alignment_score !== undefined) {
        // RunInsight 数据（内联在 DecisionTrace 中）
        updateRunInsightCard(data);
        updateStatusBar(data);
    }
}

/**
 * 更新当前决策卡片
 * @param {Object} trace - 决策轨迹数据
 */
function updateDecisionCard(trace) {
    // 阶段
    const stageEl = document.getElementById('card-stage');
    if (stageEl) {
        stageEl.textContent = trace.stage_title || getStageName(trace.stage);
    }

    // 风险标签
    const riskEl = document.getElementById('risk-badge');
    if (riskEl) {
        const level = (trace.risk && trace.risk.level) || 'none';
        riskEl.textContent = getRiskLabel(level);
        riskEl.className = 'risk-badge risk-' + level;
    }

    // 当前阶段
    const whatEl = document.getElementById('card-what-value');
    if (whatEl) {
        whatEl.textContent = trace.what || '—';
    }

    // 为什么
    const whyEl = document.getElementById('card-why-value');
    if (whyEl) {
        whyEl.textContent = trace.why || '—';
    }

    // 依据标签
    const evidenceSection = document.getElementById('card-evidence-section');
    const evidenceTagsEl = document.getElementById('evidence-tags');
    if (evidenceTagsEl) {
        evidenceTagsEl.innerHTML = '';
        if (trace.evidence && trace.evidence.length > 0) {
            evidenceSection.style.display = '';
            trace.evidence.forEach(ev => {
                const tag = document.createElement('span');
                tag.className = 'evidence-tag';
                const confPct = Math.round((ev.confidence || 0) * 100);
                tag.innerHTML = escapeHtml(ev.title || ev.summary || '—')
                    + ' <span class="ev-confidence">' + confPct + '%</span>';
                tag.title = ev.reason || '';
                evidenceTagsEl.appendChild(tag);
            });
        } else {
            evidenceSection.style.display = 'none';
        }
    }

    // 丢弃标签
    const discardedSection = document.getElementById('card-discarded-section');
    const discardedTagsEl = document.getElementById('discarded-tags');
    if (discardedTagsEl) {
        discardedTagsEl.innerHTML = '';
        if (trace.discarded && trace.discarded.length > 0) {
            discardedSection.style.display = '';
            trace.discarded.forEach(ev => {
                const tag = document.createElement('span');
                tag.className = 'discarded-tag';
                tag.textContent = ev.title || ev.summary || '—';
                tag.title = ev.reason || '';
                discardedTagsEl.appendChild(tag);
            });
        } else {
            discardedSection.style.display = 'none';
        }
    }

    // 下一步
    const nextEl = document.getElementById('card-next-value');
    if (nextEl) {
        nextEl.textContent = trace.next || trace.decision || '—';
    }

    // 高亮卡片
    const cardEl = document.getElementById('decision-card');
    if (cardEl) {
        cardEl.classList.add('highlight');
        setTimeout(() => cardEl.classList.remove('highlight'), 2000);
    }
}

/**
 * 更新底部状态栏
 * @param {Object} trace - 决策轨迹或 RunInsight 数据
 */
function updateStatusBar(trace) {
    // Token
    const tokenUsed = trace.token_used || 0;
    const tokenBudget = trace.token_budget || 8000;
    if (tokenBudget > 0) {
        const pct = Math.min(100, (tokenUsed / tokenBudget) * 100);
        const tokenBarFill = document.getElementById('token-bar-fill-v2');
        if (tokenBarFill) {
            tokenBarFill.style.width = pct + '%';
            if (pct > 80) {
                tokenBarFill.classList.add('warning');
            } else {
                tokenBarFill.classList.remove('warning');
            }
        }
        const tokenValue = document.getElementById('token-value');
        if (tokenValue) {
            tokenValue.textContent = `${tokenUsed} / ${tokenBudget} (${Math.round(pct)}%)`;
        }
    }

    // Quality
    const qualityEl = document.getElementById('quality-value');
    if (qualityEl && trace.quality_score != null) {
        qualityEl.textContent = trace.quality_score.toFixed(2);
    }

    // 意图对齐
    const intentEl = document.getElementById('intent-value');
    if (intentEl && trace.intent_alignment_score != null) {
        intentEl.textContent = trace.intent_alignment_score.toFixed(2);
    }

    // 记忆命中
    const memoryEl = document.getElementById('memory-value');
    if (memoryEl && trace.memory_hit_rate != null) {
        memoryEl.textContent = (trace.memory_hit_rate * 100).toFixed(0) + '%';
    }
}

/**
 * 更新运行状态
 * @param {'idle' | 'running' | 'completed' | 'error'} status
 */
function updateRunStatus(status) {
    const dot = document.getElementById('status-dot-v2');
    const text = document.getElementById('status-text-v2');
    if (!dot || !text) return;

    dot.className = 'status-dot-v2';
    const statusMap = {
        idle: { cls: '', key: 'status_idle' },
        running: { cls: 'running', key: 'status_running' },
        completed: { cls: 'active', key: 'status_completed' },
        error: { cls: 'error', key: 'status_failed' },
    };
    const info = statusMap[status] || statusMap.idle;
    if (info.cls) dot.classList.add(info.cls);
    text.textContent = t(info.key);

    // 同时更新场景标签
    const avatarText = document.getElementById('avatar-status-text');
    if (avatarText) {
        if (status === 'running') {
            avatarText.textContent = t('avatar_working');
        } else if (status === 'idle') {
            avatarText.textContent = t('avatar_waiting');
        }
    }

    // 任务完成/失败时显示反馈区域
    if (status === 'completed' || status === 'error') {
        showFeedbackSection();
    }
}

/**
 * 更新 Avatar 状态文字
 * @param {Object} trace
 */
function updateAvatarStatus(trace) {
    const textEl = document.getElementById('avatar-status-text');
    if (textEl && trace.what) {
        textEl.textContent = trace.what;
    }
}

// ---------------------------------------------------------------------------
// 语言切换回调
// ---------------------------------------------------------------------------
window.addEventListener('localechange', (event) => {
    // 刷新所有 data-i18n 元素已在 i18n.js 中处理
    // 这里额外处理时间线中的节点标题
    const container = document.getElementById('timeline-list-v2');
    if (!container) return;

    container.querySelectorAll('.timeline-node').forEach(node => {
        const stage = node.dataset.stage;
        if (stage) {
            const titleEl = node.querySelector('.timeline-node-title');
            if (titleEl) {
                titleEl.textContent = getStageName(stage);
            }
        }
    });
});

// ---------------------------------------------------------------------------
// 用户反馈功能
// ---------------------------------------------------------------------------

/**
 * 显示反馈区域
 */
function showFeedbackSection() {
    const section = document.getElementById('feedback-section');
    if (section) {
        section.style.display = '';
    }
}

/**
 * 隐藏反馈区域
 */
function hideFeedbackSection() {
    const section = document.getElementById('feedback-section');
    if (section) {
        section.style.display = 'none';
    }
}

/**
 * 提交反馈
 * @param {string} type - 反馈类型（FEEDBACK_TYPES 之一）
 */
function submitFeedback(type) {
    // off_track 需要额外输入评论
    if (type === 'off_track' || type === 'not_specific' || type === 'no_executable_plan') {
        document.getElementById('feedback-comment').style.display = '';
        window._pendingFeedback = type;
        // 聚焦到评论输入框
        var input = document.getElementById('fb-comment-input');
        if (input) { setTimeout(function () { input.focus(); }, 100); }
        return;
    }
    sendFeedback(type, '');
}

/**
 * 带评论提交反馈
 */
function submitFeedbackWithComment() {
    const commentInput = document.getElementById('fb-comment-input');
    const comment = commentInput ? commentInput.value : '';
    const type = window._pendingFeedback || 'off_track';
    sendFeedback(type, comment);
    // 隐藏评论区域
    document.getElementById('feedback-comment').style.display = 'none';
    if (commentInput) { commentInput.value = ''; }
}

/**
 * 取消反馈评论
 */
function cancelFeedbackComment() {
    document.getElementById('feedback-comment').style.display = 'none';
    var input = document.getElementById('fb-comment-input');
    if (input) { input.value = ''; }
    window._pendingFeedback = null;
}

/**
 * 通过 fetch 发送反馈到 /api/feedback
 * @param {string} type - 反馈类型
 * @param {string} comment - 可选评论
 */
function sendFeedback(type, comment) {
    const fb = {
        run_id: window._currentRunId || currentRunId || '',
        signal_type: type,
        comment: comment,
    };

    // 按钮视觉反馈
    highlightFeedbackButton(type);

    // 通过 fetch 发送
    fetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(fb)
    }).then(function (r) { return r.json(); }).then(function (data) {
        if (data.ok) {
            // 显示感谢信息
            showFeedbackThanks();
            // 如果后端返回了 learning_evidence，更新面板
            if (data.learning_evidence) {
                updateLearningPanel(data.learning_evidence);
            }
        }
    }).catch(function (err) {
        console.error('[Dashboard V2] Feedback error:', err);
    });
}

/**
 * 高亮被点击的反馈按钮
 * @param {string} type
 */
function highlightFeedbackButton(type) {
    // 先移除所有高亮
    var buttons = document.querySelectorAll('.feedback-buttons .fb-btn');
    buttons.forEach(function (btn) {
        btn.classList.remove('fb-selected');
    });
    // 高亮当前
    var activeBtn = document.querySelector('.fb-btn.fb-' + type.replace(/_/g, '-'));
    if (activeBtn) {
        activeBtn.classList.add('fb-selected');
    }
}

/**
 * 显示感谢信息并渐隐反馈区域
 */
function showFeedbackThanks() {
    var thanks = document.getElementById('feedback-thanks');
    var buttons = document.getElementById('feedback-buttons');
    if (thanks) { thanks.style.display = ''; }
    if (buttons) { buttons.style.opacity = '0.4'; }
}

// ---------------------------------------------------------------------------
// RunInsight 总结卡片
// ---------------------------------------------------------------------------

/**
 * 更新 RunInsight 总结卡片
 * @param {Object} insight - RunInsight 数据
 */
function updateRunInsightCard(insight) {
    const card = document.getElementById('run-insight-card');
    if (!card) return;
    card.style.display = '';

    // 任务摘要
    const summaryEl = document.getElementById('insight-summary');
    if (summaryEl) {
        summaryEl.textContent = insight.task_summary_zh || insight.task_summary_en || '—';
    }

    // 最终结果
    const resultEl = document.getElementById('insight-result');
    if (resultEl) {
        resultEl.textContent = insight.final_result_zh || insight.final_result_en || '—';
    }

    // 质量评分
    const qualityEl = document.getElementById('insight-quality');
    if (qualityEl && insight.quality_score != null) {
        qualityEl.textContent = insight.quality_score.toFixed(2);
    }

    // 意图对齐
    const intentEl = document.getElementById('insight-intent');
    if (intentEl && insight.intent_alignment_score != null) {
        intentEl.textContent = insight.intent_alignment_score.toFixed(2);
    }

    // Token ROI
    const roiEl = document.getElementById('insight-roi');
    if (roiEl && insight.token_roi != null) {
        roiEl.textContent = insight.token_roi.toFixed(2);
    }

    // 记忆命中率
    const memoryEl = document.getElementById('insight-memory');
    if (memoryEl && insight.memory_hit_rate != null) {
        memoryEl.textContent = (insight.memory_hit_rate * 100).toFixed(0) + '%';
    }

    // 改进建议
    const improvementRow = document.getElementById('insight-improvement-row');
    const improvementEl = document.getElementById('insight-improvement');
    if (improvementRow && improvementEl) {
        const improvement = insight.improvement_summary_zh || insight.improvement_summary_en || '';
        if (improvement) {
            improvementRow.style.display = '';
            improvementEl.textContent = improvement;
        } else {
            improvementRow.style.display = 'none';
        }
    }

    // 失败原因
    const failureRow = document.getElementById('insight-failure-row');
    const failureEl = document.getElementById('insight-failure');
    if (failureRow && failureEl) {
        const failure = insight.failure_reason_zh || insight.failure_reason_en || '';
        if (failure) {
            failureRow.style.display = '';
            failureEl.textContent = failure;
        } else {
            failureRow.style.display = 'none';
        }
    }

    // 下次注意
    const nextRuleRow = document.getElementById('insight-next-rule-row');
    const nextRuleEl = document.getElementById('insight-next-rule');
    if (nextRuleRow && nextRuleEl) {
        const nextRule = insight.next_time_rule_zh || insight.next_time_rule_en || '';
        if (nextRule) {
            nextRuleRow.style.display = '';
            nextRuleEl.textContent = nextRule;
        } else {
            nextRuleRow.style.display = 'none';
        }
    }

    // 如果触发了学习，在卡片中标注
    if (insight.learning_triggered) {
        card.classList.add('has-learning');
    }
    if (insight.skill_updated) {
        card.classList.add('skill-updated');
    }
}
