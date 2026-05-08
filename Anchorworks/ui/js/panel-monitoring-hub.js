// panel-monitoring-hub.js — Monitoring Control Plane
// Tabs: Overview · Pipelines · Servers · Network · System
// Follows the same patterns as panel-genesis.js / panel-monitoring.js

if (!window.bridgeApi) console.warn('core.js must load before panel-monitoring-hub.js');

// ── State ─────────────────────────────────────────────────────────────────────

const _MON_TABS     = ['overview', 'pipelines', 'servers', 'network', 'system'];
let   _monActiveTab = localStorage.getItem('mon-active-tab') || 'overview';
let   _monTimers    = {};
let   _monNetPrev   = {};   // path → {count, t} for rps delta
let   _monNetHistory= {};   // path → [{rps}] rolling 60 samples
const _MON_HIST_LEN = 60;

// ── Helpers ───────────────────────────────────────────────────────────────────

async function _monGet(path) {
    const r = await fetch(bridgeApi(path), { credentials: 'include' });
    if (!r.ok) throw new Error(`${path} → ${r.status}`);
    return r.json();
}

async function _monPost(path) {
    const r = await fetch(bridgeApi(path), {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json' }, body: '{}',
    });
    return r.json().catch(() => ({}));
}

function _monEl(id) { return document.getElementById(id); }

function _monFmt(n, dec = 1) {
    if (n == null || isNaN(n)) return '—';
    if (n >= 1e9) return (n / 1e9).toFixed(dec) + 'B';
    if (n >= 1e6) return (n / 1e6).toFixed(dec) + 'M';
    if (n >= 1e3) return (n / 1e3).toFixed(dec) + 'K';
    return Number(n).toFixed(dec).replace(/\.0$/, '');
}

function _monTimer(key, fn, ms) {
    _monClearTimer(key);
    fn();
    _monTimers[key] = setInterval(fn, ms);
}

function _monClearTimer(key) {
    if (_monTimers[key]) { clearInterval(_monTimers[key]); delete _monTimers[key]; }
}

function _monClearAll() {
    Object.keys(_monTimers).forEach(k => _monClearTimer(k));
    window._obsStopPolling?.();
}

// ── Tab switching ─────────────────────────────────────────────────────────────

function monSetTab(tab) {
    if (!_MON_TABS.includes(tab)) return;
    _monActiveTab = tab;
    localStorage.setItem('mon-active-tab', tab);

    // Update left-menu buttons
    _MON_TABS.forEach(t => {
        const btn = _monEl('mon-btn-' + t);
        if (btn) btn.classList.toggle('active', t === tab);
    });

    // Show/hide tab content
    _MON_TABS.forEach(t => {
        const el = _monEl('mon-tab-' + t);
        if (el) el.classList.toggle('active', t === tab);
    });

    // Stop all timers, start the one for the active tab
    _monClearAll();

    if (tab === 'overview')   _monTimer('overview',   _monRenderOverview,   5000);
    if (tab === 'pipelines')  _monTimer('pipelines',  _monRenderPipelines,  2000);
    if (tab === 'servers')    _monTimer('servers',     _monRenderServers,    5000);
    if (tab === 'network')    _monTimer('network',     _monRenderNetwork,    2000);
    if (tab === 'system')     { obsInit?.(); window._obsStartPolling?.(); }
}

// ── Entry point (called by switchPanel in core.js) ────────────────────────────

function monInit() {
    monSetTab(_monActiveTab);
}

window.monInit    = monInit;
window.monSetTab  = monSetTab;
window._monStopPolling = _monClearAll;

// ═══════════════════════════════════════════════════════════════════════════════
// OVERVIEW
// ═══════════════════════════════════════════════════════════════════════════════

