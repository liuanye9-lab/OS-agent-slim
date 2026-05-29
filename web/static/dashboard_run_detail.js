/**
 * Commercial SaaS v2.1 — Dashboard Run 详情面板
 *
 * 功能：
 * 1. 从 /api/runs/{run_id}/detail 获取 Run 完整数据
 * 2. 渲染 RunLifecycle 20 阶段进度条
 * 3. 渲染 Trace 时间线
 * 4. 渲染 Eval 评分卡片 + DecisionTrace 决策说明
 * 5. 自动刷新（每 3 秒）
 */
(function () {
  'use strict';
  var _pollTimer = null;
  var _currentRunId = '';

  // RunLifecycle 20 阶段中文映射
  var STAGE_LABELS = {
    created: '已创建', received: '接收任务', intent_parsing: '理解意图',
    context_budgeting: '估算预算', memory_retrieving: '检索记忆',
    rag_retrieving: '检索资料', context_building: '构建上下文',
    planning: '规划步骤', acting: '执行中', observing: '观察结果',
    evaluating: '评估质量', failure_attribution: '分析失败原因',
    regression_generation: '生成回归用例', skill_patch_proposal: '生成Skill补丁',
    validation: '验证补丁', human_review: '等待人工审核',
    exporting: '导出best_skill', completed: '完成', failed: '失败', cancelled: '已取消'
  };

  // RunLifecycle 阶段 → 进度百分比
  var STAGE_PROGRESS = {
    created:0,received:5,intent_parsing:10,context_budgeting:20,
    memory_retrieving:30,rag_retrieving:40,context_building:50,
    planning:60,acting:70,observing:78,evaluating:85,
    failure_attribution:90,regression_generation:93,
    skill_patch_proposal:95,validation:97,human_review:98,
    exporting:99,completed:100,failed:-1,cancelled:-1
  };

  var _events = [];

  // 初始化
  var meta = document.querySelector('meta[name="run-id"]');
  if (meta) _currentRunId = meta.getAttribute('content') || '';

  window.addEventListener('hashchange', function () {
    var id = getRunIdFromHash();
    if (id && id !== _currentRunId) { _currentRunId = id; loadRunDetail(id); startPolling(id); }
  });

  if (_currentRunId) { loadRunDetail(_currentRunId); startPolling(_currentRunId); }
  else { var hashId = getRunIdFromHash(); if (hashId) { _currentRunId = hashId; loadRunDetail(hashId); startPolling(hashId); } }

  function getRunIdFromHash() {
    var h = window.location.hash;
    return h.startsWith('#run=') ? h.slice(5) : '';
  }

  window.showRunDetail = function (runId) {
    if (!runId) return;
    _currentRunId = runId;
    window.location.hash = 'run=' + runId;
    loadRunDetail(runId);
    startPolling(runId);
  };

  function startPolling(runId) {
    if (_pollTimer) clearInterval(_pollTimer);
    _pollTimer = setInterval(function () { loadRunDetail(runId, true); }, 3000);
  }

  function loadRunDetail(runId, silent) {
    Promise.all([
      fetch('/api/runs/' + runId + '/events').then(function (r) { return r.json(); }).catch(function () { return []; }),
      fetch('/api/runs/' + runId).then(function (r) { return r.json(); }).catch(function () { return null; }),
    ]).then(function (data) {
      var events = data[0], runData = data[1];
      _events = events || [];
      renderRunDetail(runId, runData, _events);
    }).catch(function () {
      if (!silent) console.warn('Failed to load run detail for', runId);
    });
  }

  function renderRunDetail(runId, runData, events) {
    var panel = document.getElementById('run-detail-panel');
    if (!panel) return;
    if (!runData || runData.error) {
      panel.innerHTML = '<div class="glass-card" style="padding:16px;text-align:center;color:var(--text-muted);">暂无运行数据</div>';
      return;
    }

    var currentStage = runData.current_stage || 'created';
    var stageLabel = STAGE_LABELS[currentStage] || currentStage;
    var pct = typeof runData.progress_pct === 'number' ? runData.progress_pct : STAGE_PROGRESS[currentStage] || 0;
    var statusEmoji = { completed: '✅', failed: '❌', cancelled: '⏹️' };
    var emoji = statusEmoji[runData.status] || (pct >= 100 ? '✅' : '🟢');

    var html = '';
    // 概要卡片
    html += '<div class="glass-card" style="padding:12px 16px;margin-bottom:10px;">';
    html += '<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">';
    html += '<div><span style="font-size:1.1rem;font-weight:700;">' + emoji + ' Run ' + runId.slice(0, 14) + '...</span></div>';
    html += '<div style="display:flex;gap:10px;align-items:center;font-size:0.85rem;">';
    html += '<span>' + stageLabel + '</span>';
    html += '<span style="color:var(--accent);font-weight:700;">' + pct + '%</span>';
    html += '<span>Token: ' + (runData.token_used || 0).toLocaleString() + '</span>';
    html += '</div></div></div>';

    // RunLifecycle 阶段进度条（精简版：显示核心阶段）
    var allStages = ['received','intent_parsing','context_budgeting','memory_retrieving','context_building','planning','acting','evaluating','completed'];
    html += '<div class="glass-card" style="padding:10px 16px;margin-bottom:10px;">';
    html += '<div style="font-weight:600;margin-bottom:4px;font-size:0.85rem;">📊 RunLifecycle 进度</div>';
    html += '<div style="display:flex;gap:2px;align-items:flex-end;height:32px;">';
    var currentStageIdx = allStages.indexOf(currentStage);
    if (currentStageIdx < 0) currentStageIdx = allStages.length;
    for (var i = 0; i < allStages.length; i++) {
      var s = allStages[i];
      var sPct = STAGE_PROGRESS[s] || 0;
      var active = i <= currentStageIdx;
      var color = active ? 'var(--accent)' : 'var(--glass-border)';
      var height = active ? 28 : 14;
      html += '<div title="' + (STAGE_LABELS[s]||s) + ' (' + sPct + '%)" style="flex:1;background:' + color + ';height:' + height + 'px;border-radius:3px;cursor:pointer;transition:all 0.3s;"></div>';
    }
    html += '</div>';
    html += '<div style="text-align:right;font-size:0.75rem;color:var(--text-muted);margin-top:2px;">' + pct + '% — ' + stageLabel + '</div>';
    html += '</div>';

    // 为什么这样做（DecisionTrace）
    if (runData.decision_summary_zh || runData.why_zh) {
      html += '<div class="glass-card" style="padding:10px 16px;margin-bottom:10px;font-size:0.85rem;">';
      html += '<div style="font-weight:600;">🧠 为什么这样做</div>';
      if (runData.decision_summary_zh) html += '<div style="margin-top:4px;">' + runData.decision_summary_zh + '</div>';
      if (runData.why_zh) html += '<div style="color:var(--text-muted);margin-top:2px;">' + runData.why_zh + '</div>';
      html += '</div>';
    }

    // Eval 评分
    if (runData.overall_score != null || runData.intent_alignment_score != null) {
      html += '<div class="glass-card" style="padding:10px 16px;margin-bottom:10px;">';
      html += '<div style="font-weight:600;margin-bottom:4px;font-size:0.85rem;">📝 Eval 评分</div>';
      html += '<div style="display:flex;gap:16px;flex-wrap:wrap;">';
      if (runData.overall_score != null) html += '<div><span style="font-size:0.8rem;color:var(--text-muted);">综合</span><br><b>' + (runData.overall_score * 100).toFixed(0) + '%</b></div>';
      if (runData.intent_alignment_score != null) html += '<div><span style="font-size:0.8rem;color:var(--text-muted);">意图对齐</span><br><b>' + (runData.intent_alignment_score * 100).toFixed(0) + '%</b></div>';
      html += '</div></div>';
    }

    // 时间线（最近事件）
    if (events && events.length) {
      var shown = events.slice(-20);
      html += '<div class="glass-card" style="padding:10px 16px;max-height:300px;overflow-y:auto;">';
      html += '<div style="font-weight:600;margin-bottom:4px;font-size:0.85rem;">📋 事件时间线 (' + events.length + ')</div>';
      for (var j = shown.length - 1; j >= 0; j--) {
        var ev = shown[j];
        var icon = '📌';
        if (ev.event_type && ev.event_type.indexOf('completed') >= 0) icon = '✅';
        if (ev.event_type && ev.event_type.indexOf('failed') >= 0) icon = '❌';
        if (ev.event_type && ev.event_type.indexOf('approval') >= 0) icon = '⏳';
        html += '<div style="display:flex;gap:6px;padding:3px 0;font-size:0.8rem;border-bottom:1px solid var(--glass-border);">';
        html += '<span>' + icon + '</span>';
        html += '<span style="flex:1;">' + (ev.status_text_zh || ev.stage_label_zh || ev.event_type || '') + '</span>';
        html += '<span style="color:var(--text-muted);font-size:0.7rem;">' + (ev.progress_pct != null ? ev.progress_pct + '%' : '') + '</span>';
        html += '</div>';
      }
      html += '</div>';
    }

    panel.innerHTML = html;
  }
})();
