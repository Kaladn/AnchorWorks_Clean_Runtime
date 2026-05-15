// panel-genesis.js — Genesis Ingestion Control Surface (gn* namespace)
// Provides: gnInit(), gnGoto(), gnPrev(), gnNext(), gnNextPending(), gnSend(), gnMark()
// Depends on: core.js (bridgeApi, escapeHtml), genesis-cite.js (optional badges)
if (!window.bridgeApi) console.warn('core.js not loaded before panel-genesis.js');

// ── Module state ──────────────────────────────────────────────────────────────

let _gnBlocks   = [];       // [{tag, title, source, series}, ...] from /api/genesis/list
let _gnStatuses = {};       // { "G-0001": {status, date, notes}, ... }
let _gnActiveIdx = 0;       // currently displayed block index
let _gnState    = 'IDLE';   // IDLE | SENDING | CONFIRMING

// ── Init ──────────────────────────────────────────────────────────────────────

async function gnInit() {
    // Restore last position
    const saved = parseInt(localStorage.getItem('gn_active_idx') || '0', 10);
    _gnActiveIdx = isNaN(saved) ? 0 : saved;

    await Promise.all([_gnLoadBlocks(), _gnLoadStatus()]);

    _gnRenderList();
    _gnActivate(_gnActiveIdx, /*skipScroll=*/false);
}

async function _gnLoadBlocks() {
    try {
        const res  = await fetch(bridgeApi('/api/genesis/list'), { credentials: 'include' });
        const data = await res.json();
        if (Array.isArray(data)) {
            _gnBlocks = data;
            _gnUpdateBlockTotals();
        }
    } catch (e) {
        _gnSetSendStatus('Genesis service not reachable — is the bridge running?', 'error');
    }
}

async function _gnLoadStatus() {
    try {
        const res  = await fetch(bridgeApi('/api/genesis/ingestion/status'), { credentials: 'include' });
        const data = await res.json();
        if (data.ok) {
            _gnStatuses = data.statuses || {};
            _gnUpdateProgressBar(data);
        }
    } catch (_) { /* INGESTION_LOG unavailable — non-fatal */ }
}

// ── Block list (left column) ──────────────────────────────────────────────────

const _GN_COLOR = {
    INGESTED: '#00ff88',
    REJECTED: '#e94560',
    SKIPPED:  '#ffd700',
    PENDING:  'var(--text-secondary)',
};
const _GN_ICON = { INGESTED: '✓', REJECTED: '✗', SKIPPED: '⊘', PENDING: '·' };

function _gnRenderList() {
    const el = document.getElementById('gn-block-list');
    if (!el || !_gnBlocks.length) return;

    el.innerHTML = _gnBlocks.map((b, i) => {
        const st     = (_gnStatuses[b.tag] || {}).status || 'PENDING';
        const active = i === _gnActiveIdx;
        const color  = _GN_COLOR[st] || _GN_COLOR.PENDING;
        const icon   = _GN_ICON[st]  || '·';
        return `<div class="gn-list-item" id="gn-item-${i}"
            onclick="gnGoto(${i})"
            style="padding:5px 8px;cursor:pointer;border-radius:4px;margin-bottom:2px;
                   background:${active ? 'var(--accent-bg)' : 'transparent'};
                   border-left:3px solid ${active ? '#00d4ff' : 'transparent'};">
          <div style="display:flex;align-items:center;gap:5px;">
            <span style="color:${color};font-weight:700;font-size:11px;width:12px;text-align:center;">${icon}</span>
            <span style="font-size:10px;font-weight:700;color:#00d4ff;letter-spacing:0.02em;">${b.tag}</span>
          </div>
          <div style="font-size:10px;color:var(--text-secondary);white-space:nowrap;
                      overflow:hidden;text-overflow:ellipsis;max-width:185px;margin-top:1px;">
            ${escapeHtml(b.title || '')}
          </div>
        </div>`;
    }).join('');

    // Scroll active into view
    const active = document.getElementById(`gn-item-${_gnActiveIdx}`);
    if (active) active.scrollIntoView({ block: 'nearest' });
}

function _gnUpdateBlockTotals() {
    const total = _gnBlocks.length;
    const totalEl = document.getElementById('gn-stat-total');
    const labelEl = document.getElementById('gn-block-count-label');
    if (totalEl) totalEl.textContent = String(total);
    if (labelEl) labelEl.textContent = `${total} blocks`;
}

