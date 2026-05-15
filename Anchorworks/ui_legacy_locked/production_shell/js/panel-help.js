// panel-help.js — Help System + Tutorial Mode (help*, ht* namespaces)
// Extracted from anchorworks_production.js L5454-5951
if (!window.bridgeApi) console.warn('core.js not loaded before panel-help.js');

// ── Help System (contextual help, Alt + right-click → "What is this?") ─────
let _helpContent = {};        // cache: { helpId: responseData }
let _helpCurrentId = null;
let _helpCurrentLayer = 1;
let _helpMenuTarget = null;   // element that was right-clicked
let _helpSearchTimer = null;
let _hcCatalog = [];
let _hcSelectedId = null;
let _hcCurrentLayer = 1;
let _hcStatus = null;
let _hcFilterText = '';
const _HC_CHAT_STORAGE_KEY = 'anchorworks_help_center_chat_v1';
let _hcChatState = null;

function helpInit() {
    document.addEventListener('contextmenu', helpRightClick);
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            helpClose();
            const ctxMenu = document.getElementById('help-ctx-menu');
            if (ctxMenu) ctxMenu.classList.remove('visible');
        }
    });
    document.addEventListener('click', () => {
        const ctxMenu = document.getElementById('help-ctx-menu');
        if (ctxMenu) ctxMenu.classList.remove('visible');
    });
}

function helpRightClick(event) {
    // Only intercept when Alt is held — otherwise pass through to OS context menu
    if (!event.altKey) return;

    // Walk up from target to find nearest data-help-id
    let el = event.target;
    let helpId = null;
    while (el && el !== document.body) {
        if (el.dataset && el.dataset.helpId) {
            helpId = el.dataset.helpId;
            break;
        }
        el = el.parentElement;
    }
    if (!helpId) return;

    event.preventDefault();
    event.stopPropagation();
    _helpMenuTarget = helpId;

    const ctxMenu = document.getElementById('help-ctx-menu');
    if (!ctxMenu) return;
    ctxMenu.style.left = event.clientX + 'px';
    ctxMenu.style.top = event.clientY + 'px';
    ctxMenu.classList.add('visible');
}

function helpOpenFromMenu() {
    const ctxMenu = document.getElementById('help-ctx-menu');
    if (ctxMenu) ctxMenu.classList.remove('visible');
    if (_helpMenuTarget) helpOpen(_helpMenuTarget);
}

async function helpOpen(helpId) {
    _helpCurrentId = helpId;
    _helpCurrentLayer = 1;

    const panel = document.getElementById('help-panel');
    const content = document.getElementById('help-panel-content');
    const title = document.getElementById('help-panel-title');
    const searchResults = document.getElementById('help-search-results');
    const searchInput = document.getElementById('help-search-input');
    if (!panel || !content) return;

    // Show panel immediately with loading state
    if (searchResults) searchResults.style.display = 'none';
    if (searchInput) searchInput.value = '';
    content.innerHTML = '<div style="color: var(--text-secondary); padding: 20px;">Loading...</div>';
    if (title) title.textContent = 'Help';
    panel.classList.add('open');

    // Check cache first
    if (_helpContent[helpId]) {
        helpRenderEntry(_helpContent[helpId], 1);
        return;
    }

    try {
        const resp = await fetch(bridgeApi('/api/help/content/' + encodeURIComponent(helpId)));
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        const data = await resp.json();
        if (data.found) {
            _helpContent[helpId] = data;
            helpRenderEntry(data, 1);
        } else {
            content.innerHTML = '<div style="color: var(--text-secondary); padding: 20px;">No help available for <code>' +
                _helpEsc(helpId) + '</code>.</div>';
        }
    } catch (err) {
        content.innerHTML = '<div style="color: var(--danger); padding: 20px;">Failed to load help: ' +
            _helpEsc(err.message) + '</div>';
    }
}

