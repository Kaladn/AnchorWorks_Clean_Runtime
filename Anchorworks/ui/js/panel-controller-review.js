// panel-controller-review.js — Gamepad-driven lexicon review session
// Scope: Unmatched Words view in the Lexicon Browser panel only.
// Parallel path — never calls lexAcceptUnmatched / lexDenyUnmatched.

(function () {
    'use strict';

    // ── Inject styles ─────────────────────────────────────────────────────
    const _style = document.createElement('style');
    _style.textContent = `
        .ctrl-focused {
            outline: 2px solid #00d4ff !important;
            outline-offset: 2px !important;
            box-shadow: 0 0 0 4px rgba(0,212,255,0.18) !important;
        }
        .ctrl-state-approved {
            border-left-color: #00ff88 !important;
            background: rgba(0,255,136,0.07) !important;
        }
        .ctrl-state-denied {
            border-left-color: #ff4444 !important;
            background: rgba(255,68,68,0.07) !important;
            opacity: 0.6;
        }
        .ctrl-state-neutral {
            border-left-color: #ff9f43 !important;
            background: var(--accent-bg) !important;
            opacity: 1;
        }
        #ctrl-hud {
            display: none;
            align-items: center;
            gap: 16px;
            padding: 8px 14px;
            margin-bottom: 8px;
            background: rgba(0,0,0,0.6);
            border: 1px solid #00d4ff44;
            border-radius: 8px;
            font-size: 11px;
            font-family: 'Consolas', monospace;
            flex-wrap: wrap;
        }
        #ctrl-hud-mode  { color: #00d4ff; font-weight: 700; font-size: 12px; }
        #ctrl-hud-flash { color: #00ff88; font-weight: 600; margin-left: auto; }
        .ctrl-hud-stat  { display: flex; flex-direction: column; align-items: center; gap: 1px; }
        .ctrl-hud-stat span:first-child { font-size: 9px; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.5px; }
        .ctrl-hud-stat span:last-child  { font-weight: 700; font-size: 13px; }
        #ctrl-hud-hint {
            width: 100%;
            font-size: 9px;
            color: #555;
            padding-top: 2px;
            letter-spacing: 0.3px;
        }
    `;
    document.head.appendChild(_style);

    // ── Button map (standard mapping) ─────────────────────────────────────
    const BTN = {
        A: 0, B: 1, X: 2, Y: 3,
        LB: 4, RB: 5,
        SELECT: 8, START: 9,
        DPAD_UP: 12, DPAD_DOWN: 13, DPAD_LEFT: 14, DPAD_RIGHT: 15,
    };

    // ── Session state ─────────────────────────────────────────────────────
    const _s = {
        active: false,
        focusIndex: 0,
        mode: 'main',          // 'main' | 'review-approved' | 'review-denied'
        approved: new Set(),
        denied: new Set(),
        history: [],           // [{word, prevApproved, prevDenied}]
        cards: [],             // word strings in DOM order (main view)
        reviewCards: [],       // word strings in current review view
        pollHandle: null,
        lastButtons: {},
        commitInFlight: false,
    };

    // ── Guard ─────────────────────────────────────────────────────────────
    function _guard() {
        if (!_s.active) return false;
        const panel = document.getElementById('panel-lexicon');
        if (!panel || window.getComputedStyle(panel).display === 'none') return false;
        const lexView = document.getElementById('lex-view-lexicon');
        if (!lexView || window.getComputedStyle(lexView).display === 'none') return false;
        return true;
    }

    // ── Card sync ─────────────────────────────────────────────────────────
    function _syncCards() {
        const els = document.querySelectorAll('[id^="unmatch-card-"]');
        _s.cards = [...els].map(el => el.id.slice('unmatch-card-'.length));
    }

    // ── Focus ─────────────────────────────────────────────────────────────
    function _focusAt(index) {
        const list = _s.mode === 'main' ? _s.cards : _s.reviewCards;
        if (list.length === 0) { _s.focusIndex = 0; _hudUpdate(); return; }
        _s.focusIndex = Math.max(0, Math.min(index, list.length - 1));
        document.querySelectorAll('.ctrl-focused').forEach(el => el.classList.remove('ctrl-focused'));
        const card = document.getElementById(`unmatch-card-${list[_s.focusIndex]}`);
        if (card) {
            card.classList.add('ctrl-focused');
            card.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
        _hudUpdate();
    }

    function _advance() {
        const list = _s.mode === 'main' ? _s.cards : _s.reviewCards;
        _focusAt(_s.focusIndex < list.length - 1 ? _s.focusIndex + 1 : 0);
    }

    // ── Decision state rendering ──────────────────────────────────────────
    function _renderCardState(word) {
        const card = document.getElementById(`unmatch-card-${word}`);
        if (!card) return;
        card.classList.remove('ctrl-state-approved', 'ctrl-state-denied', 'ctrl-state-neutral');
        if (_s.approved.has(word)) card.classList.add('ctrl-state-approved');
        else if (_s.denied.has(word)) card.classList.add('ctrl-state-denied');
        else card.classList.add('ctrl-state-neutral');
    }

    // ── Current word ──────────────────────────────────────────────────────
    function _currentWord() {
        const list = _s.mode === 'main' ? _s.cards : _s.reviewCards;
        return list[_s.focusIndex] ?? null;
    }

    // ── Decision engine ───────────────────────────────────────────────────
    function controllerApprove() {
        const word = _currentWord();
        if (!word) return;
        if (word.includes('_')) {
            _hudFlash('⚠ Compound — use B to deny or skip', '#ff9f43');
            _advance();
            return;
        }
        _s.history.push({ word, prevApproved: _s.approved.has(word), prevDenied: _s.denied.has(word) });
        _s.denied.delete(word);
        _s.approved.add(word);
        _renderCardState(word);
        _advance();
    }

    function controllerDeny() {
        const word = _currentWord();
        if (!word) return;
        _s.history.push({ word, prevApproved: _s.approved.has(word), prevDenied: _s.denied.has(word) });
        _s.approved.delete(word);
        _s.denied.add(word);
        _renderCardState(word);
        _advance();
    }

    function controllerUndo() {
        if (_s.mode !== 'main') return;
        const entry = _s.history.pop();
        if (!entry) { _hudFlash('Nothing to undo', '#888'); return; }
        const { word, prevApproved, prevDenied } = entry;
        _s.approved.delete(word);
        _s.denied.delete(word);
        if (prevApproved) _s.approved.add(word);
        else if (prevDenied) _s.denied.add(word);
        _renderCardState(word);
        const idx = _s.cards.indexOf(word);
        if (idx !== -1) _focusAt(idx);
        _hudFlash(`↩ Undid "${word}"`, '#aaa');
    }

    async function controllerCommit() {
        if (_s.commitInFlight) return;
        const approvedWords = [..._s.approved];
        const deniedWords   = [..._s.denied];
        if (approvedWords.length === 0 && deniedWords.length === 0) {
            _hudFlash('Nothing to commit', '#888');
            return;
        }
        _s.commitInFlight = true;
        _hudFlash(`Committing ${approvedWords.length} ✓  ${deniedWords.length} ✗ …`, '#ffd700');
        const base = window.app?.serverUrl || 'https://127.0.0.1:5050';
        try {
            if (approvedWords.length > 0) {
                const r = await fetch(`${base}/api/lexicon/unmatched/approve-all`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ words: approvedWords }),
                });
                if (!r.ok) throw new Error(`approve-all HTTP ${r.status}`);
            }
            if (deniedWords.length > 0) {
                const r = await fetch(`${base}/api/lexicon/unmatched/deny-all`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ words: deniedWords }),
                });
                if (!r.ok) throw new Error(`deny-all HTTP ${r.status}`);
            }
        } catch (e) {
            _hudFlash(`Commit failed: ${e.message}`, '#ff4444');
            _s.commitInFlight = false;
            return;
        }
        _s.approved.clear();
        _s.denied.clear();
        _s.history.length = 0;
        _s.commitInFlight = false;
        _hudFlash('✓ Committed. Loading next batch…', '#00ff88');
        setTimeout(async () => {
            if (window.app?.lexShowUnmatched) {
                await window.app.lexShowUnmatched();
                _syncCards();
                _s.cards.forEach(w => _renderCardState(w));
                _focusAt(0);
                _hudUpdate();
            }
        }, 600);
    }

    // ── Review mode ───────────────────────────────────────────────────────
    function _enterReview(kind) {
        _s.mode = kind === 'approved' ? 'review-approved' : 'review-denied';
        const words = kind === 'approved' ? [..._s.approved] : [..._s.denied];
        _s.reviewCards = words;
        _renderReviewList(kind, words);
        _focusAt(0);
    }

    function _exitReview() {
        const savedIndex = _s.focusIndex;
        _s.mode = 'main';
        _s.reviewCards = [];
        if (window.app?.lexShowUnmatched) {
            window.app.lexShowUnmatched().then(() => {
                _syncCards();
                _s.cards.forEach(w => _renderCardState(w));
                _focusAt(savedIndex);
            });
        }
    }

    function _renderReviewList(kind, words) {
        const container = document.getElementById('lexicon-results');
        if (!container) return;
        const color = kind === 'approved' ? '#00ff88' : '#ff4444';
        const label = kind === 'approved' ? 'APPROVED' : 'DENIED';
        if (words.length === 0) {
            container.innerHTML = `<div style="grid-column:1/-1;text-align:center;padding:30px;color:var(--text-secondary);">No ${label.toLowerCase()} words in buffer. Press Y to return.</div>`;
            return;
        }
        container.innerHTML = words.map(w => `
            <div id="unmatch-card-${_escHtml(w)}"
                 style="background:var(--accent-bg);border:1px solid var(--border);border-radius:8px;padding:12px;border-left:4px solid ${color};cursor:default;">
                <div style="font-size:14px;font-weight:700;color:var(--text-primary);">${_escHtml(w)}</div>
                <div style="font-size:10px;color:${color};margin-top:4px;font-weight:600;">${label}</div>
                <div style="font-size:9px;color:var(--text-secondary);margin-top:4px;">A = flip${kind === 'approved' ? ' to denied' : ' to approved'} · B = keep · Y = back</div>
            </div>`).join('');
        words.forEach(w => _renderCardState(w));
    }

    // ── HUD ───────────────────────────────────────────────────────────────
    function _hudUpdate() {
        const hud = document.getElementById('ctrl-hud');
        if (!hud) return;
        const list = _s.mode === 'main' ? _s.cards : _s.reviewCards;
        const remaining = _s.mode === 'main'
            ? _s.cards.filter(w => !_s.approved.has(w) && !_s.denied.has(w)).length
            : list.length;
        const modeMap = { 'main': '🎮 CONTROLLER', 'review-approved': '✅ REVIEW: APPROVED', 'review-denied': '❌ REVIEW: DENIED' };
        document.getElementById('ctrl-hud-mode').textContent = modeMap[_s.mode] || '🎮';
        document.getElementById('ctrl-hud-approved').textContent = _s.approved.size;
        document.getElementById('ctrl-hud-denied').textContent   = _s.denied.size;
        document.getElementById('ctrl-hud-remaining').textContent = remaining;
        document.getElementById('ctrl-hud-index').textContent =
            list.length > 0 ? `${_s.focusIndex + 1} / ${list.length}` : '—';
    }

    let _flashTimer = null;
    function _hudFlash(msg, color) {
        const el = document.getElementById('ctrl-hud-flash');
        if (!el) return;
        el.textContent = msg;
        el.style.color = color || 'var(--text-primary)';
        clearTimeout(_flashTimer);
        _flashTimer = setTimeout(() => { if (el) el.textContent = ''; }, 2400);
    }

    // ── Gamepad edge-trigger ──────────────────────────────────────────────
    function _edgeTrigger(gp) {
        const fired = [];
        gp.buttons.forEach((btn, i) => {
            const pressed = btn.pressed || btn.value > 0.5;
            if (pressed && !_s.lastButtons[i]) fired.push(i);
            _s.lastButtons[i] = pressed;
        });
        return fired;
    }

    // ── Poll loop ─────────────────────────────────────────────────────────
    function _pollFrame() {
        if (!_s.active) return;
        _s.pollHandle = requestAnimationFrame(_pollFrame);
        if (!_guard()) return;

        const gamepads = navigator.getGamepads ? navigator.getGamepads() : [];
        for (const gp of gamepads) {
            if (!gp || gp.mapping !== 'standard') continue;
            for (const btn of _edgeTrigger(gp)) {
                switch (btn) {
                    case BTN.A:
                        if (_s.mode === 'review-denied')   { controllerApprove(); }
                        else if (_s.mode === 'review-approved') { _advance(); }
                        else                               { controllerApprove(); }
                        break;
                    case BTN.B:
                        if (_s.mode === 'review-approved') { controllerDeny(); }
                        else if (_s.mode === 'review-denied') { _advance(); }
                        else                               { controllerDeny(); }
                        break;
                    case BTN.X:      controllerUndo(); break;
                    case BTN.Y:      _s.mode !== 'main' ? _exitReview() : undefined; break;
                    case BTN.LB:     _s.mode !== 'review-denied'   ? _enterReview('denied')   : _exitReview(); break;
                    case BTN.RB:     _s.mode !== 'review-approved' ? _enterReview('approved') : _exitReview(); break;
                    case BTN.START:  controllerCommit(); break;
                    case BTN.DPAD_DOWN:
                    case BTN.DPAD_RIGHT: _focusAt(_s.focusIndex + 1); break;
                    case BTN.DPAD_UP:
                    case BTN.DPAD_LEFT:  _focusAt(_s.focusIndex - 1); break;
                }
            }
        }
    }

    // ── Activate / Deactivate ─────────────────────────────────────────────
    function controllerActivate() {
        if (_s.active) return;
        if (!navigator.getGamepads) {
            alert('Gamepad API not supported in this browser.');
            return;
        }
        const gamepads = [...(navigator.getGamepads() || [])];
        const nonStandard = gamepads.filter(g => g && g.mapping !== 'standard');
        const standard    = gamepads.filter(g => g && g.mapping === 'standard');
        if (gamepads.filter(Boolean).length > 0 && standard.length === 0) {
            _hudFlash('Controller detected but mapping is not "standard". Unsupported.', '#ff9f43');
        }

        _s.active = false; // set after guard check below
        _s.mode = 'main';
        _s.focusIndex = 0;
        _s.approved.clear();
        _s.denied.clear();
        _s.history.length = 0;
        _s.lastButtons = {};
        _s.active = true;

        const hud = document.getElementById('ctrl-hud');
        if (hud) hud.style.display = 'flex';

        const toggleBtn = document.getElementById('ctrl-toggle-btn');
        if (toggleBtn) { toggleBtn.textContent = '🎮 Exit Controller'; toggleBtn.style.background = '#c23152'; }

        _syncCards();
        _s.cards.forEach(w => _renderCardState(w));
        _focusAt(0);
        _s.pollHandle = requestAnimationFrame(_pollFrame);
        _hudUpdate();
        _hudFlash('Active — A=✓ B=✗ X=undo RB=approved LB=denied Start=commit', '#00ff88');
    }

    function controllerDeactivate() {
        if (!_s.active) return;
        _s.active = false;
        if (_s.pollHandle) { cancelAnimationFrame(_s.pollHandle); _s.pollHandle = null; }
        document.querySelectorAll('.ctrl-focused,.ctrl-state-approved,.ctrl-state-denied,.ctrl-state-neutral')
            .forEach(el => el.classList.remove('ctrl-focused','ctrl-state-approved','ctrl-state-denied','ctrl-state-neutral'));
        if (_s.mode !== 'main') {
            _s.mode = 'main';
            if (window.app?.lexShowUnmatched) window.app.lexShowUnmatched();
        }
        const hud = document.getElementById('ctrl-hud');
        if (hud) hud.style.display = 'none';
        const toggleBtn = document.getElementById('ctrl-toggle-btn');
        if (toggleBtn) { toggleBtn.textContent = '🎮 Controller'; toggleBtn.style.background = 'linear-gradient(135deg,#6c3483,#9b59b6)'; }
    }

    function controllerToggle() {
        _s.active ? controllerDeactivate() : controllerActivate();
    }

    // ── Hook lexShowUnmatched to auto-sync on reload ───────────────────────
    function _hookLexShowUnmatched() {
        const orig = window.app?.lexShowUnmatched;
        if (!orig || orig._ctrlPatched) return;
        window.app.lexShowUnmatched = async function (...args) {
            const result = await orig.apply(window.app, args);
            if (_s.active && _s.mode === 'main') {
                _syncCards();
                _s.cards.forEach(w => _renderCardState(w));
                _hudUpdate();
            }
            return result;
        };
        window.app.lexShowUnmatched._ctrlPatched = true;
    }

    function _escHtml(str) {
        return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }

    // ── Expose globals ────────────────────────────────────────────────────
    window.controllerToggle     = controllerToggle;
    window.controllerActivate   = controllerActivate;
    window.controllerDeactivate = controllerDeactivate;
    window.controllerCommit     = controllerCommit;
    window._ctrlEnterReview     = function(kind) { if (_s.active) _enterReview(kind); };

    function _waitForApp() {
        if (window.app?.lexShowUnmatched) { _hookLexShowUnmatched(); }
        else { setTimeout(_waitForApp, 500); }
    }
    _waitForApp();

})();
