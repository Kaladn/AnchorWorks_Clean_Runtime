// panel-inference-ctrl.js — Inference Control Surface + Model Discovery + Providers + Server Modules
// Extracted from anchorworks_production.js L4256-5105
if (!window.bridgeApi) console.warn('core.js not loaded before panel-inference-ctrl.js');

// ── Inference Control Surface ──────────────────────────────────

const PRESETS = {
    precise:    { temperature: 0.1, top_p: 0.85, repeat_penalty: 1.2,  max_tokens: 4096,  top_k: 40, frequency_penalty: 0.0, presence_penalty: 0.0, seed: -1, mirostat_mode: 0, mirostat_tau: 5.0, mirostat_eta: 0.1 },
    workhorse:  { temperature: 0.5, top_p: 0.95, repeat_penalty: 1.15, max_tokens: 6144,  top_k: 40, frequency_penalty: 0.0, presence_penalty: 0.0, seed: -1, mirostat_mode: 0, mirostat_tau: 5.0, mirostat_eta: 0.1 },
    balanced:   { temperature: 0.7, top_p: 1.0,  repeat_penalty: 1.1,  max_tokens: 4096,  top_k: 40, frequency_penalty: 0.0, presence_penalty: 0.0, seed: -1, mirostat_mode: 0, mirostat_tau: 5.0, mirostat_eta: 0.1 },
    explorer:   { temperature: 0.8, top_p: 1.0,  repeat_penalty: 1.05, max_tokens: 8192,  top_k: 60, frequency_penalty: 0.0, presence_penalty: 0.0, seed: -1, mirostat_mode: 0, mirostat_tau: 5.0, mirostat_eta: 0.1 },
    locked:     { temperature: 0.0, top_p: 1.0,  repeat_penalty: 1.1,  max_tokens: 4096,  top_k: 40, frequency_penalty: 0.0, presence_penalty: 0.0, seed: 42,  mirostat_mode: 0, mirostat_tau: 5.0, mirostat_eta: 0.1 },
};

const SLIDER_MAP = {
    'ctrl-temp':      { key: 'temperature',       div: 100, digits: 2 },
    'ctrl-topp':      { key: 'top_p',             div: 100, digits: 2 },
    'ctrl-maxtok':    { key: 'max_tokens',        div: 1,   digits: 0 },
    'ctrl-repeat':    { key: 'repeat_penalty',    div: 100, digits: 2 },
    'ctrl-topk':      { key: 'top_k',             div: 1,   digits: 0 },
    'ctrl-freqpen':   { key: 'frequency_penalty', div: 100, digits: 2 },
    'ctrl-prespen':   { key: 'presence_penalty',  div: 100, digits: 2 },
    'ctrl-miro-mode': { key: 'mirostat_mode',     div: 1,   digits: 0, suffix: ['0 (off)', '1 (v1)', '2 (v2)'] },
    'ctrl-miro-tau':  { key: 'mirostat_tau',      div: 10,  digits: 2 },
    'ctrl-miro-eta':  { key: 'mirostat_eta',      div: 100, digits: 2 },
};

class InferenceController {
    constructor() {
        this.activePreset = 'balanced';
        this._initSliders();
        this._initPresets();
        this.updateContractPreview();
        this.updateLiveConfig();
    }

