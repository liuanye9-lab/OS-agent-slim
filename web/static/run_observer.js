// run_observer.js — Dashboard Observer 前端逻辑
// 后端事件驱动，前端不猜进度、不伪造状态

const AVATAR_SCENE_MAP = {
  listening:       { scene: "desk",           labelZh: "接收任务",    prop: "task_card" },
  thinking:        { scene: "thinking_board",  labelZh: "理解需求",    prop: "magnifier" },
  calculating:     { scene: "budget_panel",    labelZh: "计算预算",    prop: "abacus" },
  reading_notes:   { scene: "memory_wall",     labelZh: "找时间记忆",  prop: "memory_cards" },
  searching_books: { scene: "library",         labelZh: "查项目资料",  prop: "books" },
  organizing:      { scene: "context_table",   labelZh: "压缩上下文",  prop: "context_blocks" },
  planning:        { scene: "map_table",       labelZh: "规划步骤",    prop: "route_map" },
  tooling:         { scene: "tool_bench",      labelZh: "调用工具",    prop: "wrench" },
  watching:        { scene: "monitor",         labelZh: "观察结果",    prop: "screen" },
  grading:         { scene: "exam_table",      labelZh: "评估结果",    prop: "score_sheet" },
  diagnosing:      { scene: "diagnosis_board", labelZh: "分析失败",    prop: "warning_card" },
  writing_case:    { scene: "case_desk",       labelZh: "生成错题",    prop: "case_file" },
  learning:        { scene: "skill_book",      labelZh: "提出改法",    prop: "skill_patch" },
  waiting_approval:{ scene: "approval_gate",   labelZh: "等待审核",    prop: "red_card" },
  archiving:       { scene: "archive_cabinet", labelZh: "导出规则",    prop: "best_skill" },
  done:            { scene: "delivery_desk",   labelZh: "完成任务",    prop: "checkmark" },
  failed:          { scene: "error_board",     labelZh: "任务失败",    prop: "error_sign" },
  idle:            { scene: "desk",            labelZh: "空闲",        prop: "coffee" }
};

// Emoji fallback (when no Canvas avatar available)
const AVATAR_EMOJI = {
  listening:        "📥",
  thinking:         "🔎",
  calculating:      "🧮",
  reading_notes:    "🗂️",
  searching_books:  "📚",
  organizing:       "🧩",
  planning:         "🗺️",
  tooling:          "🔧",
  watching:         "📝",
  grading:          "📖",
  diagnosing:       "🔍",
  writing_case:     "📋",
  learning:         "✅",
  waiting_approval: "⏳",
  archiving:        "📦",
  done:             "🎉",
  failed:           "⚠️",
  idle:             "☕"
};

// ========== State ==========
let logs = [];
let timelineItems = [];

// ========== DOM refs ==========
const $taskName    = document.getElementById("taskName");
const $runId       = document.getElementById("runId");
const $progressPct = document.getElementById("progressPct");
const $progressBar = document.getElementById("progressBar");
const $mcpStatus   = document.getElementById("mcpStatus");
const $avatarScene = document.getElementById("avatarScene");
const $sceneLabel  = document.getElementById("sceneLabel");
const $sceneProp   = document.getElementById("sceneProp");
const $nowStatus   = document.getElementById("nowStatus");
const $whyText     = document.getElementById("whyText");
const $evidenceText = document.getElementById("evidenceText");
const $nextStepText = document.getElementById("nextStepText");
const $progressText = document.getElementById("progressText");
const $logPanel    = document.getElementById("logPanel");
const $timelineEmpty = document.getElementById("timelineEmpty");
const $timelineCol   = document.getElementById("timelineCol");
const $siReport    = document.getElementById("siReport");

// ========== URL param ==========
const params = new URLSearchParams(window.location.search);
const runId   = params.get("run_id");

if (runId) {
  $runId.textContent = runId;
  const v3Link = document.getElementById("v3Link");
  if (v3Link) v3Link.href = `/runs/${runId}`;
  connectWebSocket(runId);
}

// ========== WebSocket ==========
function connectWebSocket(runId) {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl    = `${protocol}//${location.host}/dashboard-sync/ws/runs/${runId}`;

  const ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    $mcpStatus.textContent = "已连接";
    $mcpStatus.className   = "mcp-status";
    addLogLine("info", `WebSocket 已连接: ${runId}`);
  };

  ws.onmessage = (e) => {
    try {
      const event = JSON.parse(e.data);
      applyEvent(event);
    } catch (err) {
      addLogLine("error", `消息解析失败: ${err.message}`);
    }
  };

  ws.onclose = () => {
    $mcpStatus.textContent = "已断开";
    $mcpStatus.className   = "mcp-status disconnected";
    addLogLine("warn", "WebSocket 已断开");
  };

  ws.onerror = () => {
    addLogLine("error", "WebSocket 连接错误");
  };
}

