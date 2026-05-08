// panel-artifacts.js — Artifact Viewer (af* namespace)
// Extracted from anchorworks_production.js L10034-10153
if (!window.bridgeApi) console.warn('core.js not loaded before panel-artifacts.js');

// ── Artifact Viewer (af*) ──────────────────────────────────────

let _afSelected = null;

async function afInit() {
    const list = document.getElementById('af-list');
    const count = document.getElementById('af-count');
    if (!list) return;
    list.innerHTML = '<div style="color:var(--text-secondary);padding:12px;font-size:12px;">Loading...</div>';
    try {
        const resp = await fetch(bridgeApi('/api/artifacts'));
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        afRenderList(data.artifacts || []);
        if (count) count.textContent = `${(data.artifacts || []).length} artifact${(data.artifacts || []).length !== 1 ? 's' : ''}`;
    } catch (e) {
        list.innerHTML = `<div style="color:var(--danger);padding:12px;font-size:12px;">Failed to load: ${e.message}</div>`;
    }
}

function afRenderList(items) {
    const list = document.getElementById('af-list');
    if (!list) return;
    if (!items.length) {
        list.innerHTML = '<div style="color:var(--text-secondary);padding:20px;text-align:center;font-size:12px;">No artifacts yet.<br>Enable Tools in chat and ask the LLM to create a file.</div>';
        return;
    }
    list.innerHTML = '';
    for (const item of items) {
        const row = document.createElement('div');
        row.className = 'plugin-row' + (item.name === _afSelected ? ' selected' : '');
        row.style.cursor = 'pointer';
        row.onclick = () => afSelect(item.name);

        const ext = item.name.includes('.') ? item.name.split('.').pop() : '?';
        const sizeStr = item.size_bytes < 1024 ? `${item.size_bytes} B` : `${(item.size_bytes / 1024).toFixed(1)} KB`;
        const dateStr = item.created_at ? new Date(item.created_at).toLocaleString() : '—';

        row.innerHTML = `
            <div class="pr-dot ok" style="background:var(--highlight);box-shadow:0 0 6px rgba(0,212,255,0.3);"></div>
            <div style="flex:1;min-width:0;">
                <div style="font-size:13px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${_afEsc(item.name)}</div>
                <div style="font-size:11px;color:var(--text-secondary);">${sizeStr} &middot; ${_afEsc(dateStr)}</div>
            </div>
            <span style="font-size:10px;padding:2px 6px;border-radius:8px;background:rgba(255,255,255,0.06);color:var(--text-secondary);text-transform:uppercase;">${_afEsc(ext)}</span>
        `;
        list.appendChild(row);
    }
}

async function afSelect(filename) {
    _afSelected = filename;
    const detail = document.getElementById('af-detail');
    if (!detail) return;
    detail.innerHTML = '<div style="color:var(--text-secondary);padding:20px;text-align:center;">Decrypting...</div>';

    // Re-highlight selected row
    document.querySelectorAll('#af-list .plugin-row').forEach(r => {
        r.classList.toggle('selected', r.querySelector('div[style*="font-weight"]')?.textContent === filename);
    });

    try {
        const resp = await fetch(bridgeApi(`/api/artifacts/${encodeURIComponent(filename)}`));
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();

        detail.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;padding-bottom:12px;border-bottom:1px solid var(--border);">
                <div>
                    <div style="font-size:15px;font-weight:600;">${_afEsc(data.name)}</div>
                    <div style="font-size:11px;color:var(--text-secondary);">${data.size_bytes} bytes</div>
                </div>
                <div style="display:flex;gap:6px;">
                    <button class="btn btn-sm" onclick="afDownload('${_afEsc(filename)}')" style="font-size:11px;">⬇ Download</button>
                    <button class="btn btn-sm" onclick="afDelete('${_afEsc(filename)}')" style="font-size:11px;color:var(--danger);border-color:var(--danger);">🗑 Delete</button>
                </div>
            </div>
            <pre style="flex:1;overflow:auto;margin:0;padding:16px;background:rgba(0,0,0,0.2);border-radius:6px;font-size:12px;line-height:1.6;white-space:pre-wrap;word-break:break-word;color:var(--text-primary);font-family:'Cascadia Code','Fira Code',monospace;">${_afEsc(data.content)}</pre>
        `;
    } catch (e) {
        detail.innerHTML = `<div style="color:var(--danger);padding:20px;">Failed to read: ${e.message}</div>`;
    }
}

async function afDelete(filename) {
    if (!confirm(`Delete artifact "${filename}"?\n\nThis is permanent and audited.`)) return;
    try {
        const resp = await fetch(bridgeApi(`/api/artifacts/${encodeURIComponent(filename)}`), { method: 'DELETE' });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        _afSelected = null;
        const detail = document.getElementById('af-detail');
        if (detail) detail.innerHTML = '<div style="color:var(--text-secondary);padding:40px;text-align:center;">Select an artifact to view</div>';
        afInit();
    } catch (e) {
        alert(`Delete failed: ${e.message}`);
    }
}

async function afDownload(filename) {
    try {
        const resp = await fetch(bridgeApi(`/api/artifacts/${encodeURIComponent(filename)}/download`));
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    } catch (e) {
        alert(`Download failed: ${e.message}`);
    }
}

function _afEsc(str) {
    if (!str) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

window.ANCHORWORKS.ready.panel_artifacts = true;