    _initSliders() {
        // Debounced auto-save for per-model profiles
        let _saveTimeout = null;
        const autoSave = () => {
            clearTimeout(_saveTimeout);
            _saveTimeout = setTimeout(() => this.saveProfileForCurrentModel(), 1000);
        };

        for (const [id, meta] of Object.entries(SLIDER_MAP)) {
            const slider = document.getElementById(id);
            if (!slider) continue;
            slider.addEventListener('input', () => {
                this._markCustom();
                this._updateValLabel(id);
                this.updateLiveConfig();
                autoSave();
            });
        }
        // Seed input
        const seedInput = document.getElementById('ctrl-seed');
        if (seedInput) {
            seedInput.addEventListener('change', () => { this._markCustom(); this.updateLiveConfig(); autoSave(); });
        }
        // Contract checkboxes — persist to localStorage on change
        ['ctrl-require-end', 'ctrl-essentials', 'ctrl-bullet-mode'].forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                // Restore saved state
                const saved = localStorage.getItem('anchorworks_' + id);
                if (saved !== null) el.checked = saved === 'true';
                el.addEventListener('change', () => {
                    localStorage.setItem('anchorworks_' + id, el.checked);
                    this.updateContractPreview();
                });
            }
        });
    }

    _initPresets() {
        document.querySelectorAll('.ctrl-preset').forEach(btn => {
            btn.addEventListener('click', () => {
                const name = btn.dataset.preset;
                if (name === 'custom') {
                    this._markCustom();
                    return;
                }
                this.applyPreset(name);
            });
        });
    }

    _updateValLabel(sliderId) {
        const slider = document.getElementById(sliderId);
        const meta = SLIDER_MAP[sliderId];
        const val = document.getElementById(sliderId + '-val');
        if (!slider || !val || !meta) return;
        const raw = parseFloat(slider.value) / meta.div;
        if (meta.suffix) {
            val.textContent = meta.suffix[parseInt(slider.value)] || raw.toString();
        } else {
            val.textContent = raw.toFixed(meta.digits);
        }
    }

    _markCustom() {
        this.activePreset = 'custom';
        document.querySelectorAll('.ctrl-preset').forEach(b => b.classList.remove('active'));
        const custom = document.querySelector('.ctrl-preset[data-preset="custom"]');
        if (custom) custom.classList.add('active');
    }

    applyPreset(name) {
        const preset = PRESETS[name];
        if (!preset) return;
        this.activePreset = name;

        // Set sliders
        for (const [id, meta] of Object.entries(SLIDER_MAP)) {
            const slider = document.getElementById(id);
            if (!slider || preset[meta.key] === undefined) continue;
            slider.value = Math.round(preset[meta.key] * meta.div);
            this._updateValLabel(id);
        }
        // Set seed
        const seedInput = document.getElementById('ctrl-seed');
        if (seedInput) seedInput.value = preset.seed ?? -1;

        // Update preset buttons
        document.querySelectorAll('.ctrl-preset').forEach(b => b.classList.remove('active'));
        const btn = document.querySelector(`.ctrl-preset[data-preset="${name}"]`);
        if (btn) btn.classList.add('active');

        this.updateLiveConfig();
        this.saveProfileForCurrentModel();
    }

    getParams() {
        const params = {};
        for (const [id, meta] of Object.entries(SLIDER_MAP)) {
            const slider = document.getElementById(id);
            if (!slider) continue;
            params[meta.key] = parseFloat(slider.value) / meta.div;
        }
        const seedInput = document.getElementById('ctrl-seed');
        params.seed = seedInput ? parseInt(seedInput.value) || -1 : -1;
        return params;
    }

    getContract() {
        const requireEnd = document.getElementById('ctrl-require-end')?.checked ?? true;
        const essentials = document.getElementById('ctrl-essentials')?.checked ?? true;
        const bulletMode = document.getElementById('ctrl-bullet-mode')?.checked ?? false;
        let rules = [];
        if (bulletMode) rules.push('Answer in concise bullet points.');
        if (essentials) rules.push('After your answer, add "Essentials:" with 3-7 key items that must be present.');
        if (requireEnd) rules.push('End your response with ⟦END⟧.');

        // Add custom rules from textarea
        const customRules = document.getElementById('ctrl-custom-rules')?.value.trim();
        if (customRules) {
            rules.push(customRules);
        }

        return { requireEnd, essentials, bulletMode, text: rules.join(' ') };
    }

    updateContractPreview() {
        const contract = this.getContract();
        const el = document.getElementById('ctrl-contract-preview');
        if (!el) return;
        if (!contract.text) {
            el.textContent = '(no contract rules active)';
        } else {
            el.textContent = contract.text;
        }
    }

    updateLiveConfig() {
        const params = this.getParams();
        const el = document.getElementById('ctrl-live-config');
        if (!el) return;
        el.innerHTML = [
            `<span>temp: ${params.temperature.toFixed(2)}</span>`,
            `<span>top_p: ${params.top_p.toFixed(2)}</span>`,
            `<span>max: ${params.max_tokens}</span>`,
            `<span>repeat: ${params.repeat_penalty.toFixed(2)}</span>`,
            `<span>top_k: ${params.top_k}</span>`,
            `<span>seed: ${params.seed}</span>`,
            `<span>preset: ${this.activePreset}</span>`,
        ].join('');
    }

    async applyToServer() {
        const params = this.getParams();
        try {
            const resp = await fetch((ANCHORWORKS_CONFIG?.llm || 'http://localhost:11435') + '/api/inference/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify(params)
            });
            if (resp.ok) {
                const data = await resp.json();
                console.log('Inference config applied:', data);
                alert('Inference config applied to server.');
            } else {
                alert('Failed to apply config: ' + resp.status);
            }
        } catch (e) {
            alert('Server not reachable: ' + e.message);
        }
    }

    resetDefaults() {
        this.applyPreset('balanced');
        this.updateContractPreview();
    }

    // Called by AnchorWorksConsole before sending to build the request body
    buildRequestBody(model, prompt) {
        const params = this.getParams();
        const contract = this.getContract();

        const body = {
            model: model,
            prompt: prompt,
            stream: false,
        };

        // Only send non-default params to keep requests clean
        if (params.temperature !== 0.7)  body.temperature = params.temperature;
        if (params.max_tokens !== 4096)   body.max_tokens = params.max_tokens;
        if (params.top_p !== 1.0)         body.top_p = params.top_p;
        if (params.top_k !== 40)          body.top_k = params.top_k;
        if (params.repeat_penalty !== 1.1) body.repeat_penalty = params.repeat_penalty;
        if (params.frequency_penalty > 0) body.frequency_penalty = params.frequency_penalty;
        if (params.presence_penalty > 0)  body.presence_penalty = params.presence_penalty;
        if (params.seed >= 0)             body.seed = params.seed;
        if (params.mirostat_mode > 0) {
            body.mirostat_mode = params.mirostat_mode;
            body.mirostat_tau = params.mirostat_tau;
            body.mirostat_eta = params.mirostat_eta;
        }

        return { body, contract };
    }

    // ── Per-Model Profile Management ──────────────────────────

    async loadProfileForModel(modelName) {
        if (!modelName) return;
        try {
            const resp = await fetch(bridgeApi(`/api/inference/profiles/${encodeURIComponent(modelName)}`), {
                credentials: 'include'
            });
            if (resp.ok) {
                const data = await resp.json();
                if (data.profile) {
                    this._applyProfileToSliders(data.profile);
                    this._updateModelBadge(data.profile.preset || 'custom', false);
                    return;
                }
            }
        } catch { /* bridge down, use defaults */ }
        this.applyPreset('balanced');
        this._updateModelBadge('balanced', true);
    }

    _applyProfileToSliders(profile) {
        for (const [id, meta] of Object.entries(SLIDER_MAP)) {
            const slider = document.getElementById(id);
            if (!slider || profile[meta.key] === undefined) continue;
            slider.value = Math.round(profile[meta.key] * meta.div);
            this._updateValLabel(id);
        }
        const seedInput = document.getElementById('ctrl-seed');
        if (seedInput && profile.seed !== undefined) seedInput.value = profile.seed;
        if (profile.preset && PRESETS[profile.preset]) {
            this.activePreset = profile.preset;
            document.querySelectorAll('.ctrl-preset').forEach(b => b.classList.remove('active'));
            const btn = document.querySelector(`.ctrl-preset[data-preset="${profile.preset}"]`);
            if (btn) btn.classList.add('active');
        } else {
            this._markCustom();
        }
        this.updateLiveConfig();
    }

    _updateModelBadge(presetName, isDefault) {
        const badge = document.getElementById('ctrl-model-profile-badge');
        if (!badge) return;
        badge.textContent = isDefault ? 'defaults' : `saved: ${presetName}`;
        badge.style.color = isDefault ? 'var(--text-secondary)' : 'var(--success)';
    }

    async saveProfileForCurrentModel() {
        const select = document.getElementById('ctrl-model-select');
        if (!select || !select.value) return;
        const modelName = select.value;
        const params = this.getParams();
        params.preset = this.activePreset;
        try {
            await fetch(bridgeApi(`/api/inference/profiles/${encodeURIComponent(modelName)}`), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify(params)
            });
            this._updateModelBadge(this.activePreset, false);
        } catch { /* bridge down — params are still live in UI */ }
    }

    onModelSelectChange(modelName) {
        if (!modelName) return;
        this.loadProfileForModel(modelName);
    }
}