// ========== Apply Event ==========
function applyEvent(evt) {
  addLogLine("info", `收到事件: ${evt.event_type || evt.type || "unknown"}`);

  // 1. Update progress
  if (evt.progress_pct !== undefined) {
    updateProgress(evt.progress_pct, evt.status_text_zh || evt.stage_label_zh || "");
  }

  // 2. Update avatar
  if (evt.avatar_state) {
    updateAvatar(evt.avatar_state);
  }

  // 3. Update status card text
  updateStatusCard(evt);

  // 4. Append timeline
  appendTimeline(evt);

  // 5. Update Self-Improvement Report
  if (evt.si_report || evt.self_improvement) {
    updateSIReport(evt.si_report || evt.self_improvement);
  }

  // 6. Update task name
  if (evt.run_id && evt.run_id !== $runId.textContent) {
    $runId.textContent = evt.run_id;
  }
}

// ========== Update Progress ==========
function updateProgress(pct, label) {
  const safe = Math.max(0, Math.min(100, pct));
  $progressPct.textContent = `${safe}%`;
  $progressBar.style.width = `${safe}%`;
  $progressText.textContent = label ? `${safe}% — ${label}` : `${safe}%`;

  if (safe >= 100) {
    $progressPct.style.color = "#34c759";
  } else if (safe >= 80) {
    $progressPct.style.color = "#0071e3";
  } else {
    $progressPct.style.color = "#1d1d1f";
  }
}

// ========== Update Avatar ==========
function updateAvatar(state) {
  const info = AVATAR_SCENE_MAP[state] || AVATAR_SCENE_MAP.idle;

  // Canvas pixel avatar (from avatar_scene.js)
  if (typeof renderAvatarScene === "function") {
    renderAvatarScene(info.scene, "avatarCanvas");
  }

  // Emoji fallback shown inside canvas as well
  $sceneLabel.textContent = info.labelZh;
  $sceneProp.textContent = `场景: ${info.scene} | 道具: ${info.prop}`;
}

// ========== Update Status Card ==========
function updateStatusCard(evt) {
  const now = evt.stage_label_zh || evt.status_text_zh || evt.what_happened_zh || "";
  const why = evt.why_zh || evt.decision_summary_zh || "";
  const next = evt.next_step_zh || "";
  const evidence = evt.evidence || [];

  if (now) $nowStatus.textContent = now;
  if (why) $whyText.textContent = why;

  if (evidence.length > 0) {
    $evidenceText.textContent = evidence.slice(0, 3).join(" | ");
  } else if (evt.decision_summary_zh) {
    $evidenceText.textContent = evt.decision_summary_zh;
  } else {
    $evidenceText.textContent = "--";
  }

  if (next) $nextStepText.textContent = next;

  if (evt.task_name) $taskName.textContent = evt.task_name;
}

// ========== Append Timeline ==========
function appendTimeline(evt) {
  // Remove empty state
  if ($timelineEmpty) {
    $timelineEmpty.remove();
    // reclaim reference
    window._timelineEmptyRemoved = true;
  }

  const stage = evt.stage_label_zh || evt.stage || "";
  const what  = evt.what_happened_zh || evt.status_text_zh || evt.event_type || "";
  const pct   = evt.progress_pct !== undefined ? `${evt.progress_pct}%` : "";

  const item = document.createElement("div");
  item.className = "timeline-item";
  item.innerHTML = `
    <div class="tl-stage">${escapeHtml(stage)}</div>
    <div class="tl-what">${escapeHtml(what)}</div>
    <div class="tl-progress">${pct}</div>
  `;

  $timelineCol.appendChild(item);
  timelineItems.push(item);

  // Limit to 50 items
  while (timelineItems.length > 50) {
    const old = timelineItems.shift();
    if (old) old.remove();
  }
}

// ========== Update Self-Improvement Report ==========
function updateSIReport(report) {
  if (!report) return;

  $siReport.classList.add("visible");

  document.getElementById("siTriggered").querySelector(".si-value").textContent =
    report.learning_triggered ? "是" : "否";

  document.getElementById("siRegressions").querySelector(".si-value").textContent =
    (report.regression_cases || []).length;

  document.getElementById("siMemories").querySelector(".si-value").textContent =
    (report.memory_candidates || []).length;

  document.getElementById("siPatches").querySelector(".si-value").textContent =
    (report.skill_patches || []).length;

  document.getElementById("siValidation").querySelector(".si-value").textContent =
    report.validation_passed ? "通过" : "未通过";

  const reviewEl = document.getElementById("siReview");
  reviewEl.querySelector(".si-value").textContent =
    report.human_review_status || "--";
  reviewEl.className = report.human_review_status === "approved"
    ? "si-item ok"
    : report.human_review_status === "rejected"
      ? "si-item warn"
      : "si-item";

  document.getElementById("siExport").querySelector(".si-value").textContent =
    report.best_skill_exported ? "是" : "否";

  document.getElementById("siSummary").querySelector(".si-value").textContent =
    report.summary_zh || "--";
}