async function _monRenderOverview() {
    try {
        const [boot, jobs, serviceHealth] = await Promise.all([
            _monGet('/api/boot'),
            _monGet('/api/jobs'),
            _monGet('/api/services/health').catch(() => ({})),
        ]);

        // Health badges
        const health = {
            ...(boot.health || {}),
            ...(boot.services || {}),
            ...(serviceHealth || {}),
        };
        const hEl = _monEl('mon-ov-health');
        if (hEl) {
            const services = [
                { key: 'bridge',    label: 'Bridge',    port: 5050 },
                { key: 'llm',       label: 'LLM',       port: 11435 },
                { key: 'ui',        label: 'UI',        port: 8080 },
                { key: 'reasoning', label: 'Reasoning', port: null },
            ];
            hEl.innerHTML = services.map(s => {
                const ok = health[s.key] === true;
                return `<div class="mon-health-badge">
                    <span class="mon-dot ${ok ? 'ok' : 'down'}"></span>
                    <span>${s.label}${s.port ? ` <span style="font-size:10px;color:var(--text-secondary);">:${s.port}</span>` : ''}</span>
                </div>`;
            }).join('');
        }

        // Job stats
        const jobList   = Array.isArray(jobs) ? jobs : (jobs.jobs || []);
        const running   = jobList.filter(j => j.status === 'running').length;
        const queued    = jobList.filter(j => j.status === 'queued').length;
        const errored   = jobList.filter(j => j.status === 'error').length;

        _monStat('mon-ov-running',  running);
        _monStat('mon-ov-queued',   queued);
        _monStat('mon-ov-errors',   errored);

        // Lexicon stats
        const stats = boot.stats || {};
        _monStat('mon-ov-entries',  _monFmt(stats.lexicon_entries ?? stats.entries, 0));
        _monStat('mon-ov-datalake', stats.data_lake_files ?? boot.data_lake_files ?? '—');
        _monStat('mon-ov-ws',       boot.active_ws ?? boot.ws_connections ?? '—');

        // Plugin count
        const plugins = boot.plugins || {};
        const mountedCount = Object.values(plugins).filter(Boolean).length;
        _monStat('mon-ov-plugins', mountedCount);

        // Uptime — session (bridge) + lifetime (OS)
        const sys = boot.system || {};
        const now = Date.now() / 1000;
        if (sys.bridge_started_at) {
            const secs = Math.round(now - sys.bridge_started_at);
            _monStat('mon-ov-session-uptime', _monFmtDur(secs));
            const since = new Date(sys.bridge_started_at * 1000);
            _monStat('mon-ov-session-since', 'since ' + since.toLocaleTimeString());
        }
        if (sys.os_boot_time) {
            const secs = Math.round(now - sys.os_boot_time);
            _monStat('mon-ov-os-uptime', _monFmtDur(secs));
            const since = new Date(sys.os_boot_time * 1000);
            _monStat('mon-ov-os-since', 'since ' + since.toLocaleDateString() + ' ' + since.toLocaleTimeString());
        }

        // Node cards — fetch async (non-blocking, failure is fine)
        _monRenderNodes();

    } catch (e) {
        const hEl = _monEl('mon-ov-health');
        if (hEl) hEl.innerHTML = `<span style="color:#e94560;font-size:12px;">Bridge offline — ${escapeHtml(e.message)}</span>`;
    }
}

function _monFmtDur(totalSecs) {
    const d = Math.floor(totalSecs / 86400);
    const h = Math.floor((totalSecs % 86400) / 3600);
    const m = Math.floor((totalSecs % 3600) / 60);
    if (d > 0) return `${d}d ${h}h ${m}m`;
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
}

