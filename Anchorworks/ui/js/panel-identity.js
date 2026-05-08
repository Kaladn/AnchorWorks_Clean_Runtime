// panel-identity.js — System Prompt (per-model) & User Profile (global)
// Extracted from anchorworks_production.js L4254-4433
if (!window.bridgeApi) console.warn('core.js not loaded before panel-identity.js');

// ── System Prompt & User Profile ───────────────────────────────

let _defaultArchiveInstruction = '';
let _identitySaveTimeout = null;

// ── Per-model identity load/save ────────────────────────────────

async function loadIdentityForModel(modelName) {
    if (!modelName) return;
    const badge = document.getElementById('sp-model-profile-badge');
    try {
        const resp = await fetch(bridgeApi(`/api/identity/profiles/${encodeURIComponent(modelName)}`), {
            credentials: 'include', signal: AbortSignal.timeout(3000),
        });
        if (resp.ok) {
            const data = await resp.json();
            if (data.profile) {
                document.getElementById('sp-identity').value = data.profile.identity_role || '';
                document.getElementById('sp-archive').value = data.profile.archive_instruction || '';
                if (badge) { badge.textContent = 'saved'; badge.style.color = 'var(--success)'; }
                buildLocalPreview();
                return;
            }
        }
    } catch { /* bridge down */ }
    // No per-model profile — load global defaults
    await loadSystemPrompt();
    if (badge) { badge.textContent = 'global defaults'; badge.style.color = 'var(--text-secondary)'; }
}

async function saveIdentityForModel() {
    const select = document.getElementById('sp-model-select');
    if (!select || !select.value) return;
    const modelName = select.value;
    const payload = {
        identity_role: document.getElementById('sp-identity').value,
        archive_instruction: document.getElementById('sp-archive').value,
    };
    const badge = document.getElementById('sp-model-profile-badge');
    try {
        const resp = await fetch(bridgeApi(`/api/identity/profiles/${encodeURIComponent(modelName)}`), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify(payload),
        });
        if (resp.ok) {
            if (badge) { badge.textContent = 'saved'; badge.style.color = 'var(--success)'; }
            _flashStatus('sp-save-status', `✅ Identity saved for ${modelName}`);
            buildLocalPreview();
        }
    } catch { /* bridge down */ }
}

function onIdentityModelChange(modelName) {
    if (!modelName) return;
    loadIdentityForModel(modelName);
}

function _identityAutoSave() {
    clearTimeout(_identitySaveTimeout);
    _identitySaveTimeout = setTimeout(() => saveIdentityForModel(), 1000);
}

// ── Model selector population (called from panel-inference-ctrl.js) ──

async function _populateIdentityModelSelect(localModels, activeModel) {
    const select = document.getElementById('sp-model-select');
    if (!select) return;
    const prevValue = select.value;
    select.innerHTML = '';

    (localModels || []).forEach(m => {
        const opt = document.createElement('option');
        opt.value = m.name;
        opt.textContent = `[Local] ${m.name}`;
        select.appendChild(opt);
    });

    try {
        const provResp = await fetch(bridgeApi('/api/providers'), { credentials: 'include', signal: AbortSignal.timeout(2000) });
        const provData = await provResp.json();
        for (const prov of (provData.providers || [])) {
            if (!prov.configured) continue;
            const cloudModels = (typeof PROVIDER_META !== 'undefined' ? PROVIDER_META[prov.name]?.models : null) ?? [];
            cloudModels.forEach(m => {
                const opt = document.createElement('option');
                opt.value = m;
                opt.textContent = `[${prov.name}] ${m}`;
                select.appendChild(opt);
            });
        }
    } catch { /* bridge down */ }

    if (prevValue && [...select.options].some(o => o.value === prevValue)) {
        select.value = prevValue;
    } else if (activeModel && [...select.options].some(o => o.value === activeModel)) {
        select.value = activeModel;
    }

    // Load identity for whichever model ended up selected
    if (select.value) loadIdentityForModel(select.value);
}

// ── Global system prompt load (fallback when no per-model profile) ──

async function loadSystemPrompt() {
    const endpoint = (localStorage.getItem('gptEndpoint') || 'https://127.0.0.1:5050/api/generate').replace('/api/generate', '');
    try {
        const res = await fetch(endpoint + '/api/system-prompt', { credentials: 'include' });
        if (!res.ok) return;
        const data = await res.json();

        document.getElementById('sp-identity').value = data.identity_role || '';
        document.getElementById('sp-archive').value = data.archive_instruction || '';
        _defaultArchiveInstruction = data.default_archive_instruction || '';

        // Auto sections
        if (data.auto.yesterday_context) {
            const el = document.getElementById('sp-auto-yesterday');
            el.style.display = 'block';
            document.getElementById('sp-auto-yesterday-text').textContent =
                data.auto.yesterday_context.substring(0, 200) + (data.auto.yesterday_context.length > 200 ? '...' : '');
        }
        document.getElementById('sp-auto-clock').textContent = data.auto.clock;

        // Preview
        document.getElementById('sp-preview').textContent = data.assembled_preview;
        document.getElementById('sp-char-count').textContent = `${data.char_count} chars`;
        if (data.char_count > 1500) {
            document.getElementById('sp-char-count').style.color = 'var(--danger)';
        } else {
            document.getElementById('sp-char-count').style.color = 'var(--text-secondary)';
        }

        // Load user profile (global — not per-model)
        const p = data.user_profile || {};
        document.getElementById('up-display-name').value = p.display_name || '';
        document.getElementById('up-role').value = p.role || '';
        document.getElementById('up-context').value = p.context || '';
        document.getElementById('up-style').value = p.style || '';
        document.getElementById('up-level').value = p.level || '';
        document.getElementById('up-notes').value = p.notes || '';
    } catch (e) {
        console.warn('Failed to load system prompt:', e);
    }
}