function _gnUpdateProgressBar(data) {
    const ingested = data.INGESTED || 0;
    const total    = data.total || _gnBlocks.length || 0;
    const pct      = total > 0 ? Math.round((ingested / total) * 100) : 0;

    const elI = document.getElementById('gn-stat-ingested');
    const elP = document.getElementById('gn-stat-pending');
    const elF = document.getElementById('gn-progress-fill');
    const elPc = document.getElementById('gn-stat-pct');
    const elT = document.getElementById('gn-stat-total');

    if (elI)  elI.textContent  = ingested;
    if (elP)  elP.textContent  = data.PENDING || 0;
    if (elF)  elF.style.width  = pct + '%';
    if (elPc) elPc.textContent = pct + '%';
    if (elT)  elT.textContent  = total;
}

// ── Active block (right column) ───────────────────────────────────────────────

async function _gnActivate(idx, skipScroll) {
    if (!_gnBlocks.length) return;
    idx = Math.max(0, Math.min(idx, _gnBlocks.length - 1));
    _gnActiveIdx = idx;
    localStorage.setItem('gn_active_idx', String(idx));

    _gnSetState('IDLE');
    _gnSetSendStatus('');
    _gnRenderList();

    const b = _gnBlocks[idx];

    const tagEl   = document.getElementById('gn-active-tag');
    const titleEl = document.getElementById('gn-active-title');
    const metaEl  = document.getElementById('gn-active-meta');
    const bodyEl  = document.getElementById('gn-block-body');
    const respEl  = document.getElementById('gn-response-area');

    if (tagEl)   tagEl.textContent   = b.tag;
    if (titleEl) titleEl.textContent = b.title || '';
    if (respEl)  {
        const pre = respEl.querySelector('pre');
        if (pre) pre.textContent = '';
        respEl.style.display = 'none';
    }

    const st  = (_gnStatuses[b.tag] || {}).status || 'PENDING';
    const dt  = (_gnStatuses[b.tag] || {}).date   || '';
    if (metaEl) {
        const parts = [
            b.series ? `Series ${b.series}` : '',
            b.source || '',
            dt ? `Last logged: ${dt}` : '',
            `Status: ${st}`,
        ].filter(Boolean);
        metaEl.textContent = parts.join('  ·  ');
        metaEl.style.color = _GN_COLOR[st] || 'var(--text-secondary)';
    }

    // Fetch full block body from the Genesis service
    if (bodyEl) {
        bodyEl.textContent = 'Loading…';
        try {
            const res  = await fetch(
                bridgeApi(`/api/genesis/cite/${encodeURIComponent(b.tag)}`),
                { credentials: 'include' }
            );
            const data = await res.json();
            if (data.ok && data.result) {
                bodyEl.textContent = data.result.body || '(empty body)';
            } else {
                bodyEl.textContent = `(error: ${data.detail || data.error || 'unknown'})`;
            }
        } catch (e) {
            bodyEl.textContent = `(fetch error: ${e.message})`;
        }
    }
}

// ── Navigation ────────────────────────────────────────────────────────────────

function gnGoto(idx)  { _gnActivate(idx); }
function gnPrev()     { _gnActivate(_gnActiveIdx - 1); }
function gnNext()     { _gnActivate(_gnActiveIdx + 1); }

function gnNextPending() {
    // Scan forward from current position
    for (let i = _gnActiveIdx + 1; i < _gnBlocks.length; i++) {
        if (((_gnStatuses[_gnBlocks[i].tag] || {}).status || 'PENDING') === 'PENDING') {
            _gnActivate(i);
            return;
        }
    }
    // Wrap from top
    for (let i = 0; i < _gnActiveIdx; i++) {
        if (((_gnStatuses[_gnBlocks[i].tag] || {}).status || 'PENDING') === 'PENDING') {
            _gnActivate(i);
            return;
        }
    }
    _gnSetSendStatus('All blocks have been processed!', 'ok');
}

// ── Send block to model ───────────────────────────────────────────────────────

