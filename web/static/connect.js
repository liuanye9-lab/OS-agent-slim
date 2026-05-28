// connect.js — StableAgent OS 一键接入页面
const MCP_URL = window.location.origin + '/mcp/v5/mcp';
const HEALTH_URL = window.location.origin + '/api/connect/health';

function showToast(msg) {
  const existing = document.querySelector('.toast');
  if (existing) existing.remove();
  const t = document.createElement('div');
  t.className = 'toast';
  t.textContent = msg;
  document.getElementById('toast-container').appendChild(t);
  setTimeout(() => t.remove(), 2200);
}

// 加载状态
async function loadStatus() {
  try {
    const res = await fetch('/api/connect/health');
    const data = await res.json();
    const online = data.ok;
    const endpoint = data.mcp_endpoint || MCP_URL;
    
    ['claude', 'codex', 'generic'].forEach(card => {
      const badge = document.getElementById('badge-' + card);
      const ep = document.getElementById('endpoint-' + card);
      if (badge) {
        badge.textContent = online ? '● 运行中' : '○ 未连接';
        badge.className = 'status-badge ' + (online ? 'online' : 'offline');
      }
      if (ep) ep.textContent = endpoint;
    });

    // 加载配置预览
    if (online) {
      for (const card of ['claude', 'codex', 'generic']) {
        try {
          const cr = await fetch('/api/connect/config/' + card);
          const cd = await cr.json();
          const pre = document.querySelector('#preview-' + card + ' pre');
          if (pre) pre.textContent = JSON.stringify(cd.mcp_json || cd.config || cd, null, 2);
        } catch(e) {}
      }
    }
  } catch(e) {
    ['claude','codex','generic'].forEach(card => {
      const badge = document.getElementById('badge-' + card);
      if (badge) { badge.textContent = '○ 未连接'; badge.className = 'status-badge offline'; }
      const ep = document.getElementById('endpoint-' + card);
      if (ep) ep.textContent = MCP_URL;
    });
  }
}

function copyConfig(card) {
  const pre = document.querySelector('#preview-' + card + ' pre');
  const text = pre ? pre.textContent : '';
  
  const mcpJson = text || JSON.stringify({
    mcpServers: { 'stableagent-os': { transport: 'streamable_http', url: MCP_URL } }
  }, null, 2);
  
  navigator.clipboard.writeText(mcpJson).then(() => {
    showToast('✅ 已复制到剪贴板');
  }).catch(() => {
    // fallback
    const ta = document.createElement('textarea');
    ta.value = mcpJson;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    ta.remove();
    showToast('✅ 已复制到剪贴板');
  });

  // 展开预览
  const preview = document.getElementById('preview-' + card);
  if (preview) preview.classList.toggle('open');
}

function healthCheck() {
  fetch(HEALTH_URL)
    .then(r => r.json())
    .then(data => {
      showToast(data.ok ? '✅ 服务正常运行' : '❌ 服务异常');
      loadStatus();
    })
    .catch(() => showToast('❌ 无法连接到服务'));
}

// 页面加载
loadStatus();
setInterval(loadStatus, 30000);
