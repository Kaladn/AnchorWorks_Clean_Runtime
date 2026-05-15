const state = {
  branch: "main",
  lastResult: null,
  lastAssistant: null,
  lastWorkflow: null,
  sending: false,
};

const $ = (selector) => document.querySelector(selector);

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  let payload = null;
  const text = await response.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = { raw: text };
    }
  }
  if (!response.ok) {
    const detail = payload?.detail || payload?.error || response.statusText;
    throw new Error(String(detail));
  }
  return payload;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function compactTime(value) {
  if (!value) return "";
  const text = String(value);
  return text.includes("T") ? text.replace("T", " ").slice(0, 19) : text;
}

function setServerPill(ok, label) {
  const pill = $("#server-pill");
  pill.textContent = label || (ok ? "online" : "offline");
  pill.className = ok ? "status-ok" : "status-bad";
}

function showError(target, message) {
  target.innerHTML = `<div class="card error"><strong>Error</strong><pre>${escapeHtml(message)}</pre></div>`;
}

function activateTab(name) {
  document.querySelectorAll(".tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === name);
  });
  document.querySelectorAll(".panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === `panel-${name}`);
  });
  if (name === "system") refreshSystem();
  if (name === "evidence") renderEvidence();
}

function messageRecordHtml(record) {
  const sender = record.sender || record.actor || "message";
  const isAssistant = sender === "assistant";
  const identity = record.model_identity || {};
  const mode = identity.evidence_mode || identity.engine || record.mode || "";
  const uuid = record.message_uuid || record.id || "";
  const day = record.day || "";
  const actions = isAssistant
    ? `<div class="message-actions">
        <button class="mini-btn" type="button" data-note="${escapeHtml(uuid)}" data-day="${escapeHtml(day)}">Note</button>
        <button class="mini-btn" type="button" data-cite="${escapeHtml(uuid)}" data-day="${escapeHtml(day)}">Cite</button>
      </div>`
    : "";
  return `
    <article class="message ${isAssistant ? "assistant" : "user"}" data-message-id="${escapeHtml(uuid)}">
      <div class="message-head">
        <span>${escapeHtml(sender)}${mode ? ` · ${escapeHtml(mode)}` : ""}</span>
        <span>${escapeHtml(compactTime(record.created_at || record.timestamp || day))}</span>
      </div>
      <div class="message-body">${escapeHtml(record.content || record.response || "")}</div>
      ${actions}
    </article>
  `;
}

async function loadHistory() {
  const feed = $("#chat-feed");
  try {
    const history = await api(`/api/chat/history?branch=${encodeURIComponent(state.branch)}&limit=120`);
    const messages = history.messages || [];
    feed.innerHTML = messages.length ? messages.map(messageRecordHtml).join("") : `<div class="empty-state">No chat rows yet.</div>`;
    const assistants = messages.filter((item) => item.sender === "assistant");
    state.lastAssistant = assistants.at(-1) || null;
    feed.scrollTop = feed.scrollHeight;
  } catch (error) {
    showError(feed, error.message);
  }
}

function renderWorkbenchActions(result) {
  const actions = result?.actions || result?.workbench?.actions || [];
  if (!actions.length) return "";
  return `
    <div class="message-actions">
      ${actions.map((action) => `<button class="mini-btn" type="button" data-action="${escapeHtml(action.id)}">${escapeHtml(action.label || action.id)}</button>`).join("")}
      <button class="mini-btn" type="button" data-note="${escapeHtml(result.assistant_message?.message_uuid || "")}" data-day="${escapeHtml(result.assistant_message?.day || "")}">Note</button>
      <button class="mini-btn" type="button" data-cite="${escapeHtml(result.assistant_message?.message_uuid || "")}" data-day="${escapeHtml(result.assistant_message?.day || "")}">Cite</button>
    </div>
  `;
}

function appendAssistantResult(result) {
  const feed = $("#chat-feed");
  const assistant = result.assistant_message || {};
  const html = `
    <article class="message assistant" data-message-id="${escapeHtml(assistant.message_uuid || "")}">
      <div class="message-head">
        <span>assistant · ${escapeHtml(result.mode || assistant.model_identity?.engine || "anchorworks")}</span>
        <span>${escapeHtml(compactTime(assistant.created_at || assistant.day))}</span>
      </div>
      <div class="message-body">${escapeHtml(result.response || assistant.content || "")}</div>
      ${renderWorkbenchActions(result)}
    </article>
  `;
  feed.insertAdjacentHTML("beforeend", html);
  feed.scrollTop = feed.scrollHeight;
}