async function gnSend() {
    if (_gnState !== 'IDLE') return;
    if (!_gnBlocks.length) return;

    const b      = _gnBlocks[_gnActiveIdx];
    const bodyEl = document.getElementById('gn-block-body');
    const body   = bodyEl ? bodyEl.textContent : '';

    if (!body || body === 'Loading…' || body.startsWith('(')) {
        _gnSetSendStatus('Block body not loaded yet — wait a moment', 'warn');
        return;
    }

    const prompt =
        `[GENESIS INGEST] Please read and confirm your understanding of this AnchorWorks ` +
        `documentation block.\n\n` +
        `Block: ${b.tag} — ${b.title || ''}\n\n` +
        `${body}\n\n` +
        `Please confirm with: "Understood. Key facts from ${b.tag}: ..." ` +
        `and list 3–5 key facts.`;

    _gnSetState('SENDING');
    _gnSetSendStatus('Sending to model…', 'info');

    try {
        const model = localStorage.getItem('gptModel') || '';
        const res   = await fetch(bridgeApi('/api/chat/send'), {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                message:         prompt,
                mode:            'llm',
                model:           model,
                session_id:      'genesis-ingest',
                routing_enabled: false,
                tools_enabled:   false,
                topk:            0,
            }),
        });

        const data = await res.json();

        if (data.error) {
            throw new Error(data.error.message || JSON.stringify(data.error));
        }

        // Extract reply — support both chain and single-response formats
        const reply = data.contributions?.[0]?.content || data.response || '(no response)';

        // Show model response in the dedicated response area
        const respEl    = document.getElementById('gn-response-area');
        const respPreEl = respEl?.querySelector('pre');
        if (respEl) {
            if (respPreEl) respPreEl.textContent = reply;
            respEl.style.display = 'block';
        }
        _gnSetSendStatus('Model responded — confirm or reject below', 'ok');
        _gnSetState('CONFIRMING');

    } catch (err) {
        _gnSetSendStatus(`Send failed: ${err.message}`, 'error');
        _gnSetState('IDLE');
    }
}

// ── Mark ingestion status ─────────────────────────────────────────────────────

async function gnMark(status) {
    if (_gnState !== 'CONFIRMING') return;
    const b = _gnBlocks[_gnActiveIdx];

    try {
        const res  = await fetch(bridgeApi('/api/genesis/ingestion/mark'), {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ tag: b.tag, status, notes: '' }),
        });
        const data = await res.json();
        if (!data.ok) throw new Error(data.detail || 'Mark failed');

        // Update local cache immediately
        _gnStatuses[b.tag] = { status, date: data.date || '', notes: '' };
        await _gnLoadStatus();   // refresh counts
        _gnRenderList();

        _gnSetSendStatus(`${b.tag} marked ${status}`, 'ok');
        _gnSetState('IDLE');

        if (status !== 'PENDING') {
            setTimeout(gnNextPending, 700);
        }
    } catch (err) {
        _gnSetSendStatus(`Mark failed: ${err.message}`, 'error');
    }
}

// ── State machine helpers ─────────────────────────────────────────────────────

function _gnSetState(state) {
    _gnState = state;

    const sendBtn    = document.getElementById('gn-send-btn');
    const confirmBar = document.getElementById('gn-confirm-bar');
    const stateLabel = document.getElementById('gn-state-label');

    if (sendBtn) {
        sendBtn.disabled      = state !== 'IDLE';
        sendBtn.style.opacity = state !== 'IDLE' ? '0.5' : '1';
        sendBtn.style.cursor  = state !== 'IDLE' ? 'not-allowed' : 'pointer';
    }
    if (confirmBar) {
        confirmBar.style.display = state === 'CONFIRMING' ? 'flex' : 'none';
    }
    if (stateLabel) {
        const labels = {
            IDLE:        'Ready to send',
            SENDING:     'Waiting for model…',
            CONFIRMING:  'Did the model confirm the block?',
        };
        stateLabel.textContent = labels[state] || '';
    }
}

function _gnSetSendStatus(msg, level) {
    const el = document.getElementById('gn-send-status');
    if (!el) return;
    const colors = {
        info:     'var(--text-secondary)',
        ok:       '#00ff88',
        error:    '#e94560',
        warn:     '#ffd700',
    };
    el.style.color   = colors[level] || colors.info;
    el.textContent   = msg;
}

// ── Expose globals ────────────────────────────────────────────────────────────
window.gnInit        = gnInit;
window.gnGoto        = gnGoto;
window.gnPrev        = gnPrev;
window.gnNext        = gnNext;
window.gnNextPending = gnNextPending;
window.gnSend        = gnSend;
window.gnMark        = gnMark;
