// panel-mapping.js -- DocuMap (dm* namespace)
// Extracted from anchorworks_production.js
if (!window.bridgeApi) console.warn('core.js not loaded before panel-mapping.js');

// ── DocuMap Constants & Polling ───────────────────────────────
const LABELS = { grove: "Data Lake", documap: "DocuMap" };

let _dmPollInterval = null;
let _dmAbort = null;
const _DM_SHELL_MODES = {
    browser: ['browser', 'topk'],
    build: ['mapping', 'intake'],
};
let _dmShell = localStorage.getItem('dm_ui_shell') || 'browser';
let _dmBrowserMode = localStorage.getItem('dm_ui_mode_browser') || 'browser';
let _dmBuildMode = localStorage.getItem('dm_ui_mode_build') || 'mapping';
let _dmUiMode = _dmShell === 'build' ? _dmBuildMode : _dmBrowserMode;
let _dmCurrentRunId = localStorage.getItem('dm_selected_run') || null;
let _dmDevice = localStorage.getItem('dm_device') || 'cpu';
let _dmCiteSyncTimer = null;

function dmToggleDevice() {
    _dmDevice = _dmDevice === 'cpu' ? 'gpu' : 'cpu';
    localStorage.setItem('dm_device', _dmDevice);
    const btn = document.getElementById('dm-device-toggle');
    const hint = document.getElementById('dm-device-hint');
    if (btn) btn.textContent = _dmDevice.toUpperCase();
    if (hint) hint.textContent = _dmDevice === 'cpu'
        ? 'CPU recommended for 6-1-6 mapping'
        : 'GPU — faster for large documents (requires CUDA)';
}

const _DM_STAT_IDS   = ['dm-stat-queued', 'dm-stat-mapped', 'dm-stat-grove-anchors', 'dm-stat-sys-anchors'];
const _DM_VALID_MODES = ['mapping', 'browser', 'topk', 'intake'];

function _dmShellDefault(shell) {
    return shell === 'build' ? 'mapping' : 'browser';
}

function _dmPersistMode() {
    localStorage.setItem('dm_ui_shell', _dmShell);
    localStorage.setItem('dm_ui_mode', _dmUiMode);
    if (_dmShell === 'build') localStorage.setItem('dm_ui_mode_build', _dmUiMode);
    else localStorage.setItem('dm_ui_mode_browser', _dmUiMode);
}

function dmSetShell(shell) {
    _dmShell = shell === 'build' ? 'build' : 'browser';
    localStorage.setItem('dm_ui_shell', _dmShell);

    const allowed = _DM_SHELL_MODES[_dmShell] || _DM_VALID_MODES;
    document.querySelectorAll('#dm-tab-bar .dm-mode-tab').forEach(tab => {
        tab.style.display = allowed.includes(tab.dataset.mode) ? '' : 'none';
    });

    const preferred = _dmShell === 'build' ? _dmBuildMode : _dmBrowserMode;
    dmSetMode(preferred);
}

function _dmSyncSelectedUi() {
    const selectedEl = document.getElementById('dm-selected-receipt');
    if (selectedEl) selectedEl.textContent = _dmCurrentRunId || 'None';
}

function _dmSetSelectedRun(runId) {
    _dmCurrentRunId = runId || null;
    if (_dmCurrentRunId) localStorage.setItem('dm_selected_run', _dmCurrentRunId);
    else localStorage.removeItem('dm_selected_run');
    _dmSyncSelectedUi();
    _dmUpdateNavButtons();
}

function dmSetMode(mode) {
    const allowed = _DM_SHELL_MODES[_dmShell] || _DM_VALID_MODES;
    _dmUiMode = allowed.includes(mode) ? mode : _dmShellDefault(_dmShell);
    if (_dmShell === 'build') _dmBuildMode = _dmUiMode;
    else _dmBrowserMode = _dmUiMode;
    _dmPersistMode();

    const mappingView = document.getElementById('dm-view-mapping');
    const browserView = document.getElementById('dm-view-browser');
    const topkView = document.getElementById('dm-view-topk');
    if (mappingView) mappingView.style.display = _dmUiMode === 'mapping' ? '' : 'none';
    if (browserView) browserView.style.display = _dmUiMode === 'browser' ? '' : 'none';
    if (topkView) topkView.style.display = _dmUiMode === 'topk' ? '' : 'none';
    const intakeView = document.getElementById('dm-view-intake');
    if (intakeView) intakeView.style.display = _dmUiMode === 'intake' ? '' : 'none';

    document.querySelectorAll('#dm-tab-bar .dm-mode-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.mode === _dmUiMode);
    });

    if (_dmUiMode === 'topk') dmLoadTopK();
}

async function dmRefreshStats() {
    // Loading state
    _DM_STAT_IDS.forEach(id => {
        const el = document.getElementById(id);
        if (el && el.textContent !== '...') el.textContent = el.textContent === '\u2014' ? '...' : el.textContent;
    });
    const banner = document.getElementById('dm-error-banner');
    if (banner) banner.style.display = 'none';

    if (_dmAbort) _dmAbort.abort();
    _dmAbort = new AbortController();

    try {
        const resp = await fetch(dmApi('/api/documap/stats'), {
            signal: AbortSignal.timeout(5000)
        });
        const data = await resp.json();

        const q = document.getElementById('dm-stat-queued');
        const m = document.getElementById('dm-stat-mapped');
        const ga = document.getElementById('dm-stat-grove-anchors');
        const sa = document.getElementById('dm-stat-sys-anchors');
        const mt = document.getElementById('dm-mapped-today');

        if (q) q.textContent = data.uploads_queued ?? 0;
        if (m) m.textContent = data.docs_mapped_total ?? 0;
        if (ga) ga.textContent = data.anchors_total_grove ?? 0;
        if (sa) sa.textContent = data.anchors_sys_verified ?? 0;
        if (mt) mt.textContent = data.mapped_today ? `${data.mapped_today} mapped today` : '';

        if (data.grove_label) LABELS.grove = data.grove_label;
        if (data.documap_label) LABELS.documap = data.documap_label;

        // Update upload status strip
        const strip = document.getElementById('dm-upload-status');
        if (strip) strip.textContent = `Queued: ${data.uploads_queued ?? 0} | Processing: ${data.uploads_processing ?? 0} | Mapped today: ${data.mapped_today ?? 0}`;
    } catch (err) {
        if (err.name === 'AbortError') return;
        console.error('DocuMap stats fetch failed:', err);
        _DM_STAT_IDS.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = '\u2014';
        });
        if (banner) banner.style.display = 'block';
    }
}