function _helpBuildLayerHtml(data, layer) {
    let html = '';

    if (data.category) {
        html += '<span class="help-category-badge">' + _helpEsc(data.category) + '</span>';
    }

    if (layer === 1 && data.layer1) {
        const l = data.layer1;
        if (l.what) html += '<h3>What it does</h3><p>' + _helpEsc(l.what) + '</p>';
        if (l.why) html += '<h3>Why it matters</h3><p>' + _helpEsc(l.why) + '</p>';
        if (l.consequence) html += '<h3>What happens</h3><p>' + _helpEsc(l.consequence) + '</p>';
        if (l.avoid) html += '<h3>Common mistake</h3><p>' + _helpEsc(l.avoid) + '</p>';
    } else if (layer === 2 && data.layer2) {
        const l = data.layer2;
        if (l.examples && l.examples.length) {
            html += '<h3>Examples</h3><ul>';
            l.examples.forEach(ex => { html += '<li>' + _helpEsc(ex) + '</li>'; });
            html += '</ul>';
        }
        if (l.relationships && l.relationships.length) {
            html += '<h3>Related</h3><ul>';
            l.relationships.forEach(r => { html += '<li>' + _helpEsc(r) + '</li>'; });
            html += '</ul>';
        }
        if (l.common_mistakes && l.common_mistakes.length) {
            html += '<h3>Common mistakes</h3><ul>';
            l.common_mistakes.forEach(m => { html += '<li>' + _helpEsc(m) + '</li>'; });
            html += '</ul>';
        }
        if (l.typical_workflow) html += '<h3>Typical workflow</h3><p>' + _helpEsc(l.typical_workflow) + '</p>';
    } else if (layer === 3 && data.layer3) {
        const l = data.layer3;
        html += '<h3>Technical Details</h3>';
        html += '<table class="help-tech-table">';
        if (l.api_param) html += '<tr><td>API param</td><td><code>' + _helpEsc(l.api_param) + '</code></td></tr>';
        if (l.api_endpoint) html += '<tr><td>API endpoint</td><td><code>' + _helpEsc(l.api_endpoint) + '</code></td></tr>';
        if (l.type) html += '<tr><td>Type</td><td>' + _helpEsc(l.type) + '</td></tr>';
        if (l.range) html += '<tr><td>Range</td><td>' + _helpEsc(JSON.stringify(l.range)) + '</td></tr>';
        if (l.default !== undefined) html += '<tr><td>Default</td><td>' + _helpEsc(String(l.default)) + '</td></tr>';
        if (l.config_path) html += '<tr><td>Config path</td><td><code>' + _helpEsc(l.config_path) + '</code></td></tr>';
        if (l.data_source) html += '<tr><td>Data source</td><td><code>' + _helpEsc(l.data_source) + '</code></td></tr>';
        html += '</table>';
        if (l.edge_cases && l.edge_cases.length) {
            html += '<h3>Edge cases</h3><ul>';
            l.edge_cases.forEach(e => { html += '<li>' + _helpEsc(e) + '</li>'; });
            html += '</ul>';
        }
        if (l.related_params && l.related_params.length) {
            html += '<h3>Related params</h3><ul>';
            l.related_params.forEach(p => { html += '<li>' + _helpEsc(p) + '</li>'; });
            html += '</ul>';
        }
        if (l.related_endpoints && l.related_endpoints.length) {
            html += '<h3>Related endpoints</h3><ul>';
            l.related_endpoints.forEach(p => { html += '<li><code>' + _helpEsc(p) + '</code></li>'; });
            html += '</ul>';
        }
    } else {
        html += '<p style="color: var(--text-secondary);">No Layer ' + layer + ' content available.</p>';
    }

    return html;
}

function helpRenderEntry(data, layer) {
    const content = document.getElementById('help-panel-content');
    const title = document.getElementById('help-panel-title');
    const nav = document.getElementById('help-panel-nav');
    const btnMore = document.getElementById('help-btn-more');
    const btnTech = document.getElementById('help-btn-tech');
    if (!content) return;

    _helpCurrentLayer = layer;
    if (title) title.textContent = data.label || data.help_id || 'Help';

    let html = _helpBuildLayerHtml(data, layer);

    // Tutorial button (when pack available)
    if (data.tutorial_available && layer === 1) {
        html += '<div style="margin-top: 16px; padding-top: 12px; border-top: 1px solid var(--border);">' +
            '<button class="btn btn-primary btn-sm" style="width:100%;" ' +
            'onclick="htStart(\'' + _helpEsc(data.tutorial_available) + '\')">Start Tutorial</button></div>';
    }

    content.innerHTML = html;

    // Update nav buttons
    if (nav) {
        nav.style.display = 'flex';
        if (btnMore) {
            btnMore.style.display = (layer < 2 && data.layer2) ? '' : 'none';
            btnMore.textContent = 'Show me more';
            btnMore.onclick = () => helpShowLayer(2);
        }
        if (btnTech) {
            btnTech.style.display = (data.layer3 && layer < 3) ? '' : 'none';
        }
        // Add "Back" button behavior
        if (layer > 1) {
            if (btnMore) {
                btnMore.style.display = '';
                btnMore.textContent = '← Back';
                btnMore.onclick = () => helpShowLayer(layer - 1);
            }
            if (btnTech && layer === 2 && data.layer3) btnTech.style.display = '';
        }
    }
}

function helpShowLayer(n) {
    if (!_helpCurrentId || !_helpContent[_helpCurrentId]) return;
    helpRenderEntry(_helpContent[_helpCurrentId], n);
}

