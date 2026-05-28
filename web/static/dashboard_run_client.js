/**
 * Dashboard Run 客户端 — V5 per-run WebSocket 订阅
 *
 * 从 URL 中提取 run_id（/runs/{run_id}），连接 /dashboard/ws/runs/{run_id}，
 * 实时更新 Timeline / 像素机器人 / 大白话 / token / eval / skill 面板。
 */
(function () {
    "use strict";

    var urlMatch = window.location.pathname.match(/\/runs\/([a-zA-Z0-9-]+)/);
    var runId = urlMatch ? urlMatch[1] : null;

    if (!runId) {
        return; // 不在 run 页面，不启动
    }

    var wsUrl = "ws://" + window.location.host + "/dashboard/ws/runs/" + runId;
    var ws = null;
    var reconnectTimer = null;

    // ---- 状态标签 ----
    var stateLabels = {
        listening: "\u804a\u542c\u4e2d...",
        thinking: "\u601d\u8003\u4e2d...",
        calculating: "\u7b97\u76d8\u4e2d...",
        reading_notes: "\u67e5\u9605\u8bb0\u5fc6...",
        searching_books: "\u641c\u7d22\u77e5\u8bc6\u5e93...",
        safety_check: "\u5b89\u5168\u68c0\u67e5...",
        waiting_approval: "\u7b49\u5f85\u5ba1\u6279...",
        working: "\u5de5\u4f5c\u4e2d...",
        grading: "\u8bc4\u5206\u4e2d...",
        writing_rule: "\u7f16\u5199\u89c4\u5219...",
        examining: "\u8003\u8bd5\u4e2d...",
        archiving: "\u5f52\u6863\u4e2d...",
        sweating: "\u51fa\u9519\u4e86...",
        celebrating: "\u5e86\u795d\u4e2d\uff01",
        idle: "\u5f85\u547d\u4e2d...",
    };

    // ---- 获取 DOM 元素 ----
    function getTimelineList() {
        return document.getElementById("timeline-list");
    }

    function getStage() {
        return document.getElementById("robot-stage") || document.getElementById("agent-canvas");
    }

    function getStatusLabel() {
        return document.getElementById("robot-status-label");
    }

    function getExplanation() {
        return document.getElementById("robot-explanation");
    }

    function getApprovalPanel() {
        return document.getElementById("approval-panel");
    }

    function getWsDot() {
        return document.getElementById("ws-dot");
    }

    function getWsText() {
        return document.getElementById("ws-text");
    }

    // ---- 连接管理 ----
    function connect() {
        ws = new WebSocket(wsUrl);

        ws.onopen = function () {
            var dot = getWsDot();
            var text = getWsText();
            if (dot) {
                dot.classList.add("connected");
            }
            if (text) {
                text.textContent = "\u5df2\u8fde\u63a5 [Run]";
            }
        };

        ws.onmessage = function (event) {
            var data = JSON.parse(event.data);
            var evtType = data.event_type || "";
            var payload = data.payload || {};

            // 1) 更新 Timeline
            addTimelineEntryV5(data);

            // 2) 更新像素机器人（使用 avatar_state）
            if (data.avatar_state) {
                updateAvatarByState(data.avatar_state);
            } else if (evtType) {
                // 回退到旧版 updateAvatar
                if (typeof updateAvatar === "function") {
                    updateAvatar(evtType);
                }
            }

            // 3) 更新大白话解释
            if (data.plain_text) {
                var explanationEl = getExplanation();
                if (explanationEl) {
                    explanationEl.textContent = data.plain_text;
                }
            }

            // 4) 更新 Token 面板
            if (payload.token_usage) {
                if (typeof updateTokenBar === "function") {
                    updateTokenBar(payload.token_usage);
                }
            }

            // 5) 更新 Eval 面板
            if (payload.eval_scores) {
                if (typeof updateEvalPanel === "function") {
                    updateEvalPanel(payload.eval_scores);
                }
            }

            // 6) 更新 Skill 面板
            if (evtType && evtType.indexOf("skillopt") === 0) {
                if (typeof fetchSkillOptStatus === "function") {
                    fetchSkillOptStatus();
                }
            }

            // 7) 审批处理
            if (evtType === "approval.required") {
                showApprovalUI(payload);
            }
        };

        ws.onclose = function () {
            var dot = getWsDot();
            var text = getWsText();
            if (dot) {
                dot.classList.remove("connected");
            }
            if (text) {
                text.textContent = "\u65ad\u5f00 [Run]";
            }
            // 3 秒后自动重连
            reconnectTimer = setTimeout(connect, 3000);
        };

        ws.onerror = function () {
            // 错误由 onclose 处理
        };
    }

    // ---- Timeline 更新 ----
    function addTimelineEntryV5(data) {
        var timeline = getTimelineList();
        if (!timeline) {
            return;
        }
        var entry = document.createElement("div");
        entry.className = "timeline-entry";
        var ts = data.timestamp ? new Date(data.timestamp * 1000) : new Date();
        var timeStr = ts.toLocaleTimeString();
        var typeStr = data.event_type || "event";
        var textStr = data.plain_text || "";
        entry.innerHTML =
            '<span class="timeline-time">' +
            timeStr +
            "</span>" +
            '<span class="timeline-type">' +
            typeStr +
            "</span>" +
            '<span class="timeline-text">' +
            textStr +
            "</span>";
        timeline.prepend(entry);
    }

    // ---- 像素机器人状态更新 ----
    function updateAvatarByState(state) {
        var stage = getStage();
        if (!stage) {
            return;
        }
        // 设置 CSS 类
        var baseClass = stage.className.split(" ")[0] || "";
        stage.className = baseClass + " avatar-" + (state || "idle");

        // 更新状态标签
        var label = getStatusLabel();
        if (label) {
            label.textContent = stateLabels[state] || state;
        }

        // 通过 PixelAgent API 播放动画（如果可用）
        if (typeof window.updateAvatarByState === "function" && window.updateAvatarByState !== updateAvatarByState) {
            window.updateAvatarByState(state);
        }
    }

    // ---- 审批 UI ----
    function showApprovalUI(payload) {
        var panel = getApprovalPanel();
        if (!panel) {
            return;
        }
        panel.style.display = "block";
        var actionEl = panel.querySelector(".approval-action");
        if (actionEl) {
            actionEl.textContent = payload.action || "\u9700\u8981\u5ba1\u6279";
        }
        if (payload.request_id) {
            panel.dataset.requestId = payload.request_id;
        }
    }

    // ---- 初始化 ----
    connect();
})();
