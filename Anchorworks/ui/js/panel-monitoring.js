// panel-monitoring.js — Monitoring / Observe module (obs* namespace)
// Extracted from anchorworks_production.js L9592-10032
if (!window.bridgeApi) console.warn('core.js not loaded before panel-monitoring.js');

// ── Monitoring (Observe) Module ─────────────────────────────────

const _OBS_POLL_MS = 3000;
const _OBS_HISTORY_LEN = 60;

const _OBS_COLORS = {
    cpu:     '#e94560',
    ram:     '#00d4ff',
    gpu:     '#00ff88',
    disk:    '#ffd700',
    net:     '#b388ff',
    os:      '#ff6bd6',
    process: '#ff8c42',
};

const _OBS_GAUGE_IDS = ['cpu.percent', 'ram.percent', 'gpu.util_percent', 'disk.percent'];

const _OBS_CHART_LINES = [
    { id: 'cpu.percent',      label: 'CPU %',    color: '#e94560' },
    { id: 'ram.percent',      label: 'RAM %',    color: '#00d4ff' },
    { id: 'gpu.util_percent', label: 'GPU %',    color: '#00ff88' },
    { id: 'disk.percent',     label: 'Disk %',   color: '#ffd700' },
    { id: 'gpu.temp_c',       label: 'GPU Temp', color: '#ff6bd6' },
];

const _OBS_CAT_PEEK = {
    cpu:     [{ id: 'cpu.percent', label: 'Usage' }, { id: 'cpu.freq_mhz', label: 'Freq' }],
    ram:     [{ id: 'ram.percent', label: 'Usage' }, { id: 'ram.used_gb', label: 'Used' }],
    disk:    [{ id: 'disk.percent', label: 'Usage' }, { id: 'disk.used_gb', label: 'Used' }],
    net:     [{ id: 'net.bytes_recv', label: 'Recv' }, { id: 'net.bytes_sent', label: 'Sent' }],
    gpu:     [{ id: 'gpu.util_percent', label: 'Util' }, { id: 'gpu.temp_c', label: 'Temp' }],
    os:      [{ id: 'os.uptime_sec', label: 'Uptime' }],
    process: [{ id: 'proc.count', label: 'Procs' }],
};

const _OBS_CAT_META = {
    cpu:     { icon: '\uD83D\uDDA5\uFE0F', name: 'CPU',       order: 0 },
    ram:     { icon: '\uD83E\uDDE0',       name: 'RAM',       order: 1 },
    gpu:     { icon: '\uD83C\uDFAE',       name: 'GPU',       order: 2 },
    disk:    { icon: '\uD83D\uDCBE',       name: 'Disk',      order: 3 },
    net:     { icon: '\uD83C\uDF10',       name: 'Network',   order: 4 },
    os:      { icon: '\u2699\uFE0F',        name: 'OS',        order: 5 },
    process: { icon: '\uD83D\uDCCA',       name: 'Processes', order: 6 },
};

let _obsPollInterval = null;
let _obsAbort = null;
let _obsChart = null;
let _obsCatalog = null;
let _obsCategories = null;
let _obsHistory = {};
let _obsTimeLabels = [];
let _obsChartEnabled = {};
let _obsInitialized = false;

async function obsInit() {
    if (_obsInitialized) {
        _obsStartPolling();
        return;
    }

    // Lazy-load Chart.js on first use
    if (typeof Chart === 'undefined') {
        await window._loadScriptOnce('vendor/chart.umd.min.js');
    }

    _obsSetStatus('loading', 'Loading sensor catalog...');

    try {
        const [catResp, catgResp] = await Promise.all([
            fetch(bridgeApi('/api/observe/sensors'), { signal: AbortSignal.timeout(5000) }),
            fetch(bridgeApi('/api/observe/sensors/categories'), { signal: AbortSignal.timeout(5000) }),
        ]);

        if (!catResp.ok || !catgResp.ok) throw new Error('Catalog fetch failed');

        const catData = await catResp.json();
        const catgData = await catgResp.json();

        _obsCatalog = catData.sensors;
        _obsCategories = catgData.categories;

        _OBS_CHART_LINES.forEach(line => {
            _obsChartEnabled[line.id] = ['cpu.percent', 'ram.percent', 'gpu.util_percent'].includes(line.id);
        });

        _obsCatalog.forEach(s => { _obsHistory[s.id] = []; });
        _obsTimeLabels = [];

        _obsRenderCategories();
        _obsRenderChartToggles();
        _obsInitChart();

        _obsInitialized = true;
        _obsStartPolling();

    } catch (err) {
        console.error('Observe init failed:', err);
        _obsSetStatus('error', 'Failed to connect to observe API');
    }
}

