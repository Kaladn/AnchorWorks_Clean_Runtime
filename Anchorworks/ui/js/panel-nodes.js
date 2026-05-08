// panel-nodes.js — AnchorWorks Nodes: connection surface
// Node tab = who is connected. Mesh tab = what you do with them.
if (!window.bridgeApi) console.warn('core.js not loaded before panel-nodes.js');

// ── State ─────────────────────────────────────────────────────────────────
let _nodesInitDone = false;
let _nodesData = [];
let _nodesHeartbeatResults = {};

// ── Init / Refresh ─────────────────────────────────────────────────────────

async function nodesInit() {
    if (_nodesInitDone) { nodesRefresh(); return; }
    _nodesInitDone = true;
    // Auto-start mDNS discovery silently
    fetch(bridgeApi('/api/nodes/discovery/start'), { method: 'POST', credentials: 'include' })
        .then(r => r.json())
        .then(d => _updateDiscoveryBadge(d.running))
        .catch(() => {});
    await nodesRefresh();
}

async function nodesRefresh() {
    const btn = document.querySelector('[onclick="nodesRefresh()"]');
    const orig = btn?.textContent;
    if (btn) { btn.textContent = '…'; btn.disabled = true; }

    try {
        const [statusResp, listResp] = await Promise.all([
            fetch(bridgeApi('/api/nodes/status'), { credentials: 'include', signal: AbortSignal.timeout(4000) }),
            fetch(bridgeApi('/api/nodes'), { credentials: 'include', signal: AbortSignal.timeout(4000) }),
        ]);

        if (statusResp.ok) {
            const status = await statusResp.json();
            if (!status.error) _renderLocalInfo(status);
        }

        if (listResp.ok) {
            const list = await listResp.json();
            _nodesData = (list.nodes || []).filter(n => !n.self);
            _renderNodeList(_nodesData);
            const total = _nodesData.length;
            const online = _nodesData.filter(n => n.online).length;
            const el = document.getElementById('nodes-summary');
            if (el) el.textContent = total ? `${online}/${total} online` : '';
            const countEl = document.getElementById('nodes-count');
            if (countEl) countEl.textContent = total ? `${total} registered` : '';
        }

        // Also refresh discovery badge
        fetch(bridgeApi('/api/nodes/discovery/status'), { credentials: 'include' })
            .then(r => r.json())
            .then(d => _updateDiscoveryBadge(d.running, d.peers_count))
            .catch(() => {});

    } catch (e) {
        const el = document.getElementById('nodes-local-info');
        if (el) el.textContent = 'Node service unavailable';
    } finally {
        if (btn) { btn.textContent = orig; btn.disabled = false; }
    }
}

// ── Local info card ─────────────────────────────────────────────────────────

function _renderLocalInfo(status) {
    const el = document.getElementById('nodes-local-info');
    if (!el) return;
    const caps = status.caps || {};
    el.innerHTML = `
        <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:6px;">
            ${_infoChip('Node ID', status.local_node_id || '—')}
            ${_infoChip('Hostname', caps.hostname || '—')}
            ${_infoChip('CPU', caps.cpu_name ? caps.cpu_name.split(' ').slice(-2).join(' ') : '—')}
            ${_infoChip('Cores', caps.cpu_cores != null ? caps.cpu_cores : '—')}
            ${_infoChip('RAM', caps.ram_gb != null ? caps.ram_gb + ' GB' : '—')}
            ${_infoChip('GPU', caps.gpu_name || 'None')}
            ${_infoChip('Paired nodes', status.paired_count ?? 0)}
        </div>`;
}

function _infoChip(label, value) {
    return `<div style="background:rgba(255,255,255,0.04);border-radius:6px;padding:6px 10px;">
        <div style="font-size:10px;color:var(--text-tertiary);margin-bottom:2px;">${_esc(label)}</div>
        <div style="font-size:12px;color:var(--text-primary);font-family:monospace;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${_esc(String(value))}</div>
    </div>`;
}