function buildLocalPreview() {
    const identity = document.getElementById('sp-identity').value || 'You are a helpful assistant.';
    const archive = document.getElementById('sp-archive').value || _defaultArchiveInstruction;
    const parts = [identity];

    // Profile
    const profileFields = [
        ['Display Name', document.getElementById('up-display-name').value],
        ['Role', document.getElementById('up-role').value],
        ['Context', document.getElementById('up-context').value],
        ['Style', document.getElementById('up-style').value],
        ['Level', document.getElementById('up-level').value],
        ['Notes', document.getElementById('up-notes').value],
    ];
    const profileLines = profileFields.filter(([, v]) => v.trim()).map(([k, v]) => `${k}: ${v}`);
    if (profileLines.length > 0) {
        parts.push('USER PROFILE:\n' + profileLines.join('\n'));
    }

    parts.push(archive);

    // Auto sections (read from current display)
    const yesterdayEl = document.getElementById('sp-auto-yesterday-text');
    if (yesterdayEl && yesterdayEl.textContent) {
        parts.push('PREVIOUS SESSION: ' + yesterdayEl.textContent);
    }
    const clockEl = document.getElementById('sp-auto-clock');
    if (clockEl && clockEl.textContent) {
        parts.push(clockEl.textContent);
    }

    const assembled = parts.join('\n\n');
    document.getElementById('sp-preview').textContent = assembled;
    document.getElementById('sp-char-count').textContent = `${assembled.length} chars`;
    document.getElementById('sp-char-count').style.color =
        assembled.length > 1500 ? 'var(--danger)' : 'var(--text-secondary)';
}

async function saveSystemPrompt() {
    // If a model is selected, save per-model
    const select = document.getElementById('sp-model-select');
    if (select && select.value) {
        await saveIdentityForModel();
        return;
    }
    // Fallback: save to global config (no model selected)
    const endpoint = (localStorage.getItem('gptEndpoint') || 'https://127.0.0.1:5050/api/generate').replace('/api/generate', '');
    const payload = {
        identity_role: document.getElementById('sp-identity').value,
        archive_instruction: document.getElementById('sp-archive').value,
    };
    try {
        const res = await fetch(endpoint + '/api/system-prompt', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify(payload),
        });
        if (res.ok) {
            _flashStatus('sp-save-status', '✅ Identity & archive saved. Hot-reloaded.');
            buildLocalPreview();
        } else {
            _flashStatus('sp-save-status', '❌ Save failed: ' + res.statusText);
        }
    } catch (e) {
        _flashStatus('sp-save-status', '❌ ' + e.message);
    }
}

async function saveUserProfile() {
    const endpoint = (localStorage.getItem('gptEndpoint') || 'https://127.0.0.1:5050/api/generate').replace('/api/generate', '');
    const profile = {
        display_name: document.getElementById('up-display-name').value.trim(),
        role: document.getElementById('up-role').value.trim(),
        context: document.getElementById('up-context').value.trim(),
        style: document.getElementById('up-style').value,
        level: document.getElementById('up-level').value,
        notes: document.getElementById('up-notes').value.trim(),
    };
    // Strip empty fields
    const clean = {};
    for (const [k, v] of Object.entries(profile)) {
        if (v) clean[k] = v;
    }
    try {
        const res = await fetch(endpoint + '/api/user-profile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ user_profile: clean }),
        });
        if (res.ok) {
            _flashStatus('up-save-status', '✅ Profile saved. Hot-reloaded.');
            buildLocalPreview();
        } else {
            _flashStatus('up-save-status', '❌ Save failed: ' + res.statusText);
        }
    } catch (e) {
        _flashStatus('up-save-status', '❌ ' + e.message);
    }
}

function clearUserProfile() {
    document.getElementById('up-display-name').value = '';
    document.getElementById('up-role').value = '';
    document.getElementById('up-context').value = '';
    document.getElementById('up-style').value = '';
    document.getElementById('up-level').value = '';
    document.getElementById('up-notes').value = '';
    buildLocalPreview();
}

function resetArchiveInstruction() {
    document.getElementById('sp-archive').value = _defaultArchiveInstruction;
    buildLocalPreview();
    _identityAutoSave();
}

function copyAssembledPrompt() {
    const text = document.getElementById('sp-preview').textContent;
    navigator.clipboard.writeText(text).then(() => {
        _flashStatus('sp-save-status', '📋 Copied to clipboard.');
    });
}

function _flashStatus(elementId, message) {
    const el = document.getElementById(elementId);
    if (!el) return;
    el.textContent = message;
    el.style.display = 'block';
    setTimeout(() => { el.style.display = 'none'; }, 3000);
}

// Wire live preview updates on input + auto-save for identity fields
document.addEventListener('DOMContentLoaded', () => {
    const previewInputs = ['sp-identity', 'sp-archive', 'up-display-name', 'up-role', 'up-context', 'up-style', 'up-level', 'up-notes'];
    previewInputs.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('input', buildLocalPreview);
            // Auto-save identity fields per-model (not user profile fields)
            if (id === 'sp-identity' || id === 'sp-archive') {
                el.addEventListener('input', _identityAutoSave);
            }
        }
    });
});


window.ANCHORWORKS.ready.panel_identity = true;
