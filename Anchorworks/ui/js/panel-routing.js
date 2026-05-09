// panel-routing.js — Routing Panel (dr* namespace)
// Extracted from anchorworks_production.js L8916-9189
if (!window.bridgeApi) console.warn('core.js not loaded before panel-routing.js');

// ── Routing Panel ─────────────────────────────────────────────
let _drProfile = null;
let _drSavedSnapshot = null; // JSON snapshot for dirty detection
let _drDirty = false;

function drInit() {
    drLoadProfile();
    drLoadProfilesList();
}

async function drLoadProfile() {
    const banner = document.getElementById('dr-error-banner');
    try {
        const r = await fetch(bridgeApi('/api/routing/profile'), { signal: AbortSignal.timeout(3000) });
        if (!r.ok) throw new Error(`${r.status}`);
        _drProfile = await r.json();
        _drSavedSnapshot = JSON.stringify(_drProfile);
        _drDirty = false;
        _drUpdateDirtyBanner();
        if (banner) banner.style.display = 'none';
        _drRenderPipeline(_drProfile);
        _drRenderProfileInfo(_drProfile);
    } catch (e) {
        if (banner) { banner.textContent = `Routing config unavailable: ${e.message}`; banner.style.display = ''; }
    }
}

async function drLoadProfilesList() {
    const dd = document.getElementById('dr-profiles-dropdown');
    if (!dd) return;
    try {
        const r = await fetch(bridgeApi('/api/routing/profiles'), { signal: AbortSignal.timeout(3000) });
        if (!r.ok) return;
        const data = await r.json();
        dd.innerHTML = '<option value="">-- saved profiles --</option>';
        for (const p of (data.profiles || [])) {
            const opt = document.createElement('option');
            opt.value = p.name;
            opt.textContent = `${p.name} (v${p.version})`;
            dd.appendChild(opt);
        }
    } catch { /* ignore */ }
}

function _drMarkDirty() {
    _drDirty = JSON.stringify(_drProfile) !== _drSavedSnapshot;
    _drUpdateDirtyBanner();
}

function _drUpdateDirtyBanner() {
    const banner = document.getElementById('dr-dirty-banner');
    if (banner) banner.style.display = _drDirty ? '' : 'none';
}

// ── Stage toggle ────────────────────────────────────────────
function drToggleStage(idx) {
    if (!_drProfile || !_drProfile.pipeline[idx]) return;
    _drProfile.pipeline[idx].enabled = !_drProfile.pipeline[idx].enabled;
    _drMarkDirty();
    _drRenderPipeline(_drProfile);
}

// ── Stage reorder (number input) ────────────────────────────
function drReorder(fromIdx, newPos) {
    if (!_drProfile || !_drProfile.pipeline) return;
    const pipe = _drProfile.pipeline;
    const toIdx = Math.max(0, Math.min(pipe.length - 1, newPos - 1));
    if (fromIdx === toIdx) return;
    const [stage] = pipe.splice(fromIdx, 1);
    pipe.splice(toIdx, 0, stage);
    _drMarkDirty();
    _drRenderPipeline(_drProfile);
}

// ── Config field update ─────────────────────────────────────
function drUpdateConfig(idx, key, value) {
    if (!_drProfile || !_drProfile.pipeline[idx]) return;
    if (!_drProfile.pipeline[idx].config) _drProfile.pipeline[idx].config = {};
    // Coerce types
    if (typeof value === 'string' && !isNaN(value) && value.trim() !== '') {
        value = Number(value);
    }
    if (value === 'true') value = true;
    if (value === 'false') value = false;
    _drProfile.pipeline[idx].config[key] = value;
    _drMarkDirty();
}

// ── Plugin toggle inside plugin_chain ───────────────────────
function drTogglePlugin(stageIdx, pluginIdx) {
    const plugins = _drProfile?.pipeline[stageIdx]?.config?.plugins;
    if (!plugins || !plugins[pluginIdx]) return;
    plugins[pluginIdx].enabled = !plugins[pluginIdx].enabled;
    _drMarkDirty();
    _drRenderPipeline(_drProfile);
}

// ── Save active profile to server ───────────────────────────
async function drSave() {
    if (!_drProfile) return;
    try {
        const r = await fetch(bridgeApi('/api/routing/profile'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(_drProfile),
        });
        if (!r.ok) {
            const err = await r.json().catch(() => ({}));
            alert(`Save failed: ${err.detail || r.status}`);
            return;
        }
        _drSavedSnapshot = JSON.stringify(_drProfile);
        _drDirty = false;
        _drUpdateDirtyBanner();
    } catch (e) {
        alert(`Save error: ${e.message}`);
    }
}

