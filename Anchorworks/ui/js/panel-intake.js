// Intake Pipeline panel — bulk local-source 616 mapping
// Scan UI + /api/intake/scan wired (commit 2)
// Run Pipeline + WebSocket job events (commit 3)

let _intakeJobId = null;
let _intakeWs    = null;

// ── Scan ──────────────────────────────────────────────────────────────────────

function intakeScan() {
    const path = document.getElementById('intake-path-input').value.trim();
    if (!path) return;
    const mode = document.querySelector('input[name="intake-scan-mode"]:checked')?.value || 'root_only';
    const btn  = document.getElementById('intake-scan-btn');
    btn.disabled = true;
    btn.textContent = 'Scanning\u2026';

    fetch(bridgeApi('/api/intake/scan'), {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ source_path: path, scan_mode: mode }),
    })
    .then(r => r.ok ? r.json() : r.json().then(e => Promise.reject(e.detail || 'Scan failed')))
    .then(data => {
        document.getElementById('intake-count-discovered').textContent = data.discovered_paths ?? 0;
        document.getElementById('intake-count-eligible').textContent   = data.eligible_paths   ?? 0;
        document.getElementById('intake-count-skipped').textContent    = data.skipped_paths    ?? 0;
        document.getElementById('intake-scan-summary').style.display   = '';
        document.getElementById('intake-run-btn').disabled = (data.eligible_paths === 0);
        btn.disabled    = false;
        btn.textContent = 'Scan';
    })
    .catch(err => {
        console.error('[intake] scan error:', err);
        document.getElementById('intake-res-status').textContent = 'Scan error: ' + err;
        document.getElementById('intake-results').style.display  = '';
        btn.disabled    = false;
        btn.textContent = 'Scan';
    });
}

// ── Clear ─────────────────────────────────────────────────────────────────────

function intakeClear() {
    document.getElementById('intake-path-input').value            = '';
    document.getElementById('intake-scan-summary').style.display  = 'none';
    document.getElementById('intake-results').style.display       = 'none';
    document.getElementById('intake-progress-row').style.display  = 'none';
    document.getElementById('intake-run-btn').disabled            = true;
    document.getElementById('intake-run-btn').style.display       = '';
    document.getElementById('intake-cancel-btn').style.display    = 'none';
    const rootRadio = document.querySelector('input[name="intake-scan-mode"][value="root_only"]');
    if (rootRadio) rootRadio.checked = true;
    _intakeJobId = null;
    _intakeCloseWs();
}

// ── Run ───────────────────────────────────────────────────────────────────────

function intakeRun() {
    const path = document.getElementById('intake-path-input').value.trim();
    if (!path) return;
    const mode      = document.querySelector('input[name="intake-scan-mode"]:checked')?.value || 'root_only';
    const recursive = mode === 'full_directory';

    document.getElementById('intake-run-btn').style.display      = 'none';
    document.getElementById('intake-cancel-btn').style.display   = '';
    document.getElementById('intake-progress-row').style.display = '';
    document.getElementById('intake-results').style.display      = 'none';
    document.getElementById('intake-progress-fill').style.width  = '0%';
    document.getElementById('intake-progress-label').textContent = 'Starting\u2026';

    fetch(bridgeApi('/api/map_files'), {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ paths: [path], recursive, source: 'intake' }),
    })
    .then(r => r.ok ? r.json() : r.json().then(e => Promise.reject(e.detail || 'Run failed')))
    .then(data => {
        _intakeJobId = data.job_id;
        _intakeConnectWs();
    })
    .catch(err => {
        console.error('[intake] run error:', err);
        document.getElementById('intake-res-status').textContent = 'Pipeline error: ' + err;
        document.getElementById('intake-results').style.display  = '';
        _intakeResetButtons();
    });
}

// ── Cancel ────────────────────────────────────────────────────────────────────

function intakeCancel() {
    if (!_intakeJobId) return;
    // POST /api/cancel — verified endpoint (anchorworks_bridge_server.py:3285)
    fetch(bridgeApi('/api/cancel'), {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ job_id: _intakeJobId }),
    }).catch(() => {});
}

// ── WebSocket ─────────────────────────────────────────────────────────────────

function _intakeConnectWs() {
    _intakeCloseWs();
    const wsUrl = bridgeApi('').replace(/^http/, 'ws') + '/ws/stream';
    _intakeWs = new WebSocket(wsUrl);
    _intakeWs.onmessage = (ev) => {
        try { _intakeHandleEvent(JSON.parse(ev.data)); } catch (_) {}
    };
    _intakeWs.onerror = () => {
        console.error('[intake] WebSocket error');
        document.getElementById('intake-res-status').textContent = 'Connection error — pipeline may still be running';
        document.getElementById('intake-results').style.display  = '';
        _intakeResetButtons();
    };
}

// Verified event schema from anchorworks_bridge_server.py:
//   job-progress:  { evt, job_id, processed, total, current }
//   job-complete:  { evt, job_id, result_path, device }
//   job-error:     { evt, job_id, error }
//   job-cancelled: { evt, job_id }
function _intakeHandleEvent(msg) {
    // Ignore events for other jobs
    if (msg.job_id && msg.job_id !== _intakeJobId) return;

    if (msg.evt === 'job-progress') {
        const pct = msg.total > 0 ? Math.round((msg.processed / msg.total) * 100) : 0;
        document.getElementById('intake-progress-fill').style.width  = pct + '%';
        document.getElementById('intake-progress-label').textContent = `${msg.processed} / ${msg.total}`;

    } else if (msg.evt === 'job-complete') {
        _intakeResetButtons();
        _intakeCloseWs();
        document.getElementById('intake-progress-fill').style.width = '100%';
        document.getElementById('intake-res-status').textContent    = 'complete';
        document.getElementById('intake-res-progress').textContent  =
            document.getElementById('intake-progress-label').textContent;
        document.getElementById('intake-res-path').textContent      = msg.result_path || '\u2014';
        document.getElementById('intake-results').style.display     = '';

    } else if (msg.evt === 'job-error') {
        _intakeResetButtons();
        _intakeCloseWs();
        document.getElementById('intake-res-status').textContent = 'error: ' + (msg.error || 'unknown');
        document.getElementById('intake-res-path').textContent   = '\u2014';
        document.getElementById('intake-results').style.display  = '';

    } else if (msg.evt === 'job-cancelled') {
        _intakeResetButtons();
        _intakeCloseWs();
        document.getElementById('intake-res-status').textContent = 'cancelled';
        document.getElementById('intake-results').style.display  = '';
    }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function _intakeCloseWs() {
    if (_intakeWs) { _intakeWs.close(); _intakeWs = null; }
    _intakeJobId = null;
}

function _intakeResetButtons() {
    document.getElementById('intake-run-btn').style.display    = '';
    document.getElementById('intake-cancel-btn').style.display = 'none';
}