function _dmStartPolling() {
    dmRefreshStats();
    dmLoadDocs();
    _dmPollInterval = setInterval(dmRefreshStats, 5000);
}

function _dmStopPolling() {
    if (_dmAbort) { _dmAbort.abort(); _dmAbort = null; }
    if (_dmPollInterval) { clearInterval(_dmPollInterval); _dmPollInterval = null; }
}

// ── Grove Explorer ───────────────────────────────────────────
let _dmDocsCache = [];
let _dmVisibleDocs = [];
let _dmDocFilters = { query: '', sort: 'newest', relationsOnly: false, minTokens: 0, minAnchors: 0 };
let _dmDocsOffset = 0;
let _dmDocsLimit = 50;
let _dmDocsTotal = 0;

function _dmUpdateDocMeta() {
    const metaEl = document.getElementById('dm-doc-meta');
    if (!metaEl) return;
    const shown = _dmVisibleDocs.length;
    const pageCount = _dmDocsCache.length;
    const total = _dmDocsTotal || pageCount;
    const start = total > 0 ? (_dmDocsOffset + 1) : 0;
    const end = Math.min(_dmDocsOffset + pageCount, total);
    const filters = [];
    if (_dmDocFilters.relationsOnly) filters.push('relations');
    if ((_dmDocFilters.minTokens || 0) > 0) filters.push(`tokens>=${_dmDocFilters.minTokens}`);
    if ((_dmDocFilters.minAnchors || 0) > 0) filters.push(`anchors>=${_dmDocFilters.minAnchors}`);
    const filterText = filters.length ? ` | filters: ${filters.join(', ')}` : '';
    metaEl.textContent = `${shown} shown | page ${start}-${end} of ${total} | sort: ${_dmDocFilters.sort}${filterText}`;
}

function _dmUpdatePagerUi() {
    const pageEl = document.getElementById('dm-doc-page');
    const prevBtn = document.getElementById('dm-doc-page-prev');
    const nextBtn = document.getElementById('dm-doc-page-next');
    const totalPages = Math.max(1, Math.ceil((Math.max(0, _dmDocsTotal)) / _dmDocsLimit));
    const currentPage = Math.min(totalPages, Math.floor(_dmDocsOffset / _dmDocsLimit) + 1);
    if (pageEl) pageEl.textContent = `${currentPage}/${totalPages}`;
    if (prevBtn) prevBtn.disabled = _dmDocsOffset <= 0;
    if (nextBtn) nextBtn.disabled = (_dmDocsOffset + _dmDocsLimit) >= _dmDocsTotal;
}

function _dmUpdateNavButtons() {
    const prevBtn = document.getElementById('dm-prev-doc');
    const nextBtn = document.getElementById('dm-next-doc');
    if (!prevBtn || !nextBtn) return;
    const idx = _dmVisibleDocs.findIndex(d => d.receipt_id === _dmCurrentRunId);
    const hasSel = idx >= 0;
    prevBtn.disabled = !hasSel || idx <= 0;
    nextBtn.disabled = !hasSel || idx >= (_dmVisibleDocs.length - 1);
}

function _dmApplyDocFilters() {
    let docs = Array.isArray(_dmDocsCache) ? [..._dmDocsCache] : [];
    const q = (_dmDocFilters.query || '').trim().toLowerCase();
    const minTokens = Math.max(0, Number(_dmDocFilters.minTokens) || 0);
    const minAnchors = Math.max(0, Number(_dmDocFilters.minAnchors) || 0);

    if (q) {
        docs = docs.filter(d => (d.receipt_id || '').toLowerCase().includes(q));
    }
    if (minTokens > 0) {
        docs = docs.filter(d => (Number(d.total_tokens) || 0) >= minTokens);
    }
    if (minAnchors > 0) {
        docs = docs.filter(d => (Number(d.anchor_count) || 0) >= minAnchors);
    }
    if (_dmDocFilters.relationsOnly) {
        docs = docs.filter(d => !!d.has_relations);
    }

    switch (_dmDocFilters.sort) {
        case 'tokens':
            docs.sort((a, b) => (b.total_tokens || 0) - (a.total_tokens || 0) || String(b.receipt_id || '').localeCompare(String(a.receipt_id || '')));
            break;
        case 'anchors':
            docs.sort((a, b) => (b.anchor_count || 0) - (a.anchor_count || 0) || String(b.receipt_id || '').localeCompare(String(a.receipt_id || '')));
            break;
        case 'newest':
        default:
            docs.sort((a, b) => String(b.receipt_id || '').localeCompare(String(a.receipt_id || '')));
            break;
    }

    _dmRenderDocs(docs);
    if (_dmDocsCache.length > 0 && _dmCurrentRunId && !_dmVisibleDocs.some(d => d.receipt_id === _dmCurrentRunId)) {
        dmCloseDoc();
    } else {
        _dmUpdateNavButtons();
    }
}

function dmSetDocSort(sortValue) {
    _dmDocFilters.sort = ['newest', 'tokens', 'anchors'].includes(sortValue) ? sortValue : 'newest';
    _dmApplyDocFilters();
}

function dmSetRelationsOnly(enabled) {
    _dmDocFilters.relationsOnly = !!enabled;
    _dmApplyDocFilters();
}

function dmSetMinTokens(value) {
    _dmDocFilters.minTokens = Math.max(0, Number(value) || 0);
    _dmApplyDocFilters();
}

function dmSetMinAnchors(value) {
    _dmDocFilters.minAnchors = Math.max(0, Number(value) || 0);
    _dmApplyDocFilters();
}

