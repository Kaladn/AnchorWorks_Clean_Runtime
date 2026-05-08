// panel-chat-packs.js — Chat Packs / Learning Center (cp* namespace)
// Extracted from anchorworks_production.js L9191-9590
if (!window.bridgeApi) console.warn('core.js not loaded before panel-chat-packs.js');

// ── Chat Packs / Learning Center (cp*) Module ─────────────────

let _cpSessionId = null;
let _cpPackId = null;
let _cpSession = null;
let _cpViewingIndex = null;

// ── Init + State Routing ──

function cpInit() {
    if (_cpSessionId) {
        cpEnterWorkspace(_cpSessionId);
    } else {
        cpEnterLibrary();
    }
}

// ── Library Mode (State A) ──

async function cpEnterLibrary() {
    document.getElementById('cp-library').style.display = '';
    document.getElementById('cp-workspace').style.display = 'none';
    cpLoadPacks();
    cpLoadSavedSessions();
}

async function cpLoadSavedSessions() {
    const wrapper = document.getElementById('cp-saved-sessions');
    const el = document.getElementById('cp-sessions-list');
    if (!wrapper || !el) return;
    try {
        const res = await fetch(bridgeApi('/api/chat-packs/sessions'), { credentials: 'include' });
        const data = await res.json();
        if (data.error || !data.sessions || !data.sessions.length) {
            wrapper.style.display = 'none';
            return;
        }
        const active = data.sessions.filter(s => s.phase !== 'complete');
        if (!active.length) { wrapper.style.display = 'none'; return; }
        wrapper.style.display = '';
        el.innerHTML = active.map(s => {
            const pct = s.total_sections > 0
                ? Math.round((s.section_index / s.total_sections) * 100) : 0;
            const label = s.phase === 'questions'
                ? `Questions ${s.question_index + 1}/${s.total_questions}`
                : `Section ${s.section_index + 1}/${s.total_sections}`;
            return `
                <div class="cp-resume-card" onclick="cpResume('${escapeHtml(s.session_id)}')">
                    <div>
                        <div style="font-weight:600;font-size:14px;">${escapeHtml(s.pack_title)}</div>
                        <div style="font-size:12px;color:var(--text-secondary);margin-top:2px;">
                            ${label} &middot; ${pct}% complete
                        </div>
                    </div>
                    <span class="btn btn-sm" style="font-size:11px;">Resume</span>
                </div>`;
        }).join('');
    } catch (e) {
        wrapper.style.display = 'none';
    }
}

function cpResume(sessionId) {
    _cpSessionId = sessionId;
    cpEnterWorkspace(sessionId);
}

async function cpLoadPacks() {
    const el = document.getElementById('cp-packs-list');
    if (!el) return;
    try {
        const res = await fetch(bridgeApi('/api/chat-packs/list'), { credentials: 'include' });
        const data = await res.json();
        if (data.error) {
            el.innerHTML = `<div style="color:var(--text-secondary);font-size:13px;">Error: ${escapeHtml(data.error.message || JSON.stringify(data.error))}</div>`;
            return;
        }
        const packs = data.packs || [];
        if (!packs.length) {
            el.innerHTML = '<div style="color:var(--text-secondary);font-size:13px;">No packs installed yet.</div>';
            return;
        }
        el.innerHTML = packs.map(p => `
            <div class="cp-pack-card" onclick="cpStartPack('${escapeHtml(p.pack_id)}')">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <span style="font-weight:600;font-size:14px;">${escapeHtml(p.title || p.pack_id)}</span>
                    ${p.difficulty ? `<span style="font-size:11px;color:var(--text-secondary);">${escapeHtml(p.difficulty)}</span>` : ''}
                </div>
                <div style="font-size:12px;color:var(--text-secondary);margin-top:4px;">
                    ${p.total_sections} sections &middot; ${p.total_questions} questions
                    ${p.tags && p.tags.length ? ' &middot; ' + p.tags.map(t => escapeHtml(t)).join(', ') : ''}
                </div>
            </div>
        `).join('');
    } catch (e) {
        el.innerHTML = `<div style="color:var(--text-secondary);font-size:13px;">Could not load packs: ${escapeHtml(e.message)}</div>`;
    }
}

// ── Start Pack ──

async function cpStartPack(packId) {
    try {
        const res = await fetch(bridgeApi(`/api/chat-packs/session/start/${encodeURIComponent(packId)}`), {
            method: 'POST', credentials: 'include',
        });
        const data = await res.json();
        if (data.error) {
            alert('Start failed: ' + (data.error.message || JSON.stringify(data.error)));
            return;
        }
        const sess = data.session;
        _cpSessionId = sess.session_id;
        _cpPackId = sess.pack_id;
        _cpSession = sess;
        cpEnterWorkspace(sess.session_id);
    } catch (e) {
        alert('Start error: ' + e.message);
    }
}

