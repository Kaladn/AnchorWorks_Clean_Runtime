const state = {
  activeTab: 'chat',
  lastTrace: null,
  lexPack: 'all',
};

const SETTINGS_TRUTH_LABEL = 'diagnostic-only';

const $ = (id) => document.getElementById(id);

function setStatus(ok, text) {
  const strip = $('health-strip');
  if (!strip) return;
  strip.innerHTML = `<span class="dot ${ok ? 'ok' : 'bad'}"></span><span>${escapeHtml(text)}</span>`;
}

function escapeHtml(value) {
  const div = document.createElement('div');
  div.textContent = value == null ? '' : String(value);
  return div.innerHTML;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || data.error || `HTTP ${response.status}`);
  }
  return data;
}

function switchTab(tab) {
  state.activeTab = tab;
  document.querySelectorAll('.tab-button').forEach((button) => {
    button.classList.toggle('active', button.dataset.tab === tab);
  });
  document.querySelectorAll('.panel').forEach((panel) => {
    panel.classList.toggle('active', panel.id === `panel-${tab}`);
  });
  $('page-title').textContent = tab[0].toUpperCase() + tab.slice(1);
  if (tab === 'system') loadSystem();
  if (tab === 'lexicon') loadGenome();
}

function renderChatRows(rows) {
  const thread = $('chat-thread');
  if (!rows || !rows.length) {
    thread.innerHTML = '<div class="empty-state">No saved chat rows for this view.</div>';
    return;
  }
  thread.innerHTML = rows.map((row) => {
    const role = row.role || row.sender || 'unknown';
    const content = row.content || row.message || row.text || '';
    const mode = row.mode || row.route || '';
    const time = row.timestamp || row.created_at || '';
    return `
      <article class="message ${escapeHtml(role)}">
        <div class="message-meta">
          <span>${escapeHtml(role)}</span>
          <span>${escapeHtml(mode)}</span>
          <span>${escapeHtml(time)}</span>
        </div>
        <div>${escapeHtml(content)}</div>
      </article>
    `;
  }).join('');
}

async function loadChat() {
  try {
    const data = await api('/api/chat/history?limit=80');
    const rows = data.rows || data.messages || data.history || [];
    renderChatRows(rows);
  } catch (error) {
    $('chat-thread').innerHTML = `<div class="empty-state error">Chat history unavailable: ${escapeHtml(error.message)}</div>`;
  }
}

function evidenceFromPayload(payload) {
  if (!payload) return null;
  return payload.clearspeak || payload.response?.clearspeak || payload;
}

function setEvidence(payload) {
  state.lastTrace = payload || null;
  $('evidence-trace').textContent = payload ? JSON.stringify(payload, null, 2) : 'No answer trace selected yet.';
  const lanes = ['lexicon', 'local overlay', 'AWSC counts', 'flat document', 'visual packet', 'none'];
  $('lane-grid').innerHTML = lanes.map((lane) => `
    <div class="lane">
      <strong>${escapeHtml(lane)}</strong>
      <span>${payload ? 'inspect trace for support' : 'no trace selected'}</span>
    </div>
  `).join('');
}

async function sendChat(event) {
  event.preventDefault();
  const message = $('chat-input').value.trim();
  if (!message) return;
  const mode = $('chat-mode').value;
  const readOnly = $('read-only-query').checked;

  try {
    if (readOnly) {
      const queryMode = mode === 'counts' ? 'counts' : mode === 'documents' ? 'documents' : 'auto';
      const payload = await api('/api/clearspeak/query', {
        method: 'POST',
        body: JSON.stringify({ query: message, evidence_mode: queryMode }),
      });
      setEvidence(evidenceFromPayload(payload));
      renderChatRows([
        { role: 'user', mode: 'read-only', content: message, timestamp: new Date().toISOString() },
        { role: 'assistant', mode: 'clearspeak-read-only', content: payload.answer || payload.speech || JSON.stringify(payload), timestamp: new Date().toISOString() },
      ]);
    } else {
      const payload = await api('/api/chat/send', {
        method: 'POST',
        body: JSON.stringify({ message, mode }),
      });
      setEvidence(evidenceFromPayload(payload));
      await loadChat();
    }
    $('chat-input').value = '';
  } catch (error) {
    $('chat-thread').innerHTML = `<div class="empty-state error">Send failed: ${escapeHtml(error.message)}</div>`;
  }
}

async function stopResponse() {
  try {
    const payload = await api('/api/chat/stop', {
      method: 'POST',
      body: JSON.stringify({ reason: 'user_requested_stop' }),
    });
    setEvidence({ stop_requested: true, response: payload });
  } catch (error) {
    setEvidence({ stop_requested: true, error: error.message });
  }
}