function dmSetPageSize(value) {
    const next = Number(value);
    if (![25, 50, 100].includes(next)) return;
    if (next === _dmDocsLimit) return;
    _dmDocsLimit = next;
    _dmDocsOffset = 0;
    _dmUpdatePagerUi();
    dmLoadDocs(0);
}

function dmPage(step) {
    const delta = step < 0 ? -_dmDocsLimit : _dmDocsLimit;
    const target = Math.max(0, _dmDocsOffset + delta);
    if (target === _dmDocsOffset) return;
    if (target >= _dmDocsTotal && _dmDocsTotal > 0) return;
    dmLoadDocs(target);
}

function dmResetDocFilters() {
    _dmDocFilters = { query: '', sort: 'newest', relationsOnly: false, minTokens: 0, minAnchors: 0 };
    const searchEl = document.getElementById('dm-doc-search');
    const sortEl = document.getElementById('dm-doc-sort');
    const relEl = document.getElementById('dm-relations-only');
    const minTokEl = document.getElementById('dm-min-tokens');
    const minAnchEl = document.getElementById('dm-min-anchors');
    if (searchEl) searchEl.value = '';
    if (sortEl) sortEl.value = 'newest';
    if (relEl) relEl.checked = false;
    if (minTokEl) minTokEl.value = '0';
    if (minAnchEl) minAnchEl.value = '0';
    _dmApplyDocFilters();
}

function dmStepDoc(direction) {
    if (!_dmVisibleDocs.length) return;
    const step = direction < 0 ? -1 : 1;
    let idx = _dmVisibleDocs.findIndex(d => d.receipt_id === _dmCurrentRunId);
    if (idx < 0) {
        idx = step > 0 ? -1 : _dmVisibleDocs.length;
    }
    const nextIdx = Math.max(0, Math.min(_dmVisibleDocs.length - 1, idx + step));
    const nextDoc = _dmVisibleDocs[nextIdx];
    if (nextDoc && nextDoc.receipt_id && nextDoc.receipt_id !== _dmCurrentRunId) {
        dmViewDoc(nextDoc.receipt_id);
    }
}

async function dmLoadDocs(offset = _dmDocsOffset) {
    const listEl = document.getElementById('dm-doc-list');
    if (!listEl) return;
    listEl.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-secondary);">Loading...</div>';
    _dmDocsOffset = Math.max(0, Number(offset) || 0);
    try {
        const resp = await fetch(dmApi(`/api/documap/docs?limit=${_dmDocsLimit}&offset=${_dmDocsOffset}`), { signal: AbortSignal.timeout(5000) });
        const data = await resp.json();
        _dmDocsCache = data.docs || [];
        _dmDocsTotal = Math.max(0, Number(data.total) || 0);
        _dmApplyDocFilters();
        _dmSyncSelectedUi();
        _dmUpdatePagerUi();
    } catch (err) {
        console.error('Failed to load docs:', err);
        _dmDocsCache = [];
        _dmVisibleDocs = [];
        _dmDocsTotal = 0;
        _dmUpdatePagerUi();
        listEl.innerHTML = '<div style="text-align:center;padding:20px;color:var(--danger);">Failed to load documents</div>';
    }
}

function dmSearchDocs(query) {
    _dmDocFilters.query = query || '';
    _dmApplyDocFilters();
}