// ── Workspace Mode (State B) ──

async function cpEnterWorkspace(sessionId) {
    document.getElementById('cp-library').style.display = 'none';
    document.getElementById('cp-workspace').style.display = '';
    try {
        const res = await fetch(bridgeApi(`/api/chat-packs/session/${sessionId}/view`),
                                { credentials: 'include' });
        const data = await res.json();
        if (data.error || !data.session) {
            _cpSessionId = null; _cpPackId = null; _cpSession = null;
            cpShowBreadcrumb(null);
            cpEnterLibrary();
            return;
        }
        _cpSessionId = data.session.session_id;
        _cpPackId = data.session.pack_id;
        _cpSession = data.session;
        _cpViewingIndex = null;
        cpRenderWorkspace(data);
    } catch (e) {
        cpEnterLibrary();
    }
}

function cpRenderWorkspace(data) {
    const sess = data.session;
    if (!sess) return;

    // Header
    document.getElementById('cp-ws-title').textContent = data.pack_title || sess.pack_id;

    // Progress
    const total = sess.total_sections + sess.total_questions;
    const done = sess.phase === 'complete' ? total
        : sess.phase === 'questions' ? sess.total_sections + sess.question_index
        : sess.section_index;
    const pct = total > 0 ? Math.round((done / total) * 100) : 0;
    document.getElementById('cp-ws-progress-text').textContent =
        sess.phase === 'questions'
            ? `Question ${sess.question_index + 1}/${sess.total_questions}`
            : `Section ${sess.section_index + 1}/${sess.total_sections}`;
    document.getElementById('cp-ws-progress-fill').style.width = pct + '%';

    // Section outline
    const outlineEl = document.getElementById('cp-ws-outline');
    if (outlineEl && data.sections) {
        outlineEl.innerHTML = data.sections.map(s => {
            let icon, cls, onclick;
            if (s.status === 'completed') {
                icon = '<span style="color:var(--success);">&#10003;</span>';
                cls = 'completed';
                onclick = `onclick="cpViewSection(${s.index})"`;
            } else if (s.status === 'current') {
                icon = '<span style="color:var(--gpt-oss);">&rarr;</span>';
                cls = 'current';
                onclick = `onclick="cpViewSection(${s.index})"`;
            } else {
                icon = '<span>&#128274;</span>';
                cls = 'locked';
                onclick = '';
            }
            return `<div class="cp-outline-item ${cls}" ${onclick}>
                <span class="cp-icon">${icon}</span>
                <span>${escapeHtml(s.title)}</span>
            </div>`;
        }).join('');
    }

    // Content
    cpRenderContent(data.current_content);

    // Next button state
    const nextBtn = document.getElementById('cp-ws-next-btn');
    if (nextBtn) {
        if (sess.phase === 'complete') {
            nextBtn.textContent = 'Completed';
            nextBtn.disabled = true;
            nextBtn.style.opacity = '0.5';
        } else if (sess.phase === 'questions') {
            nextBtn.textContent = 'Next Question';
            nextBtn.disabled = false;
            nextBtn.style.opacity = '1';
        } else {
            nextBtn.textContent = 'Next Section';
            nextBtn.disabled = false;
            nextBtn.style.opacity = '1';
        }
    }

    cpShowBreadcrumb(data.pack_title || sess.pack_id);
}

function cpRenderContent(content) {
    const titleEl = document.getElementById('cp-ws-content-title');
    const bodyEl = document.getElementById('cp-ws-content-body');
    if (!titleEl || !bodyEl) return;
    if (!content) { titleEl.textContent = '\u2014'; bodyEl.textContent = ''; return; }
    titleEl.textContent = content.title || '\u2014';
    bodyEl.textContent = content.body || '';
}

async function cpViewSection(index) {
    if (!_cpPackId || !_cpSession) return;
    const currentIdx = _cpSession.section_index || 0;
    const phase = _cpSession.phase || 'lesson';
    const allDone = (phase === 'questions' || phase === 'complete');

    if (!allDone && index > currentIdx) return; // Locked

    if (index === currentIdx && !allDone) {
        // Clicking current section — re-render current
        _cpViewingIndex = null;
        cpEnterWorkspace(_cpSessionId);
        return;
    }

    // Viewing a completed section
    _cpViewingIndex = index;
    try {
        const res = await fetch(
            bridgeApi(`/api/chat-packs/pack/${encodeURIComponent(_cpPackId)}/section/${index}`),
            { credentials: 'include' });
        const data = await res.json();
        if (data.error) return;
        cpRenderContent({ title: data.title, body: data.body });

        // Show "back to current" button
        const nextBtn = document.getElementById('cp-ws-next-btn');
        if (nextBtn && !allDone) {
            nextBtn.textContent = 'Back to Current';
            nextBtn.disabled = false;
            nextBtn.style.opacity = '1';
            nextBtn.onclick = function() {
                _cpViewingIndex = null;
                nextBtn.onclick = function() { cpAdvance(); };
                cpEnterWorkspace(_cpSessionId);
            };
        }
    } catch (e) { /* silent */ }
}