async function _monRenderNodes() {
    const grid = _monEl('mon-node-grid');
    if (!grid) return;
    try {
        const data  = await _monGet('/api/nodes');
        const nodes = data.nodes || [];
        if (!nodes.length) {
            grid.innerHTML = '<div style="color:var(--text-secondary);font-size:12px;grid-column:1/-1;">No nodes configured. Add entries to anchorworks.config.json → "nodes".</div>';
            return;
        }
        grid.innerHTML = nodes.map(n => {
            const ok      = n.online === true;
            const isSelf  = n.self  === true;
            const safeHost = String(n.host || 'localhost').replace(/[^a-zA-Z0-9.\-:]/g, '');
            const safePort = parseInt(n.ui_port, 10) || 8080;
            const uiUrl   = `http://${safeHost}:${safePort}`;
            const entries = n.entries ? _monFmt(n.entries, 0) + ' entries' : '';
            const ver     = n.version ? `v${escapeHtml(String(n.version))}` : '';
            return `<div class="mon-stat-card" style="border-left-color:${ok ? '#00ff88' : '#555'};cursor:${ok && !isSelf ? 'pointer' : 'default'};"
                        ${ok && !isSelf ? `onclick="window.open('${escapeHtml(uiUrl)}','_blank')" title="Open ${escapeHtml(n.name)} UI"` : ''}>
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
                    <span class="mon-dot ${ok ? 'ok' : 'idle'}" style="flex-shrink:0;"></span>
                    <span class="mon-stat-label" style="font-size:12px;font-weight:700;color:var(--text-primary);">${escapeHtml(n.name)}${isSelf ? ' ★' : ''}</span>
                </div>
                <div style="font-size:10px;color:var(--text-secondary);line-height:1.8;">
                    <div>${escapeHtml(n.host)}:${n.port || 5050}</div>
                    ${entries ? `<div>${entries}</div>` : ''}
                    ${ver ? `<div>${ver}</div>` : ''}
                    ${ok && !isSelf ? `<div style="color:#00d4ff;margin-top:4px;">↗ click to open UI</div>` : ''}
                    ${!ok ? '<div style="color:#555;">offline</div>' : ''}
                </div>
            </div>`;
        }).join('');
    } catch (e) {
        grid.innerHTML = `<div style="color:#e94560;font-size:12px;grid-column:1/-1;">Node registry error: ${escapeHtml(e.message)}</div>`;
    }
}

function _monStat(id, val) {
    const el = _monEl(id);
    if (el) el.textContent = (val == null || val === '') ? '—' : val;
}

// ═══════════════════════════════════════════════════════════════════════════════
// PIPELINES
// ═══════════════════════════════════════════════════════════════════════════════

const _monJobLatency = {}; // job_type → {sum, count, last5:[]}

