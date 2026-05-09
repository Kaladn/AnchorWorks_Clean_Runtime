// console.js — AnchorWorksConsole class + global wrappers + Lexicon Danger Gate
// Extracted from anchorworks_production.js L154-4253
if (!window.bridgeApi) console.warn('core.js not loaded before console.js');

class AnchorWorksConsole {
    constructor(bootData) {
        this._bridgeStorageKey = 'anchorworks_bridge_url';
        const bridgeUrl = localStorage.getItem(this._bridgeStorageKey);
        const legacyServerUrl = localStorage.getItem('serverUrl');
        this.serverUrl = bridgeUrl || legacyServerUrl || (window.ANCHORWORKS_CONFIG?.bridge || 'http://127.0.0.1:5050');
        if (!bridgeUrl && legacyServerUrl) {
            localStorage.setItem(this._bridgeStorageKey, legacyServerUrl);
            localStorage.removeItem('serverUrl');
        }
        this.gptEndpoint = localStorage.getItem('gptEndpoint') || (window.ANCHORWORKS_CONFIG?.llm || 'http://localhost:11435') + '/api/generate';
        this.localApiBase = window.ANCHORWORKS_CONFIG?.llm || 'http://localhost:11435';
        this.citeBase = window.ANCHORWORKS_CONFIG?.citations || 'http://localhost:5052';
        this.gptModel = localStorage.getItem('gptModel') || '';
        this.websocket = null;
        this._wsWasConnected = false;  // tracks reconnect vs first connect
        this._historyLoadPromise = null;
        this._historyLoaded = false;
        this.currentJob = null;
        this.currentReport = null;

        this.gptConnected = false;
        this.serverConnected = false;
        this.userDisplayName = null;  // Loaded from server on connect
        this._todayStr = new Date().toISOString().slice(0, 10);  // YYYY-MM-DD for citation sidecar
        this.activeSideChatId = localStorage.getItem('anchorworks_active_side_chat') || null;
        this.activeSideChatDescription = localStorage.getItem('anchorworks_active_side_chat_desc') || '';

        // De-noise feature flag: strip "Essentials:" contract output from chat display
        // Set to false to disable stripping if any issues arise
        this._stripEssentials = true;

        this.init(bootData);
    }

    init(bootData) {
        console.log('🌲 AnchorWorks Console initializing...');
        this.setupEventListeners();
        this.loadSettings();
        this._refreshSideChatIndicator();
        const modeSelect = document.getElementById('chat-mode-select');
        const savedMode = localStorage.getItem('anchorworks_chat_mode') || 'llm';
        if (modeSelect && ['llm', 'grounded', 'reasoning', 'multi_llm'].includes(savedMode)) {
            modeSelect.value = savedMode;
        }

        // ── Apply boot payload (one /api/boot call replaces 8+ separate fetches) ──
        if (bootData) {
            this.serverConnected = true;
            this.updateConnectionStatus(true);
            if (bootData.stats) this.updateStats(bootData.stats);
            this._applyBootHealth(bootData.health);
            this.connectWebSocket();
            this.addLog('Connected to AnchorWorks server', 'success');
        } else {
            // Fallback: boot call failed, do legacy connect
            this.connectToServer();
        }

        this.startStatsRefresh();

        // Checkbox toggle restarts/stops the stats interval cleanly
        document.getElementById('auto-refresh')?.addEventListener('change', () => {
            this.startStatsRefresh();
        });
        window.addEventListener('beforeunload', () => {
            this.stopStatsRefresh();
            if (this._sysmonInterval) clearInterval(this._sysmonInterval);
        });

        this.loadPreviousSummary();       // Show yesterday's recap banner
        this._initAutoDailySummary();    // Auto-request yesterday's summary on new day
        this._historyLoadPromise = this.loadConversationHistory()
            .catch(() => null)
            .finally(() => { this._historyLoaded = true; });
        this.startSystemMonitor();       // Poll PC metrics every 5s
        this.initLexiconBrowser();       // Build alphabet strip, bind search
        this.addLog('System initialized', 'info', { source: 'sys' });

        // ── Block Governance keyboard shortcuts ──
        document.addEventListener('keydown', (e) => {
            const overlay = document.getElementById('note-overlay');
            if (!overlay || !overlay.classList.contains('active')) return;
            if (e.key === 'Escape') { this.closeNoteOverlay(); e.preventDefault(); }
            if (e.key === 'Enter' && e.ctrlKey) { this.saveNote(); e.preventDefault(); }
        });
    }

    /** Apply health data from /api/boot to plugin card dots. */
    _applyBootHealth(health) {
        if (!health) return;
        // Plugin page card dots
        const dotMap = { lakespeak: 'lakespeak', reasoning: 'reasoning_engine', nodes: 'anchorworks_node' };
        for (const [key, pluginId] of Object.entries(dotMap)) {
            const dot = document.getElementById(`prow-${pluginId}-dot`);
            if (dot) dot.className = 'pr-dot ' + (health[key] ? 'ok' : 'down');
        }
    }

    // Load previous day's summary and display as banner
    async loadPreviousSummary() {
        const summaryUrl = `${this.localApiBase}/api/summary/previous`;

        try {
            const response = await fetch(summaryUrl, { credentials: 'include' });
            if (!response.ok) return;
            const data = await response.json();

            const banner = document.getElementById('previous-session-banner');
            if (!banner) return;

            // ONLY show banner if there's an actual summary (silent mode - no prompts)
            if (data.has_summary && data.summary) {
                document.getElementById('session-banner-date').textContent = data.date || '';
                document.getElementById('session-banner-body').textContent = data.summary;

                if (data.pending_days > 0) {
                    const pendingEl = document.getElementById('session-banner-pending');
                    pendingEl.textContent = `⚠ ${data.pending_days} prior day(s) still need summaries generated.`;
                    pendingEl.style.display = 'block';
                }

                banner.style.display = 'block';
                this.addLog('Previous session summary loaded', 'info');
            }
            // Silent: no banner for pending summaries or missing sessions
        } catch (error) {
            // Silent: no console spam
        }
    }

