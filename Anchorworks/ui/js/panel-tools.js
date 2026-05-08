// panel-tools.js — Tool Workshop (tw* namespace)
// Extracted from anchorworks_production.js L10155-10553
if (!window.bridgeApi) console.warn('core.js not loaded before panel-tools.js');

// ── DEBUGWIRE Toggle (dw* namespace) ────────────────────────────

let _dwState = { enabled: false, mode: 'off', components: [] };
const _DW_KNOWN = ['auth', 'toolcall', 'http', 'documap'];

async function dwInit() {
    const container = document.getElementById('dw-toggle-section');
    if (!container) return;
    try {
        const resp = await fetch(bridgeApi('/api/debugwire/status'));
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        _dwState = await resp.json();
    } catch (e) {
        _dwState = { enabled: false, mode: 'off', components: [] };
    }
    dwRender();
}

function dwRender() {
    const container = document.getElementById('dw-toggle-section');
    if (!container) return;

    const dotColor = _dwState.enabled ? 'var(--success, #00e676)' : 'var(--text-secondary)';
    const dotShadow = _dwState.enabled ? '0 0 8px rgba(0,230,118,0.5)' : 'none';
    const modeLabel = _dwState.mode === 'all' ? 'ALL' : (_dwState.mode === 'selective' ? _dwState.components.join(', ') : 'OFF');

    const chipHtml = _DW_KNOWN.map(c => {
        const active = _dwState.mode === 'all' || _dwState.components.includes(c);
        const bg = active ? 'rgba(0,212,255,0.2)' : 'rgba(255,255,255,0.04)';
        const color = active ? 'var(--highlight)' : 'var(--text-secondary)';
        const border = active ? '1px solid rgba(0,212,255,0.3)' : '1px solid transparent';
        return `<button class="btn btn-sm dw-chip" data-comp="${c}" onclick="dwToggleComponent('${c}')"
            style="font-size:10px;padding:2px 8px;background:${bg};color:${color};border:${border};border-radius:10px;cursor:pointer;text-transform:uppercase;letter-spacing:0.5px;">${c}</button>`;
    }).join('');

    container.innerHTML = `
        <div style="display:flex;align-items:center;justify-content:space-between;">
            <div style="display:flex;align-items:center;gap:8px;">
                <div style="width:8px;height:8px;border-radius:50%;background:${dotColor};box-shadow:${dotShadow};"></div>
                <span style="font-size:12px;font-weight:600;color:var(--text-primary);">DEBUGWIRE</span>
                <span style="font-size:10px;color:var(--text-secondary);">${modeLabel}</span>
            </div>
            <label style="position:relative;display:inline-block;width:36px;height:20px;cursor:pointer;">
                <input type="checkbox" id="dw-master-toggle" onchange="dwMasterToggle(this.checked)"
                    ${_dwState.enabled ? 'checked' : ''}
                    style="opacity:0;width:0;height:0;">
                <span style="position:absolute;top:0;left:0;right:0;bottom:0;background:${_dwState.enabled ? 'var(--highlight)' : 'rgba(255,255,255,0.1)'};border-radius:10px;transition:background 0.2s;"></span>
                <span style="position:absolute;top:2px;left:${_dwState.enabled ? '18px' : '2px'};width:16px;height:16px;background:white;border-radius:50%;transition:left 0.2s;box-shadow:0 1px 3px rgba(0,0,0,0.3);"></span>
            </label>
        </div>
        <div style="display:flex;gap:4px;margin-top:8px;flex-wrap:wrap;">
            ${chipHtml}
        </div>
    `;
}

async function dwMasterToggle(on) {
    try {
        const resp = await fetch(bridgeApi('/api/debugwire/toggle'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: on, components: null }),
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        _dwState = await resp.json();
    } catch (e) {
        _dwState.enabled = false;
        _dwState.mode = 'off';
    }
    dwRender();
}

async function dwToggleComponent(comp) {
    let current = new Set(_dwState.components || []);
    if (_dwState.mode === 'all') {
        // Switching from ALL to selective: remove this one component
        current = new Set(_DW_KNOWN);
        current.delete(comp);
    } else if (current.has(comp)) {
        current.delete(comp);
    } else {
        current.add(comp);
    }
    const components = [...current];
    const enabled = components.length > 0;
    try {
        const resp = await fetch(bridgeApi('/api/debugwire/toggle'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled, components: enabled ? components : null }),
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        _dwState = await resp.json();
    } catch (e) {
        _dwState.enabled = false;
        _dwState.mode = 'off';
    }
    dwRender();
}