// ========== Log ==========
function addLogLine(level, msg) {
  const time = new Date().toLocaleTimeString("zh-CN");
  logs.push(`[${time}] [${level}] ${msg}`);
  if (logs.length > 200) logs.shift();
  $logPanel.textContent = logs.join("\n");
  if ($logPanel.classList.contains("open")) {
    $logPanel.scrollTop = $logPanel.scrollHeight;
  }
}

function toggleLog() {
  $logPanel.classList.toggle("open");
  if ($logPanel.classList.contains("open")) {
    $logPanel.scrollTop = $logPanel.scrollHeight;
  }
}

// ========== Utility ==========
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text || "";
  return div.innerHTML;
}

// ==================================================================
// V8.0: Multi-Agent Collaboration — parallel run observation
// ==================================================================

// Active WebSocket connections (runId → WebSocket)
const activeConnections = new Map();
// Per-run event buffers (runId → events[])
const runBuffers = new Map();

/**
 * Observe multiple runs in parallel.
 * @param {string[]} runIds - list of run IDs to observe
 */
function observeMultipleRuns(runIds) {
  // Close existing connections
  for (const [id, ws] of activeConnections) {
    if (!runIds.includes(id)) {
      ws.close();
      activeConnections.delete(id);
      runBuffers.delete(id);
    }
  }

  // Open new connections
  for (const runId of runIds) {
    if (!activeConnections.has(runId)) {
      connectMultiAgentWebSocket(runId);
    }
  }

  // Update display
  updateMultiAgentDisplay();
}

function connectMultiAgentWebSocket(runId) {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${location.host}/dashboard-sync/ws/runs/${runId}`;
  const ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    addLogLine("info", `[Agent ${runId.slice(0, 8)}] 已连接`);
    activeConnections.set(runId, ws);
    runBuffers.set(runId, []);
  };

  ws.onmessage = (e) => {
    try {
      const event = JSON.parse(e.data);
      const buffer = runBuffers.get(runId) || [];
      buffer.push(event);
      if (buffer.length > 100) buffer.shift();
      runBuffers.set(runId, buffer);

      // If this is the "primary" run, also apply to main UI
      if (runId === primaryRunId) {
        applyEvent(event);
      }
    } catch (err) {
      addLogLine("error", `[Agent ${runId.slice(0, 8)}] 消息解析失败`);
    }
  };

  ws.onclose = () => {
    addLogLine("warn", `[Agent ${runId.slice(0, 8)}] 断开`);
    activeConnections.delete(runId);
  };
}

let primaryRunId = null;

/**
 * Update the multi-agent display panel.
 */
function updateMultiAgentDisplay() {
  const panel = document.getElementById("multiAgentPanel");
  if (!panel) return;

  let html = "";
  for (const [runId, ws] of activeConnections) {
    const buffer = runBuffers.get(runId) || [];
    const lastEvent = buffer.length > 0 ? buffer[buffer.length - 1] : null;
    const status = lastEvent ? (lastEvent.status_text_zh || lastEvent.event_type) : "connecting";
    const progress = lastEvent ? (lastEvent.progress_pct || 0) : 0;

    html += `
      <div class="agent-card ${runId === primaryRunId ? 'primary' : ''}"
           onclick="switchPrimaryAgent('${runId}')">
        <div class="agent-header">
          <span class="agent-id">${runId.slice(0, 10)}...</span>
          <span class="agent-status ${ws.readyState === WebSocket.OPEN ? 'online' : 'offline'}">
            ${ws.readyState === WebSocket.OPEN ? '●' : '○'}
          </span>
        </div>
        <div class="agent-progress">
          <div class="agent-progress-bar" style="width:${progress}%"></div>
        </div>
        <div class="agent-label">${status}</div>
        <div class="agent-event-count">${buffer.length} events</div>
      </div>`;
  }

  panel.innerHTML = html;
}

function switchPrimaryAgent(runId) {
  primaryRunId = runId;
  const buffer = runBuffers.get(runId) || [];

  // Replay all events to main UI
  for (const event of buffer) {
    applyEvent(event);
  }
  // Update display
  document.getElementById("runId").textContent = runId;
  updateMultiAgentDisplay();
  addLogLine("info", `切换到 Agent: ${runId.slice(0, 10)}`);
}

// Auto-refresh multi-agent display every 2 seconds
setInterval(updateMultiAgentDisplay, 2000);
