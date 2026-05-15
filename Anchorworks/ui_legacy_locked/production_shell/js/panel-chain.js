/* panel-chain.js - Chain Builder modal logic + state management
   Manages the multi-model chain: Local Hub -> Slot 1-10 -> OUT.
   Config persisted to localStorage as anchorworks_chain_config.
*/

const CHAIN_SLOT_MIN = 1;
const CHAIN_SLOT_MAX = 10;

// Provider model lists (mirrors PROVIDER_META in panel-inference-ctrl.js)
const CHAIN_PROVIDER_MODELS = {
    ollama:   [],
    grounded: ['(uses hub model)'],
    reasoning:['616'],
    openai:   ['gpt-5.4', 'gpt-5.2', 'gpt-5', 'gpt-5-mini', 'gpt-5-nano', 'o3', 'o4-mini', 'o3-mini'],
    claude:   ['claude-opus-4-20250918', 'claude-sonnet-4-6-20250627', 'claude-haiku-4-5-20251001'],
    gemini:   ['gemini-2.5-flash', 'gemini-2.5-pro', 'gemini-2.0-flash'],
    grok:     ['grok-3-fast', 'grok-3', 'grok-3-mini', 'grok-4-latest'],
};

let _chainLocalModels = [];

function _slotRange() {
    return Array.from(
        { length: CHAIN_SLOT_MAX - CHAIN_SLOT_MIN + 1 },
        (_, idx) => CHAIN_SLOT_MIN + idx
    );
}

function _chainProviderOptionsHtml() {
    return `
        <option value="">-- Provider --</option>
        <option value="ollama">Local (Hub Models)</option>
        <option value="grounded">Grounded (LakeSpeak)</option>
        <option value="reasoning">Reasoning (6-1-6)</option>
        <option value="openai">OpenAI</option>
        <option value="claude">Anthropic (Claude)</option>
        <option value="gemini">Google (Gemini)</option>
        <option value="grok">xAI (Grok)</option>
    `;
}

function _ensureChainUIScaffold() {
    const flow = document.getElementById('chain-flow-diagram');
    if (flow) {
        let html = '';
        html += '<span class="chain-node chain-node-fixed">YOU</span>';
        html += '<span class="chain-arrow"></span>';
        html += '<span class="chain-node chain-node-hub">Hub (Local)</span>';
        for (const i of _slotRange()) {
            html += `<span class="chain-arrow" id="chain-arrow-${i}" style="display:none;"></span>`;
            html += `<span class="chain-node chain-node-slot" id="chain-flow-${i}" style="display:none;">Slot ${i}</span>`;
        }
        html += '<span class="chain-arrow" id="chain-arrow-resolver" style="display:none;"></span>';
        html += '<span class="chain-node chain-node-slot" id="chain-flow-resolver" style="display:none;">Resolver</span>';
        html += '<span class="chain-arrow"></span>';
        html += '<span class="chain-node chain-node-fixed">OUT</span>';
        flow.innerHTML = html;
    }

    const slotsContainer = document.getElementById('chain-slots-container');
    if (slotsContainer) {
        const providerOptions = _chainProviderOptionsHtml();
        let html = '';
        for (const i of _slotRange()) {
            html += `
                <div class="chain-card chain-card-slot" data-slot="${i}">
                    <div class="chain-card-header">
                        <label class="chain-slot-enable">
                            <input type="checkbox" class="chain-slot-checkbox" data-slot="${i}" onchange="chainSlotToggled(${i})">
                            <strong>Slot ${i}</strong>
                        </label>
                        <select class="chain-select chain-provider-select" data-slot="${i}" onchange="chainProviderChanged(${i})">
                            ${providerOptions}
                        </select>
                    </div>
                    <div class="chain-card-body">
                        <label style="font-size:11px; color:var(--text-secondary);">Model:</label>
                        <select class="chain-select chain-model-select" data-slot="${i}">
                            <option value="">-- select provider first --</option>
                        </select>
                        <label class="chain-interrupt-label" style="font-size:11px; color:var(--text-secondary); margin-top:4px; display:flex; align-items:center; gap:4px;">
                            <input type="checkbox" class="chain-interrupt-checkbox" data-slot="${i}">
                            <span>Interrupt after (pause for user input)</span>
                        </label>
                    </div>
                </div>
            `;
        }
        slotsContainer.innerHTML = html;
    }
}