async function _monRenderPipelines() {
    try {
        const data   = await _monGet('/api/jobs');
        const jobs   = Array.isArray(data) ? data : (data.jobs || []);
        const root   = _monEl('mon-pipe-list');
        if (!root) return;

        if (!jobs.length) {
            root.innerHTML = '<div style="color:var(--text-secondary);font-size:13px;padding:24px 0;text-align:center;">No jobs in queue.</div>';
            return;
        }

        // Accumulate latency stats
        jobs.forEach(j => {
            if (!j.job_type) return;
            const t = _monJobLatency[j.job_type] = _monJobLatency[j.job_type] || { sum: 0, count: 0, last5: [] };
            if (j.status === 'completed' && j.updated_at && j.created_at) {
                const ms = (new Date(j.updated_at) - new Date(j.created_at));
                if (ms > 0) {
                    t.sum += ms; t.count++;
                    t.last5.push(ms);
                    if (t.last5.length > 5) t.last5.shift();
                }
            }
        });

        // Sort: running first, then queued, then rest
        const order = { running: 0, queued: 1, completed: 2, error: 3, cancelling: 4 };
        jobs.sort((a, b) => (order[a.status] ?? 9) - (order[b.status] ?? 9));

        root.innerHTML = jobs.map(j => {
            const lat  = _monJobLatency[j.job_type];
            const avg  = lat && lat.count ? Math.round(lat.sum / lat.count) : null;
            const prog = j.progress ? Object.entries(j.progress).map(([k, v]) => `${escapeHtml(String(k))}: ${escapeHtml(String(v))}`).join(' · ') : '';
            const err  = j.error ? `<div style="color:#e94560;margin-top:6px;font-family:monospace;font-size:10px;word-break:break-all;">${escapeHtml(j.error)}</div>` : '';
            const last5 = lat?.last5?.map(ms => `${ms}ms`).join(', ') || '—';

            return `<div class="mon-job-card ${escapeHtml(j.status || '')}" onclick="this.classList.toggle('expanded')" data-job-id="${escapeHtml(String(j.job_id || ''))}">
                <div class="mon-job-header">
                    <span class="mon-job-id">#${escapeHtml(String(j.job_id || '').slice(0, 8))}</span>
                    <span class="mon-job-type">${escapeHtml(j.job_type || 'unknown')}</span>
                    <span class="mon-job-status ${escapeHtml(j.status || '')}">${escapeHtml(j.status || '')}</span>
                </div>
                <div class="mon-job-meta">
                    ${prog ? `<span>${prog}</span>` : ''}
                    ${avg ? `<span>avg ${avg}ms</span>` : ''}
                    ${j.created_at ? `<span>started ${new Date(j.created_at).toLocaleTimeString()}</span>` : ''}
                </div>
                <div class="mon-job-detail">
                    <div>Last 5 durations: ${last5}</div>
                    ${err}
                </div>
            </div>`;
        }).join('');

    } catch (e) {
        const root = _monEl('mon-pipe-list');
        if (root) root.innerHTML = `<div style="color:#e94560;font-size:12px;">Error: ${escapeHtml(e.message)}</div>`;
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// SERVERS
// ═══════════════════════════════════════════════════════════════════════════════

async function _monRenderServers() {
    try {
        const [health, plugins, sys] = await Promise.all([
            _monGet('/api/services/health'),
            _monGet('/api/plugins'),
            _monGet('/api/system'),
        ]);

        const root = _monEl('mon-srv-grid');
        if (!root) return;

        const coreServers = [
            { key: 'bridge',    name: 'Bridge Server',  port: 5050,  desc: 'Lexicon mapping, API gateway' },
            { key: 'llm',       name: 'LLM Server',     port: 11435, desc: 'Ollama proxy + auth' },
            { key: 'ui',        name: 'UI Server',       port: 8080,  desc: 'AnchorWorks Production Console' },
            { key: 'reasoning', name: 'Reasoning Engine',port: null,  desc: '6-1-6 reasoning and structured inference' },
        ];

        root.innerHTML = coreServers.map(s => {
            const ok = health[s.key] === true;
            return `<div class="mon-server-card">
                <div class="mon-srv-header">
                    <span class="mon-dot ${ok ? 'ok' : 'down'}" style="flex-shrink:0;"></span>
                    <span class="mon-srv-name">${s.name}</span>
                </div>
                <div class="mon-srv-meta">
                    ${s.port ? `<span class="k">Port</span><span class="v">${s.port}</span>` : ''}
                    <span class="k">Status</span><span class="v" style="color:${ok ? '#00ff88' : '#e94560'}">${ok ? 'online' : 'offline'}</span>
                    <span class="k">Info</span><span class="v" style="font-family:sans-serif;font-size:11px;">${s.desc}</span>
                </div>
                <div class="mon-srv-actions">
                </div>
            </div>`;
        }).join('');

        // Plugin servers
        const pluginList = Array.isArray(plugins) ? plugins : (plugins.plugins || []);
        const plugEl = _monEl('mon-plugin-list');
        if (plugEl && pluginList.length) {
            plugEl.innerHTML = pluginList.map(p => {
                const ok = p.connected || p.mounted;
                return `<div class="mon-server-card">
                    <div class="mon-srv-header">
                        <span class="mon-dot ${ok ? 'ok' : 'idle'}" style="flex-shrink:0;"></span>
                        <span class="mon-srv-name">${escapeHtml(p.name || p.id)}</span>
                    </div>
                    <div class="mon-srv-meta">
                        <span class="k">Mount</span><span class="v">${escapeHtml(p.mount || '—')}</span>
                        <span class="k">Type</span><span class="v">${escapeHtml(p.type || '—')}</span>
                        <span class="k">Status</span><span class="v" style="color:${ok ? '#00ff88' : '#888'}">${ok ? 'mounted' : 'disconnected'}</span>
                    </div>
                </div>`;
            }).join('');
        }

        // Restart All button binding
        const btn = _monEl('mon-restart-btn');
        if (btn && !btn._bound) {
            btn._bound = true;
            btn.addEventListener('click', async () => {
                if (!confirm('Restart all AnchorWorks services? They will relaunch automatically.')) return;
                btn.disabled = true;
                btn.textContent = 'Restarting…';
                try {
                    await _monPost('/api/system/restart');
                    btn.textContent = 'Restarted — reconnecting…';
                } catch (e) {
                    btn.textContent = 'Restart failed';
                    btn.disabled = false;
                }
            });
        }

    } catch (e) {
        const root = _monEl('mon-srv-grid');
        if (root) root.innerHTML = `<div style="color:#e94560;font-size:12px;">Error: ${escapeHtml(e.message)}</div>`;
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// NETWORK
// ═══════════════════════════════════════════════════════════════════════════════

async function _monRenderNetwork() {
    try {
        const m    = await _monGet('/api/metrics');
        const now  = Date.now();
        const rows = Object.entries(m.by_path || {});

        // Compute rps deltas and push history
        rows.forEach(([path, row]) => {
            const prev = _monNetPrev[path];
            const rps  = prev && (now - prev.t) > 0
                ? (row.count - prev.count) / ((now - prev.t) / 1000)
                : 0;
            _monNetPrev[path] = { count: row.count, t: now };

            if (!_monNetHistory[path]) _monNetHistory[path] = [];
            _monNetHistory[path].push(Math.max(0, rps));
            if (_monNetHistory[path].length > _MON_HIST_LEN) _monNetHistory[path].shift();

            row._rps = rps;
        });

        // Sort by total count desc
        rows.sort((a, b) => b[1].count - a[1].count);

        // Uptime
        const uptime = m.started_at ? Math.round((now / 1000) - m.started_at) : 0;
        const uptimeEl = _monEl('mon-net-uptime');
        if (uptimeEl) {
            const h = Math.floor(uptime / 3600);
            const min = Math.floor((uptime % 3600) / 60);
            uptimeEl.textContent = `Bridge up ${h}h ${min}m`;
        }

        // Total requests
        const totalReq = rows.reduce((s, [, r]) => s + r.count, 0);
        const totalErr = rows.reduce((s, [, r]) => s + r.errors, 0);
        _monStat('mon-net-total', _monFmt(totalReq, 0));
        _monStat('mon-net-errs',  totalErr);

        // Table
        const tbody = _monEl('mon-net-tbody');
        if (!tbody) return;

        if (!rows.length) {
            tbody.innerHTML = '<tr><td colspan="5" style="color:var(--text-secondary);text-align:center;padding:20px;">No requests recorded yet.</td></tr>';
            return;
        }

        tbody.innerHTML = rows.map(([path, row]) => {
            const rps    = (row._rps || 0).toFixed(2);
            const spark  = _monSparkline(_monNetHistory[path] || []);
            const errPct = row.count ? ((row.errors / row.count) * 100).toFixed(1) : '0.0';
            return `<tr>
                <td class="col-path" title="${escapeHtml(path)}">${escapeHtml(path)}</td>
                <td class="col-rps">${rps}/s ${spark}</td>
                <td class="col-err">${row.errors} <span style="font-size:10px;color:var(--text-secondary);">(${errPct}%)</span></td>
                <td class="col-lat">${row.avg_latency_ms}ms</td>
                <td class="col-tot">${_monFmt(row.count, 0)}</td>
            </tr>`;
        }).join('');

    } catch (e) {
        const tbody = _monEl('mon-net-tbody');
        if (tbody) tbody.innerHTML = `<tr><td colspan="5" style="color:#e94560;">Error: ${escapeHtml(e.message)}</td></tr>`;
    }
}

function _monSparkline(data) {
    if (!data.length) return '';
    const w = 50, h = 16;
    const max = Math.max(...data, 0.01);
    const pts = data.slice(-20).map((v, i, arr) => {
        const x = Math.round((i / (arr.length - 1 || 1)) * w);
        const y = Math.round(h - (v / max) * h);
        return `${x},${y}`;
    }).join(' ');
    return `<svg class="mon-sparkline" width="${w}" height="${h}" style="vertical-align:middle;margin-left:4px;opacity:0.8;">
        <polyline points="${pts}" fill="none" stroke="#00d4ff" stroke-width="1.5"/>
    </svg>`;
}