function helpClose() {
    const panel = document.getElementById('help-panel');
    if (panel) panel.classList.remove('open');
    _helpCurrentId = null;
    _helpCurrentLayer = 1;
    // Clean up tutorial mode if active
    if (_htSessionId) htExit();
}

function helpSearchDebounced(q) {
    if (_helpSearchTimer) clearTimeout(_helpSearchTimer);
    _helpSearchTimer = setTimeout(() => helpSearch(q), 300);
}

async function helpSearch(query) {
    const resultsEl = document.getElementById('help-search-results');
    const contentEl = document.getElementById('help-panel-content');
    const nav = document.getElementById('help-panel-nav');
    if (!resultsEl) return;

    if (!query || query.trim().length < 2) {
        resultsEl.style.display = 'none';
        if (contentEl) contentEl.style.display = '';
        if (nav) nav.style.display = _helpCurrentId ? 'flex' : 'none';
        return;
    }

    try {
        const resp = await fetch(bridgeApi('/api/help/search?q=' + encodeURIComponent(query.trim())));
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        const data = await resp.json();

        if (contentEl) contentEl.style.display = 'none';
        if (nav) nav.style.display = 'none';
        resultsEl.style.display = '';

        if (!data.results || data.results.length === 0) {
            resultsEl.innerHTML = '<div style="padding: 12px; color: var(--text-secondary);">No results for "' +
                _helpEsc(query) + '"</div>';
            return;
        }

        let html = '';
        data.results.forEach(r => {
            html += '<div class="help-search-item" onclick="helpOpen(\'' + _helpEsc(r.help_id) + '\')">' +
                '<div style="font-weight: 600; font-size: 13px;">' + _helpEsc(r.label) + '</div>' +
                '<div style="font-size: 11px; color: var(--text-secondary);">' + _helpEsc(r.category) + '</div>' +
                (r.snippet ? '<div style="font-size: 12px; margin-top: 4px;">' + _helpEsc(r.snippet) + '</div>' : '') +
                '</div>';
        });
        resultsEl.innerHTML = html;
    } catch (err) {
        resultsEl.style.display = '';
        resultsEl.innerHTML = '<div style="padding: 12px; color: var(--danger);">Search failed: ' +
            _helpEsc(err.message) + '</div>';
    }
}

function _helpEsc(str) {
    if (!str) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}


// ── Help Center (Knowledge page) ──────────────────────────────────────────

function hcGetSelectedHelpId() {
    return _hcSelectedId || '';
}

function _hcNewBranchId() {
    const now = new Date();
    const pad = (n) => String(n).padStart(2, '0');
    const ymd = `${now.getUTCFullYear()}${pad(now.getUTCMonth() + 1)}${pad(now.getUTCDate())}`;
    const hms = `${pad(now.getUTCHours())}${pad(now.getUTCMinutes())}${pad(now.getUTCSeconds())}`;
    const rand = Math.random().toString(16).slice(2, 10).padEnd(8, '0');
    return `side_${ymd}_${hms}_${rand.slice(0, 8)}`;
}

function _hcChatDefaultState() {
    return {
        provider: 'ollama',
        model: localStorage.getItem('gptModel') || '',
        branch: _hcNewBranchId(),
        messages: [{
            role: 'assistant',
            content: 'Help Chat is ready. Ask about the selected help topic, and I will answer only from the current AnchorWorks help dataset. If it is not documented there, I will say so.',
            ts: new Date().toISOString(),
        }],
        providers: [],
        localModels: [],
        sending: false,
    };
}

function _hcChatLoadState() {
    try {
        const raw = localStorage.getItem(_HC_CHAT_STORAGE_KEY);
        if (!raw) return _hcChatDefaultState();
        const parsed = JSON.parse(raw);
        return {
            ..._hcChatDefaultState(),
            ...parsed,
            providers: [],
            localModels: [],
            sending: false,
            messages: Array.isArray(parsed?.messages) && parsed.messages.length
                ? parsed.messages
                : _hcChatDefaultState().messages,
        };
    } catch {
        return _hcChatDefaultState();
    }
}

function _hcChatPersist() {
    if (!_hcChatState) return;
    const { provider, model, branch, messages } = _hcChatState;
    localStorage.setItem(_HC_CHAT_STORAGE_KEY, JSON.stringify({ provider, model, branch, messages }));
}

function _hcLlmBase() {
    return String(window.ANCHORWORKS_CONFIG?.llm || 'http://127.0.0.1:11435').replace(/\/$/, '');
}

function _hcProviderLabel(name) {
    if (name === 'ollama') return 'Local (Ollama)';
    const meta = (typeof PROVIDER_META !== 'undefined' ? PROVIDER_META[name] : null);
    return meta?.name || name;
}