function getChainConfig() {
    try {
        const raw = localStorage.getItem('anchorworks_chain_config');
        if (!raw) return null;
        return JSON.parse(raw);
    } catch {
        return null;
    }
}

function setChainConfig(config) {
    localStorage.setItem('anchorworks_chain_config', JSON.stringify(config));
}

function getActiveSlotCount() {
    const cfg = getChainConfig();
    if (!cfg || !cfg.slots) return 0;
    return cfg.slots.filter(s => s.enabled).length;
}

function _normalizeLocalModels(models) {
    return (models || [])
        .map(m => (typeof m === 'string' ? m : m?.name))
        .filter(Boolean);
}

function _setSelectValue(selectEl, value) {
    if (!selectEl || !value) return;
    const hasOption = [...selectEl.options].some(o => o.value === value);
    if (hasOption) {
        selectEl.value = value;
        return;
    }
    const opt = document.createElement('option');
    opt.value = value;
    opt.textContent = `${value} (saved)`;
    selectEl.appendChild(opt);
    selectEl.value = value;
}

function _populateSelect(selectEl, models, emptyLabel, preferredValue) {
    if (!selectEl) return;
    const prior = selectEl.value;
    selectEl.innerHTML = '';

    const normalized = (models || []).filter(Boolean);
    if (!normalized.length) {
        if (preferredValue) {
            const opt = document.createElement('option');
            opt.value = preferredValue;
            opt.textContent = `${preferredValue} (saved)`;
            selectEl.appendChild(opt);
            selectEl.value = preferredValue;
        } else {
            const opt = document.createElement('option');
            opt.value = '';
            opt.textContent = emptyLabel;
            selectEl.appendChild(opt);
        }
        return;
    }

    normalized.forEach(name => {
        const opt = document.createElement('option');
        opt.value = name;
        opt.textContent = name;
        selectEl.appendChild(opt);
    });

    const pick = preferredValue || prior || normalized[0];
    _setSelectValue(selectEl, pick);
}

function chainSetLocalModels(models, activeModel) {
    _chainLocalModels = _normalizeLocalModels(models);

    const preferred = activeModel
        || localStorage.getItem('gptModel')
        || _chainLocalModels[0]
        || '';

    CHAIN_PROVIDER_MODELS.ollama = _chainLocalModels.length
        ? [..._chainLocalModels]
        : (preferred ? [preferred] : []);

    _populateSelect(
        document.getElementById('chain-hub-model'),
        CHAIN_PROVIDER_MODELS.ollama,
        '(from Inference Control)',
        preferred
    );

    if (preferred) {
        chainHubModelChanged(preferred, { updateConfig: false });
    }

    for (const i of _slotRange()) {
        const card = document.querySelector(`.chain-card-slot[data-slot="${i}"]`);
        const provider = card?.querySelector('.chain-provider-select')?.value;
        if (provider === 'ollama') {
            chainProviderChanged(i);
        }
    }
}

function chainHubModelChanged(modelName, options = {}) {
    const selected = `${modelName || ''}`.trim();
    if (!selected) return;

    // Keep gptModel in localStorage for backward compat with other panels
    localStorage.setItem('gptModel', selected);
    if (window.app) window.app.gptModel = selected;

    _setSelectValue(document.getElementById('chain-hub-model'), selected);

    if (options.updateConfig === false) return;
    const cfg = getChainConfig();
    if (cfg) {
        cfg.local_model = selected;
        setChainConfig(cfg);
    }
}

// Legacy alias — other code may still call this
function chainChatModelChanged(modelName, options = {}) {
    chainHubModelChanged(modelName, options);
}

function openChainBuilder() {
    const modal = document.getElementById('chain-modal');
    if (!modal) return;
    _loadChainConfigToUI();
    modal.classList.add('active');
}

function closeChainBuilder() {
    const modal = document.getElementById('chain-modal');
    if (modal) modal.classList.remove('active');
}