    // Generate a missing summary on-demand
    async generatePreviousSummary(dateStr) {
        const genUrl = `${this.localApiBase}/api/summary/generate`;
        const banner = document.getElementById('previous-session-banner');
        const body = document.getElementById('session-banner-body');

        body.innerHTML = '⏳ Generating summary for ' + dateStr + '...<br><span style="color:#6b8f71;font-size:11px;">This sends the conversation to your local LLM. May take a minute.</span>';

        try {
            const response = await fetch(genUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ date: dateStr })
            });
            const data = await response.json();

            if (data.status === 'ok' && data.summary) {
                body.textContent = data.summary;
                // Update pending count
                const pendingEl = document.getElementById('session-banner-pending');
                pendingEl.style.display = 'none';
                this.addLog('Summary generated for ' + dateStr, 'success');
            } else {
                body.textContent = 'Summary generation failed: ' + (data.error || 'Unknown error');
            }
        } catch (error) {
            body.textContent = 'Could not generate summary: ' + error.message;
        }
    }

    // ── Auto Daily Summary on Login ──────────────────────────
    _initAutoDailySummary() {
        // Restore toggle state
        const toggle = document.getElementById('auto-daily-summary-toggle');
        const enabled = localStorage.getItem('anchorworks_auto_daily_summary') !== 'false'; // default ON
        if (toggle) toggle.checked = enabled;

        const lastEl = document.getElementById('auto-daily-summary-last');
        const lastDate = localStorage.getItem('anchorworks_last_summary_date');
        if (lastEl) lastEl.textContent = lastDate || 'never';

        if (!enabled) return;

        // Check: is today different from last summary request date?
        const today = new Date().toISOString().slice(0, 10);
        if (lastDate === today) return; // Already requested today

        // Delay slightly to let the UI finish loading and model connect
        setTimeout(() => this._autoRequestDailySummary(), 4000);
    }

    async _autoRequestDailySummary() {
        const today = new Date().toISOString().slice(0, 10);
        const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);

        this.addLog(`Auto-requesting summary for ${yesterday}...`, 'info');

        // Send as a normal chat message through whatever mode is active
        const mode = document.getElementById('chat-mode-select')?.value || 'llm';
        const model = localStorage.getItem('gptModel') || '';

        const payload = {
            message: `Daily debriefing for ${yesterday}. Summarize what we worked on, what was accomplished, and what remains open. Bullet points, no fluff.`,
            mode: mode,
            local_model: model,
            hub_enabled: true,
        };

        // If multi_llm, include chain config
        if (mode === 'multi_llm' && typeof buildChainPayload === 'function') {
            const chainFields = buildChainPayload();
            if (chainFields && Array.isArray(chainFields.chain_slots) && chainFields.chain_slots.length > 0) {
                payload.chain_slots = chainFields.chain_slots;
                payload.hub_provider = chainFields.hub_provider || 'ollama';
                payload.hub_enabled = chainFields.hub_enabled !== false;
                payload.plugins_enabled = chainFields.plugins_enabled;
                payload.enabled_plugins = chainFields.enabled_plugins;
                if (chainFields.resolver_enabled) {
                    payload.resolver_enabled  = true;
                    payload.resolver_provider = chainFields.resolver_provider;
                    payload.resolver_model    = chainFields.resolver_model;
                }
            }
        }

        try {
            const bridgeApi = (path) => `${this.serverUrl}${path}`;
            const res = await fetch(bridgeApi('/api/chat/send'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify(payload),
            });

            if (res.ok) {
                const data = await res.json();
                const reply = data.response || '(no debriefing generated)';
                // Inject as the first messages of the day — not a popup
                this.addGptMessage('system', `Daily Debriefing — ${yesterday}`);
                this.addGptMessage('assistant', reply);
                localStorage.setItem('anchorworks_last_summary_date', today);
                const lastEl = document.getElementById('auto-daily-summary-last');
                if (lastEl) lastEl.textContent = today;
                this.addLog('Daily debriefing received', 'success');

                // Follow-up: offer to map unmapped chats
                this._showMapOffer(yesterday);
                // Follow-up: check for stale temp pool checkouts
                this._checkStaleTempSlots();
            } else {
                this.addLog('Daily summary request failed: ' + res.status, 'warning');
            }
        } catch (err) {
            this.addLog('Daily summary error: ' + err.message, 'warning');
        }
    }

    _showMapOffer(targetDate) {
        const offerId = `map-offer-${Date.now()}`;
        const html = `<div class="chain-interrupt-bar" id="${offerId}" style="margin:8px 0;">
            <div style="font-size:13px; margin-bottom:6px;">
                Would you like to map unmapped chats to the data lake?
                <span style="font-size:11px; color:var(--text-secondary);">(616 map + LakeSpeak ingest)</span>
            </div>
            <div style="display:flex;gap:8px;">
                <button class="btn-update" onclick="app._runChatIngest('${offerId}', '${targetDate}')">Yes, map it</button>
                <button class="btn-update" style="opacity:0.6;" onclick="document.getElementById('${offerId}').remove()">Skip</button>
            </div>
        </div>`;

        const chatWindow = document.getElementById('chat-window');
        if (chatWindow) {
            chatWindow.insertAdjacentHTML('beforeend', html);
            chatWindow.scrollTop = chatWindow.scrollHeight;
        }
    }

    async _runChatIngest(offerId, targetDate) {
        const el = document.getElementById(offerId);
        if (el) {
            el.querySelectorAll('button').forEach(b => { b.disabled = true; });
            el.querySelector('div:first-child').textContent = 'Mapping chats to data lake...';
        }

        const bridgeApi = (path) => `${this.serverUrl}${path}`;

        try {
            // Step 1: Run chat ingest (616 map + LakeSpeak)
            const ingestRes = await fetch(bridgeApi('/api/memory/ingest'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ start_date: targetDate, end_date: targetDate }),
            });

            if (!ingestRes.ok) {
                this.addGptMessage('system', `Chat ingest failed: HTTP ${ingestRes.status}`);
                if (el) el.remove();
                return;
            }

            const ingestData = await ingestRes.json();
            const results = ingestData.results || [];
            const mapped = results.filter(r => r.ok);
            const anchors = mapped.reduce((sum, r) => sum + (r.unique_anchors || 0), 0);

            this.addGptMessage('system',
                `Mapped ${mapped.length} day(s) — ${anchors} unique anchors indexed.`);

            // Step 2: Fetch top 20 unmapped words and have the model review them
            const unmatchedRes = await fetch(
                bridgeApi('/api/lexicon/unmatched?limit=20&sort=frequency'),
                { credentials: 'include' }
            );

            if (unmatchedRes.ok) {
                const unmatchedData = await unmatchedRes.json();
                const words = unmatchedData.words || unmatchedData.items || unmatchedData || [];
                const wordList = Array.isArray(words)
                    ? words.map(w => typeof w === 'string' ? w : (w.word || w.anchor || w["to" + "ken"] || '')).filter(Boolean)
                    : [];

                if (wordList.length > 0) {
                    // Send to active model for review
                    const reviewPrompt = `Review these top ${wordList.length} words from today's chat mapping that are NOT in the lexicon yet:\n\n`
                        + wordList.map((w, i) => `${i + 1}. ${w}`).join('\n')
                        + `\n\nFor each word: should it be added to the lexicon, ignored (noise/typo), or flagged for review? Be concise — one line per word.`;

                    const mode = document.getElementById('chat-mode-select')?.value || 'llm';
                    const model = localStorage.getItem('gptModel') || '';

                    const reviewRes = await fetch(bridgeApi('/api/chat/send'), {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        credentials: 'include',
                        body: JSON.stringify({
                            message: reviewPrompt,
                            mode: mode,
                            local_model: model,
                            hub_enabled: true,
                        }),
                    });

                    if (reviewRes.ok) {
                        const reviewData = await reviewRes.json();
                        const reviewReply = reviewData.response || '(no review generated)';
                        this.addGptMessage('system', `Lexicon Review — ${wordList.length} unmapped words`);
                        this.addGptMessage('assistant', reviewReply);
                    }
                } else {
                    this.addGptMessage('system', 'All mapped words are already in the lexicon.');
                }
            }

            if (el) el.remove();
            this.addLog('Chat ingest + lexicon review complete', 'success');

        } catch (err) {
            this.addGptMessage('system', `Chat ingest error: ${err.message}`);
            if (el) el.remove();
        }
    }

    async _checkStaleTempSlots() {
        const bridgeApi = (path) => `${this.serverUrl}${path}`;
        try {
            const res = await fetch(bridgeApi('/api/lexicon/temp/stale?hours=24'), { credentials: 'include' });
            if (!res.ok) return;
            const data = await res.json();
            const stale = data.stale || [];
            if (stale.length === 0) return;

            const staleId = `stale-temp-${Date.now()}`;
            const rows = stale.map(s => {
                const docLabel = s.doc_id ? ` <span style="color:var(--text-secondary);font-size:11px;">(${s.doc_id})</span>` : '';
                const age = s.hours_ago ? ` — ${Math.round(s.hours_ago)}h ago` : '';
                return `<div class="stale-temp-row" data-word="${s.word}" style="display:flex;align-items:center;gap:6px;padding:4px 0;border-bottom:1px solid var(--glass-border);">
                    <span style="flex:1;font-weight:500;">${s.word}${docLabel}${age}</span>
                    <button class="btn-update" style="font-size:11px;padding:2px 8px;background:linear-gradient(135deg,#ffd700,#f0c000);" onclick="app._resolveStaleTempWord('${staleId}','${s.word}','keep')">Keep</button>
                    <button class="btn-update" style="font-size:11px;padding:2px 8px;" onclick="app._resolveStaleTempWord('${staleId}','${s.word}','lake')">Add to Lake</button>
                    <button class="btn-update" style="font-size:11px;padding:2px 8px;opacity:0.7;" onclick="app._resolveStaleTempWord('${staleId}','${s.word}','return')">Return</button>
                </div>`;
            }).join('');

            const html = `<div class="chain-interrupt-bar" id="${staleId}" style="margin:8px 0;max-height:300px;overflow-y:auto;">
                <div style="font-size:13px;font-weight:600;margin-bottom:6px;color:#ffd700;">
                    ⚠ ${stale.length} stale temp slot${stale.length > 1 ? 's' : ''} checked out
                    <span style="font-size:11px;font-weight:normal;color:var(--text-secondary);">— resolve: keep (promote to canonical), add to lake (return + ingest), or return to pool</span>
                </div>
                ${rows}
                <div style="margin-top:8px;display:flex;gap:8px;">
                    <button class="btn-update" style="font-size:11px;" onclick="app._resolveAllStaleTemp('${staleId}','return')">Return All</button>
                    <button class="btn-update" style="font-size:11px;opacity:0.6;" onclick="document.getElementById('${staleId}').remove()">Dismiss</button>
                </div>
            </div>`;

            const chatWindow = document.getElementById('chat-window');
            if (chatWindow) {
                chatWindow.insertAdjacentHTML('beforeend', html);
                chatWindow.scrollTop = chatWindow.scrollHeight;
            }
        } catch (err) {
            this.addLog('Stale temp check error: ' + err.message, 'warning');
        }
    }

    async _resolveStaleTempWord(containerId, word, action) {
        const bridgeApi = (path) => `${this.serverUrl}${path}`;
        try {
            const res = await fetch(bridgeApi('/api/lexicon/temp/resolve'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ word, action }),
            });
            if (!res.ok) {
                this.addLog(`Temp resolve failed for "${word}": HTTP ${res.status}`, 'warning');
                return;
            }
            const data = await res.json();
            // Remove the row from UI
            const container = document.getElementById(containerId);
            if (container) {
                const row = container.querySelector(`.stale-temp-row[data-word="${word}"]`);
                if (row) {
                    row.style.opacity = '0.3';
                    row.style.textDecoration = 'line-through';
                    row.querySelectorAll('button').forEach(b => b.remove());
                    const label = action === 'keep' ? 'promoted' : action === 'lake' ? 'returned + lake' : 'returned';
                    row.insertAdjacentHTML('beforeend', `<span style="font-size:11px;color:var(--text-secondary);">${label}</span>`);
                }
                // If all rows resolved, auto-remove container after 2s
                const remaining = container.querySelectorAll('.stale-temp-row:not([style*="line-through"])');
                if (remaining.length === 0) {
                    setTimeout(() => container.remove(), 2000);
                }
            }
        } catch (err) {
            this.addLog(`Temp resolve error: ${err.message}`, 'warning');
        }
    }

    async _resolveAllStaleTemp(containerId, action) {
        const container = document.getElementById(containerId);
        if (!container) return;
        const rows = container.querySelectorAll('.stale-temp-row:not([style*="line-through"])');
        for (const row of rows) {
            const word = row.dataset.word;
            if (word) await this._resolveStaleTempWord(containerId, word, action);
        }
    }

    // Load conversation history from today's log
    async loadConversationHistory() {
        const historyUrl = `${this.localApiBase}/api/conversation/history`;
        
        try {
            const response = await fetch(historyUrl, { credentials: 'include' });
            if (response.ok) {
                const data = await response.json();
                
                // Pick up user display name early (before Connect)
                if (data.user_display_name) {
                    this.userDisplayName = data.user_display_name;
                }

                if (data.messages && data.messages.length > 0) {
                    console.log(`📜 Loading ${data.messages.length} previous messages...`);
                    
                    // Clear default system message
                    const chat = document.getElementById('gpt-chat');
                    const hasLiveConversation = !!chat?.querySelector('.chat-message.user, .chat-message.assistant');
                    if (hasLiveConversation) {
                        this.addLog('History load skipped to preserve active chat', 'info', { source: 'sys' });
                        return;
                    }
                    chat.innerHTML = '';
                    
                    // Track client→server ID mapping for citation hydration
                    const clientIdMap = {};  // serverId → clientMessageId
                    
                    // Add all previous messages (pass server msg.id for citation anchoring)
                    data.messages.forEach(msg => {
                        // Envelope v2: use actor field (authoritative), fallback to sender
                        const actor = msg.actor || (msg.sender === 'user' ? 'user' : 'assistant');
                        const role = (actor === 'user') ? 'user' : (actor === 'system' ? 'system' : 'assistant');
                        // Seat-derived model name (authoritative), fallback to legacy model field
                        const seatModel = msg.seat ? `${msg.seat.model}` : null;
                        const seatChip = msg.seat ? `${msg.seat.provider}` : null;
                        const modelName = seatModel || msg.model || null;
                        const clientId = this.addGptMessage(role, msg.content, null, null, msg.timestamp, modelName, msg.display_name, null, msg.id, seatChip, msg.actor);
                        if (clientId && msg.id != null) {
                            clientIdMap[String(msg.id)] = clientId;
                        }
                    });
                    
                    // Hydrate persisted citations from sidecar
                    const citesByBlock = data.citations_by_block || {};
                    for (const [blockKey, cites] of Object.entries(citesByBlock)) {
                        // blockKey = "serverId:blockId"
                        const sepIdx = blockKey.indexOf(':');
                        if (sepIdx < 0) continue;
                        const srvId = blockKey.slice(0, sepIdx);
                        const blockId = blockKey.slice(sepIdx + 1);
                        const clientMsgId = clientIdMap[srvId];
                        if (!clientMsgId) continue;
                        const msgData = this._messageStore.get(clientMsgId);
                        if (!msgData) continue;
                        
                        if (!msgData.citesByBlock[blockId]) msgData.citesByBlock[blockId] = [];
                        for (const cite of cites) {
                            // Avoid duplicates
                            if (!msgData.citesByBlock[blockId].some(c => c.cite_id === cite.cite_id)) {
                                msgData.citesByBlock[blockId].push(cite);
                            }
                        }
                    }
                    
                    // Re-render messages that got citations
                    for (const clientId of Object.values(clientIdMap)) {
                        const msgData = this._messageStore.get(clientId);
                        if (msgData && Object.keys(msgData.citesByBlock).length > 0) {
                            this._rerenderMessage(clientId);
                        }
                    }
                    
                    // Scroll to bottom after full history load + citation hydration
                    requestAnimationFrame(() => {
                        const chatEl = document.getElementById('gpt-chat');
                        if (chatEl) chatEl.scrollTop = chatEl.scrollHeight;
                    });

                    this.addLog(`Loaded ${data.messages.length} messages from today's conversation`, 'success');
                } else {
                    // No history, show welcome message
                    this.addGptMessage('system', 'AnchorWorks ready. No previous conversation found for today.');
                }
            }
        } catch (error) {
            console.log('Could not load conversation history:', error);
            // Fail silently - just start fresh
            this.addGptMessage('system', 'AnchorWorks ready. Starting fresh conversation.');
        }
    }

    _refreshSideChatIndicator() {
        const chip = document.getElementById('side-chat-indicator');
        if (!chip) return;
        if (this.activeSideChatId) {
            const desc = this.activeSideChatDescription || this.activeSideChatId;
            chip.textContent = `side: ${desc}`;
            chip.style.color = 'var(--warning)';
            chip.style.background = 'rgba(255, 180, 0, 0.15)';
        } else {
            chip.textContent = 'main';
            chip.style.color = 'var(--text-secondary)';
            chip.style.background = 'var(--accent-bg)';
        }
    }

    _setActiveSideChat(sideChatId, description = '') {
        this.activeSideChatId = sideChatId || null;
        this.activeSideChatDescription = description || '';
        if (this.activeSideChatId) {
            localStorage.setItem('anchorworks_active_side_chat', this.activeSideChatId);
            localStorage.setItem('anchorworks_active_side_chat_desc', this.activeSideChatDescription);
        } else {
            localStorage.removeItem('anchorworks_active_side_chat');
            localStorage.removeItem('anchorworks_active_side_chat_desc');
        }
        this._refreshSideChatIndicator();
    }

    _clearActiveSideChat() {
        this._setActiveSideChat(null, '');
    }

    async startSideChatFromContext({ fromDay, messageId = 0, content = '', actor = 'assistant', description = '' }) {
        const payload = {
            from_day: fromDay,
            message_id: messageId,
            content,
            actor,
            description,
        };
        const resp = await fetch(`${this.localApiBase}/api/conversation/side/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify(payload),
        });
        const data = await resp.json();
        if (!resp.ok || !data.ok) {
            throw new Error(data.detail || 'side chat start failed');
        }
        this._setActiveSideChat(data.side_chat_id, data.description || description);
        return data;
    }

    // Server Connection
    async connectToServer() {
        try {
            const response = await fetch(`${this.serverUrl}/api/stats`);
            if (response.ok) {
                const stats = await response.json();
                this.serverConnected = true;
                this.updateConnectionStatus(true);
                this.updateStats(stats);
                this.addLog('Connected to AnchorWorks server', 'success');
                this.connectWebSocket();
            }
        } catch (error) {
            this.serverConnected = false;
            this.updateConnectionStatus(false);
            this.addLog('Server connection failed - retrying in 5s', 'error', { source: 'srv', detail: error.message });
            setTimeout(() => this.connectToServer(), 5000);
        }
    }

    connectWebSocket() {
        const wsUrl = this.serverUrl.replace('http', 'ws') + '/ws/stream';
        this.websocket = new WebSocket(wsUrl);

        this.websocket.onopen = () => {
            if (this._wsWasConnected) {
                this.addLog('Bridge reconnected — live session preserved', 'success');
                this.updateStats().catch(() => {});
                return;
            }
            this._wsWasConnected = true;
            this.addLog('WebSocket connected', 'success');
        };

        this.websocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleWebSocketMessage(data);
        };

        this.websocket.onerror = (error) => {
            this.addLog('WebSocket error', 'error');
        };

        this.websocket.onclose = () => {
            this.addLog('WebSocket disconnected - reconnecting...', 'warning');
            setTimeout(() => this.connectWebSocket(), 3000);
        };
    }

    handleWebSocketMessage(data) {
        // Server sends 'evt' field, not 'type'
        if (data.evt === 'job-progress') {
            this.updateJobProgress(data);
        } else if (data.evt === 'job-complete') {
            this.addLog(`Job complete: ${data.job_id}`, 'success');
            document.getElementById('mapping-progress').style.display = 'none';
        } else if (data.evt === 'job-start') {
            this.addLog(`Job started: ${data.job_id} (${data.count} files)`, 'info');
        } else if (data.evt === 'job-error') {
            this.addLog(`Job failed: ${data.error}`, 'error');
        }
    }

    updateConnectionStatus(connected) {
        // Connection state is now reflected by header health pills
    }

    // Stats and Monitoring
    async updateStats(stats = null) {
        if (!stats) {
            try {
                const response = await fetch(`${this.serverUrl}/api/stats`);
                stats = await response.json();
            } catch (error) {
                return;
            }
        }

        // Lexicon stat
        const statLexicon = document.getElementById('stat-lexicon');
        if (statLexicon) statLexicon.textContent = stats.entries?.toLocaleString() || '0';

        const statDevice = document.getElementById('stat-device');
        if (statDevice) statDevice.textContent = (stats.canonical_count || 0).toLocaleString();

        // External packs are disabled in the active AnchorWorks runtime
        const packCounts = stats.domain_pack_entries || {};
        const packTotal = Object.values(packCounts).reduce((a, b) => a + b, 0);
        const packLabel = Object.entries(packCounts).map(([k, v]) => `${k}: ${v.toLocaleString()}`).join(' | ') || 'none';
        const slotsEl = document.getElementById('stat-slots-total');
        if (slotsEl) {
            slotsEl.textContent = packTotal.toLocaleString();
            slotsEl.title = packLabel;
        }

        // Disk size (canonical + packs)
        const diskBytes = stats.disk_size_bytes || 0;
        const diskLabel = diskBytes >= 1073741824
            ? (diskBytes / 1073741824).toFixed(2) + ' GB'
            : (diskBytes / 1048576).toFixed(1) + ' MB';
        const statSlots = document.getElementById('stat-slots-assigned');
        if (statSlots) statSlots.textContent = diskLabel;

        // Pool available
        const statAvail = document.getElementById('stat-slots-available');
        if (statAvail) statAvail.textContent = (stats.pool_available || 0).toLocaleString();

        // Data lake meta
        const lake = stats.data_lake || {};
        const lakeSize = lake.size_bytes >= 1048576
            ? (lake.size_bytes / 1048576).toFixed(1) + ' MB'
            : ((lake.size_bytes || 0) / 1024).toFixed(0) + ' KB';
        const jobsEl = document.getElementById('stat-jobs');
        if (jobsEl) {
            jobsEl.textContent = `${lake.files || 0} files`;
            jobsEl.title = `${lake.folders || 0} folders | ${lakeSize}`;
        }

        // Available storage
        const storageEl = document.getElementById('stat-coverage');
        const storage = stats.storage || {};
        const freeBytes = storage.total_free_bytes || 0;
        const capBytes = storage.total_capacity_bytes || 0;
        const freeLabel = freeBytes >= 1073741824
            ? (freeBytes / 1073741824).toFixed(1) + ' GB'
            : (freeBytes / 1048576).toFixed(0) + ' MB';
        const driveDetail = Object.entries(storage.drives || {}).map(([d, b]) => {
            if (b < 0) return `${d} offline`;
            return `${d} ${(b / 1073741824).toFixed(1)} GB free`;
        }).join(' | ');
        if (storageEl) {
            storageEl.textContent = freeLabel;
            storageEl.title = driveDetail;
            storageEl.style.color = '';
        }
    }

    startStatsRefresh() {
        // Clear any existing interval first (prevents stacking on reconnect)
        if (this._statsInterval) {
            clearInterval(this._statsInterval);
            this._statsInterval = null;
        }

        const auto = document.getElementById('auto-refresh');
        if (!auto || !auto.checked) return;

        // 30s is plenty — stats only change on lexicon reload or map runs
        this._statsInterval = setInterval(() => {
            if (!this.serverConnected) return;
            if (document.hidden) return;
            this.updateStats();
        }, 30000);
    }

    stopStatsRefresh() {
        if (this._statsInterval) {
            clearInterval(this._statsInterval);
            this._statsInterval = null;
        }
    }

    // File Upload and Job Submission
    async submitMappingJob() {
        const fileInput = document.getElementById('file-input');
        const textInput = document.getElementById('text-input');
        const jobName = document.getElementById('job-name').value || 'manual_job';

        let content = textInput.value;
        let filename = jobName;
        this.currentJob = jobName;

        if (fileInput.files.length > 0) {
            const file = fileInput.files[0];
            content = await file.text();
            filename = file.name;
        }

        if (!content.trim()) {
            alert('Please provide text or upload a file');
            return;
        }

        this.addLog(`Starting mapping: ${filename}`, 'info');
        
        document.getElementById('mapping-progress').style.display = 'block';
        document.getElementById('mapping-results').style.display = 'none';

        try {
            // Use /api/map for text content (synchronous)
            const response = await fetch(`${this.serverUrl}/api/map`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    text: content,
                    source: filename
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const result = await response.json();
            this.addLog(`Mapping completed for ${filename}`, 'success');
            this.currentReport = result;
            this.displayDirectResults(result);
        } catch (error) {
            this.addLog(`Mapping failed: ${error.message}`, 'error', { source: 'map', detail: error.stack || error.message });
            document.getElementById('mapping-progress').style.display = 'none';
        }
    }

    displayDirectResults(result) {
        // Display results from synchronous /api/map call
        document.getElementById('mapping-progress').style.display = 'none';
        document.getElementById('mapping-results').style.display = 'block';

        const totalAnchors = result.total_anchors || result["total_" + "to" + "kens"] || 0;
        const items = result.items || {};
        const anchors = Object.keys(items);
        const mappedAnchors = anchors.filter(k => items[k].lexicon_payload !== null);
        const unmappedCount = anchors.length - mappedAnchors.length;
        const coverage = anchors.length > 0
            ? ((mappedAnchors.length / anchors.length) * 100).toFixed(1)
            : 0;

        document.getElementById('result-anchors').textContent = totalAnchors.toLocaleString();
        document.getElementById('result-coverage').textContent = `${coverage}%`;
        document.getElementById('result-unmapped').textContent = unmappedCount.toLocaleString();

        // Update global stats
        const jobsEl = document.getElementById('stat-jobs');
        if (jobsEl) {
            const currentJobs = parseInt(jobsEl.textContent) || 0;
            jobsEl.textContent = currentJobs + 1;
        }
        const coverageEl = document.getElementById('stat-coverage');
        if (coverageEl) coverageEl.textContent = `${coverage}%`;
    }

    updateJobProgress(data) {
        // Handle job-progress WebSocket messages for batch file processing
        if (data.processed !== undefined && data.total !== undefined) {
            const progress = Math.round((data.processed / data.total) * 100);
            document.getElementById('progress-fill').style.width = `${progress}%`;
            document.getElementById('progress-text').textContent = `Processing... ${data.processed}/${data.total} (${progress}%)`;
        }
    }



    downloadReport() {
        if (!this.currentReport) {
            alert('No report available');
            return;
        }

        const blob = new Blob([JSON.stringify(this.currentReport, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${this.currentJob}_616_map.json`;
        a.click();
        URL.revokeObjectURL(url);
        this.addLog('Report downloaded', 'success');
    }

    async commitToDataLake() {
        if (!this.currentReport) {
            alert('No report available. Run a mapping job first.');
            return;
        }

        try {
            const response = await fetch(`${this.serverUrl}/api/map/commit`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    job_name: this.currentJob || '616_map',
                    report: this.currentReport
                })
            });

            const result = await response.json();

            if (result.status === 'committed') {
                this.addLog(`Committed to data lake: ${result.path}`, 'success');
            } else {
                this.addLog(`Commit failed: ${result.detail || 'Unknown error'}`, 'error');
            }
        } catch (error) {
            this.addLog(`Commit error: ${error.message}`, 'error', { source: 'lake', detail: error.stack || error.message });
        }
    }



    // Local LLM Integration
    async testGptConnection() {
        const baseUrl = this.localApiBase;
        this.addLog('Testing LLM connection...', 'info');

        try {
            const tagsResp = await fetch(`${baseUrl}/api/tags`, { credentials: 'include' });
            if (!tagsResp.ok) throw new Error('Cannot reach server');
            const tagsData = await tagsResp.json();
            const models = tagsData.models || [];

            const savedModel = localStorage.getItem('gptModel');
            let activeModel = null;
            models.forEach(m => { if (m.active) activeModel = m.name; });

            // Determine best model: active > saved > first available
            const bestModel = activeModel || savedModel || (models[0] && models[0].name) || '';
            localStorage.setItem('gptModel', bestModel);
            this.gptModel = bestModel;

            const healthResp = await fetch(`${baseUrl}/health`);
            if (healthResp.ok) {
                const healthData = await healthResp.json();
                this.userDisplayName = healthData.user_display_name || null;
                this.gptConnected = true;
                this.addLog(`Connected. ${models.length} model(s). Active: ${bestModel}`, 'success');
                this.addGptMessage('system', `Connected to AnchorWorks LLM. Active model: ${bestModel}. ${models.length} model(s) available.`);
                updateLocalProvider(models, bestModel);
                window.chainSetLocalModels?.(models, bestModel);
            } else {
                throw new Error('Health check failed');
            }
        } catch (error) {
            this.gptConnected = false;
            this.addLog(`LLM connection failed: ${error.message}`, 'error', { source: 'llm', detail: error.stack || error.message });
        }
    }

    async switchModel(modelName) {
        const baseUrl = this.localApiBase;
        this.addLog(`Switching model to ${modelName}...`, 'info');
        this.addGptMessage('system', `Switching to ${modelName}... (this may take a moment)`);

        try {
            const resp = await fetch(`${baseUrl}/api/model/switch`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ model: modelName }),
            });
            if (!resp.ok) {
                const err = await resp.json();
                throw new Error(err.detail || 'Switch failed');
            }
            const data = await resp.json();
            this.addLog(`Model switched to ${data.model} (${data.size_gb}GB)`, 'success');
            this.addGptMessage('system', `Now using ${data.model} (${data.size_gb}GB). Ready.`);
            localStorage.setItem('gptModel', data.model);
            this.gptModel = data.model;
            refreshModelList();
        } catch (error) {
            this.addLog(`Model switch failed: ${error.message}`, 'error');
        }
    }

    async sendGptMessage() {
        const prompt = document.getElementById('gpt-prompt').value;
        if (!prompt.trim()) return;

        const modeSelect = document.getElementById('chat-mode-select');
        const selectedMode = (modeSelect?.value || localStorage.getItem('anchorworks_chat_mode') || 'llm').trim();
        const mode = ['llm', 'grounded', 'reasoning', 'multi_llm'].includes(selectedMode) ? selectedMode : 'llm';
        localStorage.setItem('anchorworks_chat_mode', mode);
        // Hub model is the sole model authority for all modes
        const hubModel = document.getElementById('chain-hub-model')?.value
            || (typeof getChainConfig === 'function' && getChainConfig()?.local_model)
            || localStorage.getItem('gptModel')
            || this.gptModel
            || '';

        if (this._historyLoadPromise) {
            await this._historyLoadPromise;
            this._historyLoadPromise = null;
        }

        this.addGptMessage('user', prompt, null, null, null, null, this.userDisplayName);
        document.getElementById('gpt-prompt').value = '';

        // Show typing indicator
        const thinkingEl = this._showThinking();

        // ── Normalized payload ────────────────────────────────
        const chainCfg = getChainConfig();
        const payload = {
            message: prompt,
            mode: mode,
            local_model: hubModel,
            hub_provider: chainCfg?.hub_provider || 'ollama',
            session_id: 'ui',
            tools_enabled: localStorage.getItem('anchorworks_tools_enabled') === 'true',
            topk: 8,
        };
        if (this.activeSideChatId) {
            payload.side_chat_id = this.activeSideChatId;
        }

        // Attach inference params + generation contract
        if (typeof inferenceCtrl !== 'undefined' && inferenceCtrl) {
            payload.inference_params = inferenceCtrl.getParams();
            const contract = inferenceCtrl.getContract();
            if (contract && contract.text) {
                payload.generation_contract = contract.text;
            }
        }

        // ── Chain builder fields (multi_llm only) ───────────
        let chainFields = null;
        if (typeof buildChainPayload === 'function') {
            chainFields = buildChainPayload();
        }
        if (mode === 'multi_llm') {
            if (!chainFields || !Array.isArray(chainFields.chain_slots) || chainFields.chain_slots.length === 0) {
                this.addGptMessage('system', 'multi_llm requires at least one enabled slot in Chain Builder.');
                return;
            }
            if (chainFields) {
                payload.chain_slots     = chainFields.chain_slots;
                payload.hub_provider    = chainFields.hub_provider || 'ollama';
                payload.hub_enabled     = chainFields.hub_enabled !== false;
                payload.plugins_enabled = chainFields.plugins_enabled;
                payload.enabled_plugins = chainFields.enabled_plugins;
                if (chainFields.resolver_enabled) {
                    payload.resolver_enabled  = true;
                    payload.resolver_provider = chainFields.resolver_provider;
                    payload.resolver_model    = chainFields.resolver_model;
                }
            }
        }

        // ── Single fetch ──────────────────────────────────────
        try {
            const res = await tracedFetch(bridgeApi('/api/chat/send'), {  // DEBUGWIRE:TRACE
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify(payload),
            });

            const data = await res.json();
            this._removeThinking(thinkingEl);

            // ── Unified error handling ────────────────────────
            if (data.error) {
                const errMsg = data.error.message || JSON.stringify(data.error);
                this.addGptMessage('system', `${mode}: ${errMsg}`);
                return;
            }

            // ── Chain contributions (multi-mind) ────────────────
            if (data.contributions && data.contributions.length > 0) {
                const now = new Date().toISOString().replace('T', ' ').slice(0, 19) + 'Z';
                for (let ci = 0; ci < data.contributions.length; ci++) {
                    const contrib = data.contributions[ci];
                    const isHub = contrib.author === 'hub';

                    // Position label: HUB / SLOT 1 / SLOT 2 ...
                    const posLabel = isHub ? 'HUB' : contrib.author.replace('slot_', 'SLOT ').toUpperCase();
                    const provName = contrib.provider || 'local';
                    const modelName = contrib.model || '?';
                    const msLabel = contrib.ms ? `${contrib.ms}ms` : '';
                    const headerClass = isHub ? 'hub' : 'slot';

                    // Tool chips
                    let toolChips = '';
                    if (Array.isArray(contrib.tools_used) && contrib.tools_used.length) {
                        const names = contrib.tools_used.map(t => typeof t === 'string' ? t : t.tool || '?');
                        toolChips = `<span class="chain-contrib-tools">[${names.join(', ')}]</span>`;
                    }

                    // Followup indicator
                    const followupChip = contrib.followup_to
                        ? `<span class="chain-contrib-followup">reply to ${this.escapeHtml(contrib.followup_to)}</span>`
                        : '';

                    const chainHeader = `<div class="chain-contrib-header ${headerClass}">`
                        + `<span class="chain-contrib-pos">${posLabel}</span>`
                        + `<span class="chain-contrib-identity">${this.escapeHtml(provName)} / ${this.escapeHtml(modelName)}</span>`
                        + toolChips + followupChip
                        + `<span class="chain-contrib-ms">${msLabel}</span>`
                        + `<span class="chain-contrib-ts">${now}</span>`
                        + `</div>`;

                    const content = contrib.content || '(no response)';
                    const providerMap = { ollama: 'ollama', openai: 'openai', anthropic: 'anthropic', google: 'google', xai: 'xai' };
                    const seatProv = providerMap[contrib.provider] || contrib.provider || null;

                    const msgId = this.addGptMessage('assistant', content, null, null, null,
                                       contrib.model || null, null, null, null, seatProv);
                    // Inject chain header as rendered HTML before blockified content
                    if (msgId) {
                        const msgEl = document.querySelector(`[data-msg-id="${msgId}"]`);
                        const contentDiv = msgEl?.querySelector('.message-content');
                        if (contentDiv) contentDiv.insertAdjacentHTML('afterbegin', chainHeader);
                    }
                }

                // ── Chain interrupt: show steering input ──
                if (data.chain_state) {
                    this._showChainInterrupt(data.chain_state, payload);
                }
            } else {
                // ── Single response (non-chain / backward compat) ──
                const reply = data.response || 'No response';

                const retrievalCtx = {
                    source:          data.source || mode,
                    mode:            data.mode || mode,
                    answer_frame:    data.answer_frame || null,
                    reasoning_trace: data.reasoning_trace || null,
                    citations:       data.citations || [],
                    grounded:        data.grounded || false,
                    verdict:         data.verdict || null,
                };

                if (data.reasoning_trace) {
                    retrievalCtx.archive_chars     = data.reasoning_trace.archive_chars || 0;
                    retrievalCtx.archive_hits      = data.reasoning_trace.archive_hits || 0;
                    retrievalCtx.retrieval_context = data.reasoning_trace.retrieval_context || null;
                }

                const displayModel = data.seat?.model || data.reasoning_trace?.model || hubModel;
                const seatProvider = data.seat?.provider || null;

                const msgId = this.addGptMessage('assistant', reply, null, retrievalCtx, null,
                                   displayModel, null, null, null, seatProvider);
                // Typewriter reveal for new assistant messages
                if (msgId) {
                    const msgEl = document.querySelector(`[data-msg-id="${msgId}"]`);
                    if (msgEl) this._typewriteReveal(msgEl);
                }
            }

        } catch (e) {
            this._removeThinking(thinkingEl);
            this.addGptMessage('system', `Error: ${e.message}`);
        }
    }

    // ── Typing indicator ──────────────────────────────────
    _showThinking() {
        const chat = document.getElementById('gpt-chat');
        const el = document.createElement('div');
        el.className = 'chat-message assistant thinking-indicator';
        el.innerHTML = `
            <div class="message-header"><span>thinking</span></div>
            <div class="message-content"><span class="typing-dots"><span>.</span><span>.</span><span>.</span></span></div>
        `;
        chat.appendChild(el);
        requestAnimationFrame(() => { chat.scrollTop = chat.scrollHeight; });
        return el;
    }

    _removeThinking(el) {
        if (el && el.parentNode) el.remove();
    }

    // ── Typewriter reveal for assistant messages ──────────
    _typewriteReveal(messageDiv) {
        const contentEl = messageDiv.querySelector('.message-content');
        if (!contentEl) return;

        const blocks = contentEl.querySelectorAll('.msg-block');
        if (!blocks.length) return;

        // Hide all blocks initially
        blocks.forEach(b => {
            b.style.opacity = '0';
            b.style.transform = 'translateY(6px)';
            b.style.transition = 'opacity 0.25s ease, transform 0.25s ease';
        });

        // Reveal blocks one by one with stagger
        const delay = Math.min(120, 600 / blocks.length);
        blocks.forEach((b, i) => {
            setTimeout(() => {
                b.style.opacity = '1';
                b.style.transform = 'translateY(0)';
                const chat = document.getElementById('gpt-chat');
                if (chat) chat.scrollTop = chat.scrollHeight;
            }, i * delay);
        });
    }

    generate616Summary() {
        if (!this.currentReport) return 'No mapping data available.';

        const items = this.currentReport.items || {};
        const anchors = Object.keys(items);
        const totalAnchors = this.currentReport.total_anchors || this.currentReport["total_" + "to" + "kens"] || 0;
        const mappedAnchors = anchors.filter(k => items[k].lexicon_payload !== null);
        const coverage = anchors.length > 0
            ? ((mappedAnchors.length / anchors.length) * 100).toFixed(1)
            : 0;

        // Get top anchors by total window count
        const topWords = anchors
            .map(k => {
                const entry = items[k];
                let total = 0;
                for (const side of ['before', 'after']) {
                    for (const bucket of Object.values(entry[side] || {})) {
                        for (const item of bucket) {
                            total += item.count || 0;
                        }
                    }
                }
                return { word: entry.lexicon_word || k, total };
            })
            .sort((a, b) => b.total - a.total)
            .slice(0, 10)
            .map(t => t.word);

        return `Document Analysis:
- Total anchors: ${totalAnchors}
- Unique anchors: ${anchors.length}
- In lexicon: ${mappedAnchors.length} (${coverage}%)
- Top anchors: ${topWords.join(', ')}

Analyzed using 6-1-6 contextual mapping with paragraph boundary enforcement.`;
    }

    injectAnchorWorksContext() {
        // Disabled in Local Chat - use 6-1-6 Mapping panel instead
        // Button preserved as hook for future plugin routing architecture
        return;
    }

    addGptMessage(role, content, citeReport = null, retrievalCtx = null, serverTimestamp = null, modelName = null, displayName = null, infParams = null, serverId = null, seatProvider = null, actorField = null) {
        // System messages → activity log, never chat.
        // Keeps chat clean for reading + data lake ingestion.
        if (role === 'system') {
            const level = /error|fail/i.test(content) ? 'error' : 'info';
            this.addLog(content, level, { source: 'sys' });
            return null;
        }

        const chat = document.getElementById('gpt-chat');
        const timestamp = this.formatUtcTime(serverTimestamp);

        // De-noise: Strip "Essentials:" contract output from assistant messages
        if (role === 'assistant' && this._stripEssentials) {
            const essentialsMatch = content.match(/\n\s*Essentials:\s*\n([\s\S]*?)(?=\n\n|\n[A-Z]|$)/);
            if (essentialsMatch) {
                const extractedEssentials = essentialsMatch[0].trim();
                content = content.replace(essentialsMatch[0], '').trim();
                infParams = infParams || {};
                infParams.essentials = extractedEssentials;
            }
        }

        // Build header label: identity-first, never from display_name for role
        let headerLabel;
        let missingMetaChip = '';
        if (role === 'assistant') {
            headerLabel = modelName ? this.escapeHtml(modelName) : 'assistant';
            // MISSING META: assistant with no model/seat identity
            if (!modelName && !seatProvider && actorField !== 'system') {
                missingMetaChip = '<span class="msg-missing-meta">MISSING META</span>';
            }
        } else if (role === 'user') {
            // Display name is decorative — actor was already determined from 'actor' field
            headerLabel = displayName ? this.escapeHtml(displayName) : (this.userDisplayName || 'user');
        } else {
            headerLabel = role.toUpperCase();
        }

        // Source chip: seat provider (authoritative) or fallback to retrievalCtx
        let sourceChip = '';
        if (role === 'assistant' && seatProvider) {
            // Seat-based chip (envelope v2)
            const p = seatProvider.toLowerCase();
            if (p === 'openai') sourceChip = '<span class="msg-source-chip cloud">\u2601 OpenAI</span>';
            else if (p === 'anthropic') sourceChip = '<span class="msg-source-chip cloud">\u2601 Claude</span>';
            else if (p === 'google') sourceChip = '<span class="msg-source-chip cloud">\u2601 Gemini</span>';
            else if (p === 'ollama') sourceChip = '<span class="msg-source-chip local">Local</span>';
            else if (p === 'reasoning_engine') sourceChip = '<span class="msg-source-chip engine">Reasoning</span>';
            else sourceChip = `<span class="msg-source-chip engine">${this.escapeHtml(p)}</span>`;
        } else if (role === 'assistant' && retrievalCtx) {
            // Legacy fallback from retrievalCtx
            const src = retrievalCtx.source || '';
            const mode = retrievalCtx.mode || '';
            if (src === 'openai_api' || mode === 'openai') {
                sourceChip = '<span class="msg-source-chip cloud">\u2601 OpenAI</span>';
            } else if (src === 'anthropic_api' || mode === 'claude') {
                sourceChip = '<span class="msg-source-chip cloud">\u2601 Claude</span>';
            } else if (src === 'ollama' || mode === 'llm') {
                sourceChip = '<span class="msg-source-chip local">Local</span>';
            } else if (src === 'reasoning_engine' || mode === 'reasoning') {
                sourceChip = '<span class="msg-source-chip engine">Reasoning</span>';
            } else if (src === 'lakespeak' || mode === 'grounded') {
                sourceChip = '<span class="msg-source-chip engine">GroveSpeak</span>';
            } else if (src === 'chat_packs' || mode === 'chat_pack') {
                sourceChip = '<span class="msg-source-chip engine">Chat Pack</span>';
            }
        }

        // Inference metadata row for assistant messages
        let metaHtml = '';
        if (role === 'assistant' && infParams) {
            const parts = [];
            if (infParams.temperature !== undefined) parts.push(`temp:${infParams.temperature}`);
            if (infParams.top_p !== undefined && infParams.top_p !== 1.0) parts.push(`p:${infParams.top_p}`);
            if (infParams.top_k !== undefined && infParams.top_k !== 40) parts.push(`k:${infParams.top_k}`);
            if (infParams.repeat_penalty !== undefined && infParams.repeat_penalty !== 1.1) parts.push(`rpt:${infParams.repeat_penalty}`);
            if (infParams.max_output !== undefined) parts.push(`max:${infParams.max_output}`);
            else if (infParams["max_" + "to" + "kens"] !== undefined) parts.push(`max:${infParams["max_" + "to" + "kens"]}`);
            if (infParams.seed !== undefined && infParams.seed >= 0) parts.push(`seed:${infParams.seed}`);
            if (infParams.mirostat_mode > 0) parts.push(`miro:v${infParams.mirostat_mode}`);
            if (parts.length > 0) {
                metaHtml = `<div class="ctrl-meta-row">${parts.map(p => `<span>${p}</span>`).join('')}</div>`;
            }
        }

        // Build content HTML — block governance for assistant, plain for others
        let contentHtml;
        let messageId = null;

        if (role === 'assistant') {
            messageId = `msg_${++this._msgCounter}_${Date.now()}`;
            const blocks = this.blockify(content);
            const notesByBlock = {};

            // Store BEFORE render so renderBlocksHtml can read role
            this._messageStore.set(messageId, {
                blocks,
                notesByBlock,
                citesByBlock: {},
                revisionLinks: {},
                role,
                text: content,
                citeReport: citeReport || null,
                element: null,
                serverId: serverId,
            });

            contentHtml = this.renderBlocksHtml(blocks, messageId, notesByBlock, citeReport);
        } else if (role === 'user') {
            messageId = `msg_${++this._msgCounter}_${Date.now()}`;
            const blocks = this.blockify(content);
            const notesByBlock = {};

            // Store BEFORE render so renderBlocksHtml can read role
            this._messageStore.set(messageId, {
                blocks,
                notesByBlock,
                citesByBlock: {},
                revisionLinks: {},
                role,
                text: content,
                citeReport: null,
                element: null,
                serverId: serverId,
            });

            contentHtml = this.renderBlocksHtml(blocks, messageId, notesByBlock, null);
        } else {
            // system: escape only
            contentHtml = this.escapeHtml(content);
        }

        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message ${role}`;
        if (messageId) messageDiv.dataset.msgId = messageId;
        messageDiv.innerHTML = `
            <div class="message-header">
                <span>${headerLabel}${sourceChip}${missingMetaChip}</span>
                <span>${timestamp}</span>
            </div>
            <div class="message-content">${contentHtml}</div>
            ${metaHtml}
        `;

        chat.appendChild(messageDiv);
        requestAnimationFrame(() => { chat.scrollTop = chat.scrollHeight; });

        // Routing telemetry badge
        if (role === 'assistant' && retrievalCtx?.reasoning_trace?.routing) {
            const rt = retrievalCtx.reasoning_trace.routing;
            const stages = (rt.stages || [])
                .filter(s => s.enabled)
                .map(s => `${s.id}: ${s.ms}ms`)
                .join(' | ');
            if (stages) {
                const badge = document.createElement('div');
                badge.style.cssText = 'font-size:11px;color:var(--text-secondary);margin-top:6px;padding:4px 8px;background:rgba(255,165,0,0.1);border-radius:4px;font-family:monospace;';
                badge.textContent = `Route: ${rt.profile || '?'} | ${stages}`;
                messageDiv.appendChild(badge);
            }
        }

        // Ollama performance meter
        if (role === 'assistant' && retrievalCtx?.reasoning_trace?.ollama) {
            const ol = retrievalCtx.reasoning_trace.ollama;
            const parts = [];
            if (ol.prompt_eval_count) parts.push(`in:${ol.prompt_eval_count}`);
            if (ol.eval_count) parts.push(`out:${ol.eval_count}`);
            if (ol.anchors_per_second) parts.push(`${ol.anchors_per_second} anchors/s`);
            else if (ol["to" + "kens_per_second"]) parts.push(`${ol["to" + "kens_per_second"]} units/s`);
            if (ol.eval_duration_ms) parts.push(`gen:${(ol.eval_duration_ms / 1000).toFixed(1)}s`);
            if (ol.load_duration_ms > 500) parts.push(`load:${(ol.load_duration_ms / 1000).toFixed(1)}s`);
            if (parts.length) {
                const meter = document.createElement('div');
                meter.style.cssText = 'font-size:11px;color:var(--text-secondary);margin-top:4px;padding:4px 8px;background:rgba(100,200,255,0.08);border-radius:4px;font-family:monospace;';
                meter.textContent = parts.join(' · ');
                messageDiv.appendChild(meter);
            }
        }

        // Back-link element ref into store
        if (messageId && this._messageStore.has(messageId)) {
            this._messageStore.get(messageId).element = messageDiv;
        }

        // Store last assistant content for continuation
        if (role === 'assistant') {
            this._lastAssistantContent = content;
        }

        // Attach badge click handlers and populate citations pane
        if (role === 'assistant') {
            const hasCitations = citeReport && citeReport.citations && citeReport.citations.length > 0;
            const hasRetrieval = retrievalCtx && retrievalCtx.hits && retrievalCtx.hits.length > 0;

            if (hasCitations) {
                // Stream 1: Cited-by-model
                this.lastCiteReport = citeReport;
                this.lastCiteIndex = this.buildCitationIndex(citeReport);
                this.selectedCite = null;
                this.populateCitationPane(citeReport, null);
                this.attachBadgeHandlers(messageDiv);
            } else if (hasRetrieval) {
                // Stream 2: Retrieved-context (model didn't cite, but we have hits)
                this.lastCiteReport = null;
                this.lastCiteIndex = null;
                this.selectedCite = null;
                this.populateCitationPane(null, retrievalCtx);
            } else {
                this.populateCitationPane(null, null);
            }
        }

        return messageId;
    }

    // Loop detection state
    _prevAssistantContent = null;
    _loopCount = 0;

    // ── Block Governance Layer ────────────────────────────────
    _msgCounter = 0;
    _messageStore = new Map();  // message_id -> { blocks, notesByBlock, role, text, citeReport, element }

    // ── History Queue (immutable source, writes to today) ──────
    _historyQueue = [];
    _historyQueueSeq = 0;
    _historySessionId = typeof crypto !== 'undefined' && crypto.randomUUID
        ? crypto.randomUUID() : 'sess_' + Date.now();

    // ── Blockifier ────────────────────────────────────────
    // Pure function: text -> blocks[]
    blockify(text) {
        const raw = (text || '').replace(/\r\n/g, '\n').trim();
        if (!raw) return [{ block_id: 'b0', type: 'p', text: '' }];

        const chunks = raw.split(/\n\s*\n+/).map(s => s.trim()).filter(Boolean);
        const blocks = [];
        let idx = 0;

        for (const chunk of chunks) {
            const lines = chunk.split('\n');
            const isList = lines.length > 0 &&
                lines.every(l => /^(\-|\*|\d+\.)\s+/.test(l.trim()));

            if (isList) {
                for (const line of lines) {
                    const t = line.replace(/^(\-|\*|\d+\.)\s+/, '').trim();
                    if (!t) continue;
                    blocks.push({ block_id: `b${idx++}`, type: 'li', text: t });
                }
            } else {
                blocks.push({ block_id: `b${idx++}`, type: 'p', text: chunk });
            }
        }
        return blocks;
    }

    // ── Block Renderer ──────────────────────────────────────
    renderBlocksHtml(blocks, messageId, notesByBlock, citeReport) {
        // Pull citesByBlock from store if available
        const msg = this._messageStore.get(messageId);
        const citesByBlock = msg ? (msg.citesByBlock || {}) : {};

        let html = '<div class="msg-blocks">';

        for (const block of blocks) {
            const hasNotes = notesByBlock[block.block_id] &&
                notesByBlock[block.block_id].length > 0;
            const noteCount = hasNotes ? notesByBlock[block.block_id].length : 0;

            const hasCites = citesByBlock[block.block_id] &&
                citesByBlock[block.block_id].length > 0;
            const citeCount = hasCites ? citesByBlock[block.block_id].length : 0;

            let safe = this.escapeHtml(block.text);
            safe = this.renderCiteBadges(safe, citeReport);
            if (window.genesisCite) safe = window.genesisCite.renderBadges(safe);

            const typeCls = block.type === 'li' ? ' msg-block-li' : '';
            const noteCls = hasNotes ? ' has-notes' : '';
            const citeCls = hasCites ? ' has-cites' : '';

            let markers = '';
            if (hasNotes) markers += `<span class="note-marker" title="${noteCount} note${noteCount > 1 ? 's' : ''}">\u25cf${noteCount}</span>`;
            if (hasCites) markers += `<span class="cite-marker" title="${citeCount} citation${citeCount > 1 ? 's' : ''}">\u2693${citeCount}</span>`;

            // Inline note strips — visibly appended to block
            let noteStrips = '';
            if (hasNotes) {
                const notes = notesByBlock[block.block_id];
                noteStrips = `<div class="block-note-strips">` +
                    notes.map((n, i) => `<div class="block-note-strip" onclick="event.stopPropagation()">
                        <span class="block-note-icon">\u270f\ufe0f</span>
                        <span class="block-note-text">${this.escapeHtml(n.note)}</span>
                        <button class="block-note-delete" onclick="event.stopPropagation(); app.deleteNote('${messageId}', '${block.block_id}', ${i})" title="Remove">\u2715</button>
                    </div>`).join('') + `</div>`;
            }

            // Revision link — set by runUpdate() after generating revision
            const revisionLink = (msg && msg.revisionLinks && msg.revisionLinks[block.block_id])
                ? `<a class="block-revision-link" href="#" onclick="event.stopPropagation(); app.scrollToMessage('${msg.revisionLinks[block.block_id]}'); return false;">\u2193 see revision</a>`
                : '';

            html += `<div class="msg-block${typeCls}${noteCls}${citeCls}"
                          data-msg-id="${messageId}"
                          data-block-id="${block.block_id}"
                          onclick="app.openBlockPicker('${messageId}', '${block.block_id}', event)"
                     >${safe}${markers}${noteStrips}${revisionLink}</div>`;
        }

        html += '</div>';

        const totalNotes = Object.values(notesByBlock)
            .reduce((sum, arr) => sum + arr.length, 0);
        const totalCites = Object.values(citesByBlock)
            .reduce((sum, arr) => sum + arr.length, 0);
        const msgRole = msg ? msg.role : 'assistant';

        // Build revision model options from the main model dropdown
        const _revModelOpts = this._buildRevisionModelOptions();

        if (msgRole === 'assistant') {
            // Assistant messages get UPDATE bar
            html += `<div class="msg-update-bar" data-msg-id="${messageId}">
                <button class="btn-update"
                        onclick="app.runUpdate('${messageId}')"
                        ${totalNotes === 0 ? 'disabled' : ''}>\u27f3 UPDATE</button>
                <select class="revision-model-select" data-msg-id="${messageId}"
                        title="Revision model">${_revModelOpts}</select>
                <span class="update-note-count" id="note-count-${messageId}">
                    ${totalNotes > 0 || totalCites > 0
                        ? (totalNotes > 0 ? totalNotes + ' note' + (totalNotes > 1 ? 's' : '') : '')
                          + (totalNotes > 0 && totalCites > 0 ? ' \u2022 ' : '')
                          + (totalCites > 0 ? totalCites + ' citation' + (totalCites > 1 ? 's' : '') : '')
                        : 'click a block to annotate'}
                </span>
            </div>`;
        } else {
            // User messages get REGENERATE (re-send with added context)
            html += `<div class="msg-update-bar" data-msg-id="${messageId}" style="border-top-color:rgba(255,255,255,0.05);">
                <button class="btn-update btn-regenerate"
                        onclick="app.runRegenerate('${messageId}')"
                        ${totalNotes === 0 ? 'disabled' : ''}>\u27f3 REGENERATE</button>
                <select class="revision-model-select" data-msg-id="${messageId}"
                        title="Revision model">${_revModelOpts}</select>
                <span class="update-note-count" id="note-count-${messageId}" style="font-size:11px;">
                    ${totalNotes > 0 || totalCites > 0
                        ? (totalNotes > 0 ? totalNotes + ' context note' + (totalNotes > 1 ? 's' : '') : '')
                          + (totalNotes > 0 && totalCites > 0 ? ' \u2022 ' : '')
                          + (totalCites > 0 ? totalCites + ' citation' + (totalCites > 1 ? 's' : '') : '')
                        : 'add context notes to regenerate'}
                </span>
            </div>`;
        }

        return html;
    }

    _buildRevisionModelOptions() {
        const currentModel = localStorage.getItem('gptModel') || this.gptModel || '';
        return `<option value="${currentModel}" selected>${currentModel || 'unknown'}</option>`;
    }

    _getRevisionModel(messageId) {
        const bar = document.querySelector(`.msg-update-bar[data-msg-id="${messageId}"]`);
        if (bar) {
            const sel = bar.querySelector('.revision-model-select');
            if (sel && sel.value) return sel.value;
        }
        return localStorage.getItem('gptModel') || this.gptModel || '';
    }

    // ── Block Action Picker ────────────────────────────────
    openBlockPicker(messageId, blockId, event) {
        // Close any existing picker
        this.closeBlockPicker();

        const msg = this._messageStore.get(messageId);
        if (!msg) return;

        // Highlight selected block
        document.querySelectorAll('.msg-block.active-block').forEach(el =>
            el.classList.remove('active-block'));
        const blockEl = document.querySelector(
            `.msg-block[data-msg-id="${messageId}"][data-block-id="${blockId}"]`);
        if (blockEl) blockEl.classList.add('active-block');

        // Create picker element
        const picker = document.createElement('div');
        picker.className = 'block-picker';
        picker.id = 'block-picker';
        picker.innerHTML = `
            <button onclick="app.handleBlockAction('cite', '${messageId}', '${blockId}')" title="Attach citation to this block">
                \ud83d\udccc Cite
            </button>
            <button onclick="app.handleBlockAction('note', '${messageId}', '${blockId}')" title="Add correction / note">
                \u270f\ufe0f Note
            </button>
        `;

        // Position near the block
        if (blockEl) {
            const rect = blockEl.getBoundingClientRect();
            picker.style.position = 'fixed';
            picker.style.top = `${rect.bottom + 4}px`;
            picker.style.left = `${rect.left}px`;
        }

        document.body.appendChild(picker);

        // Close on outside click (delayed to avoid immediate dismiss)
        setTimeout(() => {
            this._pickerDismiss = (e) => {
                if (!picker.contains(e.target) && e.target !== blockEl) {
                    this.closeBlockPicker();
                }
            };
            document.addEventListener('click', this._pickerDismiss);
        }, 50);
    }

    closeBlockPicker() {
        const existing = document.getElementById('block-picker');
        if (existing) existing.remove();
        if (this._pickerDismiss) {
            document.removeEventListener('click', this._pickerDismiss);
            this._pickerDismiss = null;
        }
        // Clear highlight if no overlay is about to open
        document.querySelectorAll('.msg-block.active-block').forEach(el =>
            el.classList.remove('active-block'));
    }

    handleBlockAction(action, messageId, blockId) {
        const intent = { action, message_id: messageId, block_id: blockId };
        this.closeBlockPicker();

        // Intercept history block actions → queue instead of direct write
        if (messageId.startsWith('hist_')) {
            this._enqueueHistoryAction(action, messageId, blockId);
            return;
        }

        // Re-highlight block for the overlay that's about to open
        const blockEl = document.querySelector(
            `.msg-block[data-msg-id="${messageId}"][data-block-id="${blockId}"]`);
        if (blockEl) blockEl.classList.add('active-block');

        switch (action) {
            case 'note':
                this.openNoteOverlay(messageId, blockId);
                break;
            case 'autocite':
                this.openAutoCite(messageId, blockId);
                break;
            case 'cite':
                this.openCiteOverlay(messageId, blockId);
                break;
        }
    }

    // ── History Queue Methods ─────────────────────────────────

    _enqueueHistoryAction(action, messageId, blockId) {
        const msg = this._messageStore.get(messageId);
        if (!msg) return;
        const block = msg.blocks.find(b => b.block_id === blockId);
        const blockText = block ? block.text.slice(0, 80) : '';

        // Parse day from hist_{day}_{id}
        const parts = messageId.split('_');
        const day = parts.length >= 3 ? parts[1] : '';

        const actionUpper = action.toUpperCase();

        if (action === 'autocite') {
            // Auto-enqueue with block text as context
            this._pushQueueItem(action, messageId, blockId, day, blockText, blockText);
            return;
        }

        // Prompt for payload inline
        const promptText = action === 'note'
            ? 'Note text:'
            : 'Citation coordinate (e.g. 2026-02-23:L5):';

        const payload = prompt(promptText);
        if (!payload || !payload.trim()) return;

        this._pushQueueItem(action, messageId, blockId, day, payload.trim(), blockText);
    }

    _pushQueueItem(action, messageId, blockId, day, payload, blockPreview) {
        const id = `q_${++this._historyQueueSeq}`;
        const item = {
            id, action, messageId, blockId, day,
            payload, blockPreview,
            ts: new Date().toISOString(),
        };
        this._historyQueue.push(item);
        this._renderHistoryQueue();

        // Log to server ledger
        fetch(bridgeApi('/api/history/queue/log'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                event: 'queue_add',
                session_id: this._historySessionId,
                source_day: day,
                source_msg_id: messageId,
                source_block_id: blockId,
                action: action.toUpperCase(),
                payload_preview: payload.slice(0, 128),
            }),
        }).catch(() => {});

        this.addLog(`Queued ${action.toUpperCase()} on ${blockId} (not written to history)`, 'info');
    }

    _removeQueueItem(queueId) {
        const item = this._historyQueue.find(q => q.id === queueId);
        this._historyQueue = this._historyQueue.filter(q => q.id !== queueId);
        this._renderHistoryQueue();

        if (item) {
            fetch(bridgeApi('/api/history/queue/log'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    event: 'queue_remove',
                    session_id: this._historySessionId,
                    queue_item_id: queueId,
                    action: item.action.toUpperCase(),
                    source_day: item.day,
                }),
            }).catch(() => {});
        }
    }

    _renderHistoryQueue() {
        const container = document.getElementById('chat-hist-queue');
        const countEl = document.getElementById('chat-hist-queue-count');
        if (!container) return;
        if (countEl) countEl.textContent = this._historyQueue.length;

        if (this._historyQueue.length === 0) {
            container.innerHTML = '<div style="text-align: center; padding: 20px 8px; color: var(--text-secondary); font-size: 11px;">Click a block, then Note/Cite to queue actions. Source history stays immutable.</div>';
            return;
        }

        container.innerHTML = this._historyQueue.map(item => {
            const actionColor = item.action === 'note' ? '#ffd700'
                : item.action === 'cite' ? '#00d4ff' : '#00ff88';
            const actionLabel = item.action.toUpperCase();
            const preview = (item.payload || '').slice(0, 40) + ((item.payload || '').length > 40 ? '...' : '');
            return `<div style="padding:6px 4px; border-bottom:1px solid var(--border); display:flex; align-items:flex-start; gap:6px;">
                <span style="font-size:10px; font-weight:700; color:${actionColor}; white-space:nowrap; min-width:36px;">${actionLabel}</span>
                <div style="flex:1; min-width:0;">
                    <div style="font-size:10px; color:var(--text-secondary);">${item.day} &middot; ${item.blockId}</div>
                    <div style="font-size:11px; color:var(--text-primary); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${escapeHtml(preview)}</div>
                </div>
                <button onclick="app._removeQueueItem('${item.id}')" style="background:none; border:none; color:var(--danger); cursor:pointer; font-size:12px; padding:0 2px;" title="Remove">&times;</button>
            </div>`;
        }).join('');
    }

    async _processHistoryQueue() {
        if (this._historyQueue.length === 0) {
            this.addLog('Queue is empty — nothing to process', 'warning');
            return;
        }

        const items = [...this._historyQueue];
        const sessionId = this._historySessionId;

        // Log process_start
        fetch(bridgeApi('/api/history/queue/log'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ event: 'process_start', session_id: sessionId, item_count: items.length }),
        }).catch(() => {});

        let okCount = 0;
        let errorCount = 0;
        const baseUrl = ANCHORWORKS_CONFIG?.llm || 'http://127.0.0.1:11435';

        for (const item of items) {
            let status = 'ok';
            let error = null;

            try {
                // History actions fork to linked side-chats (main thread stays clean)
                const actionLabel = item.action.toUpperCase();
                let forwardContent = '';

                if (item.action === 'note') {
                    forwardContent = `[NOTE from ${item.day} ${item.blockId}]\n\n`
                        + `Block: ${item.blockPreview}\n\n`
                        + `Note: ${item.payload}`;
                } else if (item.action === 'cite' || item.action === 'autocite') {
                    forwardContent = `[CITE from ${item.day} ${item.blockId}]\n\n`
                        + `Block: ${item.blockPreview}\n\n`
                        + `Coordinate: ${item.payload}`;
                }

                const result = await this.startSideChatFromContext({
                    fromDay: item.day,
                    messageId: 0,
                    content: forwardContent,
                    actor: 'system',
                    description: `${actionLabel} from ${item.day} ${item.blockId}`.trim(),
                });

                if (result.ok) {
                    this.addGptMessage(
                        'system',
                        `SIDE CHAT ${result.side_chat_id}: ${result.description}`
                    );
                    okCount++;
                } else {
                    status = 'error';
                    error = result.detail || 'side chat start failed';
                    errorCount++;
                }
            } catch (e) {
                status = 'error';
                error = e.message;
                errorCount++;
            }

            // Log each item result
            fetch(bridgeApi('/api/history/queue/log'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    event: 'process_item',
                    session_id: sessionId,
                    queue_item_id: item.id,
                    action: item.action.toUpperCase(),
                    source_day: item.day,
                    source_block_id: item.blockId,
                    status, error,
                }),
            }).catch(() => {});
        }

        // Log process_end
        fetch(bridgeApi('/api/history/queue/log'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                event: 'process_end',
                session_id: sessionId,
                total: items.length,
                ok_count: okCount,
                error_count: errorCount,
            }),
        }).catch(() => {});

        this._historyQueue = [];
        this._renderHistoryQueue();
        this.addLog(`Processed ${okCount} item${okCount !== 1 ? 's' : ''} into today workspace${errorCount > 0 ? ` (${errorCount} errors)` : ''}`, errorCount > 0 ? 'warning' : 'success');
    }

    _cancelHistoryQueue() {
        if (this._historyQueue.length === 0) return;
        const count = this._historyQueue.length;

        fetch(bridgeApi('/api/history/queue/log'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                event: 'queue_cancel',
                session_id: this._historySessionId,
                item_count: count,
            }),
        }).catch(() => {});

        this._historyQueue = [];
        this._renderHistoryQueue();
        this.addLog(`Cancelled ${count} queued action${count !== 1 ? 's' : ''}`, 'info');
    }

    // ── Auto-Cite (LLM-powered search) ─────────────────────
    openAutoCite(messageId, blockId) {
        // Opens the normal cite overlay, then kicks off LLM search for linked cites + data lake
        this.openCiteOverlay(messageId, blockId);
        const overlay = document.getElementById('cite-overlay');
        overlay.dataset.mode = 'autocite';
        this._runAutoCiteSearch(messageId, blockId);
    }

    async _runAutoCiteSearch(messageId, blockId) {
        const msg = this._messageStore.get(messageId);
        if (!msg) return;
        const block = msg.blocks.find(b => b.block_id === blockId);
        if (!block) return;
        const blockText = (block.text || block.content || '').slice(0, 500);

        const linkedEl = document.getElementById('cite-linked-list');
        const lakeEl = document.getElementById('cite-data-lake');

        if (linkedEl) linkedEl.innerHTML = '<div style="color:var(--warning);">LLM analyzing block for related citations...</div>';
        if (lakeEl) lakeEl.innerHTML = '<div style="color:var(--warning);">Searching data lake...</div>';

        // LLM-powered auto-cite (creative prompt approach)
        try {
            const r = await fetch(`${this.citeBase}/api/citations/autocite`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ block_text: blockText, limit: 5 })
            });
            if (r.ok) {
                const data = await r.json();
                let html = '';

                // LLM-suggested related citations
                if (data.related && data.related.length > 0) {
                    html += data.related.map(c =>
                        `<div style="padding:4px 0;border-bottom:1px solid var(--border);font-size:11px;">
                            <strong>${this.escapeHtml(c.coord || '')}</strong>
                            <span style="color:var(--text-secondary);margin-left:6px;">${this.escapeHtml((c.reason || '').slice(0, 80))}</span>
                        </div>`
                    ).join('');
                } else {
                    html = 'LLM found no related citations.';
                }

                // Auto-fill subject/note suggestions
                if (data.suggested_subject) {
                    const subEl = document.getElementById('cite-subject-input');
                    if (subEl && !subEl.value) subEl.value = data.suggested_subject;
                }
                if (data.suggested_note) {
                    const noteEl = document.getElementById('cite-note-input');
                    if (noteEl && !noteEl.value) noteEl.value = data.suggested_note.slice(0, 250);
                }

                linkedEl.innerHTML = html;
            } else {
                // Fallback to keyword search if LLM unavailable
                const r2 = await fetch(`${this.citeBase}/api/citations/search`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({ query: blockText, limit: 5 })
                });
                if (r2.ok) {
                    const data2 = await r2.json();
                    if (data2.results && data2.results.length > 0) {
                        linkedEl.innerHTML = data2.results.map(c =>
                            `<div style="padding:4px 0;border-bottom:1px solid var(--border);font-size:11px;">
                                <strong>${this.escapeHtml(c.coord)}</strong>
                                <span style="color:var(--text-secondary);margin-left:6px;">${this.escapeHtml((c.subject || c.snippet || '').slice(0, 80))}</span>
                            </div>`
                        ).join('');
                    } else {
                        linkedEl.innerHTML = 'No related citations found.';
                    }
                } else {
                    linkedEl.innerHTML = 'Citation search unavailable.';
                }
            }
        } catch {
            linkedEl.innerHTML = 'Citation search unavailable.';
        }

        // Search data lake (LakeSpeak)
        try {
            const r = await fetch(bridgeApi('/api/lakespeak/query'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ query: blockText, topk: 3 })
            });
            if (r.ok) {
                const data = await r.json();
                const hits = data.citations || data.results || [];
                if (hits.length > 0) {
                    lakeEl.innerHTML = hits.map(h =>
                        `<div style="padding:4px 0;border-bottom:1px solid var(--border);font-size:11px;">
                            <strong>${this.escapeHtml(h.receipt_id || h.source || h.anchor || 'chunk')}</strong>
                            <span style="color:var(--text-secondary);margin-left:6px;">${this.escapeHtml((h.text || h.content || h.snippet || '').slice(0, 100))}</span>
                        </div>`
                    ).join('');
                } else if (data.response) {
                    lakeEl.innerHTML = `<div style="font-size:11px;">${this.escapeHtml(data.response.slice(0, 200))}</div>`;
                } else {
                    lakeEl.innerHTML = 'No data lake matches.';
                }
            } else {
                lakeEl.innerHTML = 'Data lake not available.';
            }
        } catch {
            lakeEl.innerHTML = 'Data lake not available.';
        }
    }

    async _runDataLakeSearch() {
        const overlay = document.getElementById('cite-overlay');
        const messageId = overlay?.dataset.msgId;
        const blockId = overlay?.dataset.blockId;
        if (!messageId || !blockId) return;

        const msg = this._messageStore.get(messageId);
        if (!msg) return;
        const block = msg.blocks.find(b => b.block_id === blockId);
        if (!block) return;
        const blockText = (block.text || block.content || '').slice(0, 500);

        const lakeEl = document.getElementById('cite-data-lake');
        if (!lakeEl) return;
        lakeEl.innerHTML = '<div style="color:var(--warning);">Searching data lake...</div>';

        try {
            const r = await fetch(bridgeApi('/api/lakespeak/query'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ query: blockText, topk: 3 })
            });
            if (r.ok) {
                const data = await r.json();
                const hits = data.citations || data.results || [];
                if (hits.length > 0) {
                    lakeEl.innerHTML = hits.map(h =>
                        `<div style="padding:4px 0;border-bottom:1px solid var(--border);font-size:11px;">
                            <strong>${this.escapeHtml(h.receipt_id || h.source || h.anchor || 'chunk')}</strong>
                            <span style="color:var(--text-secondary);margin-left:6px;">${this.escapeHtml((h.text || h.content || h.snippet || '').slice(0, 100))}</span>
                        </div>`
                    ).join('');
                } else if (data.response) {
                    lakeEl.innerHTML = `<div style="font-size:11px;">${this.escapeHtml(data.response.slice(0, 200))}</div>`;
                } else {
                    lakeEl.innerHTML = 'No data lake matches.';
                }
            } else {
                lakeEl.innerHTML = 'Data lake not available.';
            }
        } catch {
            lakeEl.innerHTML = 'Data lake not available.';
        }
    }

    // ── Manual Cite Overlay ─────────────────────────────────
    openCiteOverlay(messageId, blockId) {
        const msg = this._messageStore.get(messageId);
        if (!msg) return;
        const block = msg.blocks.find(b => b.block_id === blockId);

        const overlay = document.getElementById('cite-overlay');
        document.getElementById('cite-block-preview').textContent = block ? block.text : '';

        // Auto-fill block pointer coordinate with date prefix
        const coordInput = document.getElementById('cite-coord-input');
        const ord = parseInt(String(blockId || 'b0').replace('b', ''), 10) || 0;
        const stableId = (msg && msg.serverId != null) ? `SID:${msg.serverId}` : `MID:${messageId}`;
        coordInput.value = `${this._todayStr}:${stableId}:BLK:${ord}`;
        document.getElementById('cite-resolve-result').innerHTML = '';

        document.getElementById('cite-subject-input').value = '';
        const noteInput = document.getElementById('cite-note-input');
        if (noteInput) noteInput.value = '';
        document.getElementById('cite-linked-list').innerHTML =
            'Click "Search Archive" or use Auto-Cite to find related citations.';
        const lakeDiv = document.getElementById('cite-data-lake');
        if (lakeDiv) lakeDiv.innerHTML = 'Click "Search Lake" to find related data lake entries.';
        document.getElementById('btn-attach-cite').disabled = true;

        // Resolve button starts disabled — enabled by input validation
        const resolveBtn = overlay.querySelector('.cite-coord-row button');
        if (resolveBtn) resolveBtn.disabled = true;

        overlay.dataset.msgId = messageId;
        overlay.dataset.blockId = blockId;
        overlay.dataset.mode = 'manual';
        overlay.classList.add('active');
        document.body.style.overflow = 'hidden';

        // Wire real-time format validation on the coord input
        const ci = document.getElementById('cite-coord-input');
        ci._citeValidate = () => {
            const v = ci.value.trim();
            const valid =
                /^\d{4}-\d{2}-\d{2}:(SID:\d+|MID:[^:]+):BLK:\d+$/.test(v) ||
                /^\d{4}-\d{2}-\d{2}:L\d+$/.test(v);
            if (resolveBtn) resolveBtn.disabled = !valid;
        };
        ci.removeEventListener('input', ci._citeValidate);
        ci.addEventListener('input', ci._citeValidate);
        ci._citeValidate();  // run once now

        // Focus and place cursor at end (after the 'L')
        setTimeout(() => { ci.focus(); ci.setSelectionRange(ci.value.length, ci.value.length); }, 50);
    }

    closeCiteOverlay() {
        document.getElementById('cite-overlay').classList.remove('active');
        document.body.style.overflow = '';
        document.querySelectorAll('.msg-block.active-block').forEach(el =>
            el.classList.remove('active-block'));
    }

    async resolveCitePreview() {
        const coord = document.getElementById('cite-coord-input').value.trim();
        const resultEl = document.getElementById('cite-resolve-result');

        // Date-prefixed block format: YYYY-MM-DD:SID:N:BLK:N or YYYY-MM-DD:MID:id:BLK:N
        const blockSid = coord.match(/^(\d{4}-\d{2}-\d{2}):SID:(\d+):BLK:(\d+)$/);
        const blockMid = coord.match(/^(\d{4}-\d{2}-\d{2}):MID:([^:]+):BLK:(\d+)$/);
        const line = coord.match(/^(\d{4}-\d{2}-\d{2}):L(\d+)$/);

        if (!blockSid && !blockMid && !line) {
            resultEl.innerHTML = '<div style="color:var(--danger);">Invalid format. Use: YYYY-MM-DD:SID:N:BLK:N</div>';
            document.getElementById('btn-attach-cite').disabled = true;
            return;
        }

        // Resolve block coord locally from messageStore (today's chat)
        if (blockMid || blockSid) {
            const match = blockMid || blockSid;
            const coordDay = match[1];
            const blkIdx = parseInt(match[3], 10) || 0;
            let msg = null;

            if (blockMid) {
                msg = this._messageStore.get(match[2]);
            } else {
                const serverId = parseInt(match[2], 10);
                for (const [, m] of this._messageStore) {
                    if (m.serverId === serverId) { msg = m; break; }
                }
            }

            // If found locally — show snippet
            if (msg && msg.blocks && blkIdx < msg.blocks.length) {
                const b = msg.blocks[blkIdx];
                const content = (b && (b.text || b.content || '')).toString();
                resultEl.innerHTML = `
                    <div class="cite-resolve-hit">
                        <div><strong>${this.escapeHtml(coord)}</strong> — <span style="color:var(--success);">\u2713 valid (local)</span></div>
                        <div class="cite-resolve-snippet">${this.escapeHtml(content.slice(0, 300))}</div>
                    </div>`;
                document.getElementById('btn-attach-cite').disabled = false;
                return;
            }

            // Not in local store — try server resolve (archive day)
            try {
                const r = await fetch(`${this.citeBase}/api/citations/resolve?cite=${encodeURIComponent(coord)}`, {
                    credentials: 'include'
                });
                if (!r.ok) throw new Error(`HTTP ${r.status}`);
                const data = await r.json();
                if (data.found) {
                    resultEl.innerHTML = `
                        <div class="cite-resolve-hit">
                            <div><strong>${this.escapeHtml(coord)}</strong> \u2014 <span style="color:var(--success);">\u2713 valid (archive)</span></div>
                            <div class="cite-resolve-snippet">${this.escapeHtml((data.content || '').slice(0, 300))}</div>
                        </div>`;
                    document.getElementById('btn-attach-cite').disabled = false;
                } else {
                    resultEl.innerHTML = `<div style="color:var(--danger);">Not found in chat for ${coordDay}.</div>`;
                    document.getElementById('btn-attach-cite').disabled = true;
                }
            } catch (e) {
                resultEl.innerHTML = `<div style="color:var(--danger);">Resolve failed: ${this.escapeHtml(e.message)}</div>`;
                document.getElementById('btn-attach-cite').disabled = true;
            }
            return;
        }

        // Legacy day:line format — call backend resolve

        resultEl.innerHTML = '<div style="color:var(--text-secondary);">Resolving...</div>';

        try {
            const r = await fetch(`${this.citeBase}/api/citations/resolve?cite=${encodeURIComponent(coord)}`, {
                credentials: 'include'
            });
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            const data = await r.json();

            if (data.found) {
                resultEl.innerHTML = `
                    <div class="cite-resolve-hit">
                        <div><strong>${this.escapeHtml(data.cite)}</strong> \u2014 <span style="color:var(--success);">\u2713 valid</span></div>
                        <div style="color:var(--text-secondary);font-size:11px;">${this.escapeHtml(data.sender || '')} \u2022 ${this.escapeHtml(data.branch || 'main')}</div>
                        <div class="cite-resolve-snippet">${this.escapeHtml((data.content || '(no content)').slice(0, 300))}</div>
                    </div>`;
                document.getElementById('btn-attach-cite').disabled = false;
            } else {
                resultEl.innerHTML = `<div style="color:var(--danger);">\u2717 Not found in archive. Line may not exist for that day.</div>`;
                document.getElementById('btn-attach-cite').disabled = true;
            }
        } catch (e) {
            resultEl.innerHTML = `<div style="color:var(--danger);">Resolve failed: ${this.escapeHtml(e.message)}</div>`;
            document.getElementById('btn-attach-cite').disabled = true;
        }
    }

    async attachCite() {
        const overlay = document.getElementById('cite-overlay');
        const messageId = overlay.dataset.msgId;
        const blockId = overlay.dataset.blockId;
        const coord = document.getElementById('cite-coord-input').value.trim();

        if (!coord) return;

        const msg = this._messageStore.get(messageId);
        if (!msg) return;

        if (!msg.citesByBlock[blockId]) msg.citesByBlock[blockId] = [];

        // Avoid duplicate
        if (msg.citesByBlock[blockId].some(c => c.canonical === coord)) {
            this.addLog(`Citation ${coord} already on block ${blockId}`, 'warning');
            this.closeCiteOverlay();
            return;
        }

        const subject = (document.getElementById('cite-subject-input').value || '').trim();
        const note = (document.getElementById('cite-note-input')?.value || '').trim();
        const source = overlay.dataset.mode === 'autocite' ? 'auto' : 'manual';
        const blockOrdinal = parseInt((blockId || 'b0').replace('b', ''), 10) || 0;

        // Persist to server sidecar (uses serverId as stable anchor)
        const serverId = msg.serverId;
        if (serverId != null) {
            try {
                const resp = await fetch(`${this.citeBase}/api/citations/attach`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({
                        day: this._todayStr,
                        message_id: String(serverId),
                        block_id: blockId,
                        block_ordinal: blockOrdinal,
                        canonical: coord,
                        subject: subject || null,
                        note: note || null,
                        source: source,
                    })
                });
                if (!resp.ok) {
                    const err = await resp.json().catch(() => ({}));
                    throw new Error(err.detail || `HTTP ${resp.status}`);
                }
                const result = await resp.json();
                // Use server-generated record (has cite_id, ts, etc.)
                msg.citesByBlock[blockId].push(result.cite);
            } catch (e) {
                this.addLog(`Citation save failed: ${e.message}`, 'error');
                this.closeCiteOverlay();
                return;
            }
        } else {
            // No server ID yet (edge case) — store in RAM only
            msg.citesByBlock[blockId].push({
                cite_id: `c_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
                canonical: coord,
                subject: subject || null,
                source: source,
                linked: [],
                data_lake: null,
                ts: Date.now()
            });
            this.addLog('Citation stored in memory only (no server ID)', 'warning');
        }

        this._rerenderMessage(messageId);
        this.closeCiteOverlay();
        this.addLog(`Citation ${coord} attached to block ${blockId}`, 'success');
    }

    async deleteCite(messageId, blockId, citeIndex) {
        const msg = this._messageStore.get(messageId);
        if (!msg || !msg.citesByBlock[blockId]) return;

        const cite = msg.citesByBlock[blockId][citeIndex];
        const citeId = cite ? cite.cite_id : null;
        const serverId = msg.serverId;

        // Persist detach to server sidecar
        if (citeId && serverId != null) {
            try {
                const resp = await fetch(`${this.citeBase}/api/citations/detach`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({
                        day: this._todayStr,
                        message_id: String(serverId),
                        block_id: blockId,
                        cite_id: citeId,
                    })
                });
                if (!resp.ok) {
                    const err = await resp.json().catch(() => ({}));
                    this.addLog(`Detach failed: ${err.detail || resp.status}`, 'error');
                }
            } catch (e) {
                this.addLog(`Detach request failed: ${e.message}`, 'error');
            }
        }

        msg.citesByBlock[blockId].splice(citeIndex, 1);
        if (msg.citesByBlock[blockId].length === 0) {
            delete msg.citesByBlock[blockId];
        }

        this._rerenderMessage(messageId);
        this.addLog(`Citation removed from block ${blockId}`, 'info');
    }

    // ── Note Overlay ───────────────────────────────────────
    openNoteOverlay(messageId, blockId) {
        const msg = this._messageStore.get(messageId);
        if (!msg) return;

        const block = msg.blocks.find(b => b.block_id === blockId);
        if (!block) return;

        document.querySelectorAll('.msg-block.active-block').forEach(el =>
            el.classList.remove('active-block'));
        const blockEl = document.querySelector(
            `.msg-block[data-msg-id="${messageId}"][data-block-id="${blockId}"]`);
        if (blockEl) blockEl.classList.add('active-block');

        const overlay = document.getElementById('note-overlay');
        document.getElementById('note-block-preview').textContent = block.text;
        document.getElementById('note-input').value = '';

        overlay.dataset.msgId = messageId;
        overlay.dataset.blockId = blockId;

        const existingEl = document.getElementById('note-existing');
        const notes = msg.notesByBlock[blockId] || [];
        if (notes.length > 0) {
            existingEl.innerHTML = `
                <div class="note-existing-label">Existing notes:</div>
                ${notes.map((n, i) => `
                    <div class="note-item">
                        <span class="note-item-text">${this.escapeHtml(n.note)}</span>
                        <button class="note-item-delete"
                                onclick="app.deleteNote('${messageId}', '${blockId}', ${i})"
                                title="Delete note">\u2715</button>
                    </div>
                `).join('')}`;
        } else {
            existingEl.innerHTML = '';
        }

        overlay.classList.add('active');
        document.body.style.overflow = 'hidden';
        setTimeout(() => document.getElementById('note-input').focus(), 50);
    }

    closeNoteOverlay() {
        const overlay = document.getElementById('note-overlay');
        overlay.classList.remove('active');
        document.body.style.overflow = '';
        document.querySelectorAll('.msg-block.active-block').forEach(el =>
            el.classList.remove('active-block'));
    }

    async saveNote() {
        const overlay = document.getElementById('note-overlay');
        const messageId = overlay.dataset.msgId;
        const blockId = overlay.dataset.blockId;
        const noteText = document.getElementById('note-input').value.trim();

        if (!noteText) return;

        const msg = this._messageStore.get(messageId);
        if (!msg) return;

        if (!msg.notesByBlock[blockId]) msg.notesByBlock[blockId] = [];
        const blockOrdinal = parseInt((blockId || 'b0').replace('b', ''), 10) || 0;

        // Persist note to server
        let noteRecord = null;
        if (msg.serverId != null) {
            try {
                const resp = await fetch(`${this.citeBase}/api/notes/attach`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({
                        day: this._todayStr,
                        message_id: String(msg.serverId),
                        block_id: blockId,
                        block_ordinal: blockOrdinal,
                        note: noteText,
                    })
                });
                if (resp.ok) {
                    const result = await resp.json();
                    noteRecord = result.note;
                }
            } catch (e) {
                this.addLog(`Note persist failed: ${e.message}`, 'warning');
            }
        }

        // Store in RAM (use server record if available)
        msg.notesByBlock[blockId].push(noteRecord || {
            note_id: `n_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
            note: noteText,
            ts: Date.now()
        });

        // Auto-cite: attach a citation to this block when a note is added
        const stableId = (msg.serverId != null) ? `SID:${msg.serverId}` : `MID:${messageId}`;
        const coord = `${this._todayStr}:${stableId}:BLK:${blockOrdinal}`;

        if (!msg.citesByBlock[blockId]) msg.citesByBlock[blockId] = [];
        const alreadyCited = msg.citesByBlock[blockId].some(c => c.canonical === coord && c.source === 'note');
        if (!alreadyCited) {
            if (msg.serverId != null) {
                try {
                    const resp = await fetch(`${this.citeBase}/api/citations/attach`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        credentials: 'include',
                        body: JSON.stringify({
                            day: this._todayStr,
                            message_id: String(msg.serverId),
                            block_id: blockId,
                            block_ordinal: blockOrdinal,
                            canonical: coord,
                            subject: noteText.slice(0, 120),
                            source: 'note',
                        })
                    });
                    if (resp.ok) {
                        const result = await resp.json();
                        msg.citesByBlock[blockId].push(result.cite);
                    }
                } catch (e) {
                    this.addLog(`Auto-cite failed: ${e.message}`, 'warning');
                }
            } else {
                msg.citesByBlock[blockId].push({
                    cite_id: `c_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
                    canonical: coord,
                    subject: noteText.slice(0, 120),
                    source: 'note',
                    linked: [],
                    data_lake: null,
                    ts: Date.now()
                });
            }
        }

        this._rerenderMessage(messageId);
        this.closeNoteOverlay();
        this.addLog(`Note saved on block ${blockId} (auto-cited)`, 'success');
    }

    async deleteNote(messageId, blockId, noteIndex) {
        const msg = this._messageStore.get(messageId);
        if (!msg || !msg.notesByBlock[blockId]) return;

        const note = msg.notesByBlock[blockId][noteIndex];
        const noteId = note ? note.note_id : null;

        // Persist detach to server
        if (noteId && msg.serverId != null) {
            try {
                await fetch(`${this.citeBase}/api/notes/detach`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({
                        day: this._todayStr,
                        message_id: String(msg.serverId),
                        block_id: blockId,
                        note_id: noteId,
                    })
                });
            } catch (e) {
                this.addLog(`Note detach failed: ${e.message}`, 'warning');
            }
        }

        msg.notesByBlock[blockId].splice(noteIndex, 1);
        if (msg.notesByBlock[blockId].length === 0) {
            delete msg.notesByBlock[blockId];
        }

        this._rerenderMessage(messageId);

        const overlay = document.getElementById('note-overlay');
        if (overlay.classList.contains('active') &&
            overlay.dataset.msgId === messageId &&
            overlay.dataset.blockId === blockId) {
            this.openNoteOverlay(messageId, blockId);
        }

        this.addLog(`Note deleted from block ${blockId}`, 'info');
    }

    _rerenderMessage(messageId) {
        const msg = this._messageStore.get(messageId);
        if (!msg || !msg.element) return;

        const contentEl = msg.element.querySelector('.message-content');
        if (!contentEl) return;

        contentEl.innerHTML = this.renderBlocksHtml(
            msg.blocks, messageId, msg.notesByBlock, msg.citeReport);

        this.attachBadgeHandlers(msg.element);
    }

    // ── Citations Manager (cit* namespace) ────────────────────

    _citItems = [];        // flat array of all loaded cite records
    _citCursor = null;     // next_cursor for pagination
    _citActiveSource = 'all';
    _citSearchQuery = '';
    _citActiveCiteId = null;
    _citDistribution = null; // cached distribution data

    // ── Citation Explorer (day distribution, date strip, explorer cards) ──

    async citUpdateExplorerStats() {
        /**Fetch citation distribution and render day chart + date strip + context strip.
         * Mirrors updateLexiconStats() for the lexicon tab.
         */
        try {
            const resp = await fetch(`${this.citeBase}/api/citations/distribution`, {
                credentials: 'include'
            });
            const data = await resp.json();
            this._citDistribution = data;

            // Update context strip
            const totalEl = document.getElementById('cit-stat-total');
            const daysEl = document.getElementById('cit-stat-days');
            const srcEl = document.getElementById('cit-stat-sources');
            if (totalEl) totalEl.textContent = (data.total || 0).toLocaleString();
            if (daysEl) daysEl.textContent = (data.days || []).length;
            if (srcEl) srcEl.textContent = '—'; // updated after first load

            // Render day distribution chart
            this._citRenderDayDistribution(data.days || []);

            // Build date strip (like alpha strip)
            this._citBuildDateStrip(data.days || []);
        } catch (e) {
            console.warn('Citation distribution fetch failed:', e);
        }
    }

    _citRenderDayDistribution(days) {
        /**Render citations-per-day bar chart (same visual as letter distribution).**/
        const chart = document.getElementById('cit-distribution-chart');
        const label = document.getElementById('cit-chart-label');
        if (!chart) return;

        if (days.length === 0) {
            chart.innerHTML = '<span style="color: var(--text-secondary); font-size: 12px;">No citation data</span>';
            if (label) label.textContent = '';
            return;
        }

        // Show last 30 days max in chart (newest on right)
        const chartDays = days.slice(0, 30).reverse();
        const maxCount = Math.max(1, ...chartDays.map(d => d.count));
        const totalCites = days.reduce((s, d) => s + d.count, 0);
        if (label) label.textContent = `${totalCites.toLocaleString()} citations across ${days.length} days`;

        const barColors = [
            '#e94560', '#ff6bd6', '#b388ff', '#00d4ff', '#00ff88',
            '#ffd700', '#ff9f43', '#9b59b6', '#0077b6', '#c23152',
        ];
        chart.innerHTML = chartDays.map((d, i) => {
            const pct = Math.max(4, (d.count / maxCount) * 100);
            const color = barColors[i % barColors.length];
            const shortDay = d.day.slice(5); // MM-DD
            return `<div style="flex:1; display:flex; flex-direction:column; align-items:center; gap:2px; cursor:pointer;" title="${d.day}: ${d.count} citations" onclick="app.citBrowseDay('${d.day}')">
                <span style="font-size:9px; color:var(--text-secondary);">${d.count}</span>
                <div style="width:100%; height:${pct}%; min-height:3px; background:${color}; border-radius:3px 3px 0 0; transition:height 0.3s;"></div>
                <span style="font-size:9px; font-weight:700; color:${color};">${shortDay}</span>
            </div>`;
        }).join('');
    }

    _citBuildDateStrip(days) {
        /**Build clickable date buttons (like A-Z alpha strip but for days).**/
        const strip = document.getElementById('cit-date-strip');
        if (!strip) return;

        strip.innerHTML = '';
        // Show all days as buttons, newest first
        days.forEach(d => {
            const btn = document.createElement('button');
            btn.className = 'btn btn-sm';
            btn.style.cssText = 'padding:4px 8px;font-size:11px;font-weight:700;min-width:28px;background:var(--accent-bg);color:var(--text-secondary);border:1px solid var(--border);cursor:pointer;transition:all 0.15s;';
            btn.textContent = d.day.slice(5); // MM-DD
            btn.title = `${d.day}: ${d.count} citations`;
            btn.onclick = () => this.citBrowseDay(d.day);
            btn.onmouseenter = () => { btn.style.background = 'var(--gpt-oss)'; btn.style.color = '#000'; };
            btn.onmouseleave = () => { btn.style.background = 'var(--accent-bg)'; btn.style.color = 'var(--text-secondary)'; };
            strip.appendChild(btn);
        });
    }

    async citBrowseDay(day) {
        /**Load citations for a specific day and render as explorer cards.**/
        try {
            // Use the paginated endpoint with the day before as cursor to get that day
            // OR load all and filter — simpler for now since data is already paginated by day
            const resp = await fetch(`${this.citeBase}/api/citations/all?limit=1&cursor=${
                // Get the day before 'day' as cursor, so the result includes 'day'
                (() => {
                    const d = new Date(day + 'T00:00:00Z');
                    d.setUTCDate(d.getUTCDate() + 1);
                    return d.toISOString().slice(0, 10);
                })()
            }`, {
                credentials: 'include'
            });
            const data = await resp.json();
            const dayItems = (data.items || []).filter(c => c.day === day);

            // Merge into _citItems if not already present
            const existingIds = new Set(this._citItems.map(c => c.cite_id));
            for (const item of dayItems) {
                if (!existingIds.has(item.cite_id)) {
                    this._citItems.push(item);
                }
            }

            // Show only this day's items
            this._citRenderResults(dayItems);

            const meta = document.getElementById('cit-result-meta');
            if (meta) {
                meta.style.display = 'block';
                meta.innerHTML = `<span style="color: var(--gpt-oss);">${dayItems.length}</span> citations — ${day}`;
            }
        } catch (e) {
            this.addLog(`Failed to browse day ${day}: ${e.message}`, 'error');
        }
    }

    async citLoadAll(reset = true) {
        if (reset) {
            this._citItems = [];
            this._citCursor = null;
        }
        const params = new URLSearchParams({ limit: '5' });
        if (this._citCursor) params.set('cursor', this._citCursor);

        try {
            const res = await fetch(`${this.citeBase}/api/citations/all?${params}`, {
                credentials: 'include'
            });
            const data = await res.json();
            if (data.items) this._citItems.push(...data.items);
            this._citCursor = data.next_cursor || null;

            // Update context strip
            const totalEl = document.getElementById('cit-stat-total');
            const daysEl = document.getElementById('cit-stat-days');
            if (totalEl) totalEl.textContent = data.total_days !== undefined
                ? this._citItems.length : this._citItems.length;
            if (daysEl) daysEl.textContent = data.total_days || 0;

            const metaEl = document.getElementById('cit-result-meta');
            if (metaEl) {
                metaEl.textContent = data.next_cursor
                    ? `Showing ${this._citItems.length} citations (more available)`
                    : `${this._citItems.length} citations total`;
            }

            this._citRenderFiltered();
        } catch (e) {
            this.addLog(`Citations load failed: ${e.message}`, 'error');
        }
    }

    citLoadMore() {
        if (!this._citCursor) {
            this.addLog('No more citations to load', 'info');
            return;
        }
        this.citLoadAll(false);
    }

    citSearch(query) {
        this._citSearchQuery = (query || '').toLowerCase().trim();
        this._citRenderFiltered();
    }

    citFilterSource(src) {
        this._citActiveSource = src;
        // Update pill-style filter buttons (matches lexicon pack filter pattern)
        document.querySelectorAll('#cit-source-filter .btn').forEach(btn => {
            const isActive = btn.dataset.src === src;
            if (isActive) {
                btn.style.background = 'linear-gradient(135deg, #00d4ff, #0099cc)';
                btn.style.color = '#000';
                btn.style.border = 'none';
            } else {
                btn.style.background = 'var(--accent-bg)';
                btn.style.color = '';
                btn.style.border = '';
            }
        });
        // Show filter indicator in context strip
        const indicator = document.getElementById('cit-strip-filter');
        if (indicator) {
            if (src === 'all') {
                indicator.style.display = 'none';
            } else {
                indicator.style.display = '';
                indicator.textContent = `Filtering: ${src.toUpperCase()}`;
            }
        }
        this._citRenderFiltered();
    }

    _citRenderFiltered() {
        let items = this._citItems;

        // Source filter
        if (this._citActiveSource !== 'all') {
            items = items.filter(c => c.source === this._citActiveSource);
        }

        // Search filter
        if (this._citSearchQuery) {
            const q = this._citSearchQuery;
            items = items.filter(c =>
                (c.coord || '').toLowerCase().includes(q) ||
                (c.canonical || '').toLowerCase().includes(q) ||
                (c.subject || '').toLowerCase().includes(q) ||
                (c.note || '').toLowerCase().includes(q) ||
                (c.cite_id || '').toLowerCase().includes(q)
            );
        }

        this._citRenderResults(items);
    }

    _citRenderResults(items) {
        const grid = document.getElementById('cit-results');
        const meta = document.getElementById('cit-result-meta');
        if (!grid) return;

        if (meta) {
            meta.style.display = items.length > 0 ? 'block' : 'none';
            meta.innerHTML = `<span style="color: var(--gpt-oss);">${items.length}</span> citations`;
        }

        if (items.length === 0) {
            grid.innerHTML = `<div style="grid-column:1/-1; text-align: center; padding: 30px; color: var(--text-secondary);">
                ${this._citItems.length === 0 ? 'No citations loaded yet.' : 'No citations match the current filter.'}
            </div>`;
            return;
        }

        // Explorer-style cards (matching Lexicon Browser visual language)
        grid.innerHTML = items.map(c => {
            const coord = c.coord || c.canonical || '?';
            const src = (c.source || 'unknown').toUpperCase();
            const subject = c.subject ? this.escapeHtml(c.subject) : '';
            const note = c.note ? this.escapeHtml(c.note) : '';
            const preview = note || subject || '(no note)';
            const day = c.day || coord.slice(0, 10);

            // Source color mapping (like lexicon status colors)
            let srcColor, srcBg, srcGlow;
            switch (c.source) {
                case 'ui':
                    srcColor = 'var(--success)'; srcBg = 'rgba(0,255,136,0.12)'; srcGlow = 'rgba(0,255,136,0.3)'; break;
                case 'system':
                    srcColor = 'var(--gpt-oss)'; srcBg = 'rgba(0,212,255,0.12)'; srcGlow = 'rgba(0,212,255,0.3)'; break;
                case 'lakespeak':
                    srcColor = '#ffd700'; srcBg = 'rgba(255,215,0,0.12)'; srcGlow = 'rgba(255,215,0,0.3)'; break;
                default:
                    srcColor = 'var(--text-secondary)'; srcBg = 'rgba(255,255,255,0.05)'; srcGlow = 'rgba(255,255,255,0.1)'; break;
            }

            return `
            <div style="background: var(--accent-bg); border: 1px solid var(--border); border-radius: 8px; padding: 14px; cursor: pointer; transition: all 0.2s; border-left: 4px solid ${srcColor};"
                 onmouseenter="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 16px ${srcGlow}';"
                 onmouseleave="this.style.transform=''; this.style.boxShadow='';"
                 onclick="app.citShowDetail('${c.cite_id}')">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                    <span style="font-size: 16px; font-weight: 700; color: var(--text-primary);">${this.escapeHtml(coord)}</span>
                    <span style="font-size: 10px; padding: 2px 8px; border-radius: 10px; background: ${srcBg}; color: ${srcColor}; font-weight: 600;">${src}</span>
                </div>
                <div style="font-size: 12px; color: var(--text-secondary); margin-bottom: 8px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${preview}</div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <div style="flex: 1; height: 6px; background: var(--border); border-radius: 3px; overflow: hidden;">
                        <div style="width: 100%; height: 100%; background: linear-gradient(90deg, ${srcColor}, transparent); border-radius: 3px;"></div>
                    </div>
                    <span style="font-size: 11px; font-weight: 600; color: var(--text-secondary); min-width: 70px; text-align: right;">${day}</span>
                </div>
            </div>`;
        }).join('');
    }

    async citShowDetail(citeId) {
        this._citActiveCiteId = citeId;
        const c = this._citItems.find(x => x.cite_id === citeId);
        if (!c) return;

        // Highlight active card
        document.querySelectorAll('.cit-card').forEach(el => {
            el.classList.toggle('cit-active', el.dataset.citeId === citeId);
        });

        const drawer = document.getElementById('cit-detail-drawer');
        const body = document.getElementById('cit-detail-body');
        const jsonEl = document.getElementById('cit-detail-json');
        const titleEl = document.getElementById('cit-detail-title');

        titleEl.textContent = c.coord || c.canonical || citeId;

        body.innerHTML = `
            <div style="display: grid; grid-template-columns: 100px 1fr; gap: 8px 12px; font-size: 12px;">
                <span style="color: var(--text-secondary);">Cite ID</span>
                <span style="font-family: var(--mono); font-size: 11px;">${this.escapeHtml(c.cite_id)}</span>

                <span style="color: var(--text-secondary);">Coordinate</span>
                <input class="cit-edit-field" id="cit-edit-coord" value="${this.escapeHtml(c.coord || c.canonical || '')}">

                <span style="color: var(--text-secondary);">Subject</span>
                <input class="cit-edit-field" id="cit-edit-subject" value="${this.escapeHtml(c.subject || '')}">

                <span style="color: var(--text-secondary);">Note</span>
                <textarea class="cit-edit-field" id="cit-edit-note" rows="3">${this.escapeHtml(c.note || '')}</textarea>

                <span style="color: var(--text-secondary);">Source</span>
                <span>${c.source || 'unknown'}</span>

                <span style="color: var(--text-secondary);">Day</span>
                <span>${c.day || '?'}</span>

                <span style="color: var(--text-secondary);">Created</span>
                <span>${(c.created_at_utc || '').replace('T', ' ')}</span>

                <span style="color: var(--text-secondary);">Block</span>
                <span>${c.message_id || '?'}:${c.block_id || '?'}</span>
            </div>
            <div style="display: flex; gap: 8px; margin-top: 14px;">
                <button class="btn btn-sm" style="background: #00d4ff; color: #000; font-weight: 700;"
                        onclick="app.citSave('${citeId}')">Save Changes</button>
                <button class="btn btn-sm" style="border-color: #ffd700; color: #ffd700;"
                        onclick="app.citDetach('${citeId}')">Detach</button>
                <button class="btn btn-sm" style="border-color: #ff4444; color: #ff4444;"
                        onclick="app.citHardDelete('${citeId}')">Hard Delete</button>
            </div>`;

        jsonEl.textContent = JSON.stringify(c, null, 2);
        drawer.style.display = '';
    }

    citCloseDetail() {
        document.getElementById('cit-detail-drawer').style.display = 'none';
        this._citActiveCiteId = null;
        document.querySelectorAll('.cit-card.cit-active').forEach(el =>
            el.classList.remove('cit-active'));
    }

    citToggleJson() {
        const el = document.getElementById('cit-detail-json');
        el.style.display = el.style.display === 'none' ? '' : 'none';
    }

    async citSave(citeId) {
        const coord = document.getElementById('cit-edit-coord')?.value.trim();
        const subject = document.getElementById('cit-edit-subject')?.value.trim();
        const note = document.getElementById('cit-edit-note')?.value.trim();

        try {
            const res = await fetch(`${this.citeBase}/api/citations/edit`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ cite_id: citeId, coord, subject, note })
            });
            const data = await res.json();
            if (data.ok && data.cite) {
                // Update in-memory
                const idx = this._citItems.findIndex(x => x.cite_id === citeId);
                if (idx >= 0) this._citItems[idx] = data.cite;
                this._citRenderFiltered();
                this.citShowDetail(citeId);
                this.addLog(`Citation ${citeId.slice(0, 12)}... saved`, 'success');
            } else {
                this.addLog(`Save failed: ${data.detail || 'unknown error'}`, 'error');
            }
        } catch (e) {
            this.addLog(`Save failed: ${e.message}`, 'error');
        }
    }

    async citDetach(citeId) {
        if (!confirm('Detach this citation from its block? (citation record preserved for re-attach)')) return;
        await this._citDelete(citeId, false);
    }

    async citHardDelete(citeId) {
        if (!confirm('PERMANENTLY delete this citation from all indexes? This cannot be undone.')) return;
        await this._citDelete(citeId, true);
    }

    async _citDelete(citeId, hard) {
        try {
            const res = await fetch(`${this.citeBase}/api/citations/delete`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ cite_id: citeId, hard })
            });
            const data = await res.json();
            if (data.ok) {
                this._citItems = this._citItems.filter(x => x.cite_id !== citeId);
                this._citRenderFiltered();
                this.citCloseDetail();
                this.addLog(`Citation ${citeId.slice(0, 12)}... ${hard ? 'deleted' : 'detached'}`, 'success');
            } else {
                this.addLog(`Delete failed: ${data.detail || 'unknown error'}`, 'error');
            }
        } catch (e) {
            this.addLog(`Delete failed: ${e.message}`, 'error');
        }
    }

    async citRunHealth() {
        const reportEl = document.getElementById('cit-health-report');
        const bodyEl = document.getElementById('cit-health-body');
        const statusEl = document.getElementById('cit-stat-health');

        try {
            const res = await fetch(`${this.citeBase}/api/citations/health?days=30`, {
                credentials: 'include'
            });
            const h = await res.json();

            reportEl.style.display = '';
            reportEl.style.borderColor = h.clean ? '#00ff88' : '#ff4444';

            const rows = [
                { label: 'Total citations', value: h.total_cites, color: '#00d4ff' },
                { label: 'Days scanned', value: `${h.scanned_days} / ${h.total_days}`, color: '#00d4ff' },
                { label: 'Orphaned', value: h.orphaned?.length || 0, color: h.orphaned?.length ? '#ff4444' : '#00ff88' },
                { label: 'Dangling refs', value: h.dangling?.length || 0, color: h.dangling?.length ? '#ff4444' : '#00ff88' },
                { label: 'Stale sidecars', value: h.stale?.length || 0, color: h.stale?.length ? '#ffd700' : '#00ff88' },
                { label: 'Duplicates', value: h.duplicates?.length || 0, color: h.duplicates?.length ? '#ffd700' : '#00ff88' },
                { label: 'Cross-day collisions', value: h.cross_day?.length || 0, color: h.cross_day?.length ? '#ff4444' : '#00ff88' },
            ];

            bodyEl.innerHTML = rows.map(r => `
                <div class="cit-health-row">
                    <span class="cit-health-dot" style="background: ${r.color};"></span>
                    <span style="flex: 1;">${r.label}</span>
                    <span style="font-weight: 700; color: ${r.color};">${r.value}</span>
                </div>
            `).join('');

            // Detail sections for failures
            const sections = [
                { key: 'orphaned', label: 'Orphaned Citations', items: h.orphaned },
                { key: 'dangling', label: 'Dangling References', items: h.dangling },
                { key: 'duplicates', label: 'Duplicate Coords', items: h.duplicates },
                { key: 'cross_day', label: 'Cross-Day Collisions', items: h.cross_day },
            ];
            for (const sec of sections) {
                if (sec.items && sec.items.length > 0) {
                    bodyEl.innerHTML += `
                        <div style="margin-top: 12px; font-size: 11px;">
                            <strong style="color: #ff4444;">${sec.label} (${sec.items.length}):</strong>
                            <div style="margin-top: 4px; font-family: var(--mono); max-height: 120px; overflow-y: auto;">
                                ${sec.items.slice(0, 20).map(x => `<div style="padding: 2px 0; color: var(--text-secondary);">${JSON.stringify(x)}</div>`).join('')}
                                ${sec.items.length > 20 ? `<div style="color: var(--text-secondary);">... and ${sec.items.length - 20} more</div>` : ''}
                            </div>
                        </div>`;
                }
            }

            if (h.stale && h.stale.length > 0) {
                bodyEl.innerHTML += `
                    <div style="margin-top: 12px; font-size: 11px;">
                        <strong style="color: #ffd700;">Stale Sidecars (${h.stale.length}):</strong>
                        <span style="color: var(--text-secondary);"> ${h.stale.join(', ')}</span>
                    </div>`;
            }

            if (statusEl) {
                statusEl.textContent = h.clean ? 'CLEAN' : `${(h.orphaned?.length || 0) + (h.dangling?.length || 0) + (h.duplicates?.length || 0) + (h.cross_day?.length || 0)} issues`;
                statusEl.style.color = h.clean ? '#00ff88' : '#ff4444';
            }

            this.addLog(`Health check: ${h.clean ? 'CLEAN' : 'issues found'}`, h.clean ? 'success' : 'warning');
        } catch (e) {
            this.addLog(`Health check failed: ${e.message}`, 'error');
        }
    }

    // ── Notes Explorer ─────────────────────────────────────

    _noteItems = [];
    _noteCursor = null;
    _noteSearchQuery = '';
    _noteActiveNoteId = null;
    _noteDistribution = null;

    async noteUpdateExplorerStats() {
        try {
            const resp = await fetch(`${this.citeBase}/api/notes/distribution`, {
                credentials: 'include'
            });
            const data = await resp.json();
            this._noteDistribution = data;

            const totalEl = document.getElementById('note-stat-total');
            const daysEl = document.getElementById('note-stat-days');
            if (totalEl) totalEl.textContent = (data.total || 0).toLocaleString();
            if (daysEl) daysEl.textContent = (data.days || []).length;

            this._noteRenderDayDistribution(data.days || []);
            this._noteBuildDateStrip(data.days || []);
        } catch (e) {
            console.warn('Note distribution fetch failed:', e);
        }
    }

    _noteRenderDayDistribution(days) {
        const chart = document.getElementById('note-distribution-chart');
        const label = document.getElementById('note-chart-label');
        if (!chart) return;

        if (days.length === 0) {
            chart.innerHTML = '<span style="color: var(--text-secondary); font-size: 12px;">No notes data</span>';
            if (label) label.textContent = '';
            return;
        }

        const chartDays = days.slice(0, 30).reverse();
        const maxCount = Math.max(1, ...chartDays.map(d => d.count));
        const totalNotes = days.reduce((s, d) => s + d.count, 0);
        if (label) label.textContent = `${totalNotes.toLocaleString()} notes across ${days.length} days`;

        const barColors = [
            '#b388ff', '#ff6bd6', '#00d4ff', '#00ff88', '#ffd700',
            '#ff9f43', '#e94560', '#9b59b6', '#0077b6', '#c23152',
        ];
        chart.innerHTML = chartDays.map((d, i) => {
            const pct = Math.max(4, (d.count / maxCount) * 100);
            const color = barColors[i % barColors.length];
            const shortDay = d.day.slice(5);
            return `<div style="flex:1; display:flex; flex-direction:column; align-items:center; gap:2px; cursor:pointer;" title="${d.day}: ${d.count} notes" onclick="app.noteBrowseDay('${d.day}')">
                <span style="font-size:9px; color:var(--text-secondary);">${d.count}</span>
                <div style="width:100%; height:${pct}%; min-height:3px; background:${color}; border-radius:3px 3px 0 0; transition:height 0.3s;"></div>
                <span style="font-size:9px; font-weight:700; color:${color};">${shortDay}</span>
            </div>`;
        }).join('');
    }

    _noteBuildDateStrip(days) {
        const strip = document.getElementById('note-date-strip');
        if (!strip) return;
        strip.innerHTML = '';
        days.forEach(d => {
            const btn = document.createElement('button');
            btn.className = 'btn btn-sm';
            btn.style.cssText = 'padding:4px 8px;font-size:11px;font-weight:700;min-width:28px;background:var(--accent-bg);color:var(--text-secondary);border:1px solid var(--border);cursor:pointer;transition:all 0.15s;';
            btn.textContent = d.day.slice(5);
            btn.title = `${d.day}: ${d.count} notes`;
            btn.onclick = () => this.noteBrowseDay(d.day);
            btn.onmouseenter = () => { btn.style.background = '#b388ff'; btn.style.color = '#000'; };
            btn.onmouseleave = () => { btn.style.background = 'var(--accent-bg)'; btn.style.color = 'var(--text-secondary)'; };
            strip.appendChild(btn);
        });
    }

    async noteBrowseDay(day) {
        try {
            const resp = await fetch(`${this.citeBase}/api/notes/all?limit=1&cursor=${
                (() => {
                    const d = new Date(day + 'T00:00:00Z');
                    d.setUTCDate(d.getUTCDate() + 1);
                    return d.toISOString().slice(0, 10);
                })()
            }`, { credentials: 'include' });
            const data = await resp.json();
            const dayItems = (data.items || []).filter(n => n.day === day);

            const existingIds = new Set(this._noteItems.map(n => n.note_id));
            for (const item of dayItems) {
                if (!existingIds.has(item.note_id)) this._noteItems.push(item);
            }

            this._noteRenderResults(dayItems);
            const meta = document.getElementById('note-result-meta');
            if (meta) {
                meta.style.display = 'block';
                meta.innerHTML = `<span style="color: #b388ff;">${dayItems.length}</span> notes — ${day}`;
            }
        } catch (e) {
            this.addLog(`Failed to browse notes day ${day}: ${e.message}`, 'error');
        }
    }

    async noteLoadAll(reset = true) {
        if (reset) {
            this._noteItems = [];
            this._noteCursor = null;
        }
        const params = new URLSearchParams({ limit: '5' });
        if (this._noteCursor) params.set('cursor', this._noteCursor);

        try {
            const res = await fetch(`${this.citeBase}/api/notes/all?${params}`, {
                credentials: 'include'
            });
            const data = await res.json();
            if (data.items) this._noteItems.push(...data.items);
            this._noteCursor = data.next_cursor || null;

            const totalEl = document.getElementById('note-stat-total');
            const daysEl = document.getElementById('note-stat-days');
            if (totalEl) totalEl.textContent = this._noteItems.length;
            if (daysEl) daysEl.textContent = data.total_days || 0;

            // Count unique blocks
            const blocksEl = document.getElementById('note-stat-blocks');
            if (blocksEl) {
                const blockSet = new Set(this._noteItems.map(n => `${n.message_id}:${n.block_id}`));
                blocksEl.textContent = blockSet.size;
            }

            const metaEl = document.getElementById('note-result-meta');
            if (metaEl) {
                metaEl.style.display = 'block';
                metaEl.textContent = data.next_cursor
                    ? `Showing ${this._noteItems.length} notes (more available)`
                    : `${this._noteItems.length} notes total`;
            }

            this._noteRenderFiltered();
        } catch (e) {
            this.addLog(`Notes load failed: ${e.message}`, 'error');
        }
    }

    noteLoadMore() {
        if (!this._noteCursor) {
            this.addLog('No more notes to load', 'info');
            return;
        }
        this.noteLoadAll(false);
    }

    noteSearch(query) {
        this._noteSearchQuery = (query || '').toLowerCase().trim();
        this._noteRenderFiltered();
    }

    _noteRenderFiltered() {
        let items = this._noteItems;
        if (this._noteSearchQuery) {
            const q = this._noteSearchQuery;
            items = items.filter(n =>
                (n.note || '').toLowerCase().includes(q) ||
                (n.note_id || '').toLowerCase().includes(q) ||
                (n.message_id || '').toLowerCase().includes(q) ||
                (n.block_id || '').toLowerCase().includes(q)
            );
        }
        this._noteRenderResults(items);
    }

    _noteRenderResults(items) {
        const grid = document.getElementById('note-results');
        const meta = document.getElementById('note-result-meta');
        if (!grid) return;

        if (meta) {
            meta.style.display = items.length > 0 ? 'block' : 'none';
            meta.innerHTML = `<span style="color: #b388ff;">${items.length}</span> notes`;
        }

        if (items.length === 0) {
            grid.innerHTML = `<div style="grid-column:1/-1; text-align: center; padding: 30px; color: var(--text-secondary);">
                ${this._noteItems.length === 0 ? 'No notes loaded yet.' : 'No notes match the current filter.'}
            </div>`;
            return;
        }

        grid.innerHTML = items.map(n => {
            const noteText = n.note ? this.escapeHtml(n.note) : '(empty)';
            const preview = noteText.length > 120 ? noteText.slice(0, 120) + '...' : noteText;
            const day = n.day || '?';
            const block = `${n.message_id || '?'}:${n.block_id || '?'}`;
            const ts = n.ts ? new Date(n.ts).toLocaleTimeString() : '';

            return `
            <div style="background: var(--accent-bg); border: 1px solid var(--border); border-radius: 8px; padding: 14px; cursor: pointer; transition: all 0.2s; border-left: 4px solid #b388ff;"
                 onmouseenter="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 16px rgba(179,136,255,0.3)';"
                 onmouseleave="this.style.transform=''; this.style.boxShadow='';"
                 onclick="app.noteShowDetail('${n.note_id}')">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                    <span style="font-size: 12px; font-weight: 600; color: var(--text-secondary); font-family: var(--mono);">${this.escapeHtml(block)}</span>
                    <span style="font-size: 10px; padding: 2px 8px; border-radius: 10px; background: rgba(179,136,255,0.12); color: #b388ff; font-weight: 600;">${ts}</span>
                </div>
                <div style="font-size: 13px; color: var(--text-primary); margin-bottom: 8px; line-height: 1.4;">${preview}</div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <div style="flex: 1; height: 6px; background: var(--border); border-radius: 3px; overflow: hidden;">
                        <div style="width: 100%; height: 100%; background: linear-gradient(90deg, #b388ff, transparent); border-radius: 3px;"></div>
                    </div>
                    <span style="font-size: 11px; font-weight: 600; color: var(--text-secondary); min-width: 70px; text-align: right;">${day}</span>
                </div>
            </div>`;
        }).join('');
    }

    async noteShowDetail(noteId) {
        this._noteActiveNoteId = noteId;
        const n = this._noteItems.find(x => x.note_id === noteId);
        if (!n) return;

        const drawer = document.getElementById('note-detail-drawer');
        const body = document.getElementById('note-detail-body');
        const jsonEl = document.getElementById('note-detail-json');
        const titleEl = document.getElementById('note-detail-title');

        titleEl.textContent = `Note — ${n.message_id || '?'}:${n.block_id || '?'}`;

        body.innerHTML = `
            <div style="display: grid; grid-template-columns: 100px 1fr; gap: 8px 12px; font-size: 12px;">
                <span style="color: var(--text-secondary);">Note ID</span>
                <span style="font-family: var(--mono); font-size: 11px;">${this.escapeHtml(n.note_id)}</span>

                <span style="color: var(--text-secondary);">Note</span>
                <textarea class="cit-edit-field" id="note-edit-text" rows="4">${this.escapeHtml(n.note || '')}</textarea>

                <span style="color: var(--text-secondary);">Day</span>
                <span>${n.day || '?'}</span>

                <span style="color: var(--text-secondary);">Block</span>
                <span>${n.message_id || '?'}:${n.block_id || '?'}</span>

                <span style="color: var(--text-secondary);">Ordinal</span>
                <span>${n.block_ordinal ?? '?'}</span>

                <span style="color: var(--text-secondary);">Created</span>
                <span>${n.ts ? new Date(n.ts).toLocaleString() : '?'}</span>
            </div>
            <div style="display: flex; gap: 8px; margin-top: 14px;">
                <button class="btn btn-sm" style="background: #b388ff; color: #000; font-weight: 700;"
                        onclick="app.noteSave('${noteId}')">Save Changes</button>
                <button class="btn btn-sm" style="border-color: #ff4444; color: #ff4444;"
                        onclick="app.noteHardDelete('${noteId}')">Delete</button>
            </div>`;

        jsonEl.textContent = JSON.stringify(n, null, 2);
        drawer.style.display = '';
    }

    noteCloseDetail() {
        document.getElementById('note-detail-drawer').style.display = 'none';
        this._noteActiveNoteId = null;
    }

    noteToggleJson() {
        const el = document.getElementById('note-detail-json');
        el.style.display = el.style.display === 'none' ? '' : 'none';
    }

    async noteSave(noteId) {
        const noteText = document.getElementById('note-edit-text')?.value.trim();

        try {
            const res = await fetch(`${this.citeBase}/api/notes/edit`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ note_id: noteId, note: noteText })
            });
            const data = await res.json();
            if (data.ok && data.note) {
                const idx = this._noteItems.findIndex(x => x.note_id === noteId);
                if (idx >= 0) this._noteItems[idx] = data.note;
                this._noteRenderFiltered();
                this.noteShowDetail(noteId);
                this.addLog(`Note ${noteId.slice(0, 12)}... saved`, 'success');
            } else {
                this.addLog(`Save failed: ${data.detail || 'unknown error'}`, 'error');
            }
        } catch (e) {
            this.addLog(`Save failed: ${e.message}`, 'error');
        }
    }

    async noteHardDelete(noteId) {
        if (!confirm('PERMANENTLY delete this note? This cannot be undone.')) return;
        try {
            const res = await fetch(`${this.citeBase}/api/notes/delete`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ note_id: noteId })
            });
            const data = await res.json();
            if (data.ok) {
                this._noteItems = this._noteItems.filter(x => x.note_id !== noteId);
                this._noteRenderFiltered();
                this.noteCloseDetail();
                this.addLog(`Note ${noteId.slice(0, 12)}... deleted`, 'success');
            } else {
                this.addLog(`Delete failed: ${data.detail || 'unknown error'}`, 'error');
            }
        } catch (e) {
            this.addLog(`Delete failed: ${e.message}`, 'error');
        }
    }

    // ── Update Pipeline ─────────────────────────────────────
    async runUpdate(messageId) {
        const msg = this._messageStore.get(messageId);
        if (!msg) return;

        const totalNotes = Object.values(msg.notesByBlock)
            .reduce((sum, arr) => sum + arr.length, 0);
        if (totalNotes === 0) return;

        const annotatedBlocks = msg.blocks.map(b => ({
            block_id: b.block_id,
            type: b.type,
            text: b.text,
            notes: (msg.notesByBlock[b.block_id] || []).map(n => n.note)
        }));

        // Walk DOM backward to find the user prompt that generated this response
        let originPrompt = '';
        if (msg.element) {
            let prev = msg.element.previousElementSibling;
            while (prev) {
                if (prev.classList.contains('user')) {
                    const contentEl = prev.querySelector('.message-content');
                    if (contentEl) originPrompt = contentEl.textContent.trim();
                    break;
                }
                prev = prev.previousElementSibling;
            }
        }

        const btn = msg.element.querySelector('.btn-update');
        if (btn) { btn.disabled = true; btn.textContent = '\u27f3 UPDATING...'; }

        try {
            const endpoint = this.gptEndpoint;
            const model = this._getRevisionModel(messageId);

            let revisionPrompt = '';
            if (originPrompt) {
                revisionPrompt += `The user originally asked: "${originPrompt}"\n\n`;
                revisionPrompt += 'Below is the assistant\'s response, broken into blocks. The user has annotated some blocks with correction notes.\n';
            }
            revisionPrompt += 'Revise the full response block-by-block. Apply the user notes to their respective blocks. Rules:\n';
            revisionPrompt += '- Notes win over original text\n';
            revisionPrompt += '- Do not invent new facts\n';
            revisionPrompt += '- Keep structure close unless notes require restructure\n';
            revisionPrompt += '- Preserve blocks without notes as-is\n\n';

            for (const ab of annotatedBlocks) {
                revisionPrompt += `[Block ${ab.block_id}]\n${ab.text}\n`;
                if (ab.notes.length > 0) {
                    for (const note of ab.notes) {
                        revisionPrompt += `  \u2192 NOTE: ${note}\n`;
                    }
                }
                revisionPrompt += '\n';
            }

            revisionPrompt += 'Produce the revised answer as plain text. Maintain paragraph structure.';

            const { body } = inferenceCtrl
                ? inferenceCtrl.buildRequestBody(model, revisionPrompt)
                : { body: { model, prompt: revisionPrompt, stream: false } };

            // Revision calls get their own system prompt — bypass archive/history
            body.system_prompt = 'You are revising a previous response based on user correction notes. '
                + 'Apply the notes faithfully. Do not refuse or say you cannot find information. '
                + 'The notes and original text are your complete context.';

            console.log(`[revision] model=${model}, notes=${totalNotes}, prompt_len=${revisionPrompt.length}`);

            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify(body)
            });

            if (response.ok) {
                const data = await response.json();
                let reply = data.response || data.content || 'No response';

                reply = reply.replace(/\u27e6END\u27e7/g, '').trim();
                reply = reply.replace(/Need continuation\.?/g, '').trim();

                const revisionMsgId = this.addGptMessage('assistant', reply,
                    data.citations || null,
                    data.retrieval_context || null,
                    data.created_at,
                    data.model ? `${data.model} (revision)` : 'assistant (revision)',
                    null,
                    data.inference_params || null);

                // Store revision links on all annotated blocks → re-render to show links
                if (!msg.revisionLinks) msg.revisionLinks = {};
                for (const ab of annotatedBlocks) {
                    if (ab.notes.length > 0) {
                        msg.revisionLinks[ab.block_id] = revisionMsgId;
                    }
                }
                this._rerenderMessage(messageId);

                this.addLog(`Update applied from ${messageId} \u2192 ${revisionMsgId}`, 'success');
            } else {
                throw new Error(`Revision failed: ${response.status}`);
            }
        } catch (error) {
            this.addGptMessage('system', `Update error: ${error.message}`);
            this.addLog(`Update failed: ${error.message}`, 'error');
        } finally {
            if (btn) { btn.disabled = false; btn.textContent = '\u27f3 UPDATE'; }
        }
    }

    // ── Regenerate (user messages) ───────────────────────
    async runRegenerate(messageId) {
        const msg = this._messageStore.get(messageId);
        if (!msg || msg.role !== 'user') return;

        const annotatedBlocks = msg.blocks.map(b => ({
            block_id: b.block_id,
            text: b.text,
            notes: (msg.notesByBlock[b.block_id] || []).map(n => n.note)
        }));

        const hasNotes = annotatedBlocks.some(ab => ab.notes.length > 0);
        if (!hasNotes) {
            this.addLog('No context notes to regenerate with', 'warning');
            return;
        }

        const btn = msg.element.querySelector('.btn-regenerate');
        if (btn) { btn.disabled = true; btn.textContent = '\u27f3 REGENERATING...'; }

        try {
            // Build enriched prompt: original + injected context
            let enrichedPrompt = msg.text + '\n\n';
            enrichedPrompt += '--- ADDITIONAL CONTEXT (added by user after original message) ---\n';
            for (const ab of annotatedBlocks) {
                if (ab.notes.length > 0) {
                    enrichedPrompt += `[Re: "${ab.text.slice(0, 80)}${ab.text.length > 80 ? '...' : ''}"]\n`;
                    for (const note of ab.notes) {
                        enrichedPrompt += `  \u2192 ${note}\n`;
                    }
                }
            }
            enrichedPrompt += '--- END ADDITIONAL CONTEXT ---\n';
            enrichedPrompt += 'Answer the original question incorporating the additional context. Do not mention the context injection itself.';

            // Mark old assistant response as superseded
            let nextEl = msg.element.nextElementSibling;
            while (nextEl) {
                if (nextEl.classList.contains('chat-message') &&
                    nextEl.classList.contains('assistant')) {
                    if (!nextEl.querySelector('.superseded-tag')) {
                        const tag = document.createElement('div');
                        tag.className = 'superseded-tag';
                        tag.textContent = '\u2193 superseded by regeneration below';
                        const header = nextEl.querySelector('.message-header');
                        if (header) header.appendChild(tag);
                    }
                    nextEl.classList.add('superseded');
                    break;
                }
                nextEl = nextEl.nextElementSibling;
            }

            const endpoint = this.gptEndpoint;
            const model = this._getRevisionModel(messageId);

            const { body } = inferenceCtrl
                ? inferenceCtrl.buildRequestBody(model, enrichedPrompt)
                : { body: { model, prompt: enrichedPrompt, stream: false } };

            // Regeneration gets its own system prompt — bypass archive/history
            const noteCount = annotatedBlocks.filter(a => a.notes.length > 0).length;
            body.system_prompt = 'You are answering a question with additional context notes provided by the user. '
                + 'Incorporate the notes naturally. Do not refuse or say you cannot find information. '
                + 'The question and notes are your complete context.';

            console.log(`[regenerate] model=${model}, notes=${noteCount}, prompt_len=${enrichedPrompt.length}`);

            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify(body)
            });

            if (response.ok) {
                const data = await response.json();
                let reply = data.response || data.content || 'No response';
                reply = reply.replace(/\u27e6END\u27e7/g, '').trim();
                reply = reply.replace(/Need continuation\.?/g, '').trim();

                this.addGptMessage('assistant', reply,
                    data.citations || null,
                    data.retrieval_context || null,
                    data.created_at,
                    data.model ? `${data.model} (regenerated)` : 'assistant (regenerated)',
                    null,
                    data.inference_params || null);

                this.addLog(`Regenerated from ${messageId} with ${annotatedBlocks.filter(a => a.notes.length > 0).length} context notes`, 'success');
            } else {
                throw new Error(`Regeneration failed: ${response.status}`);
            }
        } catch (error) {
            this.addGptMessage('system', `Regenerate error: ${error.message}`);
            this.addLog(`Regenerate failed: ${error.message}`, 'error');
        } finally {
            if (btn) { btn.disabled = false; btn.textContent = '\u27f3 REGENERATE'; }
        }
    }

    // ── Chain interrupt: user steering input ───────────────
    _showChainInterrupt(chainState, originalPayload) {
        const interruptSlot = chainState.interrupted_after_slot;
        const remaining = chainState.remaining_slot_ids || [];

        const interruptId = `chain-interrupt-${Date.now()}`;
        const html = `<div class="chain-interrupt-bar" id="${interruptId}">
            <div class="chain-interrupt-header">
                <span>Chain paused after Slot ${interruptSlot} — ${remaining.length} slot${remaining.length !== 1 ? 's' : ''} remaining</span>
            </div>
            <textarea class="chain-interrupt-input" placeholder="Add steering, context, or corrections..."
                      rows="3" style="width:100%;resize:vertical;"></textarea>
            <div style="display:flex;gap:8px;margin-top:4px;">
                <button class="btn-update chain-interrupt-continue"
                        onclick="app._resumeChain('${interruptId}')">Continue Chain</button>
                <button class="btn-update chain-interrupt-skip"
                        onclick="app._resumeChain('${interruptId}', true)">Skip (no input)</button>
            </div>
        </div>`;

        const chatWindow = document.getElementById('chat-window');
        if (chatWindow) {
            chatWindow.insertAdjacentHTML('beforeend', html);
            chatWindow.scrollTop = chatWindow.scrollHeight;
        }

        // Stash state for resume
        const el = document.getElementById(interruptId);
        if (el) {
            el._chainState = chainState;
            el._originalPayload = originalPayload;
        }
    }

    async _resumeChain(interruptId, skipInput = false) {
        const el = document.getElementById(interruptId);
        if (!el) return;

        const chainState = el._chainState;
        const originalPayload = el._originalPayload;
        const textarea = el.querySelector('.chain-interrupt-input');
        const userSteering = skipInput ? '' : (textarea?.value?.trim() || '');

        // Disable controls
        el.querySelectorAll('button').forEach(b => { b.disabled = true; });
        if (textarea) textarea.disabled = true;

        // Show user steering as a message if provided
        if (userSteering) {
            this.addGptMessage('user', `[Chain steering] ${userSteering}`);
        }

        // Build resume payload — same as original but with chain_resume
        const resumePayload = { ...originalPayload };
        resumePayload.chain_resume = {
            ...chainState,
            user_steering: userSteering,
        };

        try {
            this.addLog('Resuming chain...', 'info');
            const response = await fetch('/api/chat/send', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify(resumePayload),
            });

            if (response.ok) {
                const data = await response.json();
                // Remove the interrupt bar
                el.remove();
                // Process the response through normal chain handling
                this._handleChainResumeResponse(data, resumePayload);
            } else {
                const errText = await response.text();
                this.addGptMessage('system', `Chain resume failed: ${errText}`);
                el.querySelectorAll('button').forEach(b => { b.disabled = false; });
                if (textarea) textarea.disabled = false;
            }
        } catch (error) {
            this.addGptMessage('system', `Chain resume error: ${error.message}`);
            el.querySelectorAll('button').forEach(b => { b.disabled = false; });
            if (textarea) textarea.disabled = false;
        }
    }

    _handleChainResumeResponse(data, payload) {
        if (data.error) {
            this.addGptMessage('system', `Chain resume: ${data.error.message || JSON.stringify(data.error)}`);
            return;
        }

        if (data.contributions && data.contributions.length > 0) {
            const now = new Date().toISOString().replace('T', ' ').slice(0, 19) + 'Z';
            for (const contrib of data.contributions) {
                // Skip contributions we already rendered (user interrupt + prior slots)
                if (contrib.author === 'user' && contrib.provider === 'human') continue;

                const isHub = contrib.author === 'hub';
                const posLabel = isHub ? 'HUB' : contrib.author.replace('slot_', 'SLOT ').toUpperCase();
                const provName = contrib.provider || 'local';
                const modelName = contrib.model || '?';
                const msLabel = contrib.ms ? `${contrib.ms}ms` : '';
                const headerClass = isHub ? 'hub' : 'slot';

                const chainHeader = `<div class="chain-contrib-header ${headerClass}">`
                    + `<span class="chain-contrib-pos">${posLabel}</span>`
                    + `<span class="chain-contrib-identity">${this.escapeHtml(provName)} / ${this.escapeHtml(modelName)}</span>`
                    + `<span class="chain-contrib-ms">${msLabel}</span>`
                    + `<span class="chain-contrib-ts">${now}</span>`
                    + `</div>`;

                const content = contrib.content || '(no response)';
                const providerMap = { ollama: 'ollama', openai: 'openai', anthropic: 'anthropic', google: 'google', xai: 'xai' };
                const seatProv = providerMap[contrib.provider] || contrib.provider || null;

                const msgId = this.addGptMessage('assistant', content, null, null, null,
                                   contrib.model || null, null, null, null, seatProv);
                if (msgId) {
                    const msgEl = document.querySelector(`[data-msg-id="${msgId}"]`);
                    const contentDiv = msgEl?.querySelector('.message-content');
                    if (contentDiv) contentDiv.insertAdjacentHTML('afterbegin', chainHeader);
                }
            }

            // Another interrupt?
            if (data.chain_state) {
                this._showChainInterrupt(data.chain_state, payload);
            }
        } else if (data.response) {
            this.addGptMessage('assistant', data.response);
        }
    }

    // ── Scroll to message (for revision links) ────────────────
    scrollToMessage(targetMsgId) {
        const target = this._messageStore.get(targetMsgId);
        if (target && target.element) {
            target.element.scrollIntoView({ behavior: 'smooth', block: 'center' });
            target.element.classList.add('revision-flash');
            setTimeout(() => target.element.classList.remove('revision-flash'), 1500);
        }
    }

    // ── System Lifecycle ──────────────────────────────────────

    anchorworksLock() {
        // Activate lock overlay — pretty splash mode
        const overlay = document.getElementById('lock-overlay');
        overlay.classList.add('active');
        overlay.classList.remove('lock-awake');
        document.getElementById('lock-error').style.display = 'none';
        document.getElementById('lock-unlock-area').style.display = 'none';

        // Ask bridge to trigger Windows screensaver (best-effort)
        fetch(`${this.serverUrl}/api/system/lock`, {
            method: 'POST', credentials: 'include'
        }).catch(() => {});

        this.addLog('Console locked', 'warning');
    }

    async anchorworksUnlock() {
        // Re-authenticate via Windows Hello to unlock
        try {
            await authLogin();
            document.getElementById('lock-overlay').classList.remove('active');
            document.getElementById('lock-overlay').classList.remove('lock-awake');
            document.getElementById('lock-error').style.display = 'none';
            this.addLog('Console unlocked', 'success');
        } catch (e) {
            const err = document.getElementById('lock-error');
            err.textContent = 'Authentication failed — try again';
            err.style.display = 'block';
            setTimeout(() => { err.style.display = 'none'; }, 3000);
        }
    }

    clearGptChat() {
        this._messageStore.clear();
        this._msgCounter = 0;
        document.getElementById('gpt-chat').innerHTML = `
            <div class="chat-message system">
                <div class="message-header">
                    <span>SYSTEM</span>
                    <span>Ready</span>
                </div>
                <div class="message-content">
                    Chat cleared. Ready for new conversation.
                </div>
            </div>
        `;
    }

    // ── Lexicon Browser ─────────────────────────────────────

    initLexiconBrowser() {
        // Alphabet strip
        const strip = document.getElementById('lex-alpha-strip');
        if (strip && !strip.hasChildNodes()) {
            const letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');
            letters.forEach(l => {
                const btn = document.createElement('button');
                btn.className = 'btn btn-sm';
                btn.style.cssText = 'padding:4px 8px;font-size:11px;font-weight:700;min-width:28px;background:var(--accent-bg);color:var(--text-secondary);border:1px solid var(--border);cursor:pointer;transition:all 0.15s;';
                btn.textContent = l;
                btn.onclick = () => this.lexBrowseLetter(l);
                btn.onmouseenter = () => { btn.style.background = 'var(--gpt-oss)'; btn.style.color = '#000'; };
                btn.onmouseleave = () => { btn.style.background = 'var(--accent-bg)'; btn.style.color = 'var(--text-secondary)'; };
                strip.appendChild(btn);
            });
        }
        // Debounced search
        const input = document.getElementById('lexicon-search');
        if (input && !input._lexBound) {
            input._lexBound = true;
            let debounce = null;
            input.addEventListener('input', () => {
                clearTimeout(debounce);
                debounce = setTimeout(() => this.searchLexicon(input.value), 250);
            });
        }
        const symbolKind = document.getElementById('lex-symbol-kind');
        if (symbolKind && !symbolKind._lexBound) {
            symbolKind._lexBound = true;
            symbolKind.value = this._lexSymbolKind;
            symbolKind.addEventListener('change', () => {
                this._lexSymbolKind = symbolKind.value || 'hex';
                if (_explorerMode === 'symbols') {
                    this._lexApplyExplorerChrome();
                    this._lexRenderResults(this._lexLastEntries || [], this._lexLastMeta || 'Symbols');
                    if (this._lexActiveDetailWord) this.lexShowDetail(this._lexActiveDetailWord);
                }
            });
        }
        // Update lexicon stats
        this.updateLexiconStats();

        // Restore explorer mode from localStorage — view toggle only, no auto-fetch
        const savedMode = localStorage.getItem('anchorworks_explorer_mode') || 'lexicon';
        setExplorerMode(savedMode);
    }

    _lexActivePack = 'all';  // current pack filter
    _lexSymbolKind = 'hex';
    _lexLastEntries = [];
    _lexLastMeta = '';
    _lexActiveDetailWord = '';

    _lexApplyExplorerChrome() {
        const symbolMode = _explorerMode === 'symbols';
        const input = document.getElementById('lexicon-search');
        const wrap = document.getElementById('lex-symbol-kind-wrap');
        const chartTitle = document.querySelector('#lex-view-lexicon .card h2');
        if (input) {
            input.placeholder = symbolMode
                ? '🔍 Search lexicon entries, then inspect symbol views...'
                : '🔍 Search by word, binary, hex, or tone...';
        }
        if (wrap) wrap.style.display = symbolMode ? '' : 'none';
        if (chartTitle && chartTitle.textContent.includes('Letter Distribution')) {
            chartTitle.textContent = symbolMode ? '🔣 Symbol Distribution' : '📊 Letter Distribution';
        }
    }

    async updateLexiconStats() {
        const el = (id) => document.getElementById(id);
        try {
            const resp = await fetch(`${this.serverUrl}/api/lexicon/distribution`, {
                credentials: 'include'
            });
            const d = await resp.json();
            if (el('lex-stat-total'))     el('lex-stat-total').textContent     = (d.total || 0).toLocaleString();
            if (el('lex-stat-canonical')) el('lex-stat-canonical').textContent = (d.canonical || 0).toLocaleString();
            if (el('lex-stat-spare'))     el('lex-stat-spare').textContent     = (d.spare_slots || 0).toLocaleString();
            // Render distribution chart
            this._lexRenderDistributionChart(d.letters || {});
        } catch (err) {
            // Fallback: use cached stat
            if (el('lex-stat-total')) el('lex-stat-total').textContent = (el('stat-lexicon')?.textContent || '0');
        }
    }

    async searchLexicon(query) {
        if (!query || query.length < 2) {
            this._lexShowEmpty();
            return;
        }
        try {
            const pack = this._lexActivePack || 'all';
            const resp = await fetch(`${this.serverUrl}/api/search_lexicon?query=${encodeURIComponent(query)}&pack=${pack}`);
            const results = await resp.json();
            this._lexRenderResults(results, `Search: "${query}"`);
        } catch (error) {
            this.addLog(`Lexicon search failed: ${error.message}`, 'error', { source: 'lex', detail: error.message });
        }
    }

    async lexBrowseLetter(letter) {
        try {
            const pack = this._lexActivePack || 'all';
            const resp = await fetch(`${this.serverUrl}/api/lexicon/browse?letter=${letter}&limit=50&pack=${pack}`);
            const data = await resp.json();
            this._lexRenderResults(data.entries || [], `Letter: ${letter.toUpperCase()} (${data.total} entries)`);
        } catch (error) {
            this.addLog(`Lexicon browse failed: ${error.message}`, 'error', { source: 'lex', detail: error.message });
        }
    }

    async lexBrowseRandom() {
        try {
            const pack = this._lexActivePack || 'all';
            const resp = await fetch(`${this.serverUrl}/api/lexicon/sample?count=24&pack=${pack}`);
            const data = await resp.json();
            this._lexRenderResults(data.entries || [], `Random sample from ${(data.total || 0).toLocaleString()} entries`);
        } catch (error) {
            this.addLog(`Lexicon sample failed: ${error.message}`, 'error', { source: 'lex', detail: error.message });
        }
    }

    async lexBrowseTop() {
        try {
            const pack = this._lexActivePack || 'all';
            const resp = await fetch(`${this.serverUrl}/api/lexicon/top?count=30&pack=${pack}`);
            const data = await resp.json();
            this._lexRenderResults(data.entries || [], `\ud83d\udd25 Top ${data.total} by frequency`);
        } catch (error) {
            this.addLog(`Lexicon top failed: ${error.message}`, 'error', { source: 'lex', detail: error.message });
        }
    }

    _lexSymbolValue(entry, kind = this._lexSymbolKind) {
        const payload = entry?.payload || {};
        if (kind === 'font_symbol') return payload.font_symbol || entry?.symbol || '—';
        if (kind === 'tone_signature') return payload.tone_signature || '—';
        if (kind === 'binary') return payload.binary || '—';
        return payload.hex || entry?.symbol || '—';
    }

    async lexShowDetail(word) {
        const drawer = document.getElementById('lex-detail-drawer');
        const title = document.getElementById('lex-detail-title');
        const body = document.getElementById('lex-detail-body');
        if (!drawer || !body) return;

        this._lexActiveDetailWord = word;
        title.innerHTML = `\ud83d\udd0d <span style="color: var(--gpt-oss);">${this.escapeHtml(word)}</span>`;
        body.innerHTML = '<p style="color: var(--text-secondary);">Loading entry...</p>';
        drawer.style.display = 'block';
        drawer.scrollIntoView({ behavior: 'smooth', block: 'start' });

        let html = '';

        // ── Phase 1: Full entry metadata ──
        try {
            const entryResp = await fetch(`${this.serverUrl}/api/lexicon/entry?word=${encodeURIComponent(word)}`);
            if (entryResp.ok) {
                const e = await entryResp.json();
                if (_explorerMode === 'symbols') {
                    const symbolKind = this._lexSymbolKind;
                    const symbolLabel = symbolKind === 'font_symbol'
                        ? 'Font Symbol'
                        : symbolKind === 'tone_signature'
                            ? 'Tone Signature'
                            : symbolKind === 'binary'
                                ? 'Binary'
                                : 'HEX Address';
                    const symbolValue = this._lexSymbolValue(e, symbolKind);
                    title.innerHTML = `<span style="display:block;font-size:10px;text-transform:uppercase;color:var(--text-secondary);letter-spacing:0.08em;margin-bottom:4px;">${symbolLabel}</span><span style="display:block;color:var(--gpt-oss);font-size:${symbolKind === 'binary' ? '18px' : '28px'};font-family:${symbolKind === 'font_symbol' ? 'inherit' : 'Consolas, monospace'};line-height:1.2;word-break:break-word;">${this.escapeHtml(symbolValue)}</span><span style="display:block;font-size:11px;color:var(--text-secondary);margin-top:6px;">${this.escapeHtml(word)}</span>`;
                    html += `<div style="background:linear-gradient(135deg, rgba(0,212,255,0.09), rgba(179,136,255,0.08)); border:1px solid var(--border); border-radius:10px; padding:16px; margin-bottom:16px;">
                        <div style="font-size:10px; text-transform:uppercase; color:var(--text-secondary); margin-bottom:8px;">Primary Symbol View</div>
                        <div style="font-size:${symbolKind === 'binary' ? '18px' : '28px'}; font-family:${symbolKind === 'font_symbol' ? 'inherit' : 'Consolas, monospace'}; color:var(--gpt-oss); font-weight:700; line-height:1.2; word-break:break-word;">${this.escapeHtml(symbolValue)}</div>
                        <div style="font-size:11px; color:var(--text-secondary); margin-top:6px;">word: ${this.escapeHtml(word)}</div>
                    </div>`;
                }
                html += `<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; margin-bottom: 16px;">`;
                // Address block
                html += `<div style="background: var(--primary-bg); border: 1px solid var(--border); border-radius: 8px; padding: 12px;">`;
                html += `<div style="font-size: 10px; text-transform: uppercase; color: var(--text-secondary); margin-bottom: 6px;">Address</div>`;
                if (e.hex)    html += `<div style="font-family: Consolas, monospace; font-size: 12px; color: var(--gpt-oss); margin-bottom: 3px;">HEX ${this.escapeHtml(e.hex)}</div>`;
                if (e.binary) html += `<div style="font-family: Consolas, monospace; font-size: 11px; color: var(--text-secondary); word-break: break-all;">${this.escapeHtml(e.binary)}</div>`;
                html += `</div>`;
                // Status block
                html += `<div style="background: var(--primary-bg); border: 1px solid var(--border); border-radius: 8px; padding: 12px;">`;
                html += `<div style="font-size: 10px; text-transform: uppercase; color: var(--text-secondary); margin-bottom: 6px;">Status</div>`;
                const sc = e.status === 'ASSIGNED' ? 'var(--success)' : 'var(--warning)';
                html += `<div style="color: ${sc}; font-weight: 700; font-size: 14px;">${e.status || 'UNKNOWN'}</div>`;
                if (e.pack) html += `<div style="font-size: 11px; color: #b388ff; margin-top: 4px;">Pack: ${this.escapeHtml(e.pack)}</div>`;
                if (e.mapped_at) html += `<div style="font-size: 11px; color: var(--text-secondary); margin-top: 4px;">Mapped: ${new Date(e.mapped_at).toLocaleDateString()}</div>`;
                html += `</div>`;
                // Frequency block
                html += `<div style="background: var(--primary-bg); border: 1px solid var(--border); border-radius: 8px; padding: 12px;">`;
                html += `<div style="font-size: 10px; text-transform: uppercase; color: var(--text-secondary); margin-bottom: 6px;">Frequency</div>`;
                html += `<div style="font-size: 20px; font-weight: 800; color: var(--gpt-oss);">${(e.frequency || 0).toLocaleString()}</div>`;
                if (e.tone_signature) html += `<div style="font-size: 11px; color: #b388ff; margin-top: 4px;">Tone: ${this.escapeHtml(e.tone_signature)}</div>`;
                if (e.font_symbol) html += `<div style="font-size: 18px; margin-top: 4px;" title="Font symbol">${this.escapeHtml(e.font_symbol)}</div>`;
                html += `</div>`;
                html += `</div>`;

                // WordNet data if present
                if (e.wordnet) {
                    html += `<div style="background: var(--primary-bg); border: 1px solid var(--border); border-radius: 8px; padding: 12px; margin-bottom: 12px;">`;
                    html += `<div style="font-size: 10px; text-transform: uppercase; color: var(--text-secondary); margin-bottom: 8px;">WordNet</div>`;
                    const wn = e.wordnet;
                    if (wn.pos && wn.pos.length) html += `<div style="margin-bottom: 4px;"><span style="color: var(--text-secondary); font-size: 11px;">POS:</span> <span style="color: var(--success); font-size: 12px; font-weight: 600;">${wn.pos.join(', ')}</span></div>`;
                    if (wn.definitions && wn.definitions.length) {
                        html += `<div style="margin-bottom: 4px;"><span style="color: var(--text-secondary); font-size: 11px;">Definitions:</span></div>`;
                        wn.definitions.slice(0, 3).forEach(d => {
                            html += `<div style="font-size: 12px; color: var(--text-primary); padding-left: 12px; margin-bottom: 2px;">\u2022 ${this.escapeHtml(d)}</div>`;
                        });
                    }
                    if (wn.synonyms && wn.synonyms.length) html += `<div style="margin-top: 4px;"><span style="color: var(--text-secondary); font-size: 11px;">Synonyms:</span> <span style="font-size: 12px; color: #ff9f43;">${wn.synonyms.slice(0, 8).map(s => this.escapeHtml(s)).join(', ')}</span></div>`;
                    if (wn.antonyms && wn.antonyms.length) html += `<div style="margin-top: 4px;"><span style="color: var(--text-secondary); font-size: 11px;">Antonyms:</span> <span style="font-size: 12px; color: var(--highlight);">${wn.antonyms.slice(0, 5).map(s => this.escapeHtml(s)).join(', ')}</span></div>`;
                    html += `</div>`;
                }

                // Aliases, categories, notes
                const extras = [];
                if (e.aliases && e.aliases.length) extras.push(`<span style="color: var(--text-secondary); font-size: 11px;">Aliases:</span> <span style="color: #b388ff;">${e.aliases.map(a => this.escapeHtml(a)).join(', ')}</span>`);
                if (e.categories && e.categories.length) extras.push(`<span style="color: var(--text-secondary); font-size: 11px;">Categories:</span> <span style="color: #00ff88;">${e.categories.map(c => this.escapeHtml(c)).join(', ')}</span>`);
                if (e.notes) extras.push(`<span style="color: var(--text-secondary); font-size: 11px;">Notes:</span> <span style="color: var(--text-primary);">${this.escapeHtml(e.notes)}</span>`);
                if (extras.length) {
                    html += `<div style="font-size: 12px; margin-bottom: 12px; display: flex; flex-wrap: wrap; gap: 12px;">${extras.join('')}</div>`;
                }
            }
        } catch (err) {
            html += `<p style="color: var(--text-secondary); font-size: 12px;">Entry metadata unavailable</p>`;
        }

        // ── Phase 2: 6-1-6 Context ──
        html += `<div style="border-top: 1px solid var(--border); padding-top: 12px; margin-top: 4px;">`;
        html += `<h3 style="font-size: 13px; color: var(--gpt-oss); margin: 0 0 10px;">6-1-6 Context Map</h3>`;
        try {
            const resp = await fetch(`${this.serverUrl}/api/616`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ word }),
            });
            const data = await resp.json();

            if (!data.total_windows || data.total_windows === 0) {
                html += `<p style="color: var(--text-secondary); font-size: 12px;">No 6-1-6 context yet. Run a mapping job to generate windows.</p>`;
            } else {
                html += `<div style="display: flex; gap: 16px; margin-bottom: 10px; font-size: 12px;">`;
                html += `<span style="color: var(--text-secondary);">Windows: <strong style="color: var(--success);">${data.total_windows.toLocaleString()}</strong></span>`;
                html += `</div>`;
                html += this._lex616Section('\u25c0 Before', data.before, 'var(--highlight)');
                html += this._lex616Section('After \u25b6', data.after, 'var(--gpt-oss)');
            }
        } catch (error) {
            html += `<p style="color: var(--danger); font-size: 12px;">Context load failed: ${this.escapeHtml(error.message)}</p>`;
        }
        html += `</div>`;

        body.innerHTML = html;
    }

    _lex616Section(label, buckets, accentColor) {
        if (!buckets || Object.keys(buckets).length === 0) {
            return `<p style="color: var(--text-secondary); font-size: 12px; margin: 8px 0;">${label}: No data</p>`;
        }
        let html = `<h3 style="font-size: 13px; color: ${accentColor}; margin: 12px 0 8px;">${label}</h3>`;
        html += `<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 8px;">`;

        // Sort distances
        const distances = Object.keys(buckets).sort((a, b) => parseInt(a) - parseInt(b));
        for (const dist of distances) {
            const items = buckets[dist];
            if (!items || items.length === 0) continue;
            const maxCount = items[0][1] || 1;
            html += `<div style="background: var(--primary-bg); border-radius: 6px; padding: 10px; border: 1px solid var(--border);">`;
            html += `<div style="font-size: 10px; color: var(--text-secondary); text-transform: uppercase; margin-bottom: 6px;">Distance ${dist}</div>`;
            for (const [anchor, count] of items.slice(0, 8)) {
                const pct = Math.max(8, (count / maxCount) * 100);
                html += `<div style="display: flex; align-items: center; gap: 6px; margin-bottom: 3px;">`;
                html += `<span style="flex-shrink: 0; width: 70px; font-size: 12px; font-family: Consolas, monospace; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: var(--text-primary);" title="${this.escapeHtml(anchor)}">${this.escapeHtml(anchor)}</span>`;
                html += `<div style="flex: 1; height: 6px; background: var(--border); border-radius: 3px; overflow: hidden;"><div style="width: ${pct}%; height: 100%; background: ${accentColor}; border-radius: 3px;"></div></div>`;
                html += `<span style="font-size: 10px; color: var(--text-secondary); min-width: 24px; text-align: right;">${count}</span>`;
                html += `</div>`;
            }
            html += `</div>`;
        }
        html += `</div>`;
        return html;
    }

    _lexRenderResults(entries, metaText) {
        const container = document.getElementById('lexicon-results');
        const meta = document.getElementById('lex-result-meta');
        if (!container) return;
        this._lexLastEntries = Array.isArray(entries) ? entries : [];
        this._lexLastMeta = metaText || '';
        const symbolMode = _explorerMode === 'symbols';

        if (meta) {
            meta.style.display = 'block';
            meta.innerHTML = `<span style="color: var(--gpt-oss);">${entries.length}</span> results — ${metaText}`;
        }

        if (entries.length === 0) {
            container.innerHTML = '<div style="grid-column:1/-1; text-align: center; padding: 30px; color: var(--text-secondary);">No entries found.</div>';
            return;
        }

        // Find max frequency for bar scaling
        const maxFreq = Math.max(1, ...entries.map(e => e.frequency || 0));

        container.innerHTML = entries.map(entry => {
            const freq = entry.frequency || 0;
            const freqPct = Math.max(5, (freq / maxFreq) * 100);

            // Status color mapping
            let statusColor, statusBg, statusGlow;
            switch (entry.status) {
                case 'ASSIGNED':
                    statusColor = 'var(--success)'; statusBg = 'rgba(0,255,136,0.12)'; statusGlow = 'rgba(0,255,136,0.3)'; break;
                case 'CUSTOM':
                    statusColor = 'var(--gpt-oss)'; statusBg = 'rgba(0,212,255,0.12)'; statusGlow = 'rgba(0,212,255,0.3)'; break;
                default:
                    statusColor = 'var(--warning)'; statusBg = 'rgba(255,215,0,0.12)'; statusGlow = 'rgba(255,215,0,0.3)'; break;
            }

            // Frequency tier color
            let freqColor = 'var(--text-secondary)';
            if (freq > 10000) freqColor = 'var(--success)';
            else if (freq > 1000) freqColor = 'var(--gpt-oss)';
            else if (freq > 100) freqColor = 'var(--warning)';
            else if (freq > 10) freqColor = 'var(--highlight)';

            const symbolDisplay = this._lexSymbolValue(entry);
            return symbolMode ? `
            <div style="background: var(--accent-bg); border: 1px solid var(--border); border-radius: 8px; padding: 14px; cursor: pointer; transition: all 0.2s; border-left: 4px solid ${statusColor};"
                 onmouseenter="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 16px ${statusGlow}';"
                 onmouseleave="this.style.transform=''; this.style.boxShadow='';"
                 onclick="app.lexShowDetail('${this.escapeHtml(entry.word)}')">
                <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:10px; margin-bottom:10px;">
                    <div style="min-width:0;">
                        <div style="font-size:10px; text-transform:uppercase; color:var(--text-secondary); margin-bottom:4px;">${this.escapeHtml(this._lexSymbolKind.replace('_', ' '))}</div>
                        <div style="font-size:${this._lexSymbolKind === 'binary' ? '16px' : '22px'}; font-weight:700; color:var(--gpt-oss); font-family:${this._lexSymbolKind === 'font_symbol' ? 'inherit' : 'Consolas, monospace'}; line-height:1.15; word-break:break-word;">${this.escapeHtml(symbolDisplay)}</div>
                        <div style="font-size:11px; color:var(--text-secondary); margin-top:6px;">${this.escapeHtml(entry.word)}</div>
                    </div>
                    <span style="font-size: 10px; padding: 2px 8px; border-radius: 10px; background: ${statusBg}; color: ${statusColor}; font-weight: 600;">${entry.status}</span>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <div style="flex: 1; height: 6px; background: var(--border); border-radius: 3px; overflow: hidden;">
                        <div style="width: ${freqPct}%; height: 100%; background: linear-gradient(90deg, ${statusColor}, ${freqColor}); border-radius: 3px; transition: width 0.3s;"></div>
                    </div>
                    <span style="font-size: 12px; font-weight: 700; color: ${freqColor}; min-width: 50px; text-align: right;">${freq.toLocaleString()}</span>
                </div>
            </div>` : `
            <div style="background: var(--accent-bg); border: 1px solid var(--border); border-radius: 8px; padding: 14px; cursor: pointer; transition: all 0.2s; border-left: 4px solid ${statusColor};"
                 onmouseenter="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 16px ${statusGlow}';"
                 onmouseleave="this.style.transform=''; this.style.boxShadow='';"
                 onclick="app.lexShowDetail('${this.escapeHtml(entry.word)}')">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                    <span style="font-size: 16px; font-weight: 700; color: var(--text-primary);">${this.escapeHtml(entry.word)}</span>
                    <span style="font-size: 10px; padding: 2px 8px; border-radius: 10px; background: ${statusBg}; color: ${statusColor}; font-weight: 600;">${entry.status}</span>
                </div>
                <div style="font-family: Consolas, monospace; font-size: 11px; color: var(--gpt-oss); margin-bottom: 8px; opacity: 0.7;">\u23e3 ${this.escapeHtml(entry.symbol || 'N/A')}</div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <div style="flex: 1; height: 6px; background: var(--border); border-radius: 3px; overflow: hidden;">
                        <div style="width: ${freqPct}%; height: 100%; background: linear-gradient(90deg, ${statusColor}, ${freqColor}); border-radius: 3px; transition: width 0.3s;"></div>
                    </div>
                    <span style="font-size: 12px; font-weight: 700; color: ${freqColor}; min-width: 50px; text-align: right;">${freq.toLocaleString()}</span>
                </div>
            </div>`;
        }).join('');
    }

    _lexShowEmpty() {
        const container = document.getElementById('lexicon-results');
        const meta = document.getElementById('lex-result-meta');
        if (meta) meta.style.display = 'none';
        if (container) {
            container.innerHTML = `
                <div style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--text-secondary);">
                    <div style="font-size: 48px; margin-bottom: 12px;">${_explorerMode === 'symbols' ? '\ud83d\udd23' : '\ud83d\udcda'}</div>
                    <p style="font-size: 14px;">${_explorerMode === 'symbols'
                        ? 'Browse lexicon entries through their symbol forms, then open any entry to inspect the chosen symbol view.'
                        : 'Search, browse by letter, or hit <strong style="color: var(--highlight);">\ud83d\udd25 Top Words</strong> to explore your lexicon.'}</p>
                </div>`;
        }
    }

    // ── Distribution Chart ──────────────────────────────────

    _lexRenderDistributionChart(letters) {
        const chart = document.getElementById('lex-distribution-chart');
        const label = document.getElementById('lex-chart-label');
        if (!chart) return;
        const sorted = Object.entries(letters).sort((a, b) => a[0].localeCompare(b[0]));
        if (sorted.length === 0) {
            chart.innerHTML = '<span style="color: var(--text-secondary); font-size: 12px;">No distribution data</span>';
            return;
        }
        const maxCount = Math.max(1, ...sorted.map(([, v]) => v));
        const totalWords = sorted.reduce((s, [, v]) => s + v, 0);
        if (label) label.textContent = `${totalWords.toLocaleString()} words across ${sorted.length} letters`;

        const barColors = [
            '#e94560', '#ff6bd6', '#b388ff', '#00d4ff', '#00ff88',
            '#ffd700', '#ff9f43', '#9b59b6', '#0077b6', '#c23152',
        ];
        chart.innerHTML = sorted.map(([letter, count], i) => {
            const pct = Math.max(4, (count / maxCount) * 100);
            const color = barColors[i % barColors.length];
            return `<div style="flex:1; display:flex; flex-direction:column; align-items:center; gap:2px; cursor:pointer;" title="${letter}: ${count.toLocaleString()} words" onclick="app.lexBrowseLetter('${letter}')">
                <span style="font-size:9px; color:var(--text-secondary);">${count >= 1000 ? Math.round(count/1000)+'k' : count}</span>
                <div style="width:100%; height:${pct}%; min-height:3px; background:${color}; border-radius:3px 3px 0 0; transition:height 0.3s;"></div>
                <span style="font-size:10px; font-weight:700; color:${color};">${letter}</span>
            </div>`;
        }).join('');
    }

    // ── Pack Filtering ──────────────────────────────────────

    lexSetPack(pack) {
        this._lexActivePack = pack || 'all';
        // Toggle active button styling
        document.querySelectorAll('.lex-pack-btn').forEach(btn => {
            const btnPack = btn.getAttribute('data-pack');
            if (btnPack === this._lexActivePack) {
                btn.style.background = 'linear-gradient(135deg, #00d4ff, #0099cc)';
                btn.style.color = '#000';
                btn.style.border = 'none';
                btn.classList.add('active');
            } else {
                btn.style.background = 'var(--accent-bg)';
                btn.style.border = '1px solid var(--border)';
                btn.classList.remove('active');
                // Restore per-pack color
                if (btnPack === 'canonical') { btn.style.color = '#00ff88'; btn.style.borderColor = '#00ff8833'; }
                else { btn.style.color = 'var(--text-secondary)'; }
            }
        });
        // Re-run last query with pack filter
        const searchInput = document.getElementById('lexicon-search');
        if (searchInput && searchInput.value.length >= 2) {
            this.searchLexicon(searchInput.value);
        } else {
            this._lexShowEmpty();
        }
        // Update context strip filter indicator
        const filterSpan = document.getElementById('lex-strip-filter');
        if (filterSpan) {
            if (pack === 'all') {
                filterSpan.style.display = 'none';
            } else {
                filterSpan.textContent = `◉ Filtered: ${pack.toUpperCase()}`;
                filterSpan.style.display = 'inline';
            }
        }
        this.addLog(`Lexicon pack filter: ${this._lexActivePack}`, 'info', { source: 'lex' });
    }

    // ── Recently Mapped ─────────────────────────────────────

    async lexBrowseRecent() {
        try {
            const resp = await fetch(`${this.serverUrl}/api/lexicon/recent?count=30`);
            const data = await resp.json();
            if (data.entries && data.entries.length > 0) {
                this._lexRenderResults(data.entries, `\ud83d\udd50 Recently mapped (${data.total} with timestamps)`);
            } else {
                const container = document.getElementById('lexicon-results');
                const meta = document.getElementById('lex-result-meta');
                if (meta) { meta.style.display = 'block'; meta.innerHTML = '<span style="color: var(--warning);">No entries with mapped_at timestamps yet.</span> Run a binding job to populate.'; }
                if (container) container.innerHTML = `
                    <div style="grid-column:1/-1; text-align:center; padding:30px; color:var(--text-secondary);">
                        <div style="font-size:36px; margin-bottom:8px;">\ud83d\udd50</div>
                        <p>No recently mapped entries found.</p>
                        <p style="font-size:12px; margin-top:6px;">Entries need a <code style="color:var(--gpt-oss);">mapped_at</code> timestamp to appear here.</p>
                    </div>`;
            }
        } catch (error) {
            this.addLog(`Lexicon recent failed: ${error.message}`, 'error', { source: 'lex', detail: error.message });
        }
    }

    // ── File Manager ────────────────────────────────────────

    async lexShowFiles() {
        const container = document.getElementById('lexicon-results');
        const meta = document.getElementById('lex-result-meta');
        if (!container) return;

        try {
            const resp = await fetch(`${this.serverUrl}/api/lexicon/files`);
            const data = await resp.json();
            const files = data.files || [];
            if (meta) { meta.style.display = 'block'; meta.innerHTML = `<span style="color:var(--gpt-oss);">${files.length}</span> partition files in <code style="font-size:11px;">${this.escapeHtml(data.lexicon_root || '')}</code>`; }

            const sizeLabel = (bytes) => bytes >= 1048576 ? (bytes / 1048576).toFixed(1) + ' MB' : (bytes / 1024).toFixed(0) + ' KB';
            const maxSize = Math.max(1, ...files.map(f => f.size_bytes || 0));

            container.innerHTML = files.map(f => {
                const pct = Math.max(8, ((f.size_bytes || 0) / maxSize) * 100);
                const modDate = f.modified ? new Date(f.modified * 1000).toLocaleDateString() : '—';
                return `
                <div style="background:var(--accent-bg); border:1px solid var(--border); border-radius:8px; padding:14px; cursor:pointer; transition:all 0.2s; border-left:4px solid var(--gpt-oss);"
                     onmouseenter="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 16px rgba(0,212,255,0.2)';"
                     onmouseleave="this.style.transform=''; this.style.boxShadow='';"
                     onclick="app.lexPreviewFile('${this.escapeHtml(f.filename)}')">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:8px;">
                        <span style="font-size:16px; font-weight:700; color:var(--text-primary);">${this.escapeHtml(f.letter)}</span>
                        <span style="font-size:10px; padding:2px 8px; border-radius:10px; background:rgba(0,212,255,0.12); color:var(--gpt-oss); font-weight:600;">${this.escapeHtml(f.filename)}</span>
                    </div>
                    <div style="font-size:12px; color:var(--text-secondary); margin-bottom:8px;">${sizeLabel(f.size_bytes)} &middot; Modified: ${modDate}</div>
                    <div style="height:6px; background:var(--border); border-radius:3px; overflow:hidden;">
                        <div style="width:${pct}%; height:100%; background:linear-gradient(90deg, var(--gpt-oss), var(--success)); border-radius:3px;"></div>
                    </div>
                </div>`;
            }).join('');
        } catch (error) {
            this.addLog(`Lexicon files failed: ${error.message}`, 'error', { source: 'lex', detail: error.message });
        }
    }

    _lexFileOffset = 0;
    _lexFileName = null;

    async lexPreviewFile(filename, offset = 0) {
        this._lexFileName = filename;
        this._lexFileOffset = offset;
        const container = document.getElementById('lexicon-results');
        const meta = document.getElementById('lex-result-meta');
        if (!container) return;

        try {
            const resp = await fetch(`${this.serverUrl}/api/lexicon/file/${encodeURIComponent(filename)}?offset=${offset}&limit=50`);
            const data = await resp.json();
            const entries = data.entries || [];
            const total = data.total || 0;
            const endIdx = Math.min(offset + entries.length, total);
            if (meta) {
                meta.style.display = 'block';
                meta.innerHTML = `\ud83d\udcc1 <strong>${this.escapeHtml(filename)}</strong> — entries ${offset + 1}–${endIdx} of ${total.toLocaleString()}`;
            }

            // Pagination controls
            let paginationHtml = '<div style="grid-column:1/-1; display:flex; gap:8px; justify-content:center; margin-top:8px;">';
            if (offset > 0) {
                paginationHtml += `<button class="btn btn-sm" style="background:var(--accent-bg); color:var(--gpt-oss); border:1px solid var(--gpt-oss); cursor:pointer; padding:4px 12px;" onclick="app.lexPreviewFile('${this.escapeHtml(filename)}', ${Math.max(0, offset - 50)})">◀ Prev 50</button>`;
            }
            paginationHtml += `<button class="btn btn-sm" style="background:var(--accent-bg); color:var(--warning); border:1px solid var(--border); cursor:pointer; padding:4px 12px;" onclick="app.lexShowFiles()">\ud83d\udcc2 Back to Files</button>`;
            if (endIdx < total) {
                paginationHtml += `<button class="btn btn-sm" style="background:var(--accent-bg); color:var(--gpt-oss); border:1px solid var(--gpt-oss); cursor:pointer; padding:4px 12px;" onclick="app.lexPreviewFile('${this.escapeHtml(filename)}', ${offset + 50})">Next 50 ▶</button>`;
            }
            paginationHtml += '</div>';

            container.innerHTML = entries.map(e => {
                const statusColor = e.status === 'ASSIGNED' ? 'var(--success)' : 'var(--warning)';
                const statusBg = e.status === 'ASSIGNED' ? 'rgba(0,255,136,0.12)' : 'rgba(255,215,0,0.12)';
                return `
                <div style="background:var(--accent-bg); border:1px solid var(--border); border-radius:8px; padding:12px; border-left:4px solid ${statusColor};">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:6px;">
                        <span style="font-size:14px; font-weight:700; color:var(--text-primary);">${e.word ? this.escapeHtml(e.word) : '<em style="color:var(--text-secondary);">empty slot</em>'}</span>
                        <span style="font-size:10px; padding:2px 8px; border-radius:10px; background:${statusBg}; color:${statusColor}; font-weight:600;">${e.status}</span>
                    </div>
                    <div style="font-family:Consolas,monospace; font-size:11px; color:var(--gpt-oss); opacity:0.7;">\u23e3 ${this.escapeHtml(e.hex || 'N/A')}</div>
                    ${e.mapped_at ? `<div style="font-size:10px; color:var(--text-secondary); margin-top:4px;">\ud83d\udd50 ${new Date(e.mapped_at).toLocaleString()}</div>` : ''}
                </div>`;
            }).join('') + paginationHtml;
        } catch (error) {
            this.addLog(`File preview failed: ${error.message}`, 'error', { source: 'lex', detail: error.message });
        }
    }

    // ── Unmatched Words Viewer ──────────────────────────────

    async lexShowUnmatched(letter = null) {
        const container = document.getElementById('lexicon-results');
        const meta = document.getElementById('lex-result-meta');
        if (!container) return;

        try {
            const params = new URLSearchParams({ limit: '100', sort: 'frequency' });
            if (letter) params.set('letter', letter);
            const resp = await fetch(`${this.serverUrl}/api/lexicon/unmatched?${params}`);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            const entries = data.entries || [];

            if (meta) {
                meta.style.display = 'block';
                meta.innerHTML = `<div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">` +
                    `<span>\u26a0\ufe0f <span style="color:#ff9f43;">${data.unmatched_total || 0}</span> unmatched words total` +
                    (letter ? ` — filtered to <strong>${letter.toUpperCase()}</strong>` : '') +
                    ` — showing top ${entries.length}</span>` +
                    (entries.length > 0 ? `<span style="display:flex; gap:6px;">` +
                        `<button onclick="app.lexBulkApproveAll()" style="padding:4px 12px; font-size:11px; background:#ffd700; color:#000; border:none; border-radius:4px; cursor:pointer; font-weight:700;">Approve All</button>` +
                        `<button onclick="app.lexBulkDenyAll()" style="padding:4px 12px; font-size:11px; background:#ff4444; color:#fff; border:none; border-radius:4px; cursor:pointer; font-weight:700;">Deny All</button>` +
                    `</span>` : '') +
                    `</div>`;
            }

            if (entries.length === 0) {
                container.innerHTML = `
                    <div style="grid-column:1/-1; text-align:center; padding:30px; color:var(--text-secondary);">
                        <div style="font-size:36px; margin-bottom:8px;">\u2705</div>
                        <p>No unmatched words${letter ? ' for ' + letter.toUpperCase() : ''}. Run a mapping job to discover unknown anchors.</p>
                    </div>`;
                return;
            }

            const maxFreq = Math.max(1, ...entries.map(e => e.frequency || 0));
            container.innerHTML = entries.map(e => {
                const freq = e.frequency || 0;
                const pct = Math.max(5, (freq / maxFreq) * 100);
                const freqColor = freq > 100 ? '#ff9f43' : freq > 10 ? '#ffd700' : 'var(--text-secondary)';
                const isCompound = e.word.includes('_');
                const badge = isCompound
                    ? `<span style="font-size:9px; font-weight:700; background:#555; color:#ccc; border-radius:3px; padding:1px 5px; margin-left:6px; letter-spacing:0.5px;">COMPOUND</span>`
                    : '';
                const acceptBtn = isCompound
                    ? `<button disabled style="padding:4px 10px; font-size:11px; background:#333; color:#666; border:1px solid #444; border-radius:4px; cursor:not-allowed; font-weight:600;" title="Compound anchors are not promoted to lexicon">✓ Accept</button>`
                    : `<button data-word="${this.escapeHtml(e.word)}" onclick="app.lexAcceptUnmatched(this.dataset.word, this)"
                         style="padding:4px 10px; font-size:11px; background:#00ff88; color:#000; border:none; border-radius:4px; cursor:pointer; font-weight:600; transition:background 0.1s, transform 0.08s;"
                         onmouseenter="if(!this.disabled){this.style.background='#00cc66';}"
                         onmouseleave="if(!this.disabled){this.style.background='#00ff88'; this.style.transform='';}"
                         onmousedown="if(!this.disabled){this.style.transform='scale(0.93)';}"
                         onmouseup="if(!this.disabled){this.style.transform='';}">✓ Accept</button>`;
                return `
                <div id="unmatch-card-${this.escapeHtml(e.word)}" style="background:var(--accent-bg); border:1px solid var(--border); border-radius:8px; padding:12px; border-left:4px solid ${isCompound ? '#888' : '#ff9f43'}; transition:all 0.2s;"
                     onmouseenter="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 12px rgba(255,159,67,0.2)';"
                     onmouseleave="this.style.transform=''; this.style.boxShadow='';">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                        <div style="display:flex; align-items:center;">
                            <span style="font-size:14px; font-weight:700; color:var(--text-primary);">${this.escapeHtml(e.word)}</span>${badge}
                        </div>
                        <span style="font-size:12px; font-weight:700; color:${freqColor};">${freq}x</span>
                    </div>
                    <div style="height:6px; background:var(--border); border-radius:3px; overflow:hidden; margin-bottom:10px;">
                        <div style="width:${pct}%; height:100%; background:linear-gradient(90deg, #ff9f43, #e94560); border-radius:3px;"></div>
                    </div>
                    <div style="display:flex; gap:6px; justify-content:flex-end;">
                        ${acceptBtn}
                        <button data-word="${this.escapeHtml(e.word)}" onclick="app.lexDenyUnmatched(this.dataset.word, this)"
                            style="padding:4px 10px; font-size:11px; background:#ff4444; color:#fff; border:none; border-radius:4px; cursor:pointer; font-weight:600; transition:background 0.1s, transform 0.08s;"
                            onmouseenter="if(!this.disabled){this.style.background='#cc2222';}"
                            onmouseleave="if(!this.disabled){this.style.background='#ff4444'; this.style.transform='';}"
                            onmousedown="if(!this.disabled){this.style.transform='scale(0.93)';}"
                            onmouseup="if(!this.disabled){this.style.transform='';}">✗ Deny</button>
                    </div>
                </div>`;
            }).join('');
        } catch (error) {
            this.addLog(`Unmatched query failed: ${error.message}`, 'error', { source: 'lex', detail: error.message });
        }
    }

    // ── Unmatched Review Actions ──────────────────────────────

    async lexAcceptUnmatched(word, btn) {
        const card = btn?.closest('[id^="unmatch-card-"]');
        const allBtns = card?.querySelectorAll('button');
        allBtns?.forEach(b => { b.disabled = true; });
        const origText = btn?.textContent;
        if (btn) { btn.textContent = '…'; btn.style.opacity = '0.6'; }
        try {
            const resp = await fetch(`${this.serverUrl}/api/lexicon/approve`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ word }),
            });
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                throw new Error(err.detail || `HTTP ${resp.status}`);
            }
            if (card) {
                card.style.transition = 'opacity 0.25s, transform 0.25s, border-left-color 0.1s, background 0.1s';
                card.style.borderLeftColor = '#ffd700';
                card.style.background = 'rgba(255,215,0,0.08)';
                await new Promise(r => setTimeout(r, 220));
                card.style.opacity = '0';
                card.style.transform = 'translateX(14px)';
                await new Promise(r => setTimeout(r, 260));
                card.remove();
            }
            this.addLog(`Approved "${word}" — moved to pending review`, 'success', { source: 'lex' });
        } catch (e) {
            allBtns?.forEach(b => { b.disabled = false; });
            if (btn) { btn.textContent = origText; btn.style.opacity = ''; }
            if (card) {
                card.style.transition = 'border-left-color 0.1s, background 0.1s';
                card.style.borderLeftColor = '#ff4444';
                card.style.background = 'rgba(255,68,68,0.1)';
                setTimeout(() => { if (card.parentNode) { card.style.borderLeftColor = ''; card.style.background = ''; } }, 1500);
            }
            this.addLog(`Approve failed for "${word}": ${e.message}`, 'error', { source: 'lex' });
        }
    }

    async lexDenyUnmatched(word, btn) {
        const card = btn?.closest('[id^="unmatch-card-"]');
        const allBtns = card?.querySelectorAll('button');
        allBtns?.forEach(b => { b.disabled = true; });
        const origText = btn?.textContent;
        if (btn) { btn.textContent = '…'; btn.style.opacity = '0.6'; }
        try {
            const resp = await fetch(`${this.serverUrl}/api/lexicon/ignore`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ word }),
            });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            if (card) {
                card.style.transition = 'opacity 0.25s, transform 0.25s, border-left-color 0.1s, background 0.1s';
                card.style.borderLeftColor = '#555';
                card.style.background = 'rgba(80,80,80,0.1)';
                await new Promise(r => setTimeout(r, 220));
                card.style.opacity = '0';
                card.style.transform = 'translateX(-14px)';
                await new Promise(r => setTimeout(r, 260));
                card.remove();
            }
            this.addLog(`Denied "${word}" — added to ignore list`, 'info', { source: 'lex' });
        } catch (e) {
            allBtns?.forEach(b => { b.disabled = false; });
            if (btn) { btn.textContent = origText; btn.style.opacity = ''; }
            if (card) {
                card.style.transition = 'border-left-color 0.1s, background 0.1s';
                card.style.borderLeftColor = '#ff4444';
                card.style.background = 'rgba(255,68,68,0.1)';
                setTimeout(() => { if (card.parentNode) { card.style.borderLeftColor = ''; card.style.background = ''; } }, 1500);
            }
            this.addLog(`Deny failed for "${word}": ${e.message}`, 'error', { source: 'lex' });
        }
    }

    // ── Bulk Unmatched Operations ──────────────────────────────

    async lexBulkApproveAll() {
        const cards = document.querySelectorAll('[id^="unmatch-card-"]');
        const words = [...cards].map(c => {
            const btn = c.querySelector('button[data-word]');
            return btn?.dataset?.word;
        }).filter(Boolean);
        if (!words.length) return;
        try {
            const resp = await fetch(`${this.serverUrl}/api/lexicon/unmatched/approve-all`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ words }),
            });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            // Animate all cards out
            cards.forEach(card => {
                card.style.transition = 'opacity 0.3s, transform 0.3s';
                card.style.borderLeftColor = '#ffd700';
                card.style.background = 'rgba(255,215,0,0.08)';
                card.style.opacity = '0';
                card.style.transform = 'translateX(14px)';
            });
            await new Promise(r => setTimeout(r, 350));
            cards.forEach(c => c.remove());
            this.addLog(`Approved all ${data.moved || words.length} words to pending review`, 'success', { source: 'lex' });
        } catch (e) {
            this.addLog(`Bulk approve failed: ${e.message}`, 'error', { source: 'lex' });
        }
    }

    async lexBulkDenyAll() {
        const cards = document.querySelectorAll('[id^="unmatch-card-"]');
        const words = [...cards].map(c => {
            const btn = c.querySelector('button[data-word]');
            return btn?.dataset?.word;
        }).filter(Boolean);
        if (!words.length) return;
        try {
            const resp = await fetch(`${this.serverUrl}/api/lexicon/unmatched/deny-all`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ words }),
            });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            cards.forEach(card => {
                card.style.transition = 'opacity 0.3s, transform 0.3s';
                card.style.borderLeftColor = '#555';
                card.style.background = 'rgba(80,80,80,0.1)';
                card.style.opacity = '0';
                card.style.transform = 'translateX(-14px)';
            });
            await new Promise(r => setTimeout(r, 350));
            cards.forEach(c => c.remove());
            this.addLog(`Denied all ${data.ignored || words.length} words`, 'info', { source: 'lex' });
        } catch (e) {
            this.addLog(`Bulk deny failed: ${e.message}`, 'error', { source: 'lex' });
        }
    }

    // ── Pending Review Queue ─────────────────────────────────────

    async lexShowPending() {
        const container = document.getElementById('lexicon-results');
        const meta = document.getElementById('lex-result-meta');
        if (!container) return;

        try {
            const resp = await fetch(`${this.serverUrl}/api/lexicon/pending`);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            const words = data.words || [];

            if (meta) {
                meta.style.display = 'block';
                meta.innerHTML = `<div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">` +
                    `<span style="color:#ffd700;">${data.total || 0}</span> words pending final assignment` +
                    (words.length > 0 ? `<span style="display:flex; gap:6px;">` +
                        `<button onclick="app.lexAssignAllPending()" style="padding:4px 12px; font-size:11px; background:#00ff88; color:#000; border:none; border-radius:4px; cursor:pointer; font-weight:700;">Assign All</button>` +
                    `</span>` : '') +
                    `</div>`;
            }

            if (words.length === 0) {
                container.innerHTML = `
                    <div style="grid-column:1/-1; text-align:center; padding:30px; color:var(--text-secondary);">
                        <p>No words pending review. Approve words from the Unmatched tab first.</p>
                    </div>`;
                return;
            }

            container.innerHTML = words.map(e => {
                const w = e.display || e.word;
                const addedAt = e.added_at ? new Date(e.added_at).toLocaleDateString() : '';
                return `
                <div id="pending-card-${this.escapeHtml(e.word)}" style="background:var(--accent-bg); border:1px solid var(--border); border-radius:8px; padding:12px; border-left:4px solid #ffd700; transition:all 0.2s;"
                     onmouseenter="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 12px rgba(255,215,0,0.15)';"
                     onmouseleave="this.style.transform=''; this.style.boxShadow='';">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                        <span style="font-size:14px; font-weight:700; color:var(--text-primary);">${this.escapeHtml(w)}</span>
                        <span style="font-size:10px; color:var(--text-secondary);">${addedAt}</span>
                    </div>
                    <div id="pending-proof-${this.escapeHtml(e.word)}" style="display:none; margin-bottom:8px; padding:6px 8px; background:rgba(0,255,136,0.06); border:1px solid rgba(0,255,136,0.2); border-radius:4px; font-family:monospace; font-size:11px; color:#00ff88;"></div>
                    <div style="display:flex; gap:6px; justify-content:flex-end;">
                        <button data-word="${this.escapeHtml(e.word)}" onclick="app.lexAssignPending(this.dataset.word, this)"
                            style="padding:4px 10px; font-size:11px; background:#00ff88; color:#000; border:none; border-radius:4px; cursor:pointer; font-weight:600; transition:background 0.1s, transform 0.08s;"
                            onmouseenter="if(!this.disabled){this.style.background='#00cc66';}"
                            onmouseleave="if(!this.disabled){this.style.background='#00ff88';}"
                            onmousedown="if(!this.disabled){this.style.transform='scale(0.93)';}"
                            onmouseup="if(!this.disabled){this.style.transform='';}">Assign Slot</button>
                        <button data-word="${this.escapeHtml(e.word)}" onclick="app.lexRemovePending(this.dataset.word, this)"
                            style="padding:4px 10px; font-size:11px; background:#555; color:#ccc; border:none; border-radius:4px; cursor:pointer; font-weight:600; transition:background 0.1s;"
                            onmouseenter="if(!this.disabled){this.style.background='#666';}"
                            onmouseleave="if(!this.disabled){this.style.background='#555';}">Remove</button>
                    </div>
                </div>`;
            }).join('');
        } catch (error) {
            this.addLog(`Pending query failed: ${error.message}`, 'error', { source: 'lex' });
        }
    }

    async lexAssignPending(word, btn) {
        const card = btn?.closest('[id^="pending-card-"]');
        const allBtns = card?.querySelectorAll('button');
        allBtns?.forEach(b => { b.disabled = true; });
        if (btn) { btn.textContent = '…'; btn.style.opacity = '0.6'; }
        try {
            const resp = await fetch(`${this.serverUrl}/api/lexicon/pending/assign`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ word }),
            });
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                throw new Error(err.detail || `HTTP ${resp.status}`);
            }
            const data = await resp.json();
            // Show proof before removing
            const proofEl = card?.querySelector('[id^="pending-proof-"]');
            if (proofEl) {
                const hex = data.hex || data.symbol || '—';
                const sym = data.symbol || '—';
                proofEl.textContent = `ASSIGNED  hex: ${hex}  symbol: ${sym}  slot: canonical`;
                proofEl.style.display = 'block';
            }
            if (card) {
                card.style.borderLeftColor = '#00ff88';
                card.style.background = 'rgba(0,255,136,0.08)';
            }
            // Hold proof visible, then fade out
            await new Promise(r => setTimeout(r, 1200));
            if (card) {
                card.style.transition = 'opacity 0.3s, transform 0.3s';
                card.style.opacity = '0';
                card.style.transform = 'translateX(14px)';
                await new Promise(r => setTimeout(r, 320));
                card.remove();
            }
            this.addLog(`Assigned "${word}" to slot ${data.hex || ''}`, 'success', { source: 'lex' });
        } catch (e) {
            allBtns?.forEach(b => { b.disabled = false; });
            if (btn) { btn.textContent = 'Assign Slot'; btn.style.opacity = ''; }
            this.addLog(`Assign failed for "${word}": ${e.message}`, 'error', { source: 'lex' });
        }
    }

    async lexRemovePending(word, btn) {
        const card = btn?.closest('[id^="pending-card-"]');
        const allBtns = card?.querySelectorAll('button');
        allBtns?.forEach(b => { b.disabled = true; });
        try {
            const resp = await fetch(`${this.serverUrl}/api/lexicon/pending/${encodeURIComponent(word)}`, {
                method: 'DELETE',
            });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            if (card) {
                card.style.transition = 'opacity 0.25s, transform 0.25s';
                card.style.opacity = '0';
                card.style.transform = 'translateX(-14px)';
                await new Promise(r => setTimeout(r, 280));
                card.remove();
            }
            this.addLog(`Removed "${word}" from pending — back to unmatched`, 'info', { source: 'lex' });
        } catch (e) {
            allBtns?.forEach(b => { b.disabled = false; });
            this.addLog(`Remove failed for "${word}": ${e.message}`, 'error', { source: 'lex' });
        }
    }

    async lexAssignAllPending() {
        try {
            const resp = await fetch(`${this.serverUrl}/api/lexicon/pending/assign-all`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
            });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            // Show proof on each card then fade all
            const results = data.results || [];
            for (const r of results) {
                if (!r.ok) continue;
                const card = document.getElementById(`pending-card-${r.word}`);
                if (!card) continue;
                const proofEl = card.querySelector('[id^="pending-proof-"]');
                if (proofEl) {
                    proofEl.textContent = `ASSIGNED  hex: ${r.hex || '—'}  symbol: ${r.symbol || '—'}`;
                    proofEl.style.display = 'block';
                }
                card.style.borderLeftColor = '#00ff88';
                card.style.background = 'rgba(0,255,136,0.08)';
            }
            await new Promise(r => setTimeout(r, 1500));
            const cards = document.querySelectorAll('[id^="pending-card-"]');
            cards.forEach(card => {
                card.style.transition = 'opacity 0.3s, transform 0.3s';
                card.style.opacity = '0';
                card.style.transform = 'translateX(14px)';
            });
            await new Promise(r => setTimeout(r, 350));
            cards.forEach(c => c.remove());
            this.addLog(`Assigned ${data.assigned || 0} words to lexicon${data.failed ? `, ${data.failed} failed` : ''}`, 'success', { source: 'lex' });
            this.updateLexiconStats();
        } catch (e) {
            this.addLog(`Assign All failed: ${e.message}`, 'error', { source: 'lex' });
        }
    }

    async lexShowIgnored(letter = null) {
        const container = document.getElementById('lexicon-results');
        const meta = document.getElementById('lex-result-meta');
        if (!container) return;

        try {
            const params = new URLSearchParams();
            if (letter) params.set('letter', letter);
            const resp = await fetch(`${this.serverUrl}/api/lexicon/ignored?${params}`);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            const words = data.words || [];

            if (meta) {
                meta.style.display = 'block';
                meta.innerHTML = `🚫 <span style="color:#888;">${data.total || 0}</span> ignored words total` +
                    (letter ? ` — filtered to <strong>${letter.toUpperCase()}</strong>` : '') +
                    ` — showing ${words.length}`;
            }

            if (words.length === 0) {
                container.innerHTML = `
                    <div style="grid-column:1/-1; text-align:center; padding:30px; color:var(--text-secondary);">
                        <div style="font-size:36px; margin-bottom:8px;">✅</div>
                        <p>No ignored words${letter ? ' for ' + letter.toUpperCase() : ''}.</p>
                    </div>`;
                return;
            }

            container.innerHTML = words.map(w => `
                <div id="ignore-card-${this.escapeHtml(w)}" style="background:var(--accent-bg); border:1px solid var(--border); border-radius:8px; padding:10px 12px; border-left:4px solid #555; display:flex; align-items:center; justify-content:space-between;">
                    <span style="font-size:13px; font-weight:600; color:var(--text-secondary);">${this.escapeHtml(w)}</span>
                    <button data-word="${this.escapeHtml(w)}" onclick="app.lexUnignoreWord(this.dataset.word, this)" style="padding:3px 9px; font-size:11px; background:#333; color:#aaa; border:1px solid #555; border-radius:4px; cursor:pointer; font-weight:600;">↩ Restore</button>
                </div>`).join('');
        } catch (error) {
            this.addLog(`Ignored list query failed: ${error.message}`, 'error', { source: 'lex', detail: error.message });
        }
    }

    async lexUnignoreWord(word, btn) {
        if (btn) btn.disabled = true;
        try {
            const resp = await fetch(`${this.serverUrl}/api/lexicon/ignore/${encodeURIComponent(word)}`, { method: 'DELETE' });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const card = btn?.closest('[id^="ignore-card-"]');
            if (card) card.remove();
            this.addLog(`Restored "${word}" — removed from ignore list`, 'info', { source: 'lex' });
        } catch (e) {
            if (btn) btn.disabled = false;
            this.addLog(`Restore failed for "${word}": ${e.message}`, 'error', { source: 'lex' });
        }
    }

    // ── Canonical Management ──────────────────────────────────

    async lexClearCanonical() {
        // Confirmation handled by lexDangerGate modal
        const container = document.getElementById('lexicon-results');
        const meta = document.getElementById('lex-result-meta');
        if (container) container.innerHTML = '<div style="grid-column:1/-1; text-align:center; padding:40px; color:var(--text-secondary);"><div style="font-size:36px; margin-bottom:8px;">⏳</div><p>Clearing canonical lexicon...</p></div>';
        try {
            const resp = await fetch(`${this.serverUrl}/api/lexicon/canonical`, { method: 'DELETE' });
            let data;
            try { data = await resp.json(); } catch { data = { detail: `HTTP ${resp.status} ${resp.statusText}` }; }
            if (!resp.ok) throw new Error(data.detail || `HTTP ${resp.status}`);
            this.addLog(`Canonical cleared: ${data.purged} entries purged, ${data.slots_available} slots available`, 'success', { source: 'lex' });
            if (meta) {
                meta.style.display = 'block';
                meta.innerHTML = `🗑️ <span style="color:#ff4444;">${data.purged}</span> canonical entries purged — <span style="color:#00ff88;">${data.slots_reclaimed}</span> slots reclaimed to pool`;
            }
            if (container) container.innerHTML = '<div style="grid-column:1/-1; text-align:center; padding:40px; color:var(--text-secondary);"><div style="font-size:36px; margin-bottom:8px;">✅</div><p>Canonical lexicon cleared. Import a word list to rebind.</p></div>';
            this.updateLexiconStats();
            this.connectToServer();  // refresh stats
        } catch (err) {
            this.addLog(`Clear canonical failed: ${err.message}`, 'error', { source: 'lex' });
            if (container) container.innerHTML = `<div style="grid-column:1/-1; text-align:center; padding:40px; color:var(--danger);"><div style="font-size:36px; margin-bottom:8px;">❌</div><p>${err.message}</p></div>`;
        }
    }

    async lexReturnToPool() {
        // Confirmation handled by lexDangerGate modal
        const container = document.getElementById('lexicon-results');
        const meta = document.getElementById('lex-result-meta');
        if (container) container.innerHTML = '<div style="grid-column:1/-1; text-align:center; padding:40px; color:var(--text-secondary);"><div style="font-size:36px; margin-bottom:8px;">⏳</div><p>Moving canonical slots to pool…</p></div>';
        try {
            const resp = await fetch(`${this.serverUrl}/api/lexicon/return-to-pool`, { method: 'POST' });
            let data;
            try { data = await resp.json(); } catch { data = { detail: `HTTP ${resp.status} ${resp.statusText}` }; }
            if (!resp.ok) throw new Error(data.detail || `HTTP ${resp.status}`);
            this.addLog(`Return to pool: ${data.moved?.toLocaleString()} slots moved, pool now ${data.pool_available?.toLocaleString()}`, 'success', { source: 'lex' });
            if (meta) {
                meta.style.display = 'block';
                meta.innerHTML = `🔄 <span style="color:#ff8800;">${(data.moved || 0).toLocaleString()}</span> slots returned to pool — pool now <span style="color:#00ff88;">${(data.pool_available || 0).toLocaleString()}</span>`;
            }
            if (container) container.innerHTML = '<div style="grid-column:1/-1; text-align:center; padding:40px; color:var(--text-secondary);"><div style="font-size:36px; margin-bottom:8px;">✅</div><p>All canonical slots returned to pool.</p></div>';
            this.updateLexiconStats();
            this.connectToServer();
        } catch (err) {
            this.addLog(`Return to pool failed: ${err.message}`, 'error', { source: 'lex' });
            if (container) container.innerHTML = `<div style="grid-column:1/-1; text-align:center; padding:40px; color:var(--danger);"><div style="font-size:36px; margin-bottom:8px;">❌</div><p>${this.escapeHtml(err.message)}</p></div>`;
        }
    }

    async lexImportWordList() {
        // Confirmation handled by lexDangerGate modal — now ask for path
        const wordsDir = prompt(
            'Enter the full path to the directory containing verified_A.json … verified_Z.json:\n\n' +
            '(e.g. C:\\Users\\mydyi\\Desktop\\verified_words)'
        );
        if (!wordsDir || !wordsDir.trim()) {
            this.addLog('Import cancelled — no path provided', 'info', { source: 'lex' });
            return;
        }
        const container = document.getElementById('lexicon-results');
        const meta = document.getElementById('lex-result-meta');
        const cleanDir = wordsDir.trim();
        this.addLog(`Import: sending path "${cleanDir}"`, 'info', { source: 'lex' });
        if (container) container.innerHTML = '<div style="grid-column:1/-1; text-align:center; padding:40px; color:var(--text-secondary);"><div style="font-size:36px; margin-bottom:8px;">⏳</div><p>Importing word lists… this may take a moment.</p></div>';
        try {
            const payload = JSON.stringify({ words_dir: cleanDir });
            console.log('[lexImport] POST /api/lexicon/import', payload);
            const resp = await fetch(`${this.serverUrl}/api/lexicon/import`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: payload,
            });
            let data;
            try { data = await resp.json(); } catch { data = { detail: `HTTP ${resp.status} ${resp.statusText}` }; }
            if (!resp.ok) throw new Error(data.detail || JSON.stringify(data) || `HTTP ${resp.status}`);
            this.addLog(`Import complete: ${data.imported} bound, ${data.skipped} skipped, ${data.no_slots} overflow`, 'success', { source: 'lex' });
            if (meta) {
                meta.style.display = 'block';
                meta.innerHTML = `📥 <span style="color:#00ff88;">${data.imported.toLocaleString()}</span> words imported` +
                    (data.skipped ? ` — <span style="color:#ffd700;">${data.skipped}</span> skipped (already bound)` : '') +
                    (data.no_slots ? ` — <span style="color:#ff4444;">${data.no_slots}</span> overflow (no slots)` : '') +
                    ` — <span style="color:#00d4ff;">${data.slots_available.toLocaleString()}</span> slots remaining`;
            }
            // Show per-letter breakdown
            if (container && data.letters) {
                const letterCards = data.letters.filter(l => l.bound > 0 || l.no_slots > 0).map(l => {
                    const color = l.no_slots > 0 ? '#ff9f43' : '#00ff88';
                    return `<div style="background:var(--accent-bg); border:1px solid var(--border); border-radius:8px; padding:10px; text-align:center; border-top:3px solid ${color};">
                        <div style="font-size:18px; font-weight:700; color:var(--text-primary);">${l.letter}</div>
                        <div style="font-size:13px; color:#00ff88; font-weight:600;">${(l.bound || 0).toLocaleString()}</div>
                        <div style="font-size:10px; color:var(--text-secondary);">bound</div>
                        ${l.no_slots ? `<div style="font-size:11px; color:#ff4444; margin-top:4px;">${l.no_slots} overflow</div>` : ''}
                    </div>`;
                }).join('');
                container.innerHTML = letterCards || '<div style="grid-column:1/-1; text-align:center; padding:30px; color:var(--text-secondary);">No words imported.</div>';
            }
            this.updateLexiconStats();
            this.connectToServer();  // refresh stats
        } catch (err) {
            this.addLog(`Import failed: ${err.message}`, 'error', { source: 'lex' });
            if (container) container.innerHTML = `<div style="grid-column:1/-1; text-align:center; padding:40px; color:var(--danger);"><div style="font-size:36px; margin-bottom:8px;">❌</div><p>${this.escapeHtml(err.message)}</p></div>`;
        }
    }

    // Settings
    saveSettings() {
        const serverUrlEl = document.getElementById('server-url');
        const serverUrl = serverUrlEl ? serverUrlEl.value : this.serverUrl;

        localStorage.setItem(this._bridgeStorageKey, serverUrl);
        localStorage.removeItem('serverUrl');
        localStorage.setItem('gptEndpoint', this.gptEndpoint);
        localStorage.setItem('gptModel', this.gptModel);

        this.serverUrl = serverUrl;

        this.addLog('Settings saved', 'success');
        alert('Settings saved successfully!');
    }

    loadSettings() {
        const serverUrl = localStorage.getItem(this._bridgeStorageKey) || localStorage.getItem('serverUrl');
        const gptEndpoint = localStorage.getItem('gptEndpoint');
        const gptModel = localStorage.getItem('gptModel');

        // Sync localStorage → instance vars
        if (serverUrl) {
            this.serverUrl = serverUrl;
            localStorage.setItem(this._bridgeStorageKey, serverUrl);
            localStorage.removeItem('serverUrl');
        }
        if (gptEndpoint) this.gptEndpoint = gptEndpoint;
        if (gptModel) this.gptModel = gptModel;

        const serverUrlEl = document.getElementById('server-url');
        if (serverUrlEl) serverUrlEl.value = this.serverUrl;

        // Restore tools toggle from localStorage
        const toolsToggle = document.getElementById('tools-toggle');
        if (toolsToggle) {
            toolsToggle.checked = localStorage.getItem('anchorworks_tools_enabled') === 'true';
        }
    }

    // Logging
    addLog(message, level = 'info', meta = {}) {
        const timestamp = this.formatUtcTime();
        const log = `[${timestamp}] ${message}`;
        
        console.log(log);

        // Build source tag from meta
        const source = meta.source || this._inferSource(message);
        const duration = meta.duration ? ` (${meta.duration})` : '';
        const detail = meta.detail || '';

        // Activity log
        const activityLog = document.getElementById('activity-log');
        if (activityLog) {
            const entry = document.createElement('div');
            entry.className = `log-entry ${level}`;
            entry.style.cssText = 'display:flex; justify-content:space-between; align-items:flex-start; gap:8px; padding:4px 0;';

            const left = document.createElement('span');
            left.style.cssText = 'flex:1; min-width:0;';
            // Main line: level badge + message
            let badge = `<span style="display:inline-block;padding:1px 5px;border-radius:3px;font-size:10px;font-weight:600;margin-right:6px;`;
            if (level === 'error') badge += `background:rgba(255,68,68,0.2);color:var(--danger);">`;
            else if (level === 'warning') badge += `background:rgba(255,215,0,0.2);color:var(--warning);">`;
            else if (level === 'success') badge += `background:rgba(0,255,136,0.15);color:var(--success);">`;
            else badge += `background:rgba(0,212,255,0.12);color:var(--gpt-oss);">`;
            badge += level.toUpperCase() + '</span>';

            left.innerHTML = badge + this.escapeHtml(message) + this.escapeHtml(duration);

            // Error detail line
            if (level === 'error' && detail) {
                left.innerHTML += `<div style="font-size:10px;color:var(--danger);opacity:0.8;margin-top:2px;padding-left:12px;white-space:pre-wrap;">${this.escapeHtml(detail)}</div>`;
            }

            const right = document.createElement('span');
            right.style.cssText = 'white-space:nowrap; font-size:10px; color:var(--text-secondary); flex-shrink:0;';
            right.textContent = `${source}  ${timestamp}`;

            entry.appendChild(left);
            entry.appendChild(right);
            activityLog.appendChild(entry);
            requestAnimationFrame(() => { activityLog.scrollTop = activityLog.scrollHeight; });

            // Cap at 200 entries
            while (activityLog.children.length > 200) {
                activityLog.removeChild(activityLog.firstChild);
            }
        }

        // Server logs (monitoring panel)
        const serverLogs = document.getElementById('server-logs');
        if (serverLogs) {
            const entry = document.createElement('div');
            entry.className = `log-entry ${level}`;
            entry.textContent = `[${timestamp}] [${source}] ${message}${duration}`;
            if (level === 'error' && detail) {
                entry.textContent += `\n    → ${detail}`;
            }
            serverLogs.appendChild(entry);
            requestAnimationFrame(() => { serverLogs.scrollTop = serverLogs.scrollHeight; });
        }

        // Footer status
        document.getElementById('footer-status').textContent = message;
    }

    _inferSource(msg) {
        const m = msg.toLowerCase();
        if (m.includes('websocket')) return 'ws';
        if (m.includes('gpt') || m.includes('model') || m.includes('connected.')) return 'llm';
        if (m.includes('mapping') || m.includes('map ')) return 'map';
        if (m.includes('lexicon') || m.includes('search')) return 'lex';
        if (m.includes('commit') || m.includes('data lake')) return 'lake';
        if (m.includes('server') || m.includes('connect')) return 'srv';
        if (m.includes('session') || m.includes('summary')) return 'sess';
        if (m.includes('loaded') || m.includes('messages')) return 'hist';
        if (m.includes('citation') || m.includes('flag')) return 'cite';
        if (m.includes('setting') || m.includes('save')) return 'cfg';
        return 'sys';
    }

    // ── System Monitor ─────────────────────────────────────

    startSystemMonitor() {
        // Poll /api/system every 5s
        if (this._sysmonInterval) clearInterval(this._sysmonInterval);
        this._sysmonInterval = setInterval(() => {
            if (document.hidden) return;
            this.fetchSystemMetrics();
        }, 5000);
        // Initial fetch
        this.fetchSystemMetrics();
    }

    async fetchSystemMetrics() {
        try {
            const resp = await fetch(`${this.serverUrl}/api/system`);
            if (!resp.ok) return;
            const m = await resp.json();
            if (!m.available) return;

            // CPU
            const cpuEl = document.getElementById('sysmon-cpu');
            const cpuMeta = document.getElementById('sysmon-cpu-meta');
            if (cpuEl) {
                cpuEl.textContent = `${m.cpu.percent}%`;
                cpuEl.style.color = m.cpu.percent > 80 ? 'var(--danger)' : m.cpu.percent > 50 ? 'var(--warning)' : 'var(--gpt-oss)';
            }
            if (cpuMeta) {
                const freq = m.cpu.freq_mhz ? `${(m.cpu.freq_mhz / 1000).toFixed(1)} GHz` : '';
                cpuMeta.textContent = `${m.cpu.cores_physical}c/${m.cpu.cores_logical}t ${freq}`;
            }

            // RAM
            const ramEl = document.getElementById('sysmon-ram');
            const ramMeta = document.getElementById('sysmon-ram-meta');
            if (ramEl) {
                ramEl.textContent = `${m.memory.percent}%`;
                ramEl.style.color = m.memory.percent > 85 ? 'var(--danger)' : m.memory.percent > 65 ? 'var(--warning)' : 'var(--success)';
            }
            if (ramMeta) {
                ramMeta.textContent = `${m.memory.used} / ${m.memory.total}`;
            }

            // GPU
            const gpuEl = document.getElementById('sysmon-gpu');
            const gpuMeta = document.getElementById('sysmon-gpu-meta');
            if (m.gpu && m.gpu.length > 0) {
                const g = m.gpu[0];
                if (gpuEl) {
                    gpuEl.textContent = `${g.load_percent}%`;
                    gpuEl.style.color = g.load_percent > 80 ? 'var(--danger)' : 'var(--warning)';
                }
                if (gpuMeta) {
                    gpuMeta.textContent = `${g.name} · ${g.memory_used_mb}/${g.memory_total_mb} MB${g.temperature ? ' · ' + g.temperature + '°C' : ''}`;
                }
            } else {
                if (gpuEl) { gpuEl.textContent = 'N/A'; gpuEl.style.color = 'var(--text-secondary)'; }
                if (gpuMeta) gpuMeta.textContent = 'No GPU detected';
            }

            // Disk — pick C: or first
            const diskEl = document.getElementById('sysmon-disk');
            const diskMeta = document.getElementById('sysmon-disk-meta');
            if (m.disks && m.disks.length > 0) {
                const cDrive = m.disks.find(d => d.mount && d.mount.toUpperCase().startsWith('C')) || m.disks[0];
                if (diskEl) {
                    diskEl.textContent = `${cDrive.percent}%`;
                    diskEl.style.color = cDrive.percent > 90 ? 'var(--danger)' : cDrive.percent > 75 ? 'var(--warning)' : 'var(--highlight)';
                }
                const label = cDrive.mount.replace('\\', '');
                if (diskMeta) {
                    diskMeta.textContent = `${label} ${cDrive.used} / ${cDrive.total}`;
                    // Show all drives as tooltip
                    diskMeta.title = m.disks.map(d => `${d.mount.replace('\\','')} ${d.percent}% (${d.free} free)`).join('\n');
                }
            }

            // Network
            const netEl = document.getElementById('sysmon-net');
            const netMeta = document.getElementById('sysmon-net-meta');
            if (netEl) {
                netEl.textContent = m.network.recv;
                netEl.style.color = '#9b59b6';
            }
            if (netMeta) netMeta.textContent = `↑ ${m.network.sent}  ↓ ${m.network.recv}`;

            // Uptime
            const upEl = document.getElementById('sysmon-uptime');
            const procMeta = document.getElementById('sysmon-proc-meta');
            if (upEl) {
                upEl.textContent = m.uptime.display;
                upEl.style.color = 'var(--text-primary)';
            }
            if (procMeta) {
                procMeta.textContent = `${m.processes.total} procs · AnchorWorks: ${m.processes.anchorworks_mem}`;
            }

        } catch (e) {
            // Silent fail — don't spam logs for missed polls
        }
    }

    async viewSystemLogs() {
        try {
            const resp = await fetch(`${this.serverUrl}/api/logs/recent?lines=150`);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            const lines = data.lines || [];

            if (lines.length === 0) {
                alert('No log entries yet. Logs appear after server restart.');
                return;
            }

            // Show in modal
            document.getElementById('cite-modal-title').textContent = `System Logs (${lines.length} lines)`;
            document.getElementById('cite-modal-content').textContent = lines.join('\n');
            document.getElementById('cite-modal').classList.add('active');
        } catch (e) {
            this.addLog(`Failed to fetch system logs: ${e.message}`, 'error', { source: 'sys', detail: e.stack || '' });
        }
    }

    // Event Listeners
    setupEventListeners() {
        // Rail icon navigation
        document.querySelectorAll('.rail-icon').forEach(icon => {
            icon.addEventListener('click', () => switchSpace(icon.dataset.space));
        });

        // Initialize default space (renders tabs + activates default panel)
        switchSpace('workspace');

        // File upload drag and drop
        const fileUpload = document.getElementById('file-upload');
        if (fileUpload) {
            fileUpload.addEventListener('dragover', (e) => {
                e.preventDefault();
                fileUpload.classList.add('dragover');
            });

            fileUpload.addEventListener('dragleave', () => {
                fileUpload.classList.remove('dragover');
            });

            fileUpload.addEventListener('drop', (e) => {
                e.preventDefault();
                fileUpload.classList.remove('dragover');
                const files = e.dataTransfer.files;
                if (files.length > 0) {
                    const mappingInput = document.getElementById('file-input');
                    try {
                        if (mappingInput) mappingInput.files = files;
                    } catch (_) {
                        // Some browser contexts disallow assigning FileList directly.
                    }
                    handleFileSelect({
                        target: mappingInput || { id: 'file-input', files }
                    });
                }
            });
        }

        // Chat window drag-and-drop upload
        const chatCol = document.querySelector('.gpt-chat-col');
        if (chatCol) {
            chatCol.addEventListener('dragover', (e) => {
                e.preventDefault();
                chatCol.classList.add('chat-dragover');
            });
            chatCol.addEventListener('dragleave', (e) => {
                // Only remove if leaving the container (not entering a child)
                if (!chatCol.contains(e.relatedTarget)) {
                    chatCol.classList.remove('chat-dragover');
                }
            });
            chatCol.addEventListener('drop', (e) => {
                e.preventDefault();
                chatCol.classList.remove('chat-dragover');
                const files = e.dataTransfer.files;
                if (files.length > 0) {
                    chatHandleFileUpload({ target: { files } });
                }
            });
        }

        // Enter key for GPT chat
        const gptPrompt = document.getElementById('gpt-prompt');
        if (gptPrompt) {
            gptPrompt.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendGptMessage();
                }
            });
        }

        // Model hot-swap now handled by Inference Control / Chain Builder
    }

    // ── Citation rendering ──────────────────────────────────

    buildCitationIndex(citeReport) {
        const idx = new Map();
        if (!citeReport || !citeReport.citations) return idx;
        for (const c of citeReport.citations) {
            const key = (c.canonical || '').trim();
            if (key) idx.set(key, c);
        }
        return idx;
    }

    renderCiteBadges(escapedHtml, citeReport) {
        // Match [CITE YYYY-MM-DD:L<n>] or [CITE YYYY-MM-DD#<n>] in escaped text
        const re = /\[CITE\s+([0-9]{4}-[0-9]{2}-[0-9]{2})[:#]L?(\d+)\b[^\]]*\]/g;
        const idx = this.buildCitationIndex(citeReport);

        return escapedHtml.replace(re, (full, day, num) => {
            const canonical = `${day}:L${num}`;
            const c = idx.get(canonical);

            let cls = 'cite-badge';
            if (c) {
                cls += c.valid ? ' cite-valid' : ' cite-invalid';
                if (c.id_mismatch) cls += ' cite-warn';
            } else {
                cls += ' cite-warn';
            }

            return `<span class="${cls}" data-cite="${this.escapeHtml(canonical)}">${this.escapeHtml(canonical)}</span>`;
        });
    }

    attachBadgeHandlers(containerEl) {
        containerEl.querySelectorAll('.cite-badge').forEach(badge => {
            badge.addEventListener('click', (e) => {
                e.stopPropagation();
                const canonical = badge.getAttribute('data-cite');
                this.selectCitation(canonical);
            });
        });
        if (window.genesisCite) window.genesisCite.attachHandlers(containerEl);
    }

    // ── Citations pane ──────────────────────────────────────

    populateCitationPane(citeReport, retrievalCtx) {
        const paneEl = document.getElementById('cite-pane');
        const listEl = document.getElementById('cite-list');
        const summaryEl = document.getElementById('cite-summary');
        const headerCount = document.getElementById('cite-header-count');
        const detailEl = document.getElementById('cite-detail');
        const actionsEl = document.getElementById('cite-actions');
        if (!paneEl || !listEl || !summaryEl || !headerCount || !detailEl || !actionsEl) return;

        // Reset
        detailEl.style.display = 'none';
        actionsEl.style.display = 'none';

        const hasCitations = citeReport && citeReport.citations && citeReport.citations.length > 0;
        const hasRetrieval = retrievalCtx && retrievalCtx.hits && retrievalCtx.hits.length > 0;

        // ── Stream 1: Cited-by-model ──────────────────────
        if (hasCitations) {
            if (paneEl) paneEl.style.display = '';
            const cites = citeReport.citations;
            headerCount.textContent = `${cites.length}`;

            const v = citeReport.valid_count || 0;
            const inv = citeReport.invalid_count || 0;
            const parts = [];
            parts.push('Source: Cited-by-model');
            if (v > 0) parts.push(`\u2713 ${v} valid`);
            if (inv > 0) parts.push(`\u2717 ${inv} invalid`);
            if (citeReport.id_mismatch_count > 0) parts.push(`\u26a0 ${citeReport.id_mismatch_count} mismatch`);
            summaryEl.textContent = parts.join('  \u2022  ');
            summaryEl.style.display = 'block';

            listEl.innerHTML = cites.map(c => {
                const dotCls = c.valid ? 'valid' : 'invalid';
                const sender = c.source_sender || (c.valid ? '' : 'unresolved');
                const branch = c.source_branch || '';
                const meta = [sender, branch].filter(Boolean).join(' \u2022 ');
                return `
                    <div class="cite-item" data-cite="${this.escapeHtml(c.canonical)}" onclick="app.selectCitation('${this.escapeHtml(c.canonical)}')">
                        <div class="cite-dot ${dotCls}"></div>
                        <div class="cite-item-body">
                            <div class="cite-item-canon">${this.escapeHtml(c.canonical)}</div>
                            <div class="cite-item-meta">${this.escapeHtml(meta)}</div>
                        </div>
                    </div>
                `;
            }).join('');
            return;
        }

        // ── Stream 2: Retrieved-context ───────────────────
        if (hasRetrieval) {
            if (paneEl) paneEl.style.display = '';
            const hits = retrievalCtx.hits;
            headerCount.textContent = `${hits.length}`;

            summaryEl.textContent = `Source: Retrieved-context  \u2022  ${hits.length} archive hit${hits.length !== 1 ? 's' : ''} provided to model`;
            summaryEl.style.display = 'block';

            // Build a synthetic cite index so selectCitation works
            this.lastCiteIndex = new Map();
            hits.forEach(h => {
                this.lastCiteIndex.set(h.canonical, {
                    canonical: h.canonical,
                    day: h.day,
                    line: h.line,
                    valid: true,
                    source_sender: h.sender,
                    source_branch: h.branch,
                    source_snippet: h.snippet,
                    score: h.score,
                    retrieval_hit: true,
                });
            });

            listEl.innerHTML = hits.map(h => {
                const score = h.score !== undefined ? ` (${h.score.toFixed(1)})` : '';
                const meta = [h.sender, h.branch].filter(Boolean).join(' \u2022 ');
                return `
                    <div class="cite-item" data-cite="${this.escapeHtml(h.canonical)}" onclick="app.selectCitation('${this.escapeHtml(h.canonical)}')">
                        <div class="cite-dot valid"></div>
                        <div class="cite-item-body">
                            <div class="cite-item-canon">${this.escapeHtml(h.canonical)}${score}</div>
                            <div class="cite-item-meta">${this.escapeHtml(meta)}</div>
                        </div>
                    </div>
                `;
            }).join('');
            return;
        }

        // ── Empty state ───────────────────────────────────
        if (paneEl) paneEl.style.display = 'none';
        headerCount.textContent = '';
        summaryEl.style.display = 'none';
        listEl.innerHTML = `
            <div class="cite-empty">
                <div style="margin-bottom: 8px;">No citations were emitted by the model.</div>
                <div style="margin-bottom: 8px; color: var(--text-secondary);">No retrieved-context hits for this query.</div>
                <div style="font-size: 11px; color: var(--text-secondary); font-style: italic;">
                    Tip: ask a question with date/line anchors, e.g.<br>
                    &ldquo;Resolve 2026-02-08:L1, :L3, :L5&rdquo;
                </div>
            </div>
        `;
    }

    selectCitation(canonical) {
        this.selectedCite = canonical;
        const c = this.lastCiteIndex ? this.lastCiteIndex.get(canonical) : null;

        // Highlight in list
        document.querySelectorAll('.cite-item').forEach(el => {
            el.classList.toggle('selected', el.getAttribute('data-cite') === canonical);
        });

        // Highlight badge in chat (only exists for cited-by-model)
        document.querySelectorAll('.cite-badge').forEach(el => {
            el.classList.toggle('cite-selected', el.getAttribute('data-cite') === canonical);
        });

        const detailEl = document.getElementById('cite-detail');
        const actionsEl = document.getElementById('cite-actions');
        const snippetEl = document.getElementById('cite-detail-snippet');
        const gridEl = document.getElementById('cite-detail-grid');
        if (!detailEl || !actionsEl || !snippetEl || !gridEl) return;

        if (!c) {
            snippetEl.textContent = 'No resolved data for this citation.';
            gridEl.innerHTML = `<dt>Canonical</dt><dd>${this.escapeHtml(canonical)}</dd>`;
        } else if (c.retrieval_hit) {
            // Retrieved-context hit — show score + snippet
            snippetEl.textContent = c.source_snippet || '(no content)';
            const fields = [
                ['Day', c.day],
                ['Line', c.line],
                ['Source', 'Retrieved-context'],
                ['Score', c.score !== undefined ? c.score.toFixed(3) : null],
                ['Sender', c.source_sender],
                ['Branch', c.source_branch],
            ];
            gridEl.innerHTML = fields
                .filter(([, v]) => v !== undefined && v !== null)
                .map(([k, v]) => `<dt>${k}</dt><dd>${this.escapeHtml(String(v))}</dd>`)
                .join('');
        } else {
            // Cited-by-model — full citation detail
            snippetEl.textContent = c.source_snippet || c.source_content || '(no content)';
            const fields = [
                ['Day', c.day],
                ['Line', c.line],
                ['Source', 'Cited-by-model'],
                ['Valid', c.valid ? 'Yes' : 'No'],
                ['Sender', c.source_sender],
                ['Branch', c.source_branch],
                ['Hash', c.source_hash],
                ['Timestamp', c.source_timestamp],
            ];
            if (c.id_mismatch) fields.push(['ID Mismatch', `source_id=${c.source_id}`]);
            gridEl.innerHTML = fields
                .filter(([, v]) => v !== undefined && v !== null)
                .map(([k, v]) => `<dt>${k}</dt><dd>${this.escapeHtml(String(v))}</dd>`)
                .join('');
        }

        detailEl.style.display = 'block';
        actionsEl.style.display = 'flex';

        // Scroll detail into view
        detailEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    // ── Citation actions ─────────────────────────────────────

    async flagCitation() {
        if (!this.selectedCite) return;
        const c = this.lastCiteIndex ? this.lastCiteIndex.get(this.selectedCite) : null;

        const reason = prompt(
            'Reason for flagging this citation:\n' +
            '• wrong_support — doesn\'t support the claim\n' +
            '• wrong_scope — true but irrelevant\n' +
            '• conflict — contradicts another cite\n' +
            '• other',
            'wrong_support'
        );
        if (!reason) return;

        const endpoint = this.gptEndpoint;
        const flagUrl = endpoint.replace('/api/generate', '/api/citations/flag');

        try {
            const resp = await fetch(flagUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({
                    cite: this.selectedCite,
                    reason: reason,
                    citation_meta: c || null
                })
            });
            if (resp.ok) {
                this.addLog(`Flagged citation ${this.selectedCite}: ${reason}`, 'warning');
            } else {
                this.addLog('Flag failed: ' + resp.statusText, 'error');
            }
        } catch (err) {
            this.addLog('Flag failed: ' + err.message, 'error');
        }
    }

    copyCanonical() {
        if (!this.selectedCite) return;
        navigator.clipboard.writeText(this.selectedCite).then(() => {
            this.addLog(`Copied: ${this.selectedCite}`, 'info');
        }).catch(() => {
            // Fallback
            const ta = document.createElement('textarea');
            ta.value = this.selectedCite;
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
            this.addLog(`Copied: ${this.selectedCite}`, 'info');
        });
    }

    async viewFullMessage() {
        if (!this.selectedCite) return;
        const endpoint = this.gptEndpoint;
        const resolveUrl = endpoint.replace('/api/generate', '/api/citations/resolve');

        try {
            const resp = await fetch(`${resolveUrl}?cite=${encodeURIComponent(this.selectedCite)}`, { credentials: 'include' });
            if (!resp.ok) throw new Error(resp.statusText);
            const data = await resp.json();

            document.getElementById('cite-modal-title').textContent = this.selectedCite;
            document.getElementById('cite-modal-content').textContent = data.content || '(empty)';
            document.getElementById('cite-modal').classList.add('active');
        } catch (err) {
            this.addLog('Could not load full message: ' + err.message, 'error');
        }
    }

    async jumpToSourceDay() {
        if (!this.selectedCite) return;
        const endpoint = this.gptEndpoint;
        const resolveUrl = endpoint.replace('/api/generate', '/api/citations/resolve');

        // Extract day from canonical
        const day = this.selectedCite.split(':')[0];
        if (!day) return;

        try {
            const resp = await fetch(`${resolveUrl}?day=${encodeURIComponent(day)}`, { credentials: 'include' });
            if (!resp.ok) throw new Error(resp.statusText);
            const data = await resp.json();

            const messages = data.messages || [];
            const citeLine = parseInt(this.selectedCite.split(':L')[1]) || 0;

            let content = messages.map((m, i) => {
                const lineNum = i + 1;
                const marker = lineNum === citeLine ? '  ◀── CITED' : '';
                return `[L${lineNum}] ${m.sender}: ${m.content}${marker}`;
            }).join('\n\n');

            document.getElementById('cite-modal-title').textContent = `Source Day: ${day} (${messages.length} messages)`;
            document.getElementById('cite-modal-content').textContent = content || '(no messages found)';
            document.getElementById('cite-modal').classList.add('active');
        } catch (err) {
            this.addLog('Could not load source day: ' + err.message, 'error');
        }
    }

    // Utilities

    /**
     * Format a timestamp as UTC HH:MM:SSZ.
     * Accepts ISO-8601 string from server, or null (uses current time).
     */
    formatUtcTime(isoString = null) {
        const d = isoString ? new Date(isoString) : new Date();
        if (isNaN(d.getTime())) return isoString || '';  // fallback if unparseable
        const hh = String(d.getUTCHours()).padStart(2, '0');
        const mm = String(d.getUTCMinutes()).padStart(2, '0');
        const ss = String(d.getUTCSeconds()).padStart(2, '0');
        return `${hh}:${mm}:${ss}Z`;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// switchPanel lives in core.js (single source of truth, guarded with optional chaining)

// ── Explorer Mode (Lexicon / Citations tab state) ─────────────────────────
let _explorerMode = localStorage.getItem('anchorworks_explorer_mode') || 'lexicon';

function setExplorerMode(mode) {
    _explorerMode = mode;
    localStorage.setItem('anchorworks_explorer_mode', mode);

    // Toggle view containers
    const lexView   = document.getElementById('lex-view-lexicon');
    const citView   = document.getElementById('lex-view-citations');
    const noteView  = document.getElementById('lex-view-notes');
    const chatView  = document.getElementById('lex-view-chat-history');
    const gnView    = document.getElementById('lex-view-genesis');
    const spellView = document.getElementById('lex-view-spell-check');
    if (lexView)   lexView.style.display   = (mode === 'lexicon' || mode === 'symbols') ? '' : 'none';
    if (citView)   citView.style.display   = mode === 'citations'     ? '' : 'none';
    if (noteView)  noteView.style.display  = mode === 'notes'         ? '' : 'none';
    if (chatView)  chatView.style.display  = mode === 'chat-history'  ? '' : 'none';
    if (gnView)    gnView.style.display    = mode === 'genesis'       ? '' : 'none';
    if (spellView) spellView.style.display = mode === 'spell-check'   ? '' : 'none';

    // Toggle tab active states
    document.querySelectorAll('.lex-mode-tab').forEach(tab => {
        const isActive = tab.dataset.mode === mode;
        tab.classList.toggle('active', isActive);
        /* styling handled by .lex-mode-tab / .lex-mode-tab.active in CSS */
    });

    // Auto-load data when switching tabs (deferred so window.app is assigned)
    setTimeout(() => {
        const _app = window.app;
        _app?._lexApplyExplorerChrome?.();
        if (mode === 'symbols') {
            if (_app?._lexLastEntries?.length) _app._lexRenderResults(_app._lexLastEntries, _app._lexLastMeta || 'Symbols');
            else _app?.lexBrowseTop?.();
        }
        if (mode === 'lexicon' && _app?._lexLastEntries?.length) {
            _app._lexRenderResults(_app._lexLastEntries, _app._lexLastMeta || 'Lexicon');
        }
        if (mode === 'citations') _app?.citUpdateExplorerStats();
        if (mode === 'notes') _app?.noteUpdateExplorerStats();
        if (mode === 'chat-history') _loadBrowserChatDays();
        if (mode === 'genesis') window.gnInit?.();
        if (mode === 'spell-check') spellRefreshQueue();
    }, 0);
}

// ── Spell Check (renders inside panel-lexicon as explorer mode) ──────

let _spellPollTimer = null;

async function spellRefreshQueue() {
    try {
        const [queueRes, statsRes] = await Promise.all([
            fetch('/api/spellcheck/queue?limit=50'),
            fetch('/api/spellcheck/stats'),
        ]);
        if (!queueRes.ok || !statsRes.ok) return;
        const queueData = await queueRes.json();
        const statsData = await statsRes.json();

        // Update stats strip
        const el = (id) => document.getElementById(id);
        if (el('spell-stat-pending'))  el('spell-stat-pending').textContent  = statsData.pending  || 0;
        if (el('spell-stat-accepted')) el('spell-stat-accepted').textContent = statsData.accepted || 0;
        if (el('spell-stat-rejected')) el('spell-stat-rejected').textContent = statsData.rejected || 0;
        if (el('spell-stat-aliases'))  el('spell-stat-aliases').textContent  = statsData.alias_count || 0;

        // Render queue table
        const tbody = el('spell-queue-body');
        if (!tbody) return;
        const entries = queueData.entries || [];
        if (entries.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="padding:24px; text-align:center; color:var(--text-secondary);">No pending corrections</td></tr>';
            return;
        }
        tbody.innerHTML = entries.map(e => `
            <tr style="border-bottom:1px solid var(--border);">
                <td style="padding:8px 12px; color:var(--error); font-weight:600;">${_esc(e.original)}</td>
                <td style="padding:8px 12px; color:var(--success);">${e.suggestion ? _esc(e.suggestion) : '<span style="color:var(--text-secondary);">—</span>'}</td>
                <td style="padding:8px 12px; color:var(--text-secondary); max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${_esc(e.context || '')}</td>
                <td style="padding:8px 12px; color:var(--text-secondary);">${_esc(e.source || '')}</td>
                <td style="padding:8px 12px; text-align:center; white-space:nowrap;">
                    ${e.suggestion ? `<button onclick="spellResolve('${e.id}','accept','${_esc(e.suggestion)}')" style="padding:3px 10px; font-size:11px; background:var(--success); color:#000; border:none; border-radius:4px; cursor:pointer; margin:0 2px;">Accept</button>` : ''}
                    <button onclick="spellResolve('${e.id}','reject','')" style="padding:3px 10px; font-size:11px; background:var(--error); color:#fff; border:none; border-radius:4px; cursor:pointer; margin:0 2px;">Reject</button>
                    ${!e.suggestion ? `<button onclick="spellModelAssist('${e.id}','${_esc(e.original)}','${_esc(e.context||'')}')" style="padding:3px 10px; font-size:11px; background:var(--gpt-oss); color:#000; border:none; border-radius:4px; cursor:pointer; margin:0 2px;">Model Assist</button>` : ''}
                </td>
            </tr>
        `).join('');
    } catch (err) {
        console.warn('spellRefreshQueue error:', err);
    }
}

function _esc(s) {
    if (!s) return '';
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

async function spellResolve(entryId, action, finalToken) {
    try {
        const res = await fetch('/api/spellcheck/resolve', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: entryId, action, final_token: finalToken }),
        });
        if (res.ok) spellRefreshQueue();
    } catch (err) {
        console.warn('spellResolve error:', err);
    }
}

async function spellModelAssist(entryId, anchor, context) {
    try {
        const res = await fetch('/api/spellcheck/model-assist', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ anchor, ["to" + "ken"]: anchor, context }),
        });
        if (!res.ok) return;
        const data = await res.json();
        if (data.suggestion) {
            // Update the row to show the suggestion with accept/reject buttons
            spellRefreshQueue();
            // Also prompt for the specific entry
            if (confirm(`Model suggests: "${data.suggestion}" for "${anchor}"\nAccept this correction?`)) {
                spellResolve(entryId, 'accept', data.suggestion);
            }
        } else {
            alert(`Model could not suggest a correction for "${anchor}".`);
        }
    } catch (err) {
        console.warn('spellModelAssist error:', err);
    }
}