function _hcProviderModels(name) {
    if (name === 'ollama') return _hcChatState?.localModels || [];
    const meta = (typeof PROVIDER_META !== 'undefined' ? PROVIDER_META[name] : null);
    return Array.isArray(meta?.models) ? meta.models : [];
}

function _hcEnsureProviderModel() {
    if (!_hcChatState) return;
    const providers = (_hcChatState.providers || []).map(p => p.name);
    if (!providers.includes(_hcChatState.provider)) {
        _hcChatState.provider = providers.includes('ollama') ? 'ollama' : (providers[0] || 'ollama');
    }
    const models = _hcProviderModels(_hcChatState.provider);
    const preferredLocal = localStorage.getItem('gptModel') || '';
    if (!models.length) {
        _hcChatState.model = '';
        return;
    }
    if (_hcChatState.provider === 'ollama' && preferredLocal && models.includes(preferredLocal)) {
        _hcChatState.model = preferredLocal;
        return;
    }
    if (!models.includes(_hcChatState.model)) {
        _hcChatState.model = models[0];
    }
}

async function _hcLoadProviders() {
    const providers = [{ name: 'ollama', configured: true }];
    try {
        const resp = await fetch(bridgeApi('/api/providers'), {
            credentials: 'include',
            signal: AbortSignal.timeout(2500),
        });
        if (!resp.ok) return providers;
        const data = await resp.json();
        for (const prov of (data.providers || [])) {
            if (prov?.name && prov.configured) providers.push({ name: prov.name, configured: true });
        }
    } catch {
        // Keep local provider when provider config is unavailable.
    }
    return providers;
}

async function _hcLoadLocalModels() {
    try {
        const resp = await fetch(`${_hcLlmBase()}/api/tags`, {
            credentials: 'include',
            signal: AbortSignal.timeout(3000),
        });
        if (!resp.ok) return [];
        const data = await resp.json();
        return (data.models || []).map(m => m.name).filter(Boolean);
    } catch {
        return [];
    }
}

function _hcChatFocusLabel() {
    if (!_hcSelectedId) return 'Catalog search';
    const row = (_hcCatalog || []).find(item => item.help_id === _hcSelectedId);
    return row ? `${row.label} (${row.help_id})` : _hcSelectedId;
}

function _hcChatMessageHtml(msg) {
    const role = msg.role || 'assistant';
    const label = role === 'user' ? 'You' : role === 'system' ? 'System' : 'Guide';
    return `
        <div class="hc-chat-msg ${_helpEsc(role)}">
            <div class="hc-chat-bubble">
                <div class="hc-chat-role">${_helpEsc(label)}</div>
                <div class="hc-chat-text">${_helpEsc(msg.content || '')}</div>
            </div>
        </div>
    `;
}

function _hcUpdateChatFocus() {
    const el = document.getElementById('hc-chat-focus');
    if (el) el.textContent = _hcChatFocusLabel();
}

function hcRenderChat() {
    if (!_hcChatState) _hcChatState = _hcChatLoadState();
    const providerEl = document.getElementById('hc-provider-select');
    const modelEl = document.getElementById('hc-model-select');
    const transcript = document.getElementById('hc-chat-transcript');
    const branchEl = document.getElementById('hc-branch-id');
    const sendBtn = document.getElementById('hc-chat-send');
    if (!providerEl || !modelEl || !transcript || !branchEl || !sendBtn) return;

    providerEl.innerHTML = (_hcChatState.providers || []).map(prov =>
        `<option value="${_helpEsc(prov.name)}"${prov.name === _hcChatState.provider ? ' selected' : ''}>${_helpEsc(_hcProviderLabel(prov.name))}</option>`
    ).join('');

    const models = _hcProviderModels(_hcChatState.provider);
    modelEl.innerHTML = models.length
        ? models.map(name => `<option value="${_helpEsc(name)}"${name === _hcChatState.model ? ' selected' : ''}>${_helpEsc(name)}</option>`).join('')
        : '<option value="">No models available</option>';
    modelEl.disabled = !models.length;

    transcript.innerHTML = (_hcChatState.messages || []).map(_hcChatMessageHtml).join('');
    transcript.scrollTop = transcript.scrollHeight;
    branchEl.textContent = _hcChatState.branch;
    sendBtn.disabled = _hcChatState.sending;
    sendBtn.textContent = _hcChatState.sending ? 'Sending...' : 'Send';
    _hcUpdateChatFocus();
}

async function _hcInitChat(force = false) {
    const transcript = document.getElementById('hc-chat-transcript');
    if (!transcript) return;
    if (!_hcChatState || force) _hcChatState = _hcChatLoadState();
    _hcChatState.providers = await _hcLoadProviders();
    _hcChatState.localModels = await _hcLoadLocalModels();
    _hcEnsureProviderModel();
    _hcChatPersist();
    hcRenderChat();
}

