// core.js — AnchorWorks shared infrastructure (Phase 1)
// v1.4.0
//
// Globals defined here: bridgeApi, escapeHtml, switchPanel,
// auth functions, lock screen, plugin health, ollamaWarmup.
// Every panel module depends on this file being loaded first.

window.ANCHORWORKS = window.ANCHORWORKS || {};
window.ANCHORWORKS.ready = window.ANCHORWORKS.ready || {};


// ── CSRF Protection ──
// Auto-inject X-AnchorWorks-CSRF header on all state-changing requests.
// Browsers block cross-origin custom headers without CORS preflight,
// so any attacker page's request will fail the preflight check.
(function () {
    const _origFetch = window.fetch;
    const _CSRF_METHODS = new Set(['POST', 'PUT', 'DELETE', 'PATCH']);
    window.fetch = function (input, init) {
        if (init && _CSRF_METHODS.has((init.method || 'GET').toUpperCase())) {
            init = Object.assign({}, init);
            init.headers = new Headers(init.headers || {});
            if (!init.headers.has('X-AnchorWorks-CSRF')) {
                init.headers.set('X-AnchorWorks-CSRF', '1');
            }
        }
        return _origFetch.call(this, input, init);
    };
})();


// ── Theme System ──
const _themePresets = {
    classic: {
        '--primary-bg': '#1a1a2e', '--secondary-bg': '#16213e',
        '--accent-bg': '#0f3460', '--border': '#2a2a3e',
        '--highlight': '#e94560', '--success': '#00ff88',
        '--gpt-oss': '#00d4ff', '--warning': '#ffd700',
        '--danger': '#ff4444', '--btn-primary': '#c73050',
        '--text-primary': '#e8e8e8', '--text-secondary': '#a0a0a0',
        '--lock-accent': '#ab9df2',
    },
    anchorworks: {
        '--primary-bg': '#0d1a0d', '--secondary-bg': '#132413',
        '--accent-bg': '#1a3a1a', '--border': '#1e3a1e',
        '--highlight': '#00d4aa', '--success': '#00ff88',
        '--gpt-oss': '#00d4ff', '--warning': '#ffd700',
        '--danger': '#ff4444', '--btn-primary': '#2a7a5a',
        '--text-primary': '#d4e8d4', '--text-secondary': '#7a9a7a',
        '--lock-accent': '#ab9df2',
    },
};

function _readThemeCustomColors() {
    const raw = localStorage.getItem('anchorworks-ai-custom-colors');
    if (!raw) return {};
    try {
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
            return parsed;
        }
    } catch (_) {
        // Ignore malformed storage; reset below.
    }
    localStorage.removeItem('anchorworks-ai-custom-colors');
    return {};
}

function applyPreset(name) {
    document.documentElement.dataset.theme = name === 'classic' ? '' : name;
    localStorage.setItem('anchorworks-ai-theme', name);
    // Clear custom color overrides — revert to CSS-defined preset
    Object.keys(_themePresets.classic).forEach(v => {
        document.documentElement.style.removeProperty(v);
    });
    localStorage.removeItem('anchorworks-ai-custom-colors');
    _syncPickersFromPreset(name);
    _highlightActiveSwatch(name);
}

function resetThemeColors() {
    const current = localStorage.getItem('anchorworks-ai-theme') || 'classic';
    applyPreset(current);
    // Also reset font size
    document.documentElement.style.fontSize = '';
    localStorage.removeItem('anchorworks-ai-font-size');
    const slider = document.getElementById('theme-font-size');
    const label = document.getElementById('theme-font-size-label');
    if (slider) slider.value = 13;
    if (label) label.textContent = '13px';
}

// ── User-defined theme slots (6 slots) ──
const USER_THEME_SLOTS = 6;

function _getUserThemes() {
    try {
        const raw = localStorage.getItem('anchorworks-ai-user-themes');
        if (raw) return JSON.parse(raw);
    } catch {}
    return {};
}

function saveUserTheme(slotIdx) {
    const name = prompt('Theme name:', `Custom ${slotIdx + 1}`);
    if (!name) return;
    const colors = {};
    document.querySelectorAll('.theme-color').forEach(input => {
        colors[input.dataset.var] = input.value;
    });
    const themes = _getUserThemes();
    themes[slotIdx] = { name, colors };
    localStorage.setItem('anchorworks-ai-user-themes', JSON.stringify(themes));
    _renderUserThemeSlots();
}

function loadUserTheme(slotIdx) {
    const themes = _getUserThemes();
    const slot = themes[slotIdx];
    if (!slot || !slot.colors) return;
    Object.entries(slot.colors).forEach(([v, c]) => {
        document.documentElement.style.setProperty(v, c);
    });
    localStorage.setItem('anchorworks-ai-custom-colors', JSON.stringify(slot.colors));
    _syncPickersFromCustom(slot.colors);
    _highlightActiveSwatch(null);
}

function deleteUserTheme(slotIdx) {
    const themes = _getUserThemes();
    if (!themes[slotIdx]) return;
    if (!confirm(`Delete "${themes[slotIdx].name}"?`)) return;
    delete themes[slotIdx];
    localStorage.setItem('anchorworks-ai-user-themes', JSON.stringify(themes));
    _renderUserThemeSlots();
}