function _obsStartPolling() {
    _obsFetchAndUpdate();
    if (_obsPollInterval) clearInterval(_obsPollInterval);
    _obsPollInterval = setInterval(() => {
        if (document.hidden) return;
        // Support both hub context (#mon-tab-system visible) and standalone panel (.active)
        const hubTab = document.getElementById('mon-tab-system');
        const sa = document.getElementById('panel-monitoring');
        const visible = (hubTab && hubTab.style.display !== 'none')
                     || (sa && sa.classList.contains('active'));
        if (!visible) return;
        _obsFetchAndUpdate();
    }, _OBS_POLL_MS);
    _obsSetStatus('ok', 'Live \u2014 polling every ' + (_OBS_POLL_MS / 1000) + 's');
}

function _obsStopPolling() {
    if (_obsAbort) { _obsAbort.abort(); _obsAbort = null; }
    if (_obsPollInterval) { clearInterval(_obsPollInterval); _obsPollInterval = null; }
}

async function _obsFetchAndUpdate() {
    _obsAbort = new AbortController();

    const tier = new Set(_OBS_GAUGE_IDS);
    _OBS_CHART_LINES.forEach(l => tier.add(l.id));
    // Gauge meta IDs
    ['cpu.count', 'cpu.freq_mhz', 'ram.used_gb', 'ram.total_gb',
     'gpu.temp_c', 'gpu.mem_used_mb', 'gpu.mem_total_mb',
     'disk.used_gb', 'disk.total_gb'].forEach(id => tier.add(id));
    // Peek IDs
    Object.values(_OBS_CAT_PEEK).forEach(peeks => {
        peeks.forEach(p => tier.add(p.id));
    });
    // Expanded card sensors
    document.querySelectorAll('.obs-cat-card.open').forEach(card => {
        const cat = card.dataset.category;
        if (_obsCatalog) {
            _obsCatalog.filter(s => s.category === cat).forEach(s => tier.add(s.id));
        }
    });

    const idsToRead = Array.from(tier);

    try {
        const resp = await fetch(bridgeApi('/api/observe/read'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ids: idsToRead, window_sec: 0, samples: 1 }),
            signal: _obsAbort.signal,
        });

        if (!resp.ok) throw new Error('' + resp.status);
        const data = await resp.json();
        const readings = data.readings;

        const now = new Date();
        const timeLabel = now.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
        _obsTimeLabels.push(timeLabel);
        if (_obsTimeLabels.length > _OBS_HISTORY_LEN) _obsTimeLabels.shift();

        for (const id of idsToRead) {
            if (!_obsHistory[id]) _obsHistory[id] = [];
            const val = readings[id] ? readings[id].value : null;
            _obsHistory[id].push(val);
            if (_obsHistory[id].length > _OBS_HISTORY_LEN) _obsHistory[id].shift();
        }

        _obsUpdateGauges(readings);
        _obsUpdateChart();
        _obsUpdateCategories(readings);

    } catch (err) {
        if (err.name === 'AbortError') return;
        console.error('Observe poll failed:', err);
        _obsSetStatus('error', 'Poll failed: ' + err.message);
    }
}

function _obsUpdateGauges(readings) {
    const gauges = [
        { key: 'cpu',  id: 'cpu.percent' },
        { key: 'ram',  id: 'ram.percent' },
        { key: 'gpu',  id: 'gpu.util_percent' },
        { key: 'disk', id: 'disk.percent' },
    ];

    for (const g of gauges) {
        const valEl  = document.getElementById('obs-v-' + g.key);
        const metaEl = document.getElementById('obs-m-' + g.key);
        const barEl  = document.getElementById('obs-b-' + g.key);

        const r = readings[g.id];
        if (!r) {
            if (valEl) valEl.textContent = 'N/A';
            continue;
        }

        const pct = typeof r.value === 'number' ? r.value : 0;

        if (valEl) {
            valEl.textContent = pct.toFixed(1) + '%';
            valEl.style.color = pct > 80 ? 'var(--danger)' :
                                pct > 60 ? 'var(--warning)' :
                                _OBS_COLORS[g.key];
        }

        if (barEl) {
            barEl.style.width = Math.min(pct, 100) + '%';
        }

        if (metaEl) {
            let meta = '';
            if (g.key === 'cpu') {
                const cores = readings['cpu.count'] && readings['cpu.count'].value;
                const freq = readings['cpu.freq_mhz'] && readings['cpu.freq_mhz'].value;
                if (cores) meta += cores + ' threads';
                if (freq) meta += (meta ? ' \u00b7 ' : '') + (freq / 1000).toFixed(1) + ' GHz';
            } else if (g.key === 'ram') {
                const used = readings['ram.used_gb'] && readings['ram.used_gb'].value;
                const total = readings['ram.total_gb'] && readings['ram.total_gb'].value;
                if (used != null && total != null) meta = used + ' / ' + total + ' GB';
            } else if (g.key === 'gpu') {
                const temp = readings['gpu.temp_c'] && readings['gpu.temp_c'].value;
                const memU = readings['gpu.mem_used_mb'] && readings['gpu.mem_used_mb'].value;
                const memT = readings['gpu.mem_total_mb'] && readings['gpu.mem_total_mb'].value;
                if (temp != null) meta += temp + '\u00b0C';
                if (memU != null && memT != null) meta += (meta ? ' \u00b7 ' : '') + Math.round(memU) + '/' + Math.round(memT) + ' MiB';
            } else if (g.key === 'disk') {
                const used = readings['disk.used_gb'] && readings['disk.used_gb'].value;
                const total = readings['disk.total_gb'] && readings['disk.total_gb'].value;
                if (used != null && total != null) meta = used + ' / ' + total + ' GB';
            }
            metaEl.textContent = meta;
        }
    }
}