async function spellManualCheck() {
    const input = document.getElementById('spell-manual-input');
    const resultsDiv = document.getElementById('spell-manual-results');
    if (!input || !resultsDiv) return;
    const text = input.value.trim();
    if (!text) return;

    const anchors = text.toLowerCase().split(/\s+/);
    try {
        const res = await fetch('/api/spellcheck/check', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ anchors, ["to" + "kens"]: anchors }),
        });
        if (!res.ok) { resultsDiv.textContent = 'Error checking anchors'; return; }
        const data = await res.json();
        const results = data.results || [];
        resultsDiv.innerHTML = results.map(r => {
            if (r.status === 'correct') return `<span style="color:var(--success);">${_esc(r.anchor || r["to" + "ken"])}</span>`;
            if (r.status === 'suggested') return `<span style="color:var(--warning);"><s>${_esc(r.anchor || r["to" + "ken"])}</s> &rarr; ${_esc(r.suggestion)}</span>`;
            return `<span style="color:var(--error);">${_esc(r.anchor || r["to" + "ken"])}?</span>`;
        }).join(' ');
    } catch (err) {
        resultsDiv.textContent = 'Error: ' + err.message;
    }
}

// ── Browser Chat History (renders inside panel-lexicon, not modal) ──────

let _chatHistCurrentDay = null;