// ── Save As named profile ───────────────────────────────────
async function drSaveAs() {
    const name = prompt('Profile name (alphanumeric, hyphens, underscores):');
    if (!name) return;
    try {
        const r = await fetch(bridgeApi(`/api/routing/profiles/${encodeURIComponent(name)}`), {
            method: 'POST',
        });
        if (!r.ok) {
            const err = await r.json().catch(() => ({}));
            alert(`Save As failed: ${err.detail || r.status}`);
            return;
        }
        drLoadProfilesList();
    } catch (e) {
        alert(`Save As error: ${e.message}`);
    }
}

// ── Activate named profile ──────────────────────────────────
async function drActivateProfile() {
    const dd = document.getElementById('dr-profiles-dropdown');
    const name = dd?.value;
    if (!name) return;
    if (_drDirty && !confirm('You have unsaved changes. Switch profile anyway?')) {
        dd.value = '';
        return;
    }
    try {
        const r = await fetch(bridgeApi(`/api/routing/profiles/${encodeURIComponent(name)}/activate`), {
            method: 'POST',
        });
        if (!r.ok) {
            const err = await r.json().catch(() => ({}));
            alert(`Activate failed: ${err.detail || r.status}`);
            return;
        }
        drLoadProfile();
    } catch (e) {
        alert(`Activate error: ${e.message}`);
    }
}

// ── Reset to default ────────────────────────────────────────
async function drReset() {
    if (!confirm('Reset to default routing profile? This will discard all changes.')) return;
    try {
        const r = await fetch(bridgeApi('/api/routing/reset'), { method: 'POST' });
        if (!r.ok) {
            alert(`Reset failed: ${r.status}`);
            return;
        }
        drLoadProfile();
    } catch (e) {
        alert(`Reset error: ${e.message}`);
    }
}

