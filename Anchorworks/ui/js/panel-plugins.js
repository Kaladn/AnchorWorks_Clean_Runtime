// panel-plugins.js -- Plugin Hub (loadPlugins)
// Extracted from anchorworks_production.js
if (!window.bridgeApi) console.warn('core.js not loaded before panel-plugins.js');

// Header health pills removed (v1.5.0). Service status visible in Monitoring panel.
function hdrStartHealthPolling() { /* no-op — pills removed */ }

// ══════════════════════════════════════════════════════════════
// Plugins Page — Catalog, Connect/Disconnect, Pipeline Order
// ══════════════════════════════════════════════════════════════

// Local fallback registry — cards render even if bridge API is unreachable
const _FALLBACK_PLUGINS = [];

let _pluginsData = [];
let _selectedPluginId = null;

async function loadPlugins() {
    const listEl = document.getElementById('plugins-list');
    const summary = document.getElementById('plugins-summary');
    if (!listEl) return;

    // Try API first, fall back to local registry
    try {
        const resp = await fetch(bridgeApi('/api/plugins'), { signal: AbortSignal.timeout(5000) });
        if (resp.ok) {
            _pluginsData = await resp.json();
        } else {
            throw new Error('API unavailable');
        }
    } catch {
        _pluginsData = JSON.parse(JSON.stringify(_FALLBACK_PLUGINS));
    }

    const connected = _pluginsData.filter(p => p.connected).length;
    if (summary) summary.textContent = `${_pluginsData.length} installed, ${connected} connected`;

    // Auto-select first plugin if none selected
    if (!_selectedPluginId && _pluginsData.length > 0) {
        _selectedPluginId = _pluginsData[0].id;
    }

    pluginsRenderList();
    pluginsRenderDetail();
    _renderPipelineLane();
    checkAllPluginHealth();
}

function pluginsRenderList() {
    const listEl = document.getElementById('plugins-list');
    if (!listEl) return;
    listEl.innerHTML = '';

    for (const p of _pluginsData) {
        const row = document.createElement('div');
        row.className = 'plugin-row' +
            (_selectedPluginId === p.id ? ' selected' : '') +
            (!p.connected ? ' disconnected' : '');
        row.style.setProperty('--row-accent', p.color || '#888');
        row.id = `prow-${p.id}`;

        row.innerHTML = `
            <span class="pr-dot unknown" id="prow-${p.id}-dot"></span>
            <span class="pr-name">${p.name}</span>
            <span class="pr-version">v${p.version}</span>
        `;

        row.addEventListener('click', () => {
            _selectedPluginId = p.id;
            pluginsRenderList();
            pluginsRenderDetail();
        });

        listEl.appendChild(row);
    }
}

function pluginsRenderDetail() {
    const detail = document.getElementById('plugins-detail');
    if (!detail) return;

    const plugin = _pluginsData.find(p => p.id === _selectedPluginId);
    if (!plugin) {
        detail.innerHTML = '<div class="pd-empty">Select a plugin to view details</div>';
        return;
    }

    // Generic header (all plugins)
    const statusClass = plugin.connected ? 'connected' : 'disconnected';
    const statusLabel = plugin.connected ? 'Connected' : 'Disconnected';
    let html = `
        <div class="pd-header">
            <span style="font-size:24px;">${_pluginIcon(plugin.id)}</span>
            <div style="flex:1;">
                <h3 style="color:${plugin.color || '#eee'};">${plugin.name}
                    <span style="font-size:11px;color:var(--text-secondary);font-family:monospace;margin-left:8px;">v${plugin.version}</span>
                </h3>
            </div>
            <span class="pd-badge ${statusClass}">${statusLabel}</span>
        </div>
        <p style="font-size:12px;color:var(--text-secondary);margin:0 0 12px;line-height:1.5;">
            ${plugin.description || 'No description available.'}
        </p>
        <p style="font-size:11px;color:var(--text-tertiary);font-family:monospace;margin:0 0 16px;">
            Mount: ${plugin.mount || 'N/A'} &middot; Type: ${plugin.type || 'unknown'}
        </p>
        <div style="display:flex;gap:8px;margin-bottom:8px;">
            ${plugin.connected
                ? `<button class="btn btn-sm" style="border-color:#e94560;color:#e94560;" onclick="pluginDisconnect('${plugin.id}')">Disconnect</button>`
                : `<button class="btn btn-sm" style="border-color:#00ff88;color:#00ff88;" onclick="pluginConnect('${plugin.id}')">Connect</button>`
            }
        </div>
    `;

    // Plugin-specific detail sections
    html += '<div id="plugin-specific-detail"></div>';
    detail.innerHTML = html;

    renderGenericPluginDetail(plugin);
}