async function _loadBrowserChatDays() {
    const list = document.getElementById('chat-hist-day-list');
    const statDays = document.getElementById('chat-hist-stat-days');
    const statMsgs = document.getElementById('chat-hist-stat-messages');
    const status = document.getElementById('chat-hist-strip-status');
    if (!list) return;

    list.innerHTML = '<div style="color:var(--text-secondary); font-size:11px; padding:12px; text-align:center;">Loading...</div>';
    if (status) status.textContent = 'loading...';

    try {
        const resp = await fetch(
            (ANCHORWORKS_CONFIG?.llm || 'http://127.0.0.1:11435') + '/api/conversation/days',
            { credentials: 'include' }
        );
        const data = await resp.json();
        if (!data.days || data.days.length === 0) {
            list.innerHTML = '<div style="color:var(--text-secondary); font-size:11px; padding:12px; text-align:center;">No conversation days found.</div>';
            if (statDays) statDays.textContent = '0';
            if (statMsgs) statMsgs.textContent = '0';
            if (status) status.textContent = '';
            return;
        }

        const totalMsgs = data.days.reduce((sum, d) => sum + (d.message_count || 0), 0);
        if (statDays) statDays.textContent = data.days.length;
        if (statMsgs) statMsgs.textContent = totalMsgs;
        if (status) status.textContent = '';

        const today = new Date().toISOString().slice(0, 10);
        list.innerHTML = data.days.map(d => {
            const isToday = d.day === today;
            const isActive = d.day === _chatHistCurrentDay;
            return `<div onclick="_openBrowserChatDay('${d.day}')" style="padding:8px 12px; cursor:pointer; border-bottom:1px solid var(--border); font-size:12px; display:flex; justify-content:space-between; align-items:center; background:${isActive ? 'var(--accent-bg)' : ''};"
                onmouseenter="this.style.background='var(--accent-bg)'" onmouseleave="this.style.background='${isActive ? 'var(--accent-bg)' : ''}'">
                <span style="font-weight:${isToday ? '700' : '400'}; color:${isToday ? '#00d4ff' : 'var(--text-primary)'};">${d.day}${isToday ? ' (today)' : ''}</span>
                <span style="color:var(--text-secondary); font-size:10px;">${d.message_count} msgs</span>
            </div>`;
        }).join('');
    } catch (e) {
        list.innerHTML = `<div style="color:var(--danger); font-size:11px; padding:12px;">Error: ${e.message}</div>`;
        if (status) status.textContent = 'error';
    }
}

