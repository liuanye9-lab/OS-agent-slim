/* Effectiveness Dashboard JavaScript */

const API = '/api/effectiveness';

// -- Initialization --

document.addEventListener('DOMContentLoaded', () => {
  loadSummaries();
  loadTasks();
});

// -- API Helpers --

async function apiFetch(path, options = {}) {
  const res = await fetch(API + path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

// -- Summary Loading --

async function loadSummaries() {
  try {
    const data = await apiFetch('/summary');
    renderSummaryCards(data.summaries);
    renderComparisonTable(data.summaries);
  } catch (err) {
    console.error('Failed to load summaries:', err);
  }
}

async function loadTasks() {
  try {
    const data = await apiFetch('/tasks');
    populateTaskSelect(data.tasks);
  } catch (err) {
    console.error('Failed to load tasks:', err);
  }
}

// -- Rendering --

function renderSummaryCards(summaries) {
  const totalTasks = summaries.length;
  let totalRuns = 0;
  let effectiveCount = 0;
  let totalTokenDelta = 0;
  let tokenDeltaCount = 0;

  summaries.forEach(s => {
    totalRuns += (s.baseline_count || 0) + (s.stableagent_count || 0);
    if (s.verdict === 'effective') effectiveCount++;
    if (s.delta_tokens !== 0) {
      totalTokenDelta += s.delta_tokens;
      tokenDeltaCount++;
    }
  });

  document.getElementById('totalTasks').textContent = totalTasks;
  document.getElementById('totalRuns').textContent = totalRuns;
  document.getElementById('effectiveTasks').textContent = effectiveCount;

  const avgSave = tokenDeltaCount > 0 ? (totalTokenDelta / tokenDeltaCount).toFixed(0) : '--';
  document.getElementById('avgTokenSave').textContent = avgSave === '--' ? '--' : `${avgSave} tokens`;
}

function renderComparisonTable(summaries) {
  const tbody = document.getElementById('comparisonBody');

  if (!summaries || summaries.length === 0) {
    tbody.innerHTML = '<tr><td colspan="9" class="empty-row">暂无数据，请创建任务并记录运行</td></tr>';
    return;
  }

  tbody.innerHTML = summaries.map(s => {
    const task = getTaskById(s.task_id);
    const desc = task ? task.description : s.task_id;

    return `
      <tr>
        <td><code>${s.task_id}</code></td>
        <td>${desc}</td>
        <td>${s.baseline_count || 0}</td>
        <td>${s.stableagent_count || 0}</td>
        <td class="${deltaClass(s.delta_success, true)}">${formatDelta(s.delta_success, true)}</td>
        <td class="${deltaClass(s.delta_tokens, false)}">${formatDelta(s.delta_tokens, false)}</td>
        <td class="${deltaClass(s.delta_intent_drift, false)}">${formatDelta(s.delta_intent_drift, true)}</td>
        <td><span class="verdict verdict-${s.verdict}">${verdictLabel(s.verdict)}</span></td>
        <td><button onclick="viewTask('${s.task_id}')" class="btn btn-link">详情</button></td>
      </tr>
    `;
  }).join('');
}

// -- Helpers --

let _cachedTasks = [];

function getTaskById(taskId) {
  return _cachedTasks.find(t => t.task_id === taskId);
}

function populateTaskSelect(tasks) {
  _cachedTasks = tasks;
  const select = document.getElementById('runTaskIdSelect');
  select.innerHTML = tasks.map(t =>
    `<option value="${t.task_id}">${t.task_id} — ${t.description}</option>`
  ).join('');
}

function deltaClass(value, higherIsBetter) {
  if (Math.abs(value) < 0.001) return 'delta-neutral';
  const positive = higherIsBetter ? value > 0 : value < 0;
  return positive ? 'delta-positive' : 'delta-negative';
}

function formatDelta(value, higherIsBetter) {
  if (Math.abs(value) < 0.001) return '≈ 持平';
  const arrow = higherIsBetter ? (value > 0 ? '↑' : '↓') : (value < 0 ? '↓' : '↑');
  return `${arrow} ${Math.abs(value).toFixed(2)}`;
}

function verdictLabel(verdict) {
  const labels = {
    'insufficient_data': '数据不足',
    'promising': '有潜力',
    'effective': '有效',
    'not_effective': '未见效',
  };
  return labels[verdict] || verdict;
}

function showToast(message, type = 'success') {
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}

// -- Modal Handling --

function openTaskModal() {
  document.getElementById('taskModal').classList.add('active');
}

function closeTaskModal() {
  document.getElementById('taskModal').classList.remove('active');
  document.getElementById('taskIdInput').value = '';
  document.getElementById('taskDescInput').value = '';
}

function openRunModal() {
  document.getElementById('runModal').classList.add('active');
  loadTasks(); // Refresh task select
}

function closeRunModal() {
  document.getElementById('runModal').classList.remove('active');
}

// Close modal on backdrop click
document.querySelectorAll('.modal').forEach(modal => {
  modal.addEventListener('click', e => {
    if (e.target === modal) {
      modal.classList.remove('active');
    }
  });
});

// -- Form Submission --

async function submitTask(e) {
  e.preventDefault();

  const taskId = document.getElementById('taskIdInput').value.trim();
  const description = document.getElementById('taskDescInput').value.trim();
  const category = document.getElementById('taskCategoryInput').value;

  if (!taskId) {
    showToast('请输入任务 ID', 'error');
    return;
  }

  try {
    await apiFetch('/task', {
      method: 'POST',
      body: JSON.stringify({ task_id: taskId, description, category }),
    });
    showToast(`任务 "${taskId}" 已创建`);
    closeTaskModal();
    loadSummaries();
    loadTasks();
  } catch (err) {
    showToast(`创建失败: ${err.message}`, 'error');
  }
}

async function submitRun(e) {
  e.preventDefault();

  const body = {
    task_id: document.getElementById('runTaskIdSelect').value,
    mode: document.getElementById('runModeSelect').value,
    success: document.getElementById('runSuccessSelect').value === 'true',
    edits_made: parseInt(document.getElementById('runEditsInput').value, 10),
    files_changed: parseInt(document.getElementById('runFilesInput').value, 10),
    tokens_used: parseInt(document.getElementById('runTokensInput').value, 10),
    intent_drift: parseFloat(document.getElementById('runDriftInput').value),
    duration_sec: parseFloat(document.getElementById('runDurationInput').value),
    error_message: document.getElementById('runErrorInput').value.trim(),
  };

  if (!body.task_id) {
    showToast('请选择任务', 'error');
    return;
  }

  try {
    await apiFetch('/run', {
      method: 'POST',
      body: JSON.stringify(body),
    });
    showToast('运行结果已记录');
    closeRunModal();
    loadSummaries();
  } catch (err) {
    showToast(`记录失败: ${err.message}`, 'error');
  }
}

function viewTask(taskId) {
  // For now, just show a toast. Could navigate to a detail page.
  showToast(`查看任务详情: ${taskId}`);
  // Future: window.location.href = `/effectiveness/task/${taskId}`;
}
