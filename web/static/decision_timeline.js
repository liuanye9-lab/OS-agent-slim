/**
 * StableAgent OS V5.6 — 决策时间线组件
 *
 * 升级要点：
 * - 重要性边框：critical=红色, important=黄色, normal=无特殊样式
 * - 决策卡片包含「为什么这么做」和「丢弃了什么」两个区域
 * - 调试事件（importance < normal）默认不展示（进抽屉）
 * - 点击节点展开专业详情（JSON payload）
 */

/** @type {string} */
let timelineContainerId = 'timeline-list-v2';

/** @type {Map<string, HTMLElement>} */
const timelineNodes = new Map();

/** @type {Array<Object>} */
let timelineData = [];

/** @type {Array<Object>} 调试抽屉中暂存的事件 */
let debugDrawerEvents = [];

/**
 * 初始化时间线
 * @param {string} containerId - 容器元素 ID
 */
function initTimeline(containerId) {
    timelineContainerId = containerId;
    timelineNodes.clear();
    timelineData = [];
    debugDrawerEvents = [];
}

/**
 * 追加时间线节点
 * @param {Object} trace - 决策轨迹数据（来自 DashboardProjection.project_trace()）
 */
function addNode(trace) {
    // 只显示 importance >= normal 的节点；debug 事件进抽屉
    const importanceLevels = { debug: 0, normal: 1, important: 2, critical: 3 };
    const importance = (trace.importance && trace.importance.level) || 'normal';
    if ((importanceLevels[importance] || 0) < (importanceLevels['normal'] || 1)) {
        // 进抽屉
        debugDrawerEvents.push({ id: trace.id || `${trace.stage}-${Date.now()}`, trace, addedAt: Date.now() });
        _updateDebugDrawerBadge();
        return;
    }

    const container = document.getElementById(timelineContainerId);
    if (!container) return;

    const emptyEl = container.querySelector('.timeline-empty-v2');
    if (emptyEl) emptyEl.style.display = 'none';

    const nodeId = trace.id || `${trace.stage}-${Date.now()}`;

    const node = document.createElement('div');
    node.className = 'timeline-node';
    node.dataset.nodeId = nodeId;
    node.dataset.stage = trace.stage;
    node.dataset.status = 'in_progress';
    node.dataset.importance = importance;

    // ---- 重要性边框样式 ----
    if (importance === 'critical') {
        node.classList.add('timeline-node-critical');
    } else if (importance === 'important') {
        node.classList.add('timeline-node-important');
    }

    // 图标
    const iconSpan = document.createElement('span');
    iconSpan.className = 'timeline-node-icon in_progress';
    iconSpan.textContent = '⏳';

    // 主体
    const body = document.createElement('div');
    body.className = 'timeline-node-body';

    // 阶段标题
    const titleEl = document.createElement('div');
    titleEl.className = 'timeline-node-title';
    titleEl.textContent = trace.stage_title || getStageName(trace.stage);

    // What 区域
    const whatEl = document.createElement('div');
    whatEl.className = 'timeline-node-what';
    whatEl.textContent = trace.what || '';

    // ---- 「为什么这么做」区域 ----
    const whyEl = document.createElement('div');
    whyEl.className = 'timeline-node-why';
    const whyLabel = document.createElement('span');
    whyLabel.className = 'timeline-node-section-label';
    whyLabel.textContent = '为什么这么做';
    const whyContent = document.createElement('span');
    whyContent.className = 'timeline-node-section-content';
    whyContent.textContent = trace.why || (trace.decision_trace && trace.decision_trace.why_zh) || '—';
    whyEl.appendChild(whyLabel);
    whyEl.appendChild(whyContent);

    // ---- 「丢弃了什么」区域 ----
    const discardedEl = document.createElement('div');
    discardedEl.className = 'timeline-node-discarded';
    const discardedLabel = document.createElement('span');
    discardedLabel.className = 'timeline-node-section-label';
    discardedLabel.textContent = '丢弃了什么';
    const discardedContent = document.createElement('span');
    discardedContent.className = 'timeline-node-section-content';
    const discardedData = trace.discarded || (trace.decision_trace && trace.decision_trace.discarded_evidence);
    if (discardedData && Array.isArray(discardedData) && discardedData.length > 0) {
        discardedContent.textContent = discardedData
            .map(function(d) { return d.title || d.summary || JSON.stringify(d); })
            .join('；');
    } else if (discardedData && typeof discardedData === 'string') {
        discardedContent.textContent = discardedData;
    } else {
        discardedContent.textContent = '—';
    }
    discardedEl.appendChild(discardedLabel);
    discardedEl.appendChild(discardedContent);

    // 可折叠的详情（JSON payload）
    const detailEl = document.createElement('pre');
    detailEl.className = 'timeline-node-detail';
    detailEl.textContent = JSON.stringify(trace.raw_payload || trace, null, 2);

    body.appendChild(titleEl);
    body.appendChild(whatEl);
    body.appendChild(whyEl);
    body.appendChild(discardedEl);
    body.appendChild(detailEl);
    node.appendChild(iconSpan);
    node.appendChild(body);

    // 点击展开详情
    node.addEventListener('click', function(e) {
        // 如果点击的是原因/丢弃区域内部，不折叠
        if (e.target.closest('.timeline-node-why') || e.target.closest('.timeline-node-discarded')) {
            return;
        }
        node.classList.toggle('expanded');
    });

    container.appendChild(node);
    timelineNodes.set(nodeId, node);
    timelineData.push({ id: nodeId, trace });

    // 滚动到底部
    container.scrollTop = container.scrollHeight;
}