function chainHubProviderChanged() {
    const provSelect = document.getElementById('chain-hub-provider');
    const modelSelect = document.getElementById('chain-hub-model');
    if (!provSelect || !modelSelect) return;

    const provider = provSelect.value;
    const previousModel = modelSelect.value;

    if (provider === 'ollama' || !provider) {
        // Restore local models list
        _populateSelect(modelSelect, CHAIN_PROVIDER_MODELS.ollama, '(from Inference Control)', previousModel);
        return;
    }

    const models = CHAIN_PROVIDER_MODELS[provider] || [];
    _populateSelect(modelSelect, models, '-- no models available --', previousModel);
}

function chainResolverToggled() {
    _updateFlowDiagram();
}

function chainResolverProviderChanged() {
    const provSelect = document.getElementById('chain-resolver-provider');
    const modelSelect = document.getElementById('chain-resolver-model');
    if (!provSelect || !modelSelect) return;

    const provider = provSelect.value;
    const previousModel = modelSelect.value;
    modelSelect.innerHTML = '';

    if (!provider || !Object.prototype.hasOwnProperty.call(CHAIN_PROVIDER_MODELS, provider)) {
        modelSelect.innerHTML = '<option value="">-- select provider first --</option>';
        return;
    }

    const models = CHAIN_PROVIDER_MODELS[provider] || [];
    if (!models.length) {
        const label = provider === 'ollama'
            ? '-- no local models detected --'
            : '-- no models available --';
        modelSelect.innerHTML = `<option value="">${label}</option>`;
        return;
    }

    models.forEach((name, index) => {
        const opt = document.createElement('option');
        opt.value = name;
        opt.textContent = name;
        if (index === 0) opt.selected = true;
        modelSelect.appendChild(opt);
    });

    _setSelectValue(modelSelect, previousModel);
}

function chainHubToggled() {
    _updateFlowDiagram();
}

function chainSlotToggled(slotNum) {
    _updateFlowDiagram();
}

function chainProviderChanged(slotNum) {
    const card = document.querySelector(`.chain-card-slot[data-slot="${slotNum}"]`);
    if (!card) return;
    const provSelect = card.querySelector('.chain-provider-select');
    const modelSelect = card.querySelector('.chain-model-select');
    if (!provSelect || !modelSelect) return;

    const provider = provSelect.value;
    const previousModel = modelSelect.value;
    modelSelect.innerHTML = '';

    if (!provider || !Object.prototype.hasOwnProperty.call(CHAIN_PROVIDER_MODELS, provider)) {
        modelSelect.innerHTML = '<option value="">-- select provider first --</option>';
        return;
    }

    const models = CHAIN_PROVIDER_MODELS[provider] || [];
    if (!models.length) {
        const label = provider === 'ollama'
            ? '-- no local models detected --'
            : '-- no models available --';
        modelSelect.innerHTML = `<option value="">${label}</option>`;
        return;
    }

    models.forEach((name, index) => {
        const opt = document.createElement('option');
        opt.value = name;
        opt.textContent = name;
        if (index === 0) opt.selected = true;
        modelSelect.appendChild(opt);
    });

    _setSelectValue(modelSelect, previousModel);
}

function _updateFlowDiagram() {
    // Hub node visibility
    const hubToggle = document.getElementById('chain-hub-toggle');
    const hubFlowNode = document.querySelector('.chain-node-hub');
    if (hubFlowNode && hubToggle) {
        hubFlowNode.style.opacity = hubToggle.checked ? '1' : '0.35';
    }

    for (const i of _slotRange()) {
        const cb = document.querySelector(`.chain-slot-checkbox[data-slot="${i}"]`);
        const flowNode = document.getElementById(`chain-flow-${i}`);
        const flowArrow = document.getElementById(`chain-arrow-${i}`);
        if (!cb || !flowNode || !flowArrow) continue;
        const show = cb.checked;
        flowNode.style.display = show ? '' : 'none';
        flowArrow.style.display = show ? '' : 'none';
    }

    // Resolver node visibility
    const resolverToggle = document.getElementById('chain-resolver-toggle');
    const resolverFlowNode = document.getElementById('chain-flow-resolver');
    const resolverFlowArrow = document.getElementById('chain-arrow-resolver');
    if (resolverFlowNode && resolverFlowArrow && resolverToggle) {
        const showResolver = resolverToggle.checked;
        resolverFlowNode.style.display = showResolver ? '' : 'none';
        resolverFlowArrow.style.display = showResolver ? '' : 'none';
    }
}