function _dmRenderDocs(docs) {
    const listEl = document.getElementById('dm-doc-list');
    if (!listEl) return;
    _dmVisibleDocs = Array.isArray(docs) ? docs : [];
    if (_dmVisibleDocs.length === 0) {
        const emptyMsg = _dmDocsCache.length > 0 ? 'No documents match current filters' : 'No documents in lake';
        listEl.innerHTML = `<div style="text-align:center;padding:40px;color:var(--text-secondary);">${emptyMsg}</div>`;
        _dmUpdateDocMeta();
        _dmUpdatePagerUi();
        _dmUpdateNavButtons();
        return;
    }
    listEl.innerHTML = _dmVisibleDocs.map(d => {
        const receiptId = String(d.receipt_id || '');
        const safeRunId = receiptId.replace(/'/g, "\\'");
        const isActive = _dmCurrentRunId === receiptId;
        const selTag = isActive ? '<span class="dm-doc-tag dm-doc-tag-sel">SEL</span>' : '';
        const relTag = d.has_relations ? '<span class="dm-doc-tag dm-doc-tag-rel">REL</span>' : '';
        return `<div class="dm-doc-row${isActive ? ' dm-doc-active' : ''}" onclick="dmViewDoc('${safeRunId}')">
            <div>
                <div class="dm-doc-row-name">${_dmEscapeHtml(receiptId)}${selTag}${relTag}</div>
                <div class="dm-doc-row-meta">${d.chunk_count ?? 0} chunks · ${d.total_tokens ?? 0} tokens</div>
            </div>
            <div class="dm-doc-row-anchors">${d.anchor_count ?? 0} ⚓</div>
        </div>`;
    }).join('');
    _dmUpdateDocMeta();
    _dmUpdatePagerUi();
    _dmUpdateNavButtons();
}

async function dmViewDoc(runId) {
    _dmSetSelectedRun(runId);
    const bodyEl = document.getElementById('dm-reconstruct-body');
    const titleEl = document.getElementById('dm-reconstruct-title');
    const badgeEl = document.getElementById('dm-reconstruct-badge');
    const statsEl = document.getElementById('dm-reconstruct-stats');
    const viewEl = document.getElementById('dm-view-browser');
    if (!bodyEl) return;

    _dmRenderDocs(_dmVisibleDocs.length ? _dmVisibleDocs : _dmDocsCache);
    bodyEl.innerHTML = '<span style="color:var(--text-secondary);">Loading...</span>';
    if (viewEl) viewEl.style.display = 'block';
    if (titleEl) titleEl.textContent = runId;
    _dmResetCloudDock('Hover a highlighted anchor to inspect context cloud.');

    try {
        const resp = await fetch(dmApi(`/api/documap/docs/${runId}/reconstruct`), { signal: AbortSignal.timeout(8000) });
        const data = await resp.json();

        if (badgeEl) badgeEl.style.display = data.lossy ? 'block' : 'none';
        if (statsEl) {
            const unknown = data.unknown_token_count ?? 0;
            statsEl.textContent = `${data.total_tokens ?? 0} tokens | ${data.anchor_count ?? 0} anchors | ${unknown} unmapped`;
        }

        // Build text with anchor highlighting
        let html = _dmEscapeHtml(data.text);
        if (data.anchors && data.anchors.length > 0) {
            const anchorWords = new Set(data.anchors.map(a => a.word.toLowerCase()));
            const anchorMap = {};
            data.anchors.forEach(a => { anchorMap[a.word.toLowerCase()] = a.hex_addr; });
            // Highlight anchor words in text
            const pattern = Array.from(anchorWords).sort((a, b) => b.length - a.length).map(_dmEscapeRegex).join('|');
            if (pattern) {
                const re = new RegExp(`\\b(${pattern})\\b`, 'gi');
                html = html.replace(re, (match) => {
                    const addr = anchorMap[match.toLowerCase()] || '';
                    return `<span class="dm-anchor" data-anchor="${_dmEscapeHtml(match.toLowerCase())}" data-addr="${addr}" style="background:rgba(var(--success-rgb,40,167,69),0.15);border-bottom:2px solid var(--success);padding:0 2px;cursor:pointer;" title="${addr}">${match}</span>`;
                });
            }
        }
        bodyEl.innerHTML = html;
    } catch (err) {
        console.error('Failed to reconstruct:', err);
        bodyEl.innerHTML = '<span style="color:var(--danger);">Failed to load document</span>';
        _dmResetCloudDock('Cloud unavailable until document loads.');
    }
}

function dmCloseDoc() {
    const bodyEl = document.getElementById('dm-reconstruct-body');
    const titleEl = document.getElementById('dm-reconstruct-title');
    const badgeEl = document.getElementById('dm-reconstruct-badge');
    const statsEl = document.getElementById('dm-reconstruct-stats');
    _dmSetSelectedRun(null);
    _dmRenderDocs(_dmVisibleDocs.length ? _dmVisibleDocs : _dmDocsCache);
    if (titleEl) titleEl.textContent = 'Select a document';
    if (badgeEl) badgeEl.style.display = 'none';
    if (statsEl) statsEl.textContent = 'Select a document from the list to inspect mapped text.';
    if (bodyEl) bodyEl.innerHTML = '<span style="color:var(--text-secondary);">No document selected.</span>';
    _dmResetCloudDock('Select a document first.');
}

function _dmEscapeHtml(s) {
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
}

function _dmEscapeRegex(s) {
    return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// ── Citation-Map Library Functions ────────────────────────────

const LIBRARY_API = (window.ANCHORWORKS_CONFIG?.llm || 'http://localhost:11435') + '/api/library';
let currentLibraryData = null;
var lastCreatedMap = null;
var lastCreatedCitationId = null;
let _dmBatchQueue = [];
let _dmBatchActive = false;

// Legacy library refresh — retained for document list rendering
// DocuMap stats are now handled by dmRefreshStats() polling

// Refresh library data
async function refreshLibrary() {
    try {
        const resp = await fetch(`${LIBRARY_API}/summary`);
        const data = await resp.json();
        currentLibraryData = data;

        // Update stats
        document.getElementById('lib-stat-docs').textContent = data.total_citations || 0;
        document.getElementById('lib-stat-maps').textContent = data.total_maps || 0;
        document.getElementById('lib-stat-anchors').textContent = data.unique_anchors || 0;

        // Render document list
        renderLibraryDocs(data.citations || []);
    } catch (error) {
        console.error('Failed to load library:', error);
        document.getElementById('library-doc-list').innerHTML = `
            <div style="text-align: center; padding: 40px; color: var(--danger);">
                Failed to load library. Is the server running?
            </div>
        `;
    }
}

// Render document list
function renderLibraryDocs(citations) {
    const listEl = document.getElementById('library-doc-list');

    if (!citations || citations.length === 0) {
        listEl.innerHTML = `
            <div style="text-align: center; padding: 40px; color: var(--text-secondary);">
                No documents yet. Upload one below!
            </div>
        `;
        return;
    }

    listEl.innerHTML = citations.map(cit => `
        <div style="
            padding: 12px;
            background: var(--accent-bg);
            border: 1px solid var(--border);
            border-radius: 4px;
            margin-bottom: 8px;
            cursor: pointer;
            transition: all 0.2s;
        " onmouseover="this.style.background='var(--highlight)'" onmouseout="this.style.background='var(--accent-bg)'" onclick="viewMapDetails('${cit.cite_id}')">
            <div style="display: flex; justify-content: space-between; align-items: start;">
                <div>
                    <div style="font-weight: 500; margin-bottom: 4px;">
                        📄 ${cit.filename}
                        ${cit.source_type === 'test' ? '<span style="font-size: 10px; background: rgba(255,215,0,0.2); color: var(--warning); padding: 2px 6px; border-radius: 3px; margin-left: 6px;">TEST</span>' : ''}
                    </div>
                    <div style="font-size: 11px; color: var(--text-secondary);">
                        ${cit.cite_id.substring(0, 20)}... • ${new Date(cit.uploaded_at).toLocaleDateString()}
                    </div>
                </div>
            </div>
        </div>
    `).join('');
}

// View map details (simple alert for now)
async function viewMapDetails(citeId) {
    try {
        const resp = await fetch(`${LIBRARY_API}/maps/${citeId}`);
        const mapData = await resp.json();

        const anchorCount = Object.keys(mapData.anchors || {}).length;
        const stats = mapData.stats || {};

        alert(`Map Details\n\n` +
              `Citation: ${mapData.cite_id}\n` +
              `Map ID: ${mapData.map_id}\n` +
              `Window Size: ${mapData.window_size}\n` +
              `Unique Anchors: ${anchorCount}\n` +
              `Total Tokens: ${stats.total_tokens || 0}\n` +
              `Lexicon Match Rate: ${(stats.lexicon_coverage * 100).toFixed(1)}%\n\n` +
              `Tip: Use "Neo4j" or "Export JSON" buttons to visualize this map in external tools.`);
    } catch (error) {
        console.error('Failed to load map:', error);
        alert('Failed to load map details');
    }
}

// SHA-256 fingerprint via Web Crypto API
async function _dmFingerprint(text) {
    const buf = new TextEncoder().encode(text);
    const hash = await crypto.subtle.digest('SHA-256', buf);
    return Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2, '0')).join('');
}