function _syncPickersFromCustom(colors) {
    document.querySelectorAll('.theme-color').forEach(input => {
        const varName = input.dataset.var;
        if (colors[varName]) input.value = colors[varName];
    });
}

function _renderUserThemeSlots() {
    const container = document.getElementById('user-theme-slots');
    if (!container) return;
    const themes = _getUserThemes();
    container.innerHTML = '';
    for (let i = 0; i < USER_THEME_SLOTS; i++) {
        const slot = themes[i];
        const div = document.createElement('div');
        div.className = 'user-theme-slot';
        if (slot) {
            const preview = Object.values(slot.colors).slice(0, 5);
            div.innerHTML = `
                <div class="uts-colors">${preview.map(c => `<span style="background:${c}"></span>`).join('')}</div>
                <div class="uts-name">${slot.name}</div>
                <div class="uts-actions">
                    <button onclick="loadUserTheme(${i})" class="btn btn-sm" title="Apply">Apply</button>
                    <button onclick="deleteUserTheme(${i})" class="btn btn-sm uts-delete" title="Delete">&times;</button>
                </div>`;
        } else {
            div.innerHTML = `
                <div class="uts-empty">Empty</div>
                <button onclick="saveUserTheme(${i})" class="btn btn-sm uts-save-empty">Save Current</button>`;
            div.classList.add('empty');
        }
        container.appendChild(div);
    }
}

function setFontSize(val) {
    document.documentElement.style.fontSize = val + 'px';
    const label = document.getElementById('theme-font-size-label');
    if (label) label.textContent = val + 'px';
    localStorage.setItem('anchorworks-ai-font-size', val);
}

function _syncPickersFromPreset(name) {
    const preset = _themePresets[name] || _themePresets.classic;
    document.querySelectorAll('.theme-color').forEach(input => {
        const varName = input.dataset.var;
        if (preset[varName]) input.value = preset[varName];
    });
}

function _highlightActiveSwatch(name) {
    document.querySelectorAll('.theme-swatch').forEach(btn => {
        btn.style.borderColor = '';
        btn.style.opacity = '0.7';
    });
    const active = document.getElementById('theme-btn-' + name);
    if (active) { active.style.borderColor = 'var(--highlight)'; active.style.opacity = '1'; }
}

function _initThemeControls() {
    const theme = localStorage.getItem('anchorworks-ai-theme') || 'classic';
    document.documentElement.dataset.theme = theme === 'classic' ? '' : theme;
    // Restore custom color overrides (inline head script already applied them,
    // but we need to sync picker values)
    const custom = _readThemeCustomColors();
    if (Object.keys(custom).length > 0) {
        try {
            // Apply overrides (idempotent — head script did this too)
            Object.entries(custom).forEach(([v, c]) => {
                document.documentElement.style.setProperty(v, c);
            });
            // Sync pickers: custom value wins, else preset default
            const preset = _themePresets[theme] || _themePresets.classic;
            document.querySelectorAll('.theme-color').forEach(input => {
                const varName = input.dataset.var;
                input.value = custom[varName] || preset[varName] || '#000000';
            });
        } catch { _syncPickersFromPreset(theme); }
    } else {
        _syncPickersFromPreset(theme);
    }
    // Restore font size (head script already applied)
    const savedSize = localStorage.getItem('anchorworks-ai-font-size');
    if (savedSize) {
        const slider = document.getElementById('theme-font-size');
        const label = document.getElementById('theme-font-size-label');
        if (slider) slider.value = savedSize;
        if (label) label.textContent = savedSize + 'px';
    }
    // Wire color picker live-update events
    document.querySelectorAll('.theme-color').forEach(input => {
        const persistColor = () => {
            const varName = input.dataset.var;
            document.documentElement.style.setProperty(varName, input.value);
            const obj = _readThemeCustomColors();
            obj[varName] = input.value;
            localStorage.setItem('anchorworks-ai-custom-colors', JSON.stringify(obj));
        };
        input.addEventListener('input', persistColor);
        input.addEventListener('change', persistColor);
    });
    _highlightActiveSwatch(theme);
    _renderUserThemeSlots();
}

function setSettingsTab(tabName) {
    const tabs = ['colors', 'server', 'display', 'genesis', 'retrieval', 'lexicon-sys'];
    const active = tabs.includes(tabName) ? tabName : 'colors';
    tabs.forEach((name) => {
        const btn = document.getElementById('settings-tab-btn-' + name);
        const panel = document.getElementById('settings-tab-' + name);
        if (btn) btn.classList.toggle('active', name === active);
        if (panel) panel.classList.toggle('active', name === active);
    });
    localStorage.setItem('anchorworks-settings-tab', active);
}

function initSettingsTabs() {
    const saved = localStorage.getItem('anchorworks-settings-tab') || 'colors';
    setSettingsTab(saved);
    if (saved === 'genesis') gsRefresh();
}