function hcProviderChanged() {
    if (!_hcChatState) _hcChatState = _hcChatLoadState();
    const providerEl = document.getElementById('hc-provider-select');
    _hcChatState.provider = providerEl?.value || 'ollama';
    _hcEnsureProviderModel();
    _hcChatPersist();
    hcRenderChat();
}

function hcModelChanged() {
    if (!_hcChatState) _hcChatState = _hcChatLoadState();
    const modelEl = document.getElementById('hc-model-select');
    _hcChatState.model = modelEl?.value || '';
    _hcChatPersist();
}

function hcResetChat() {
    const provider = _hcChatState?.provider || 'ollama';
    const model = _hcChatState?.model || (localStorage.getItem('gptModel') || '');
    _hcChatState = {
        ..._hcChatDefaultState(),
        provider,
        model,
        providers: _hcChatState?.providers || [],
        localModels: _hcChatState?.localModels || [],
    };
    _hcEnsureProviderModel();
    _hcChatPersist();
    hcRenderChat();
}

async function hcSend() {
    if (!_hcChatState) _hcChatState = _hcChatLoadState();
    const input = document.getElementById('hc-chat-input');
    const text = (input?.value || '').trim();
    if (!text || _hcChatState.sending) return;

    _hcChatState.messages.push({ role: 'user', content: text, ts: new Date().toISOString() });
    _hcChatState.sending = true;
    _hcChatPersist();
    if (input) input.value = '';
    hcRenderChat();

    try {
        const resp = await fetch(bridgeApi('/api/help/chat'), {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: text,
                mode: 'llm',
                local_model: _hcChatState.model || undefined,
                hub_provider: _hcChatState.provider || 'ollama',
                side_chat_id: _hcChatState.branch,
                session_id: 'help_guide',
                tools_enabled: false,
                focus_help_id: _hcSelectedId || undefined,
            }),
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || data?.error) {
            throw new Error(data?.error?.message || data?.detail || `HTTP ${resp.status}`);
        }
        _hcChatState.messages.push({
            role: 'assistant',
            content: (data.response || '').trim() || '(No response)',
            ts: new Date().toISOString(),
        });
    } catch (e) {
        _hcChatState.messages.push({
            role: 'system',
            content: `Help chat error: ${e.message}`,
            ts: new Date().toISOString(),
        });
    } finally {
        _hcChatState.sending = false;
        _hcChatPersist();
        hcRenderChat();
        input?.focus();
    }
}

function hcRenderStats() {
    const status = _hcStatus || {};
    const cats = status.categories || {};
    const layers = status.layers_coverage || {};
    const totalIds = document.getElementById('hc-total-ids');
    const catEl = document.getElementById('hc-categories');
    const l1 = document.getElementById('hc-layer1');
    const l2 = document.getElementById('hc-layer2');
    const l3 = document.getElementById('hc-layer3');
    if (totalIds) totalIds.textContent = String(status.total_ids ?? '—');
    if (catEl) catEl.textContent = String(Object.keys(cats).length || '—');
    if (l1) l1.textContent = String(layers.layer1 ?? '—');
    if (l2) l2.textContent = String(layers.layer2 ?? '—');
    if (l3) l3.textContent = String(layers.layer3 ?? '—');
}

function hcRenderCatalog(items) {
    const resultsEl = document.getElementById('hc-results');
    const countEl = document.getElementById('hc-result-count');
    if (!resultsEl) return;
    if (countEl) countEl.textContent = `${items.length} topic${items.length === 1 ? '' : 's'}`;
    if (!items.length) {
        resultsEl.innerHTML = '<div class="hc-empty">No help topics match this filter.</div>';
        return;
    }
    resultsEl.innerHTML = items.map(item => `
        <div class="hc-result${item.help_id === _hcSelectedId ? ' active' : ''}" onclick="hcSelect('${_helpEsc(item.help_id)}')">
            <div class="hc-result-title">${_helpEsc(item.label || item.help_id)}</div>
            <div class="hc-result-meta">${_helpEsc(item.category || 'Uncategorized')} • ${_helpEsc(item.help_id)}</div>
            ${item.snippet ? `<div class="hc-result-snippet">${_helpEsc(item.snippet)}</div>` : ''}
        </div>
    `).join('');
}

function hcApplyFilters() {
    const category = document.getElementById('hc-category')?.value || '';
    const query = (_hcFilterText || '').trim().toLowerCase();
    const items = (_hcCatalog || []).filter(item => {
        const inCategory = !category || item.category === category;
        if (!inCategory) return false;
        if (!query) return true;
        const hay = [
            item.help_id,
            item.label,
            item.category,
            item.snippet,
            item.difficulty,
        ].join(' ').toLowerCase();
        return hay.includes(query);
    });
    hcRenderCatalog(items);
    if (items.length && !_hcSelectedId) {
        hcSelect(items[0].help_id);
    } else if (_hcSelectedId && !items.some(item => item.help_id === _hcSelectedId)) {
        _hcSelectedId = null;
        hcRenderDetail(null);
    }
}