async function sendChat(messageOverride = "") {
  if (state.sending) return;
  const input = $("#chat-input");
  const message = (messageOverride || input.value).trim();
  if (!message) return;

  state.sending = true;
  const sendButton = $("#chat-form button[type='submit']");
  sendButton.disabled = true;
  const feed = $("#chat-feed");
  feed.insertAdjacentHTML("beforeend", messageRecordHtml({ sender: "user", content: message, created_at: new Date().toISOString() }));
  feed.scrollTop = feed.scrollHeight;

  try {
    const result = await api("/api/chat/send", {
      method: "POST",
      body: JSON.stringify({
        message,
        mode: $("#chat-mode").value,
        branch: state.branch,
        model: $("#chat-model").value.trim(),
        evidence_visible: $("#evidence-toggle").checked,
      }),
    });
    state.lastResult = result;
    state.lastAssistant = result.assistant_message || null;
    state.lastWorkflow = result.workflow || null;
    appendAssistantResult(result);
    renderEvidence();
    input.value = "";
  } catch (error) {
    feed.insertAdjacentHTML("beforeend", `<div class="card error"><strong>Send failed</strong><pre>${escapeHtml(error.message)}</pre></div>`);
  } finally {
    state.sending = false;
    sendButton.disabled = false;
    input.focus();
  }
}

async function stopResponse() {
  const workflowId = state.lastWorkflow?.workflow_id || state.lastResult?.workflow?.workflow_id || "";
  const responseId = state.lastAssistant?.message_uuid || "";
  try {
    const result = await api("/api/chat/stop", {
      method: "POST",
      body: JSON.stringify({ workflow_id: workflowId, response_id: responseId }),
    });
    $("#chat-feed").insertAdjacentHTML("beforeend", `<div class="card"><strong>Stopped</strong><pre>${escapeHtml(JSON.stringify(result, null, 2))}</pre></div>`);
  } catch (error) {
    $("#chat-feed").insertAdjacentHTML("beforeend", `<div class="card error"><strong>Stop failed</strong><pre>${escapeHtml(error.message)}</pre></div>`);
  }
}

async function attachNote(messageId, day) {
  const text = prompt("Note for this block:");
  if (!text) return;
  try {
    await api("/api/chat/notes/attach", {
      method: "POST",
      body: JSON.stringify({ day, message_id: messageId, block_id: "b0", block_ordinal: 0, text }),
    });
    await loadHistory();
  } catch (error) {
    alert(`Note failed: ${error.message}`);
  }
}

async function attachCitation(messageId, day) {
  const coord = prompt("Citation coordinate/source reference:");
  if (!coord) return;
  const subject = prompt("Citation subject:", "AnchorWorks evidence") || "";
  try {
    await api("/api/chat/citations/attach", {
      method: "POST",
      body: JSON.stringify({ day, message_id: messageId, block_id: "b0", block_ordinal: 0, coord, subject, source: "ui" }),
    });
    await loadHistory();
  } catch (error) {
    alert(`Citation failed: ${error.message}`);
  }
}

function flattenEvidenceCards(title, value) {
  if (value == null || value === "" || (Array.isArray(value) && !value.length)) {
    return `<div class="trace-card"><h2>${escapeHtml(title)}</h2><div class="empty-state">No data.</div></div>`;
  }
  return `<div class="trace-card"><h2>${escapeHtml(title)}</h2><pre>${escapeHtml(JSON.stringify(value, null, 2))}</pre></div>`;
}

function renderEvidence() {
  const target = $("#evidence-view");
  const result = state.lastResult;
  if (!result) {
    target.innerHTML = `<div class="empty-state">Ask something in Chat to create an evidence frame.</div>`;
    return;
  }
  const clearspeak = result.clearspeak || {};
  target.innerHTML = [
    flattenEvidenceCards("Route", {
      mode: result.mode,
      writes_performed: result.writes_performed,
      evidence_visible: result.evidence_visible,
      engine: clearspeak.engine,
      evidence_mode: clearspeak.evidence_mode,
    }),
    flattenEvidenceCards("Represented", clearspeak.represented_anchors || clearspeak.query_anchors || clearspeak.represented || []),
    flattenEvidenceCards("Missing", clearspeak.missing_anchors || clearspeak.missing || []),
    flattenEvidenceCards("Citations", result.citations || clearspeak.citations || []),
    flattenEvidenceCards("Workbench Actions", result.actions || []),
    flattenEvidenceCards("Raw Evidence", result.evidence || clearspeak.evidence || clearspeak),
  ].join("");
}