// ── Tool Factory (tf*) ───────────────────────────────────────

const _TF_STORAGE_KEY = 'anchorworks_tool_factory_state_v1';
const _TF_WELCOME = 'Tool Factory is ready. Describe the tool you want to build, and I will help shape the contract, runner, safety, and test plan. Tool execution is disabled here by policy.';
let _tfState = null;

function _tfNowIso() {
    return new Date().toISOString();
}

function _tfNewBranchId() {
    const now = new Date();
    const pad = (n) => String(n).padStart(2, '0');
    const ymd = `${now.getUTCFullYear()}${pad(now.getUTCMonth() + 1)}${pad(now.getUTCDate())}`;
    const hms = `${pad(now.getUTCHours())}${pad(now.getUTCMinutes())}${pad(now.getUTCSeconds())}`;
    const rand = Math.random().toString(16).slice(2, 10).padEnd(8, '0');
    return `side_${ymd}_${hms}_${rand.slice(0, 8)}`;
}

function _tfDefaultState() {
    return {
        provider: 'ollama',
        model: localStorage.getItem('gptModel') || '',
        branch: _tfNewBranchId(),
        messages: [{ role: 'assistant', content: _TF_WELCOME, ts: _tfNowIso() }],
        localModels: [],
        providers: [],
        sending: false,
    };
}

function _tfLoadState() {
    try {
        const raw = localStorage.getItem(_TF_STORAGE_KEY);
        if (!raw) return _tfDefaultState();
        const parsed = JSON.parse(raw);
        return {
            ..._tfDefaultState(),
            ...parsed,
            localModels: [],
            providers: [],
            sending: false,
            messages: Array.isArray(parsed?.messages) && parsed.messages.length
                ? parsed.messages
                : [{ role: 'assistant', content: _TF_WELCOME, ts: _tfNowIso() }],
        };
    } catch {
        return _tfDefaultState();
    }
}

function _tfPersist() {
    if (!_tfState) return;
    const { provider, model, branch, messages } = _tfState;
    localStorage.setItem(_TF_STORAGE_KEY, JSON.stringify({ provider, model, branch, messages }));
}

function _tfLlmBase() {
    return String(window.ANCHORWORKS_CONFIG?.llm || 'http://127.0.0.1:11435').replace(/\/$/, '');
}

function _tfProviderLabel(name) {
    if (name === 'ollama') return 'Local (Ollama)';
    const meta = (typeof PROVIDER_META !== 'undefined' ? PROVIDER_META[name] : null);
    return meta?.name || name;
}

function _tfProviderModels(name) {
    if (name === 'ollama') return _tfState?.localModels || [];
    const meta = (typeof PROVIDER_META !== 'undefined' ? PROVIDER_META[name] : null);
    return Array.isArray(meta?.models) ? meta.models : [];
}

function _tfEnsureProviderModel() {
    if (!_tfState) return;
    const availableProviders = (_tfState.providers || []).map(p => p.name);
    if (!availableProviders.includes(_tfState.provider)) {
        _tfState.provider = availableProviders.includes('ollama') ? 'ollama' : (availableProviders[0] || 'ollama');
    }
    const models = _tfProviderModels(_tfState.provider);
    const preferredLocal = localStorage.getItem('gptModel') || '';
    if (!models.length) {
        _tfState.model = '';
        return;
    }
    if (_tfState.provider === 'ollama' && preferredLocal && models.includes(preferredLocal)) {
        _tfState.model = preferredLocal;
        return;
    }
    if (!models.includes(_tfState.model)) {
        _tfState.model = models[0];
    }
}

async function _tfLoadProviders() {
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
        // Keep local provider only when bridge config cannot answer.
    }
    return providers;
}