function _pluginIcon(id) {
    const icons = {};
    return icons[id] || '\uD83D\uDD0C';
}

async function pluginConnect(pluginId) {
    try {
        const resp = await fetch(bridgeApi(`/api/plugins/${pluginId}/connect`), { method: 'POST' });
        if (resp.ok) await loadPlugins();
    } catch (e) {
        console.error('Plugin connect failed:', e);
    }
}

async function pluginDisconnect(pluginId) {
    try {
        const resp = await fetch(bridgeApi(`/api/plugins/${pluginId}/disconnect`), { method: 'POST' });
        if (resp.ok) await loadPlugins();
    } catch (e) {
        console.error('Plugin disconnect failed:', e);
    }
}

// ── Pipeline Lane (drag-drop reorder) ────────────────────────

function _renderPipelineLane() {
    const lane = document.getElementById('pipeline-lane');
    if (!lane) return;
    lane.innerHTML = '';

    // Get connected plugins sorted by pipeline_index
    const ordered = _pluginsData
        .filter(p => p.connected && p.pipeline_index >= 0)
        .sort((a, b) => a.pipeline_index - b.pipeline_index);

    if (ordered.length === 0) {
        lane.innerHTML = '<span class="pipeline-empty">No plugins in pipeline. Connect a plugin to add it.</span>';
        return;
    }

    ordered.forEach((p, idx) => {
        const chip = document.createElement('div');
        chip.className = 'pipeline-chip';
        chip.draggable = true;
        chip.dataset.pluginId = p.id;
        chip.style.borderColor = p.color || '#888';
        chip.innerHTML = `
            <span class="chip-order">${idx + 1}</span>
            <span>${p.name}</span>
            <span class="chip-remove" onclick="pipelineRemove('${p.id}')" title="Remove from pipeline">&times;</span>
        `;

        // Drag events
        chip.addEventListener('dragstart', (e) => {
            e.dataTransfer.setData('text/plain', p.id);
            chip.style.opacity = '0.5';
        });
        chip.addEventListener('dragend', () => { chip.style.opacity = '1'; });
        chip.addEventListener('dragover', (e) => {
            e.preventDefault();
            chip.style.boxShadow = `0 0 8px ${p.color || '#888'}44`;
        });
        chip.addEventListener('dragleave', () => { chip.style.boxShadow = ''; });
        chip.addEventListener('drop', (e) => {
            e.preventDefault();
            chip.style.boxShadow = '';
            const draggedId = e.dataTransfer.getData('text/plain');
            if (draggedId && draggedId !== p.id) {
                _reorderPipeline(draggedId, p.id);
            }
        });

        lane.appendChild(chip);
    });
}

async function _reorderPipeline(draggedId, targetId) {
    // Build new order: remove dragged, insert before target
    const current = _pluginsData
        .filter(p => p.connected && p.pipeline_index >= 0)
        .sort((a, b) => a.pipeline_index - b.pipeline_index)
        .map(p => p.id);

    const without = current.filter(id => id !== draggedId);
    const targetIdx = without.indexOf(targetId);
    without.splice(targetIdx, 0, draggedId);

    try {
        const resp = await fetch(bridgeApi('/api/plugins/reorder'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(without),
        });
        if (resp.ok) await loadPlugins();
    } catch (e) {
        console.error('Reorder failed:', e);
    }
}