// Write event to DocuMap job ledger
async function _dmLedgerEvent(event, fingerprint, extra = {}) {
    try {
        await fetch(dmApi('/api/documap/jobs/event'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ event, fingerprint, ...extra })
        });
    } catch (e) { console.warn('Ledger write failed:', e); }
}

function _dmSetCitationResult(citeId) {
    const resultEl = document.getElementById('result-cite-id');
    const openBtn = document.getElementById('result-open-citation');
    const clean = String(citeId || '').trim();
    if (resultEl) resultEl.textContent = clean || 'Unavailable';
    if (openBtn) openBtn.disabled = !clean;
}

function dmOpenLatestCitation() {
    const citeId = String(lastCreatedCitationId || '').trim();
    if (!citeId) {
        alert('No mapped citation available yet');
        return;
    }

    window.switchPanel?.('citations');
    window.setExplorerMode?.('citations');
    window.app?.citSearch?.(citeId);
    if (window.app?.citLoadAll) {
        window.app.citLoadAll(true).catch(() => {});
    }

    let attempts = 0;
    const syncSearchUi = () => {
        const input = document.getElementById('cit-search');
        if (!input) return false;
        input.value = citeId;
        window.app?.citSearch?.(citeId);
        return true;
    };
    if (syncSearchUi()) return;

    if (_dmCiteSyncTimer) clearInterval(_dmCiteSyncTimer);
    _dmCiteSyncTimer = setInterval(() => {
        attempts += 1;
        if (syncSearchUi() || attempts >= 20) {
            clearInterval(_dmCiteSyncTimer);
            _dmCiteSyncTimer = null;
        }
    }, 120);
}

