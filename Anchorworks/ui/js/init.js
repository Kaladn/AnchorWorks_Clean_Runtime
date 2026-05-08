// init.js — Application bootstrap (must load last)
// Extracted from anchorworks_production.js DOMContentLoaded handler

// Mobile enrollment file handler
async function handleEnrollmentFile(file) {
    const statusEl = document.getElementById('enroll-status');
    if (!file) return;
    try {
        if (statusEl) statusEl.textContent = 'Enrolling...';
        const nodeId = await AnchorWorksMobileAuth.importBundle(file);
        if (statusEl) statusEl.textContent = 'Enrolled as ' + nodeId + '! Reloading...';
        setTimeout(() => location.reload(), 1500);
    } catch (e) {
        if (statusEl) {
            statusEl.textContent = 'Error: ' + e.message;
            statusEl.style.color = '#e94560';
        }
    }
}

document.addEventListener('DOMContentLoaded', async () => {
    // Mobile enrollment check: show enrollment overlay if on mobile + no credential
    const _ua = navigator.userAgent || '';
    const _platform = navigator.platform || '';
    const _isWindowsHost = /Windows/i.test(_ua) || /^Win/i.test(_platform);
    if (window.AnchorWorksMobileAuth?.isMobile() && !_isWindowsHost) {
        const cred = await AnchorWorksMobileAuth.getCredential();
        if (!cred) {
            try {
                const authBase = window.getAuthBase?.()
                    || ANCHORWORKS_CONFIG?.llm
                    || 'http://127.0.0.1:11435';
                const status = await fetch(
                    authBase + '/api/auth/status',
                    { credentials: 'include' }
                );
                const data = await status.json();
                if (!data.authenticated) {
                    document.getElementById('enroll-overlay')?.classList.add('active');
                    return;
                }
            } catch {
                document.getElementById('enroll-overlay')?.classList.add('active');
                return;
            }
        }
    }

    // Auth gate first — app initializes only after authentication
    await window.initAuth?.();

    // Initialize theme controls (color pickers, font size, swatch highlight)
    if (typeof _initThemeControls === 'function') _initThemeControls();

    // Single consolidated boot call replaces 8+ separate API requests
    const bootData = await _fetchBoot();

    // Populate origin footer from boot payload
    const _originEl = document.getElementById('footer-origin');
    if (_originEl && bootData?.origin) {
        const commitDate = bootData.origin.commit_date ? ` (${bootData.origin.commit_date})` : '';
        _originEl.textContent = `RUNNING FROM: ${bootData.origin.workspace} | COMMIT: ${bootData.origin.commit}${commitDate}`;
    }

    // Live server health indicator in footer
    _startFooterHealth();

    window.app = new window.AnchorWorksConsole(bootData);
    window.inferenceCtrl = new window.InferenceController();
    window.inferenceCtrl.syncFromSliders = function() { this.updateLiveConfig(); }.bind(window.inferenceCtrl);

    // Load custom contract rules from localStorage
    window.loadCustomRules?.();

    // Wire up custom rules textarea to auto-save and update preview
    const customRulesTextarea = document.getElementById('ctrl-custom-rules');
    if (customRulesTextarea) {
        customRulesTextarea.addEventListener('input', window.saveCustomRules);
        customRulesTextarea.addEventListener('blur', window.saveCustomRules);
    }

    // Wire up checkboxes to update preview when changed
    ['ctrl-require-end', 'ctrl-essentials', 'ctrl-bullet-mode'].forEach(id => {
        const checkbox = document.getElementById(id);
        if (checkbox) {
            checkbox.addEventListener('change', () => {
                if (window.inferenceCtrl) window.inferenceCtrl.updateContractPreview();
            });
        }
    });

    // Help System — right-click contextual help
    window.helpInit?.();

    // Ollama warm-up — pre-load model when user focuses prompt
    const _warmTarget = document.getElementById('gpt-prompt');
    if (_warmTarget) _warmTarget.addEventListener('focus', window.ollamaWarmup);

    // Plugin card health (ongoing only — boot already set initial state)
    setInterval(() => window.checkAllPluginHealth?.(), 10000);

    console.log('AnchorWorks modules:', Object.keys(window.ANCHORWORKS?.ready || {}));
});

/**
 * Footer health: polls Bridge, LLM, Citations every 10s. Shows colored dots.
 * When Bridge transitions DOWN→UP, triggers reauth so an already-open UI
 * reconnects its session after a server restart.
 */