async function _openBrowserChatDay(day) {
    _chatHistCurrentDay = day;
    const container = document.getElementById('chat-hist-messages');
    const activeLabel = document.getElementById('chat-hist-active-day');
    if (!container || !window.app) return;

    if (activeLabel) activeLabel.textContent = day;
    container.innerHTML = '<div style="color:var(--text-secondary); text-align:center; padding:20px;">Loading...</div>';

    // Re-highlight active day in list
    const list = document.getElementById('chat-hist-day-list');
    if (list) {
        list.querySelectorAll('div[onclick]').forEach(el => {
            const isActive = el.getAttribute('onclick').includes(day);
            el.style.background = isActive ? 'var(--accent-bg)' : '';
        });
    }

    try {
        const resp = await fetch(
            (ANCHORWORKS_CONFIG?.llm || 'http://127.0.0.1:11435') + `/api/conversation/day/${day}`,
            { credentials: 'include' }
        );
        const data = await resp.json();
        if (!data.messages || data.messages.length === 0) {
            container.innerHTML = '<div style="color:var(--text-secondary); text-align:center; padding:20px;">No messages for this day.</div>';
            return;
        }

        // Render using the same blockify → _messageStore → renderBlocksHtml pipeline as live chat
        container.innerHTML = data.messages.map(msg => {
            const actor = msg.actor || (msg.sender === 'user' ? 'user' : 'assistant');
            const role = actor === 'user' ? 'user' : (actor === 'system' ? 'system' : 'assistant');
            const label = role === 'user' ? (msg.display_name || 'user')
                        : (msg.seat?.model || msg.model || 'assistant');
            const time = msg.timestamp ? msg.timestamp.slice(11, 19) : '';
            const bg = role === 'user' ? 'var(--accent-bg)' : 'var(--card-bg, var(--secondary-bg))';
            const border = role === 'system' ? '2px solid var(--warning)' : '1px solid var(--border)';

            // Generate a stable messageId for the store
            const messageId = `hist_${day}_${msg.id || 0}`;
            const blocks = app.blockify(msg.content);
            const notesByBlock = {};

            // Register in _messageStore so openBlockPicker works
            app._messageStore.set(messageId, {
                blocks,
                notesByBlock,
                role,
                text: msg.content,
                citeReport: null,
                citesByBlock: {},
                serverId: msg.id || null,
            });

            const blocksHtml = app.renderBlocksHtml(blocks, messageId, notesByBlock, null);

            const b64 = btoa(unescape(encodeURIComponent(msg.content)));
            return `<div style="margin:8px 0; padding:8px 10px; border-radius:6px; background:${bg}; border:${border};">
                <div style="font-size:10px; color:var(--text-secondary); margin-bottom:4px; display:flex; justify-content:space-between; align-items:center;">
                    <span><strong>${escapeHtml(label)}</strong></span>
                    <span style="display:flex; gap:6px; align-items:center;">
                        <button onclick="forkToCurrentChat('${day}', ${msg.id || 0}, '${b64}', '${actor}')" class="btn btn-sm" style="font-size:9px; padding:1px 6px; background:var(--success); color:#fff; border:none; border-radius:4px; cursor:pointer;">Fork to Side Chat</button>
                        <span>${time}</span>
                    </span>
                </div>
                ${blocksHtml}
            </div>`;
        }).join('');
    } catch (e) {
        container.innerHTML = `<div style="color:var(--danger); text-align:center; padding:20px;">Error: ${e.message}</div>`;
    }
}

