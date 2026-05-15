const state = {
  activeTab: 'chat',
  lastTrace: null,
  lexPack: 'all',
  lastInvocation: null,
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

const CARD_RECIPES = {
  'evidence.trace.card': {
    title: 'Evidence Trace',
    purpose: 'Show why the current answer or selected command was produced.',
    risk: 'read',
    requiredRoutes: [],
  },
  'system.status.card': {
    title: 'System Status',
    purpose: 'Show real runtime facts from backend status routes.',
    risk: 'read',
    requiredRoutes: ['/api/health', '/api/settings/inventory'],
  },
};

function buildInvocation(cardId, surfaceText, intent, context = {}) {
  return {
    invocation_id: `inv_${Date.now().toString(36)}`,
    card_id: cardId,
    source: 'chat',
    surface_text: surfaceText,
    intent,
    context,
    risk: CARD_RECIPES[cardId]?.risk || 'read',
    confirmation_state: 'not_required',
    trace_id: `trace_${Date.now().toString(36)}`,
  };
}

function matchInvokedSurface(message) {
  const text = message.trim().toLowerCase();
  if (/^(evidence|show|open|review)\s*(the\s+)?evidence\b/.test(text) || text === 'evidence' || /why did (it|you|the system) choose/.test(text)) {
    return buildInvocation('evidence.trace.card', message, 'show_evidence');
  }
  if (/^(status|system|system status|show system status|open system status|runtime status|what settings are real)\b/.test(text)) {
    return buildInvocation('system.status.card', message, 'system_status');
  }
  return null;
}

function appendLocalChatRow(role, mode, content) {
  const thread = $('chat-thread');
  if (thread.querySelector('.empty-state')) thread.innerHTML = '';
  const article = document.createElement('article');
  article.className = `message ${role}`;
  article.innerHTML = `
    <div class="message-meta">
      <span>${escapeHtml(role)}</span>
      <span>${escapeHtml(mode)}</span>
      <span>${escapeHtml(new Date().toISOString())}</span>
    </div>
    <div>${escapeHtml(content)}</div>
  `;
  thread.appendChild(article);
  thread.scrollTop = thread.scrollHeight;
}

function showInvokedCard(invocation, bodyHtml) {
  const recipe = CARD_RECIPES[invocation.card_id];
  state.lastInvocation = invocation;
  $('invoked-card-title').textContent = recipe.title;
  $('invoked-card-purpose').textContent = recipe.purpose;
  $('invoked-card-body').innerHTML = `
    <div class="invocation-meta">
      <div><strong>intent:</strong> ${escapeHtml(invocation.intent)}</div>
      <div><strong>risk:</strong> ${escapeHtml(invocation.risk)}</div>
      <div><strong>trace:</strong> ${escapeHtml(invocation.trace_id)}</div>
      <div><strong>source:</strong> ${escapeHtml(invocation.surface_text)}</div>
    </div>
    ${bodyHtml}
  `;
  $('invoked-card-panel').hidden = false;
  document.querySelector('.chat-grid')?.classList.add('card-open');
}

function dismissInvokedCard() {
  state.lastInvocation = null;
  $('invoked-card-panel').hidden = true;
  $('invoked-card-body').innerHTML = '';
  document.querySelector('.chat-grid')?.classList.remove('card-open');
}

function runUiAction(action) {
  if (action === 'evidence') switchTab('evidence');
  if (action === 'lexicon') switchTab('lexicon');
  if (action === 'system') switchTab('system');
  if (action === 'stop') stopResponse();
  if (action === 'counts') {
    $('chat-mode').value = 'counts';
    $('read-only-query').checked = true;
    $('chat-input').focus();
  }
}

async function openEvidenceTraceCard(invocation) {
  const trace = state.lastTrace || { message: 'No answer trace is active yet.', evidence_lanes: ['none'] };
  showInvokedCard(invocation, `
    <pre class="trace-box">${escapeHtml(JSON.stringify(trace, null, 2))}</pre>
    <div class="card-action-row">
      <button class="secondary-button" type="button" data-action="evidence">Open Evidence Home</button>
    </div>
  `);
}

async function openSystemStatusCard(invocation) {
  try {
    const [health, inventory] = await Promise.all([
      api('/api/health'),
      api('/api/settings/inventory').catch((error) => ({ settings: [], unavailable: error.message })),
    ]);
    const settings = inventory.settings || [];
    showInvokedCard(invocation, `
      <div class="fact-list">
        <div class="fact"><strong>health</strong><span>${escapeHtml(health.ok ? 'ok' : 'not ok')}</span></div>
        <div class="fact"><strong>version</strong><span>${escapeHtml(health.version || 'unknown')}</span></div>
        <div class="fact"><strong>data_root</strong><span>${escapeHtml(health.data_root || 'unknown')}</span></div>
        <div class="fact"><strong>served_ui</strong><span>UI2</span></div>
        <div class="fact"><strong>runtime settings</strong><span>${escapeHtml(settings.filter((row) => row.runtime_active).map((row) => row.label || row.id).join(', ') || 'none')}</span></div>
        <div class="fact"><strong>diagnostic-only</strong><span>${escapeHtml(settings.filter((row) => !row.runtime_active).map((row) => row.label || row.id).join(', ') || 'none')}</span></div>
      </div>
      <div class="card-action-row">
        <button class="secondary-button" type="button" data-action="system">Open System Home</button>
      </div>
    `);
  } catch (error) {
    showInvokedCard(invocation, `<div class="empty-state error">System status unavailable: ${escapeHtml(error.message)}</div>`);
  }
}

async function handleInvokedSurface(message) {
  const invocation = matchInvokedSurface(message);
  if (!invocation) return false;
  appendLocalChatRow('user', 'surface-request', message);
  if (invocation.card_id === 'evidence.trace.card') await openEvidenceTraceCard(invocation);
  if (invocation.card_id === 'system.status.card') await openSystemStatusCard(invocation);
  appendLocalChatRow('assistant', 'surface-card', `Opened ${CARD_RECIPES[invocation.card_id].title}.`);
  return true;
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
    if (await handleInvokedSurface(message)) {
      $('chat-input').value = '';
      return;
    }
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
  document.addEventListener('click', (event) => {
    const button = event.target.closest('[data-action]');
    if (!button) return;
    runUiAction(button.dataset.action);
  });
  document.querySelectorAll('[data-lex-pack]').forEach((button) => {
    button.addEventListener('click', () => {
      state.lexPack = button.dataset.lexPack;
      document.querySelectorAll('[data-lex-pack]').forEach((other) => other.classList.toggle('active', other === button));
    });
  });

  $('chat-form').addEventListener('submit', sendChat);
  $('chat-input').addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      $('chat-form').requestSubmit();
    }
  });
  $('stop-response').addEventListener('click', stopResponse);
  $('refresh-chat').addEventListener('click', loadChat);
  $('lexicon-form').addEventListener('submit', searchLexicon);
  $('refresh-genome').addEventListener('click', loadGenome);
  $('refresh-system').addEventListener('click', loadSystem);
  $('copy-trace').addEventListener('click', async () => {
    if (state.lastTrace) await navigator.clipboard.writeText(JSON.stringify(state.lastTrace, null, 2));
  });
  $('dismiss-invoked-card').addEventListener('click', dismissInvokedCard);

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
