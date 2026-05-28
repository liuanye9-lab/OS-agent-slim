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
        // RunInsight 数据
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