function _obsInitChart() {
    const ctx = document.getElementById('obs-chart-canvas');
    if (!ctx || typeof Chart === 'undefined') return;

    if (_obsChart) { _obsChart.destroy(); _obsChart = null; }

    const datasets = _OBS_CHART_LINES.map(line => ({
        label: line.label,
        data: [],
        borderColor: line.color,
        backgroundColor: 'transparent',
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 4,
        tension: 0.3,
        hidden: !_obsChartEnabled[line.id],
    }));

    _obsChart = new Chart(ctx, {
        type: 'line',
        data: { labels: [], datasets: datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 400, easing: 'easeOutQuart' },
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(22, 33, 62, 0.95)',
                    titleColor: '#e8e8e8',
                    bodyColor: '#a0a0a0',
                    borderColor: '#2a2a3e',
                    borderWidth: 1,
                    cornerRadius: 6,
                    padding: 10,
                    callbacks: {
                        label: function(context) {
                            const line = _OBS_CHART_LINES[context.datasetIndex];
                            const val = context.parsed.y;
                            if (val == null) return '';
                            const unit = line.id.includes('temp') ? '\u00b0C' : '%';
                            return line.label + ': ' + val.toFixed(1) + unit;
                        }
                    }
                },
            },
            scales: {
                x: {
                    display: true,
                    ticks: { color: '#666', font: { size: 10 }, maxTicksLimit: 10, maxRotation: 0 },
                    grid: { color: 'rgba(255, 255, 255, 0.04)' },
                },
                y: {
                    display: true,
                    min: 0,
                    max: 100,
                    ticks: {
                        color: '#666', font: { size: 10 }, stepSize: 25,
                        callback: function(value) { return value + '%'; },
                    },
                    grid: { color: 'rgba(255, 255, 255, 0.04)' },
                },
            },
        },
    });
}

function _obsUpdateChart() {
    if (!_obsChart) return;
    _obsChart.data.labels = [..._obsTimeLabels];
    _OBS_CHART_LINES.forEach((line, i) => {
        const ds = _obsChart.data.datasets[i];
        ds.data = [...(_obsHistory[line.id] || [])];
        ds.hidden = !_obsChartEnabled[line.id];
    });
    _obsChart.update('none');
}

function _obsRenderChartToggles() {
    const container = document.getElementById('obs-chart-toggles');
    if (!container) return;
    container.innerHTML = _OBS_CHART_LINES.map(line => {
        const active = _obsChartEnabled[line.id] ? 'active' : '';
        const bc = _obsChartEnabled[line.id] ? line.color : 'var(--border)';
        return '<button class="obs-chart-toggle ' + active + '"'
            + ' data-obs-line="' + line.id + '"'
            + ' style="color:' + line.color + ';border-color:' + bc + ';"'
            + ' onclick="obsToggleChartLine(\'' + line.id + '\')">'
            + line.label + '</button>';
    }).join('');
}

function obsToggleChartLine(id) {
    _obsChartEnabled[id] = !_obsChartEnabled[id];
    _obsRenderChartToggles();
    _obsUpdateChart();
}