function toggleCtrlSection(name) {
    const body = document.getElementById('ctrl-' + name);
    if (!body) return;
    body.classList.toggle('open');
    // Toggle arrow
    const toggle = body.previousElementSibling;
    if (toggle) {
        const label = toggle.querySelector('span:first-child');
        if (label) {
            label.textContent = body.classList.contains('open')
                ? label.textContent.replace('▸', '▾')
                : label.textContent.replace('▾', '▸');
        }
    }
}

function loadCustomRules() {
    const saved = localStorage.getItem('customContractRules');
    const textarea = document.getElementById('ctrl-custom-rules');
    if (textarea && saved) {
        textarea.value = saved;
    }
}

function saveCustomRules() {
    const textarea = document.getElementById('ctrl-custom-rules');
    if (textarea) {
        localStorage.setItem('customContractRules', textarea.value);
        // Update preview if inferenceCtrl exists
        if (window.inferenceCtrl) {
            inferenceCtrl.updateContractPreview();
        }
    }
}

function resetCustomRules() {
    const textarea = document.getElementById('ctrl-custom-rules');
    if (textarea) {
        textarea.value = '';
        localStorage.removeItem('customContractRules');
        // Update preview if inferenceCtrl exists
        if (window.inferenceCtrl) {
            inferenceCtrl.updateContractPreview();
        }
    }
}