/**
 * 更新节点状态
 * @param {string} stage - 阶段名
 * @param {'pending' | 'in_progress' | 'done' | 'failed'} status
 */
function updateNode(stage, status) {
    const iconMap = {
        pending: { icon: '⏸️', cls: 'pending' },
        in_progress: { icon: '⏳', cls: 'in_progress' },
        done: { icon: '✅', cls: 'done' },
        failed: { icon: '❌', cls: 'failed' },
    };

    const info = iconMap[status] || iconMap.pending;

    // 找到最后一个该 stage 的节点
    const container = document.getElementById(timelineContainerId);
    if (!container) return;

    const nodes = container.querySelectorAll('.timeline-node');
    let targetNode = null;
    nodes.forEach(node => {
        if (node.dataset.stage === stage) {
            targetNode = node;
        }
    });

    if (!targetNode) return;
    targetNode.dataset.status = status;

    const iconEl = targetNode.querySelector('.timeline-node-icon');
    if (iconEl) {
        iconEl.className = 'timeline-node-icon ' + info.cls;
        iconEl.textContent = info.icon;
    }
}

/**
 * 高亮当前进行中的节点
 * @param {string} stage - 当前阶段名
 */
function highlightNode(stage) {
    const container = document.getElementById(timelineContainerId);
    if (!container) return;

    // 移除所有高亮
    container.querySelectorAll('.timeline-node.highlight').forEach(node => {
        node.classList.remove('highlight');
    });

    // 高亮匹配节点
    const nodes = container.querySelectorAll('.timeline-node');
    nodes.forEach(node => {
        if (node.dataset.stage === stage) {
            node.classList.add('highlight');
        }
    });
}

/**
 * 清空时间线
 */
function clearTimelineV2() {
    const container = document.getElementById(timelineContainerId);
    if (!container) return;

    timelineNodes.clear();
    timelineData = [];
    container.innerHTML = [
        '<div class="timeline-empty-v2" id="timeline-empty-v2">',
        '  <span data-i18n="timeline_waiting">等待决策事件...</span>',
        '</div>',
    ].join('');
}

/**
 * 根据 trace 自动处理节点添加、更新和高亮
 * @param {Object} trace - 决策轨迹数据
 */
function handleTrace(trace) {
    const stage = trace.stage;

    // 已完成/失败的阶段 — 更新节点状态
    if (stage === 'completed') {
        // 标记前一个节点为完成
        updatePreviousNodes('done');
        // 添加完成节点
        trace.importance = trace.importance || { level: 'important' };
        addNode(trace);
        updateNode('completed', 'done');
        return;
    }

    if (stage === 'failed') {
        updatePreviousNodes('failed');
        trace.importance = trace.importance || { level: 'critical' };
        addNode(trace);
        updateNode('failed', 'failed');
        return;
    }

    // 将当前 stage 已有的 in_progress 节点标记为完成
    markStageDone(stage);

    // 添加新节点
    addNode(trace);

    // 高亮当前节点
    highlightNode(stage);
}

// ---------------------------------------------------------------------------
// 内部辅助
// ---------------------------------------------------------------------------