function hcHandleSearch(value) {
    _hcFilterText = value || '';
    clearTimeout(_helpSearchTimer);
    _helpSearchTimer = setTimeout(() => hcApplyFilters(), 150);
}

function hcRenderDetail(data) {
    const idEl = document.getElementById('hc-detail-help-id');
    const titleEl = document.getElementById('hc-detail-title');
    const badgesEl = document.getElementById('hc-detail-badges');
    const bodyEl = document.getElementById('hc-detail-body');
    const tutorialBtn = document.getElementById('hc-start-tutorial');
    if (!idEl || !titleEl || !badgesEl || !bodyEl || !tutorialBtn) return;

    if (!data) {
        idEl.textContent = 'Select a help topic';
        titleEl.textContent = 'Help topic';
        badgesEl.innerHTML = '';
        bodyEl.innerHTML = '<div class="hc-empty">Choose a help topic from the catalog to explore it here.</div>';
        tutorialBtn.style.display = 'none';
        _hcUpdateChatFocus();
        return;
    }

    idEl.textContent = data.help_id || '';
    titleEl.textContent = data.label || data.help_id || 'Help topic';

    const badges = [];
    if (data.category) badges.push(`<span class="hc-badge">${_helpEsc(data.category)}</span>`);
    if (data.difficulty) badges.push(`<span class="hc-badge">${_helpEsc(data.difficulty)}</span>`);
    if (data.tutorial_available) badges.push('<span class="hc-badge">tutorial</span>');
    badgesEl.innerHTML = badges.join('');

    bodyEl.innerHTML = _helpBuildLayerHtml(data, _hcCurrentLayer);

    const layer2Btn = document.getElementById('hc-layer-btn-2');
    const layer3Btn = document.getElementById('hc-layer-btn-3');
    [1, 2, 3].forEach(layer => {
        const btn = document.getElementById(`hc-layer-btn-${layer}`);
        if (!btn) return;
        btn.classList.toggle('active', layer === _hcCurrentLayer);
    });
    if (layer2Btn) layer2Btn.style.display = data.layer2 ? '' : 'none';
    if (layer3Btn) layer3Btn.style.display = data.layer3 ? '' : 'none';
    tutorialBtn.style.display = data.tutorial_available ? '' : 'none';
    _hcUpdateChatFocus();
}

async function hcSelect(helpId) {
    _hcSelectedId = helpId;
    _hcCurrentLayer = 1;
    hcRenderCatalog((_hcCatalog || []).filter(item => {
        const category = document.getElementById('hc-category')?.value || '';
        const query = (_hcFilterText || '').trim().toLowerCase();
        const inCategory = !category || item.category === category;
        if (!inCategory) return false;
        if (!query) return true;
        const hay = [item.help_id, item.label, item.category, item.snippet, item.difficulty].join(' ').toLowerCase();
        return hay.includes(query);
    }));

    if (_helpContent[helpId]) {
        hcRenderDetail(_helpContent[helpId]);
        return;
    }

    try {
        const resp = await fetch(bridgeApi('/api/help/content/' + encodeURIComponent(helpId)));
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        const data = await resp.json();
        if (data.found) {
            _helpContent[helpId] = data;
            hcRenderDetail(data);
        } else {
            hcRenderDetail(null);
        }
    } catch (err) {
        const bodyEl = document.getElementById('hc-detail-body');
        if (bodyEl) {
            bodyEl.innerHTML = '<div class="hc-empty" style="color: var(--danger);">Failed to load help: ' + _helpEsc(err.message) + '</div>';
        }
    }
}

function hcShowLayer(layer) {
    if (!_hcSelectedId || !_helpContent[_hcSelectedId]) return;
    _hcCurrentLayer = layer;
    hcRenderDetail(_helpContent[_hcSelectedId]);
}

function hcStartTutorial() {
    const entry = _hcSelectedId ? _helpContent[_hcSelectedId] : null;
    const packId = entry?.tutorial_available;
    if (!packId) return;
    switchPanel('chat-packs');
    window.setTimeout(() => window.cpStartPack?.(packId), 50);
}