function toggleToolAccess() {
    const enabled = document.getElementById('tools-toggle').checked;
    localStorage.setItem('anchorworks_tools_enabled', enabled ? 'true' : 'false');
}

function toggleContinueContext() {
    const toggle = document.getElementById('continue-toggle');
    const area = document.getElementById('continue-context-area');
    const warning = document.getElementById('continue-loop-warning');
    if (toggle && area) {
        area.classList.toggle('open', toggle.checked);
    }
    if (warning) warning.style.display = 'none';
}

async function continueLast() {
    if (!app || !app._lastAssistantContent) return;

    // Loop breaker: if 2+ identical responses in a row, refuse
    if (app._loopCount >= 2) {
        const warning = document.getElementById('continue-loop-warning');
        if (warning) warning.style.display = 'block';
        return;
    }

    const tail = app._lastAssistantContent.slice(-800);
    const contextInput = document.getElementById('continue-context-input');
    const userContext = contextInput ? contextInput.value.trim() : '';
    const prompt = document.getElementById('gpt-prompt');

    if (userContext) {
        // Error-aware continue: carry plan context + user's error/context
        prompt.value = `I was following your instructions and hit a problem. Here is the tail of your last response for context:\n\n"${tail}"\n\nHere is the error or additional context:\n\n${userContext}\n\nFix the failing step and continue with the remaining steps. Do not repeat steps that already succeeded.`;
        // Clear context field after sending
        if (contextInput) contextInput.value = '';
    } else {
        // Blind continue: just pick up where we left off
        prompt.value = `Continue from exactly where you left off. Do not repeat previous text. Here is the tail of your last output for context:\n\n"${tail}"\n\nContinue.`;
    }

    // Continue always forks into a side chat to keep the daily main thread clean.
    try {
        const sideContent = userContext
            ? `CONTINUE WITH CONTEXT\n\nTail:\n${tail}\n\nContext:\n${userContext}`
            : `CONTINUE\n\nTail:\n${tail}`;
        await app.startSideChatFromContext({
            fromDay: new Date().toISOString().slice(0, 10),
            messageId: 0,
            content: sideContent,
            actor: 'assistant',
            description: userContext ? 'Continue flow with error context' : 'Continue flow from latest assistant output',
        });
    } catch (_) {
        // If side chat creation fails, we still allow continue to proceed.
    }

    await app.sendGptMessage();
}

let inferenceCtrl;
function syncFromSliders() { if (inferenceCtrl) inferenceCtrl.updateLiveConfig(); }

// ── LLM Model Discovery & Provider Status ────────────────────

async function refreshModelList() {
    const baseUrl = window.ANCHORWORKS_CONFIG?.llm || 'http://localhost:11435';
    try {
        const resp = await fetch(`${baseUrl}/api/tags`, { credentials: 'include', signal: AbortSignal.timeout(3000) });
        if (!resp.ok) throw new Error('unreachable');
        const data = await resp.json();
        const models = data.models || [];

        const savedModel = localStorage.getItem('gptModel');
        let activeModel = null;
        models.forEach(m => { if (m.active) activeModel = m.name; });

        // Persist best model to localStorage
        const bestModel = activeModel || savedModel || (models[0] && models[0].name) || '';
        if (bestModel) localStorage.setItem('gptModel', bestModel);

        // Update Local provider slot in Connections panel
        updateLocalProvider(models, bestModel);

        // Sync local model selectors (chat + chain hub + local slot models)
        window.chainSetLocalModels?.(models, bestModel);

        // Populate inference tuning model selector
        _populateCtrlModelSelect(models, bestModel);

        // Populate identity panel model selector
        if (typeof _populateIdentityModelSelect === 'function') {
            _populateIdentityModelSelect(models, bestModel);
        }

        return models;
    } catch {
        updateLocalProvider([], null);
        window.chainSetLocalModels?.([], null);
        _populateCtrlModelSelect([], null);
        if (typeof _populateIdentityModelSelect === 'function') {
            _populateIdentityModelSelect([], null);
        }
        return [];
    }
}