// ── Node list ───────────────────────────────────────────────────────────────

function _renderNodeList(nodes) {
    const el = document.getElementById('nodes-list');
    if (!el) return;
    if (!nodes.length) {
        el.innerHTML = `<div style="color:var(--text-tertiary);font-size:12px;padding:20px;text-align:center;">
            No nodes registered. Import a device profile or add manually.
        </div>`;
        return;
    }
    el.innerHTML = nodes.map(n => _nodeCard(n)).join('');
}

function _nodeCard(n) {
    const hb = _nodesHeartbeatResults[n.id];
    const online = hb === 'ok' ? true : (hb === 'unreachable' ? false : n.online);
    const dotColor = online ? '#00d26a' : '#666';
    const pairState = n.pairing_state || 'unpaired';
    const pairColor = pairState === 'paired' ? '#00d26a' : (pairState === 'pending' ? '#ff8800' : '#888');
    const fingerprint = n.caps_summary?.fingerprint || '';

    return `<div style="display:flex;align-items:center;justify-content:space-between;
                padding:10px 14px;background:rgba(255,255,255,0.04);border-radius:8px;
                border-left:3px solid ${dotColor};gap:12px;flex-wrap:wrap;">
        <div style="display:flex;align-items:center;gap:10px;min-width:0;">
            <span style="width:8px;height:8px;border-radius:50%;background:${dotColor};flex-shrink:0;"
                  title="${online ? 'Online' : 'Offline'}"></span>
            <div style="min-width:0;">
                <div style="font-size:13px;font-weight:600;color:var(--text-primary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                    ${_esc(n.name || n.id)}
                </div>
                <div style="font-size:11px;color:var(--text-tertiary);font-family:monospace;">
                    ${_esc(n.host || '—')}:${_esc(n.port || 5060)}
                    ${n.id ? ` · <span title="Machine ID">${_esc(n.id)}</span>` : ''}
                    ${fingerprint ? ` · <span title="Fingerprint" style="color:#888;">${fingerprint.slice(0,12)}…</span>` : ''}
                </div>
            </div>
        </div>
        <div style="display:flex;align-items:center;gap:6px;flex-shrink:0;">
            <span style="font-size:10px;padding:2px 8px;border-radius:10px;
                         background:rgba(255,255,255,0.06);color:${pairColor};">
                ${_esc(pairState)}
            </span>
            ${pairState !== 'paired'
                ? `<button class="btn btn-sm" onclick="nodesShowPairModal('${_esc(n.id)}')"
                          style="font-size:10px;padding:2px 10px;background:#cc7a00;color:#fff;">Pair</button>`
                : `<button class="btn btn-sm" onclick="nodesUnpair('${_esc(n.id)}')"
                          style="font-size:10px;padding:2px 10px;background:rgba(255,255,255,0.08);color:var(--text-secondary);">Unpair</button>`
            }
            <button class="btn btn-sm" onclick="nodesRemove('${_esc(n.id)}')"
                    style="font-size:10px;padding:2px 10px;background:rgba(220,50,50,0.15);color:#e94560;">Remove</button>
        </div>
    </div>`;
}

// ── Discovery badge ─────────────────────────────────────────────────────────

function _updateDiscoveryBadge(running, peersCount) {
    const el = document.getElementById('nodes-discovery-badge');
    if (!el) return;
    if (running) {
        const n = peersCount != null ? ` · ${peersCount} seen` : '';
        el.textContent = `mDNS active${n}`;
        el.style.background = 'rgba(0,210,106,0.12)';
        el.style.color = '#00d26a';
    } else {
        el.textContent = 'discovery off';
        el.style.background = 'rgba(255,255,255,0.06)';
        el.style.color = 'var(--text-tertiary)';
    }
}

// ── Profile import ─────────────────────────────────────────────────────────