function cpBackToLibrary() {
    cpEnterLibrary();
}

// ── Session Controls ──

async function cpAdvance() {
    if (!_cpSessionId) return;
    _cpViewingIndex = null;
    try {
        const res = await fetch(bridgeApi(`/api/chat-packs/session/advance/${_cpSessionId}`), {
            method: 'POST', credentials: 'include',
        });
        const data = await res.json();
        if (data.error) {
            alert('Advance failed: ' + (data.error.message || JSON.stringify(data.error)));
            return;
        }
        _cpSession = data.session;
        if (data.session && data.session.phase === 'complete') {
            cpShowBreadcrumb(null);
        }
        cpEnterWorkspace(_cpSessionId);
    } catch (e) {
        alert('Advance error: ' + e.message);
    }
}

async function cpReset() {
    if (!_cpSessionId) return;
    if (!confirm('Reset this lesson to the beginning?')) return;
    try {
        const res = await fetch(bridgeApi(`/api/chat-packs/session/reset/${_cpSessionId}`), {
            method: 'POST', credentials: 'include',
        });
        const data = await res.json();
        if (data.error) {
            alert('Reset failed: ' + (data.error.message || JSON.stringify(data.error)));
            return;
        }
        _cpSession = data.session;
        _cpViewingIndex = null;
        cpEnterWorkspace(_cpSessionId);
    } catch (e) {
        alert('Reset error: ' + e.message);
    }
}

// ── Progress callback (from chat responses) ──

function cpRenderProgress(trace) {
    if (!trace || !trace.pack_session) return;
    const ps = trace.pack_session;
    _cpSession = Object.assign(_cpSession || {}, ps);
    // If workspace is visible, refresh it
    const ws = document.getElementById('cp-workspace');
    if (ws && ws.style.display !== 'none') {
        cpEnterWorkspace(ps.session_id || _cpSessionId);
    }
    cpShowBreadcrumb(ps.pack_id || _cpPackId || 'Active');
}

// ── Install ──

async function cpInstall() {
    const pathEl = document.getElementById('cp-install-path');
    const fbEl = document.getElementById('cp-install-feedback');
    if (!pathEl || !fbEl) return;
    let srcPath = pathEl.value.trim();
    if (!srcPath) {
        fbEl.textContent = 'Opening folder picker...';
        fbEl.style.color = 'var(--text-secondary)';
        try {
            const pickRes = await fetch(bridgeApi('/api/chat-packs/pick-install-folder'), {
                method: 'POST',
                credentials: 'include',
            });
            const pickData = await pickRes.json();
            if (pickData.error) {
                fbEl.textContent = 'Picker error: ' + (pickData.error.message || JSON.stringify(pickData.error));
                fbEl.style.color = '#e94560';
                return;
            }
            if (pickData.cancelled || !pickData.selected_path) {
                fbEl.textContent = 'Install cancelled.';
                fbEl.style.color = 'var(--text-secondary)';
                return;
            }
            srcPath = String(pickData.selected_path || '').trim();
            pathEl.value = srcPath;
        } catch (e) {
            fbEl.textContent = 'Picker error: ' + e.message;
            fbEl.style.color = '#e94560';
            return;
        }
    }

    fbEl.textContent = 'Installing...';
    fbEl.style.color = 'var(--text-secondary)';
    try {
        const res = await fetch(bridgeApi('/api/chat-packs/install'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ source_path: srcPath }),
        });
        const data = await res.json();
        if (data.error) {
            fbEl.textContent = 'Error: ' + (data.error.message || JSON.stringify(data.error));
            fbEl.style.color = '#e94560';
            return;
        }
        fbEl.textContent = `Installed: ${data.pack_id}`;
        fbEl.style.color = '#00ff88';
        pathEl.value = '';
        cpLoadPacks();
    } catch (e) {
        fbEl.textContent = 'Install error: ' + e.message;
        fbEl.style.color = '#e94560';
    }
}

// ── Shared helpers ──

function cpShowBreadcrumb(title) {
    const el = document.getElementById('cp-chat-breadcrumb');
    if (!el) return;
    if (title) {
        el.style.display = 'flex';
        document.getElementById('cp-breadcrumb-title').textContent = '\uD83D\uDCD6 Chat Pack: ' + title;
    } else {
        el.style.display = 'none';
    }
}

function cpOpenChat() {
    switchPanel('gpt-oss');
    if (_cpSession) {
        cpShowBreadcrumb(_cpSession.pack_id || _cpPackId || 'Active');
    }
}

window.ANCHORWORKS.ready.panel_chat_packs = true;
