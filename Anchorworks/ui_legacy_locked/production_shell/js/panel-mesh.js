// panel-mesh.js -- Unified runtime overview for nodes, network, and pulse
if (!window.bridgeApi) console.warn('core.js not loaded before panel-mesh.js');

(function () {
    'use strict';

    let _meshInitDone = false;
    let _meshTimer = null;

    function _esc(value) {
        const div = document.createElement('div');
        div.textContent = value == null ? '' : String(value);
        return div.innerHTML;
    }

    function _setText(id, value) {
        const el = document.getElementById(id);
        if (el) el.textContent = value;
    }

    function _fmtPct(value) {
        if (value == null || Number.isNaN(Number(value))) return '-';
        return `${Math.round(Number(value))}%`;
    }

    function _fmtGb(value) {
        if (value == null || Number.isNaN(Number(value))) return '-';
        return `${Number(value).toFixed(1)} GB`;
    }

    async function _loadJson(path) {
        const resp = await fetch(bridgeApi(path), { credentials: 'include' });
        if (!resp.ok) throw new Error(`${path} -> ${resp.status}`);
        return resp.json();
    }

    function _renderServiceStrip(statusRes, networkRes, pulseRes) {
        const el = document.getElementById('mesh-service-strip');
        if (!el) return;

        const chips = [
            {
                label: 'Node Controller',
                ok: !!statusRes && !statusRes.error,
                meta: statusRes?.local_node_id || 'unavailable',
            },
            {
                label: 'Network Fabric',
                ok: networkRes?.ok === true,
                meta: networkRes?.nodes_configured != null
                    ? `${networkRes.nodes_configured} configured`
                    : 'unavailable',
            },
            {
                label: 'System Pulse',
                ok: pulseRes?.ok === true,
                meta: pulseRes?.sampling_interval_s != null
                    ? `every ${pulseRes.sampling_interval_s}s`
                    : 'unavailable',
            },
        ];

        el.innerHTML = chips.map((chip) => `
            <div class="mesh-service-chip ${chip.ok ? 'ok' : 'down'}">
                <span class="mesh-service-dot"></span>
                <span>${_esc(chip.label)}</span>
                <span class="mesh-service-meta">${_esc(chip.meta)}</span>
            </div>
        `).join('');
    }

    function _renderNodes(nodes, statusRes) {
        const listEl = document.getElementById('mesh-node-list');
        const summaryEl = document.getElementById('mesh-node-summary');
        if (!listEl) return;

        if (!nodes.length) {
            if (summaryEl) summaryEl.textContent = 'No nodes configured';
            listEl.innerHTML = '<div class="mesh-empty">No nodes configured yet.</div>';
            return;
        }

        const online = nodes.filter((node) => node.online).length;
        if (summaryEl) {
            summaryEl.textContent = `${online}/${nodes.length} online`;
        }

        listEl.innerHTML = nodes.map((node) => {
            const pairState = node.self ? 'local' : (node.pairing_state || 'unpaired');
            return `
                <div class="mesh-node-row">
                    <div class="mesh-node-main">
                        <span class="mesh-node-dot ${node.online ? 'ok' : 'down'}"></span>
                        <div>
                            <div class="mesh-node-name">${_esc(node.name || node.id)}</div>
                            <div class="mesh-node-meta">
                                ${_esc(node.host || 'localhost')}:${_esc(node.port || 5050)}
                                ${node.version ? ` · v${_esc(node.version)}` : ''}
                            </div>
                        </div>
                    </div>
                    <div class="mesh-node-right">
                        <span class="mesh-pill ${node.online ? 'ok' : 'idle'}">${node.online ? 'online' : 'offline'}</span>
                        <span class="mesh-pill">${_esc(pairState)}</span>
                        <button class="btn btn-sm" onclick="switchPanel('${node.self ? 'nodes' : 'network'}')">
                            ${node.self ? 'Control' : 'Browse'}
                        </button>
                    </div>
                </div>
            `;
        }).join('');

        _setText('mesh-stat-online', String(online));
        _setText('mesh-stat-total', `${nodes.length} total nodes`);
        _setText('mesh-stat-paired', String(statusRes?.paired_count ?? 0));
        _setText('mesh-stat-node-id', statusRes?.local_node_id || 'Local node unknown');
    }

    function _renderRoots(roots, networkRes) {
        const el = document.getElementById('mesh-roots');
        if (!el) return;

        _setText('mesh-stat-roots', String(roots.length));
        _setText(
            'mesh-stat-network',
            networkRes?.ok ? `phase ${networkRes.phase}` : 'network unavailable'
        );

        if (!roots.length) {
            el.innerHTML = '<div class="mesh-empty">No shared roots are configured for this machine.</div>';
            return;
        }

        el.innerHTML = roots.map((root) => `<span class="mesh-root-chip">${_esc(root)}</span>`).join('');
    }

    function _renderPulse(snapshot) {
        const el = document.getElementById('mesh-pulse');
        if (!el) return;

        if (!snapshot || snapshot.ok !== true) {
            _setText('mesh-stat-cpu', '-');
            _setText('mesh-stat-memory', 'pulse unavailable');
            el.innerHTML = '<div class="mesh-empty">System pulse is unavailable.</div>';
            return;
        }

        const cpuPct = snapshot.cpu_percent;
        const memUsed = snapshot.memory_used_gb ?? snapshot.ram_used_gb;
        const memTotal = snapshot.memory_total_gb ?? snapshot.ram_total_gb;

        _setText('mesh-stat-cpu', _fmtPct(cpuPct));
        _setText(
            'mesh-stat-memory',
            memUsed != null && memTotal != null
                ? `${_fmtGb(memUsed)} / ${_fmtGb(memTotal)}`
                : 'memory pending'
        );

        const cards = [
            ['CPU', _fmtPct(snapshot.cpu_percent)],
            ['Memory Used', memUsed != null ? _fmtGb(memUsed) : '-'],
            ['Memory Total', memTotal != null ? _fmtGb(memTotal) : '-'],
            ['Disk Used', snapshot.disk_used_gb != null ? _fmtGb(snapshot.disk_used_gb) : '-'],
            ['Disk Total', snapshot.disk_total_gb != null ? _fmtGb(snapshot.disk_total_gb) : '-'],
            ['GPU', snapshot.gpu_name || 'None'],
        ];

        el.innerHTML = cards.map(([label, value]) => `
            <div class="mesh-pulse-card">
                <span class="mesh-pulse-label">${_esc(label)}</span>
                <strong>${_esc(value)}</strong>
            </div>
        `).join('');
    }

    async function meshRefresh() {
        const [statusRes, nodesRes, networkRes, rootsRes, pulseStatusRes, pulseSnapRes] = await Promise.allSettled([
            _loadJson('/api/nodes/status'),
            _loadJson('/api/nodes'),
            _loadJson('/api/network/health'),
            _loadJson('/api/network/roots/this'),
            _loadJson('/api/system-pulse/status'),
            _loadJson('/api/system-pulse/snapshot'),
        ]);

        const status = statusRes.status === 'fulfilled' ? statusRes.value : null;
        const nodes = nodesRes.status === 'fulfilled' ? (nodesRes.value.nodes || []) : [];
        const network = networkRes.status === 'fulfilled' ? networkRes.value : null;
        const roots = rootsRes.status === 'fulfilled' ? (rootsRes.value.roots || []) : [];
        const pulseStatus = pulseStatusRes.status === 'fulfilled' ? pulseStatusRes.value : null;
        const pulseSnap = pulseSnapRes.status === 'fulfilled' ? pulseSnapRes.value : null;

        _renderServiceStrip(status, network, pulseStatus);
        _renderNodes(nodes, status);
        _renderRoots(roots, network);
        _renderPulse(pulseSnap);
    }

    async function meshInit() {
        if (!_meshInitDone) _meshInitDone = true;
        await meshRefresh();
        if (_meshTimer) clearInterval(_meshTimer);
        _meshTimer = setInterval(meshRefresh, 15000);
    }

    function meshStopPolling() {
        if (_meshTimer) {
            clearInterval(_meshTimer);
            _meshTimer = null;
        }
    }

    window.meshInit = meshInit;
    window.meshRefresh = meshRefresh;
    window._meshStopPolling = meshStopPolling;
})();

window.ANCHORWORKS.ready.panel_mesh = true;