async function nodesImportProfile(input) {
    const file = input.files[0];
    if (!file) return;
    input.value = '';
    let profile;
    try {
        profile = JSON.parse(await file.text());
    } catch {
        alert('Invalid JSON file.');
        return;
    }
    if (!profile.machine_id) {
        alert('Not a valid AnchorWorks device profile — missing machine_id.');
        return;
    }
    try {
        const resp = await fetch(bridgeApi('/api/nodes/register-profile'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify(profile),
        });
        const data = await resp.json();
        if (!resp.ok || data.error) {
            alert(`Import failed: ${data.error?.message || resp.status}`);
            return;
        }
        const node = data.node || {};
        const offline = !node.last_seen || node.last_seen === 0;
        if (offline) {
            _showFlash(`Registered ${node.hostname || node.node_id} — offline/pending. Will connect when daemon starts.`, 'warn');
        } else {
            _showFlash(`Connected: ${node.hostname || node.node_id} at ${node.ip}:${node.port}`, 'ok');
        }
        await nodesRefresh();
    } catch (e) {
        alert(`Import error: ${e.message}`);
    }
}

// ── Manual add modal ────────────────────────────────────────────────────────

function nodesShowAddModal() {
    const el = document.getElementById('nodes-add-modal');
    if (el) el.style.display = 'flex';
    const ipEl = document.getElementById('nodes-add-ip');
    if (ipEl) ipEl.focus();
    const errEl = document.getElementById('nodes-add-error');
    if (errEl) errEl.style.display = 'none';
}

function nodesHideAddModal() {
    const el = document.getElementById('nodes-add-modal');
    if (el) el.style.display = 'none';
}

async function nodesRegisterFromModal() {
    const ip = document.getElementById('nodes-add-ip')?.value?.trim();
    const port = parseInt(document.getElementById('nodes-add-port')?.value || '5060', 10);
    const nickname = document.getElementById('nodes-add-nickname')?.value?.trim() || '';
    const errEl = document.getElementById('nodes-add-error');
    const btn = document.getElementById('nodes-add-submit');

    if (!ip) { if (errEl) { errEl.textContent = 'IP address is required.'; errEl.style.display = 'block'; } return; }
    if (errEl) errEl.style.display = 'none';
    if (btn) { btn.textContent = 'Connecting…'; btn.disabled = true; }

    try {
        const resp = await fetch(bridgeApi('/api/nodes/register'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ ip, port, nickname }),
        });
        const data = await resp.json();
        if (!resp.ok || !data.ok) {
            if (errEl) { errEl.textContent = data.error?.message || 'Connection failed.'; errEl.style.display = 'block'; }
            return;
        }
        nodesHideAddModal();
        _showFlash(`Registered ${data.node?.hostname || ip}`, 'ok');
        await nodesRefresh();
    } catch (e) {
        if (errEl) { errEl.textContent = e.message; errEl.style.display = 'block'; }
    } finally {
        if (btn) { btn.textContent = 'Connect'; btn.disabled = false; }
    }
}

// ── Heartbeat ───────────────────────────────────────────────────────────────

async function nodesHeartbeat() {
    const btn = document.querySelector('[onclick="nodesHeartbeat()"]');
    const orig = btn?.textContent;
    if (btn) { btn.textContent = '…'; btn.disabled = true; }

    try {
        const resp = await fetch(bridgeApi('/api/nodes/heartbeat'), {
            method: 'POST', credentials: 'include',
        });
        const data = await resp.json();
        _nodesHeartbeatResults = data.results || {};

        const results = _nodesHeartbeatResults;
        const ok = Object.values(results).filter(v => v === 'ok').length;
        const total = Object.keys(results).length;

        if (btn) {
            btn.textContent = total ? `${ok}/${total} OK` : 'No nodes';
            setTimeout(() => { if (btn) btn.textContent = orig; }, 2500);
        }
        _renderNodeList(_nodesData);
    } catch (e) {
        if (btn) {
            btn.textContent = 'Error';
            setTimeout(() => { if (btn) btn.textContent = orig; }, 2000);
        }
    } finally {
        if (btn) btn.disabled = false;
    }
}