async function searchLexicon(event) {
  event.preventDefault();
  const query = $('lexicon-query').value.trim();
  if (!query) return;
  const pack = state.lexPack === 'phrase' ? 'phrase' : 'all';
  const results = $('lexicon-results');
  try {
    const data = await api(`/api/search_lexicon?query=${encodeURIComponent(query)}&pack=${encodeURIComponent(pack)}`);
    const entries = Array.isArray(data) ? data : (data.entries || []);
    if (!entries.length) {
      results.innerHTML = '<div class="empty-state">No matching authority rows.</div>';
      return;
    }
    results.innerHTML = entries.slice(0, 40).map((entry) => `
      <article class="result-card">
        <strong>${escapeHtml(entry.word || entry.anchor || entry.phrase || entry.display || 'entry')}</strong>
        <span class="status-chip">${escapeHtml(entry.pack || entry.status || 'authority')}</span>
        <div class="muted">symbol: ${escapeHtml(entry.symbol || entry.hex || entry.binary || 'none')}</div>
        <div class="muted">status: ${escapeHtml(entry.status || 'unknown')}</div>
      </article>
    `).join('');
  } catch (error) {
    results.innerHTML = `<div class="empty-state error">Lexicon search unavailable: ${escapeHtml(error.message)}</div>`;
  }
}

async function loadGenome() {
  const target = $('genome-status');
  try {
    const data = await api('/api/symbol-genome/status');
    target.innerHTML = Object.entries(data).slice(0, 12).map(([key, value]) => `
      <div class="fact"><strong>${escapeHtml(key)}</strong><span>${escapeHtml(typeof value === 'object' ? JSON.stringify(value) : value)}</span></div>
    `).join('');
  } catch (error) {
    target.innerHTML = `<div class="empty-state error">Genome status unavailable: ${escapeHtml(error.message)}</div>`;
  }
}

async function loadSystem() {
  const facts = $('system-facts');
  const settings = $('settings-list');
  try {
    const [health, storage, inventory] = await Promise.all([
      api('/api/health'),
      api('/api/user/storage/status').catch((error) => ({ unavailable: error.message })),
      api('/api/settings/inventory').catch((error) => ({ settings: [], unavailable: error.message })),
    ]);
    facts.innerHTML = [
      ['health', health.ok ? 'ok' : 'not ok'],
      ['version', health.version || 'unknown'],
      ['data_root', health.data_root || 'unknown'],
      ['served_ui', 'UI2'],
      ['storage', storage.unavailable || 'available'],
    ].map(([key, value]) => `<div class="fact"><strong>${escapeHtml(key)}</strong><span>${escapeHtml(value)}</span></div>`).join('');

    const rows = inventory.settings || [];
    settings.innerHTML = rows.length
      ? rows.map((row) => `
        <div class="setting-row">
          <strong>${escapeHtml(row.label || row.id)}</strong>
          <span class="status-chip">${row.runtime_active ? 'runtime active' : escapeHtml(row.classification || SETTINGS_TRUTH_LABEL)}</span>
          <div class="muted">${escapeHtml(row.reason || '')}</div>
        </div>
      `).join('')
      : `<div class="empty-state">No settings inventory returned.</div>`;
  } catch (error) {
    facts.innerHTML = `<div class="empty-state error">System status unavailable: ${escapeHtml(error.message)}</div>`;
  }
}

async function boot() {
  document.querySelectorAll('.tab-button').forEach((button) => {
    button.addEventListener('click', () => switchTab(button.dataset.tab));
  });
  document.querySelectorAll('[data-action]').forEach((button) => {
    button.addEventListener('click', () => {
      const action = button.dataset.action;
      if (action === 'evidence') switchTab('evidence');
      if (action === 'lexicon') switchTab('lexicon');
      if (action === 'stop') stopResponse();
      if (action === 'counts') {
        $('chat-mode').value = 'counts';
        $('read-only-query').checked = true;
        $('chat-input').focus();
      }
    });
  });
  document.querySelectorAll('[data-lex-pack]').forEach((button) => {
    button.addEventListener('click', () => {
      state.lexPack = button.dataset.lexPack;
      document.querySelectorAll('[data-lex-pack]').forEach((other) => other.classList.toggle('active', other === button));
    });
  });

  $('chat-form').addEventListener('submit', sendChat);
  $('stop-response').addEventListener('click', stopResponse);
  $('refresh-chat').addEventListener('click', loadChat);
  $('lexicon-form').addEventListener('submit', searchLexicon);
  $('refresh-genome').addEventListener('click', loadGenome);
  $('refresh-system').addEventListener('click', loadSystem);
  $('copy-trace').addEventListener('click', async () => {
    if (state.lastTrace) await navigator.clipboard.writeText(JSON.stringify(state.lastTrace, null, 2));
  });

  try {
    const health = await api('/api/health');
    setStatus(Boolean(health.ok), `Runtime ${health.ok ? 'ready' : 'not ready'}`);
  } catch (error) {
    setStatus(false, `Runtime unavailable: ${error.message}`);
  }
  setEvidence(null);
  await Promise.all([loadChat(), loadGenome()]);
}

document.addEventListener('DOMContentLoaded', boot);