async function _populateCtrlModelSelect(localModels, activeModel) {
    const ctrlSelect = document.getElementById('ctrl-model-select');
    if (!ctrlSelect) return;

    const prevValue = ctrlSelect.value;
    ctrlSelect.innerHTML = '';

    // Add local Ollama models
    (localModels || []).forEach(m => {
        const opt = document.createElement('option');
        opt.value = m.name;
        opt.textContent = `[Local] ${m.name}`;
        ctrlSelect.appendChild(opt);
    });

    // Add cloud provider models for configured providers
    try {
        const provResp = await fetch(bridgeApi('/api/providers'), { credentials: 'include', signal: AbortSignal.timeout(2000) });
        const provData = await provResp.json();
        for (const prov of (provData.providers || [])) {
            if (!prov.configured) continue;
            const cloudModels = PROVIDER_META[prov.name]?.models ?? [];
            cloudModels.forEach(m => {
                const opt = document.createElement('option');
                opt.value = m;
                opt.textContent = `[${prov.name}] ${m}`;
                ctrlSelect.appendChild(opt);
            });
        }
    } catch { /* bridge down */ }

    // Restore selection
    if (prevValue && [...ctrlSelect.options].some(o => o.value === prevValue)) {
        ctrlSelect.value = prevValue;
    } else if (activeModel && [...ctrlSelect.options].some(o => o.value === activeModel)) {
        ctrlSelect.value = activeModel;
    }
}

function updateLocalProvider(models, activeModel) {
    const statusEl = document.querySelector('#provider-local .provider-status');
    const slotEl = document.getElementById('provider-local');
    if (!statusEl || !slotEl) return;

    if (models.length > 0) {
        const activeText = activeModel || 'idle';
        statusEl.textContent = `${models.length} model(s) — ${activeText}`;
        statusEl.style.color = 'var(--success)';
        slotEl.classList.add('connected');
    } else {
        statusEl.textContent = 'Not reachable';
        statusEl.style.color = 'var(--danger)';
        slotEl.classList.remove('connected');
    }
}

// Auto-discover models on load, then every 60s
setTimeout(refreshModelList, 2000);
setInterval(refreshModelList, 60000);


// ── Cloud Provider Configuration ──────────────────────────────

const PROVIDER_META = {
    openai: {
        name: 'OpenAI', icon: '\uD83D\uDFE2', prefix: 'sk-',
        models: ['gpt-5.4', 'gpt-5.2', 'gpt-5', 'gpt-5-mini', 'gpt-5-nano', 'o3', 'o4-mini', 'o3-mini'],
    },
    claude: {
        name: 'Claude (Anthropic)', icon: '\uD83D\uDFE0', prefix: 'sk-ant-',
        models: ['claude-opus-4-20250918', 'claude-sonnet-4-6-20250627', 'claude-haiku-4-5-20251001'],
    },
    gemini: {
        name: 'Gemini (Google)', icon: '\uD83D\uDD35', prefix: 'AIza',
        models: ['gemini-2.5-flash', 'gemini-2.5-pro', 'gemini-2.0-flash'],
    },
    grok: {
        name: 'Grok (xAI)', icon: '\u26A1', prefix: 'xai-',
        models: ['grok-3-fast', 'grok-3', 'grok-3-mini', 'grok-4-latest'],
    },
};

let _provCurrentProvider = null;

function provOpenModal(providerName) {
    const meta = PROVIDER_META[providerName];
    if (!meta) return;
    _provCurrentProvider = providerName;

    document.getElementById('prov-modal-title').textContent = `Configure ${meta.name}`;
    document.getElementById('prov-modal-icon').textContent = meta.icon;
    document.getElementById('prov-modal-name').textContent = meta.name;
    document.getElementById('prov-modal-key').value = '';
    document.getElementById('prov-modal-key').placeholder = `${meta.prefix}...`;
    document.getElementById('prov-modal-feedback').style.display = 'none';

    // Populate model selector
    const modelSelect = document.getElementById('prov-modal-model');
    modelSelect.innerHTML = '';
    (meta.models || []).forEach(m => {
        const opt = document.createElement('option');
        opt.value = m;
        opt.textContent = m;
        modelSelect.appendChild(opt);
    });
    const saved = localStorage.getItem(`anchorworks_${providerName}_model`);
    if (saved && [...modelSelect.options].some(o => o.value === saved)) {
        modelSelect.value = saved;
    }
    modelSelect.onchange = () => {
        localStorage.setItem(`anchorworks_${providerName}_model`, modelSelect.value);
    };

    provRefreshModalStatus(providerName);
    document.getElementById('provider-modal').classList.add('active');
}

function provCloseModal() {
    document.getElementById('provider-modal').classList.remove('active');
    _provCurrentProvider = null;
}