async function searchLexicon(event) {
  event.preventDefault();
  const target = $("#lexicon-results");
  const query = $("#lexicon-query").value.trim();
  const pack = $("#lexicon-pack").value;
  if (!query) return;
  target.innerHTML = `<div class="empty-state">Searching...</div>`;
  try {
    const rows = await api(`/api/search_lexicon?query=${encodeURIComponent(query)}&pack=${encodeURIComponent(pack)}`);
    if (!rows.length) {
      target.innerHTML = `<div class="empty-state">No lexicon rows found.</div>`;
      return;
    }
    const headers = ["word", "anchor", "symbol", "hex", "pack", "status", "path"];
    target.innerHTML = `
      <table>
        <thead><tr>${headers.map((head) => `<th>${head}</th>`).join("")}</tr></thead>
        <tbody>
          ${rows.map((row) => `<tr>${headers.map((head) => `<td>${escapeHtml(row[head] ?? row.entry?.[head] ?? "")}</td>`).join("")}</tr>`).join("")}
        </tbody>
      </table>
    `;
  } catch (error) {
    showError(target, error.message);
  }
}

function statusCard(title, payload, okKey = "ok") {
  const ok = payload && (payload[okKey] === true || payload.configured === true || payload.status === "ok");
  const klass = ok ? "status-ok" : "status-warn";
  return `<div class="card"><h2>${escapeHtml(title)} <span class="${klass}">${ok ? "ok" : "check"}</span></h2><pre>${escapeHtml(JSON.stringify(payload, null, 2))}</pre></div>`;
}

async function refreshSystem() {
  const target = $("#system-view");
  target.innerHTML = `<div class="empty-state">Refreshing runtime facts...</div>`;
  const calls = [
    ["Health", "/api/health"],
    ["Chat", "/api/chat/status"],
    ["ClearSpeak", "/api/clearspeak/status"],
    ["Binary Substrate", "/api/binary-substrate/status"],
    ["Genome", "/api/symbol-genome/status"],
  ];
  const cards = [];
  for (const [name, path] of calls) {
    try {
      const payload = await api(path);
      cards.push(statusCard(name, payload));
      if (name === "Health") setServerPill(true, "online");
    } catch (error) {
      cards.push(`<div class="card error"><h2>${escapeHtml(name)}</h2><pre>${escapeHtml(error.message)}</pre></div>`);
      if (name === "Health") setServerPill(false, "offline");
    }
  }
  cards.push(statusCard("Active UI", { root: "Anchorworks/UI", fake_auth: false, dead_controls: false, plan: "Anchorworks/docs/ui buildout.MD" }));
  target.innerHTML = cards.join("");
}

function wireEvents() {
  document.querySelectorAll(".tab").forEach((button) => {
    button.addEventListener("click", () => activateTab(button.dataset.tab));
  });
  $("#chat-form").addEventListener("submit", (event) => {
    event.preventDefault();
    sendChat();
  });
  $("#refresh-history").addEventListener("click", loadHistory);
  $("#stop-response").addEventListener("click", stopResponse);
  $("#refresh-system").addEventListener("click", refreshSystem);
  $("#lexicon-form").addEventListener("submit", searchLexicon);
  $("#chat-feed").addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    if (target.dataset.action === "continue_working") sendChat("Continue working.");
    if (target.dataset.action === "hide_evidence") {
      $("#evidence-toggle").checked = false;
      renderEvidence();
    }
    if (target.dataset.action === "show_evidence") {
      $("#evidence-toggle").checked = true;
      renderEvidence();
    }
    if (target.dataset.note) attachNote(target.dataset.note, target.dataset.day || state.lastAssistant?.day || "");
    if (target.dataset.cite) attachCitation(target.dataset.cite, target.dataset.day || state.lastAssistant?.day || "");
  });
}

async function boot() {
  wireEvents();
  await refreshSystem();
  await loadHistory();
  renderEvidence();
}

boot();