function saveChainConfig() {
    const hubModel = document.getElementById('chain-hub-model')?.value?.trim()
        || localStorage.getItem('gptModel')
        || '';
    const hubEnabled = document.getElementById('chain-hub-toggle')?.checked ?? true;
    const slots = [];

    for (const i of _slotRange()) {
        const card = document.querySelector(`.chain-card-slot[data-slot="${i}"]`);
        if (!card) continue;
        const enabled = card.querySelector('.chain-slot-checkbox')?.checked || false;
        const provider = card.querySelector('.chain-provider-select')?.value || '';
        const model = card.querySelector('.chain-model-select')?.value || '';
        const interrupt_after = card.querySelector('.chain-interrupt-checkbox')?.checked || false;
        slots.push({ slot_id: i, enabled, provider, model, interrupt_after });
    }

    const hubProvider = document.getElementById('chain-hub-provider')?.value || 'ollama';

    // Resolver
    const resolverEnabled = document.getElementById('chain-resolver-toggle')?.checked || false;
    const resolverProvider = document.getElementById('chain-resolver-provider')?.value || '';
    const resolverModel = document.getElementById('chain-resolver-model')?.value || '';

    const config = {
        local_model: hubModel,
        hub_provider: hubProvider,
        hub_enabled: hubEnabled,
        resolver_enabled: resolverEnabled,
        resolver_provider: resolverProvider,
        resolver_model: resolverModel,
        slots,
    };
    setChainConfig(config);
    chainChatModelChanged(hubModel, { updateConfig: false });
    _updateChainBadge();

    // Auto-switch chat mode: if any slot is active → multi_llm, otherwise → llm
    const hasActiveSlots = slots.some(s => s.enabled && s.provider && s.model);
    const modeSelect = document.getElementById('chat-mode-select');
    if (modeSelect) {
        if (hasActiveSlots) {
            modeSelect.value = 'multi_llm';
            localStorage.setItem('anchorworks_chat_mode', 'multi_llm');
        } else if (modeSelect.value === 'multi_llm') {
            // No slots → revert from multi_llm to llm
            modeSelect.value = 'llm';
            localStorage.setItem('anchorworks_chat_mode', 'llm');
        }
    }

    closeChainBuilder();
}

function clearChainConfig() {
    localStorage.removeItem('anchorworks_chain_config');
    _loadChainConfigToUI();
    _updateChainBadge();

    // Revert to llm mode when chain is cleared
    const modeSelect = document.getElementById('chat-mode-select');
    if (modeSelect && modeSelect.value === 'multi_llm') {
        modeSelect.value = 'llm';
        localStorage.setItem('anchorworks_chat_mode', 'llm');
    }
}