async function provRefreshModalStatus(name) {
    const statusEl = document.getElementById('prov-modal-status-text');
    const disconnBtn = document.getElementById('prov-modal-disconnect');
    try {
        const resp = await fetch(bridgeApi(`/api/providers/${name}`), { credentials: 'include' });
        const data = await resp.json();
        if (data.configured) {
            statusEl.textContent = data.test_ok ? 'Connected (tested OK)' : 'Key saved';
            statusEl.style.color = 'var(--success)';
            disconnBtn.style.display = 'inline-block';
        } else {
            statusEl.textContent = 'Not configured';
            statusEl.style.color = 'var(--text-secondary)';
            disconnBtn.style.display = 'none';
        }
    } catch {
        statusEl.textContent = 'Bridge not reachable';
        statusEl.style.color = 'var(--danger)';
        disconnBtn.style.display = 'none';
    }
}

async function provSaveKey() {
    if (!_provCurrentProvider) return;
    const key = document.getElementById('prov-modal-key').value.trim();
    if (!key) {
        provShowFeedback('Enter an API key first.', 'warning');
        return;
    }
    provShowFeedback('Saving...', 'info');
    try {
        const resp = await fetch(bridgeApi(`/api/providers/${_provCurrentProvider}/key`), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ key })
        });
        const data = await resp.json();
        if (resp.ok) {
            provShowFeedback('Key saved and encrypted with DPAPI.', 'success');
            document.getElementById('prov-modal-key').value = '';
            provRefreshModalStatus(_provCurrentProvider);
            provRefreshSlots();
        } else {
            provShowFeedback(data.detail || 'Save failed', 'error');
        }
    } catch (e) {
        provShowFeedback('Bridge not reachable: ' + e.message, 'error');
    }
}

async function provTestConnection() {
    if (!_provCurrentProvider) return;
    provShowFeedback('Testing connection...', 'info');
    try {
        const resp = await fetch(bridgeApi(`/api/providers/${_provCurrentProvider}/test`), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include'
        });
        const data = await resp.json();
        if (data.ok) {
            provShowFeedback(data.message, 'success');
        } else {
            provShowFeedback(data.message || 'Test failed', 'error');
        }
        provRefreshModalStatus(_provCurrentProvider);
        provRefreshSlots();
    } catch (e) {
        provShowFeedback('Bridge not reachable: ' + e.message, 'error');
    }
}

async function provDisconnect() {
    if (!_provCurrentProvider) return;
    if (!confirm(`Remove ${PROVIDER_META[_provCurrentProvider].name} API key? This cannot be undone.`)) return;
    try {
        const resp = await fetch(bridgeApi(`/api/providers/${_provCurrentProvider}/key`), {
            method: 'DELETE',
            credentials: 'include'
        });
        if (resp.ok) {
            provShowFeedback('Key removed.', 'success');
            provRefreshModalStatus(_provCurrentProvider);
            provRefreshSlots();
        }
    } catch (e) {
        provShowFeedback('Failed: ' + e.message, 'error');
    }
}

function provShowFeedback(msg, level) {
    const el = document.getElementById('prov-modal-feedback');
    el.textContent = msg;
    el.style.display = 'block';
    el.style.color = level === 'success' ? 'var(--success)'
                   : level === 'error'   ? 'var(--danger)'
                   : level === 'warning' ? '#e6a700'
                   : 'var(--text-secondary)';
}

async function provRefreshSlots() {
    try {
        const resp = await fetch(bridgeApi('/api/providers'), { credentials: 'include' });
        const data = await resp.json();
        for (const prov of (data.providers || [])) {
            const slotEl = document.getElementById(`provider-${prov.name}`);
            const statusEl = slotEl?.querySelector('.provider-status');
            if (!slotEl || !statusEl) continue;
            if (prov.configured) {
                statusEl.textContent = prov.test_ok ? 'Connected (tested)' : 'Key saved';
                statusEl.style.color = 'var(--success)';
                slotEl.classList.add('connected');
            } else {
                statusEl.textContent = 'Not configured';
                statusEl.style.color = 'var(--text-secondary)';
                slotEl.classList.remove('connected');
            }
        }
        // Mode dropdown removed — provider access via Chain Builder slots only.
    } catch { /* bridge not reachable */ }
}

// Mode dropdown removed — all provider access via Chain Builder slots.
// updateChatModeProviders() removed: no dropdown to update.

// Refresh provider statuses on page load
setTimeout(provRefreshSlots, 3000);


// ── Server Module Controls (Connections panel) ────────────────

let _srvCtxTarget = null;  // currently right-clicked server element

const SERVER_DEFS = {
    bridge: { name: 'Bridge Server', health: (ANCHORWORKS_CONFIG?.bridge || 'http://localhost:5050') + '/api/stats' },
    llm:    { name: 'LLM Server',    health: (ANCHORWORKS_CONFIG?.llm || 'http://localhost:11435') + '/health' },
    ui:     { name: 'UI Server',     health: ANCHORWORKS_CONFIG?.ui || 'http://localhost:8080' },
};

