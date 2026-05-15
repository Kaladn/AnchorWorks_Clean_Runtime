/**
 * genesis-cite.js — Genesis Citation Drawer
 *
 * Intercepts CITE:G-XXXX patterns in rendered chat text.
 * On click: fetches /api/genesis/cite/{tag} (Bridge port 5050) and
 * renders an inline citation drawer with full block details.
 *
 * Pattern matched: CITE:G-0001 through CITE:G-9999
 * Contract: READ_ONLY. No writes. Zero side-effects on chat state.
 */

(function () {
    'use strict';

    const GENESIS_TAG_RE = /CITE:(G-\d{4})\b/g;
    const GENESIS_BASE = window.ANCHORWORKS_CONFIG?.bridge || 'http://localhost:5050';

    // ── Drawer singleton ──────────────────────────────────────────────────────

    let _drawerEl = null;
    let _drawerTagEl = null;
    let _drawerTitleEl = null;
    let _drawerSourceEl = null;
    let _drawerCommitEl = null;
    let _drawerSnippetEl = null;
    let _drawerBodyEl = null;
    let _drawerExpandBtn = null;
    let _drawerSpinnerEl = null;
    let _drawerErrorEl = null;
    let _expandedState = false;

    function _ensureDrawer() {
        if (_drawerEl) return;

        const el = document.createElement('div');
        el.id = 'genesis-cite-drawer';
        el.setAttribute('role', 'dialog');
        el.setAttribute('aria-modal', 'false');
        el.setAttribute('aria-label', 'Genesis Citation');
        el.innerHTML = `
<div class="gc-drawer-inner">
  <div class="gc-header">
    <span class="gc-tag-badge" id="gc-tag"></span>
    <span class="gc-title" id="gc-title"></span>
    <button class="gc-close-btn" onclick="genesisCite.closeDrawer()" aria-label="Close">✕</button>
  </div>
  <div class="gc-meta">
    <span class="gc-meta-item"><span class="gc-meta-label">Source</span><span id="gc-source"></span></span>
    <span class="gc-meta-item"><span class="gc-meta-label">Commit</span><span id="gc-commit" style="font-family:monospace;font-size:11px;"></span></span>
  </div>
  <div id="gc-spinner" class="gc-spinner">Loading…</div>
  <div id="gc-error" class="gc-error" style="display:none;"></div>
  <div id="gc-snippet" class="gc-snippet" style="display:none;"></div>
  <div id="gc-body" class="gc-body" style="display:none;"></div>
  <div class="gc-footer">
    <button id="gc-expand-btn" class="gc-expand-btn" onclick="genesisCite.toggleExpand()" style="display:none;">
      Show full block ▾
    </button>
  </div>
</div>`;

        // Inject styles inline (avoids extra CSS file dependency)
        const style = document.createElement('style');
        style.textContent = `
#genesis-cite-drawer {
  position: fixed;
  bottom: 80px;
  right: 20px;
  width: 420px;
  max-width: calc(100vw - 40px);
  max-height: 70vh;
  background: var(--panel-bg, #1a1a2e);
  border: 1px solid #00d4ff44;
  border-radius: 10px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6), 0 0 0 1px #00d4ff22;
  z-index: 9500;
  display: none;
  flex-direction: column;
  overflow: hidden;
}
#genesis-cite-drawer.gc-visible { display: flex; }
.gc-drawer-inner { display: flex; flex-direction: column; height: 100%; }
.gc-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px 8px;
  border-bottom: 1px solid #00d4ff22;
  flex-shrink: 0;
}
.gc-tag-badge {
  background: linear-gradient(135deg, #00d4ff, #0099cc);
  color: #000;
  font-weight: 700;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  white-space: nowrap;
  flex-shrink: 0;
}
.gc-title {
  flex: 1;
  color: var(--text-primary, #e0e0e0);
  font-size: 13px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.gc-close-btn {
  background: none;
  border: none;
  color: var(--text-secondary, #888);
  cursor: pointer;
  font-size: 14px;
  padding: 2px 6px;
  border-radius: 4px;
  flex-shrink: 0;
}
.gc-close-btn:hover { background: rgba(255,255,255,0.08); color: var(--text-primary, #e0e0e0); }
.gc-meta {
  display: flex;
  gap: 12px;
  padding: 6px 12px;
  border-bottom: 1px solid #00d4ff11;
  flex-shrink: 0;
}
.gc-meta-item { display: flex; flex-direction: column; gap: 1px; }
.gc-meta-label { font-size: 9px; text-transform: uppercase; color: #00d4ff99; letter-spacing: 0.05em; }
.gc-meta-item > span:last-child { font-size: 11px; color: var(--text-secondary, #aaa); }
.gc-spinner { padding: 16px 12px; color: var(--text-secondary, #888); font-size: 12px; }
.gc-error { padding: 12px; color: #e94560; font-size: 12px; }
.gc-snippet {
  padding: 10px 12px;
  font-size: 12px;
  color: var(--text-primary, #d0d0d0);
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
  flex-shrink: 0;
}
.gc-body {
  padding: 10px 12px;
  font-size: 11px;
  color: var(--text-secondary, #aaa);
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-y: auto;
  flex: 1;
}
.gc-footer {
  padding: 6px 12px;
  border-top: 1px solid #00d4ff11;
  flex-shrink: 0;
}
.gc-expand-btn {
  background: none;
  border: 1px solid #00d4ff33;
  color: #00d4ff;
  font-size: 11px;
  cursor: pointer;
  padding: 4px 10px;
  border-radius: 4px;
}
.gc-expand-btn:hover { background: rgba(0,212,255,0.08); }

/* Badge in chat text */
.genesis-cite-badge {
  display: inline-block;
  background: rgba(0, 212, 255, 0.12);
  border: 1px solid #00d4ff44;
  color: #00d4ff;
  font-size: 10px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 3px;
  cursor: pointer;
  vertical-align: middle;
  margin: 0 2px;
  transition: background 0.15s;
}
.genesis-cite-badge:hover {
  background: rgba(0, 212, 255, 0.25);
  border-color: #00d4ff99;
}
`;

        document.head.appendChild(style);
        document.body.appendChild(el);
        _drawerEl = el;
        _drawerTagEl = document.getElementById('gc-tag');
        _drawerTitleEl = document.getElementById('gc-title');
        _drawerSourceEl = document.getElementById('gc-source');
        _drawerCommitEl = document.getElementById('gc-commit');
        _drawerSnippetEl = document.getElementById('gc-snippet');
        _drawerBodyEl = document.getElementById('gc-body');
        _drawerExpandBtn = document.getElementById('gc-expand-btn');
        _drawerSpinnerEl = document.getElementById('gc-spinner');
        _drawerErrorEl = document.getElementById('gc-error');
    }

    // ── Public API ────────────────────────────────────────────────────────────

    const genesisCite = {

        /**
         * Replace CITE:G-XXXX patterns in escaped HTML with clickable badge spans.
         * @param {string} escapedHtml  — already HTML-escaped text
         * @returns {string} HTML with genesis cite badges substituted in
         */
        renderBadges(escapedHtml) {
            return escapedHtml.replace(GENESIS_TAG_RE, (_, tag) =>
                `<span class="genesis-cite-badge" data-genesis-tag="${tag}" ` +
                `title="Genesis Citation ${tag}" ` +
                `onclick="genesisCite.openDrawer('${tag}')">[${tag}]</span>`
            );
        },

        /**
         * Attach click handlers to any genesis badges in containerEl.
         * (Handles badges injected via innerHTML where onclick may be stripped.)
         * @param {Element} containerEl
         */
        attachHandlers(containerEl) {
            containerEl.querySelectorAll('.genesis-cite-badge[data-genesis-tag]').forEach(badge => {
                badge.addEventListener('click', (e) => {
                    e.stopPropagation();
                    genesisCite.openDrawer(badge.getAttribute('data-genesis-tag'));
                });
            });
        },

        /**
         * Fetch citation from Bridge and open the drawer.
         * @param {string} tag  e.g. "G-0017"
         */
        async openDrawer(tag) {
            _ensureDrawer();
            _expandedState = false;

            // Reset UI
            _drawerEl.classList.add('gc-visible');
            _drawerTagEl.textContent = tag;
            _drawerTitleEl.textContent = '';
            _drawerSourceEl.textContent = '';
            _drawerCommitEl.textContent = '';
            _drawerSpinnerEl.style.display = 'block';
            _drawerErrorEl.style.display = 'none';
            _drawerSnippetEl.style.display = 'none';
            _drawerBodyEl.style.display = 'none';
            _drawerExpandBtn.style.display = 'none';

            try {
                const resp = await fetch(`${GENESIS_BASE}/api/genesis/cite/${encodeURIComponent(tag)}`, {
                    credentials: 'include',
                });
                if (!resp.ok) {
                    throw new Error(`HTTP ${resp.status}`);
                }
                const data = await resp.json();
                if (!data.ok || !data.result) {
                    throw new Error(data.detail || data.error || 'Unknown error');
                }
                const c = data.result;

                _drawerTitleEl.textContent = c.title || '';
                _drawerSourceEl.textContent = c.source || '';
                _drawerCommitEl.textContent = c.source_commit
                    ? c.source_commit.slice(0, 8)
                    : 'unknown';

                // Snippet: first 3 lines of body
                const snippetLines = (c.body || '').split('\n').filter(l => l.trim()).slice(0, 3).join('\n');
                _drawerSnippetEl.textContent = snippetLines || '(no content)';
                _drawerSnippetEl.style.display = 'block';

                // Full body (hidden until expanded)
                _drawerBodyEl.textContent = c.body || '';
                _drawerExpandBtn.style.display = 'block';
                _drawerExpandBtn.textContent = 'Show full block ▾';

                _drawerSpinnerEl.style.display = 'none';
            } catch (err) {
                _drawerSpinnerEl.style.display = 'none';
                _drawerErrorEl.textContent = `Failed to load ${tag}: ${err.message}`;
                _drawerErrorEl.style.display = 'block';
            }
        },

        closeDrawer() {
            if (_drawerEl) _drawerEl.classList.remove('gc-visible');
        },

        toggleExpand() {
            _expandedState = !_expandedState;
            if (_expandedState) {
                _drawerBodyEl.style.display = 'block';
                _drawerExpandBtn.textContent = 'Hide full block ▴';
            } else {
                _drawerBodyEl.style.display = 'none';
                _drawerExpandBtn.textContent = 'Show full block ▾';
            }
        },
    };

    window.genesisCite = genesisCite;

})();