async function hcInit() {
    try {
        const [statusRes, idsRes] = await Promise.all([
            fetch(bridgeApi('/api/help/status'), { credentials: 'include' }),
            fetch(bridgeApi('/api/help/ids'), { credentials: 'include' }),
        ]);
        _hcStatus = await statusRes.json();
        const idsData = await idsRes.json();
        _hcCatalog = idsData.ids || [];

        const catEl = document.getElementById('hc-category');
        if (catEl) {
            const current = catEl.value || '';
            const categories = [...new Set(_hcCatalog.map(item => item.category).filter(Boolean))].sort();
            catEl.innerHTML = '<option value="">All categories</option>' + categories.map(cat =>
                `<option value="${_helpEsc(cat)}"${cat === current ? ' selected' : ''}>${_helpEsc(cat)}</option>`
            ).join('');
        }

        hcRenderStats();
        hcApplyFilters();
        if (!_hcSelectedId && _hcCatalog.length) {
            hcSelect(_hcCatalog[0].help_id);
        } else if (_hcSelectedId && _helpContent[_hcSelectedId]) {
            hcRenderDetail(_helpContent[_hcSelectedId]);
        }
    } catch (err) {
        const resultsEl = document.getElementById('hc-results');
        if (resultsEl) {
            resultsEl.innerHTML = '<div class="hc-empty" style="color: var(--danger);">Failed to load help catalog: ' + _helpEsc(err.message) + '</div>';
        }
    }
    _hcInitChat();
}


// ── Help Tutorial Mode (mini-chat inside help panel, powered by Chat Packs) ──
let _htSessionId = null;
let _htPackId = null;
let _htSession = null;   // { phase, section_index, total_sections, ... }
let _htSending = false;

function _htSideChatId() {
    // Keep tutorial tutoring traffic off the main daily chat branch.
    if (!_htSessionId) return 'help_tutor';
    return 'help_tutor:' + _htSessionId;
}

async function htStart(packId) {
    _htPackId = packId;
    const container = document.getElementById('ht-container');
    const content = document.getElementById('help-panel-content');
    const nav = document.getElementById('help-panel-nav');
    const search = document.querySelector('.help-panel-search');
    const searchResults = document.getElementById('help-search-results');
    const title = document.getElementById('help-panel-title');
    if (!container) return;

    // Show loading state
    if (content) content.style.display = 'none';
    if (nav) nav.style.display = 'none';
    if (search) search.style.display = 'none';
    if (searchResults) searchResults.style.display = 'none';
    if (title) title.textContent = 'Tutorial';
    container.style.display = 'flex';

    // Clear chat
    const chatEl = document.getElementById('ht-chat');
    if (chatEl) chatEl.innerHTML = '';
    htAddMessage('system', 'Starting tutorial...');

    try {
        // Start a new chat pack session
        const res = await fetch(bridgeApi('/api/chat-packs/session/start/' + encodeURIComponent(packId)), {
            method: 'POST', credentials: 'include',
        });
        const data = await res.json();
        if (data.error) {
            htAddMessage('system', 'Failed to start: ' + (data.error.message || JSON.stringify(data.error)));
            return;
        }
        _htSessionId = data.session.session_id;
        _htSession = data.session;

        // Fetch the lesson view
        await htRefreshView();

        // Send an initial "introduce this section" message
        htAddMessage('system', 'Session started. The instructor will introduce the section.');
        await htSendAuto('Please introduce this section to me.');
    } catch (e) {
        htAddMessage('system', 'Error: ' + e.message);
    }
}

async function htRefreshView() {
    if (!_htSessionId) return;
    try {
        const res = await fetch(bridgeApi('/api/chat-packs/session/' + _htSessionId + '/view'), {
            credentials: 'include',
        });
        const data = await res.json();
        if (data.error) return;

        _htSession = data.session || _htSession;
        htRenderView(data);
    } catch (e) { /* silent */ }
}

function htRenderView(data) {
    const sess = data.session || _htSession || {};
    const totalSections = sess.total_sections || 1;
    const currentIndex = sess.section_index || 0;
    const phase = sess.phase || 'lesson';

    // Progress
    const label = document.getElementById('ht-progress-label');
    const fill = document.getElementById('ht-progress-fill');
    if (phase === 'questions') {
        const qi = (sess.question_index || 0) + 1;
        const qt = sess.total_questions || 0;
        if (label) label.textContent = 'Question ' + qi + ' of ' + qt;
        if (fill) fill.style.width = '100%';
    } else if (phase === 'complete') {
        if (label) label.textContent = 'Complete';
        if (fill) fill.style.width = '100%';
    } else {
        const sectionNum = currentIndex + 1;
        if (label) label.textContent = 'Section ' + sectionNum + ' of ' + totalSections;
        if (fill) fill.style.width = Math.round((sectionNum / totalSections) * 100) + '%';
    }

    // Section content
    const cc = data.current_content || {};
    const titleEl = document.getElementById('ht-section-title');
    const bodyEl = document.getElementById('ht-section-body');
    if (titleEl) titleEl.textContent = cc.title || '';
    if (bodyEl) bodyEl.textContent = cc.body || '';

    // Advance button
    const advBtn = document.getElementById('ht-advance-btn');
    if (advBtn) {
        if (phase === 'complete') {
            advBtn.textContent = 'Completed';
            advBtn.disabled = true;
        } else if (phase === 'questions') {
            advBtn.textContent = 'Next Question';
            advBtn.disabled = false;
        } else {
            advBtn.textContent = 'Next Section';
            advBtn.disabled = false;
        }
    }

    // Title
    const panelTitle = document.getElementById('help-panel-title');
    if (panelTitle) panelTitle.textContent = data.pack_title || 'Tutorial';
}