async function chatHandleFileUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    // Size guard (10 MB)
    if (file.size > 10 * 1024 * 1024) {
        app.addGptMessage('system', `File too large: ${(file.size / (1024 * 1024)).toFixed(1)}MB (max 10MB)`);
        event.target.value = '';
        return;
    }

    app.addGptMessage('system', `Uploading: ${file.name} (${(file.size / 1024).toFixed(1)} KB)...`);

    const fd = new FormData();
    fd.append('file', file);

    try {
        const resp = await fetch(bridgeApi('/api/artifacts/upload'), {
            method: 'POST',
            credentials: 'include',
            body: fd,
        });
        const data = await resp.json();
        if (resp.ok && data.ok) {
            app.addGptMessage('system', `Uploaded: ${data.path} (${data.size_bytes} bytes)`);
            app.addLog(`Artifact uploaded: ${data.path}`, 'success');
            // Refresh artifacts panel if visible
            if (typeof afInit === 'function') afInit();
        } else {
            app.addGptMessage('system', `Upload failed: ${data.detail || 'Unknown error'}`);
        }
    } catch (e) {
        app.addGptMessage('system', `Upload error: ${e.message}`);
    }

    // Reset file input for re-upload of same file
    event.target.value = '';
}

window.chatHandleFileUpload = chatHandleFileUpload;

