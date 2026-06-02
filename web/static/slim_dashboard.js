/* StableAgent OS Slim Dashboard — 轻量 JS (3s 轮询) */
(function() {
    'use strict';

    const POLL_INTERVAL = 3000;
    let pollTimer = null;

    // ------------------------------------------------------------------
    // Helpers
    // ------------------------------------------------------------------

    function $(sel) { return document.querySelector(sel); }
    function $$(sel) { return document.querySelectorAll(sel); }

    function escapeHtml(text) {
        const d = document.createElement('div');
        d.textContent = text;
        return d.innerHTML;
    }

    function formatTime(ts) {
        if (!ts) return '-';
        const d = new Date(ts * 1000);
        return d.toLocaleTimeString('zh-CN', { hour12: false });
    }

    function formatDateTime(ts) {
        if (!ts) return '-';
        const d = new Date(ts * 1000);
        return d.toLocaleString('zh-CN', { hour12: false });
    }

    function statusBadge(status) {
        return '<span class="badge badge-' + escapeHtml(status) + '">' + escapeHtml(status) + '</span>';
    }

    function statusDot(status) {
        const cls = status === 'online' ? 'status-online' :
                    status === 'busy' ? 'status-busy' : 'status-offline';
        return '<span class="status-dot ' + cls + '"></span>';
    }

    function showResult(id, msg, isError) {
        const el = $(id);
        if (!el) return;
        el.className = 'result-msg ' + (isError ? 'result-error' : 'result-success');
        el.textContent = msg;
        el.classList.remove('hidden');
        setTimeout(() => el.classList.add('hidden'), 5000);
    }

    // ------------------------------------------------------------------
    // Data fetching
    // ------------------------------------------------------------------

    async function fetchJSON(url) {
        try {
            const resp = await fetch(url);
            if (!resp.ok) throw new Error('HTTP ' + resp.status);
            return await resp.json();
        } catch (e) {
            console.error('Fetch failed:', url, e);
            return null;
        }
    }

    async function postJSON(url, body) {
        try {
            const resp = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            return await resp.json();
        } catch (e) {
            console.error('Post failed:', url, e);
            return null;
        }
    }

    // ------------------------------------------------------------------
    // Render functions
    // ------------------------------------------------------------------

    function renderHealth(data) {
        if (!data) return;
        $('#stat-profile').textContent = data.profile || '-';
        $('#stat-workers').textContent = data.workers_online || 0;
        $('#stat-queued').textContent = data.queued_tasks || 0;
        $('#stat-running').textContent = data.running_tasks || 0;
        $('#stat-events').textContent = data.total_events || 0;
        const badge = $('#profile-badge');
        if (badge) badge.textContent = data.profile || 'slim';
    }

    function renderWorkers(workers) {
        const el = $('#worker-list');
        if (!el) return;
        if (!workers || workers.length === 0) {
            el.className = 'empty-state';
            el.textContent = 'No workers registered';
            return;
        }
        el.className = '';
        el.innerHTML = workers.map(function(w) {
            return '<div class="worker-card">' +
                '<div class="worker-info">' +
                    '<div class="worker-name">' + statusDot(w.status) + escapeHtml(w.name) + '</div>' +
                    '<div class="worker-id">' + escapeHtml(w.worker_id) + ' &middot; ' + escapeHtml(w.machine_type) + '</div>' +
                    '<div class="worker-caps">' + (w.capabilities || []).join(', ') + '</div>' +
                '</div>' +
                '<div>' +
                    statusBadge(w.status) +
                    (w.current_task_id ? '<br><small>' + escapeHtml(w.current_task_id) + '</small>' : '') +
                '</div>' +
            '</div>';
        }).join('');
    }

    function renderTasks(tasks) {
        const el = $('#task-list');
        if (!el) return;
        if (!tasks || tasks.length === 0) {
            el.className = 'empty-state';
            el.textContent = 'No tasks';
            return;
        }
        el.className = '';
        var html = '<div class="task-row task-header">' +
            '<span>Task ID</span><span>Status</span><span>Worker</span><span>Input</span><span>Created</span></div>';
        html += tasks.map(function(t) {
            return '<div class="task-row">' +
                '<span>' + escapeHtml(t.task_id.substring(0, 16)) + '</span>' +
                '<span>' + statusBadge(t.status) + '</span>' +
                '<span>' + escapeHtml(t.assigned_worker_id || '-') + '</span>' +
                '<span>' + escapeHtml((t.task_input || '').substring(0, 60)) + '</span>' +
                '<span>' + formatTime(t.created_at) + '</span>' +
            '</div>';
        }).join('');
        el.innerHTML = html;
    }

    function renderEvents(events) {
        const el = $('#event-list');
        if (!el) return;
        if (!events || events.length === 0) {
            el.className = 'empty-state';
            el.textContent = 'No events';
            return;
        }
        el.className = '';
        el.innerHTML = events.map(function(e) {
            var msg = '';
            if (e.payload && e.payload.message) msg = e.payload.message;
            else if (e.payload && e.payload.error) msg = e.payload.error;
            else if (e.payload && e.payload.source) msg = 'source: ' + e.payload.source;
            return '<div class="event-row">' +
                '<span class="event-type">' + escapeHtml(e.event_type) + '</span>' +
                '<span class="event-time">' + formatTime(e.timestamp) + '</span>' +
                '<span class="event-worker">' + escapeHtml(e.worker_id || '-') + '</span>' +
                '<span class="event-msg">' + escapeHtml(msg) + '</span>' +
            '</div>';
        }).join('');
    }

    function renderCapsule(capsule) {
        if (!capsule) return;
        $('#capsule-expr').textContent = capsule.expression_rules_count || 0;
        $('#capsule-mem').textContent = capsule.memory_count || 0;
        $('#capsule-bc').textContent = capsule.bad_case_count || 0;
    }

    // ------------------------------------------------------------------
    // Poll loop
    // ------------------------------------------------------------------

    async function poll() {
        const [statusData, capsuleData] = await Promise.all([
            fetchJSON('/api/slim/status'),
            fetchJSON('/api/slim/capsule'),
        ]);

        if (statusData && statusData.ok) {
            renderHealth(statusData.health);
            renderWorkers(statusData.workers);
            renderTasks(statusData.tasks);
            renderEvents(statusData.events);
        }
        if (capsuleData && capsuleData.ok) {
            renderCapsule(capsuleData.capsule);
        }

        $('#footer-time').textContent = new Date().toLocaleString('zh-CN', { hour12: false });
    }

    function startPolling() {
        poll();
        pollTimer = setInterval(poll, POLL_INTERVAL);
    }

    // ------------------------------------------------------------------
    // Form handlers
    // ------------------------------------------------------------------

    function initForms() {
        var taskForm = $('#task-form');
        if (taskForm) {
            taskForm.addEventListener('submit', async function(e) {
                e.preventDefault();
                var body = {
                    task_input: $('#task-input').value,
                    priority: parseInt($('#priority').value, 10),
                    source: 'dashboard',
                };
                var wid = $('#worker-id').value.trim();
                if (wid) body.worker_id = wid;

                var result = await postJSON('/api/tasks', body);
                if (result && result.ok) {
                    showResult('#submit-result', 'Task created: ' + result.task.task_id, false);
                    $('#task-input').value = '';
                    poll(); // refresh
                } else {
                    showResult('#submit-result', 'Failed to create task', true);
                }
            });
        }

        // Feedback buttons
        $$('.btn-feedback').forEach(function(btn) {
            btn.addEventListener('click', async function() {
                var action = btn.dataset.action;
                var note = prompt('Enter feedback note:');
                if (!note) return;

                var url = '/api/feedback/' + (action === 'dont' ? 'dont-do-this-again' :
                          action === 'correct' ? 'correct-and-remember' : 'remember');
                var result = await postJSON(url, { run_id: '', note: note });
                if (result && result.ok !== false) {
                    showResult('#feedback-result', result.summary_zh || 'Feedback recorded', false);
                } else {
                    showResult('#feedback-result', 'Feedback failed (service may not be available)', true);
                }
            });
        });
    }

    // ------------------------------------------------------------------
    // Init
    // ------------------------------------------------------------------

    document.addEventListener('DOMContentLoaded', function() {
        initForms();
        startPolling();
    });
})();