async function _tfLoadLocalModels() {
    try {
        const resp = await fetch(`${_tfLlmBase()}/api/tags`, {
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

function _tfMessageHtml(msg) {
    const isUser = msg.role === 'user';
    const isSystem = msg.role === 'system';
    const align = isUser ? 'flex-end' : 'flex-start';
    const bg = isUser
        ? 'rgba(0,212,255,0.14)'
        : isSystem
            ? 'rgba(233,69,96,0.12)'
            : 'rgba(255,255,255,0.04)';
    const border = isUser
        ? '1px solid rgba(0,212,255,0.28)'
        : isSystem
            ? '1px solid rgba(233,69,96,0.24)'
            : '1px solid rgba(255,255,255,0.08)';
    const label = isUser ? 'You' : isSystem ? 'System' : 'Factory';
    return `
        <div style="display:flex;justify-content:${align};">
            <div style="max-width:92%;padding:10px 12px;background:${bg};border:${border};border-radius:10px;">
                <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:6px;">
                    <span style="font-size:10px;color:var(--text-secondary);text-transform:uppercase;letter-spacing:0.5px;">${label}</span>
                    <span style="font-size:10px;color:var(--text-secondary);white-space:nowrap;">${_twEsc((msg.ts || '').replace('T', ' ').slice(0, 19))}</span>
                </div>
                <div style="font-size:13px;line-height:1.55;color:var(--text-primary);white-space:pre-wrap;word-break:break-word;">${_twEsc(msg.content || '')}</div>
            </div>
        </div>
    `;
}

function tfRender() {
    if (!_tfState) _tfState = _tfLoadState();
    const providerEl = document.getElementById('tf-provider-select');
    const modelEl = document.getElementById('tf-model-select');
    const transcript = document.getElementById('tf-transcript');
    const branchEl = document.getElementById('tf-branch-id');
    const sendBtn = document.getElementById('tf-send-btn');
    const input = document.getElementById('tf-input');
    if (!providerEl || !modelEl || !transcript || !branchEl || !sendBtn || !input) return;

    providerEl.innerHTML = (_tfState.providers || []).map((prov) => (
        `<option value="${_twEsc(prov.name)}"${prov.name === _tfState.provider ? ' selected' : ''}>${_twEsc(_tfProviderLabel(prov.name))}</option>`
    )).join('');

    const modelOptions = _tfProviderModels(_tfState.provider);
    modelEl.innerHTML = modelOptions.length
        ? modelOptions.map((name) => (
            `<option value="${_twEsc(name)}"${name === _tfState.model ? ' selected' : ''}>${_twEsc(name)}</option>`
        )).join('')
        : '<option value="">No models available</option>';
    modelEl.disabled = !modelOptions.length;

    transcript.innerHTML = (_tfState.messages || []).map(_tfMessageHtml).join('');
    transcript.scrollTop = transcript.scrollHeight;
    branchEl.textContent = _tfState.branch;
    sendBtn.disabled = _tfState.sending;
    sendBtn.textContent = _tfState.sending ? 'Sending...' : 'Send';
    input.placeholder = _tfState.sending
        ? 'Waiting for Tool Factory response...'
        : 'Describe the tool you want to build, what it should accept, and how safe it must be...';
}

async function tfInit(force = false) {
    const transcript = document.getElementById('tf-transcript');
    if (!transcript) return;
    if (!_tfState || force) _tfState = _tfLoadState();
    _tfState.providers = await _tfLoadProviders();
    _tfState.localModels = await _tfLoadLocalModels();
    _tfEnsureProviderModel();
    _tfPersist();
    tfRender();
}

async function tfProviderChanged() {
    if (!_tfState) _tfState = _tfLoadState();
    const providerEl = document.getElementById('tf-provider-select');
    _tfState.provider = providerEl?.value || 'ollama';
    _tfEnsureProviderModel();
    _tfPersist();
    tfRender();
}

function tfModelChanged() {
    if (!_tfState) _tfState = _tfLoadState();
    const modelEl = document.getElementById('tf-model-select');
    _tfState.model = modelEl?.value || '';
    _tfPersist();
}

function tfResetChat() {
    if (!_tfState) _tfState = _tfLoadState();
    const keepProvider = _tfState.provider;
    const keepModel = _tfState.model;
    _tfState = {
        ..._tfDefaultState(),
        provider: keepProvider,
        model: keepModel,
        providers: _tfState.providers || [],
        localModels: _tfState.localModels || [],
    };
    _tfEnsureProviderModel();
    _tfPersist();
    tfRender();
}

async function tfSend() {
    if (!_tfState) _tfState = _tfLoadState();
    const input = document.getElementById('tf-input');
    const text = (input?.value || '').trim();
    if (!text || _tfState.sending) return;

    _tfState.messages.push({ role: 'user', content: text, ts: _tfNowIso() });
    _tfState.sending = true;
    _tfPersist();
    if (input) input.value = '';
    tfRender();

    try {
        const resp = await fetch(bridgeApi('/api/tools/factory/chat'), {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                mode: 'llm',
                message: text,
                local_model: _tfState.model || undefined,
                hub_provider: _tfState.provider || 'ollama',
                side_chat_id: _tfState.branch,
                session_id: 'tool_factory',
                tools_enabled: false,
            }),
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || data?.error) {
            throw new Error(data?.error?.message || data?.detail || `HTTP ${resp.status}`);
        }
        _tfState.messages.push({
            role: 'assistant',
            content: (data.response || '').trim() || '(No response)',
            ts: _tfNowIso(),
        });
    } catch (e) {
        _tfState.messages.push({
            role: 'system',
            content: `Factory error: ${e.message}`,
            ts: _tfNowIso(),
        });
    } finally {
        _tfState.sending = false;
        _tfPersist();
        tfRender();
        input?.focus();
    }
}

// ── Tool Workshop (tw*) ────────────────────────────────────────

let _twTools = [];
let _twSelected = null;
let _twEditing = false;

function _twEsc(str) {
    if (!str) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

async function twInit() {
    dwInit();  // DEBUGWIRE toggle loads alongside tools
    tfInit();
    const list = document.getElementById('tw-list');
    const count = document.getElementById('tw-count');
    if (!list) return;
    list.innerHTML = '<div style="color:var(--text-secondary);padding:12px;font-size:12px;">Loading...</div>';
    try {
        const resp = await fetch(bridgeApi('/api/tools'));
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        _twTools = data.tools || [];
        twRenderList();
        if (count) {
            const custom = _twTools.filter(t => !t.is_builtin).length;
            const total = _twTools.length;
            count.textContent = `${total} tool${total !== 1 ? 's' : ''} (${custom} custom)`;
        }
    } catch (e) {
        list.innerHTML = `<div style="color:var(--danger);padding:12px;font-size:12px;">Failed to load: ${e.message}</div>`;
    }
}

function twRenderList() {
    const list = document.getElementById('tw-list');
    if (!list) return;
    if (!_twTools.length) {
        list.innerHTML = '<div style="color:var(--text-secondary);padding:20px;text-align:center;font-size:12px;">No tools registered.</div>';
        return;
    }
    list.innerHTML = '';
    // Built-in first, then custom
    const sorted = [..._twTools].sort((a, b) => {
        if (a.is_builtin !== b.is_builtin) return a.is_builtin ? 1 : -1;
        return a.name.localeCompare(b.name);
    });
    for (const tool of sorted) {
        const row = document.createElement('div');
        row.className = 'plugin-row' + (tool.name === _twSelected ? ' selected' : '');
        row.style.cursor = 'pointer';
        row.onclick = () => twSelect(tool.name);
        if (tool.is_builtin) row.style.opacity = '0.6';

        const safetyColor = tool.safety === 'write' ? 'var(--danger)' : 'var(--highlight)';
        const badge = tool.is_builtin ? 'BUILT-IN' : 'CUSTOM';
        const badgeBg = tool.is_builtin ? 'rgba(255,255,255,0.06)' : 'rgba(0,212,255,0.15)';

        row.innerHTML = `
            <div class="pr-dot" style="background:${safetyColor};box-shadow:0 0 6px ${safetyColor}33;"></div>
            <div style="flex:1;min-width:0;">
                <div style="font-size:13px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${_twEsc(tool.name)}</div>
                <div style="font-size:11px;color:var(--text-secondary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${_twEsc(tool.description)}</div>
            </div>
            <span style="font-size:9px;padding:2px 6px;border-radius:8px;background:${badgeBg};color:var(--text-secondary);text-transform:uppercase;white-space:nowrap;">${badge}</span>
        `;
        list.appendChild(row);
    }
}

async function twSelect(name) {
    _twSelected = name;
    _twEditing = false;
    twRenderList();  // re-highlight
    const detail = document.getElementById('tw-detail');
    if (!detail) return;
    detail.innerHTML = '<div style="color:var(--text-secondary);padding:20px;text-align:center;">Loading...</div>';

    try {
        const resp = await fetch(bridgeApi(`/api/tools/${encodeURIComponent(name)}`));
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const tool = await resp.json();
        twRenderDetail(tool);
    } catch (e) {
        detail.innerHTML = `<div style="color:var(--danger);padding:20px;">Failed to load: ${e.message}</div>`;
    }
}

function twRenderDetail(tool) {
    const detail = document.getElementById('tw-detail');
    if (!detail) return;
    const isBuiltin = tool.is_builtin;

    const paramsHtml = Object.keys(tool.params || {}).length
        ? Object.entries(tool.params).map(([k, v]) =>
            `<div style="padding:4px 8px;background:rgba(255,255,255,0.03);border-radius:4px;font-size:12px;">
                <span style="color:var(--highlight);font-weight:500;">${_twEsc(k)}</span>
                <span style="color:var(--text-secondary);"> : ${_twEsc(v.type || 'string')}</span>
                ${v.description ? `<span style="color:var(--text-secondary);"> — ${_twEsc(v.description)}</span>` : ''}
                ${(tool.required || []).includes(k) ? '<span style="color:var(--danger);font-size:10px;"> (required)</span>' : ''}
            </div>`
        ).join('')
        : '<div style="color:var(--text-secondary);font-size:12px;">No parameters</div>';

    const runnerHtml = tool.runner
        ? `<div style="margin-top:12px;">
            <div style="font-size:11px;color:var(--text-secondary);margin-bottom:4px;text-transform:uppercase;">Runner</div>
            <div style="padding:8px 12px;background:rgba(0,0,0,0.2);border-radius:6px;font-size:12px;">
                <div><span style="color:var(--text-secondary);">Type:</span> <span style="color:var(--highlight);">${_twEsc(tool.runner.type)}</span></div>
                <div style="margin-top:4px;"><span style="color:var(--text-secondary);">Command:</span></div>
                <pre style="margin:4px 0 0;padding:8px;background:rgba(0,0,0,0.2);border-radius:4px;font-size:11px;white-space:pre-wrap;word-break:break-word;color:var(--text-primary);font-family:'Cascadia Code','Fira Code',monospace;">${_twEsc(tool.runner.command)}</pre>
                <div style="margin-top:4px;"><span style="color:var(--text-secondary);">Timeout:</span> ${tool.runner.timeout_sec || 15}s</div>
            </div>
        </div>`
        : '';

    const actionsHtml = isBuiltin
        ? '<div style="color:var(--text-secondary);font-size:11px;margin-top:12px;">Built-in tools cannot be edited or deleted.</div>'
        : `<div style="display:flex;gap:8px;margin-top:16px;">
            <button class="btn btn-sm" onclick="twEditTool('${_twEsc(tool.name)}')" style="font-size:12px;">Edit</button>
            <button class="btn btn-sm" onclick="twTestTool('${_twEsc(tool.name)}')" style="font-size:12px;">Test</button>
            <button class="btn btn-sm" onclick="twDuplicateTool('${_twEsc(tool.name)}')" style="font-size:12px;">Duplicate</button>
            <button class="btn btn-sm" onclick="twDeleteTool('${_twEsc(tool.name)}')" style="font-size:12px;color:var(--danger);border-color:var(--danger);">Delete</button>
        </div>`;

    detail.innerHTML = `
        <div style="margin-bottom:12px;padding-bottom:12px;border-bottom:1px solid var(--border);">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <div style="font-size:16px;font-weight:600;">${_twEsc(tool.name)}</div>
                <span style="font-size:10px;padding:2px 8px;border-radius:8px;background:${tool.safety === 'write' ? 'rgba(233,69,96,0.2)' : 'rgba(0,212,255,0.15)'};color:${tool.safety === 'write' ? 'var(--danger)' : 'var(--highlight)'};text-transform:uppercase;">${_twEsc(tool.safety)}</span>
            </div>
            <div style="font-size:13px;color:var(--text-secondary);margin-top:4px;">${_twEsc(tool.description)}</div>
            ${tool.hint ? `<div style="font-size:11px;color:var(--text-secondary);margin-top:2px;font-style:italic;">Hint: ${_twEsc(tool.hint)}</div>` : ''}
        </div>
        <div>
            <div style="font-size:11px;color:var(--text-secondary);margin-bottom:4px;text-transform:uppercase;">Parameters</div>
            <div style="display:flex;flex-direction:column;gap:4px;">${paramsHtml}</div>
        </div>
        ${runnerHtml}
        ${actionsHtml}
        <div id="tw-test-output" style="display:none;margin-top:16px;"></div>
    `;
}

function twNewTool() {
    _twSelected = null;
    _twEditing = true;
    twRenderList();
    twRenderEditor({
        name: '',
        description: '',
        hint: '',
        safety: 'read',
        runner: { type: 'powershell', command: '', timeout_sec: 15 },
        params: {},
        required: [],
    });
}

async function twEditTool(name) {
    try {
        const resp = await fetch(bridgeApi(`/api/tools/${encodeURIComponent(name)}`));
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const tool = await resp.json();
        _twEditing = true;
        twRenderEditor(tool);
    } catch (e) {
        alert(`Failed to load tool: ${e.message}`);
    }
}

function twDuplicateTool(name) {
    const tool = _twTools.find(t => t.name === name);
    if (!tool) return;
    // Fetch full definition then open editor with new name
    fetch(bridgeApi(`/api/tools/${encodeURIComponent(name)}`))
        .then(r => r.json())
        .then(data => {
            data.name = data.name + '_copy';
            _twEditing = true;
            twRenderEditor(data);
        })
        .catch(e => alert(`Failed: ${e.message}`));
}

function twRenderEditor(tool) {
    const detail = document.getElementById('tw-detail');
    if (!detail) return;

    const isNew = !_twSelected || tool.name !== _twSelected;
    const runner = tool.runner || { type: 'powershell', command: '', timeout_sec: 15 };
    const params = tool.params || {};
    const required = tool.required || [];

    // Build parameter rows
    let paramRows = '';
    for (const [pname, pdef] of Object.entries(params)) {
        paramRows += _twParamRow(pname, pdef.type || 'string', pdef.description || '', required.includes(pname));
    }

    detail.innerHTML = `
        <div style="font-size:16px;font-weight:600;margin-bottom:16px;">${isNew ? 'Create New Tool' : `Edit: ${_twEsc(tool.name)}`}</div>
        <div style="display:flex;flex-direction:column;gap:12px;overflow:auto;">
            <div>
                <label style="font-size:11px;color:var(--text-secondary);text-transform:uppercase;">Name</label>
                <input id="tw-ed-name" type="text" value="${_twEsc(tool.name)}" placeholder="my_tool_name"
                    ${!isNew ? 'readonly style="opacity:0.6;background:var(--bg-primary);border:1px solid var(--border);border-radius:4px;padding:6px 10px;font-size:13px;color:var(--text-primary);width:100%;box-sizing:border-box;"'
                    : 'style="background:var(--bg-primary);border:1px solid var(--border);border-radius:4px;padding:6px 10px;font-size:13px;color:var(--text-primary);width:100%;box-sizing:border-box;"'}
                    pattern="[a-zA-Z][a-zA-Z0-9_]*" title="Alphanumeric + underscore, starts with letter">
            </div>
            <div>
                <label style="font-size:11px;color:var(--text-secondary);text-transform:uppercase;">Description</label>
                <input id="tw-ed-desc" type="text" value="${_twEsc(tool.description)}" placeholder="What this tool does"
                    style="background:var(--bg-primary);border:1px solid var(--border);border-radius:4px;padding:6px 10px;font-size:13px;color:var(--text-primary);width:100%;box-sizing:border-box;">
            </div>
            <div>
                <label style="font-size:11px;color:var(--text-secondary);text-transform:uppercase;">When to use (hint for LLM)</label>
                <input id="tw-ed-hint" type="text" value="${_twEsc(tool.hint)}" placeholder="When asked about..."
                    style="background:var(--bg-primary);border:1px solid var(--border);border-radius:4px;padding:6px 10px;font-size:13px;color:var(--text-primary);width:100%;box-sizing:border-box;">
            </div>
            <div style="display:flex;gap:16px;">
                <div>
                    <label style="font-size:11px;color:var(--text-secondary);text-transform:uppercase;">Safety</label>
                    <div style="display:flex;gap:12px;margin-top:4px;">
                        <label style="font-size:13px;color:var(--text-primary);cursor:pointer;">
                            <input type="radio" name="tw-safety" value="read" ${tool.safety !== 'write' ? 'checked' : ''}> Read
                        </label>
                        <label style="font-size:13px;color:var(--text-primary);cursor:pointer;">
                            <input type="radio" name="tw-safety" value="write" ${tool.safety === 'write' ? 'checked' : ''}> Write
                        </label>
                    </div>
                </div>
                <div>
                    <label style="font-size:11px;color:var(--text-secondary);text-transform:uppercase;">Runner Type</label>
                    <select id="tw-ed-runner-type" style="background:var(--bg-primary);border:1px solid var(--border);border-radius:4px;padding:6px 10px;font-size:13px;color:var(--text-primary);margin-top:4px;">
                        <option value="powershell" ${runner.type === 'powershell' ? 'selected' : ''}>PowerShell</option>
                        <option value="python" ${runner.type === 'python' ? 'selected' : ''}>Python</option>
                        <option value="executable" ${runner.type === 'executable' ? 'selected' : ''}>Executable</option>
                        <option value="http" ${runner.type === 'http' ? 'selected' : ''}>HTTP</option>
                    </select>
                </div>
                <div>
                    <label style="font-size:11px;color:var(--text-secondary);text-transform:uppercase;">Timeout (sec)</label>
                    <input id="tw-ed-timeout" type="number" min="1" max="60" value="${runner.timeout_sec || 15}"
                        style="background:var(--bg-primary);border:1px solid var(--border);border-radius:4px;padding:6px 10px;font-size:13px;color:var(--text-primary);width:70px;margin-top:4px;">
                </div>
            </div>
            <div>
                <label style="font-size:11px;color:var(--text-secondary);text-transform:uppercase;">Command</label>
                <textarea id="tw-ed-command" rows="4" placeholder="Get-Process | Select Name, CPU | ConvertTo-Json"
                    style="background:var(--bg-primary);border:1px solid var(--border);border-radius:4px;padding:8px 10px;font-size:12px;color:var(--text-primary);width:100%;box-sizing:border-box;font-family:'Cascadia Code','Fira Code',monospace;resize:vertical;">${_twEsc(runner.command)}</textarea>
            </div>
            <div>
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
                    <label style="font-size:11px;color:var(--text-secondary);text-transform:uppercase;">Parameters</label>
                    <button class="btn btn-sm" onclick="twAddParam()" style="font-size:11px;padding:2px 8px;">+ Add</button>
                </div>
                <div id="tw-ed-params" style="display:flex;flex-direction:column;gap:6px;">
                    ${paramRows}
                </div>
                <div style="font-size:10px;color:var(--text-secondary);margin-top:4px;">Use {param_name} in command to reference parameters</div>
            </div>
            <div style="display:flex;gap:8px;margin-top:8px;padding-top:12px;border-top:1px solid var(--border);">
                <button class="btn btn-sm" onclick="twSave()" style="font-size:12px;background:var(--highlight);color:var(--bg-primary);border-color:var(--highlight);font-weight:600;">Save</button>
                <button class="btn btn-sm" onclick="twSelect('${_twEsc(_twSelected || '')}')" style="font-size:12px;">Cancel</button>
            </div>
        </div>
    `;
}

function _twParamRow(name, type, desc, isRequired) {
    return `
        <div class="tw-param-row" style="display:flex;gap:6px;align-items:center;">
            <input type="text" value="${_twEsc(name)}" placeholder="name" class="tw-p-name"
                style="background:var(--bg-primary);border:1px solid var(--border);border-radius:4px;padding:4px 8px;font-size:12px;color:var(--text-primary);width:100px;">
            <select class="tw-p-type" style="background:var(--bg-primary);border:1px solid var(--border);border-radius:4px;padding:4px 8px;font-size:12px;color:var(--text-primary);">
                <option value="string" ${type === 'string' ? 'selected' : ''}>string</option>
                <option value="number" ${type === 'number' ? 'selected' : ''}>number</option>
                <option value="boolean" ${type === 'boolean' ? 'selected' : ''}>boolean</option>
            </select>
            <input type="text" value="${_twEsc(desc)}" placeholder="description" class="tw-p-desc"
                style="background:var(--bg-primary);border:1px solid var(--border);border-radius:4px;padding:4px 8px;font-size:12px;color:var(--text-primary);flex:1;">
            <label style="font-size:11px;white-space:nowrap;color:var(--text-secondary);cursor:pointer;">
                <input type="checkbox" class="tw-p-req" ${isRequired ? 'checked' : ''}> req
            </label>
            <button class="btn btn-sm" onclick="this.closest('.tw-param-row').remove()" style="font-size:11px;padding:2px 6px;color:var(--danger);">x</button>
        </div>
    `;
}

function twAddParam() {
    const container = document.getElementById('tw-ed-params');
    if (!container) return;
    container.insertAdjacentHTML('beforeend', _twParamRow('', 'string', '', false));
}

function _twCollectForm() {
    const name = (document.getElementById('tw-ed-name')?.value || '').trim();
    const description = (document.getElementById('tw-ed-desc')?.value || '').trim();
    const hint = (document.getElementById('tw-ed-hint')?.value || '').trim();
    const safety = document.querySelector('input[name="tw-safety"]:checked')?.value || 'read';
    const runnerType = document.getElementById('tw-ed-runner-type')?.value || 'powershell';
    const command = (document.getElementById('tw-ed-command')?.value || '').trim();
    const timeout = parseInt(document.getElementById('tw-ed-timeout')?.value || '15', 10);

    // Collect params
    const params = {};
    const required = [];
    document.querySelectorAll('#tw-ed-params .tw-param-row').forEach(row => {
        const pname = row.querySelector('.tw-p-name')?.value.trim();
        if (!pname) return;
        const ptype = row.querySelector('.tw-p-type')?.value || 'string';
        const pdesc = row.querySelector('.tw-p-desc')?.value.trim() || '';
        const preq = row.querySelector('.tw-p-req')?.checked || false;
        params[pname] = { type: ptype, description: pdesc };
        if (preq) required.push(pname);
    });

    return {
        name,
        description,
        hint,
        safety,
        runner: { type: runnerType, command, timeout_sec: Math.min(Math.max(timeout, 1), 60) },
        params,
        required,
    };
}

async function twSave() {
    const data = _twCollectForm();
    if (!data.name) { alert('Name is required.'); return; }
    if (!data.description) { alert('Description is required.'); return; }
    if (!data.runner.command) { alert('Command is required.'); return; }

    try {
        const resp = await fetch(bridgeApi('/api/tools'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.detail || `HTTP ${resp.status}`);
        }
        _twSelected = data.name;
        _twEditing = false;
        await twInit();
        twSelect(data.name);
    } catch (e) {
        alert(`Save failed: ${e.message}`);
    }
}

async function twDeleteTool(name) {
    if (!confirm(`Delete custom tool "${name}"?\n\nThis is permanent.`)) return;
    try {
        const resp = await fetch(bridgeApi(`/api/tools/${encodeURIComponent(name)}`), { method: 'DELETE' });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.detail || `HTTP ${resp.status}`);
        }
        _twSelected = null;
        const detail = document.getElementById('tw-detail');
        if (detail) detail.innerHTML = '<div style="color:var(--text-secondary);padding:40px;text-align:center;">Select a tool to view or click + New Tool to create one</div>';
        await twInit();
    } catch (e) {
        alert(`Delete failed: ${e.message}`);
    }
}

async function twTestTool(name) {
    const output = document.getElementById('tw-test-output');
    if (!output) return;
    output.style.display = 'block';
    output.innerHTML = '<div style="color:var(--text-secondary);font-size:12px;">Running tool...</div>';

    // For tools with params, collect from current form or use empty
    let args = {};
    if (_twEditing) {
        const form = _twCollectForm();
        // Can't get actual values for params in test mode from the editor
        // Just use empty — the user would test via the detail view Test button
    }

    try {
        const resp = await fetch(bridgeApi(`/api/tools/${encodeURIComponent(name)}/test`), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ arguments: args }),
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        output.innerHTML = `
            <div style="font-size:11px;color:var(--text-secondary);text-transform:uppercase;margin-bottom:4px;">Test Result</div>
            <pre style="margin:0;padding:12px;background:rgba(0,0,0,0.2);border-radius:6px;font-size:11px;white-space:pre-wrap;word-break:break-word;color:var(--text-primary);font-family:'Cascadia Code','Fira Code',monospace;max-height:300px;overflow:auto;">${_twEsc(data.result)}</pre>
        `;
    } catch (e) {
        output.innerHTML = `<div style="color:var(--danger);font-size:12px;">Test failed: ${_twEsc(e.message)}</div>`;
    }
}

window.ANCHORWORKS.ready.panel_tools = true;
