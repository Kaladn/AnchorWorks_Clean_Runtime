// config.js — AnchorWorks URL bootstrap (loaded before all other scripts)
// v1.4.0
//
// Auto-derives server URLs from the browser's location.hostname,
// so the same page works on localhost AND on 192.168.x.x (mobile nodes).
// Override any URL via localStorage for dev/testing.

function _normalizeServiceUrl(storageKey, fallbackUrl) {
    let raw = (localStorage.getItem(storageKey) || fallbackUrl || '').trim();
    if (!raw) raw = fallbackUrl;

    try {
        const parsed = new URL(raw, location.origin);
        // If UI is HTTPS, stale HTTP overrides break service calls; auto-upgrade.
        if (location.protocol === 'https:' && parsed.protocol === 'http:') {
            parsed.protocol = 'https:';
            localStorage.setItem(storageKey, parsed.origin);
        }
        return parsed.origin;
    } catch (_) {
        return fallbackUrl;
    }
}

window.ANCHORWORKS_CONFIG = {
    bridge:    _normalizeServiceUrl('anchorworks_bridge_url',    `${location.protocol}//${location.hostname}:5050`),
    llm:       _normalizeServiceUrl('anchorworks_llm_url',       `${location.protocol}//${location.hostname}:11435`),
    reasoning: _normalizeServiceUrl('anchorworks_reasoning_url', `${location.protocol}//${location.hostname}:5051`),
    citations: _normalizeServiceUrl('anchorworks_citations_url', `${location.protocol}//${location.hostname}:5052`),
    ui:        _normalizeServiceUrl('anchorworks_ui_url',        location.origin),
};

// WebSocket URL: derived from bridge, protocol-aware
window.ANCHORWORKS_CONFIG.ws = localStorage.getItem('anchorworks_ws_url') ||
    ANCHORWORKS_CONFIG.bridge.replace(/^http/, 'ws') + '/ws/stream';