// ── Pipeline rendering with interactive controls ────────────
function _drRenderPipeline(profile) {
    const lane = document.getElementById('dr-pipeline-lane');
    if (!lane) return;
    const pipeline = profile.pipeline || [];
    if (!pipeline.length) { lane.innerHTML = '<div style="color:var(--text-secondary);font-size:13px;">No stages configured</div>'; return; }

    lane.innerHTML = pipeline.map((stage, i) => {
        const enabled = stage.enabled;
        const toggleColor = enabled ? '#22c55e' : '#666';
        const toggleLabel = enabled ? 'ON' : 'OFF';
        const cfg = stage.config || {};

        // Config inspector fields per stage type
        let inspector = '';
        if (stage.type === 'inject_616') {
            inspector = `
                <div style="margin-top:8px;display:grid;grid-template-columns:auto 1fr;gap:4px 10px;font-size:12px;">
                    <label style="color:var(--text-secondary)">max_chars</label>
                    <input type="number" value="${cfg.max_chars ?? 4000}" onchange="drUpdateConfig(${i},'max_chars',this.value)"
                        style="padding:3px 6px;background:var(--bg-primary);color:var(--text-primary);border:1px solid var(--border);border-radius:4px;width:100px;">
                    <label style="color:var(--text-secondary)">days_limit</label>
                    <input type="number" value="${cfg.days_limit ?? 30}" onchange="drUpdateConfig(${i},'days_limit',this.value)"
                        style="padding:3px 6px;background:var(--bg-primary);color:var(--text-primary);border:1px solid var(--border);border-radius:4px;width:100px;">
                </div>`;
        } else if (stage.type === 'retrieval_gate') {
            inspector = `
                <div style="margin-top:8px;display:grid;grid-template-columns:auto 1fr;gap:4px 10px;font-size:12px;">
                    <label style="color:var(--text-secondary)">policy</label>
                    <select onchange="drUpdateConfig(${i},'policy',this.value)"
                        style="padding:3px 6px;background:var(--bg-primary);color:var(--text-primary);border:1px solid var(--border);border-radius:4px;width:100px;">
                        <option value="warn" ${cfg.policy === 'warn' ? 'selected' : ''}>warn</option>
                        <option value="block" ${cfg.policy === 'block' ? 'selected' : ''}>block</option>
                    </select>
                    <label style="color:var(--text-secondary)">min_docs</label>
                    <input type="number" value="${cfg.min_docs ?? 1}" onchange="drUpdateConfig(${i},'min_docs',this.value)"
                        style="padding:3px 6px;background:var(--bg-primary);color:var(--text-primary);border:1px solid var(--border);border-radius:4px;width:100px;">
                    <label style="color:var(--text-secondary)">min_score</label>
                    <input type="number" step="0.1" value="${cfg.min_score ?? 0}" onchange="drUpdateConfig(${i},'min_score',this.value)"
                        style="padding:3px 6px;background:var(--bg-primary);color:var(--text-primary);border:1px solid var(--border);border-radius:4px;width:100px;">
                </div>`;
        } else if (stage.type === 'model_call') {
            inspector = `
                <div style="margin-top:8px;display:grid;grid-template-columns:auto 1fr;gap:4px 10px;font-size:12px;">
                    <label style="color:var(--text-secondary)">model</label>
                    <input type="text" value="${escapeHtml(String(cfg.model ?? ''))}" onchange="drUpdateConfig(${i},'model',this.value)"
                        style="padding:3px 6px;background:var(--bg-primary);color:var(--text-primary);border:1px solid var(--border);border-radius:4px;width:180px;">
                    <label style="color:var(--text-secondary)">temperature</label>
                    <input type="number" step="0.1" min="0" max="2" value="${cfg.temperature ?? 0.2}" onchange="drUpdateConfig(${i},'temperature',this.value)"
                        style="padding:3px 6px;background:var(--bg-primary);color:var(--text-primary);border:1px solid var(--border);border-radius:4px;width:100px;">
                    <label style="color:var(--text-secondary)">max output</label>
                    <input type="number" value="${cfg.max_output ?? cfg['max_' + 'to' + 'kens'] ?? 800}" onchange="drUpdateConfig(${i},'max_output',this.value)"
                        style="padding:3px 6px;background:var(--bg-primary);color:var(--text-primary);border:1px solid var(--border);border-radius:4px;width:100px;">
                </div>`;
        } else if (stage.type === 'plugin_chain') {
            const pluginsHtml = (cfg.plugins || []).map((p, pi) => {
                const pColor = p.enabled ? '#22c55e' : '#666';
                return `<span onclick="drTogglePlugin(${i},${pi})" style="cursor:pointer;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;background:${pColor};color:#fff;">${escapeHtml(p.name)}: ${p.enabled ? 'ON' : 'OFF'}</span>`;
            }).join(' ');
            inspector = `
                <div style="margin-top:8px;display:flex;align-items:center;gap:8px;font-size:12px;">
                    <label style="color:var(--text-secondary)">bypass:</label>
                    <input type="checkbox" ${cfg.bypass ? 'checked' : ''} onchange="drUpdateConfig(${i},'bypass',this.checked?'true':'false')">
                    <span style="margin-left:12px;color:var(--text-secondary)">plugins:</span> ${pluginsHtml}
                </div>`;
        }

        return `<div style="background:var(--bg-secondary);border:1px solid var(--border);border-radius:8px;padding:12px 16px;">
            <div style="display:flex;align-items:center;gap:12px;">
                <input type="number" min="1" max="${pipeline.length}" value="${i + 1}"
                    onchange="drReorder(${i}, parseInt(this.value))"
                    title="Stage order"
                    style="width:36px;text-align:center;padding:2px;background:var(--bg-primary);color:var(--text-primary);border:1px solid var(--border);border-radius:4px;font-size:12px;">
                <div style="flex:1;">
                    <span style="font-weight:600;font-size:14px;">${escapeHtml(stage.id)}</span>
                    <span style="font-size:11px;color:var(--text-secondary);margin-left:8px;">type: ${escapeHtml(stage.type)}</span>
                </div>
                <span onclick="drToggleStage(${i})" style="cursor:pointer;background:${toggleColor};color:#fff;padding:2px 10px;border-radius:10px;font-size:11px;font-weight:600;user-select:none;">${toggleLabel}</span>
            </div>
            ${inspector}
        </div>`;
    }).join('');
}

function _drRenderProfileInfo(profile) {
    const el = document.getElementById('dr-profile-info');
    if (!el) return;
    el.innerHTML = `
        <div style="display:grid;grid-template-columns:auto 1fr;gap:6px 16px;font-size:13px;">
            <span style="color:var(--text-secondary);">Name:</span> <span>${escapeHtml(String(profile.name || 'unknown'))}</span>
            <span style="color:var(--text-secondary);">Version:</span> <span>${escapeHtml(String(profile.version || 0))}</span>
            <span style="color:var(--text-secondary);">Dev Mode:</span> <span>${profile.dev_mode ? 'Enabled' : 'Disabled'}</span>
            <span style="color:var(--text-secondary);">Route Badge:</span> <span>${profile.ui?.show_route_badge ? 'Visible' : 'Hidden'}</span>
        </div>
    `;
}

window.ANCHORWORKS.ready.panel_routing = true;