function submitMappingJob() {
    app.submitMappingJob();
}

function downloadReport() {
    app.downloadReport();
}

function commitToDataLake() {
    // Prefer DocuMap panel's lastCreatedMap, fall back to console's currentReport
    const report = window.lastCreatedMap || (app && app.currentReport);
    if (!report) {
        alert('No report available. Run a mapping job first.');
        return;
    }

    // Visual feedback: disable button, show progress
    const btn = document.getElementById('dm-commit-btn');
    const progressDiv = document.getElementById('dm-commit-progress');
    const fill = document.getElementById('dm-commit-fill');
    const status = document.getElementById('dm-commit-status');

    if (btn) { btn.disabled = true; btn.textContent = 'Committing...'; btn.style.opacity = '0.6'; }
    if (progressDiv) progressDiv.style.display = 'block';
    if (fill) fill.style.width = '30%';
    if (status) status.textContent = 'Sending to Data Lake...';

    const jobName = report.map_id || report.run_id || '616_map';
    const citeId = report.cite_id || window.lastCreatedCitationId || null;

    if (fill) fill.style.width = '60%';
    if (status) status.textContent = 'Processing...';

    fetch(bridgeApi('/api/map/commit'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ job_name: jobName, report: report, cite_id: citeId }),
    })
    .then(r => r.json())
    .then(result => {
        if (fill) fill.style.width = '100%';
        if (result.status === 'committed') {
            const groveMsg = result.grove_chunks
                ? ` (${result.grove_chunks} chunks ingested into Data Lake)`
                : (result.grove_error ? ` (Lake: ${result.grove_error})` : '');
            if (status) { status.textContent = 'Committed!'; status.style.color = 'var(--success, #4caf50)'; }
            if (btn) { btn.textContent = 'Committed'; btn.style.background = 'var(--success, #4caf50)'; }
            if (app) app.addLog('Committed to data lake: ' + (result.path || '') + groveMsg, 'success');
            setTimeout(() => { _resetCommitBtn(btn, progressDiv, fill, status); }, 3000);
        } else {
            if (status) { status.textContent = 'Failed: ' + (result.detail || 'Unknown error'); status.style.color = 'var(--error, #f44336)'; }
            if (btn) { btn.textContent = 'Failed — Retry?'; btn.style.background = 'var(--error, #f44336)'; }
            setTimeout(() => { _resetCommitBtn(btn, progressDiv, fill, status); }, 4000);
        }
    })
    .catch(e => {
        if (fill) fill.style.width = '100%';
        if (status) { status.textContent = 'Error: ' + e.message; status.style.color = 'var(--error, #f44336)'; }
        if (btn) { btn.textContent = 'Error — Retry?'; btn.style.background = 'var(--error, #f44336)'; }
        setTimeout(() => { _resetCommitBtn(btn, progressDiv, fill, status); }, 4000);
    });
}

