/* panel-network.js
   AnchorWorks Network — unified file browser across all nodes.

   Nodes are top-level directories in a single virtual filesystem.
   The local bridge proxies all remote node access (browser never talks to nodes directly).

   Endpoints used:
     GET  /api/nodes                              → node list with online status
     GET  /api/network/roots/{nodeId}             → allow_roots for a node
     GET  /api/network/files/{nodeId}?path=...    → browse directory
     GET  /api/network/files/{nodeId}/read?path=  → stream file (download)
     POST /api/network/files/{nodeId}/write       → write file (upload)
     GET  /api/network/files/{nodeId}/hash?path=  → SHA-256 of file

   Exports: window.netInit, window.netBrowse, window.netToggleNode,
            window.netNavigate, window.netPull, window.netPushCurrent,
            window.netHashFile, window.netRefresh, window._netStopPolling
*/
(function () {
    'use strict';

    // ── State ─────────────────────────────────────────────────────────────────
    let _nodes      = [];            // [{id, name, host, online}]
    let _expanded   = new Set();     // node IDs currently expanded in sidebar
    let _nodeRoots  = {};            // { nodeId: ["docs/GENESIS", ...] }
    let _curNode    = null;          // currently browsed node id
    let _curPath    = null;          // current browse path (relative, no leading slash)
    let _curEntries = [];            // entries from last browse call
    let _transfers  = [];            // transfer queue items
    let _xferSeq    = 0;             // monotonic transfer ID counter
    let _pollTimer  = null;          // node status refresh timer
    let _hashPopup  = null;          // currently visible hash popup element

    // ── Bridge URL ────────────────────────────────────────────────────────────
    function _api(path) {
        return (window.ANCHORWORKS_CONFIG?.bridge || 'http://localhost:5050') + path;
    }

    // ── Formatters ────────────────────────────────────────────────────────────
    function _fmtSize(bytes) {
        if (bytes == null || bytes === '') return '';
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / 1024 / 1024).toFixed(1) + ' MB';
    }

    function _fmtAge(ts) {
        if (!ts) return '';
        const diff = Date.now() - ts * 1000;
        if (diff < 60000)    return 'now';
        if (diff < 3600000)  return Math.floor(diff / 60000) + 'm';
        if (diff < 86400000) return Math.floor(diff / 3600000) + 'h';
        const d = new Date(ts * 1000);
        return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    }

    function _fmtSpeed(bps) {
        if (bps <= 0) return '';
        if (bps < 1024) return bps + ' B/s';
        if (bps < 1024 * 1024) return (bps / 1024).toFixed(1) + ' KB/s';
        return (bps / 1024 / 1024).toFixed(1) + ' MB/s';
    }

    function _esc(s) {
        return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }

    // ── Init ──────────────────────────────────────────────────────────────────
    async function netInit() {
        _renderBrowserPlaceholder('Select a node to browse');
        _renderTransfers();
        await _loadNodes();
        _renderSidebar();

        // Auto-expand and select first online node's first root
        const online = _nodes.find(n => n.online);
        if (online) {
            await _expandNode(online.id);
            const roots = _nodeRoots[online.id] || [];
            if (roots.length) netBrowse(online.id, roots[0]);
        }

        // Refresh node status every 20s (no file polling)
        if (_pollTimer) clearInterval(_pollTimer);
        _pollTimer = setInterval(async () => {
            await _loadNodes();
            _renderSidebar();
        }, 20000);
    }

    window._netStopPolling = function () {
        if (_pollTimer) { clearInterval(_pollTimer); _pollTimer = null; }
        _hideHashPopup();
    };

    // ── Node loading ──────────────────────────────────────────────────────────
    async function _loadNodes() {
        try {
            const resp = await fetch(_api('/api/nodes'), { credentials: 'include' });
            if (!resp.ok) return;
            const data = await resp.json();
            const raw = Array.isArray(data) ? data : (data.nodes || []);

            // Merge online status into existing _nodes list (preserve expansion state)
            _nodes = raw.map(n => ({
                id:     n.id || '?',
                name:   n.name || n.id || '?',
                host:   n.host || 'localhost',
                port:   n.port || 5050,
                online: n.online ?? (n.id === 'this'),
                note:   n.note || '',
            }));
        } catch (_) {
            // Fallback: at minimum show "this" node as local
            if (_nodes.length === 0) {
                _nodes = [{ id: 'this', name: 'ROCm Server', host: 'localhost', port: 5050, online: true }];
            }
        }
    }

    // ── Sidebar rendering ─────────────────────────────────────────────────────
    function _renderSidebar() {
        const el = document.getElementById('net-sidebar-body');
        if (!el) return;

        el.innerHTML = _nodes.map(node => {
            const dotCls   = node.online ? 'online' : 'offline';
            const isExp    = _expanded.has(node.id);
            const roots    = _nodeRoots[node.id];
            const tagLabel = node.id === 'this' ? 'local' : (node.online ? 'online' : 'offline');

            // Build root list if expanded
            let rootsHtml = '';
            if (isExp) {
                if (!roots) {
                    rootsHtml = '<div class="net-roots-empty">Loading…</div>';
                } else if (roots.length === 0) {
                    rootsHtml = '<div class="net-roots-empty">No shared roots</div>';
                } else {
                    rootsHtml = roots.map(r => {
                        const label = r.split('/').pop() || r;
                        const isActive = _curNode === node.id && _curPath === r;
                        return `<div class="net-root-item${isActive ? ' active' : ''}"
                                     onclick="netBrowse('${_esc(node.id)}','${_esc(r)}')"
                                     title="${_esc(r)}">
                            <span class="net-root-icon">📁</span>
                            <span>${_esc(label)}</span>
                        </div>`;
                    }).join('');
                }
            }

            return `<div class="net-node${isExp ? ' expanded' : ''}" id="net-node-${_esc(node.id)}">
                <div class="net-node-header${_curNode === node.id ? ' active' : ''}"
                     onclick="netToggleNode('${_esc(node.id)}')">
                    <span class="net-node-chevron">▶</span>
                    <span class="net-node-dot ${dotCls}"></span>
                    <span class="net-node-name">${_esc(node.name)}</span>
                    <span class="net-node-tag">${tagLabel}</span>
                </div>
                <div class="net-roots">${rootsHtml}</div>
            </div>`;
        }).join('');
    }

    // ── Node expand ───────────────────────────────────────────────────────────
    async function netToggleNode(nodeId) {
        if (_expanded.has(nodeId)) {
            _expanded.delete(nodeId);
            _renderSidebar();
            return;
        }
        await _expandNode(nodeId);
    }

    async function _expandNode(nodeId) {
        _expanded.add(nodeId);
        _nodeRoots[nodeId] = null;  // null = loading
        _renderSidebar();

        try {
            const resp = await fetch(_api(`/api/network/roots/${nodeId}`), { credentials: 'include' });
            if (resp.ok) {
                const data = await resp.json();
                _nodeRoots[nodeId] = data.roots || [];
            } else {
                _nodeRoots[nodeId] = [];
            }
        } catch (_) {
            _nodeRoots[nodeId] = [];
        }
        _renderSidebar();
    }

    window.netToggleNode = netToggleNode;

    // ── Browse ────────────────────────────────────────────────────────────────
    async function netBrowse(nodeId, path) {
        _curNode = nodeId;
        _curPath = path;
        _renderBreadcrumb();
        _renderSidebar();  // update active root highlight
        _renderBrowserLoading();

        try {
            const url = _api(`/api/network/files/${encodeURIComponent(nodeId)}?path=${encodeURIComponent(path)}`);
            const resp = await fetch(url, { credentials: 'include' });
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                _renderBrowserError(err.detail || `HTTP ${resp.status}`);
                return;
            }
            const data = await resp.json();
            _curEntries = data.entries || [];
            _renderBrowser();
        } catch (err) {
            _renderBrowserError('Network error — ' + err.message);
        }
    }

    window.netBrowse = netBrowse;

    function netNavigate(path) {
        if (_curNode) netBrowse(_curNode, path);
    }

    window.netNavigate = netNavigate;

    function netRefresh() {
        if (_curNode && _curPath != null) netBrowse(_curNode, _curPath);
    }

    window.netRefresh = netRefresh;

    // ── Breadcrumb rendering ──────────────────────────────────────────────────
    function _renderBreadcrumb() {
        const el = document.getElementById('net-crumb');
        if (!el) return;

        // Show/hide upload button
        const pushBtn = document.getElementById('net-push-btn');
        if (pushBtn) pushBtn.style.display = (_curNode && _curPath != null) ? '' : 'none';

        if (!_curNode) {
            el.innerHTML = '<span class="net-crumb-item placeholder">No node selected</span>';
            return;
        }

        const node = _nodes.find(n => n.id === _curNode);
        const nodeName = node?.name || _curNode;
        const parts = (_curPath || '').split('/').filter(Boolean);

        let html = `<span class="net-crumb-item root-name" onclick="netToggleNode('${_esc(_curNode)}')"
                         title="${_esc(_curNode)}">${_esc(nodeName)}</span>`;

        parts.forEach((part, i) => {
            const pathTo = parts.slice(0, i + 1).join('/');
            const isCurrent = i === parts.length - 1;
            html += `<span class="net-crumb-sep">›</span>`;
            html += `<span class="net-crumb-item${isCurrent ? ' current' : ''}"
                          onclick="${isCurrent ? '' : `netNavigate('${_esc(pathTo)}')`}"
                          title="${_esc(pathTo)}">${_esc(part)}</span>`;
        });

        el.innerHTML = html;
    }

    // ── File browser rendering ────────────────────────────────────────────────
    function _renderBrowserPlaceholder(msg) {
        _renderBreadcrumb();
        const el = document.getElementById('net-file-list');
        if (!el) return;
        el.innerHTML = `<div class="net-empty-state">
            <div class="net-empty-icon">🔗</div>
            <div>${_esc(msg)}</div>
        </div>`;
    }

    function _renderBrowserLoading() {
        const el = document.getElementById('net-file-list');
        if (!el) return;
        el.innerHTML = `<div class="net-empty-state">
            <div class="net-empty-icon spin">⏳</div>
            <div>Loading…</div>
        </div>`;
    }

    function _renderBrowserError(msg) {
        const el = document.getElementById('net-file-list');
        if (!el) return;
        el.innerHTML = `<div class="net-empty-state" style="color:#e94560">
            <div class="net-empty-icon">⚠</div>
            <div>${_esc(msg)}</div>
        </div>`;
    }

    function _renderBrowser() {
        _renderBreadcrumb();
        const el = document.getElementById('net-file-list');
        if (!el) return;

        if (_curEntries.length === 0) {
            el.innerHTML = '<div class="net-empty-state"><div class="net-empty-icon">📭</div><div>Empty directory</div></div>';
            return;
        }

        // Dirs first (alphabetical), then files (alphabetical)
        const dirs  = _curEntries.filter(e => e.type === 'dir').sort((a, b) => a.name.localeCompare(b.name));
        const files = _curEntries.filter(e => e.type === 'file').sort((a, b) => a.name.localeCompare(b.name));

        const rows = [...dirs, ...files].map(entry => {
            const childPath = _curPath ? `${_curPath}/${entry.name}` : entry.name;
            const safeNode  = _esc(_curNode);
            const safePath  = _esc(childPath);
            const safeName  = _esc(entry.name);

            if (entry.type === 'dir') {
                return `<div class="net-file-row is-dir" onclick="netBrowse('${safeNode}','${safePath}')">
                    <span class="net-file-icon">📁</span>
                    <span class="net-file-name">${safeName}/</span>
                    <span class="net-file-size">—</span>
                    <span class="net-file-age">${_fmtAge(entry.mtime)}</span>
                    <span class="net-file-actions">
                        <button class="net-btn" onclick="event.stopPropagation();netBrowse('${safeNode}','${safePath}')" title="Open">→</button>
                    </span>
                </div>`;
            }

            return `<div class="net-file-row">
                <span class="net-file-icon">📄</span>
                <span class="net-file-name" title="${safeName}">${safeName}</span>
                <span class="net-file-size">${_fmtSize(entry.size)}</span>
                <span class="net-file-age">${_fmtAge(entry.mtime)}</span>
                <span class="net-file-actions">
                    <button class="net-btn" onclick="netPull('${safeNode}','${safePath}','${safeName}',${entry.size||0})" title="Download">↓</button>
                    <button class="net-btn" id="hash-btn-${safeName.replace(/[^a-z0-9]/gi,'_')}"
                            onclick="netHashFile('${safeNode}','${safePath}','${safeName}',this)" title="Verify hash">#</button>
                </span>
            </div>`;
        }).join('');

        el.innerHTML = rows;
    }

    // ── Pull (download with progress) ─────────────────────────────────────────
    async function netPull(nodeId, path, filename, size) {
        const xferId = ++_xferSeq;
        _addXfer(xferId, filename, '↓', size);

        try {
            const resp = await fetch(
                _api(`/api/network/files/${encodeURIComponent(nodeId)}/read?path=${encodeURIComponent(path)}`),
                { credentials: 'include' }
            );
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                _updateXfer(xferId, { status: 'error', statusText: err.detail || `HTTP ${resp.status}` });
                _renderTransfers();
                return;
            }

            // Stream response body, tracking bytes for the progress bar
            const reader = resp.body.getReader();
            const chunks = [];
            let loaded = 0;
            let lastFlush = Date.now();
            let lastLoaded = 0;

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                chunks.push(value);
                loaded += value.length;

                const now = Date.now();
                if (now - lastFlush > 200) {
                    const speed = Math.round((loaded - lastLoaded) / ((now - lastFlush) / 1000));
                    _updateXfer(xferId, { loaded, speed });
                    _renderTransfers();
                    lastFlush = now;
                    lastLoaded = loaded;
                }
            }

            // Trigger browser download
            const blob = new Blob(chunks);
            const url  = URL.createObjectURL(blob);
            const a    = document.createElement('a');
            a.href     = url;
            a.download = filename;
            a.click();
            URL.revokeObjectURL(url);

            _updateXfer(xferId, { loaded, total: loaded, status: 'done', speed: 0 });
            _renderTransfers();
            _scheduleXferCleanup(xferId, 8000);

        } catch (err) {
            _updateXfer(xferId, { status: 'error', statusText: err.message });
            _renderTransfers();
        }
    }

    window.netPull = netPull;

    // ── Push (upload with XHR progress) ──────────────────────────────────────
    function netPushCurrent() {
        if (_curNode && _curPath != null) _doPush(_curNode, _curPath);
    }

    function _doPush(nodeId, targetPath) {
        const input = document.createElement('input');
        input.type = 'file';
        input.onchange = () => {
            const file = input.files[0];
            if (!file) return;

            const destPath = targetPath ? `${targetPath}/${file.name}` : file.name;
            const xferId = ++_xferSeq;
            _addXfer(xferId, file.name, '↑', file.size);

            const formData = new FormData();
            formData.append('path', destPath);
            formData.append('file', file);

            const xhr = new XMLHttpRequest();
            xhr.withCredentials = true;

            xhr.upload.onprogress = (e) => {
                if (e.lengthComputable) {
                    _updateXfer(xferId, { loaded: e.loaded });
                    _renderTransfers();
                }
            };

            xhr.onload = async () => {
                if (xhr.status === 200) {
                    _updateXfer(xferId, { loaded: file.size, total: file.size, status: 'done', speed: 0 });
                    _renderTransfers();
                    // Refresh directory view
                    await netBrowse(nodeId, targetPath);
                } else {
                    let detail = `HTTP ${xhr.status}`;
                    try { detail = JSON.parse(xhr.responseText).detail || detail; } catch (_) {}
                    _updateXfer(xferId, { status: 'error', statusText: detail });
                    _renderTransfers();
                }
                _scheduleXferCleanup(xferId, 8000);
            };

            xhr.onerror = () => {
                _updateXfer(xferId, { status: 'error', statusText: 'Network error' });
                _renderTransfers();
            };

            xhr.open('POST', _api(`/api/network/files/${encodeURIComponent(nodeId)}/write`));
            xhr.send(formData);
        };
        input.click();
    }

    window.netPushCurrent = netPushCurrent;

    // ── Hash ──────────────────────────────────────────────────────────────────
    async function netHashFile(nodeId, path, filename, btnEl) {
        _hideHashPopup();
        const origText = btnEl.textContent;
        btnEl.textContent = '…';
        btnEl.disabled = true;

        try {
            const resp = await fetch(
                _api(`/api/network/files/${encodeURIComponent(nodeId)}/hash?path=${encodeURIComponent(path)}`),
                { credentials: 'include' }
            );
            const data = await resp.json();
            if (resp.ok) {
                _showHashPopup(data.hash, data.size, filename, btnEl);
            } else {
                _showHashPopup('Error: ' + (data.detail || resp.statusText), 0, filename, btnEl);
            }
        } catch (err) {
            _showHashPopup('Error: ' + err.message, 0, filename, btnEl);
        } finally {
            btnEl.textContent = origText;
            btnEl.disabled = false;
        }
    }

    window.netHashFile = netHashFile;

    function _showHashPopup(hash, size, filename, anchorEl) {
        _hideHashPopup();
        const el = document.createElement('div');
        el.className = 'net-hash-popup';
        el.innerHTML = `<div class="net-hash-file">${_esc(filename)}</div>
            <div class="net-hash-val">${_esc(hash)}</div>
            ${size ? `<div class="net-hash-size">${_fmtSize(size)}</div>` : ''}`;
        document.body.appendChild(el);
        _hashPopup = el;

        // Position above the anchor button
        const rect = anchorEl.getBoundingClientRect();
        el.style.left = Math.max(8, rect.right - el.offsetWidth - 8) + 'px';
        el.style.top  = (rect.top - el.offsetHeight - 8) + 'px';

        setTimeout(() => {
            document.addEventListener('click', _hideHashPopup, { once: true });
        }, 50);
    }

    function _hideHashPopup() {
        if (_hashPopup) { _hashPopup.remove(); _hashPopup = null; }
    }

    // ── Transfer queue ────────────────────────────────────────────────────────
    function _addXfer(id, name, direction, total) {
        _transfers.unshift({ id, name, direction, loaded: 0, total, status: 'active', speed: 0 });
        _renderTransfers();
    }

    function _updateXfer(id, patch) {
        const t = _transfers.find(x => x.id === id);
        if (t) Object.assign(t, patch);
    }

    function _scheduleXferCleanup(id, delayMs) {
        setTimeout(() => {
            _transfers = _transfers.filter(t => t.id !== id);
            _renderTransfers();
        }, delayMs);
    }

    function _renderTransfers() {
        const listEl  = document.getElementById('net-xfer-list');
        const badgeEl = document.getElementById('net-xfer-badge');
        if (!listEl) return;

        const active = _transfers.filter(t => t.status === 'active').length;
        if (badgeEl) {
            badgeEl.textContent = active || '';
            badgeEl.classList.toggle('visible', active > 0);
        }

        if (_transfers.length === 0) {
            listEl.innerHTML = '<div style="padding:10px 14px;font-size:11px;color:var(--text-secondary)">No transfers</div>';
            return;
        }

        listEl.innerHTML = _transfers.map(t => {
            const pct  = t.total > 0 ? Math.min(100, Math.round((t.loaded / t.total) * 100))
                       : (t.status === 'done' ? 100 : 0);
            const fill = t.status === 'done' ? 'done' : t.status === 'error' ? 'error' : '';
            const stat = t.status === 'done'  ? 'Done'
                       : t.status === 'error' ? ('Err: ' + (t.statusText || '?'))
                       : `${pct}%`;
            return `<div class="net-xfer-row">
                <span class="net-xfer-dir">${t.direction}</span>
                <span class="net-xfer-name" title="${_esc(t.name)}">${_esc(t.name)}</span>
                <span class="net-xfer-speed">${_fmtSpeed(t.speed)}</span>
                <div class="net-xfer-bar"><div class="net-xfer-fill ${fill}" style="width:${pct}%"></div></div>
                <span class="net-xfer-status ${t.status === 'done' ? 'done' : t.status === 'error' ? 'error' : ''}">${_esc(stat)}</span>
            </div>`;
        }).join('');
    }

    // ── Expose public API ─────────────────────────────────────────────────────
    window.netInit = netInit;

})();