function _obsRenderCategories() {
    const container = document.getElementById('obs-categories');
    if (!container || !_obsCatalog || !_obsCategories) return;

    const cats = Object.keys(_obsCategories).sort((a, b) => {
        return (_OBS_CAT_META[a] ? _OBS_CAT_META[a].order : 99) - (_OBS_CAT_META[b] ? _OBS_CAT_META[b].order : 99);
    });

    container.innerHTML = cats.map(cat => {
        const meta = _OBS_CAT_META[cat] || { icon: '\uD83D\uDCCB', name: cat };
        const count = _obsCategories[cat];
        const color = _OBS_COLORS[cat] || '#888';
        const sensors = _obsCatalog.filter(s => s.category === cat);

        const peeks = _OBS_CAT_PEEK[cat] || [];
        const peekHtml = peeks.map(p =>
            '<span>' + p.label + ': <strong id="obs-peek-' + p.id.replace(/\./g, '-') + '">--</strong></span>'
        ).join('');

        const sensorRows = sensors.map(s =>
            '<div class="obs-sensor-row">'
            + '<span class="obs-sensor-name" title="' + _obsEsc(s.description) + '">' + _obsEsc(s.name) + '</span>'
            + '<span class="obs-sensor-val" id="obs-s-' + s.id.replace(/\./g, '-') + '">--</span>'
            + '<span class="obs-sensor-unit">' + _obsEsc(s.unit) + '</span>'
            + '</div>'
        ).join('');

        return '<div class="obs-cat-card" data-category="' + cat + '" style="border-top-color:' + color + ';">'
            + '<div class="obs-cat-header" onclick="obsToggleCard(this)">'
            +   '<div class="obs-cat-title">'
            +     '<span>' + meta.icon + '</span>'
            +     '<span>' + meta.name + '</span>'
            +     '<span class="obs-cat-badge">' + count + ' sensors</span>'
            +   '</div>'
            +   '<div style="display:flex;align-items:center;gap:12px;">'
            +     '<div class="obs-cat-peek">' + peekHtml + '</div>'
            +     '<span class="obs-cat-chevron">\u25B8</span>'
            +   '</div>'
            + '</div>'
            + '<div class="obs-cat-body">' + sensorRows + '</div>'
            + '</div>';
    }).join('');
}

function obsToggleCard(headerEl) {
    const card = headerEl.closest('.obs-cat-card');
    if (!card) return;
    card.classList.toggle('open');
    if (card.classList.contains('open')) {
        _obsFetchAndUpdate();
    }
}

function _obsUpdateCategories(readings) {
    for (const peeks of Object.values(_OBS_CAT_PEEK)) {
        for (const p of peeks) {
            const el = document.getElementById('obs-peek-' + p.id.replace(/\./g, '-'));
            if (!el) continue;
            const r = readings[p.id];
            if (!r) { el.textContent = '--'; continue; }
            el.textContent = _obsFormatValue(r.value, r.unit, p.id);
        }
    }
    for (const [id, r] of Object.entries(readings)) {
        const el = document.getElementById('obs-s-' + id.replace(/\./g, '-'));
        if (el) {
            el.textContent = _obsFormatValue(r.value, r.unit, id);
        }
    }
}

function _obsFormatValue(value, unit, id) {
    if (value == null) return '--';
    if (id === 'os.uptime_sec') {
        const h = Math.floor(value / 3600);
        const m = Math.floor((value % 3600) / 60);
        return h > 0 ? h + 'h ' + m + 'm' : m + 'm';
    }
    if (id === 'os.boot_time') {
        return new Date(value * 1000).toLocaleString();
    }
    if (unit === 'bytes') {
        if (value > 1e12) return (value / 1e12).toFixed(1) + ' TB';
        if (value > 1e9)  return (value / 1e9).toFixed(1) + ' GB';
        if (value > 1e6)  return (value / 1e6).toFixed(1) + ' MB';
        if (value > 1e3)  return (value / 1e3).toFixed(1) + ' KB';
        return value + ' B';
    }
    if (typeof value === 'number') {
        if (unit === '%') return value.toFixed(1);
        if (unit === 'count' || unit === 'cores') return Math.round(value).toString();
        return value.toFixed(1);
    }
    return String(value);
}

function _obsSetStatus(state, text) {
    const dot = document.getElementById('obs-status-dot');
    const txt = document.getElementById('obs-status-text');
    if (dot) {
        dot.style.background = state === 'ok' ? 'var(--success)' :
                               state === 'error' ? 'var(--danger)' :
                               'var(--warning)';
    }
    if (txt) txt.textContent = text;
}

function _obsEsc(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// Expose stop polling for switchPanel cleanup
window._obsStopPolling = _obsStopPolling;

window.ANCHORWORKS.ready.panel_monitoring = true;
