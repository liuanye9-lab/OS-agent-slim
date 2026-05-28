// progress_bar.js — 后端驱动的进度条组件
window.ProgressBar = {
  _currentPct: 0,
  _currentLabel: '',

  init() {
    const wrap = document.getElementById('progress-bar-wrap');
    if (!wrap) return;
    wrap.innerHTML = `
      <div class="progress-bar-wrap">
        <div class="progress-bar-fill" id="progress-fill" style="width: 0%"></div>
      </div>
      <div class="progress-pct" id="progress-pct">0%</div>
      <div class="stage-label" id="stage-label">等待任务...</div>
      <div class="stage-desc" id="stage-desc"></div>
    `;
  },

  update(pct, labelZh) {
    if (pct === undefined || pct === null) return;
    this._currentPct = pct;
    this._currentLabel = labelZh || '';

    const fill = document.getElementById('progress-fill');
    const pctEl = document.getElementById('progress-pct');
    const labelEl = document.getElementById('stage-label');

    if (fill) fill.style.width = pct + '%';
    if (pctEl) pctEl.textContent = pct + '%';
    if (labelEl && labelZh) labelEl.textContent = labelZh;
  },

  setStage(desc) {
    const descEl = document.getElementById('stage-desc');
    if (descEl && desc) descEl.textContent = desc;
  }
};
