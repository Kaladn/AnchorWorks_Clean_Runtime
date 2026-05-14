/**
 * panel-settings-config.js
 *
 * Handles the settings tabs that expose variables not already visible
 * anywhere else in the UI:
 *
 *   "Retrieval"          — all LakeSpeak service config
 *   "Lexicon & System"   — topK, window, min_len, gpu, log_level, auth flags
 *
 * Does NOT touch anything already in the pipeline panel or inference panel.
 */

(function () {
    'use strict';

    let _initialized = false;

    window.scfgInit = async function scfgInit() {
        if (_initialized) return;
        _initialized = true;
        try {
            const [lsConfig, sysExtra, bridgeCfg] = await Promise.all([
                _get('/api/lakespeak/config'),
                _get('/api/config/extra'),
                _get('/api/config'),
            ]);
            _populateRetrieval(lsConfig);
            _populateLexiconSys(sysExtra, bridgeCfg.config || {});
        } catch (err) {
            console.error('[settings-config] init failed:', err);
        }
    };

    // ── Populate ──────────────────────────────────────────────────────────

    function _populateRetrieval(cfg) {
        _set('scfg-chunk-size',    cfg.chunk_size    ?? 512);
        _set('scfg-chunk-overlap', cfg.chunk_overlap ?? 64);
        _set('scfg-bm25-topk',    cfg.bm25_topk     ?? 20);
        _set('scfg-dense-topk',   cfg.dense_topk    ?? 20);
        _set('scfg-final-topk',   cfg.final_topk    ?? 5);
        _set('scfg-ollama-timeout', cfg.ollama_timeout ?? 120);
        _setRange('scfg-bm25-weight',   'scfg-bm25w-val',   cfg.bm25_weight   ?? 0.4);
        _setRange('scfg-dense-weight',  'scfg-densew-val',  cfg.dense_weight  ?? 0.6);
        _setRange('scfg-anchor-weight', 'scfg-anchorw-val', cfg.anchor_weight ?? 0.3);
        _set('scfg-ls-min-score', cfg.min_score ?? 0.01);
        _setChk('scfg-dense-enabled', cfg.dense_enabled !== false);
    }

    function _populateLexiconSys(extra, bridgeCfg) {
        _set('scfg-topk',    bridgeCfg.topK   ?? 10);
        _set('scfg-window',  bridgeCfg.window  ?? 6);
        _set('scfg-min-len', bridgeCfg.min_len ?? 5);
        const gpuMode = String(bridgeCfg.gpu || 'cpu').toLowerCase();
        const gpuEnabled = gpuMode !== 'cpu';
        _setChk('scfg-gpu-enabled', gpuEnabled);
        _set('scfg-gpu', gpuEnabled ? gpuMode : 'auto');
        _gpuToggleUi(gpuEnabled);
        _set('scfg-log-level', extra.log_level || 'info');
        _setChk('scfg-require-hello', extra.anchorworks_node_require_hello !== false);
        _setChk('scfg-require-auth',  extra.network_require_auth      === true);
    }

    // ── Save handlers (called from HTML onclick) ───────────────────────────

    window.scfgSaveRetrieval = async function () {
        const statusEl = document.getElementById('scfg-status-retrieval');
        try {
            const body = {
                chunk_size:    parseInt(_val('scfg-chunk-size'))    || 512,
                chunk_overlap: parseInt(_val('scfg-chunk-overlap')) || 64,
                bm25_topk:     parseInt(_val('scfg-bm25-topk'))    || 20,
                dense_topk:    parseInt(_val('scfg-dense-topk'))   || 20,
                final_topk:    parseInt(_val('scfg-final-topk'))   || 5,
                ollama_timeout: parseFloat(_val('scfg-ollama-timeout')) || 120,
                bm25_weight:   parseFloat(document.getElementById('scfg-bm25-weight')?.value  ?? 0.4),
                dense_weight:  parseFloat(document.getElementById('scfg-dense-weight')?.value ?? 0.6),
                anchor_weight: parseFloat(document.getElementById('scfg-anchor-weight')?.value ?? 0.3),
                min_score:     parseFloat(_val('scfg-ls-min-score')) || 0.01,
                dense_enabled: document.getElementById('scfg-dense-enabled')?.checked ?? true,
            };
            const res = await _patch('/api/lakespeak/config', body);
            if (res.ok) {
                _status(statusEl, '✓ Saved — restart server to apply', 'warning');
            } else {
                const errs = res.detail?.errors || [JSON.stringify(res.detail || res)];
                _status(statusEl, '✗ ' + errs.join('; '), 'danger');
            }
        } catch (e) { _status(statusEl, '✗ ' + e.message, 'danger'); }
    };

    window.scfgSaveLexiconSys = async function () {
        const statusEl = document.getElementById('scfg-status-lexicon-sys');
        try {
            const gpuEnabled = document.getElementById('scfg-gpu-enabled')?.checked ?? false;
            const gpuRequested = String(_val('scfg-gpu') || 'auto').toLowerCase();
            const gpu = gpuEnabled
                ? (gpuRequested === 'cuda' || gpuRequested === 'rocm' ? gpuRequested : 'auto')
                : 'cpu';

            // Bridge fields (live applied via existing /api/config PATCH)
            const bridgePayload = {
                topK:    parseInt(_val('scfg-topk'))    || 10,
                window:  parseInt(_val('scfg-window'))  || 6,
                min_len: parseInt(_val('scfg-min-len')) || 0,
                gpu,
            };
            // Extra system fields (log_level, auth flags)
            const extraPayload = {
                log_level:                  _val('scfg-log-level') || 'info',
                anchorworks_node_require_hello:  document.getElementById('scfg-require-hello')?.checked ?? true,
                network_require_auth:       document.getElementById('scfg-require-auth')?.checked  ?? false,
            };

            const [r1, r2] = await Promise.all([
                _patch('/api/config', bridgePayload),
                _patch('/api/config/extra', extraPayload),
            ]);

            const bothOk = r1.config !== undefined || r1.ok;  // /api/config returns {config, stats}
            if (bothOk && r2.ok) {
                _status(statusEl, '✓ Saved', 'success');
            } else {
                _status(statusEl, '✗ One or more saves failed', 'danger');
            }
        } catch (e) { _status(statusEl, '✗ ' + e.message, 'danger'); }
    };

    window.scfgOnGpuToggle = function scfgOnGpuToggle(checked) {
        _gpuToggleUi(!!checked);
    };

    // ── Helpers ────────────────────────────────────────────────────────────

    async function _get(path) {
        const r = await fetch(bridgeApi(path), { credentials: 'include' });
        return r.json();
    }
    async function _patch(path, body) {
        const r = await fetch(bridgeApi(path), {
            method: 'PATCH', credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        return r.json();
    }

    function _val(id) {
        return document.getElementById(id)?.value ?? '';
    }
    function _set(id, val) {
        const el = document.getElementById(id);
        if (el) el.value = val;
    }
    function _setChk(id, checked) {
        const el = document.getElementById(id);
        if (el) el.checked = !!checked;
    }
    function _setRange(sliderId, displayId, val) {
        const slider  = document.getElementById(sliderId);
        const display = document.getElementById(displayId);
        if (slider)  slider.value = val;
        if (display) display.textContent = parseFloat(val).toFixed(2);
    }
    function _status(el, text, level) {
        if (!el) return;
        const c = { success: 'var(--success)', warning: 'var(--warning)', danger: 'var(--danger)' };
        el.style.color = c[level] || 'var(--text-secondary)';
        el.textContent = text;
        if (level === 'success') setTimeout(() => { if (el.textContent === text) el.textContent = ''; }, 4000);
    }

    function _gpuToggleUi(enabled) {
        const sel = document.getElementById('scfg-gpu');
        if (sel) {
            sel.disabled = !enabled;
            sel.style.opacity = enabled ? '1' : '0.6';
        }
        const hint = document.getElementById('scfg-gpu-hint');
        if (hint) {
            hint.textContent = enabled
                ? 'Bridge GPU compute is enabled. Use with known-good drivers only.'
                : 'Bridge GPU compute is disabled. CPU-first mode is active.';
        }
    }

}());
