// panel-control.js — Control Panel (cp* namespace)
// Sections: Logger Streams, Model Tool Policy, Tool Telemetry
if (!window.bridgeApi) console.warn('core.js not loaded before panel-control.js');

function _cpEsc(str) {
    if (!str) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// ── Section A: Logger Streams ────────────────────────────────

async function cpLoggerInit() {
    const container = document.getElementById('cp-logger-streams');
    if (!container) return;
    try {
        const resp = await fetch(bridgeApi('/api/control/loggers'), {
            credentials: 'include',
            signal: AbortSignal.timeout(5000),
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        cpLoggerRender(data.streams || []);
    } catch (e) {
        container.innerHTML = `<div style="color:var(--danger);font-size:12px;padding:12px;">Failed to load: ${_cpEsc(e.message)}</div>`;
    }

    // Initialize DebugWire in the control panel section (shared functions from panel-tools.js)
    const dwCp = document.getElementById('dw-toggle-section-cp');
    if (dwCp && typeof dwInit === 'function') {
        // Clone the DebugWire state into the CP section
        const origSection = document.getElementById('dw-toggle-section');
        if (!origSection) {
            // panel-tools might not be visible; create a mirror target
            dwCp.id = 'dw-toggle-section';
            dwInit();
            dwCp.id = 'dw-toggle-section-cp';
        } else {
            // DebugWire already initialized — clone content
            dwCp.innerHTML = origSection.innerHTML;
        }
    }
}

function cpLoggerRender(streams) {
    const container = document.getElementById('cp-logger-streams');
    if (!container) return;
    if (!streams.length) {
        container.innerHTML = '<div style="color:var(--text-secondary);font-size:12px;padding:12px;">No logger streams found.</div>';
        return;
    }
    container.innerHTML = '';
    for (const s of streams) {
        const dot = s.active ? 'var(--success, #00e676)' : 'var(--text-secondary)';
        const dotShadow = s.active ? '0 0 6px rgba(0,230,118,0.4)' : 'none';
        const toggleHtml = s.toggleable
            ? `<label style="position:relative;display:inline-block;width:32px;height:18px;cursor:pointer;">
                <input type="checkbox" ${s.active ? 'checked' : ''} onchange="cpLoggerToggle('${_cpEsc(s.name)}', this.checked)"
                    style="opacity:0;width:0;height:0;">
                <span style="position:absolute;top:0;left:0;right:0;bottom:0;background:${s.active ? 'var(--highlight)' : 'rgba(255,255,255,0.1)'};border-radius:9px;transition:background 0.2s;"></span>
                <span style="position:absolute;top:1px;left:${s.active ? '15px' : '1px'};width:16px;height:16px;background:white;border-radius:50%;transition:left 0.2s;box-shadow:0 1px 3px rgba(0,0,0,0.3);"></span>
               </label>`
            : `<span style="font-size:10px;color:var(--text-secondary);text-transform:uppercase;">${s.active ? 'always on' : 'on demand'}</span>`;
        const row = document.createElement('div');
        row.style.cssText = 'display:flex;align-items:center;gap:10px;padding:8px 12px;background:rgba(255,255,255,0.02);border-radius:6px;';
        row.innerHTML = `
            <div style="width:8px;height:8px;border-radius:50%;background:${dot};box-shadow:${dotShadow};flex-shrink:0;"></div>
            <div style="flex:1;min-width:0;">
                <div style="font-size:13px;font-weight:500;">${_cpEsc(s.name)}</div>
                <div style="font-size:10px;color:var(--text-secondary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${_cpEsc(s.path || '')}</div>
            </div>
            <div style="font-size:10px;color:var(--text-secondary);white-space:nowrap;">${s.last_event ? _cpEsc(s.last_event.slice(11, 19)) : '--'}</div>
            ${toggleHtml}
            <button class="btn btn-sm" onclick="cpLoggerTail('${_cpEsc(s.name)}')" style="font-size:10px;padding:2px 8px;">Tail</button>
        `;
        container.appendChild(row);
    }
}

async function cpLoggerToggle(name, enabled) {
    try {
        await fetch(bridgeApi(`/api/control/loggers/${encodeURIComponent(name)}/toggle`), {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled }),
        });
    } catch (e) {
        alert('Toggle failed: ' + e.message);
    }
    cpLoggerInit();
}

async function cpLoggerTail(name) {
    const container = document.getElementById('cp-logger-streams');
    if (!container) return;
    try {
        const resp = await fetch(bridgeApi(`/api/control/loggers/${encodeURIComponent(name)}/tail?lines=200`), {
            credentials: 'include',
            signal: AbortSignal.timeout(8000),
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        const lines = (data.lines || []).map(l => typeof l === 'string' ? l : JSON.stringify(l));
        const content = lines.length ? lines.join('\n') : '(empty)';
        // Show in a modal-like overlay
        const overlay = document.createElement('div');
        overlay.style.cssText = 'position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,0.85);display:flex;align-items:center;justify-content:center;padding:40px;';
        overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };
        overlay.innerHTML = `
            <div style="max-width:900px;width:100%;max-height:80vh;background:var(--bg-primary);border:1px solid var(--border);border-radius:8px;overflow:hidden;display:flex;flex-direction:column;">
                <div style="padding:12px 16px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center;">
                    <span style="font-size:14px;font-weight:600;">Tail: ${_cpEsc(name)} (last ${data.lines?.length || 0} lines)</span>
                    <button onclick="this.closest('[style*=fixed]').remove()" style="background:none;border:none;color:var(--text-secondary);font-size:18px;cursor:pointer;">X</button>
                </div>
                <pre style="flex:1;overflow:auto;padding:12px 16px;margin:0;font-size:11px;font-family:'Cascadia Code','Fira Code',monospace;white-space:pre-wrap;word-break:break-word;color:var(--text-primary);">${_cpEsc(content)}</pre>
            </div>
        `;
        document.body.appendChild(overlay);
    } catch (e) {
        alert('Tail failed: ' + e.message);
    }
}

// ── Section B: Model Tool Policy ────────────────────────────

let _cpToolList = [];
let _cpToolPolicy = {};

async function _cpLoadToolPolicyModels() {
    const modelNames = new Set();

    // Keep current local model visible even if discovery endpoints are down.
    const localModel = localStorage.getItem('gptModel');
    if (localModel) modelNames.add(localModel);

    // Local LLM model catalog.
    try {
        const llmBase = ANCHORWORKS_CONFIG?.llm || 'http://127.0.0.1:11435';
        const resp = await fetch(`${llmBase}/api/tags`, {
            credentials: 'include',
            signal: AbortSignal.timeout(5000),
        });
        if (resp.ok) {
            const data = await resp.json();
            for (const m of (data.models || [])) {
                const name = typeof m === 'string' ? m : (m.name || m.model || '');
                if (name) modelNames.add(name);
            }
        }
    } catch (e) {
        // Local LLM may be down; continue with other sources.
    }

    // Bridge-saved inference profiles can include models not present in local tags.
    try {
        const resp = await fetch(bridgeApi('/api/inference/profiles'), {
            credentials: 'include',
            signal: AbortSignal.timeout(5000),
        });
        if (resp.ok) {
            const data = await resp.json();
            const profiles = data.profiles || {};
            for (const name of Object.keys(profiles)) {
                if (name) modelNames.add(name);
            }
        }
    } catch (e) {
        // Bridge profile store unavailable.
    }

    return Array.from(modelNames).sort((a, b) => a.localeCompare(b));
}

async function cpToolPolicyInit() {
    // Populate model dropdown
    const select = document.getElementById('cp-tool-model-select');
    if (!select) return;
    // Keep only the placeholder option to avoid duplicate model entries on re-open.
    while (select.options.length > 1) select.remove(1);
    try {
        const models = await _cpLoadToolPolicyModels();
        for (const name of models) {
            const opt = document.createElement('option');
            opt.value = name;
            opt.textContent = name;
            select.appendChild(opt);
        }
    } catch (e) {
        // Model discovery may fail if services are offline.
    }

    // Load tool list
    try {
        const resp = await fetch(bridgeApi('/api/tools'), {
            credentials: 'include',
            signal: AbortSignal.timeout(5000),
        });
        if (resp.ok) {
            const data = await resp.json();
            _cpToolList = data.tools || [];
        }
    } catch (e) {
        _cpToolList = [];
    }
}

async function cpToolPolicyLoad() {
    const select = document.getElementById('cp-tool-model-select');
    const container = document.getElementById('cp-tool-policy');
    const actions = document.getElementById('cp-tool-policy-actions');
    if (!select || !container) return;
    const model = select.value;
    if (!model) {
        container.innerHTML = '<div style="color:var(--text-secondary);font-size:12px;padding:12px;text-align:center;">Select a model to configure tool access</div>';
        if (actions) actions.style.display = 'none';
        return;
    }

    // Fetch existing policy for this model
    let allowed = null;
    try {
        const resp = await fetch(bridgeApi(`/api/control/tool-policy/${encodeURIComponent(model)}`), {
            credentials: 'include',
            signal: AbortSignal.timeout(5000),
        });
        if (resp.ok) {
            const data = await resp.json();
            allowed = data.allowed; // list or null
        }
    } catch (e) { /* use defaults */ }

    // Build toggle list
    container.innerHTML = '';
    if (!_cpToolList.length) {
        container.innerHTML = '<div style="color:var(--text-secondary);font-size:12px;padding:12px;">No tools registered.</div>';
        return;
    }

    for (const tool of _cpToolList) {
        const isOn = allowed === null
            ? (tool.safety !== 'write') // default: read=ON, write=OFF
            : allowed.includes(tool.name);
        const safetyColor = tool.safety === 'write' ? 'var(--danger)' : 'var(--highlight)';
        const row = document.createElement('div');
        row.style.cssText = 'display:flex;align-items:center;gap:10px;padding:6px 12px;background:rgba(255,255,255,0.02);border-radius:6px;';
        row.innerHTML = `
            <div style="flex:1;min-width:0;">
                <span style="font-size:13px;font-weight:500;">${_cpEsc(tool.name)}</span>
                <span style="font-size:11px;color:var(--text-secondary);margin-left:6px;">${_cpEsc(tool.description || '').slice(0, 60)}</span>
            </div>
            <span style="font-size:9px;padding:2px 6px;border-radius:8px;background:${tool.safety === 'write' ? 'rgba(233,69,96,0.15)' : 'rgba(0,212,255,0.15)'};color:${safetyColor};text-transform:uppercase;">${_cpEsc(tool.safety || 'read')}</span>
            <label style="position:relative;display:inline-block;width:32px;height:18px;cursor:pointer;">
                <input type="checkbox" class="cp-tool-toggle" data-tool="${_cpEsc(tool.name)}" ${isOn ? 'checked' : ''}
                    style="opacity:0;width:0;height:0;">
                <span style="position:absolute;top:0;left:0;right:0;bottom:0;background:${isOn ? 'var(--highlight)' : 'rgba(255,255,255,0.1)'};border-radius:9px;transition:background 0.2s;"></span>
                <span style="position:absolute;top:1px;left:${isOn ? '15px' : '1px'};width:16px;height:16px;background:white;border-radius:50%;transition:left 0.2s;box-shadow:0 1px 3px rgba(0,0,0,0.3);"></span>
            </label>
        `;
        // Wire up the visual toggle
        const checkbox = row.querySelector('input[type=checkbox]');
        checkbox.addEventListener('change', function() {
            const span1 = this.parentElement.querySelectorAll('span');
            span1[0].style.background = this.checked ? 'var(--highlight)' : 'rgba(255,255,255,0.1)';
            span1[1].style.left = this.checked ? '15px' : '1px';
        });
        container.appendChild(row);
    }
    if (actions) actions.style.display = 'flex';
}

async function cpToolPolicySave() {
    const select = document.getElementById('cp-tool-model-select');
    if (!select || !select.value) return;
    const model = select.value;
    const toggles = document.querySelectorAll('.cp-tool-toggle');
    const allowed = [];
    toggles.forEach(cb => {
        if (cb.checked) allowed.push(cb.dataset.tool);
    });
    try {
        const resp = await fetch(bridgeApi(`/api/control/tool-policy/${encodeURIComponent(model)}`), {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ allowed }),
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        // Flash success
        const actions = document.getElementById('cp-tool-policy-actions');
        if (actions) {
            const btn = actions.querySelector('button');
            if (btn) { const orig = btn.textContent; btn.textContent = 'Saved!'; setTimeout(() => btn.textContent = orig, 1500); }
        }
    } catch (e) {
        alert('Save failed: ' + e.message);
    }
}

function cpToolPolicyReset() {
    // Reset toggles to defaults: read=ON, write=OFF
    document.querySelectorAll('.cp-tool-toggle').forEach(cb => {
        const toolName = cb.dataset.tool;
        const tool = _cpToolList.find(t => t.name === toolName);
        const shouldBeOn = tool ? tool.safety !== 'write' : true;
        cb.checked = shouldBeOn;
        cb.dispatchEvent(new Event('change'));
    });
}

// ── Section C: Tool Telemetry Dashboard ──────────────────────

async function cpTelemetryRefresh() {
    const container = document.getElementById('cp-telemetry');
    if (!container) return;
    container.innerHTML = '<div style="color:var(--text-secondary);font-size:12px;padding:12px;">Loading telemetry...</div>';
    try {
        const resp = await fetch(bridgeApi('/api/control/tool-telemetry'), {
            credentials: 'include',
            signal: AbortSignal.timeout(8000),
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        cpTelemetryRender(data.stats || {});
    } catch (e) {
        container.innerHTML = `<div style="color:var(--danger);font-size:12px;padding:12px;">Failed: ${_cpEsc(e.message)}</div>`;
    }
}

function cpTelemetryRender(stats) {
    const container = document.getElementById('cp-telemetry');
    if (!container) return;
    const models = Object.keys(stats);
    if (!models.length) {
        container.innerHTML = '<div style="color:var(--text-secondary);font-size:12px;padding:12px;text-align:center;">No telemetry data yet. Tool calls will appear here after models use tools.</div>';
        return;
    }
    container.innerHTML = '';
    for (const model of models.sort()) {
        const tools = stats[model];
        const toolNames = Object.keys(tools).sort();
        const card = document.createElement('div');
        card.style.cssText = 'padding:12px;background:rgba(255,255,255,0.02);border-radius:8px;';
        let tableHtml = `
            <div style="font-size:13px;font-weight:600;margin-bottom:8px;color:var(--text-primary);">${_cpEsc(model)}</div>
            <table style="width:100%;font-size:11px;border-collapse:collapse;">
                <tr style="color:var(--text-secondary);text-transform:uppercase;font-size:10px;">
                    <th style="text-align:left;padding:4px 8px;">Tool</th>
                    <th style="text-align:right;padding:4px 8px;">Calls</th>
                    <th style="text-align:right;padding:4px 8px;">OK</th>
                    <th style="text-align:right;padding:4px 8px;">Fail</th>
                    <th style="text-align:right;padding:4px 8px;">Denied</th>
                    <th style="text-align:right;padding:4px 8px;">Last Used</th>
                </tr>
        `;
        for (const tn of toolNames) {
            const t = tools[tn];
            const okColor = t.success > 0 ? 'var(--success, #00e676)' : 'var(--text-secondary)';
            const failColor = t.fail > 0 ? 'var(--danger, #e94560)' : 'var(--text-secondary)';
            const deniedColor = t.denied > 0 ? '#ffb400' : 'var(--text-secondary)';
            tableHtml += `
                <tr style="border-top:1px solid rgba(255,255,255,0.04);">
                    <td style="padding:4px 8px;color:var(--text-primary);">${_cpEsc(tn)}</td>
                    <td style="text-align:right;padding:4px 8px;">${t.calls}</td>
                    <td style="text-align:right;padding:4px 8px;color:${okColor};">${t.success}</td>
                    <td style="text-align:right;padding:4px 8px;color:${failColor};">${t.fail}</td>
                    <td style="text-align:right;padding:4px 8px;color:${deniedColor};">${t.denied}</td>
                    <td style="text-align:right;padding:4px 8px;color:var(--text-secondary);font-size:10px;">${t.last_used ? _cpEsc(t.last_used.slice(11, 19)) : '--'}</td>
                </tr>
            `;
        }
        tableHtml += '</table>';
        card.innerHTML = tableHtml;
        container.appendChild(card);
    }
}

// ── Initialization ───────────────────────────────────────────

async function ctrlInit() {
    await cpToolPolicyInit();
}

window.ANCHORWORKS.ready.panel_control = true;
