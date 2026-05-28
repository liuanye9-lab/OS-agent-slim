/**
 * StableAgent OS V5.5 — 自我优化证据面板
 * 展示技能学习触发状态、patch diff、验证分数等。
 *
 * 增强功能：
 * - 展示「本轮是否触发学习」
 * - 未触发时显示 explain_no_learning 的原因文本
 * - 触发时展示 before/after diff
 * - 收集了多少 rollout、发现了什么规律、通过/拒绝的 patch 数
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

    // ── 是否触发学习 ──────────────────────────────────────────────
    const triggeredEl = document.getElementById('learning-triggered');
    if (triggeredEl) {
        triggeredEl.textContent = triggered ? '✅' : '❌';
        triggeredEl.className = 'learning-value ' + (triggered ? 'triggered-yes' : 'triggered-no');
    }

    // ── 原因 / 发现规律：触发时显示发现规律；未触发时显示 explain_no_learning ──
    const reasonLabelEl = document.getElementById('learning-reason-label');
    const reasonEl = document.getElementById('learning-reason');
    if (reasonEl) {
        if (triggered) {
            // 触发学习：显示发现规律描述
            reasonEl.textContent = evidence.reason_zh
                || evidence.reason
                || evidence.diff_summary
                || '触发了技能学习';
            if (reasonLabelEl) {
                reasonLabelEl.textContent = t('learning_finding') || '发现规律';
            }
        } else {
            // 未触发：显示 explain_no_learning 原因
            reasonEl.textContent = evidence.reason_zh
                || evidence.reason
                || evidence.no_learning_reason
                || '学习触发条件未满足';
            if (reasonLabelEl) {
                reasonLabelEl.textContent = t('learning_reason') || '未触发原因';
            }
        }
    }

    // ── Rollout 统计信息 ───────────────────────────────────────────
    const rolloutEl = document.getElementById('learning-rollout-count');
    if (rolloutEl) {
        rolloutEl.textContent = evidence.rollout_count != null
            ? String(evidence.rollout_count) : '—';
    }

    const rolloutSection = document.getElementById('learning-rollout-section');
    if (rolloutSection) {
        rolloutSection.style.display = (evidence.rollout_count != null) ? '' : 'none';
    }

    // ── Patch 通过/拒绝统计 ────────────────────────────────────────
    const patchAcceptedEl = document.getElementById('learning-patch-accepted');
    const patchRejectedEl = document.getElementById('learning-patch-rejected');
    const patchTotalEl = document.getElementById('learning-patch-total');

    if (patchAcceptedEl) {
        patchAcceptedEl.textContent = evidence.patches_accepted != null
            ? String(evidence.patches_accepted) : '—';
    }
    if (patchRejectedEl) {
        patchRejectedEl.textContent = evidence.patches_rejected != null
            ? String(evidence.patches_rejected) : '—';
    }
    if (patchTotalEl) {
        const total = evidence.patches_total != null
            ? evidence.patches_total
            : ((evidence.patches && evidence.patches.length) || 0);
        patchTotalEl.textContent = total > 0 ? String(total) : '—';
    }

    // ── Diff 展示 ──────────────────────────────────────────────────
    const diffContentEl = document.getElementById('diff-content');
    if (diffContentEl) {
        if (evidence.has_patches && evidence.patches && evidence.patches.length > 0) {
            let diffHtml = '';
            evidence.patches.forEach(function (patch) {
                if (patch.diff) {
                    // 预格式化的 diff 文本
                    diffHtml += '<pre class="diff-block">' + escapeHtml(patch.diff) + '</pre>';
                } else {
                    // before/after 对比
                    diffHtml += '<div class="diff-pair">';
                    diffHtml += '<div class="diff-before"><span class="diff-label">- Before</span><pre>'
                        + escapeHtml(patch.before || '') + '</pre></div>';
                    diffHtml += '<div class="diff-after"><span class="diff-label">+ After</span><pre>'
                        + escapeHtml(patch.after || '') + '</pre></div>';
                    diffHtml += '</div>';
                }
            });
            diffContentEl.innerHTML = diffHtml || '—';
        } else if (triggered && evidence.diff_summary) {
            // 触发了学习但没有 patch 详情，显示摘要
            diffContentEl.textContent = evidence.diff_summary;
        } else if (!triggered) {
            // 未触发学习：不展示 diff
            diffContentEl.textContent = '—（本轮未触发学习）';
        } else {
            diffContentEl.textContent = '—';
        }
    }

    // ── 评分对比 ──────────────────────────────────────────────────
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

    // ── 判定标签 ──────────────────────────────────────────────────
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

/**
 * HTML 转义辅助函数
 * @param {string} str
 * @returns {string}
 */
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
