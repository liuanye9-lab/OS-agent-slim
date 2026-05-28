/**
 * StableAgent OS V5.5 — 决策时间线组件
 * 管理决策时间线的节点增删改查。
 */

/** @type {string} */
let timelineContainerId = 'timeline-list-v2';

/** @type {Map<string, HTMLElement>} */
const timelineNodes = new Map();

/** @type {Array<Object>} */
let timelineData = [];

/**
 * 初始化时间线
 * @param {string} containerId - 容器元素 ID
 */
function initTimeline(containerId) {
    timelineContainerId = containerId;
    timelineNodes.clear();
    timelineData = [];
}

/**
 * 追加时间线节点
 * @param {Object} trace - 决策轨迹数据（来自 DashboardProjection.project_trace()）
 */
function addNode(trace) {
    // 只显示 importance >= normal 的节点
    const importanceLevels = { debug: 0, normal: 1, important: 2, critical: 3 };
    const importance = (trace.importance && trace.importance.level) || 'normal';
    if ((importanceLevels[importance] || 0) < (importanceLevels['normal'] || 1)) {
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

    // 图标
    const iconSpan = document.createElement('span');
    iconSpan.className = 'timeline-node-icon in_progress';
    iconSpan.textContent = '⏳';

    // 主体
    const body = document.createElement('div');
    body.className = 'timeline-node-body';

    const titleEl = document.createElement('div');
    titleEl.className = 'timeline-node-title';
    titleEl.textContent = trace.stage_title || getStageName(trace.stage);

    const descEl = document.createElement('div');
    descEl.className = 'timeline-node-desc';
    descEl.textContent = trace.what || '';

    const detailEl = document.createElement('pre');
    detailEl.className = 'timeline-node-detail';
    detailEl.textContent = JSON.stringify(trace.raw_payload || trace, null, 2);

    body.appendChild(titleEl);
    body.appendChild(descEl);
    body.appendChild(detailEl);
    node.appendChild(iconSpan);
    node.appendChild(body);

    // 点击展开详情
    node.addEventListener('click', () => {
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
    container.innerHTML = `
        <div class="timeline-empty-v2" id="timeline-empty-v2">
            <span data-i18n="timeline_waiting">等待决策事件...</span>
        </div>
    `;
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
        trace.importance = { level: 'important' };
        addNode(trace);
        updateNode('completed', 'done');
        return;
    }

    if (stage === 'failed') {
        updatePreviousNodes('failed');
        trace.importance = { level: 'critical' };
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

/**
 * 将指定阶段的所有 in_progress 节点标记为完成
 */
function markStageDone(stage) {
    const container = document.getElementById(timelineContainerId);
    if (!container) return;

    const nodes = container.querySelectorAll('.timeline-node');
    nodes.forEach(node => {
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