async function pipelineRemove(pluginId) {
    // Remove from pipeline order but keep connected
    const current = _pluginsData
        .filter(p => p.connected && p.pipeline_index >= 0)
        .sort((a, b) => a.pipeline_index - b.pipeline_index)
        .map(p => p.id)
        .filter(id => id !== pluginId);

    try {
        const resp = await fetch(bridgeApi('/api/plugins/reorder'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(current),
        });
        if (resp.ok) await loadPlugins();
    } catch (e) {
        console.error('Pipeline remove failed:', e);
    }
}


function _escHtml(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}


// ══════════════════════════════════════════════════════════════
// Plugin Detail — Generic (fallback for unknown plugins)
// ══════════════════════════════════════════════════════════════

function renderGenericPluginDetail(plugin) {
    const container = document.getElementById('plugin-specific-detail');
    if (!container) return;

    container.innerHTML = `
        <div class="pd-section">
            <h4>Plugin Surface</h4>
            <p style="font-size:12px;color:var(--text-secondary);">
                Checking for plugin UI endpoint...
            </p>
        </div>
    `;

    void renderGenericPluginSurface(plugin);
}

async function renderGenericPluginSurface(plugin) {
    const container = document.getElementById('plugin-specific-detail');
    if (!container) return;

    const mount = _primaryPluginMount(plugin);
    if (!mount) {
        container.innerHTML = `
            <div class="pd-section">
                <h4>Plugin Info</h4>
                <p style="font-size:12px;color:var(--text-secondary);">
                    No mount path available for this plugin card.
                </p>
            </div>
        `;
        return;
    }

    const candidatePaths = [
        `${mount}/ui`,
        `${mount}/preview`,
        `${mount}/dashboard`,
    ];

    let selected = null;
    for (const relPath of candidatePaths) {
        try {
            const resp = await fetch(bridgeApi(relPath), { signal: AbortSignal.timeout(3000) });
            if (resp.ok) {
                const ct = (resp.headers.get('content-type') || '').toLowerCase();
                if (!ct || ct.includes('text/html') || ct.includes('application/xhtml+xml')) {
                    selected = relPath;
                    break;
                }
            }
        } catch (_) {
            // Try next candidate.
        }
    }

    // Guard against stale async writes after user selects another plugin.
    if (_selectedPluginId !== plugin.id) return;

    if (selected) {
        const _baseUiUrl = bridgeApi(selected);
        const uiUrl = _baseUiUrl + (_baseUiUrl.includes('?') ? '&' : '?') + 'cbts=' + Date.now();
        container.innerHTML = `
            <div class="pd-section">
                <h4>Plugin UI</h4>
                <p style="font-size:12px;color:var(--text-secondary);margin-bottom:8px;">
                    Embedded plugin surface loaded from <code>${selected}</code>.
                </p>
                <a class="btn btn-sm" href="${uiUrl}" target="_blank" rel="noopener noreferrer"
                   style="margin-bottom:10px;display:inline-block;">Open In New Tab</a>
                <iframe src="${uiUrl}"
                    style="width:100%;height:560px;border:1px solid var(--border);border-radius:8px;background:#0b1326;"
                    loading="lazy"></iframe>
            </div>
        `;
        return;
    }

    container.innerHTML = `
        <div class="pd-section">
            <h4>Plugin Info</h4>
            <p style="font-size:12px;color:var(--text-secondary);">
                No plugin UI endpoint responded. This plugin may be API-only.
            </p>
            <p style="font-size:11px;color:var(--text-tertiary);font-family:monospace;">
                Tried: ${_escHtml(candidatePaths.join(', '))}
            </p>
        </div>
    `;
}

function _primaryPluginMount(plugin) {
    const raw = (plugin && plugin.mount) ? String(plugin.mount) : '';
    if (!raw) return '';
    const first = raw.split(',')[0].trim();
    if (!first.startsWith('/')) return '';
    return first;
}


window.ANCHORWORKS.ready.panel_plugins = true;