function _resetCommitBtn(btn, progressDiv, fill, status) {
    if (btn) { btn.disabled = false; btn.textContent = 'Append to Data Lake'; btn.style.opacity = '1'; btn.style.background = ''; }
    if (progressDiv) progressDiv.style.display = 'none';
    if (fill) fill.style.width = '0%';
    if (status) { status.textContent = ''; status.style.color = 'var(--text-secondary)'; }
}

function testGptConnection() {
    app.testGptConnection();
}

/**
 * Resolve the model name for the current mode.
 * Local modes use the dropdown; cloud modes use localStorage.
 * Falls back to 'default' (server picks from config).
 */
// _resolveModelForMode removed — mode dropdown gone, cloud models via chain slots.

function sendGptMessage() {
    app.sendGptMessage();
}

function injectAnchorWorksContext() {
    app.injectAnchorWorksContext();
}

function clearGptChat() {
    app.clearGptChat();
}

function flagCitation() {
    app.flagCitation();
}

function copyCanonical() {
    app.copyCanonical();
}

function viewFullMessage() {
    app.viewFullMessage();
}

function jumpToSourceDay() {
    app.jumpToSourceDay();
}

function closeCiteModal() {
    document.getElementById('cite-modal').classList.remove('active');
}

function searchLexicon(query) {
    if (app) app.searchLexicon(query);
}

function saveSettings() {
    app.saveSettings();
}

// ── Lexicon Danger Gate (Intent → Hello → Severe Warning) ───────
let _lexDangerAction = null;
let _lexDangerAuthorizedAt = 0;   // timestamp of Hello success
let _lexDangerTimerInterval = null;
const _LEX_DANGER_TTL = 60;       // 60-second authorization window

const _LEX_DANGER_META = {
    clear_canonical: {
        name: 'Clear Canonical',
        confirmPhrase: 'CLEAR CANONICAL',
        warning: 'This will reset ALL canonical entries to AVAILABLE. Every word binding in the lexicon will be destroyed. Slots return to the pool. The brain loses its vocabulary.',
        exec: () => app.lexClearCanonical(),
    },
    return_to_pool: {
        name: 'Return to Pool',
        confirmPhrase: 'RETURN TO POOL',
        warning: 'This will move ALL canonical slots back to the spare pool. The lexicon drops to 0 entries. Every mapped word is unbound. This is a full wipe of the address space.',
        exec: () => app.lexReturnToPool(),
    },
    import_word_list: {
        name: 'Import Word List',
        confirmPhrase: 'IMPORT WORD LIST',
        warning: 'This will overwrite existing lexicon entries with imported word data. Any current mappings for imported words will be replaced. This is irreversible without a backup.',
        exec: () => app.lexImportWordList(),
    },
};

function lexDangerGate(action) {
    const meta = _LEX_DANGER_META[action];
    if (!meta) return;
    _lexDangerAction = action;
    _lexDangerAuthorizedAt = 0;
    document.getElementById('lex-danger-action-name').textContent = meta.name;
    document.getElementById('lex-danger-warning-text').textContent = meta.warning;
    document.getElementById('lex-danger-confirm-phrase').textContent = meta.confirmPhrase;
    document.getElementById('lex-danger-confirm-input').value = '';
    document.getElementById('lex-danger-hello-error').style.display = 'none';
    document.getElementById('lex-danger-step1').style.display = '';
    document.getElementById('lex-danger-step2').style.display = 'none';
    const btn = document.getElementById('lex-danger-proceed-btn');
    btn.disabled = true;
    btn.style.background = '#666';
    btn.style.color = '#999';
    btn.style.cursor = 'not-allowed';
    document.getElementById('lex-danger-overlay').style.display = 'flex';
}

async function lexDangerUnlock() {
    const errEl = document.getElementById('lex-danger-hello-error');
    const btn = document.getElementById('lex-danger-unlock-btn');
    errEl.style.display = 'none';
    btn.textContent = 'Authenticating...';
    btn.disabled = true;

    try {
        // Request Windows Hello authentication via existing WebAuthn flow
        const optRes = await fetch(`${AUTH_BASE}/api/auth/login/begin`, {
            method: 'POST', credentials: 'include',
        });
        if (!optRes.ok) throw new Error('Auth server not available');
        const options = await optRes.json();

        // Decode challenge
        options.challenge = _b64urlDecode(options.challenge);
        if (options.allowCredentials) {
            options.allowCredentials = options.allowCredentials.map(c => ({
                ...c, id: _b64urlDecode(c.id),
            }));
        }

        // Windows Hello biometric prompt
        const assertion = await navigator.credentials.get({ publicKey: options });

        // Verify with server
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
        if (!verifyRes.ok) throw new Error('Authentication rejected');

        // Hello succeeded — start 60s authorization window
        _lexDangerAuthorizedAt = Date.now();
        _lexDangerStartTimer();

        // Show Step 2: Severe Warning
        document.getElementById('lex-danger-step1').style.display = 'none';
        document.getElementById('lex-danger-step2').style.display = '';
        // Focus on Back Away (safe default)
        setTimeout(() => document.getElementById('lex-danger-backaway-btn').focus(), 50);

    } catch (e) {
        errEl.textContent = e.name === 'NotAllowedError'
            ? 'Windows Hello cancelled or not available.'
            : `Authentication failed: ${e.message}`;
        errEl.style.display = 'block';
    } finally {
        btn.textContent = 'Unlock with Windows Hello';
        btn.disabled = false;
    }
}

function _lexDangerStartTimer() {
    if (_lexDangerTimerInterval) clearInterval(_lexDangerTimerInterval);
    const timerEl = document.getElementById('lex-danger-timer');
    _lexDangerTimerInterval = setInterval(() => {
        const elapsed = Math.floor((Date.now() - _lexDangerAuthorizedAt) / 1000);
        const remaining = _LEX_DANGER_TTL - elapsed;
        if (remaining <= 0) {
            clearInterval(_lexDangerTimerInterval);
            _lexDangerTimerInterval = null;
            _lexDangerAuthorizedAt = 0;
            timerEl.textContent = 'Authorization expired. Back away and try again.';
            timerEl.style.color = '#ff4444';
            const btn = document.getElementById('lex-danger-proceed-btn');
            btn.disabled = true;
            btn.style.background = '#666';
            btn.style.color = '#999';
            btn.style.cursor = 'not-allowed';
            return;
        }
        timerEl.textContent = `Authorization expires in ${remaining}s`;
        timerEl.style.color = remaining <= 15 ? '#ff4444' : '#ff8800';
    }, 1000);
}

function lexDangerCheckTyped() {
    const meta = _LEX_DANGER_META[_lexDangerAction];
    if (!meta) return;
    const input = document.getElementById('lex-danger-confirm-input').value.trim().toUpperCase();
    const match = input === meta.confirmPhrase;
    const authorized = _lexDangerAuthorizedAt > 0 &&
        (Date.now() - _lexDangerAuthorizedAt) < _LEX_DANGER_TTL * 1000;
    const btn = document.getElementById('lex-danger-proceed-btn');
    if (match && authorized) {
        btn.disabled = false;
        btn.style.background = 'linear-gradient(135deg,#ff4444,#cc0000)';
        btn.style.color = '#fff';
        btn.style.cursor = 'pointer';
    } else {
        btn.disabled = true;
        btn.style.background = '#666';
        btn.style.color = '#999';
        btn.style.cursor = 'not-allowed';
    }
}

function lexDangerCancel() {
    if (_lexDangerTimerInterval) { clearInterval(_lexDangerTimerInterval); _lexDangerTimerInterval = null; }
    document.getElementById('lex-danger-overlay').style.display = 'none';
    _lexDangerAction = null;
    _lexDangerAuthorizedAt = 0;
    if (app) app.addLog('Lexicon operation cancelled', 'info', { source: 'lex' });
}

async function lexDangerProceed() {
    // Final check: authorization still valid?
    if (!_lexDangerAuthorizedAt || (Date.now() - _lexDangerAuthorizedAt) >= _LEX_DANGER_TTL * 1000) {
        alert('Authorization expired. Please authenticate again.');
        return;
    }
    if (_lexDangerTimerInterval) { clearInterval(_lexDangerTimerInterval); _lexDangerTimerInterval = null; }

    const meta = _LEX_DANGER_META[_lexDangerAction];
    const actionName = _lexDangerAction;

    // Auto-snapshot BEFORE destruction — the real safety net
    try {
        if (app) app.addLog(`Creating safety snapshot before ${meta.name}...`, 'info', { source: 'lex' });
        const snapRes = await fetch(bridgeApi('/api/snapshot'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tag: `pre_${actionName}` }),
        });
        if (snapRes.ok) {
            const snapData = await snapRes.json();
            if (app) app.addLog(`Safety snapshot saved: ${snapData.path}`, 'success', { source: 'lex' });
        } else {
            // Snapshot failed — still let them proceed but warn
            if (app) app.addLog('Warning: safety snapshot failed — proceeding without backup', 'warning', { source: 'lex' });
        }
    } catch (e) {
        if (app) app.addLog(`Snapshot error: ${e.message} — proceeding without backup`, 'warning', { source: 'lex' });
    }

    document.getElementById('lex-danger-overlay').style.display = 'none';
    _lexDangerAction = null;
    _lexDangerAuthorizedAt = 0;
    if (meta) meta.exec();
}

async function lexDangerRestore() {
    if (_lexDangerTimerInterval) { clearInterval(_lexDangerTimerInterval); _lexDangerTimerInterval = null; }
    document.getElementById('lex-danger-overlay').style.display = 'none';
    _lexDangerAction = null;
    _lexDangerAuthorizedAt = 0;

    // Fetch available snapshots and rollback to latest
    try {
        const listRes = await fetch(bridgeApi('/api/snapshots'));
        if (!listRes.ok) throw new Error(`HTTP ${listRes.status}`);
        const listData = await listRes.json();
        const snapshots = listData.snapshots || [];

        if (snapshots.length === 0) {
            alert('No snapshots available. No backup exists to restore from.');
            return;
        }

        // Show the latest snapshot and ask for confirmation
        const latest = snapshots[0];
        const ts = new Date(latest.created * 1000).toLocaleString();
        if (!confirm(`Restore from latest snapshot?\n\n${latest.name}\nCreated: ${ts}\n\nThis will rollback the entire lexicon to that state.`)) {
            if (app) app.addLog('Restore cancelled', 'info', { source: 'lex' });
            return;
        }

        if (app) app.addLog(`Restoring from ${latest.name}...`, 'info', { source: 'lex' });
        const rollRes = await fetch(bridgeApi('/api/rollback'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: latest.path }),
        });
        if (!rollRes.ok) {
            const err = await rollRes.json().catch(() => ({}));
            throw new Error(err.detail || `HTTP ${rollRes.status}`);
        }
        const rollData = await rollRes.json();
        if (app) {
            app.addLog(`Lexicon restored from ${latest.name}: ${rollData.entries?.toLocaleString() || '?'} entries`, 'success', { source: 'lex' });
            app.updateLexiconStats();
            app.connectToServer();
        }
        alert(`Lexicon restored from snapshot: ${latest.name}`);
    } catch (e) {
        alert(`Restore failed: ${e.message}`);
        if (app) app.addLog(`Restore failed: ${e.message}`, 'error', { source: 'lex' });
    }
}

function switchModel(name) {
    app.switchModel(name);
}

function toggleAutoDailySummary(checked) {
    localStorage.setItem('anchorworks_auto_daily_summary', checked ? 'true' : 'false');
}


// ── Chat Explorer (read-only day browser) ──────────────────────
let _explorerOpen = false;

function toggleChatExplorer() {
    _explorerOpen = !_explorerOpen;
    const panel = document.getElementById('explorer-panel');
    const citeList = document.getElementById('cite-list');
    const citeSummary = document.getElementById('cite-summary');
    const citeDetail = document.getElementById('cite-detail');
    const citeActions = document.getElementById('cite-actions');

    if (_explorerOpen) {
        panel.style.display = '';
        citeList.style.display = 'none';
        if (citeSummary) citeSummary.style.display = 'none';
        if (citeDetail) citeDetail.style.display = 'none';
        if (citeActions) citeActions.style.display = 'none';
        _loadExplorerDays();
    } else {
        panel.style.display = 'none';
        citeList.style.display = '';
    }
}

async function _loadExplorerDays() {
    const list = document.getElementById('explorer-day-list');
    list.innerHTML = '<div style="color:var(--text-secondary); font-size:11px; padding:8px;">Loading...</div>';
    try {
        const resp = await fetch(
            (ANCHORWORKS_CONFIG?.llm || 'http://127.0.0.1:11435') + '/api/conversation/days',
            { credentials: 'include' }
        );
        const data = await resp.json();
        if (!data.days || data.days.length === 0) {
            list.innerHTML = '<div style="color:var(--text-secondary); font-size:11px; padding:8px;">No conversation days found.</div>';
            return;
        }
        const today = new Date().toISOString().slice(0, 10);
        list.innerHTML = data.days.map(d => {
            const isToday = d.day === today;
            return `<div onclick="openExplorerDay('${d.day}')" style="padding:6px 8px; cursor:pointer; border-bottom:1px solid var(--border); font-size:12px; display:flex; justify-content:space-between; align-items:center;"
                onmouseenter="this.style.background='var(--accent-bg)'" onmouseleave="this.style.background=''">
                <span>${d.day}${isToday ? ' (today)' : ''}</span>
                <span style="color:var(--text-secondary); font-size:10px;">${d.message_count} msgs</span>
            </div>`;
        }).join('');
    } catch (e) {
        list.innerHTML = `<div style="color:var(--danger); font-size:11px; padding:8px;">Error: ${e.message}</div>`;
    }
}

let _explorerCurrentDay = null;

async function openExplorerDay(day) {
    _explorerCurrentDay = day;
    const modal = document.getElementById('explorer-modal');
    const title = document.getElementById('explorer-modal-title');
    const container = document.getElementById('explorer-modal-messages');
    title.textContent = `Conversation — ${day}`;
    container.innerHTML = '<div style="color:var(--text-secondary);">Loading...</div>';
    modal.style.display = 'flex';

    try {
        const resp = await fetch(
            (ANCHORWORKS_CONFIG?.llm || 'http://127.0.0.1:11435') + `/api/conversation/day/${day}`,
            { credentials: 'include' }
        );
        const data = await resp.json();
        if (!data.messages || data.messages.length === 0) {
            container.innerHTML = '<div style="color:var(--text-secondary);">No messages for this day.</div>';
            return;
        }
        container.innerHTML = data.messages.map(msg => {
            const actor = msg.actor || (msg.sender === 'user' ? 'user' : 'assistant');
            const role = actor === 'user' ? 'user' : (actor === 'system' ? 'system' : 'assistant');
            const label = role === 'user' ? (msg.display_name || 'user')
                        : (msg.seat?.model || msg.model || 'assistant');
            const time = msg.timestamp ? msg.timestamp.slice(11, 19) : '';
            const bg = role === 'user' ? 'var(--accent-bg)' : 'var(--card-bg)';
            const border = role === 'system' ? '2px solid var(--warning)' : '1px solid var(--border)';
            const content = escapeHtml(msg.content);
            const truncated = msg.content.length > 200 ? msg.content.slice(0, 200) + '...' : msg.content;
            // Encode content for fork button (base64 to avoid quoting issues)
            const b64 = btoa(unescape(encodeURIComponent(msg.content)));
            return `<div style="margin:8px 0; padding:8px 10px; border-radius:6px; background:${bg}; border:${border};">
                <div style="font-size:10px; color:var(--text-secondary); margin-bottom:4px; display:flex; justify-content:space-between; align-items:center;">
                    <span><strong>${escapeHtml(label)}</strong></span>
                    <span style="display:flex; gap:6px; align-items:center;">
                        <button onclick="forkToCurrentChat('${day}', ${msg.id || 0}, '${b64}', '${actor}')" class="btn btn-sm" style="font-size:9px; padding:1px 6px; background:var(--success); color:#fff;">Fork to Side Chat</button>
                        <span>${time}</span>
                    </span>
                </div>
                <div style="white-space:pre-wrap; word-break:break-word; font-size:12px; line-height:1.5;">${content}</div>
            </div>`;
        }).join('');
    } catch (e) {
        container.innerHTML = `<div style="color:var(--danger);">Error: ${e.message}</div>`;
    }
}

async function forkToCurrentChat(fromDay, messageId, b64Content, actor) {
    const content = decodeURIComponent(escape(atob(b64Content)));
    let result;
    try {
        result = await app.startSideChatFromContext({
            fromDay,
            messageId,
            content,
            actor,
            description: `Fork from ${fromDay} #${messageId || 0}`,
        });
    } catch (e) {
        alert('Fork failed: ' + e.message);
        return;
    }

    // Close explorer modal
    closeExplorerModal();

    if (window.app) {
        window.app.addGptMessage('system',
            `SIDE CHAT ${result.side_chat_id}: ${result.description}`
        );
    }
}

function closeExplorerModal() {
    document.getElementById('explorer-modal').style.display = 'none';
}


window.AnchorWorksConsole = AnchorWorksConsole;
window.ANCHORWORKS.ready.console = true;