// Download last created map — fetches the full 6-1-6 map data, not just the summary stub
async function downloadLastMap() {
    if (!lastCreatedMap) {
        alert('No map to download');
        return;
    }
    try {
        const resp = await fetch(`${LIBRARY_API}/maps/${lastCreatedMap.map_id}`, {
            credentials: 'include'
        });
        if (!resp.ok) throw new Error(`Server returned ${resp.status}`);
        const fullMap = await resp.json();
        const blob = new Blob([JSON.stringify(fullMap, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${lastCreatedMap.map_id}.json`;
        a.click();
        URL.revokeObjectURL(url);
    } catch (err) {
        alert(`Download failed: ${err.message}`);
    }
}

// Handle file selection
function handleFileSelect(event) {
    const inputEl = event?.target;
    if (!inputEl) return;
    if (inputEl.id !== 'file-input') {
        if (typeof window.chatHandleFileUpload === 'function') {
            window.chatHandleFileUpload(event);
            return;
        }
        const file = inputEl.files?.[0];
        if (file) window.app?.addLog?.(`File selected: ${file.name}`, 'info');
        return;
    }

    const files = Array.from(event?.target?.files || []);
    const nameInput = document.getElementById('job-name');
    if (files.length === 1 && nameInput && !nameInput.value) {
        nameInput.value = files[0].name;
    }
    _dmPrimeBatchQueue(files);
}

function _dmSetUploadControlsDisabled(disabled) {
    const submitBtn = document.getElementById('dm-submit-btn');
    const fileInput = document.getElementById('file-input');
    if (submitBtn) submitBtn.disabled = !!disabled;
    if (fileInput) fileInput.disabled = !!disabled;
}

function _dmBatchStatusBadge(status) {
    if (status === 'processing') return '[...]';
    if (status === 'done') return '[ok]';
    if (status === 'failed') return '[x]';
    if (status === 'skipped') return '[skip]';
    return '[ ]';
}

function _dmRenderBatchQueue() {
    const queueEl = document.getElementById('dm-batch-queue');
    if (!queueEl) return;
    if (!_dmBatchQueue.length) {
        queueEl.textContent = 'Batch queue: no files selected.';
        return;
    }

    const counts = { queued: 0, processing: 0, done: 0, failed: 0, skipped: 0 };
    _dmBatchQueue.forEach(item => {
        if (counts[item.status] !== undefined) counts[item.status] += 1;
    });

    const preview = _dmBatchQueue.slice(0, 5).map(item => {
        const detail = item.detail ? ` - ${_dmEscapeHtml(item.detail)}` : '';
        return `<div style="margin-top:3px;">${_dmBatchStatusBadge(item.status)} ${_dmEscapeHtml(item.name)}${detail}</div>`;
    }).join('');
    const more = _dmBatchQueue.length > 5
        ? `<div style="margin-top:4px;">+${_dmBatchQueue.length - 5} more file(s)</div>`
        : '';

    queueEl.innerHTML = `
        <div>Batch queue: ${_dmBatchQueue.length} file(s) | queued ${counts.queued} | processing ${counts.processing} | done ${counts.done} | skipped ${counts.skipped} | failed ${counts.failed}</div>
        ${preview}
        ${more}
    `;
}

function _dmPrimeBatchQueue(files) {
    _dmBatchQueue = Array.from(files || []).map(file => ({
        name: file.name,
        status: 'queued',
        detail: ''
    }));
    _dmRenderBatchQueue();
}

async function _dmRunSingleMapping(content, filename, options = {}) {
    const duplicatePolicy = options.duplicatePolicy || 'prompt'; // prompt|skip
    const suppressAlert = !!options.suppressAlert;
    const keepInputs = !!options.keepInputs;
    const deferRefresh = !!options.deferRefresh;
    const progressPrefix = options.progressPrefix ? `${options.progressPrefix} ` : '';

    const fingerprint = await _dmFingerprint(content);
    try {
        const fpResp = await fetch(dmApi(`/api/documap/fingerprint/${fingerprint}`));
        const fpData = await fpResp.json();
        if (fpData.exists && fpData.event === 'completed') {
            if (duplicatePolicy === 'skip') return { skipped: true, reason: 'Already mapped' };
            if (!confirm('This document is already mapped. Map again?')) return { skipped: true, reason: 'Skipped by user' };
        }
    } catch (e) { /* bridge offline - proceed anyway */ }

    const progressDiv = document.getElementById('mapping-progress');
    const resultsDiv = document.getElementById('mapping-results');
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');
    const fileInput = document.getElementById('file-input');
    const textInput = document.getElementById('text-input');

    lastCreatedCitationId = null;
    _dmSetCitationResult(null);

    if (progressDiv) progressDiv.style.display = 'block';
    if (resultsDiv) resultsDiv.style.display = 'none';
    if (progressFill) progressFill.style.width = '0%';
    if (progressText) progressText.textContent = `${progressPrefix}Creating citation...`;

    await _dmLedgerEvent('queued', fingerprint, { filename });

    try {
        if (progressFill) progressFill.style.width = '30%';
        const citResp = await tracedFetch(`${LIBRARY_API}/citations/create`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content, filename, source_type: 'user' })
        });

        if (!citResp.ok) throw new Error('Citation creation failed');
        const citation = await citResp.json();
        lastCreatedCitationId = citation?.cite_id || null;

        await _dmLedgerEvent('started', fingerprint, { filename });

        if (progressFill) progressFill.style.width = '60%';
        if (progressText) progressText.textContent = `${progressPrefix}Generating 6-1-6 map...`;

        const mapResp = await tracedFetch(`${LIBRARY_API}/maps/create`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cite_id: citation.cite_id, window_size: 6, device: _dmDevice })
        });

        if (!mapResp.ok) throw new Error('Map creation failed');
        const mapData = await mapResp.json();
        lastCreatedMap = mapData;

        await _dmLedgerEvent('completed', fingerprint, { filename, run_id: mapData.run_id || '' });

        if (progressFill) progressFill.style.width = '100%';
        if (progressText) progressText.textContent = `${progressPrefix}Complete!`;
        if (progressDiv) progressDiv.style.display = 'none';
        if (resultsDiv) resultsDiv.style.display = 'block';

        const stats = mapData.stats || {};
        const tokensEl = document.getElementById('result-tokens');
        const coverageEl = document.getElementById('result-coverage');
        const unmappedEl = document.getElementById('result-unmapped');
        if (tokensEl) tokensEl.textContent = stats.total_tokens || 0;
        if (coverageEl) coverageEl.textContent = ((stats.lexicon_coverage || 0) * 100).toFixed(1) + '%';
        if (unmappedEl) unmappedEl.textContent = stats.unmapped_count || 0;
        _dmSetCitationResult(lastCreatedCitationId || mapData?.cite_id || null);

        if (!keepInputs) {
            if (fileInput) fileInput.value = '';
            if (textInput) textInput.value = '';
            const jobNameEl = document.getElementById('job-name');
            if (jobNameEl) jobNameEl.value = '';
            _dmBatchQueue = [];
            _dmRenderBatchQueue();
        }

        if (!deferRefresh) {
            dmRefreshStats();
            dmLoadDocs();
        }

        return { skipped: false, mapData, citeId: lastCreatedCitationId || mapData?.cite_id || null };
    } catch (error) {
        console.error('Mapping job failed:', error);
        await _dmLedgerEvent('failed', fingerprint, { filename, reason: error.message });
        if (progressDiv) progressDiv.style.display = 'none';
        if (!suppressAlert) alert('Mapping failed: ' + error.message);
        throw error;
    }
}

async function _dmRunBatchMappings(files) {
    const fileList = Array.from(files || []);
    if (!fileList.length) return;

    _dmBatchActive = true;
    _dmSetUploadControlsDisabled(true);
    _dmPrimeBatchQueue(fileList);
    const progressDiv = document.getElementById('mapping-progress');
    const progressText = document.getElementById('progress-text');
    const progressFill = document.getElementById('progress-fill');
    const resultsDiv = document.getElementById('mapping-results');
    if (progressDiv) progressDiv.style.display = 'block';
    if (progressText) progressText.textContent = 'Batch queued...';
    if (progressFill) progressFill.style.width = '0%';
    if (resultsDiv) resultsDiv.style.display = 'none';

    let done = 0;
    let failed = 0;
    let skipped = 0;

    for (let i = 0; i < fileList.length; i += 1) {
        const item = _dmBatchQueue[i];
        item.status = 'processing';
        item.detail = 'mapping';
        _dmRenderBatchQueue();
        if (progressDiv) progressDiv.style.display = 'block';
        if (progressText) progressText.textContent = `[${i + 1}/${fileList.length}] Preparing...`;
        if (progressFill) progressFill.style.width = `${Math.round((i / fileList.length) * 100)}%`;

        try {
            const content = await fileList[i].text();
            const result = await _dmRunSingleMapping(content, fileList[i].name, {
                progressPrefix: `[${i + 1}/${fileList.length}]`,
                duplicatePolicy: 'skip',
                suppressAlert: true,
                keepInputs: true,
                deferRefresh: true
            });
            if (result?.skipped) {
                item.status = 'skipped';
                item.detail = result.reason || 'Skipped';
                skipped += 1;
            } else {
                item.status = 'done';
                item.detail = 'mapped';
                done += 1;
            }
        } catch (error) {
            item.status = 'failed';
            item.detail = error?.message || 'Failed';
            failed += 1;
        }
        _dmRenderBatchQueue();
    }

    if (progressDiv) progressDiv.style.display = 'none';
    if (progressText) progressText.textContent = `Batch complete: ${done} mapped, ${skipped} skipped, ${failed} failed`;
    if (progressFill) progressFill.style.width = '100%';

    const fileInput = document.getElementById('file-input');
    const textInput = document.getElementById('text-input');
    const jobNameEl = document.getElementById('job-name');
    if (fileInput) fileInput.value = '';
    if (textInput) textInput.value = '';
    if (jobNameEl) jobNameEl.value = '';

    dmRefreshStats();
    dmLoadDocs();

    _dmBatchActive = false;
    _dmSetUploadControlsDisabled(false);
}

async function submitMappingJob() {
    if (_dmBatchActive) return;

    const fileInput = document.getElementById('file-input');
    const textInput = document.getElementById('text-input');
    const jobNameEl = document.getElementById('job-name');
    const files = Array.from(fileInput?.files || []);
    const jobName = (jobNameEl?.value || '').trim();

    if (files.length > 1 && (textInput?.value || '').trim()) {
        alert('Clear text input to run multi-file batch mapping.');
        return;
    }

    if (files.length > 1 && !(textInput?.value || '').trim()) {
        await _dmRunBatchMappings(files);
        return;
    }

    let content = '';
    let filename = jobName || 'document.txt';

    if (files.length === 1) {
        content = await files[0].text();
        if (!jobName) filename = files[0].name;
    } else if ((textInput?.value || '').trim()) {
        content = textInput.value.trim();
    } else {
        alert('Please provide document content');
        return;
    }

    await _dmRunSingleMapping(content, filename);
}

// ── Anchor Graph Export (fetch → download) ────────────────────
// Graph visualisation handled by external tools.
// GraphML → Gephi (gephi.org) | CSV → any network tool | JSON → custom

async function dmFetchAndExportGraph() {
    const runId = _dmCurrentRunId;
    if (!runId) { alert('No document selected'); return; }
    const btn = document.getElementById('dm-graph-btn');
    if (btn) { btn.disabled = true; btn.textContent = 'Fetching…'; }
    try {
        const resp = await fetch(dmApi(`/api/documap/docs/${runId}/graph?max_nodes=200&max_edges=1000`), { signal: AbortSignal.timeout(10000) });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        const fmt = document.getElementById('dm-export-fmt')?.value || 'graphml';
        _dmDownloadGraph(data, fmt, runId);
    } catch (err) {
        console.error('Graph export failed:', err);
        alert('Graph export failed: ' + (err.message || err));
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = 'Export Graph'; }
    }
}

function _dmDownloadGraph(data, fmt, runId) {
    const slug = String(runId || 'graph').replace(/[^a-zA-Z0-9_-]/g, '_').slice(0, 48);
    let content, filename, type;
    if (fmt === 'graphml') {
        let xml = '<?xml version="1.0" encoding="UTF-8"?>\n<graphml xmlns="http://graphml.graphdrawing.org/graphml">\n<graph edgedefault="undirected">\n';
        (data.nodes || []).forEach(n => { xml += `  <node id="${_dmEscapeHtml(String(n.data.id))}"><data key="label">${_dmEscapeHtml(String(n.data.label || n.data.id))}</data><data key="freq">${n.data.freq || 0}</data></node>\n`; });
        (data.edges || []).forEach(e => { xml += `  <edge source="${_dmEscapeHtml(String(e.data.source))}" target="${_dmEscapeHtml(String(e.data.target))}"><data key="weight">${e.data.weight || 1}</data></edge>\n`; });
        xml += '</graph>\n</graphml>';
        content = xml; filename = `${slug}.graphml`; type = 'application/xml';
    } else if (fmt === 'csv') {
        let csv = 'source,target,weight\n';
        (data.edges || []).forEach(e => { csv += `${e.data.source},${e.data.target},${e.data.weight || 1}\n`; });
        content = csv; filename = `${slug}_edges.csv`; type = 'text/csv';
    } else {
        content = JSON.stringify(data, null, 2); filename = `${slug}.json`; type = 'application/json';
    }
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
}

// Legacy export — retained for backwards compat
async function openGraphJSON() {
    if (!currentLibraryData || !currentLibraryData.maps || currentLibraryData.maps.length === 0) {
        alert('No maps available to export');
        return;
    }

    const map = currentLibraryData.maps[0];

    try {
        const resp = await fetch(`${LIBRARY_API}/maps/${map.map_id}`);
        const mapData = await resp.json();

        const blob = new Blob([JSON.stringify(mapData, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `graph_export_${map.map_id}.json`;
        a.click();
        URL.revokeObjectURL(url);

    } catch (error) {
        console.error('Export failed:', error);
        alert('Failed to export graph data');
    }
}

// ── Anchor Hover Cloud (1.5s debounced) ──────────────────────
let _hoverTimer = null;
let _hoverCache = {};
let _hoverTooltip = null;
let _dmActiveCloudKey = null;

document.addEventListener('mouseover', (e) => {
    if (!e.target.classList.contains('dm-anchor')) return;
    clearTimeout(_hoverTimer);
    _hoverTimer = setTimeout(() => _dmShowCloud(e.target), 1200);
});
document.addEventListener('mouseout', (e) => {
    if (!e.target.classList.contains('dm-anchor')) return;
    clearTimeout(_hoverTimer);
});

async function _dmShowCloud(el) {
    const anchor = el.dataset.anchor;
    const runId = _dmCurrentRunId;
    if (!anchor || !runId) return;

    const cacheKey = `${runId}:${anchor}`;
    _dmActiveCloudKey = cacheKey;
    let data = _hoverCache[cacheKey];

    if (!data) {
        _dmRenderCloudLoading(anchor);
        try {
            const resp = await fetch(dmApi(`/api/documap/anchors/${encodeURIComponent(anchor)}/cloud?receipt_id=${runId}&topk=20`), { signal: AbortSignal.timeout(5000) });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            data = await resp.json();
            _hoverCache[cacheKey] = data;
        } catch (e) {
            _dmResetCloudDock(`Cloud unavailable: ${e.message}`);
            return;
        }
    }

    if (_dmActiveCloudKey !== cacheKey) return;
    _dmRenderCloudDock(anchor, data);
}

function _dmRenderTooltip(evt, html) {
    _dmHideCloud();
    const tip = document.createElement('div');
    tip.className = 'dm-cloud-tooltip';
    tip.innerHTML = html;
    document.body.appendChild(tip);
    _hoverTooltip = tip;

    const rect = evt.target.getBoundingClientRect();
    tip.style.left = (rect.left + window.scrollX) + 'px';
    tip.style.top = (rect.bottom + window.scrollY + 6) + 'px';
}

function _dmHideCloud() {
    if (_hoverTooltip) {
        _hoverTooltip.remove();
        _hoverTooltip = null;
    }
}

function _dmCloudContentEl() {
    return document.getElementById('dm-cloud-content');
}

function _dmResetCloudDock(message = 'Hover a highlighted anchor to inspect context cloud.') {
    const contentEl = _dmCloudContentEl();
    if (!contentEl) return;
    _dmActiveCloudKey = null;
    contentEl.className = 'dm-cloud-empty';
    contentEl.textContent = message;
}

function _dmRenderCloudLoading(anchor) {
    const contentEl = _dmCloudContentEl();
    if (!contentEl) return;
    contentEl.className = 'dm-cloud-loading';
    contentEl.innerHTML = `<strong>${_dmEscapeHtml(anchor)}</strong> - loading context cloud...`;
}

function _dmRenderCloudDock(anchor, data) {
    const contentEl = _dmCloudContentEl();
    if (!contentEl) return;

    if (!data.topk || data.topk.length === 0) {
        contentEl.className = 'dm-cloud-empty';
        contentEl.innerHTML = `<strong>${_dmEscapeHtml(anchor)}</strong> - no co-occurring anchors`;
        return;
    }

    let html = `<div style="font-size:12px; margin-bottom:6px;"><strong>${_dmEscapeHtml(anchor)}</strong> - context cloud</div>`;
    data.topk.forEach(item => {
        const pct = Math.round((item.score || 0) * 100);
        html += `<div class="dm-cloud-item"><span>${_dmEscapeHtml(item.anchor || '')}</span><span>${pct}%</span></div>`;
        html += `<div class="dm-cloud-bar" style="width:${pct}%;"></div>`;
    });
    contentEl.className = '';
    contentEl.innerHTML = html;
}

if (document.getElementById('dm-tab-bar')) {
    dmSetShell(_dmShell);
}
const _dmSortEl = document.getElementById('dm-doc-sort');
if (_dmSortEl) _dmSortEl.value = _dmDocFilters.sort;
const _dmRelEl = document.getElementById('dm-relations-only');
if (_dmRelEl) _dmRelEl.checked = _dmDocFilters.relationsOnly;
const _dmMinTokEl = document.getElementById('dm-min-tokens');
if (_dmMinTokEl) _dmMinTokEl.value = String(_dmDocFilters.minTokens || 0);
const _dmMinAnchEl = document.getElementById('dm-min-anchors');
if (_dmMinAnchEl) _dmMinAnchEl.value = String(_dmDocFilters.minAnchors || 0);
const _dmLimitEl = document.getElementById('dm-doc-limit');
if (_dmLimitEl) _dmLimitEl.value = String(_dmDocsLimit);
_dmSyncSelectedUi();
_dmUpdateDocMeta();
_dmUpdatePagerUi();
_dmUpdateNavButtons();
_dmResetCloudDock(_dmCurrentRunId ? 'Hover a highlighted anchor to inspect context cloud.' : 'Select a document first.');
_dmRenderBatchQueue();

// ── Corpus Anchor Index (TopK) ────────────────────────────────
let _dmTopKAbort = null;

async function dmLoadTopK() {
    if (_dmTopKAbort) _dmTopKAbort.abort();
    _dmTopKAbort = new AbortController();

    const sortEl = document.getElementById('dm-topk-sort');
    const limitEl = document.getElementById('dm-topk-limit');
    const bodyEl = document.getElementById('dm-topk-body');
    const metaEl = document.getElementById('dm-topk-meta');

    const sort = sortEl?.value || 'cf';
    const limit = parseInt(limitEl?.value || '500', 10) || 500;

    if (bodyEl) bodyEl.innerHTML = '<span style="color:var(--text-secondary)">Loading anchor index...</span>';
    if (metaEl) metaEl.textContent = '';

    try {
        const resp = await fetch(dmApi(`/api/documap/topk?limit=${limit}&sort=${sort}`), { signal: _dmTopKAbort.signal });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();

        if (metaEl) {
            metaEl.textContent = `${(data.unique_anchors || 0).toLocaleString()} unique anchors · ${data.doc_count || 0} documents`;
        }

        if (!data.anchors || data.anchors.length === 0) {
            if (bodyEl) bodyEl.innerHTML = '<span style="color:var(--text-secondary)">No anchor data. Ingest documents to populate the index.</span>';
            return;
        }

        const maxCf = data.anchors[0]?.cf || 1;
        const rows = data.anchors.map((item, i) => {
            const pct = Math.round((item.cf / maxCf) * 100);
            return `<tr>
                <td class="dm-topk-rank">${i + 1}</td>
                <td class="dm-topk-anchor">${_dmEscapeHtml(item.anchor)}</td>
                <td class="dm-topk-num">${item.cf.toLocaleString()}</td>
                <td class="dm-topk-num">${item.df.toLocaleString()}</td>
                <td class="dm-topk-bar-cell"><div class="dm-topk-bar" style="width:${pct}%"></div></td>
            </tr>`;
        });
        if (bodyEl) bodyEl.innerHTML =
            '<table class="dm-topk-table"><thead><tr><th>#</th><th>Anchor</th><th>CF</th><th>DF</th><th class="dm-topk-bar-th"></th></tr></thead><tbody>' +
            rows.join('') + '</tbody></table>';
    } catch (e) {
        if (e.name === 'AbortError') return;
        if (bodyEl) bodyEl.innerHTML = `<span style="color:var(--error,#ff6b6b)">Load failed: ${_dmEscapeHtml(e.message)}</span>`;
    }
}

window.ANCHORWORKS.ready.panel_mapping = true;