function showSrvMenu(event, el) {
    event.preventDefault();
    _srvCtxTarget = el;
    const menu = document.getElementById('srv-ctx-menu');
    menu.style.left = event.clientX + 'px';
    menu.style.top = event.clientY + 'px';
    menu.classList.add('visible');
}

document.addEventListener('click', () => {
    const menu = document.getElementById('srv-ctx-menu');
    if (menu) menu.classList.remove('visible');
});

async function restartModule() {
    if (!_srvCtxTarget) return;
    const srv = _srvCtxTarget.dataset.srv;
    const def = SERVER_DEFS[srv];
    if (!def) return;

    const proceed = confirm('Restart the full AnchorWorks stack now? Services on :5050, :11435, and :8080 will briefly disconnect.');
    if (!proceed) return;

    for (const key of Object.keys(SERVER_DEFS)) {
        const cardEl = document.getElementById('module-srv-' + key);
        const cardStatusEl = document.getElementById('srv-status-' + key);
        if (cardEl) cardEl.classList.remove('online', 'offline');
        if (cardStatusEl) {
            cardStatusEl.className = 'srv-status checking';
            cardStatusEl.textContent = '● restarting stack...';
        }
    }

    if (typeof app !== 'undefined' && app.addLog) {
        app.addLog(`Restarting AnchorWorks stack (requested from ${def.name})...`, 'info');
    }

    try {
        // Bridge endpoint restarts the full stack, not an individual module.
        const resp = await fetch(bridgeApi('/api/system/restart'), {
            method: 'POST',
        });
        if (resp.ok) {
            const statusEl = document.getElementById('srv-status-' + srv);
            if (statusEl) statusEl.textContent = '● restart requested';
            // Bridge exits quickly; give services time to relaunch before health probes.
            setTimeout(() => checkAllServers(), 7000);
        } else {
            const statusEl = document.getElementById('srv-status-' + srv);
            if (statusEl) {
                statusEl.className = 'srv-status offline';
                statusEl.textContent = '● restart failed';
            }
            _srvCtxTarget.classList.add('offline');
        }
    } catch (e) {
        const statusEl = document.getElementById('srv-status-' + srv);
        if (statusEl) {
            statusEl.className = 'srv-status offline';
            statusEl.textContent = '● unreachable';
        }
        _srvCtxTarget.classList.add('offline');
        if (typeof app !== 'undefined' && app.addLog) {
            app.addLog('Restart failed: ' + e.message, 'error');
        }
    }
}

async function checkModuleHealth() {
    if (!_srvCtxTarget) return;
    checkSrvHealth(_srvCtxTarget.dataset.srv);
}

async function checkSrvHealth(srvKey) {
    const def = SERVER_DEFS[srvKey];
    if (!def) return;
    const el = document.getElementById('module-srv-' + srvKey);
    const statusEl = document.getElementById('srv-status-' + srvKey);
    statusEl.className = 'srv-status checking';
    statusEl.textContent = '● checking';
    el.classList.remove('online', 'offline');

    try {
        const resp = await fetch(def.health, { signal: AbortSignal.timeout(3000) });
        if (resp.ok) {
            statusEl.className = 'srv-status online';
            statusEl.textContent = '● online';
            el.classList.add('online');
        } else {
            statusEl.className = 'srv-status offline';
            statusEl.textContent = '● error ' + resp.status;
            el.classList.add('offline');
        }
    } catch {
        statusEl.className = 'srv-status offline';
        statusEl.textContent = '● offline';
        el.classList.add('offline');
    }
}

function checkAllServers() {
    Object.keys(SERVER_DEFS).forEach(key => checkSrvHealth(key));
}

// Poll server health every 30s, initial check on load
setInterval(checkAllServers, 30000);
setTimeout(checkAllServers, 1500);

// Make constructor available to init.js (class is lexical, not on window)
window.InferenceController = InferenceController;


// ── AI Brief System ──────────────────────────────────────────

let _aiBriefCache = { global: null, model: null, provider: '' };
let _aiBriefActiveTab = 'global';

function _aiBriefDetectProvider() {
    const ctrlSelect = document.getElementById('ctrl-model-select');
    if (!ctrlSelect || !ctrlSelect.value) return 'local';
    const selected = ctrlSelect.selectedOptions[0];
    if (!selected) return 'local';
    const text = selected.textContent.toLowerCase();
    if (text.startsWith('[local]')) return 'local';
    if (text.startsWith('[openai]')) return 'openai';
    if (text.startsWith('[claude]') || text.startsWith('[anthropic]')) return 'anthropic';
    if (text.startsWith('[gemini]') || text.startsWith('[google]')) return 'gemini';
    return 'local';
}