// ── Genesis Settings helpers ──────────────────────────────────────────────────
async function gsRefresh() {
    const elStatus  = document.getElementById('gs-plugin-status');
    const elBlocks  = document.getElementById('gs-block-count');
    const elIngested= document.getElementById('gs-ingested');
    const elTotal   = document.getElementById('gs-total');
    const elPct     = document.getElementById('gs-pct');
    const elFill    = document.getElementById('gs-progress-fill');

    try {
        const [h, s] = await Promise.all([
            fetch(bridgeApi('/api/genesis/health'), { credentials: 'include' }).then(r => r.json()),
            fetch(bridgeApi('/api/genesis/ingestion/status'), { credentials: 'include' }).then(r => r.json()),
        ]);
        if (elStatus)  { elStatus.textContent = 'connected'; elStatus.style.color = '#00ff88'; }
        if (elBlocks)  elBlocks.textContent  = h.blocks ?? '?';
        if (s.ok) {
            const pct = s.total > 0 ? Math.round((s.INGESTED / s.total) * 100) : 0;
            if (elIngested) elIngested.textContent = s.INGESTED;
            if (elTotal)    elTotal.textContent    = s.total;
            if (elPct)      elPct.textContent      = pct + '%';
            if (elFill)     elFill.style.width     = pct + '%';
        }
    } catch (_) {
        if (elStatus) { elStatus.textContent = 'offline'; elStatus.style.color = '#e94560'; }
    }
}

async function gsReloadIndex() {
    const el = document.getElementById('gs-reload-status');
    if (el) { el.style.color = 'var(--text-secondary)'; el.textContent = 'Rebuilding index…'; }
    try {
        const res  = await fetch(bridgeApi('/api/genesis/reload'), { method: 'POST', credentials: 'include' });
        const data = await res.json();
        if (el) { el.style.color = '#00ff88'; el.textContent = `Index rebuilt — ${data.blocks} blocks, commit ${String(data.index_commit || '').slice(0, 8)}`; }
        gsRefresh();
    } catch (e) {
        if (el) { el.style.color = '#e94560'; el.textContent = `Reload failed: ${e.message}`; }
    }
}

// ── Bridge API Helper (all /api/* calls route here, never to UI :8080) ──
function bridgeApi(path) { return (window.ANCHORWORKS_CONFIG?.bridge || 'http://localhost:5050') + path; }
const dmApi = bridgeApi;  // alias for DocuMap code

// ── Trace ID (request correlation across service hops) ──────  // DEBUGWIRE:TRACE
function _traceId() {  // DEBUGWIRE:TRACE
    return (Date.now().toString(36) + Math.random().toString(36).slice(2, 8)).toUpperCase();
}
window.__lastTraceId = null;  // DEBUGWIRE:TRACE

/**
 * Fetch wrapper that stamps X-Trace-Id on every request.
 * Drop-in replacement for fetch() on traced paths.
 */
async function tracedFetch(url, options = {}) {  // DEBUGWIRE:TRACE
    const tid = _traceId();
    const headers = new Headers(options.headers || {});
    headers.set('X-Trace-Id', tid);
    window.__lastTraceId = tid;
    return fetch(url, { ...options, headers });
}


// ── HTML Escape (standalone, extracted from AnchorWorksConsole) ─────────────
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}


// ── Authentication (Windows Hello / WebAuthn) ─────────────────
let AUTH_BASE = window.ANCHORWORKS_CONFIG?.llm || 'http://localhost:11435';

function _persistAuthBase(origin) {
    if (!origin) return;
    AUTH_BASE = origin;
    try {
        localStorage.setItem('anchorworks_llm_url', origin);
        if (window.ANCHORWORKS_CONFIG) window.ANCHORWORKS_CONFIG.llm = origin;
    } catch (_) {
        // Best-effort persistence only.
    }
}

function _authCandidateOrigins() {
    const out = [];
    const add = (origin) => {
        if (!origin || out.includes(origin)) return;
        out.push(origin);
    };

    const primary = AUTH_BASE || window.ANCHORWORKS_CONFIG?.llm || 'http://localhost:11435';
    add(primary);

    try {
        const u = new URL(primary);
        const alt = new URL(primary);
        alt.protocol = u.protocol === 'https:' ? 'http:' : 'https:';
        add(alt.origin);

        const sameHostDefault = `${u.protocol}//${u.hostname}:11435`;
        add(sameHostDefault);
    } catch (_) {
        // Keep fallback list below.
    }

    const proto = location.protocol === 'https:' ? 'https' : 'http';
    add(`${proto}://localhost:11435`);
    add(`${proto}://127.0.0.1:11435`);

    return out;
}

window.getAuthBase = () => AUTH_BASE;

