// dashboard_v3.js — V6.5 Dashboard 实时同步核心
(function() {
  'use strict';

  const AVATAR_SCENE_MAP = {
    listening:      { prop: '📥', labelZh: '接收任务',    labelEn: 'Receiving task',     descZh: '它刚收到一个新任务。' },
    thinking:       { prop: '🔎', labelZh: '理解需求',    labelEn: 'Understanding intent', descZh: '它正在判断你真正想要什么。' },
    calculating:    { prop: '🧮', labelZh: '计算预算',    labelEn: 'Estimating budget',   descZh: '它正在判断这次应该花多少 token。' },
    reading_notes:  { prop: '🗂️', labelZh: '查找记忆',    labelEn: 'Retrieving memory',   descZh: '它正在找以前的相关经验。' },
    searching_books:{ prop: '📚', labelZh: '查找资料',    labelEn: 'Searching knowledge',  descZh: '它正在从项目资料里找有用内容。' },
    organizing:     { prop: '🧩', labelZh: '整理上下文',  labelEn: 'Building context',     descZh: '它正在把有用信息打包。' },
    planning:       { prop: '🗺️', labelZh: '规划步骤',    labelEn: 'Planning steps',      descZh: '它正在决定先做什么、后做什么。' },
    tooling:        { prop: '🔧', labelZh: '调用工具',    labelEn: 'Calling tools',       descZh: '它正在调用外部工具执行任务。' },
    grading:        { prop: '📝', labelZh: '评估结果',    labelEn: 'Evaluating',           descZh: '它正在检查结果是否达标。' },
    learning:       { prop: '📖', labelZh: '总结经验',    labelEn: 'Learning',             descZh: '它正在把这次经验沉淀下来。' },
    done:           { prop: '✅', labelZh: '完成任务',    labelEn: 'Completed',            descZh: '任务已经完成。' },
    failed:         { prop: '⚠️', labelZh: '任务失败',    labelEn: 'Failed',               descZh: '任务失败，正在记录原因。' },
  };

  let ws = null;
  let currentRunId = null;
  let events = [];
  let runCompleted = false;

  // ====== 初始化 ======
  function init() {
    const runId = getRunIdFromUrl();
    if (runId) {
      currentRunId = runId;
      document.getElementById('run-id-display').textContent = 'run_id: ' + runId;
      loadHistory(runId).then(() => connectWs(runId));
    } else {
      document.getElementById('run-id-display').textContent = '等待 MCP 调用...';
    }
    initFeedbackButtons();
  }

  function getRunIdFromUrl() {
    const parts = window.location.pathname.split('/');
    const idx = parts.indexOf('runs');
    return idx >= 0 ? parts[idx + 1] : null;
  }

  // ====== 历史回放 ======
  async function loadHistory(runId) {
    try {
      const res = await fetch('/api/runs/' + runId + '/events');
      if (!res.ok) return;
      const data = await res.json();
      events = data || [];
      events.forEach(applyEvent);
    } catch(e) { console.warn('加载历史失败:', e); }
  }

  // ====== WebSocket ======
  function connectWs(runId) {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const url = proto + '://' + location.host + '/ws/runs/' + runId;
    ws = new WebSocket(url);

    ws.onopen = () => {
      document.getElementById('conn-status').textContent = '● 已连接';
      document.getElementById('conn-status').className = 'status-badge online';
    };

    ws.onmessage = (evt) => {
      try {
        const traceEvent = JSON.parse(evt.data);
        events.push(traceEvent);
        applyEvent(traceEvent);
      } catch(e) {}
    };

    ws.onclose = () => {
      document.getElementById('conn-status').textContent = '○ 重连中';
      document.getElementById('conn-status').className = 'status-badge offline';
      setTimeout(() => connectWs(runId), 2000);
    };

    ws.onerror = () => {
      document.getElementById('conn-status').textContent = '○ 离线';
      document.getElementById('conn-status').className = 'status-badge offline';
    };
  }

  // ====== 事件应用 ======
  function applyEvent(evt) {
    updateProgress(evt.progress_pct, evt.stage_label_zh || evt.status_text_zh);
    updateAvatar(evt.avatar_state || 'listening', evt.avatar_scene);
    updateDecisionCard(evt);
    appendTimeline(evt);
    updateMetrics(evt.payload || evt);
    updateLearningPanel(evt);

    // 任务完成
    if (evt.event_type === 'task.completed' || evt.stage === 'completed' || evt.progress_pct >= 100) {
      onTaskComplete(evt);
    }
    if (evt.event_type === 'task.failed' || evt.stage === 'failed') {
      onTaskFailed(evt);
    }
  }

  // ====== 进度 ======
  function updateProgress(pct, label) {
    if (pct === undefined || pct === null) return;
    const fill = document.getElementById('progress-fill');
    const pctEl = document.getElementById('progress-pct');
    const labelEl = document.getElementById('stage-label');
    const descEl = document.getElementById('stage-desc');
    if (fill) fill.style.width = pct + '%';
    if (pctEl) pctEl.textContent = pct + '%';
    if (labelEl && label) labelEl.textContent = label;
    document.getElementById('current-pct').textContent = pct + '%';
  }

  // ====== 像素人场景 ======
  function updateAvatar(state, scene) {
    const info = AVATAR_SCENE_MAP[state] || AVATAR_SCENE_MAP['listening'];
    document.getElementById('avatar-prop').textContent = info.prop;
    document.getElementById('avatar-label').textContent = info.labelZh;
    document.getElementById('avatar-label-en').textContent = info.labelEn;
    document.getElementById('stage-desc').textContent = info.descZh || '';
  }

  // ====== 决策卡片 ======
  function updateDecisionCard(evt) {
    const panel = document.getElementById('decision-panel');
    if (!panel) return;

    const what = evt.status_text_zh || evt.decision_summary_zh || evt.stage_label_zh || '';
    const why = evt.why_zh || '';
    const next = evt.next_step_zh || '';
    const discarded = evt.discarded_evidence || [];

    panel.innerHTML = `
      <div class="glass-card decision-card">
        <h4>当前决策</h4>
        <div class="decision-what">${what || '处理中...'}</div>
        ${why ? '<div class="decision-why">为什么：' + why + '</div>' : ''}
        ${next ? '<div class="decision-next">下一步：' + next + '</div>' : ''}
        ${discarded.length ? '<div class="decision-discarded">丢弃了 ' + discarded.length + ' 条无关信息</div>' : ''}
      </div>`;
  }

  // ====== 时间线 ======
  function appendTimeline(evt) {
    const list = document.getElementById('timeline-list');
    if (!list) return;

    const importance = evt.importance || 'normal';
    const dotClass = importance === 'critical' ? 'critical' : importance === 'important' ? 'important' : '';
    const time = evt.timestamp ? new Date(evt.timestamp * 1000).toLocaleTimeString() : '';
    const label = evt.stage_label_zh || evt.status_text_zh || evt.event_type || '';

    const node = document.createElement('div');
    node.className = 'timeline-node';
    node.innerHTML = `
      <div class="timeline-dot ${dotClass}"></div>
      <div class="timeline-content">
        <strong>${label}</strong>
        ${evt.decision_summary_zh ? '<div style="font-size:0.82rem;color:var(--text-muted);">' + evt.decision_summary_zh + '</div>' : ''}
        <div class="timeline-time">${time}</div>
      </div>`;
    
    if (list.children.length === 1 && list.children[0].tagName === 'SPAN') {
      list.innerHTML = '';
    }
    list.prepend(node);
  }

  // ====== 指标 ======
  function updateMetrics(data) {
    if (data.token_roi !== undefined) document.getElementById('metric-roi').textContent = (data.token_roi * 100).toFixed(0) + '%';
    if (data.quality_score !== undefined) document.getElementById('metric-quality').textContent = (data.quality_score * 100).toFixed(0) + '%';
    if (data.intent_alignment_score !== undefined) document.getElementById('metric-intent').textContent = (data.intent_alignment_score * 100).toFixed(0) + '%';
    if (data.memory_hit_rate !== undefined) document.getElementById('metric-memory').textContent = (data.memory_hit_rate * 100).toFixed(0) + '%';
  }

  // ====== 学习面板 ======
  function updateLearningPanel(evt) {
    if (evt.learning_triggered === undefined && evt.skill_updated === undefined) return;
    const panel = document.getElementById('learning-status');
    const triggered = evt.learning_triggered || evt.skill_updated;
    if (triggered) {
      panel.innerHTML = '<span class="learning-status learning-triggered">✅ 触发学习</span>';
      if (evt.improvement) {
        panel.innerHTML += '<div style="font-size:0.85rem;margin-top:6px;">评分提升：+' + (evt.improvement * 100).toFixed(1) + '%</div>';
      }
    } else {
      panel.innerHTML = '<span class="learning-status learning-not-triggered">📋 本次无需学习</span>';
      panel.innerHTML += '<div class="learning-reason">原因：当前任务反馈不足，系统没有足够证据更新 skill。</div>';
    }
  }

  // ====== 任务完成/失败 ======
  function onTaskComplete(evt) {
    if (runCompleted) return;
    runCompleted = true;
    showFeedbackSection();
  }

  function onTaskFailed(evt) {
    updateAvatar('failed');
    document.getElementById('stage-label').textContent = '任务失败';
    showFeedbackSection();
  }

  // ====== 反馈 ======
  const FEEDBACK_TYPES = [
    { type: 'aligned', label: '符合我的意图' },
    { type: 'partial', label: '部分符合' },
    { type: 'off_track', label: '跑偏了' },
    { type: 'too_technical', label: '太技术化' },
    { type: 'too_generic', label: '太空泛' },
    { type: 'not_specific', label: '不够具体' },
    { type: 'no_executable_plan', label: '没有可执行方案' },
  ];

  function initFeedbackButtons() {
    const container = document.getElementById('feedback-btns');
    if (!container) return;
    FEEDBACK_TYPES.forEach(fb => {
      const btn = document.createElement('button');
      btn.className = 'btn-fb';
      btn.textContent = fb.label;
      btn.onclick = () => submitFeedback(fb.type, btn);
      container.appendChild(btn);
    });
  }

  function showFeedbackSection() {
    const section = document.getElementById('feedback-section');
    if (section) section.style.display = 'block';
  }

  function submitFeedback(type, btn) {
    if (!currentRunId) return;
    const comment = type === 'off_track' ? prompt('它哪里理解错了？') : '';

    fetch('/api/runs/' + currentRunId + '/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ label: type, comment: comment || '' })
    }).then(r => r.json()).then(data => {
      document.querySelectorAll('.btn-fb').forEach(b => b.classList.remove('selected'));
      if (btn) btn.classList.add('selected');
      document.getElementById('feedback-title').textContent = '✅ 感谢反馈！';
      if (data.learning_evidence) updateLearningPanel(data.learning_evidence);
    }).catch(() => {});
  }

  // 启动
  document.addEventListener('DOMContentLoaded', init);

  // 暴露 API 供外部调用
  window.DashboardV3 = {
    applyEvent,
    setRunId: (rid) => {
      currentRunId = rid;
      document.getElementById('run-id-display').textContent = 'run_id: ' + rid;
      loadHistory(rid).then(() => connectWs(rid));
    },
    init,
  };
})();