async function aiBriefLoad() {
    const provider = _aiBriefDetectProvider();
    const tag = document.getElementById('ai-brief-provider-tag');
    const content = document.getElementById('ai-brief-content');
    if (tag) tag.textContent = provider;

    try {
        const resp = await fetch(bridgeApi(`/api/ai-briefs/for-provider/${provider}`), {
            credentials: 'include',
            signal: AbortSignal.timeout(5000),
        });
        const data = await resp.json();
        _aiBriefCache.global = data.global || '(No global brief found)';
        _aiBriefCache.model = data.model || `(No model-specific brief for provider: ${provider})`;
        _aiBriefCache.provider = provider;
        aiBriefSwitchTab(_aiBriefActiveTab);
    } catch (e) {
        if (content) content.textContent = 'Failed to load brief: ' + e.message;
    }
}

function aiBriefSwitchTab(tab) {
    _aiBriefActiveTab = tab;
    const content = document.getElementById('ai-brief-content');
    if (!content) return;

    // Update tab styles
    document.querySelectorAll('.ai-brief-tab').forEach(btn => {
        const isActive = btn.dataset.brief === tab;
        btn.style.background = isActive ? 'var(--accent-bg)' : 'transparent';
        btn.style.color = isActive ? '#00d4ff' : 'var(--text-secondary)';
        btn.style.borderBottom = isActive ? '2px solid #00d4ff' : '2px solid transparent';
    });

    if (tab === 'global' && _aiBriefCache.global) {
        content.textContent = _aiBriefCache.global;
    } else if (tab === 'model' && _aiBriefCache.model) {
        content.textContent = _aiBriefCache.model;
    }
}

// Auto-load brief when model selection changes
const _origModelChange = InferenceController.prototype.onModelSelectChange;
InferenceController.prototype.onModelSelectChange = function(modelName) {
    _origModelChange.call(this, modelName);
    // Update provider tag when model changes
    const tag = document.getElementById('ai-brief-provider-tag');
    if (tag) tag.textContent = _aiBriefDetectProvider();
    aiBriefCheckPinStatus();
};

// ── AI Brief Pin System ─────────────────────────────────────

async function aiBriefCheckPinStatus() {
    const badge = document.getElementById('ai-brief-pin-badge');
    const btn = document.getElementById('ai-brief-pin-btn');
    if (!badge) return;
    try {
        const resp = await fetch(bridgeApi('/api/ai-briefs/pin-status'), {
            credentials: 'include',
            signal: AbortSignal.timeout(3000),
        });
        const data = await resp.json();
        badge.style.display = 'inline-block';
        if (data.pinned) {
            badge.textContent = `Pinned [${(data.sha256 || '').slice(0, 8)}]`;
            badge.style.background = 'rgba(0,230,118,0.15)';
            badge.style.color = '#00e676';
            if (btn) { btn.disabled = true; btn.textContent = 'Pinned'; btn.style.opacity = '0.5'; }
        } else {
            badge.textContent = 'Not pinned today';
            badge.style.background = 'rgba(255,180,0,0.15)';
            badge.style.color = '#ffb400';
            if (btn) { btn.disabled = false; btn.textContent = 'Pin to Session'; btn.style.opacity = '1'; }
        }
    } catch (e) {
        badge.style.display = 'none';
    }
}

async function aiBriefPin() {
    const provider = _aiBriefDetectProvider();
    const btn = document.getElementById('ai-brief-pin-btn');
    if (btn) { btn.disabled = true; btn.textContent = 'Pinning...'; }
    try {
        const resp = await fetch(bridgeApi('/api/ai-briefs/pin'), {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ provider }),
            signal: AbortSignal.timeout(5000),
        });
        const data = await resp.json();
        if (data.pinned) {
            aiBriefCheckPinStatus();
        } else {
            const reason = data.reason || 'unknown';
            alert(`Pin failed: ${reason}` + (data.chars ? ` (${data.chars} chars, limit ${data.limit})` : ''));
            if (btn) { btn.disabled = false; btn.textContent = 'Pin to Session'; }
        }
    } catch (e) {
        alert('Pin failed: ' + e.message);
        if (btn) { btn.disabled = false; btn.textContent = 'Pin to Session'; }
    }
}

// Check pin status on panel load
setTimeout(aiBriefCheckPinStatus, 500);


window.ANCHORWORKS.ready.panel_inference_ctrl = true;
