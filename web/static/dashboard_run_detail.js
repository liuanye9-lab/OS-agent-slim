/**
 * SaaS v1.3 — Dashboard Run 详情面板
 *
 * 功能：
 * 1. 从 /api/runs/{run_id}/detail 获取 Run 完整数据
 * 2. 渲染 Trace 时间线
 * 3. 渲染 Eval 评分卡片
 * 4. 自动刷新（每 5 秒）
 */
(function () {
  'use strict';
  let _pollTimer = null;
  let _currentRunId = '';

  // ------------------------------------------------------------------
  // 初始化：监听 run_id 变更
  // ------------------------------------------------------------------
  const meta = document.querySelector('meta[name="run-id"]');
  if (meta) {
    _currentRunId = meta.getAttribute('content') || '';
  }

  // 也支持通过 URL hash 指定: #run=xxx
  function getRunIdFromHash() {
    const h = window.location.hash;
    if (h.startsWith('#run=')) return h.slice(5);
    return '';
  }

  window.addEventListener('hashchange', () => {
    const id = getRunIdFromHash();
    if (id && id !== _currentRunId) {
      _currentRunId = id;
      loadRunDetail(id);
      startPolling(id);
    }
  });

  // 页面加载
  if (_currentRunId) {
    loadRunDetail(_currentRunId);
    startPolling(_currentRunId);
  } else {
    const hashId = getRunIdFromHash();
    if (hashId) {
      _currentRunId = hashId;
      loadRunDetail(hashId);
      startPolling(hashId);
    }
  }

  // 暴露到 window 以便外部调用
  window.showRunDetail = function (runId) {
    if (!runId) return;
    _currentRunId = runId;
    window.location.hash = 'run=' + runId;
    loadRunDetail(runId);
    startPolling(runId);
  };

  // ------------------------------------------------------------------
  // 轮询
  // ------------------------------------------------------------------
  function startPolling(runId) {
    if (_pollTimer) clearInterval(_pollTimer);
    _pollTimer = setInterval(() => loadRunDetail(runId, true), 5000);
  }

  // ------------------------------------------------------------------
  // 加载 Run 详情
  // ------------------------------------------------------------------
  function loadRunDetail(runId, silent) {
    Promise.all([
      fetch('/api/runs/' + runId + '/events').then(r => r.json()).catch(() => []),
      fetch('/api/runs/' + runId).then(r => r.json()).catch(() => null),
    ]).then(function (_ref) {
      var events = _ref[0];
      var runData = _ref[1];
      renderRunDetail(runId, runData, events);
    }).catch(function () {
      if (!silent) console.warn('Failed to load run detail for', runId);
    });
  }

  // ------------------------------------------------------------------
  // 渲染
  // ------------------------------------------------------------------
  function renderRunDetail(runId, runData, events) {
    var panel = document.getElementById('run-detail-panel');
    if (!panel) return;
    if (!runData || runData.error) {
      panel.innerHTML = '<div class="glass-card" style="padding:16px;text-align:center;color:var(--text-muted);">暂无运行数据</div>';
      return;
    }

    var statusEmoji = { created: '⚪', running: '🟢', completed: '✅', failed: '❌', cancelled: '⏹️' };
    var emoji = statusEmoji[runData.status] || '⚪';
    var scoreHtml = runData.overall_score != null
      ? '<span style="color:var(--accent);font-weight:700;">评分: ' + (runData.overall_score * 100).toFixed(0) + '%</span>'
      : '';

    var html = '<div class="glass-card" style="padding:16px;margin-bottom:12px;">'
      + '<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">'
      + '<div><span style="font-size:1.1rem;font-weight:700;">' + emoji + ' Run ' + runId.slice(0, 16) + '...</span></div>'
      + '<div style="display:flex;gap:12px;align-items:center;">'
      + '<span class="status-badge" style="background:var(--glass-bg);padding:4px 10px;border-radius:8px;">' + runData.status + '</span>'
      + scoreHtml
      + '<span style="font-size:0.85rem;">Token: ' + (runData.token_used || 0).toLocaleString() + '</span>'
      + '</div></div></div>';

    // Trace 时间线
    if (events && events.length) {
      html += '<div class="glass-card" style="padding:12px 16px;max-height:400px;overflow-y:auto;">';
      html += '<div style="font-weight:600;margin-bottom:8px;">📋 执行时间线 <span style="font-size:0.8rem;color:var(--text-muted);">(' + events.length + ' 个事件)</span></div>';
      html += '<div class="trace-timeline">';
      var shown = events.slice(-30); // 最近 30 个
      for (var i = 0; i < shown.length; i++) {
        var ev = shown[i];
        var icon = '📌';
        if (ev.event_type && ev.event_type.includes('started')) icon = '▶️';
        if (ev.event_type && ev.event_type.includes('completed')) icon = '✅';
        if (ev.event_type && ev.event_type.includes('failed')) icon = '❌';
        if (ev.event_type && ev.event_type.includes('decision')) icon = '🧠';
        if (ev.status_text_zh) icon = '💬';
        html += '<div class="trace-item" style="display:flex;gap:8px;padding:4px 0;font-size:0.85rem;border-bottom:1px solid var(--glass-border);">'
          + '<span>' + icon + '</span>'
          + '<span style="flex:1;">' + (ev.status_text_zh || ev.plain_text || ev.event_type || '') + '</span>'
          + '<span style="color:var(--text-muted);font-size:0.75rem;">' + (ev.progress_pct != null ? ev.progress_pct + '%' : '') + '</span>'
          + '</div>';
      }
      html += '</div></div>';
    }

    // 进度条
    html += '<div class="glass-card" style="padding:12px 16px;margin-top:8px;">'
      + '<div style="font-weight:600;margin-bottom:4px;">进度</div>'
      + '<div style="background:var(--glass-bg);border-radius:8px;height:8px;overflow:hidden;">'
      + '<div style="width:' + (runData.progress_pct || 0) + '%;height:100%;background:linear-gradient(90deg,var(--accent),var(--accent-alt));transition:width 0.5s;border-radius:8px;"></div>'
      + '</div>'
      + '<div style="text-align:right;font-size:0.8rem;color:var(--text-muted);">' + (runData.progress_pct || 0) + '%</div>'
      + '</div>';

    panel.innerHTML = html;
  }
})();