// ── Remove ──────────────────────────────────────────────────────────────────

async function nodesRemove(nodeId) {
    if (!confirm(`Remove node ${nodeId}?`)) return;
    try {
        await fetch(bridgeApi('/api/nodes/remove'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ node_id: nodeId }),
        });
        await nodesRefresh();
    } catch (e) {
        alert(`Remove failed: ${e.message}`);
    }
}

// ── Pair / Unpair ────────────────────────────────────────────────────────────

function nodesShowPairModal(nodeId) {
    const modal = document.getElementById('nodes-pair-modal');
    const idInput = document.getElementById('nodes-pair-node-id');
    const keyInput = document.getElementById('nodes-pair-key');
    const errEl = document.getElementById('nodes-pair-error');
    const okEl = document.getElementById('nodes-pair-success');
    if (modal) modal.style.display = 'flex';
    if (idInput) idInput.value = nodeId;
    if (keyInput) { keyInput.value = ''; keyInput.focus(); }
    if (errEl) errEl.style.display = 'none';
    if (okEl) okEl.style.display = 'none';
}

function nodesHidePairModal() {
    const modal = document.getElementById('nodes-pair-modal');
    if (modal) modal.style.display = 'none';
}

async function nodesPairSubmit() {
    const nodeId = document.getElementById('nodes-pair-node-id')?.value?.trim();
    const key = document.getElementById('nodes-pair-key')?.value?.trim();
    const errEl = document.getElementById('nodes-pair-error');
    const okEl = document.getElementById('nodes-pair-success');
    const btn = document.getElementById('nodes-pair-submit');

    if (errEl) errEl.style.display = 'none';
    if (okEl) okEl.style.display = 'none';
    if (!key || key.length !== 64) {
        if (errEl) { errEl.textContent = 'Key must be exactly 64 hex characters.'; errEl.style.display = 'block'; }
        return;
    }
    if (btn) { btn.textContent = 'Pairing…'; btn.disabled = true; }

    try {
        const resp = await fetch(bridgeApi('/api/nodes/pair'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ node_id: nodeId, secret_hex: key }),
        });
        const data = await resp.json();
        if (data.pairing_state === 'paired') {
            if (okEl) { okEl.textContent = 'Paired successfully.'; okEl.style.display = 'block'; }
            setTimeout(() => { nodesHidePairModal(); nodesRefresh(); }, 1200);
        } else {
            if (errEl) { errEl.textContent = data.error?.message || 'Pairing rejected.'; errEl.style.display = 'block'; }
        }
    } catch (e) {
        if (errEl) { errEl.textContent = e.message; errEl.style.display = 'block'; }
    } finally {
        if (btn) { btn.textContent = 'Pair'; btn.disabled = false; }
    }
}

async function nodesUnpair(nodeId) {
    try {
        await fetch(bridgeApi('/api/nodes/unpair'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ node_id: nodeId }),
        });
        await nodesRefresh();
    } catch (e) {
        alert(`Unpair failed: ${e.message}`);
    }
}

// ── Utilities ────────────────────────────────────────────────────────────────

function _esc(s) {
    return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function _showFlash(msg, kind) {
    const summaryEl = document.getElementById('nodes-summary');
    if (!summaryEl) return;
    const prev = summaryEl.textContent;
    summaryEl.style.color = kind === 'ok' ? '#00d26a' : '#ff8800';
    summaryEl.textContent = msg;
    setTimeout(() => { summaryEl.style.color = ''; summaryEl.textContent = prev; }, 3000);
}

window.ANCHORWORKS.ready.panel_nodes = true;