/** 阶段名映射表 */
const _STAGE_NAMES = {
    task_intake: '任务接收', intent_parse: '意图解析', context_budget: '预算估算',
    memory_retrieval: '记忆检索', rag_retrieval: '知识检索', context_build: '上下文构建',
    planning: '规划', tool_call: '工具调用', security_check: '安全检查',
    approval_waiting: '等待审批', execution: '执行', evaluation: '评估',
    badcase_record: '失败记录', skill_learning: '技能学习', skill_validation: '技能验证',
    skill_export: '技能导出', completed: '完成', failed: '失败',
};

/**
 * 根据阶段名获取可读标题
 * @param {string} stage
 * @returns {string}
 */
function getStageName(stage) {
    return _STAGE_NAMES[stage] || stage;
}

/**
 * 将指定阶段的所有 in_progress 节点标记为完成
 */
function markStageDone(stage) {
    const container = document.getElementById(timelineContainerId);
    if (!container) return;

    const nodes = container.querySelectorAll('.timeline-node');
    nodes.forEach(function(node) {
        if (node.dataset.stage === stage && node.dataset.status === 'in_progress') {
            node.dataset.status = 'done';
            const iconEl = node.querySelector('.timeline-node-icon');
            if (iconEl) {
                iconEl.className = 'timeline-node-icon done';
                iconEl.textContent = '✅';
            }
        }
    });
}

/**
 * 将最近一个 in_progress 节点标记为指定状态
 */
function updatePreviousNodes(status) {
    const container = document.getElementById(timelineContainerId);
    if (!container) return;

    const iconMap = {
        done: { icon: '✅', cls: 'done' },
        failed: { icon: '❌', cls: 'failed' },
    };
    const info = iconMap[status] || { icon: '✅', cls: 'done' };

    const nodes = container.querySelectorAll('.timeline-node');
    // 从后往前找最后一个 in_progress
    for (let i = nodes.length - 1; i >= 0; i--) {
        if (nodes[i].dataset.status === 'in_progress') {
            nodes[i].dataset.status = status;
            const iconEl = nodes[i].querySelector('.timeline-node-icon');
            if (iconEl) {
                iconEl.className = 'timeline-node-icon ' + info.cls;
                iconEl.textContent = info.icon;
            }
            break;
        }
    }
}

// ---------------------------------------------------------------------------
// 调试抽屉
// ---------------------------------------------------------------------------

/**
 * 更新调试抽屉徽章计数
 */
function _updateDebugDrawerBadge() {
    const badge = document.getElementById('debug-drawer-badge');
    if (badge) {
        badge.textContent = String(debugDrawerEvents.length);
        badge.style.display = debugDrawerEvents.length > 0 ? 'inline' : 'none';
    }
}

/**
 * 打开调试抽屉，展示所有 debug 级别事件
 */
function openDebugDrawer() {
    const drawer = document.getElementById('debug-drawer');
    if (!drawer) return;

    const list = drawer.querySelector('.debug-drawer-list');
    if (!list) return;

    // 渲染所有 debug 事件
    list.innerHTML = '';
    if (debugDrawerEvents.length === 0) {
        list.innerHTML = '<div class="debug-drawer-empty">暂无调试事件</div>';
    } else {
        debugDrawerEvents.forEach(function(ev) {
            const item = document.createElement('div');
            item.className = 'debug-drawer-item';

            const title = document.createElement('div');
            title.className = 'debug-drawer-item-title';
            title.textContent = (ev.trace.stage_title || getStageName(ev.trace.stage)) + ' (debug)';

            const detail = document.createElement('pre');
            detail.className = 'debug-drawer-item-detail';
            detail.textContent = JSON.stringify(ev.trace.raw_payload || ev.trace, null, 2);

            item.appendChild(title);
            item.appendChild(detail);
            item.addEventListener('click', function() {
                item.classList.toggle('expanded');
            });
            list.appendChild(item);
        });
    }

    drawer.classList.add('open');
}

/**
 * 关闭调试抽屉
 */
function closeDebugDrawer() {
    const drawer = document.getElementById('debug-drawer');
    if (drawer) {
        drawer.classList.remove('open');
    }
}

/**
 * 清空调试抽屉
 */
function clearDebugDrawer() {
    debugDrawerEvents = [];
    _updateDebugDrawerBadge();
    const list = document.querySelector('.debug-drawer-list');
    if (list) {
        list.innerHTML = '<div class="debug-drawer-empty">暂无调试事件</div>';
    }
}