function htAddMessage(role, text) {
    const chatEl = document.getElementById('ht-chat');
    if (!chatEl) return;
    const div = document.createElement('div');
    div.className = 'ht-msg';
    if (role === 'instructor') {
        div.innerHTML = '<div class="ht-msg-instructor">' + _helpEsc(text) + '</div>';
    } else if (role === 'user') {
        div.innerHTML = '<div class="ht-msg-user">' + _helpEsc(text) + '</div>';
    } else {
        div.innerHTML = '<div class="ht-msg-system">' + _helpEsc(text) + '</div>';
    }
    chatEl.appendChild(div);
    chatEl.scrollTop = chatEl.scrollHeight;
}

async function htSend() {
    const input = document.getElementById('ht-input');
    if (!input || !input.value.trim() || !_htSessionId || _htSending) return;
    const msg = input.value.trim();
    input.value = '';
    await htSendAuto(msg, true);
}

async function htSendAuto(msg, showUser) {
    if (_htSending) return;
    _htSending = true;
    const sendBtn = document.getElementById('ht-send-btn');
    if (sendBtn) sendBtn.disabled = true;

    if (showUser) htAddMessage('user', msg);

    try {
        const payload = {
            message: msg,
            mode: 'llm',
            model: '',  // use default from bridge
            session_id: _htSessionId,
            side_chat_id: _htSideChatId(),
        };

        const res = await fetch(bridgeApi('/api/chat/send'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (data.error) {
            htAddMessage('system', data.error.message || 'Error');
        } else {
            htAddMessage('instructor', data.response || 'No response.');
            // Update session from trace
            if (data.reasoning_trace && data.reasoning_trace.pack_session) {
                _htSession = Object.assign(_htSession || {}, data.reasoning_trace.pack_session);
            }
        }
    } catch (e) {
        htAddMessage('system', 'Send failed: ' + e.message);
    } finally {
        _htSending = false;
        if (sendBtn) sendBtn.disabled = false;
        const input = document.getElementById('ht-input');
        if (input) input.focus();
    }
}

async function htAdvance() {
    if (!_htSessionId) return;
    const advBtn = document.getElementById('ht-advance-btn');
    if (advBtn) advBtn.disabled = true;
    try {
        const res = await fetch(bridgeApi('/api/chat-packs/session/advance/' + _htSessionId), {
            method: 'POST', credentials: 'include',
        });
        const data = await res.json();
        if (data.error) {
            htAddMessage('system', 'Advance failed: ' + (data.error.message || JSON.stringify(data.error)));
            if (advBtn) advBtn.disabled = false;
            return;
        }
        _htSession = data.session;

        // Refresh view
        await htRefreshView();

        // Clear chat for new section
        const chatEl = document.getElementById('ht-chat');
        if (chatEl) chatEl.innerHTML = '';

        if (data.session && data.session.phase === 'complete') {
            htAddMessage('system', 'Tutorial complete! Well done.');
            if (advBtn) { advBtn.textContent = 'Completed'; advBtn.disabled = true; }
        } else if (data.session && data.session.phase === 'questions') {
            htAddMessage('system', 'Moving to questions...');
            await htSendAuto('Ask me the next question.');
        } else {
            htAddMessage('system', 'Next section loaded.');
            await htSendAuto('Please introduce this section to me.');
        }
    } catch (e) {
        htAddMessage('system', 'Error: ' + e.message);
        if (advBtn) advBtn.disabled = false;
    }
}

function htExit() {
    _htSessionId = null;
    _htPackId = null;
    _htSession = null;

    const container = document.getElementById('ht-container');
    const content = document.getElementById('help-panel-content');
    const nav = document.getElementById('help-panel-nav');
    const search = document.querySelector('.help-panel-search');
    const title = document.getElementById('help-panel-title');

    if (container) container.style.display = 'none';
    if (content) content.style.display = '';
    if (nav) nav.style.display = _helpCurrentId ? 'flex' : 'none';
    if (search) search.style.display = '';
    if (title) title.textContent = 'Help';
}

window.ANCHORWORKS.ready.panel_help = true;