function _loadChainConfigToUI() {
    const cfg = getChainConfig();
    const fallbackHub = localStorage.getItem('gptModel') || _chainLocalModels[0] || '';
    const resolvedHub = cfg?.local_model || fallbackHub;

    const hubInput = document.getElementById('chain-hub-model');
    if (hubInput) _setSelectValue(hubInput, resolvedHub);

    const hubToggle = document.getElementById('chain-hub-toggle');
    if (hubToggle) hubToggle.checked = cfg?.hub_enabled !== false;

    // Restore hub provider
    const hubProvSelect = document.getElementById('chain-hub-provider');
    if (hubProvSelect) {
        hubProvSelect.value = cfg?.hub_provider || 'ollama';
        chainHubProviderChanged();
        // Re-set hub model after provider change repopulated the list
        if (hubInput && resolvedHub) _setSelectValue(hubInput, resolvedHub);
    }

    // Restore resolver
    const resolverToggle = document.getElementById('chain-resolver-toggle');
    if (resolverToggle) resolverToggle.checked = !!cfg?.resolver_enabled;

    const resolverProvSelect = document.getElementById('chain-resolver-provider');
    if (resolverProvSelect) {
        resolverProvSelect.value = cfg?.resolver_provider || '';
        chainResolverProviderChanged();
    }
    const resolverModelSelect = document.getElementById('chain-resolver-model');
    if (resolverModelSelect && cfg?.resolver_model) {
        _setSelectValue(resolverModelSelect, cfg.resolver_model);
    }

    for (const i of _slotRange()) {
        const card = document.querySelector(`.chain-card-slot[data-slot="${i}"]`);
        if (!card) continue;
        const slotCfg = cfg?.slots?.find(s => s.slot_id === i);

        const cb = card.querySelector('.chain-slot-checkbox');
        const provSelect = card.querySelector('.chain-provider-select');
        const modelSelect = card.querySelector('.chain-model-select');

        if (cb) cb.checked = !!slotCfg?.enabled;
        if (provSelect) {
            provSelect.value = slotCfg?.provider || '';
            chainProviderChanged(i);
        }
        if (modelSelect && slotCfg?.model) {
            _setSelectValue(modelSelect, slotCfg.model);
        }
        const intCb = card.querySelector('.chain-interrupt-checkbox');
        if (intCb) intCb.checked = !!slotCfg?.interrupt_after;
    }

    if (resolvedHub) {
        chainChatModelChanged(resolvedHub, { updateConfig: false });
    }
    _updateFlowDiagram();
}

function _updateChainBadge() {
    const badge = document.getElementById('chain-badge');
    const btn = document.getElementById('chain-btn');
    if (!badge || !btn) return;

    const count = getActiveSlotCount();
    if (count > 0) {
        badge.textContent = count;
        badge.style.display = '';
        btn.classList.add('chain-active');
    } else {
        badge.style.display = 'none';
        btn.classList.remove('chain-active');
    }
}

function togglePluginHooks() {
    const cb = document.getElementById('plugins-toggle');
    if (!cb) return;
    localStorage.setItem('anchorworks_plugins_enabled', cb.checked ? 'true' : 'false');
}

function buildChainPayload() {
    const cfg = getChainConfig();
    if (!cfg || !cfg.slots) return null;

    const activeSlots = cfg.slots.filter(s => s.enabled && s.provider && s.model);
    if (activeSlots.length === 0) return null;

    const payload = {
        local_model: cfg.local_model || localStorage.getItem('gptModel') || null,
        hub_provider: cfg.hub_provider || 'ollama',
        hub_enabled: cfg.hub_enabled !== false,
        chain_slots: activeSlots.map(s => ({
            slot_id: s.slot_id,
            enabled: true,
            provider: s.provider,
            model: s.model,
            interrupt_after: !!s.interrupt_after,
        })),
        plugins_enabled: localStorage.getItem('anchorworks_plugins_enabled') === 'true',
        enabled_plugins: [],
    };

    // Resolver
    if (cfg.resolver_enabled && cfg.resolver_provider && cfg.resolver_model) {
        payload.resolver_enabled = true;
        payload.resolver_provider = cfg.resolver_provider;
        payload.resolver_model = cfg.resolver_model;
    }

    return payload;
}

document.addEventListener('DOMContentLoaded', () => {
    _ensureChainUIScaffold();
    _updateChainBadge();

    const pluginsCb = document.getElementById('plugins-toggle');
    if (pluginsCb) {
        pluginsCb.checked = localStorage.getItem('anchorworks_plugins_enabled') === 'true';
    }

    chainSetLocalModels([], localStorage.getItem('gptModel') || '');
});

window.getChainConfig = getChainConfig;
window.setChainConfig = setChainConfig;
window.chainSetLocalModels = chainSetLocalModels;
window.chainChatModelChanged = chainChatModelChanged;
window.chainHubModelChanged = chainHubModelChanged;
window.chainHubToggled = chainHubToggled;
window.chainHubProviderChanged = chainHubProviderChanged;
window.chainResolverToggled = chainResolverToggled;
window.chainResolverProviderChanged = chainResolverProviderChanged;

window.ANCHORWORKS = window.ANCHORWORKS || {};
window.ANCHORWORKS.ready = window.ANCHORWORKS.ready || {};
window.ANCHORWORKS.ready.panel_chain = true;
