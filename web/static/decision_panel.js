// decision_panel.js — 决策卡片实时更新
window.DecisionPanel = {
  init() {
    const panel = document.getElementById('decision-panel');
    if (!panel) return;
    panel.innerHTML = `
      <div class="glass-card decision-card">
        <h4>当前决策</h4>
        <div class="decision-what" id="decision-what">等待任务...</div>
        <div class="decision-why" id="decision-why"></div>
        <div class="decision-next" id="decision-next"></div>
        <div class="decision-discarded" id="decision-discarded"></div>
      </div>
    `;
  },

  update(traceEvent) {
    if (!traceEvent) return;

    const whatEl = document.getElementById('decision-what');
    const whyEl = document.getElementById('decision-why');
    const nextEl = document.getElementById('decision-next');
    const discardedEl = document.getElementById('decision-discarded');

    if (whatEl && traceEvent.status_text_zh) whatEl.textContent = traceEvent.status_text_zh;
    else if (whatEl && traceEvent.decision_summary_zh) whatEl.textContent = traceEvent.decision_summary_zh;

    if (whyEl && traceEvent.why_zh) whyEl.textContent = '为什么：' + traceEvent.why_zh;

    if (nextEl && traceEvent.next_step_zh) nextEl.textContent = '下一步：' + traceEvent.next_step_zh;

    if (discardedEl && traceEvent.discarded_evidence && traceEvent.discarded_evidence.length > 0) {
      discardedEl.textContent = '丢弃了 ' + traceEvent.discarded_evidence.length + ' 条无关信息';
      discardedEl.style.display = 'block';
    } else if (discardedEl) {
      discardedEl.style.display = 'none';
    }
  }
};