function _b64url(buffer) {
    return btoa(String.fromCharCode(...new Uint8Array(buffer)))
        .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
function _b64urlDecode(str) {
    str = str.replace(/-/g, '+').replace(/_/g, '/');
    while (str.length % 4) str += '=';
    return Uint8Array.from(atob(str), c => c.charCodeAt(0));
}

async function checkAuthStatus() {
    let lastError = null;
    for (const origin of _authCandidateOrigins()) {
        try {
            const r = await fetch(`${origin}/api/auth/status`, { credentials: 'include' });
            if (!r.ok) {
                lastError = new Error(`HTTP ${r.status}`);
                continue;
            }
            const data = await r.json();
            _persistAuthBase(origin);
            return data;
        } catch (e) {
            lastError = e;
        }
    }
    return {
        authenticated: false,
        has_credential: false,
        error: lastError ? lastError.message : 'Auth service unavailable',
    };
}

async function authRegister() {
    const errEl = document.getElementById('auth-error');
    errEl.style.display = 'none';
    try {
        // 1. Get registration options
        const optRes = await fetch(`${AUTH_BASE}/api/auth/register/begin`, {
            method: 'POST', credentials: 'include',
        });
        const options = await optRes.json();

        // 2. Decode challenge + user.id from base64url
        options.challenge = _b64urlDecode(options.challenge);
        options.user.id = _b64urlDecode(options.user.id);
        if (options.excludeCredentials) {
            options.excludeCredentials = options.excludeCredentials.map(c => ({
                ...c, id: _b64urlDecode(c.id),
            }));
        }

        // 3. Windows Hello prompt
        const credential = await navigator.credentials.create({ publicKey: options });

        // 4. Send response to server
        const body = {
            id: credential.id,
            rawId: _b64url(credential.rawId),
            type: credential.type,
            response: {
                attestationObject: _b64url(credential.response.attestationObject),
                clientDataJSON: _b64url(credential.response.clientDataJSON),
            },
        };
        const verifyRes = await fetch(`${AUTH_BASE}/api/auth/register/complete`, {
            method: 'POST', credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        if (!verifyRes.ok) throw new Error((await verifyRes.json()).detail);

        // Success → login
        await authLogin();
    } catch (e) {
        errEl.textContent = `Registration failed: ${e.message}`;
        errEl.style.display = 'block';
    }
}

async function authLogin() {
    const errEl = document.getElementById('auth-error');
    errEl.style.display = 'none';
    try {
        // 1. Get authentication options
        const optRes = await fetch(`${AUTH_BASE}/api/auth/login/begin`, {
            method: 'POST', credentials: 'include',
        });
        const options = await optRes.json();

        // 2. Decode
        options.challenge = _b64urlDecode(options.challenge);
        if (options.allowCredentials) {
            options.allowCredentials = options.allowCredentials.map(c => ({
                ...c, id: _b64urlDecode(c.id),
            }));
        }

        // 3. Windows Hello prompt
        const assertion = await navigator.credentials.get({ publicKey: options });

        // 4. Send to server
        const body = {
            id: assertion.id,
            rawId: _b64url(assertion.rawId),
            type: assertion.type,
            response: {
                authenticatorData: _b64url(assertion.response.authenticatorData),
                clientDataJSON: _b64url(assertion.response.clientDataJSON),
                signature: _b64url(assertion.response.signature),
                userHandle: assertion.response.userHandle
                    ? _b64url(assertion.response.userHandle) : null,
            },
        };
        const verifyRes = await fetch(`${AUTH_BASE}/api/auth/login/complete`, {
            method: 'POST', credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        if (!verifyRes.ok) throw new Error((await verifyRes.json()).detail);

        // Success → reveal app
        document.getElementById('login-gate').style.display = 'none';
        document.getElementById('app-container').style.display = '';
    } catch (e) {
        errEl.textContent = `Login failed: ${e.message}`;
        errEl.style.display = 'block';
    }
}

async function initAuth() {
    const status = await checkAuthStatus();
    const gate = document.getElementById('login-gate');
    const appEl = document.getElementById('app-container');
    const statusEl = document.getElementById('auth-status');

    if (status.error) {
        statusEl.innerHTML = `<p style="color: var(--warning);">Server not reachable. Start AnchorWorks services first.</p>`;
        return;
    }

    if (status.authenticated) {
        // Already authenticated → skip gate
        gate.style.display = 'none';
        appEl.style.display = '';
        return;
    }

    // Not authenticated → show gate, hide app (handles both first load and reauth after restart)
    gate.style.display = '';
    appEl.style.display = 'none';

    // Reset button visibility
    document.getElementById('btn-auth-register').style.display = 'none';
    document.getElementById('btn-auth-login').style.display = 'none';

    if (!status.has_credential) {
        // First time → show registration
        statusEl.innerHTML = `<p style="color: var(--text-secondary);">First time? Set up Windows Hello to secure your data.</p>`;
        document.getElementById('btn-auth-register').style.display = 'inline-block';
    } else {
        // Has credential → show login (server restarted or session expired)
        statusEl.innerHTML = `<p style="color: var(--text-secondary);">Session expired. Sign in to continue.</p>`;
        document.getElementById('btn-auth-login').style.display = 'inline-block';
    }
}

// ── End Authentication ──────────────────────────


// ── Plugin Health Checks (unified, targets Plugins page cards) ──

async function checkPluginHealth(pluginId, healthUrl) {
    const dot = document.getElementById(`prow-${pluginId}-dot`);
    const row = document.getElementById(`prow-${pluginId}`);
    if (!dot) return;
    try {
        const r = await fetch(healthUrl, { signal: AbortSignal.timeout(3000) });
        if (r.ok) {
            dot.className = 'pr-dot ok';
            if (row) row.classList.remove('disconnected');
        } else {
            dot.className = 'pr-dot down';
        }
    } catch {
        dot.className = 'pr-dot down';
    }
}

function checkAllPluginHealth() {
    const checks = [
        { id: 'lakespeak', url: bridgeApi('/api/lakespeak/status') },
    ];
    checks.forEach(c => checkPluginHealth(c.id, c.url));
}


// ── Lock Screen — auto-wake on keyboard / mouse activity ──────
let _lockClockInterval = null;

function lockUpdateClock() {
    const el = document.getElementById('lock-clock');
    if (!el) return;
    const now = new Date();
    const h = String(now.getHours()).padStart(2, '0');
    const m = String(now.getMinutes()).padStart(2, '0');
    el.textContent = `${h}:${m}`;
}

function lockWake() {
    const overlay = document.getElementById('lock-overlay');
    if (!overlay || !overlay.classList.contains('active')) return;
    if (overlay.classList.contains('lock-awake')) return;  // Already awake

    // Transition: hide splash, show unlock area
    overlay.classList.add('lock-awake');
    overlay.style.cursor = '';
    document.getElementById('lock-unlock-area').style.display = 'flex';
}

function lockGoBackToSleep() {
    const overlay = document.getElementById('lock-overlay');
    if (!overlay) return;
    overlay.classList.remove('lock-awake');
    overlay.style.cursor = 'none';
    document.getElementById('lock-unlock-area').style.display = 'none';
    document.getElementById('lock-error').style.display = 'none';
}

// Attach wake listeners (keyboard + mouse movement)
document.addEventListener('keydown', (e) => {
    const overlay = document.getElementById('lock-overlay');
    if (overlay && overlay.classList.contains('active') && !overlay.classList.contains('lock-awake')) {
        e.preventDefault();
        lockWake();
    }
});
document.addEventListener('mousemove', () => {
    const overlay = document.getElementById('lock-overlay');
    if (overlay && overlay.classList.contains('active') && !overlay.classList.contains('lock-awake')) {
        lockWake();
    }
});
document.addEventListener('click', () => {
    const overlay = document.getElementById('lock-overlay');
    if (overlay && overlay.classList.contains('active') && !overlay.classList.contains('lock-awake')) {
        lockWake();
    }
});

// Start lock clock when overlay activates
const _lockObserver = new MutationObserver(() => {
    const overlay = document.getElementById('lock-overlay');
    if (overlay && overlay.classList.contains('active')) {
        lockUpdateClock();
        if (!_lockClockInterval) {
            _lockClockInterval = setInterval(lockUpdateClock, 10000);
        }
    } else {
        if (_lockClockInterval) {
            clearInterval(_lockClockInterval);
            _lockClockInterval = null;
        }
    }
});
document.addEventListener('DOMContentLoaded', () => {
    const overlay = document.getElementById('lock-overlay');
    if (overlay) {
        _lockObserver.observe(overlay, { attributes: true, attributeFilter: ['class'] });
    }
});


// ── Ollama Warm-up (event-driven model pre-load) ─────────────────────────
let _warmLastMs = 0;
let _warmInFlight = false;

function ollamaWarmup() {
    const now = Date.now();
    if (_warmInFlight || (now - _warmLastMs) < 120000) return; // 2-min guard
    _warmInFlight = true;
    _warmLastMs = now;
    fetch(bridgeApi('/api/ollama/warmup'), { method: 'POST' })
        .catch(() => {})
        .finally(() => { _warmInFlight = false; });
}


// ── Dynamic Head Meta (per-panel title/description for Lighthouse SEO) ────

const _panelMeta = {
    "gpt-oss":         { title: "AnchorWorks — Chat",               description: "Local chat workspace with citations, block governance, and revision flow—built for deterministic debugging and controlled updates." },
    "mapping":         { title: "AnchorWorks — DocuMap",            description: "6-1-6 document mapping to measure coverage, discover unmapped anchors, and export maps for deterministic indexing and downstream governance." },
    "mapping-browser": { title: "AnchorWorks — Data Lake",          description: "Browse mapped lake documents, inspect reconstructed text, and review corpus anchor statistics without leaving the browser space." },
    "mapping-build":   { title: "AnchorWorks — Mapping",            description: "Create new 6-1-6 maps and run intake workflows for deterministic document onboarding and downstream lake indexing." },
    "lexicon":         { title: "AnchorWorks — Lexicon",            description: "Browse and inspect the lexicon, weights, and anchors that power deterministic grounding." },
    "genesis":         { title: "AnchorWorks — Genesis",            description: "Browse the AnchorWorks Genesis corpus, inspect citation blocks, and drive ingestion review from a first-class browser surface." },
    "citations":       { title: "AnchorWorks — Citations",          description: "Manage citations health, validate coordinates, and govern block-level provenance for deterministic document integrity." },
    "monitoring":      { title: "AnchorWorks — Monitoring",         description: "Real-time system telemetry, gauge charts, and per-category sensor readings for AnchorWorks infrastructure." },
    "logger-streams":  { title: "AnchorWorks — Logger Streams",     description: "Monitor logger streams, toggle safe runtime feeds, and inspect live diagnostic output without leaving the monitoring space." },
    "streams":         { title: "AnchorWorks — Data Streams",       description: "Monitor and control live data streams—GroveSync, LakeFiles, and WebSocket feeds for deterministic data ingest." },
    "inference":       { title: "AnchorWorks — Inference",          description: "Tune inference parameters—temperature, top-p, repeat penalty, and presets—for deterministic local model calls." },
    "plugins":         { title: "AnchorWorks — Plugins",            description: "Manage optional plugin surfaces and installed plugin configuration." },
    "help-center":     { title: "AnchorWorks — Help",               description: "Browse the full AnchorWorks help system, inspect deterministic guidance, and ask a constrained help assistant grounded only in authoritative help data." },
    "chat-packs":      { title: "AnchorWorks — Learning",           description: "Interactive learning packs for mastering AnchorWorks workflows, from data ingest to citation governance." },
    "control":         { title: "AnchorWorks — Model Tool Policy",  description: "Configure per-model tool access policy and inspect tool telemetry for governed model execution." },
    "connections":     { title: "AnchorWorks — Connections",        description: "Configure reasoning providers, data stream slots, and server module connectivity." },
    "routing":         { title: "AnchorWorks — Pipeline Config",     description: "Configure pipeline stages, context injection, and plugin chain settings." },
    "system-identity": { title: "AnchorWorks — Identity",           description: "View and manage the system prompt and identity configuration." },
};
const _defaultMeta = {
    title: "AnchorWorks",
    description: "AnchorWorks — local-first AI orchestration with full chain visibility: lexicon mapping, retrieval grounding, verification, reasoning, and inference control."
};

function setHeadMeta(panelName) {
    const m = _panelMeta[panelName] || _defaultMeta;
    document.title = m.title;
    let meta = document.querySelector('meta[name="description"]');
    if (!meta) {
        meta = document.createElement('meta');
        meta.name = 'description';
        document.head.appendChild(meta);
    }
    meta.setAttribute('content', m.description);
}

// ── Space & Panel Navigation ─────────────────────────────────
// Rail icons = spaces. Top tabs = panels within a space.

const SPACES = {
    workspace: {
        tabs: [
            { id: 'gpt-oss', label: '💬 Chat' },
        ],
        default: 'gpt-oss'
    },
    config: {
        tabs: [
            { id: 'system-identity', label: '🪪 Identity' },
            { id: 'inference-ctrl', label: '⚡ Inference' },
            { id: 'routing', label: '🔧 Pipeline' },
        ],
        default: 'system-identity'
    },
    browser: {
        tabs: [
            { id: 'lexicon', label: '📚 Lexicon Browser' },
            { id: 'genesis', label: '🧬 Genesis' },
            { id: 'mapping-browser', label: '🗺️ Data Lake' },
            { id: 'artifacts', label: '📦 Artifacts' },
        ],
        default: 'lexicon'
    },
    knowledge: {
        tabs: [
            { id: 'help-center', label: '❓ Help' },
            { id: 'chat-packs', label: '📋 Packs' },
        ],
        default: 'help-center'
    },
    runtime: {
        tabs: [
            { id: 'mesh', label: '🕸 Mesh' },
            { id: 'nodes', label: '🧩 Nodes' },
            { id: 'network', label: '🔗 Network' },
            { id: 'review', label: '🔌 Connections' },
        ],
        default: 'mesh'
    },
    monitoring: {
        tabs: [
            { id: 'monitoring-hub', label: '📊 Monitoring' },
            { id: 'logger-streams', label: '🪵 Logger Streams' },
        ],
        default: 'monitoring-hub'
    },
    build: {
        tabs: [
            { id: 'mapping-build', label: '🗺️ Mapping' },
            { id: 'plugins', label: '🧱 Plugins' },
            { id: 'tools', label: '🛠️ Tools' },
        ],
        default: 'mapping-build'
    },
    system: {
        tabs: [
            { id: 'settings', label: '⚙️ Settings' },
        ],
        default: 'settings'
    },
};

// Reverse lookup: panel ID → space name
const PANEL_TO_SPACE = {};
for (const [space, cfg] of Object.entries(SPACES)) {
    for (const tab of cfg.tabs) PANEL_TO_SPACE[tab.id] = space;
}

let _activeSpace = 'workspace';

function switchSpace(spaceName, targetPanel) {
    const space = SPACES[spaceName];
    if (!space) return;
    _activeSpace = spaceName;

    // Update rail highlight
    document.querySelectorAll('.rail-icon').forEach(el => {
        el.classList.toggle('active', el.dataset.space === spaceName);
    });

    // Render tabs
    const tabBar = document.getElementById('space-tabs');
    if (tabBar) {
        tabBar.innerHTML = space.tabs.map(t =>
            `<div class="space-tab" data-panel="${t.id}">${t.label}</div>`
        ).join('');

        // Bind tab clicks
        tabBar.querySelectorAll('.space-tab').forEach(tab => {
            tab.addEventListener('click', () => switchPanel(tab.dataset.panel));
        });
    }

    // Switch to target panel, or last-used (if still in this space), or default
    const validIds = new Set(space.tabs.map(t => t.id));
    const lastPanel = localStorage.getItem('space_last_' + spaceName);
    const panel = targetPanel
        || (lastPanel && validIds.has(lastPanel) ? lastPanel : null)
        || space.default;
    switchPanel(panel);
}

// ── Panel Switching (guarded init calls — safe during migration) ─────────

function switchPanel(panelName) {
    if (panelName === 'mapping') {
        panelName = _activeSpace === 'build' ? 'mapping-build' : 'mapping-browser';
    }

    // Stop polling when leaving
    window._dmStopPolling?.();
    window._obsStopPolling?.();
    window._monStopPolling?.();
    window._meshStopPolling?.();
    window._netStopPolling?.();

    // Unload lexicon from RAM when navigating away from the lexicon browser tab
    if (panelName !== 'lexicon') {
        const lexEl = document.getElementById('panel-lexicon');
        if (lexEl?.classList.contains('active')) {
            fetch(bridgeApi('/api/lexicon/unload'), { method: 'POST', credentials: 'include' }).catch(() => {});
        }
    }

    // REDIRECT: panel-citations is a legacy scaffold; canonical citations UI lives in
    // panel-lexicon explorer mode.
    const actualPanel = (panelName === 'citations' || panelName === 'genesis')
        ? 'lexicon'
        : (panelName === 'mapping-browser' || panelName === 'mapping-build' ? 'mapping' : panelName);

    // Ensure correct space is active (for direct switchPanel calls)
    const neededSpace = PANEL_TO_SPACE[panelName];
    if (neededSpace && neededSpace !== _activeSpace) {
        return switchSpace(neededSpace, panelName);
    }

    // Highlight active tab
    document.querySelectorAll('.space-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.panel === panelName);
    });

    // Activate the actual panel
    document.querySelectorAll('.content-panel').forEach(panel => {
        panel.classList.remove('active');
    });
    const panelEl = document.getElementById(`panel-${actualPanel}`);
    if (panelEl) panelEl.classList.add('active');

    // Chat panel needs outer scroll suppressed so only inner .gpt-chat scrolls
    const contentArea = document.querySelector('.content-area');
    if (contentArea) contentArea.classList.toggle('chat-active', actualPanel === 'gpt-oss');

    // Remember last panel per space
    if (neededSpace) {
        localStorage.setItem('space_last_' + neededSpace, panelName);
    }

    // Explorer mode routing — menu click is authoritative
    if (panelName === 'citations') {
        window.setExplorerMode?.('citations');
        if (window.app) {
            const chart = document.getElementById('cit-distribution-chart');
            if (chart && !chart.querySelector('div')) window.app.citUpdateExplorerStats?.();
            const grid = document.getElementById('cit-results');
            if (grid && !grid.querySelector('[onclick*="citShowDetail"]')) window.app.citLoadAll?.();
        }
    } else if (panelName === 'genesis') {
        window.setExplorerMode?.('genesis');
        window.gnInit?.();
    } else if (panelName === 'lexicon') {
        // Restore last explorer mode (lexicon, citations, or chat-history)
        const savedModeRaw = localStorage.getItem('anchorworks_explorer_mode') || 'lexicon';
        const savedMode = savedModeRaw === 'genesis' ? 'lexicon' : savedModeRaw;
        window.setExplorerMode?.(savedMode);
        if (savedMode === 'lexicon' && window.app) {
            window.app.updateLexiconStats?.();
            const results = document.getElementById('lexicon-results');
            if (results && !results.querySelector('[onclick*="lexShowDetail"]')) window.app.lexBrowseRandom?.();
        } else if (savedMode === 'citations' && window.app) {
            const chart = document.getElementById('cit-distribution-chart');
            if (chart && !chart.querySelector('div')) window.app.citUpdateExplorerStats?.();
            const grid = document.getElementById('cit-results');
            if (grid && !grid.querySelector('[onclick*="citShowDetail"]')) window.app.citLoadAll?.();
        } else if (savedMode === 'chat-history') {
            window._loadBrowserChatDays?.();
        } else if (savedMode === 'genesis') {
            window.gnInit?.();
        } else if (savedMode === 'spell-check') {
            window.spellRefreshQueue?.();
        }
    } else if (panelName === 'mapping-browser') {
        window.dmSetShell?.('browser');
    } else if (panelName === 'mapping-build') {
        window.dmSetShell?.('build');
    }

    // Panel-specific load hooks (guarded for migration safety)
    if (panelName === 'plugins') window.loadPlugins?.();
    // 'streams' panel retired — init hooks removed
    if (panelName === 'mapping-browser' || panelName === 'mapping-build') window._dmStartPolling?.();
    if (panelName === 'system-identity') window.loadSystemPrompt?.();
    if (panelName === 'routing') window.drInit?.();
    if (panelName === 'help-center') window.hcInit?.();
    if (panelName === 'chat-packs') window.cpInit?.();
    if (panelName === 'monitoring') window.obsInit?.();
    if (panelName === 'monitoring-hub') window.monInit?.();
    if (panelName === 'mesh') window.meshInit?.();
    if (panelName === 'network') window.netInit?.();
    if (panelName === 'nodes') window.nodesInit?.();
    if (panelName === 'artifacts') window.afInit?.();
    if (panelName === 'tools') {
        window.ctrlInit?.();
        window.twInit?.();
    }
    if (panelName === 'logger-streams') window.cpLoggerInit?.();
    if (panelName === 'settings') { initSettingsTabs(); window.scfgInit?.(); }

    setHeadMeta(panelName);

    // Close sidebar on mobile after switching
    closeSidebar();
}

// Open the lexicon browser directly to unmatched words from mapping result cards.
function openLexiconUnmatchedFromMapCard() {
    switchPanel('lexicon');
    let attempts = 0;
    const openUnmatched = () => {
        attempts += 1;
        window.setExplorerMode?.('lexicon');
        if (window.app?.lexShowUnmatched) {
            window.app.lexShowUnmatched();
            return;
        }
        if (attempts < 8) {
            window.setTimeout(openUnmatched, 80);
        }
    };
    window.setTimeout(openUnmatched, 120);
}

function handleFileSelect(event) {
    const file = event.target.files[0];
    if (file) {
        window.app?.addLog?.(`File selected: ${file.name}`, 'info');
    }
}


// ── Lazy script loader (used by panels that need vendored libs) ──
window._loadScriptOnce = (function () {
    const loaded = new Map();
    return function loadScriptOnce(src) {
        if (loaded.has(src)) return loaded.get(src);
        const p = new Promise((resolve, reject) => {
            const s = document.createElement('script');
            s.src = src;
            s.async = true;
            s.onload = () => resolve(true);
            s.onerror = () => {
                loaded.delete(src);
                reject(new Error('Failed to load script: ' + src));
            };
            document.head.appendChild(s);
        });
        loaded.set(src, p);
        return p;
    };
})();

// ── Mobile sidebar toggle (hamburger, responsive) ──
function toggleSidebar() {
    document.querySelector('.sidebar')?.classList.toggle('open');
}
function closeSidebar() {
    document.querySelector('.sidebar')?.classList.remove('open');
}
// Close sidebar when clicking outside on mobile
document.addEventListener('click', (e) => {
    const sidebar = document.querySelector('.sidebar');
    const hamburger = document.getElementById('hamburger-btn');
    if (sidebar?.classList.contains('open') &&
        !sidebar.contains(e.target) && !hamburger?.contains(e.target)) {
        closeSidebar();
    }
});
// Auto-collapse on resize
window.addEventListener('resize', () => {
    if (window.innerWidth > 768) closeSidebar();
});

// Unload lexicon when the browser tab/window closes — sendBeacon works during unload
window.addEventListener('beforeunload', () => {
    navigator.sendBeacon(bridgeApi('/api/lexicon/unload'));
});

// ── Mobile enrollment auth (Ed25519 signed requests) ──
window.AnchorWorksMobileAuth = {
    DB_NAME: 'AnchorWorks_Mobile',
    STORE: 'credentials',
    isMobile() {
        const ua = navigator.userAgent || '';
        const platform = navigator.platform || '';
        const maxTouch = navigator.maxTouchPoints || 0;
        const mobileUa = /Android|iPhone|iPad|iPod|Mobile/i.test(ua);
        // iPadOS can report as MacIntel while still being a touch-only mobile device.
        const iPadDesktopUa = platform === 'MacIntel' && maxTouch > 1;
        return mobileUa || iPadDesktopUa;
    },
    async _db() {
        return new Promise((resolve, reject) => {
            const req = indexedDB.open(this.DB_NAME, 1);
            req.onupgradeneeded = () => req.result.createObjectStore(this.STORE);
            req.onsuccess = () => resolve(req.result);
            req.onerror = () => reject(req.error);
        });
    },
    async getCredential() {
        try {
            const db = await this._db();
            return new Promise((resolve) => {
                const tx = db.transaction(this.STORE, 'readonly');
                const req = tx.objectStore(this.STORE).get('active');
                req.onsuccess = () => resolve(req.result || null);
                req.onerror = () => resolve(null);
            });
        } catch { return null; }
    },
    async importBundle(file) {
        const text = await file.text();
        const bundle = JSON.parse(text);
        if (!bundle.node_id || !bundle.ed25519_private_key || !bundle.enrollment_token) {
            throw new Error('Invalid enrollment bundle');
        }
        // Send enrollment credential + public key to server
        const resp = await fetch(
            (bundle.server_url || ANCHORWORKS_CONFIG.bridge) + '/api/nodes/pair/enroll',
            {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    enrollment_token: bundle.enrollment_token,
                    public_key: bundle.ed25519_public_key,
                }),
            }
        );
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.error || 'Enrollment failed');
        }
        // Store credential in IndexedDB
        const db = await this._db();
        await new Promise((resolve, reject) => {
            const tx = db.transaction(this.STORE, 'readwrite');
            tx.objectStore(this.STORE).put({
                node_id: bundle.node_id,
                private_key: bundle.ed25519_private_key,
                public_key: bundle.ed25519_public_key,
                server_url: bundle.server_url,
                ui_url: bundle.ui_url,
                enrolled_at: Date.now(),
            }, 'active');
            tx.oncomplete = () => resolve();
            tx.onerror = () => reject(tx.error);
        });
        return bundle.node_id;
    }
};

window.ANCHORWORKS.ready.core = true;