function _startFooterHealth() {
    const el = document.getElementById('footer-health');
    if (!el) return;

    const cfg = window.ANCHORWORKS_CONFIG || {};
    const svcs = [
        { name: 'Bridge',    url: (cfg.bridge || 'http://127.0.0.1:5050') + '/api/stats' },
        { name: 'LLM',       url: (cfg.llm    || 'http://127.0.0.1:11435') + '/health' },
        { name: 'Citations',  url: (cfg.citations || 'http://127.0.0.1:5052') + '/api/status' },
    ];

    let _prev = {};
    let _reauthPending = false;

    async function poll() {
        const results = await Promise.all(svcs.map(async s => {
            try {
                const r = await fetch(s.url, { signal: AbortSignal.timeout(3000) });
                return { name: s.name, up: r.ok };
            } catch { return { name: s.name, up: false }; }
        }));

        // Detect Bridge DOWN→UP transition → reauth
        const bridge = results.find(r => r.name === 'Bridge');
        if (bridge && bridge.up && _prev.Bridge === false && !_reauthPending) {
            _reauthPending = true;
            console.log('[health] Bridge recovered — triggering reauth');
            try {
                if (typeof initAuth === 'function') await initAuth();
            } catch (e) {
                console.warn('[health] reauth failed:', e);
            }
            _reauthPending = false;
        }

        // All services down after having been up → surface status, but do not
        // destroy or reload the UI. Operators need the page to stay put while
        // services are being restarted or investigated.
        const allDown = results.every(r => !r.up);
        const wasUp = Object.values(_prev).some(v => v === true);
        if (allDown && wasUp) {
            console.log('[health] All services down — keeping UI open');
            el.innerHTML = '<span style="color:#ef4444">All services stopped</span>';
            return;
        }

        // Store state for next cycle
        results.forEach(r => { _prev[r.name] = r.up; });

        const parts = results.map(r =>
            `<span style="color:${r.up ? '#22c55e' : '#ef4444'}" title="${r.name}: ${r.up ? 'UP' : 'DOWN'}">●</span> ${r.name}`
        );
        el.innerHTML = parts.join('&ensp;');
    }

    poll();
    setInterval(poll, 10000);
}

/**
 * Fetch /api/boot — one round-trip replaces connectToServer, checkAllPluginHealth,
 * hdrProbeAll, and fetchSystemMetrics initial calls.
 */
async function _fetchBoot() {
    const _persistBridge = (origin) => {
        try {
            if (!origin) return;
            localStorage.setItem('anchorworks_bridge_url', origin);
            if (window.ANCHORWORKS_CONFIG) {
                window.ANCHORWORKS_CONFIG.bridge = origin;
                window.ANCHORWORKS_CONFIG.ws = origin.replace(/^http/, 'ws') + '/ws/stream';
            }
        } catch (_) { /* no-op */ }
    };

    const _candidates = [];
    const _addCandidate = (origin) => {
        if (!origin || _candidates.includes(origin)) return;
        _candidates.push(origin);
    };
    const _primaryOrigin = window.ANCHORWORKS_CONFIG?.bridge || 'http://127.0.0.1:5050';
    _addCandidate(_primaryOrigin);

    // Protocol failover: fresh installs can leave UI/bridge on different schemes.
    try {
        const u = new URL(_primaryOrigin);
        const alt = new URL(_primaryOrigin);
        alt.protocol = (u.protocol === 'https:') ? 'http:' : 'https:';
        _addCandidate(alt.origin);
    } catch (_) {
        // If origin parsing fails, keep primary only.
    }

    // Port failover: recover from stale localStorage bridge URLs.
    const _host = location.hostname || '127.0.0.1';
    const _scheme = location.protocol === 'https:' ? 'https' : 'http';
    const _fallbackPorts = [5050, 8000];
    for (const p of _fallbackPorts) {
        _addCandidate(`${_scheme}://${_host}:${p}`);
        if (_host !== 'localhost') _addCandidate(`${_scheme}://localhost:${p}`);
        if (_host !== '127.0.0.1') _addCandidate(`${_scheme}://127.0.0.1:${p}`);
    }

    for (const origin of _candidates) {
        try {
            const resp = await fetch(origin + '/api/boot');
            if (!resp.ok) continue;
            const data = await resp.json();
            if (origin !== _primaryOrigin) _persistBridge(origin);
            return data;
        } catch (_) {
            // Try next candidate.
        }
    }

    return null;
}

window.ANCHORWORKS.ready.init = true;
