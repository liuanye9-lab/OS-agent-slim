/**
 * StableAgent OS V5.5 — 自我优化证据面板
 * 展示技能学习触发状态、patch diff、验证分数等。
 */

/** @type {string} */
let learningPanelContainerId = 'learning-panel';

/**
 * 初始化学习面板
 * @param {string} containerId - 容器元素 ID
 */
function initLearningPanel(containerId) {
    learningPanelContainerId = containerId;
}

/**
 * 更新学习面板内容
 * @param {Object} evidence - 学习证据数据（来自 DashboardProjection.project_learning()）
 */
function updateLearningPanel(evidence) {
    const container = document.getElementById(learningPanelContainerId);
    if (!container) return;

    const contentEl = container.querySelector('.learning-content');
    const emptyEl = container.querySelector('.learning-empty');
    if (!contentEl || !emptyEl) return;

    if (!evidence || Object.keys(evidence).length === 0) {
        contentEl.style.display = 'none';
        emptyEl.style.display = '';
        return;
    }

    contentEl.style.display = '';
    emptyEl.style.display = 'none';

    const triggered = evidence.triggered === true;

    // 是否学习
    const triggeredEl = document.getElementById('learning-triggered');
    if (triggeredEl) {
        triggeredEl.textContent = triggered ? '✅' : '❌';
        triggeredEl.className = 'learning-value ' + (triggered ? 'triggered-yes' : 'triggered-no');
    }

    // 原因
    const reasonEl = document.getElementById('learning-reason');
    if (reasonEl) {
        reasonEl.textContent = evidence.reason || (triggered ? '—' : (evidence.no_learning_reason || '条件未满足'));
    }

    // Diff 展示
    const diffContentEl = document.getElementById('diff-content');
    if (diffContentEl) {
        if (evidence.has_patches && evidence.patches && evidence.patches.length > 0) {
            let diffHtml = '';
            evidence.patches.forEach(patch => {
                if (patch.diff) {
                    diffHtml += patch.diff + '\n';
                } else {
                    diffHtml += '<span class="diff-del">- ' + escapeHtml(patch.before || '') + '</span>\n';
                    diffHtml += '<span class="diff-ins">+ ' + escapeHtml(patch.after || '') + '</span>\n';
                }
            });
            diffContentEl.innerHTML = diffHtml || '—';
        } else if (evidence.diff_summary) {
            diffContentEl.textContent = evidence.diff_summary;
        } else {
            diffContentEl.textContent = '—';
        }
    }

    // 评分对比
    const baselineEl = document.getElementById('score-baseline');
    const candidateEl = document.getElementById('score-candidate');
    const deltaEl = document.getElementById('score-delta');

    if (baselineEl) {
        baselineEl.textContent = evidence.baseline_score != null
            ? evidence.baseline_score.toFixed(3) : '—';
    }
    if (candidateEl) {
        candidateEl.textContent = evidence.candidate_score != null
            ? evidence.candidate_score.toFixed(3) : '—';
    }
    if (deltaEl) {
        const delta = evidence.score_delta || 0;
        deltaEl.textContent = delta !== 0 ? (delta > 0 ? '+' : '') + delta.toFixed(3) : '0.000';
        deltaEl.className = 'score-value'
            + (delta > 0 ? ' positive' : '')
            + (delta < 0 ? ' negative' : '');
    }

    // 判定标签
    const verdictEl = document.getElementById('verdict-badge');
    if (verdictEl) {
        if (evidence.passed === true) {
            verdictEl.textContent = t('verdict_passed');
            verdictEl.className = 'verdict-badge passed';
        } else if (evidence.passed === false) {
            verdictEl.textContent = t('verdict_rejected');
            verdictEl.className = 'verdict-badge rejected';
        } else {
            verdictEl.textContent = t('verdict_pending');
            verdictEl.className = 'verdict-badge pending';
        }
    }
}

/**
 * 清空学习面板
 */
function clearLearningPanel() {
    const container = document.getElementById(learningPanelContainerId);
    if (!container) return;

    const contentEl = container.querySelector('.learning-content');
    const emptyEl = container.querySelector('.learning-empty');
    if (contentEl) contentEl.style.display = 'none';
    if (emptyEl) emptyEl.style.display = '';
}

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
