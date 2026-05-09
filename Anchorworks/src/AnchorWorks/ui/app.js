const INTAKE_RAW_PREVIEW_CHAR_LIMIT = 200000;
const INTAKE_RENDER_ROW_LIMIT = 1000;

const lexApp = {
  pack: "all",
  fileName: null,
  fileOffset: 0,
  searchTimer: null,
  treeBrainControls: null,
  symbolPolicy: null,
  diagnosticsReport: null,
  chatRequestController: null,
  activeChatWorkflow: null,
  tracer: {
    sessionId: "",
    events: [],
    maxEvents: 500,
    sequence: 0,
  },
  intake: {
    file: null,
    content: "",
    prep: null,
    report: null,
    sourceName: "",
    sourcePath: "",
    fileSize: 0,
    fileType: "",
    rejected: new Set(),
    selected: new Set(),
    edits: [],
    currentStep: "Waiting for document",
  },

  async boot() {
    this.cache();
    this.bind();
    this.renderChatEvidenceToggleLabel();
    this.renderAlphaStrip();
    await this.loadHealth();
    await this.refreshStats();
    await this.showRandom();
  },

  cache() {
    this.els = {
      banner: document.getElementById("status-banner"),
      tabLexicon: document.getElementById("tab-lexicon"),
      tabIntake: document.getElementById("tab-intake"),
      tabChat: document.getElementById("tab-chat"),
      tabTreeBrain: document.getElementById("tab-tree-brain"),
      tabTracer: document.getElementById("tab-tracer"),
      lexiconTab: document.getElementById("lexicon-tab"),
      intakeTab: document.getElementById("document-intake-tab"),
      chatTab: document.getElementById("chat-memory-tab"),
      treeBrainTab: document.getElementById("tree-brain-tab"),
      tracerTab: document.getElementById("tracer-tab"),
      dataRoot: document.getElementById("data-root"),
      statTotal: document.getElementById("stat-total"),
      statCanonical: document.getElementById("stat-canonical"),
      statSpare: document.getElementById("stat-spare"),
      resultMetaTitle: document.getElementById("result-meta-title"),
      resultMeta: document.getElementById("result-meta"),
      resultsTitle: document.getElementById("results-title"),
      resultsSubtitle: document.getElementById("results-subtitle"),
      queueUnmatched: document.getElementById("queue-unmatched"),
      queuePending: document.getElementById("queue-pending"),
      queueIgnored: document.getElementById("queue-ignored"),
      searchInput: document.getElementById("search-input"),
      searchBtn: document.getElementById("search-btn"),
      resetBtn: document.getElementById("reset-btn"),
      mappingBtn: document.getElementById("mapping-btn"),
      mappingPath: document.getElementById("mapping-path"),
      observedMapsBtn: document.getElementById("observed-maps-btn"),
      importPath: document.getElementById("import-path"),
      results: document.getElementById("results"),
      pager: document.getElementById("pager"),
      chart: document.getElementById("distribution-chart"),
      detailCard: document.getElementById("detail-card"),
      detailTitle: document.getElementById("detail-title"),
      detailBody: document.getElementById("detail-body"),
      alphaStrip: document.getElementById("alpha-strip"),
      intakeFileInput: document.getElementById("intake-file-input"),
      intakeAddBtn: document.getElementById("intake-add-btn"),
      intakeMapBtn: document.getElementById("intake-map-btn"),
      intakeFileName: document.getElementById("intake-file-name"),
      intakeFileMeta: document.getElementById("intake-file-meta"),
      intakeReadyTag: document.getElementById("intake-ready-tag"),
      intakeVisualCard: document.getElementById("intake-visual-card"),
      intakeVisualGrid: document.getElementById("intake-visual-grid"),
      intakeVisualBackends: document.getElementById("intake-visual-backends"),
      intakeSpinner: document.getElementById("intake-spinner"),
      intakeStepLabel: document.getElementById("intake-step-label"),
      intakeProgressFill: document.getElementById("intake-progress-fill"),
      intakeDocName: document.getElementById("intake-doc-name"),
      intakeDocType: document.getElementById("intake-doc-type"),
      intakeParagraphCount: document.getElementById("intake-paragraph-count"),
      intakeTotalCount: document.getElementById("intake-total-count"),
      intakeUniqueCount: document.getElementById("intake-unique-count"),
      intakeKnownCount: document.getElementById("intake-known-count"),
      intakeMissingCount: document.getElementById("intake-missing-count"),
      intakeLexiconPath: document.getElementById("intake-lexicon-path"),
      intakeRawMeta: document.getElementById("intake-raw-meta"),
      intakeRawPreview: document.getElementById("intake-raw-preview"),
      intakeUniqueMeta: document.getElementById("intake-unique-meta"),
      intakeUniqueFilter: document.getElementById("intake-unique-filter"),
      intakeUniqueList: document.getElementById("intake-unique-list"),
      intakeMissingMeta: document.getElementById("intake-missing-meta"),
      intakeMissingFilter: document.getElementById("intake-missing-filter"),
      intakeMissingList: document.getElementById("intake-missing-list"),
      intakeSelectVisibleBtn: document.getElementById("intake-select-visible-btn"),
      intakeApproveSelectedBtn: document.getElementById("intake-approve-selected-btn"),
      intakeBulkApproveBtn: document.getElementById("intake-bulk-approve-btn"),
      chatArchivePath: document.getElementById("chat-archive-path"),
      chatArchiveBtn: document.getElementById("chat-archive-btn"),
      chatRefreshBtn: document.getElementById("chat-refresh-btn"),
      clearSpeakStatusBtn: document.getElementById("clearspeak-status-btn"),
      clearSpeakStatusBtnSide: document.getElementById("clearspeak-status-btn-side"),
      clearSpeakStatusPanel: document.getElementById("clearspeak-status-panel"),
      clearSpeakQueryInput: document.getElementById("clearspeak-query-input"),
      clearSpeakQueryBtn: document.getElementById("clearspeak-query-btn"),
      clearSpeakRemixBtn: document.getElementById("clearspeak-remix-btn"),
      clearSpeakQueryPanel: document.getElementById("clearspeak-query-panel"),
      clearSpeakRemixPanel: document.getElementById("clearspeak-remix-panel"),
      flatDocName: document.getElementById("flat-doc-name"),
      flatDocRefreshBtn: document.getElementById("flat-doc-refresh-btn"),
      flatDocAnchorizeBtn: document.getElementById("flat-doc-anchorize-btn"),
      flatDocAnchorizeAllBtn: document.getElementById("flat-doc-anchorize-all-btn"),
      flatDocPanel: document.getElementById("flat-doc-panel"),
      chatSendBtn: document.getElementById("chat-send-btn"),
      chatSendBtnSide: document.getElementById("chat-send-btn-side"),
      chatPreviewFinalizeBtn: document.getElementById("chat-preview-finalize-btn"),
      chatPreviewFinalizeBtnSide: document.getElementById("chat-preview-finalize-btn-side"),
      chatFinalizeBtn: document.getElementById("chat-finalize-btn"),
      chatFinalizeBtnSide: document.getElementById("chat-finalize-btn-side"),
      chatFinalizeMeta: document.getElementById("chat-finalize-meta"),
      chatThread: document.getElementById("chat-thread"),
      chatHistoryMeta: document.getElementById("chat-history-meta"),
      chatMode: document.getElementById("chat-mode"),
      chatDocumentsToggle: document.getElementById("chat-documents-toggle"),
      chatEvidenceToggle: document.getElementById("chat-evidence-toggle"),
      chatStopBtn: document.getElementById("chat-stop-btn"),
      chatCountsQuickBtn: document.getElementById("chat-counts-quick-btn"),
      chatDocsQuickBtn: document.getElementById("chat-docs-quick-btn"),
      chatModel: document.getElementById("chat-model"),
      chatBranch: document.getElementById("chat-branch"),
      chatInput: document.getElementById("chat-input"),
      chatImportPath: document.getElementById("chat-import-path"),
      chatImportBtn: document.getElementById("chat-import-btn"),
      chatStatDays: document.getElementById("chat-stat-days"),
      chatStatMessages: document.getElementById("chat-stat-messages"),
      chatStatCitations: document.getElementById("chat-stat-citations"),
      chatStatNotes: document.getElementById("chat-stat-notes"),
      chatStatRelations: document.getElementById("chat-stat-relations"),
      chatMemoryRoot: document.getElementById("chat-memory-root"),
      treeControlsRefreshBtn: document.getElementById("tree-controls-refresh-btn"),
      treeControlsSaveBtn: document.getElementById("tree-controls-save-btn"),
      treeControlsResetBtn: document.getElementById("tree-controls-reset-btn"),
      treeControlsExportBtn: document.getElementById("tree-controls-export-btn"),
      treeControlsImportBtn: document.getElementById("tree-controls-import-btn"),
      treeControlsImportFile: document.getElementById("tree-controls-import-file"),
      treeControlsValidateBtn: document.getElementById("tree-controls-validate-btn"),
      treeControlsGrid: document.getElementById("tree-controls-grid"),
      symbolPolicyGrid: document.getElementById("symbol-policy-grid"),
      symbolPolicySaveBtn: document.getElementById("symbol-policy-save-btn"),
      treeDiagnosticsRunBtn: document.getElementById("tree-diagnostics-run-btn"),
      treeDiagnosticsLoadBtn: document.getElementById("tree-diagnostics-load-btn"),
      treeDiagnosticsPanel: document.getElementById("tree-diagnostics-panel"),
      tracerRefreshBtn: document.getElementById("tracer-refresh-btn"),
      tracerCopyBtn: document.getElementById("tracer-copy-btn"),
      tracerDownloadBtn: document.getElementById("tracer-download-btn"),
      tracerClearBtn: document.getElementById("tracer-clear-btn"),
      tracerFilter: document.getElementById("tracer-filter"),
      tracerCapturePayloads: document.getElementById("tracer-capture-payloads"),
      tracerOutput: document.getElementById("tracer-output"),
      tracerStatEvents: document.getElementById("tracer-stat-events"),
      tracerStatApi: document.getElementById("tracer-stat-api"),
      tracerStatErrors: document.getElementById("tracer-stat-errors"),
      tracerSessionId: document.getElementById("tracer-session-id"),
    };
  },

  bind() {
    this.initTracer();
    this.els.tabLexicon.addEventListener("click", () => this.showTab("lexicon"));
    this.els.tabIntake.addEventListener("click", () => this.showTab("intake"));
    this.els.tabChat.addEventListener("click", () => this.showTab("chat"));
    this.els.tabTreeBrain.addEventListener("click", () => this.showTab("treeBrain"));
    this.els.tabTracer.addEventListener("click", () => this.showTab("tracer"));
    document.querySelectorAll(".pill").forEach((btn) => {
      btn.addEventListener("click", () => this.setPack(btn.dataset.pack));
    });
    this.els.searchBtn.addEventListener("click", () => this.search());
    this.els.resetBtn.addEventListener("click", () => this.resetSearch());
    this.els.mappingBtn.addEventListener("click", () => this.runMappingBuild());
    this.els.observedMapsBtn.addEventListener("click", () => this.showObservedMaps());
    document.getElementById("top-btn").addEventListener("click", () => this.showTop());
    document.getElementById("random-btn").addEventListener("click", () => this.showRandom());
    document.getElementById("recent-btn").addEventListener("click", () => this.showRecent());
    document.getElementById("files-btn").addEventListener("click", () => this.showFiles());
    document.getElementById("unmatched-btn").addEventListener("click", () => this.showUnmatched());
    document.getElementById("pending-btn").addEventListener("click", () => this.showPending());
    document.getElementById("ignored-btn").addEventListener("click", () => this.showIgnored());
    document.getElementById("clear-btn").addEventListener("click", () => this.clearCanonical());
    document.getElementById("return-btn").addEventListener("click", () => this.returnToPool());
    document.getElementById("import-btn").addEventListener("click", () => this.importWords());
    this.els.intakeAddBtn.addEventListener("click", () => this.els.intakeFileInput.click());
    this.els.intakeFileInput.addEventListener("change", () => {
      const file = this.els.intakeFileInput.files && this.els.intakeFileInput.files[0];
      if (file) this.loadIntakeDocument(file);
    });
    this.els.intakeUniqueFilter.addEventListener("input", () => this.renderIntakeUniqueList());
    this.els.intakeMissingFilter.addEventListener("input", () => this.renderIntakeMissingList());
    this.els.intakeSelectVisibleBtn.addEventListener("click", () => this.selectVisibleMissingAnchors());
    this.els.intakeApproveSelectedBtn.addEventListener("click", () => this.approveSelectedMissingAnchors());
    this.els.intakeBulkApproveBtn.addEventListener("click", () => this.approveAllMissingAnchors());
    this.els.intakeMapBtn.addEventListener("click", () => this.runIntakeMapping());
    this.els.chatArchiveBtn.addEventListener("click", () => this.loadChatArchiveIntake());
    this.els.chatRefreshBtn.addEventListener("click", () => this.refreshChatMemory());
    this.els.clearSpeakStatusBtn.addEventListener("click", () => this.refreshClearSpeakStatus());
    this.els.clearSpeakStatusBtnSide.addEventListener("click", () => this.refreshClearSpeakStatus());
    this.els.clearSpeakQueryBtn.addEventListener("click", () => this.runClearSpeakQuery());
    this.els.clearSpeakRemixBtn.addEventListener("click", () => this.runClearSpeakRemix());
    this.els.flatDocRefreshBtn.addEventListener("click", () => this.refreshFlatDocuments());
    this.els.flatDocAnchorizeBtn.addEventListener("click", () => this.anchorizeSelectedFlatDocument());
    this.els.flatDocAnchorizeAllBtn.addEventListener("click", () => this.anchorizeAllFlatDocuments());
    this.els.chatSendBtn.addEventListener("click", () => this.sendChatMessage());
    this.els.chatSendBtnSide.addEventListener("click", () => this.sendChatMessage());
    this.els.chatStopBtn.addEventListener("click", () => this.stopChatResponse());
    this.els.chatEvidenceToggle.addEventListener("change", () => this.renderChatEvidenceToggleLabel());
    this.els.chatCountsQuickBtn.addEventListener("click", () => this.setChatEvidenceMode(false));
    this.els.chatDocsQuickBtn.addEventListener("click", () => this.setChatEvidenceMode(true));
    this.els.chatPreviewFinalizeBtn.addEventListener("click", () => this.previewChatFinalize());
    this.els.chatPreviewFinalizeBtnSide.addEventListener("click", () => this.previewChatFinalize());
    this.els.chatFinalizeBtn.addEventListener("click", () => this.finalizeChatCounts());
    this.els.chatFinalizeBtnSide.addEventListener("click", () => this.finalizeChatCounts());
    this.els.chatImportBtn.addEventListener("click", () => this.importChatArchive());
    this.els.treeControlsRefreshBtn.addEventListener("click", () => this.loadTreeBrainControls());
    this.els.treeControlsSaveBtn.addEventListener("click", () => this.saveTreeBrainControls());
    this.els.treeControlsResetBtn.addEventListener("click", () => this.resetTreeBrainControls());
    this.els.treeControlsExportBtn.addEventListener("click", () => this.exportTreeBrainConfig());
    this.els.treeControlsImportBtn.addEventListener("click", () => this.els.treeControlsImportFile.click());
    this.els.treeControlsImportFile.addEventListener("change", () => this.importTreeBrainConfig());
    this.els.treeControlsValidateBtn.addEventListener("click", () => this.validateTreeBrainControls());
    this.els.symbolPolicySaveBtn.addEventListener("click", () => this.saveSymbolPolicy());
    this.els.treeDiagnosticsRunBtn.addEventListener("click", () => this.runTreeDiagnostics());
    this.els.treeDiagnosticsLoadBtn.addEventListener("click", () => this.loadLatestTreeDiagnostics());
    this.els.tracerRefreshBtn.addEventListener("click", () => this.renderTracer());
    this.els.tracerCopyBtn.addEventListener("click", () => this.copyTracerJson());
    this.els.tracerDownloadBtn.addEventListener("click", () => this.downloadTracerJson());
    this.els.tracerClearBtn.addEventListener("click", () => this.clearTracer());
    this.els.tracerFilter.addEventListener("input", () => this.renderTracer());
    this.els.tracerCapturePayloads.addEventListener("change", () => {
      this.traceEvent("tracer.capture_payloads_changed", { enabled: this.els.tracerCapturePayloads.checked });
    });
    this.els.chatInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && event.ctrlKey) {
        event.preventDefault();
        this.sendChatMessage();
      }
    });
    this.els.chatThread.addEventListener("click", (event) => this.handleWorkbenchActionClick(event));
    document.getElementById("detail-close").addEventListener("click", () => {
      this.els.detailCard.classList.remove("active");
    });
    this.els.searchInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        this.search();
      }
    });
    this.els.searchInput.addEventListener("input", () => {
      clearTimeout(this.searchTimer);
      this.searchTimer = setTimeout(() => this.search(), 200);
    });
  },

  showTab(tab) {
    const intakeActive = tab === "intake";
    const chatActive = tab === "chat";
    const treeBrainActive = tab === "treeBrain";
    const tracerActive = tab === "tracer";
    this.traceEvent("ui.tab", { tab });
    this.els.tabLexicon.classList.toggle("active", !intakeActive && !chatActive && !treeBrainActive && !tracerActive);
    this.els.tabIntake.classList.toggle("active", intakeActive);
    this.els.tabChat.classList.toggle("active", chatActive);
    this.els.tabTreeBrain.classList.toggle("active", treeBrainActive);
    this.els.tabTracer.classList.toggle("active", tracerActive);
    this.els.lexiconTab.classList.toggle("active", !intakeActive && !chatActive && !treeBrainActive && !tracerActive);
    this.els.intakeTab.classList.toggle("active", intakeActive);
    this.els.chatTab.classList.toggle("active", chatActive);
    this.els.treeBrainTab.classList.toggle("active", treeBrainActive);
    this.els.tracerTab.classList.toggle("active", tracerActive);
    if (intakeActive || chatActive || treeBrainActive || tracerActive) {
      this.clearBanner();
    }
    if (chatActive) {
      this.refreshChatMemory();
    }
    if (treeBrainActive) {
      this.loadTreeBrainControls();
      this.loadLatestTreeDiagnostics();
    }
    if (tracerActive) {
      this.renderTracer();
    }
  },

  async api(path, options = {}) {
    const method = String(options.method || "GET").toUpperCase();
    const startedAt = performance.now();
    const requestBody = this.tracerRequestBody(options.body);
    let response = null;
    try {
      response = await fetch(path, {
        headers: { "Content-Type": "application/json" },
        ...options,
      });
    } catch (error) {
      this.traceEvent("api.network_error", {
        path,
        method,
        duration_ms: Math.round(performance.now() - startedAt),
        request: requestBody,
        error: error.message,
      });
      throw error;
    }
    let data = null;
    try {
      data = await response.json();
    } catch (_) {
      data = null;
    }
    const durationMs = Math.round(performance.now() - startedAt);
    this.traceEvent("api.call", {
      path,
      method,
      ok: response.ok,
      status: response.status,
      duration_ms: durationMs,
      request: requestBody,
      response: this.tracerCapturePayloadsEnabled() ? this.compactForTrace(data) : this.summarizePayload(data),
    });
    if (!response.ok) {
      const detail = data && data.detail;
      throw new Error(typeof detail === "string" ? detail : (detail ? JSON.stringify(detail) : `HTTP ${response.status}`));
    }
    return data;
  },

  async apiForm(path, formData) {
    const startedAt = performance.now();
    let response = null;
    try {
      response = await fetch(path, {
        method: "POST",
        body: formData,
      });
    } catch (error) {
      this.traceEvent("api.form_network_error", {
        path,
        method: "POST",
        duration_ms: Math.round(performance.now() - startedAt),
        request: { form_keys: formData ? Array.from(formData.keys()) : [] },
        error: error.message,
      });
      throw error;
    }
    let data = null;
    try {
      data = await response.json();
    } catch (_) {
      data = null;
    }
    this.traceEvent("api.form_call", {
      path,
      method: "POST",
      ok: response.ok,
      status: response.status,
      duration_ms: Math.round(performance.now() - startedAt),
      request: { form_keys: formData ? Array.from(formData.keys()) : [] },
      response: this.tracerCapturePayloadsEnabled() ? this.compactForTrace(data) : this.summarizePayload(data),
    });
    if (!response.ok) {
      const detail = data && data.detail;
      throw new Error(typeof detail === "string" ? detail : (detail ? JSON.stringify(detail) : `HTTP ${response.status}`));
    }
    return data;
  },

  setBanner(kind, message) {
    this.els.banner.className = `status-banner ${kind}`;
    this.els.banner.textContent = message;
    this.traceEvent("ui.banner", { kind, message });
  },

  clearBanner() {
    this.els.banner.className = "status-banner";
    this.els.banner.textContent = "";
  },

  initTracer() {
    if (!this.tracer.sessionId) {
      this.tracer.sessionId = `ui_trace_${new Date().toISOString().replace(/[:.]/g, "-")}`;
    }
    this.els.tracerSessionId.textContent = this.tracer.sessionId;
    window.addEventListener("error", (event) => {
      this.traceEvent("browser.error", {
        message: event.message,
        source: event.filename,
        line: event.lineno,
        column: event.colno,
      });
    });
    window.addEventListener("unhandledrejection", (event) => {
      this.traceEvent("browser.unhandled_rejection", {
        reason: event.reason && event.reason.message ? event.reason.message : String(event.reason || ""),
      });
    });
    this.traceEvent("tracer.started", {
      user_agent: navigator.userAgent,
      location: window.location.href,
    });
  },

  traceEvent(type, payload = {}) {
    if (!this.tracer || !this.tracer.events) return;
    const event = {
      seq: ++this.tracer.sequence,
      timestamp: new Date().toISOString(),
      type,
      payload: this.compactForTrace(payload),
    };
    this.tracer.events.push(event);
    if (this.tracer.events.length > this.tracer.maxEvents) {
      this.tracer.events.splice(0, this.tracer.events.length - this.tracer.maxEvents);
    }
    if (this.els && this.els.tracerOutput) {
      this.renderTracerStats();
      if (this.els.tracerTab && this.els.tracerTab.classList.contains("active")) {
        this.renderTracer();
      }
    }
  },

  tracerCapturePayloadsEnabled() {
    return !this.els || !this.els.tracerCapturePayloads || this.els.tracerCapturePayloads.checked;
  },

  tracerRequestBody(body) {
    if (!body) return null;
    if (typeof body !== "string") return this.summarizePayload(body);
    try {
      return this.tracerCapturePayloadsEnabled() ? this.compactForTrace(JSON.parse(body)) : this.summarizePayload(JSON.parse(body));
    } catch (_) {
      return this.clipTraceString(body);
    }
  },

  compactForTrace(value, depth = 0) {
    if (value == null) return value;
    if (typeof value === "string") return this.clipTraceString(value);
    if (typeof value === "number" || typeof value === "boolean") return value;
    if (Array.isArray(value)) {
      const rows = value.slice(0, 30).map((item) => this.compactForTrace(item, depth + 1));
      if (value.length > 30) rows.push({ clipped_items: value.length - 30 });
      return rows;
    }
    if (typeof value === "object") {
      if (depth >= 5) return this.summarizePayload(value);
      const result = {};
      Object.entries(value).slice(0, 60).forEach(([key, item]) => {
        result[key] = this.compactForTrace(item, depth + 1);
      });
      const extra = Object.keys(value).length - Object.keys(result).length;
      if (extra > 0) result.__clipped_keys = extra;
      return result;
    }
    return String(value);
  },

  summarizePayload(value) {
    if (value == null) return value;
    if (typeof value === "string") return { type: "string", length: value.length, preview: this.clipTraceString(value, 200) };
    if (Array.isArray(value)) return { type: "array", length: value.length };
    if (typeof value === "object") return { type: "object", keys: Object.keys(value).slice(0, 30) };
    return value;
  },

  clipTraceString(value, limit = 4000) {
    const text = String(value || "");
    if (text.length <= limit) return text;
    return `${text.slice(0, limit)}... [clipped ${text.length - limit} chars]`;
  },

  tracerPayload() {
    return {
      tracer_version: "ui_tracer@1",
      session_id: this.tracer.sessionId,
      exported_at: new Date().toISOString(),
      branch: this.els.chatBranch ? this.els.chatBranch.value : "",
      location: window.location.href,
      event_count: this.tracer.events.length,
      events: this.tracer.events,
    };
  },

  renderTracerStats() {
    if (!this.els.tracerStatEvents) return;
    const apiCount = this.tracer.events.filter((event) => event.type.startsWith("api.")).length;
    const errorCount = this.tracer.events.filter((event) => event.type.includes("error") || event.type.includes("failed") || (event.payload && event.payload.ok === false)).length;
    this.els.tracerStatEvents.textContent = Number(this.tracer.events.length || 0).toLocaleString();
    this.els.tracerStatApi.textContent = Number(apiCount || 0).toLocaleString();
    this.els.tracerStatErrors.textContent = Number(errorCount || 0).toLocaleString();
    this.els.tracerSessionId.textContent = this.tracer.sessionId;
  },

  renderTracer() {
    this.renderTracerStats();
    const filter = String((this.els.tracerFilter && this.els.tracerFilter.value) || "").trim().toLowerCase();
    const payload = this.tracerPayload();
    const events = filter
      ? payload.events.filter((event) => JSON.stringify(event).toLowerCase().includes(filter))
      : payload.events;
    this.els.tracerOutput.textContent = JSON.stringify({ ...payload, events, filtered_event_count: events.length }, null, 2);
  },

  async copyTracerJson() {
    const text = JSON.stringify(this.tracerPayload(), null, 2);
    try {
      await navigator.clipboard.writeText(text);
      this.setBanner("success", "Tracer JSON copied to clipboard.");
    } catch (_) {
      this.els.tracerOutput.textContent = text;
      this.setBanner("info", "Clipboard was blocked. Tracer JSON is shown in the Tracer tab.");
    }
  },

  downloadTracerJson() {
    const text = JSON.stringify(this.tracerPayload(), null, 2);
    const blob = new Blob([text], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${this.tracer.sessionId}.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    this.setBanner("success", "Tracer JSON download prepared.");
  },

  clearTracer() {
    if (!confirm("Clear the current browser-side trace buffer? This does not change AnchorWorks state.")) return;
    this.tracer.events = [];
    this.tracer.sequence = 0;
    this.traceEvent("tracer.cleared", { session_id: this.tracer.sessionId });
    this.renderTracer();
  },

  async loadHealth() {
    const data = await this.api("/api/health");
    this.els.dataRoot.textContent = data.data_root || "Unknown";
  },

  async refreshStats() {
    const data = await this.api("/api/lexicon/distribution");
    this.els.statTotal.textContent = (data.total || 0).toLocaleString();
    this.els.statCanonical.textContent = (data.canonical || 0).toLocaleString();
    this.els.statSpare.textContent = (data.spare_slots || 0).toLocaleString();
    this.renderChart(data.letters || {});
    await this.refreshQueues();
  },

  async refreshChatMemory() {
    try {
      const branch = (this.els.chatBranch.value || "main").trim() || "main";
      const [status, history] = await Promise.all([
        this.api("/api/chat/status"),
        this.api(`/api/chat/history?branch=${encodeURIComponent(branch)}&limit=200`),
      ]);
      this.els.chatStatDays.textContent = Number(status.chat_days || 0).toLocaleString();
      this.els.chatStatMessages.textContent = Number(status.chat_messages || 0).toLocaleString();
      this.els.chatStatCitations.textContent = Number(status.citations || 0).toLocaleString();
      this.els.chatStatNotes.textContent = Number(status.notes || 0).toLocaleString();
      this.els.chatStatRelations.textContent = Number((status.clearspeak || {}).unique_relations || 0).toLocaleString();
      this.els.chatMemoryRoot.textContent = status.root || "-";
      const modelStatus = status.model_api || {};
      if (modelStatus.default_model) {
        this.els.chatModel.placeholder = `Default: ${modelStatus.default_model}`;
      }
      this.renderChatHistory(history);
    } catch (error) {
      this.setBanner("error", `Chat memory refresh failed: ${error.message}`);
    }
  },

  async refreshClearSpeakStatus() {
    const buttons = [this.els.clearSpeakStatusBtn, this.els.clearSpeakStatusBtnSide];
    buttons.forEach((button) => {
      button.disabled = true;
      button.dataset.originalText = button.textContent;
      button.textContent = "Checking...";
    });
    try {
      const status = await this.api("/api/clearspeak/status");
      this.renderClearSpeakStatus(status);
      this.setBanner("success", "ClearSpeak status loaded. Read-only check complete.");
    } catch (error) {
      this.setBanner("error", `ClearSpeak status failed: ${error.message}`);
    } finally {
      buttons.forEach((button) => {
        button.disabled = false;
        button.textContent = button.dataset.originalText || "ClearSpeak Status";
      });
    }
  },

  renderClearSpeakStatus(status) {
    this.traceEvent("clearspeak.status.rendered", {
      ingest_events: status.ingest_events,
      unique_relations: status.unique_relations,
      anchor_count: status.anchor_count,
      relation_rows: status.relation_rows,
    });
    const rows = [
      ["Name", status.name || "ClearSpeak"],
      ["Ingest events", Number(status.ingest_events || 0).toLocaleString()],
      ["Unique relations", Number(status.unique_relations || 0).toLocaleString()],
      ["Total observations", Number(status.total_relation_observations || 0).toLocaleString()],
      ["Anchor count", Number(status.anchor_count || 0).toLocaleString()],
      ["Relation rows", Number(status.relation_rows || 0).toLocaleString()],
      ["Counts path", status.counts_path || "-"],
    ];
    this.els.chatStatRelations.textContent = Number(status.unique_relations || 0).toLocaleString();
    this.els.clearSpeakStatusPanel.innerHTML = rows.map(([label, value]) => `
      <div class="clearspeak-status-row">
        <span>${this.escape(label)}</span>
        <strong>${this.escape(value)}</strong>
      </div>
    `).join("");
  },

  async runClearSpeakQuery() {
    const query = this.els.clearSpeakQueryInput.value.trim();
    if (!query) {
      this.setBanner("error", "Enter a ClearSpeak query first.");
      this.els.clearSpeakQueryInput.focus();
      return;
    }
    const button = this.els.clearSpeakQueryBtn;
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "Querying...";
    try {
      const result = await this.api("/api/clearspeak/query", {
        method: "POST",
        body: JSON.stringify({ query, limit: 6, evidence_mode: this.directClearSpeakEvidenceMode() }),
      });
      this.renderClearSpeakQuery(result);
      this.setBanner("success", "ClearSpeak query returned read-only evidence.");
    } catch (error) {
      this.setBanner("error", `ClearSpeak query failed: ${error.message}`);
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  },

  directClearSpeakEvidenceMode() {
    const mode = String((this.els.chatMode && this.els.chatMode.value) || "clearspeak").toLowerCase();
    if (mode === "clearspeak" && this.els.chatDocumentsToggle && !this.els.chatDocumentsToggle.checked) return "counts";
    if (mode === "counts" || mode === "count") return "counts";
    if (["documents", "document", "maps", "mapped", "mapped_documents", "clearspeak"].includes(mode)) return "documents";
    return "auto";
  },

  setChatEvidenceMode(documentsOn) {
    this.els.chatDocumentsToggle.checked = Boolean(documentsOn);
    this.els.chatMode.value = "clearspeak";
    this.setBanner("info", documentsOn ? "Main chat will use documents/maps first, then counts fallback." : "Main chat is now strict counts-only.");
    this.els.chatInput.focus();
  },

  renderChatEvidenceToggleLabel() {
    if (!this.els.chatEvidenceToggle) return;
    const label = this.els.chatEvidenceToggle.closest("label");
    const span = label ? label.querySelector("span") : null;
    if (span) {
      span.textContent = this.els.chatEvidenceToggle.checked ? "Evidence On" : "Evidence Off";
    }
  },

  selectedChatMode() {
    const mode = String((this.els.chatMode && this.els.chatMode.value) || "clearspeak").toLowerCase();
    if (mode === "clearspeak" && this.els.chatDocumentsToggle && !this.els.chatDocumentsToggle.checked) {
      return "counts";
    }
    return mode;
  },

  evidenceLaneInfo(mode, engine = "") {
    const rawMode = String(mode || "").toLowerCase();
    const rawEngine = String(engine || "").toLowerCase();
    if (rawMode.includes("count") || rawEngine.includes("count") || rawEngine.includes("lifetime")) {
      return { label: "Counts Only", className: "counts", title: "Count-only positional evidence. No document/map fallback." };
    }
    if (rawMode.includes("document") || rawMode.includes("map") || rawEngine.includes("tree_brain") || rawEngine.includes("document")) {
      return { label: "Docs / Maps", className: "documents", title: "Source-local document/map evidence may be used." };
    }
    if (rawMode === "auto") {
      return { label: "Auto Lane", className: "auto", title: "Automatic evidence lane selection." };
    }
    if (rawEngine.includes("chat_memory")) {
      return { label: "Conversation", className: "memory", title: "Conversation/memory context, not answer assembly evidence." };
    }
    return { label: "Evidence Lane Unknown", className: "unknown", title: "No evidence lane was returned." };
  },

  evidenceLaneBadge(mode, engine = "") {
    const info = this.evidenceLaneInfo(mode, engine);
    return `<span class="evidence-lane-badge ${info.className}" title="${this.escape(info.title)}">${this.escape(info.label)}</span>`;
  },

  renderClearSpeakQuery(result) {
    this.traceEvent("clearspeak.query.rendered", {
      query: result.query,
      engine: result.engine,
      evidence_mode: result.evidence_mode,
      represented_anchors: result.represented_anchors || [],
      missing_anchors: result.missing_anchors || [],
      evidence_count: (result.evidence || []).length,
      citation_count: (result.citations || []).length,
      response: result.response || result.speech || "",
    });
    const evidence = result.evidence || [];
    const citations = result.citations || [];
    const represented = result.represented_anchors || [];
    const missing = result.missing_anchors || [];
    const evidenceHtml = evidence.length
      ? evidence.map((row) => {
          const neighbors = row.neighbors || [];
          const neighborHtml = neighbors.length
            ? neighbors.map((item) => `
                <span class="clearspeak-evidence-pill">${this.escape(item.anchor || "")} (${Number(item.observations || 0).toLocaleString()})</span>
              `).join("")
            : `<span class="muted">No neighbors recorded.</span>`;
          return `
            <div class="clearspeak-evidence-card">
              <div class="clearspeak-evidence-title">${this.escape(row.anchor || "")}</div>
              <div class="clearspeak-evidence-pills">${neighborHtml}</div>
            </div>
          `;
        }).join("")
      : `<div class="empty-panel">No lifetime evidence found for represented anchors.</div>`;
    const citationHtml = citations.length
      ? citations.map((cite) => `<span class="chat-cite-pill">${this.escape(cite.coord || cite.source || "citation")}</span>`).join("")
      : `<span class="muted">No citation coordinates returned.</span>`;
    const speech = result.speech || result.response || "";
    const laneBadge = this.evidenceLaneBadge(result.evidence_mode, result.engine);
    this.els.clearSpeakQueryPanel.innerHTML = `
      <div class="clearspeak-speech-card">
        <div class="clearspeak-query-section-label">ClearSpeak Says ${laneBadge}</div>
        <div class="clearspeak-speech-text">${this.escape(speech)}</div>
      </div>
      <div class="clearspeak-query-response">${this.escape(result.response || "")}</div>
      <div class="clearspeak-query-meta">
        <strong>Represented:</strong> ${this.escape(represented.join(", ") || "none")}
      </div>
      <div class="clearspeak-query-meta">
        <strong>Missing:</strong> ${this.escape(missing.join(", ") || "none")}
      </div>
      <div class="clearspeak-query-section-label">Evidence</div>
      ${evidenceHtml}
      <div class="clearspeak-query-section-label">Coordinates</div>
      <div class="chat-citation-row">${citationHtml}</div>
    `;
  },

  async runClearSpeakRemix() {
    const query = this.els.clearSpeakQueryInput.value.trim();
    if (!query) {
      this.setBanner("error", "Enter a ClearSpeak query to remix first.");
      this.els.clearSpeakQueryInput.focus();
      return;
    }
    const button = this.els.clearSpeakRemixBtn;
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "Remixing...";
    try {
      const result = await this.api("/api/clearspeak/remix", {
        method: "POST",
        body: JSON.stringify({ query, top_k: 4, max_variants: 8, evaluate: true }),
      });
      this.renderClearSpeakRemix(result);
      if (result.blocked) {
        this.setBanner("error", "Query remix blocked by input mode. Use a focused question to remix.");
      } else {
        this.setBanner("success", "Query remix returned read-only variants.");
      }
    } catch (error) {
      this.setBanner("error", `Query remix failed: ${error.message}`);
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  },

  renderClearSpeakRemix(result) {
    this.traceEvent("clearspeak.remix.rendered", {
      query: result.query,
      blocked: Boolean(result.blocked),
      variant_count: (result.variants || []).length,
      winner: result.winner || null,
      query_boundary: result.query_boundary || null,
    });
    if (result.blocked) {
      const boundary = result.query_boundary || {};
      this.els.clearSpeakRemixPanel.innerHTML = `
        <div class="clearspeak-speech-card">
          <div class="clearspeak-query-section-label">Query Remix Blocked</div>
          <div class="clearspeak-speech-text">${this.escape(result.speech || boundary.safe_response || "QueryRemixer did not run.")}</div>
        </div>
        <div class="clearspeak-query-meta"><strong>Original:</strong> ${this.escape(result.query || "")}</div>
        <div class="clearspeak-query-meta"><strong>Detected mode:</strong> ${this.escape(boundary.mode || "unknown")} <strong>Reason:</strong> ${this.escape(boundary.reason || "mode_boundary")}</div>
        <div class="clearspeak-query-meta"><strong>Contract:</strong> statement/context text stays out of answer assembly and remix experiments.</div>
      `;
      return;
    }
    const variants = result.variants || [];
    const evaluations = result.evaluations || [];
    const winner = result.winner || null;
    const evalByQuery = new Map(evaluations.map((row) => [row.remixed_query, row]));
    const variantsHtml = variants.length
      ? variants.map((variant, index) => {
          const evalRow = evalByQuery.get(variant.remixed_query) || {};
          const ops = (variant.operations || []).map((op) => `${op.type}: ${op.seed_anchor || ""} -> ${op.selected_anchor || ""} (${Number(op.observations || 0).toLocaleString()})`).join("; ");
          return `
            <div class="clearspeak-evidence-card">
              <div class="clearspeak-evidence-title">#${index + 1} ${this.escape(variant.remixed_query || "")}</div>
              <div class="clearspeak-query-meta"><strong>Remix score:</strong> ${this.escape(String(variant.score || 0))} <strong>Drift:</strong> ${this.escape(String(variant.drift || 0))}</div>
              <div class="clearspeak-query-meta"><strong>Ops:</strong> ${this.escape(ops || "none")}</div>
              ${evalRow.speech ? `<div class="clearspeak-speech-text">${this.escape(evalRow.speech)}</div>` : ""}
              ${evalRow.score !== undefined ? `<div class="clearspeak-query-meta"><strong>Evaluation score:</strong> ${this.escape(String(evalRow.score))} <strong>Engine:</strong> ${this.escape(evalRow.engine || "")}</div>` : ""}
            </div>
          `;
        }).join("")
      : `<div class="empty-panel">No remix variants could be formed from current count evidence.</div>`;
    const winnerHtml = winner
      ? `<div class="clearspeak-speech-card"><div class="clearspeak-query-section-label">Remix Winner ${this.evidenceLaneBadge(winner.evidence_mode, winner.engine)}</div><div class="clearspeak-speech-text">${this.escape(winner.remixed_query || "")}</div><div class="clearspeak-query-meta">${this.escape(winner.speech || "")}</div></div>`
      : "";
    this.els.clearSpeakRemixPanel.innerHTML = `
      <div class="clearspeak-speech-card">
        <div class="clearspeak-query-section-label">Query Remix Experiment</div>
        <div class="clearspeak-speech-text">Original query stays sacred. Remixes are read-only count-neighbor experiments.</div>
      </div>
      <div class="clearspeak-query-meta"><strong>Original:</strong> ${this.escape(result.query || "")}</div>
      <div class="clearspeak-query-meta"><strong>Content anchors:</strong> ${this.escape((result.content_anchors || []).join(", ") || "none")}</div>
      ${winnerHtml}
      <div class="clearspeak-query-section-label">Variants</div>
      ${variantsHtml}
    `;
  },

  async refreshFlatDocuments() {
    const button = this.els.flatDocRefreshBtn;
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "Refreshing...";
    try {
      const data = await this.api("/api/lexicon/flat-documents");
      this.renderFlatDocuments(data);
      this.setBanner("success", "Flat document inventory loaded.");
    } catch (error) {
      this.setBanner("error", `Flat document refresh failed: ${error.message}`);
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  },

  renderFlatDocuments(data) {
    const rawFiles = data.raw_files || [];
    const symbolicFiles = data.symbolic_files || [];
    const rawHtml = rawFiles.length
      ? rawFiles.map((file) => `
          <button class="flat-doc-row" type="button" onclick="lexApp.pickFlatDocument('${this.escapeAttr(file.name || "")}')">
            <strong>${this.escape(file.name || "")}</strong>
            <span>${Number(file.size_bytes || 0).toLocaleString()} bytes</span>
          </button>
        `).join("")
      : `<div class="empty-panel">No raw flat documents found.</div>`;
    const symbolicHtml = symbolicFiles.length
      ? symbolicFiles.map((file) => `
          <div class="flat-doc-row static">
            <strong>${this.escape(file.name || "")}</strong>
            <span>${Number(file.total_anchor_observations || 0).toLocaleString()} observations, ${Number(file.unique_anchor_count || 0).toLocaleString()} unique anchors</span>
          </div>
        `).join("")
      : `<div class="empty-panel">No symbolic flat documents generated yet.</div>`;
    this.els.flatDocPanel.innerHTML = `
      <div class="clearspeak-query-meta"><strong>Raw root:</strong> ${this.escape(data.raw_root || "")}</div>
      <div class="clearspeak-query-meta"><strong>Symbolic root:</strong> ${this.escape(data.symbolic_root || "")}</div>
      <div class="clearspeak-query-section-label">Raw Files</div>
      <div class="flat-doc-list">${rawHtml}</div>
      <div class="clearspeak-query-section-label">Symbolic Files</div>
      <div class="flat-doc-list">${symbolicHtml}</div>
    `;
  },

  pickFlatDocument(name) {
    this.els.flatDocName.value = name || "";
  },

  async anchorizeSelectedFlatDocument() {
    const name = this.els.flatDocName.value.trim();
    if (!name) {
      this.setBanner("error", "Enter or select a raw flat document filename first.");
      this.els.flatDocName.focus();
      return;
    }
    const button = this.els.flatDocAnchorizeBtn;
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "Anchorizing...";
    try {
      const result = await this.api("/api/lexicon/flat-documents/anchorize", {
        method: "POST",
        body: JSON.stringify({ name }),
      });
      this.setBanner("success", `Anchorized flat document: ${result.saved_document_name || name}`);
      await this.refreshFlatDocuments();
    } catch (error) {
      this.setBanner("error", `Flat document anchorize blocked: ${error.message}`);
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  },

  async anchorizeAllFlatDocuments() {
    if (!confirm("Anchorize all raw flat documents? This is representation-only and does not write maps, counts, lifetime, or lexicon.")) return;
    const button = this.els.flatDocAnchorizeAllBtn;
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "Anchorizing all...";
    try {
      const result = await this.api("/api/lexicon/flat-documents/anchorize-all", { method: "POST" });
      const message = `${Number(result.anchorized_count || 0).toLocaleString()} anchorized, ${Number(result.error_count || 0).toLocaleString()} blocked.`;
      this.setBanner(result.error_count ? "error" : "success", message);
      await this.refreshFlatDocuments();
    } catch (error) {
      this.setBanner("error", `Flat document anchorize-all failed: ${error.message}`);
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  },

  renderChatHistory(history) {
    const messages = history.messages || [];
    this.traceEvent("chat.history.rendered", {
      day: history.day || "today",
      branch: history.branch || "main",
      message_count: messages.length,
      citation_blocks: Object.keys(history.citations_by_block || {}).length,
    });
    this.els.chatHistoryMeta.textContent = `${history.day || "today"} - ${history.branch || "main"} - ${messages.length.toLocaleString()} messages`;
    if (!messages.length) {
      this.els.chatThread.innerHTML = `<div class="empty-panel">No messages on this branch yet.</div>`;
      return;
    }

    const citationsByBlock = history.citations_by_block || {};
    this.els.chatThread.innerHTML = messages.map((message) => this.renderChatMessage(message, citationsByBlock)).join("");
    this.els.chatThread.scrollTop = this.els.chatThread.scrollHeight;
  },

  renderChatMessage(message, citationsByBlock) {
    const sender = String(message.sender || "system").toLowerCase();
    const roleClass = sender === "user" ? "user" : sender === "assistant" ? "assistant" : "system";
    const messageId = message.message_uuid || message.id || "";
    const blockKey = `${messageId}:b0`;
    const citations = citationsByBlock[blockKey] || [];
    const modelIdentity = message.model_identity || {};
    const evidenceBadge = sender === "assistant"
      ? this.evidenceLaneBadge(modelIdentity.evidence_mode || "", modelIdentity.evidence_engine || modelIdentity.engine || message.actor || "")
      : "";
    const citationHtml = citations.length
      ? `<div class="chat-citation-row">${citations.map((cite) => `<span class="chat-cite-pill">${this.escape(cite.coord || cite.cite_id || "cite")}</span>`).join("")}</div>`
      : "";
    const workbenchHtml = sender === "assistant" ? this.renderWorkbenchActions(message.workbench || {}) : "";
    return `
      <article class="chat-message ${roleClass}">
        <div class="chat-message-head">
          <span>${this.escape(message.sender || "system")} - ${this.escape(message.actor || "")} ${evidenceBadge}</span>
          <span>${this.escape(message.timestamp || "")}</span>
        </div>
        <div class="chat-message-body">${this.escape(message.content || "")}</div>
        ${citationHtml}
        ${workbenchHtml}
      </article>
    `;
  },

  renderWorkbenchActions(workbench) {
    const actions = Array.isArray(workbench.actions) ? workbench.actions : [];
    if (!actions.length) return "";
    const workflow = workbench.workflow || {};
    const workflowId = workflow.workflow_id || "";
    const buttons = actions.map((action) => {
      const id = action.id || "";
      const label = action.label || id || "Action";
      return `<button class="mini-btn chat-workbench-action" type="button" data-workflow-id="${this.escape(workflowId)}" data-action-id="${this.escape(id)}">${this.escape(label)}</button>`;
    }).join("");
    return `<div class="chat-workbench-actions">${buttons}</div>`;
  },

  handleWorkbenchActionClick(event) {
    const button = event.target && event.target.closest ? event.target.closest(".chat-workbench-action") : null;
    if (!button) return;
    const actionId = button.dataset.actionId || "";
    if (actionId === "show_evidence") {
      this.els.chatEvidenceToggle.checked = true;
      this.renderChatEvidenceToggleLabel();
      this.setBanner("info", "Evidence details will be shown on the next response.");
      return;
    }
    if (actionId === "hide_evidence") {
      this.els.chatEvidenceToggle.checked = false;
      this.renderChatEvidenceToggleLabel();
      this.setBanner("info", "Evidence details will be hidden on the next response.");
      return;
    }
    if (actionId === "continue_working") {
      this.els.chatInput.focus();
      this.setBanner("info", "Continue working selected. Ask the next step or run the next guided action.");
      return;
    }
    this.setBanner("error", `Workbench action is not wired yet: ${actionId}`);
  },

  async sendChatMessage() {
    const message = this.els.chatInput.value.trim();
    if (!message) {
      this.setBanner("error", "Enter a chat message first.");
      this.els.chatInput.focus();
      return;
    }
    const mode = this.selectedChatMode();
    const model = this.els.chatModel.value.trim();
    const branch = (this.els.chatBranch.value || "main").trim() || "main";
    const evidenceVisible = this.els.chatEvidenceToggle ? Boolean(this.els.chatEvidenceToggle.checked) : true;
    this.traceEvent("chat.send.requested", {
      branch,
      mode,
      model,
      documents_on: Boolean(this.els.chatDocumentsToggle && this.els.chatDocumentsToggle.checked),
      evidence_visible: evidenceVisible,
      message,
    });
    const buttons = [this.els.chatSendBtn, this.els.chatSendBtnSide];
    this.chatRequestController = new AbortController();
    this.els.chatStopBtn.disabled = false;
    buttons.forEach((button) => {
      button.disabled = true;
      button.dataset.originalText = button.textContent;
      button.textContent = "Sending...";
    });
    try {
      const data = await this.api("/api/chat/send", {
        method: "POST",
        signal: this.chatRequestController.signal,
        body: JSON.stringify({ message, mode, branch, model, evidence_visible: evidenceVisible }),
      });
      this.activeChatWorkflow = data.workflow || null;
      this.traceEvent("chat.send.completed", {
        branch,
        requested_mode: mode,
        returned_mode: data.mode,
        response_summary: this.summarizePayload(data),
      });
      this.els.chatInput.value = "";
      await this.refreshChatMemory();
      this.setBanner("success", `${data.mode || mode} response saved to chat memory.`);
    } catch (error) {
      if (error.name === "AbortError") {
        this.setBanner("warn", "Chat response stopped before completion.");
      } else {
        this.setBanner("error", `Chat send failed: ${error.message}`);
      }
    } finally {
      this.chatRequestController = null;
      this.els.chatStopBtn.disabled = true;
      buttons.forEach((button) => {
        button.disabled = false;
        button.textContent = button.dataset.originalText || "Send";
      });
    }
  },

  async stopChatResponse() {
    const workflow = this.activeChatWorkflow || {};
    if (this.chatRequestController) {
      this.chatRequestController.abort();
    }
    try {
      const result = await this.api("/api/chat/stop", {
        method: "POST",
        body: JSON.stringify({
          workflow_id: workflow.workflow_id || "",
          response_id: workflow.response_id || "",
        }),
      });
      this.traceEvent("chat.stop.completed", result);
    } catch (error) {
      this.traceEvent("chat.stop.failed", { error: error.message });
    } finally {
      this.els.chatStopBtn.disabled = true;
    }
  },

  async importChatArchive() {
    const archiveRoot = this.els.chatImportPath.value.trim();
    if (!archiveRoot) {
      this.setBanner("error", "Enter the old AnchorWorks archive root first.");
      this.els.chatImportPath.focus();
      return;
    }
    const button = this.els.chatImportBtn;
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "Importing...";
    try {
      const data = await this.api("/api/chat/archive/import", {
        method: "POST",
        body: JSON.stringify({ archive_root: archiveRoot }),
      });
      await this.refreshChatMemory();
      this.setBanner("success", `Imported chat archive bridge file: ${data.prepared && data.prepared.source_name ? data.prepared.source_name : "archive"}.`);
    } catch (error) {
      this.setBanner("error", `Chat archive import failed: ${error.message}`);
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  },

  async previewChatFinalize() {
    const branch = (this.els.chatBranch.value || "main").trim() || "main";
    const buttons = [this.els.chatPreviewFinalizeBtn, this.els.chatPreviewFinalizeBtnSide];
    buttons.forEach((button) => {
      button.disabled = true;
      button.dataset.originalText = button.textContent;
      button.textContent = "Previewing...";
    });
    try {
      const data = await this.api("/api/chat/finalize/preview", {
        method: "POST",
        body: JSON.stringify({ branch }),
      });
      this.els.chatFinalizeMeta.textContent =
        `${Number(data.chat_message_count || 0).toLocaleString()} messages, ` +
        `${Number(data.total_anchor_observations || 0).toLocaleString()} observations, ` +
        `${Number(data.unique_anchor_count || 0).toLocaleString()} unique anchors, ` +
        `${Number(data.missing_anchor_count || 0).toLocaleString()} missing.`;
      if (Number(data.missing_anchor_count || 0) === 0) {
        this.setBanner("success", "Chat finalize preview passed. Lexicon coverage complete; ready to update user-side counts.");
      } else {
        this.setBanner("error", `Chat finalize blocked: ${Number(data.missing_anchor_count || 0).toLocaleString()} missing anchors must be approved first.`);
      }
    } catch (error) {
      this.setBanner("error", `Chat finalize preview failed: ${error.message}`);
    } finally {
      buttons.forEach((button) => {
        button.disabled = false;
        button.textContent = button.dataset.originalText || "Preview Finalize";
      });
    }
  },

  async finalizeChatCounts() {
    const branch = (this.els.chatBranch.value || "main").trim() || "main";
    if (!confirm(`Finalize today's "${branch}" chat branch into user-side counts? This only succeeds if lexicon coverage is complete.`)) return;
    const buttons = [this.els.chatFinalizeBtn, this.els.chatFinalizeBtnSide];
    buttons.forEach((button) => {
      button.disabled = true;
      button.dataset.originalText = button.textContent;
      button.textContent = "Finalizing...";
    });
    try {
      const data = await this.api("/api/chat/finalize", {
        method: "POST",
        body: JSON.stringify({ branch }),
      });
      await this.refreshStats();
      await this.refreshChatMemory();
      this.setBanner("success", `Finalized chat into user-side counts. Saved observed map: ${data.saved_map_name || "chat map"}.`);
    } catch (error) {
      this.setBanner("error", `Chat finalize failed: ${error.message}`);
    } finally {
      buttons.forEach((button) => {
        button.disabled = false;
        button.textContent = button.dataset.originalText || "Finalize Counts";
      });
    }
  },

  renderAlphaStrip() {
    this.els.alphaStrip.innerHTML = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("").map((letter) => (
      `<button class="alpha-btn" onclick="lexApp.browseLetter('${letter}', this)">${letter}</button>`
    )).join("");
  },

  renderChart(letters) {
    const values = Object.values(letters || {});
    const max = Math.max(1, ...values);
    this.els.chart.innerHTML = Object.entries(letters || {}).map(([letter, count]) => {
      const pct = Math.max(6, (count / max) * 100);
      return `<button class="chart-bar" style="height:${pct}%;" title="${letter}: ${count.toLocaleString()}" onclick="lexApp.browseLetter('${letter}')">
        <span class="chart-bar-label">${letter}</span>
      </button>`;
    }).join("");
  },

  setPack(pack) {
    this.pack = pack || "all";
    document.querySelectorAll(".pill").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.pack === this.pack);
    });
    if (this.els.searchInput.value.trim().length >= 2) {
      this.search();
      return;
    }
    this.showRandom();
  },

  async refreshQueues() {
    try {
      const [unmatched, pending, ignored] = await Promise.all([
        this.api("/api/lexicon/unmatched?limit=1"),
        this.api("/api/lexicon/pending"),
        this.api("/api/lexicon/ignored"),
      ]);
      this.els.queueUnmatched.textContent = Number(unmatched.unmatched_total || 0).toLocaleString();
      this.els.queuePending.textContent = Number(pending.total || 0).toLocaleString();
      this.els.queueIgnored.textContent = Number(ignored.total || 0).toLocaleString();
    } catch (_) {
      this.els.queueUnmatched.textContent = "-";
      this.els.queuePending.textContent = "-";
      this.els.queueIgnored.textContent = "-";
    }
  },

  setMeta(title, text) {
    this.els.resultMetaTitle.textContent = title || "Current View";
    this.els.resultMeta.textContent = text || "";
    this.els.resultsTitle.textContent = title || "Results";
    this.els.resultsSubtitle.textContent = text || "";
  },

  resetSearch() {
    this.els.searchInput.value = "";
    this.showRandom();
  },

  setIntakeStep(label, percent, active = false, error = false) {
    this.intake.currentStep = label;
    this.els.intakeStepLabel.textContent = label;
    this.els.intakeProgressFill.style.width = `${Math.max(0, Math.min(100, percent))}%`;
    this.els.intakeSpinner.classList.toggle("active", Boolean(active));
    this.els.intakeReadyTag.textContent = error ? "error" : (percent >= 100 ? "ready" : "working");
    this.els.intakeReadyTag.classList.toggle("error", Boolean(error));
    this.els.intakeReadyTag.classList.toggle("ready", !error && percent >= 100);
  },

  async loadIntakeDocument(file) {
    this.showTab("intake");
    this.intake.file = file;
    this.intake.content = "";
    this.intake.prep = null;
    this.intake.report = null;
    this.intake.sourceName = file.name || "document";
    this.intake.sourcePath = "";
    this.intake.fileSize = file.size || 0;
    this.intake.fileType = file.type || "";
    this.intake.rejected = new Set();
    this.intake.selected = new Set();
    this.renderVisualEvidencePreview();
    this.els.intakeMapBtn.disabled = true;
    this.els.intakeBulkApproveBtn.disabled = true;
    this.els.intakeSelectVisibleBtn.disabled = true;
    this.els.intakeApproveSelectedBtn.disabled = true;
    this.els.intakeFileName.textContent = file.name || "Selected document";
    this.els.intakeFileMeta.textContent = `${this.size(file.size || 0)} - ${file.type || "unknown type"} - ${file.webkitRelativePath || file.name || ""}`;

    try {
      this.setIntakeStep("Loading document", 12, true);
      const formData = new FormData();
      formData.append("file", file, file.name || "document");
      this.setIntakeStep("Preparing document", 22, true);
      const prepared = await this.apiForm("/api/lexicon/intake/prepare", formData);
      this.intake.sourceName = prepared.source_name || file.name || "document";
      this.intake.sourcePath = prepared.source_path || file.webkitRelativePath || "";
      this.intake.fileSize = prepared.original_size || file.size || 0;
      this.intake.fileType = prepared.file_type || file.type || "";
      await this.previewPreparedIntake(prepared);
    } catch (error) {
      this.setIntakeStep(`${this.intake.currentStep} failed`, 100, false, true);
      this.setBanner("error", `${this.intake.currentStep}: ${error.message}`);
    }
  },

  async loadChatArchiveIntake() {
    const archiveRoot = this.els.chatArchivePath.value.trim();
    if (!archiveRoot) {
      this.setBanner("error", "Enter the old AnchorWorks archive root first.");
      this.els.chatArchivePath.focus();
      return;
    }

    this.showTab("intake");
    this.intake.file = null;
    this.intake.content = "";
    this.intake.prep = null;
    this.intake.report = null;
    this.intake.sourceName = "AnchorWorks chat archive";
    this.intake.sourcePath = archiveRoot;
    this.intake.fileSize = 0;
    this.intake.fileType = "anchorworks-chat-archive";
    this.intake.rejected = new Set();
    this.intake.selected = new Set();
    this.renderVisualEvidencePreview();
    this.els.intakeMapBtn.disabled = true;
    this.els.intakeBulkApproveBtn.disabled = true;
    this.els.intakeSelectVisibleBtn.disabled = true;
    this.els.intakeApproveSelectedBtn.disabled = true;
    this.els.intakeFileName.textContent = "AnchorWorks chat + memory archive";
    this.els.intakeFileMeta.textContent = archiveRoot;

    const button = this.els.chatArchiveBtn;
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "Preparing...";
    try {
      this.setIntakeStep("Loading chat archive", 12, true);
      const prepared = await this.api("/api/lexicon/intake/chat-archive/prepare", {
        method: "POST",
        body: JSON.stringify({ archive_root: archiveRoot }),
      });
      this.intake.sourceName = prepared.source_name || "AnchorWorks chat archive";
      this.intake.sourcePath = prepared.source_path || archiveRoot;
      this.intake.fileSize = prepared.original_size || 0;
      this.intake.fileType = prepared.file_type || "anchorworks-chat-archive";
      await this.previewPreparedIntake(prepared);
    } catch (error) {
      this.setIntakeStep(`${this.intake.currentStep} failed`, 100, false, true);
      this.setBanner("error", `${this.intake.currentStep}: ${error.message}`);
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  },

  async previewPreparedIntake(prepared) {
    const content = prepared.prepared_text || "";
    this.intake.content = content;
    this.intake.prep = prepared;
    this.intake.edits = [];
    this.intake.rejected = new Set();
    this.intake.selected = new Set();
    this.renderVisualEvidencePreview();
    const previewClipped = content.length > INTAKE_RAW_PREVIEW_CHAR_LIMIT;
    this.els.intakeRawPreview.textContent = previewClipped
      ? `${content.slice(0, INTAKE_RAW_PREVIEW_CHAR_LIMIT)}\n\n[Preview clipped for browser speed. Full prepared document remains loaded for intake.]`
      : content;
    const prepWarnings = (prepared.warnings || []).length ? ` - ${prepared.warnings.length} warning(s)` : "";
    const previewNote = previewClipped ? ` - showing first ${INTAKE_RAW_PREVIEW_CHAR_LIMIT.toLocaleString()} characters` : "";
    this.els.intakeRawMeta.textContent = `${prepared.converter || "prepared"} - ${Number(prepared.original_size || this.intake.fileSize || 0).toLocaleString()} bytes -> ${Number(content.length || 0).toLocaleString()} characters${previewNote}${prepWarnings}`;
    this.els.intakeFileName.textContent = prepared.source_name || this.intake.sourceName || "Prepared document";
    this.els.intakeFileMeta.textContent = `${this.size(prepared.original_size || this.intake.fileSize || 0)} - ${prepared.file_type || this.intake.fileType || "unknown type"} - ${prepared.source_path || this.intake.sourcePath || ""}`;

    if (this.isVisualIntake()) {
      const report = {
        ok: true,
        source_name: prepared.source_name || this.intake.sourceName || "visual source",
        source_path: prepared.source_path || this.intake.sourcePath || "",
        file_type: prepared.file_type || this.intake.fileType || "",
        file_size: prepared.original_size || this.intake.fileSize || content.length,
        real_lexicon_path: "visual preview only - lexicon route blocked",
        paragraph_count: 0,
        total_anchor_observations: 0,
        unique_anchor_count: 0,
        known_anchor_count: 0,
        missing_anchor_count: 0,
        known_anchor_observations: 0,
        missing_anchor_observations: 0,
        unique_anchors: [],
        missing_anchors: [],
        visual_preview_only: true,
        writes_allowed: { maps: false, counts: false, lifetime: false, lexicon: false },
        reason: "visual_intake_preview_only",
      };
      this.intake.report = report;
      this.renderIntakeReport(report);
      this.setIntakeStep("Visual evidence preview only", 100, false);
      this.setBanner("info", "Visual source recorded as preview-only evidence. Anchor approval and map/count actions are blocked until a future visual approval route exists.");
      return;
    }

    this.setIntakeStep("Extracting anchors", 28, true);
    await this.nextFrame();
    this.setIntakeStep("Building unique anchor list", 46, true);
    await this.nextFrame();
    this.setIntakeStep("Comparing against real lexicon", 64, true);
    const report = await this.api("/api/lexicon/intake/preview", {
      method: "POST",
      body: JSON.stringify({
        source_name: prepared.source_name || this.intake.sourceName || "document",
        source_path: prepared.source_path || this.intake.sourcePath || "",
        file_size: prepared.original_size || this.intake.fileSize || content.length,
        file_type: prepared.file_type || this.intake.fileType || "",
        content,
      }),
    });
    this.setIntakeStep("Preparing review list", 82, true);
    this.intake.report = report;
    this.renderIntakeReport(report);
    this.setIntakeStep("Ready for approval", 100, false);
    this.setBanner("success", `Document intake ready: ${Number(report.missing_anchor_count || 0).toLocaleString()} missing anchors need review.`);
  },

  renderIntakeReport(report) {
    const prep = this.intake.prep || {};
    const visual = this.isVisualIntake(report);
    this.els.intakeDocName.textContent = report.source_name || this.intake.sourceName || "-";
    this.els.intakeDocType.textContent = report.file_type || prep.file_type || this.intake.fileType || "unknown";
    this.els.intakeParagraphCount.textContent = Number(report.paragraph_count || 0).toLocaleString();
    this.els.intakeTotalCount.textContent = Number(report.total_anchor_observations || 0).toLocaleString();
    this.els.intakeUniqueCount.textContent = Number(report.unique_anchor_count || 0).toLocaleString();
    this.els.intakeKnownCount.textContent = Number(report.known_anchor_count || 0).toLocaleString();
    this.els.intakeMissingCount.textContent = Number(report.missing_anchor_count || 0).toLocaleString();
    this.els.intakeLexiconPath.textContent = report.real_lexicon_path || "-";
    this.els.intakeUniqueMeta.textContent = `${Number(report.unique_anchor_count || 0).toLocaleString()} anchors`;
    this.els.intakeMissingMeta.textContent = `${Number(report.missing_anchor_count || 0).toLocaleString()} anchors`;
    this.els.intakeMapBtn.disabled = visual || this.intakeUnresolvedMissingCount(report) !== 0;
    const missingAnchors = new Set((report.missing_anchors || []).map((row) => row.anchor));
    this.intake.selected = new Set([...this.intake.selected].filter((anchor) => missingAnchors.has(anchor)));
    this.intake.rejected = new Set([...this.intake.rejected].filter((anchor) => missingAnchors.has(anchor)));
    this.updateIntakeApprovalButtons();
    if (visual) {
      this.els.intakeUniqueMeta.textContent = "visual preview only - anchor route blocked";
      this.els.intakeMissingMeta.textContent = "visual preview only - approval route blocked";
    } else if (this.intakeUnresolvedMissingCount(report) === 0) {
      this.setBanner("success", "Lexicon coverage complete. Ready to map/count.");
    }
    this.renderIntakeUniqueList();
    this.renderIntakeMissingList();
  },

  visualManifest() {
    const prep = this.intake.prep || {};
    const metadata = prep.metadata || {};
    return metadata.visual_manifest || null;
  },

  visualRegionMap() {
    const prep = this.intake.prep || {};
    const metadata = prep.metadata || {};
    return metadata.visual_region_map || null;
  },

  visualRecognitionLayer() {
    const prep = this.intake.prep || {};
    const metadata = prep.metadata || {};
    return metadata.visual_recognition_layer || null;
  },

  isVisualIntake(report = null) {
    const activeReport = report || this.intake.report || {};
    return Boolean(this.visualManifest() || activeReport.visual_preview_only);
  },

  renderVisualEvidencePreview() {
    if (!this.els.intakeVisualCard) return;
    const manifest = this.visualManifest();
    if (!manifest) {
      this.els.intakeVisualCard.hidden = true;
      if (this.els.intakeVisualGrid) this.els.intakeVisualGrid.innerHTML = "";
      if (this.els.intakeVisualBackends) this.els.intakeVisualBackends.innerHTML = "";
      return;
    }

    const source = manifest.source || {};
    const writes = manifest.writes_allowed || {};
    const regionMap = this.visualRegionMap() || {};
    const recognition = this.visualRecognitionLayer() || {};
    const fields = [
      ["Record", source.visual_record_id || "-"],
      ["SHA256", source.sha256 || "-"],
      ["Native Size", `${source.width || "unknown"} x ${source.height || "unknown"}`],
      ["Aspect", source.aspect_ratio || "unknown"],
      ["Format", source.file_format || "unknown"],
      ["Mode", source.color_mode || "unknown"],
      ["Region Map", regionMap.region_map_id || "not attached"],
      ["Regions", Array.isArray(regionMap.regions) ? regionMap.regions.length : 0],
      ["Recognition", recognition.recognition_layer_id || "not attached"],
      ["Candidates", Array.isArray(recognition.candidates) ? recognition.candidates.length : 0],
      ["Authority", manifest.authority || "source_local_visual_evidence"],
      ["Approval", manifest.approval_status || "preview_only"],
      ["Write Locks", `maps=${Boolean(writes.maps)} counts=${Boolean(writes.counts)} lifetime=${Boolean(writes.lifetime)} lexicon=${Boolean(writes.lexicon)}`],
    ];
    this.els.intakeVisualGrid.innerHTML = fields.map(([label, value]) => `
      <div class="visual-evidence-row">
        <span>${this.escape(label)}</span>
        <strong>${this.escape(String(value))}</strong>
      </div>
    `).join("");

    const backends = manifest.backend_capabilities || [];
    this.els.intakeVisualBackends.innerHTML = backends.length
      ? backends.map((backend) => `
          <div class="visual-backend-card">
            <strong>${this.escape(backend.backend_id || "backend")}</strong>
            <span>${this.escape(backend.backend_type || "unknown")} - ${this.escape(backend.provider || "local")} - ${this.escape(backend.coordinate_space || "native_pixels")}</span>
            <span>resize derived: ${backend.resize_is_derived ? "yes" : "no"} / distorts source: ${backend.distorts_source ? "yes" : "no"}</span>
          </div>
        `).join("")
      : `<div class="empty-panel">No backend capability has been declared yet.</div>`;
    this.els.intakeVisualCard.hidden = false;
  },

  renderIntakeUniqueList() {
    const report = this.intake.report || {};
    const filter = this.els.intakeUniqueFilter.value.trim().toLowerCase();
    const allRows = (report.unique_anchors || []).filter((row) => !filter || String(row.anchor || "").toLowerCase().includes(filter));
    const rows = allRows.slice(0, INTAKE_RENDER_ROW_LIMIT);
    const capped = allRows.length > rows.length;
    this.els.intakeUniqueMeta.textContent = `${rows.length.toLocaleString()} shown of ${allRows.length.toLocaleString()} matching / ${Number(report.unique_anchor_count || 0).toLocaleString()} total anchors`;
    const capNotice = capped ? `<div class="empty-panel">Display capped at ${INTAKE_RENDER_ROW_LIMIT.toLocaleString()} rows for browser speed. Use search to narrow the list.</div>` : "";
    this.els.intakeUniqueList.innerHTML = rows.map((row) => `
      <div class="anchor-row ${row.known ? "known" : "missing"}">
        <span class="anchor-name">${this.escape(row.anchor || "")}</span>
        <span class="anchor-count">${Number(row.observations || 0).toLocaleString()}</span>
      </div>
    `).join("") + capNotice || `<div class="empty-panel">No anchors found.</div>`;
  },

  renderIntakeMissingList() {
    const report = this.intake.report || {};
    const filter = this.els.intakeMissingFilter.value.trim().toLowerCase();
    const allRows = (report.missing_anchors || []).filter((row) => !filter || String(row.anchor || "").toLowerCase().includes(filter));
    const rows = allRows.slice(0, INTAKE_RENDER_ROW_LIMIT);
    const capped = allRows.length > rows.length;
    this.els.intakeMissingMeta.textContent = `${rows.length.toLocaleString()} shown of ${allRows.length.toLocaleString()} matching / ${Number(report.missing_anchor_count || 0).toLocaleString()} total anchors / ${this.intake.rejected.size.toLocaleString()} marked NULL`;
    this.updateIntakeApprovalButtons(rows);
    const capNotice = capped ? `<div class="empty-panel">Display capped at ${INTAKE_RENDER_ROW_LIMIT.toLocaleString()} rows for browser speed. Use search to narrow the list, or Bulk Approve All for the full missing set.</div>` : "";
    this.els.intakeMissingList.innerHTML = rows.map((row) => {
      const anchor = row.anchor || "";
      const rejected = this.intake.rejected.has(anchor);
      const selected = this.intake.selected.has(anchor);
      const suggestion = row.suggested_existing || "";
      const reviewKind = row.review_kind || "";
      const suggestionNote = suggestion
        ? `<div class="entry-meta">suggested ${reviewKind === "possible_compound_anchor" ? "split" : "repair"}: <strong>${this.escape(suggestion)}</strong></div>`
        : "";
      return `
        <div class="anchor-row review ${rejected ? "rejected" : ""} ${selected ? "selected" : ""}">
          <label class="anchor-select">
            <input type="checkbox" ${selected ? "checked" : ""} ${rejected ? "disabled" : ""} onchange="lexApp.toggleMissingSelection(decodeURIComponent('${this.uri(anchor)}'), this.checked)">
          </label>
          <div class="review-anchor-body">
            <span class="anchor-name">${this.escape(anchor)}</span>
            <span class="entry-meta">${Number(row.observations || 0).toLocaleString()}x</span>
            ${suggestionNote}
            <div class="anchor-edit-row">
              <input class="anchor-edit-input" data-missing-edit="${this.escape(anchor)}" type="text" value="${this.escape(suggestion || anchor)}" title="Edit this missing anchor before mapping">
              <button class="mini-btn" type="button" onclick="lexApp.applyMissingAnchorEdit(decodeURIComponent('${this.uri(anchor)}'))">${suggestion ? "Use/Edit" : "Edit"}</button>
              <button class="mini-btn danger" type="button" onclick="lexApp.deleteMissingAnchor(decodeURIComponent('${this.uri(anchor)}'))">Delete</button>
            </div>
          </div>
          <div class="review-actions">
            <button class="mini-btn good" type="button" onclick="lexApp.approveMissingAnchor(decodeURIComponent('${this.uri(anchor)}'))" ${rejected ? "disabled" : ""}>Approve</button>
            <button class="mini-btn" type="button" onclick="lexApp.rejectMissingAnchor(decodeURIComponent('${this.uri(anchor)}'))">${rejected ? "NULL" : "Mark NULL"}</button>
          </div>
        </div>
      `;
    }).join("") + capNotice || `<div class="empty-panel">No missing anchors.</div>`;
  },

  updateIntakeApprovalButtons(visibleRows = null) {
    const report = this.intake.report || {};
    if (this.isVisualIntake(report)) {
      this.els.intakeBulkApproveBtn.disabled = true;
      this.els.intakeSelectVisibleBtn.disabled = true;
      this.els.intakeApproveSelectedBtn.disabled = true;
      this.els.intakeApproveSelectedBtn.textContent = "Approve Selected";
      this.els.intakeBulkApproveBtn.textContent = "Bulk Approve All (blocked)";
      return;
    }
    const missingCount = Number(report.missing_anchor_count || 0);
    const visibleCount = visibleRows ? visibleRows.length : missingCount;
    const selectedCount = this.intake.selected.size;
    this.els.intakeBulkApproveBtn.disabled = this.intakeUnresolvedMissingCount(report) === 0;
    this.els.intakeSelectVisibleBtn.disabled = visibleCount === 0;
    this.els.intakeApproveSelectedBtn.disabled = selectedCount === 0;
    this.els.intakeApproveSelectedBtn.textContent = selectedCount
      ? `Approve Selected (${selectedCount.toLocaleString()})`
      : "Approve Selected";
    this.els.intakeBulkApproveBtn.textContent = `Bulk Approve All (${missingCount.toLocaleString()})`;
  },

  intakeUnresolvedMissingCount(report = null) {
    const activeReport = report || this.intake.report || {};
    return (activeReport.missing_anchors || []).filter((row) => {
      const anchor = row.anchor || "";
      return anchor && !this.intake.rejected.has(anchor);
    }).length;
  },

  toggleMissingSelection(anchor, selected) {
    if (!anchor || this.intake.rejected.has(anchor)) return;
    if (selected) {
      this.intake.selected.add(anchor);
    } else {
      this.intake.selected.delete(anchor);
    }
    this.renderIntakeMissingList();
  },

  selectVisibleMissingAnchors() {
    if (this.isVisualIntake()) {
      this.setBanner("info", "Visual intake is preview-only. Anchor selection is blocked.");
      return;
    }
    const report = this.intake.report || {};
    const filter = this.els.intakeMissingFilter.value.trim().toLowerCase();
    const rows = (report.missing_anchors || [])
      .filter((row) => !filter || String(row.anchor || "").toLowerCase().includes(filter))
      .slice(0, INTAKE_RENDER_ROW_LIMIT);
    for (const row of rows) {
      const anchor = row.anchor || "";
      if (anchor && !this.intake.rejected.has(anchor)) {
        this.intake.selected.add(anchor);
      }
    }
    this.renderIntakeMissingList();
  },

  async approveMissingAnchor(anchor) {
    if (this.isVisualIntake()) {
      this.setBanner("info", "Visual intake is preview-only. Anchor approval is blocked.");
      return;
    }
    if (!anchor || !this.intake.report) return;
    await this.approveMissingAnchorBatch([anchor], `Add "${anchor}" to the real lexicon?`);
  },

  rejectMissingAnchor(anchor) {
    if (this.isVisualIntake()) {
      this.setBanner("info", "Visual intake is preview-only. NULL mapping is blocked until a visual approval route exists.");
      return;
    }
    if (!anchor) return;
    this.intake.rejected.add(anchor);
    this.intake.selected.delete(anchor);
    this.renderIntakeMissingList();
    this.els.intakeMapBtn.disabled = this.intakeUnresolvedMissingCount() !== 0;
    this.setBanner("info", `Marked "${anchor}" for NULL symbol during this map. It will preserve position but not become memory truth.`);
  },

  async applyMissingAnchorEdit(anchor) {
    if (!anchor || !this.intake.content) return;
    const input = document.querySelector(`[data-missing-edit="${CSS.escape(anchor)}"]`);
    const replacement = String((input && input.value) || "").trim();
    if (!replacement) {
      this.setBanner("error", "Enter a replacement anchor, or use Delete.");
      return;
    }
    if (replacement.toLowerCase() === anchor.toLowerCase()) {
      this.setBanner("info", "No edit applied; replacement matches the missing anchor.");
      return;
    }
    await this.applyIntakeAnchorEdits([{
      original_anchor: anchor,
      replacement_anchor: replacement,
      action: "replace",
    }]);
  },

  async deleteMissingAnchor(anchor) {
    if (!anchor || !this.intake.content) return;
    if (!confirm(`Delete all "${anchor}" anchor occurrences from this prepared intake text?`)) return;
    await this.applyIntakeAnchorEdits([{
      original_anchor: anchor,
      replacement_anchor: "",
      action: "delete",
    }]);
  },

  async applyIntakeAnchorEdits(edits) {
    if (this.isVisualIntake()) {
      this.setBanner("info", "Visual intake is preview-only. Anchor edits are blocked.");
      return;
    }
    const prep = this.intake.prep || {};
    this.setIntakeStep("Applying intake correction", 74, true);
    try {
      const data = await this.api("/api/lexicon/intake/edit", {
        method: "POST",
        body: JSON.stringify({
          source_name: prep.source_name || this.intake.sourceName || "document",
          content: this.intake.content,
          edits,
        }),
      });
      this.intake.content = data.content || this.intake.content;
      this.intake.edits = [...(this.intake.edits || []), ...(data.edits || [])];
      this.intake.report = data.preview || this.intake.report;
      const previewClipped = this.intake.content.length > INTAKE_RAW_PREVIEW_CHAR_LIMIT;
      this.els.intakeRawPreview.textContent = previewClipped
        ? `${this.intake.content.slice(0, INTAKE_RAW_PREVIEW_CHAR_LIMIT)}\n\n[Preview clipped for browser speed. Full edited document remains loaded for intake.]`
        : this.intake.content;
      this.els.intakeRawMeta.textContent = `${prep.converter || "prepared"} - edited ${Number((this.intake.edits || []).length).toLocaleString()} anchor correction(s)`;
      this.renderIntakeReport(this.intake.report);
      this.setIntakeStep("Ready for approval", 100, false);
      this.setBanner("success", `Applied ${Number(data.edit_count || 0).toLocaleString()} intake correction(s). Original anchor text will be preserved in the mapped-file audit header.`);
    } catch (error) {
      this.setIntakeStep("Intake correction failed", 100, false, true);
      this.setBanner("error", `Intake correction failed: ${error.message}`);
    }
  },

  async approveSelectedMissingAnchors() {
    if (this.isVisualIntake()) {
      this.setBanner("info", "Visual intake is preview-only. Anchor approval is blocked.");
      return;
    }
    const anchors = [...this.intake.selected].filter((anchor) => anchor && !this.intake.rejected.has(anchor));
    if (!anchors.length) {
      this.setBanner("info", "No selected missing anchors are available for approval.");
      return;
    }
    await this.approveMissingAnchorBatch(anchors, `Add ${anchors.length.toLocaleString()} selected anchors to the real lexicon?`);
  },

  async approveAllMissingAnchors() {
    if (this.isVisualIntake()) {
      this.setBanner("info", "Visual intake is preview-only. Bulk anchor approval is blocked.");
      return;
    }
    const report = this.intake.report;
    if (!report) return;
    const anchors = (report.missing_anchors || [])
      .map((row) => row.anchor)
      .filter((anchor) => anchor && !this.intake.rejected.has(anchor));
    if (!anchors.length) {
      this.setBanner("info", "No missing anchors are available for approval.");
      return;
    }
    await this.approveMissingAnchorBatch(anchors, `Add all ${anchors.length.toLocaleString()} missing anchors to the real lexicon?`);
  },

  async approveMissingAnchorBatch(anchors, confirmationText) {
    const report = this.intake.report;
    if (!report || !anchors.length) return;
    if (!confirm(confirmationText)) return;
    const frequencies = Object.fromEntries((report.missing_anchors || []).map((row) => [row.anchor, Number(row.observations || 0)]));
    const button = this.els.intakeBulkApproveBtn;
    const original = button.textContent;
    const selectedButton = this.els.intakeApproveSelectedBtn;
    const selectedOriginal = selectedButton.textContent;
    button.disabled = true;
    selectedButton.disabled = true;
    this.els.intakeSelectVisibleBtn.disabled = true;
    this.els.intakeMapBtn.disabled = true;
    button.textContent = "Approving...";
    selectedButton.textContent = "Approving...";
    try {
      this.setIntakeStep(`Approving anchors: ${anchors.length.toLocaleString()} queued`, 78, true);
      const result = await this.api("/api/lexicon/intake/approve", {
        method: "POST",
        body: JSON.stringify({ anchors, frequencies }),
      });
      const approvedSet = new Set(anchors);
      this.intake.selected = new Set([...this.intake.selected].filter((anchor) => !approvedSet.has(anchor)));
      this.setIntakeStep(
        `Approved ${Number(result.approved_count || 0).toLocaleString()} anchors; allocated ${Number(result.slots_allocated || 0).toLocaleString()} slots`,
        86,
        true
      );
      await this.nextFrame();
      this.setIntakeStep(`Lexicon writes: ${Number(result.lexicon_files_written || 0).toLocaleString()} files; spare writes: ${Number(result.spare_pool_writes || 0).toLocaleString()}`, 92, true);
      await this.nextFrame();
      this.setIntakeStep("Coverage refresh", 96, true);
      await this.refreshStats();
      await this.recheckIntakeCoverage("Ready for approval");
      this.setBanner(
        "success",
        `Approved ${Number(result.approved_count || 0).toLocaleString()} anchors, allocated ${Number(result.slots_allocated || 0).toLocaleString()} slots, refreshed coverage once.`
      );
    } catch (error) {
      this.setIntakeStep("Anchor approval failed", 100, false, true);
      this.setBanner("error", `Anchor approval failed: ${error.message}`);
    } finally {
      button.textContent = original;
      selectedButton.textContent = selectedOriginal;
      button.disabled = Number((this.intake.report || {}).missing_anchor_count || 0) === 0;
      this.updateIntakeApprovalButtons();
    }
  },

  async recheckIntakeCoverage(finalLabel) {
    if (this.isVisualIntake()) {
      this.setIntakeStep("Visual evidence preview only", 100, false);
      return;
    }
    const content = this.intake.content;
    const prep = this.intake.prep || {};
    if (!content) return;
    this.setIntakeStep("Comparing against real lexicon", 68, true);
    const report = await this.api("/api/lexicon/intake/preview", {
      method: "POST",
      body: JSON.stringify({
        source_name: prep.source_name || this.intake.sourceName || "document",
        source_path: prep.source_path || this.intake.sourcePath || "",
        file_size: prep.original_size || this.intake.fileSize || content.length,
        file_type: prep.file_type || this.intake.fileType || "",
        content,
      }),
    });
    this.intake.report = report;
    this.renderIntakeReport(report);
    this.setIntakeStep(this.intakeUnresolvedMissingCount(report) === 0 ? "Lexicon coverage complete or nulled. Ready to map/count." : finalLabel, 100, false);
  },

  async runIntakeMapping() {
    const report = this.intake.report;
    const sourceName = this.intake.sourceName || (this.intake.prep || {}).source_name || "document";
    if (!this.intake.content || !report) return;
    if (this.isVisualIntake(report)) {
      this.setBanner("error", "Visual intake is preview-only. Map/count is blocked until a future visual approval route exists.");
      this.setIntakeStep("Visual map/count blocked", 100, false, true);
      return;
    }
    const unresolvedMissing = this.intakeUnresolvedMissingCount(report);
    if (unresolvedMissing !== 0) {
      this.setBanner("error", "Approve, edit, delete, or mark missing anchors as NULL before mapping/counting.");
      return;
    }
    const nullCount = this.intake.rejected.size;
    const nullNote = nullCount ? `\n\n${nullCount.toLocaleString()} rejected anchor(s) will be mapped to the NULL symbol: position preserved, no memory truth recorded.` : "";
    if (!confirm(`Run mapping and lifetime counts for "${sourceName}"?${nullNote}`)) return;
    const button = this.els.intakeMapBtn;
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "Running...";
    try {
      this.setIntakeStep("Running mapping + counts", 92, true);
      const data = await this.api("/api/lexicon/intake/map", {
        method: "POST",
          body: JSON.stringify({
            source_name: sourceName,
            content: this.intake.content,
            intake_edits: [
              ...(this.intake.edits || []),
              ...[...this.intake.rejected].map((anchor) => ({
                original_anchor: anchor,
                action: "null",
                reason: "operator_marked_junk",
              })),
            ],
          }),
      });
      this.renderMappingReport(data);
      this.showTab("lexicon");
      this.setBanner("success", `Mapped ${data.source_name}. Saved observed map to ${data.saved_map_name}.`);
    } catch (error) {
      this.setIntakeStep("Mapping + counts failed", 100, false, true);
      this.setBanner("error", `Mapping + counts failed: ${error.message}`);
    } finally {
      button.textContent = original;
      button.disabled = this.isVisualIntake() || this.intakeUnresolvedMissingCount() !== 0;
    }
  },

  async runMappingBuild() {
    const filePath = this.els.mappingPath.value.trim();
    if (!filePath) {
      this.setBanner("error", "Enter a file path for mapping first.");
      this.els.mappingPath.focus();
      return;
    }

    const button = this.els.mappingBtn;
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "Starting...";
    try {
      const data = await this.api("/api/lexicon/mapping/run", {
        method: "POST",
        body: JSON.stringify({ file_path: filePath }),
      });
      this.renderMappingReport(data);
      this.setBanner("success", `Mapped ${data.source_name}. Saved observed map to ${data.saved_map_name}.`);
    } catch (error) {
      this.setBanner("error", `Mapping build failed: ${error.message}`);
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  },

  renderEmpty(message) {
    this.els.results.innerHTML = `<div class="empty-state"><div>${message}</div></div>`;
    this.els.pager.innerHTML = "";
  },

  renderMappingReport(report) {
    this.setMeta(
      "Observed Anchor Map",
      `${report.unique_anchor_count.toLocaleString()} unique anchors across ${report.total_anchor_observations.toLocaleString()} observations in ${report.paragraph_count.toLocaleString()} paragraphs from ${report.source_name}`
    );
    const observed = report.observed_anchors_preview || [];
    const known = report.known_anchors_preview || [];
    const missing = report.missing_anchors_preview || [];
    const occurrences = report.occurrence_preview || [];
    this.els.pager.innerHTML = "";
    this.els.results.innerHTML = `
      <article class="entry-card report-card">
        <div class="entry-card-top">
          <div class="entry-word">Summary</div>
          <span class="entry-tag">saved</span>
        </div>
        <div class="report-metric-grid">
          <div class="report-metric"><span class="report-metric-label">Unique anchors</span><strong>${Number(report.unique_anchor_count || 0).toLocaleString()}</strong></div>
          <div class="report-metric"><span class="report-metric-label">Total observations</span><strong>${Number(report.total_anchor_observations || 0).toLocaleString()}</strong></div>
          <div class="report-metric"><span class="report-metric-label">Paragraphs</span><strong>${Number(report.paragraph_count || 0).toLocaleString()}</strong></div>
          <div class="report-metric"><span class="report-metric-label">Window radius</span><strong>${Number(report.window_radius || 0).toLocaleString()}</strong></div>
          <div class="report-metric"><span class="report-metric-label">Known anchors</span><strong>${Number(report.known_anchor_count || 0).toLocaleString()}</strong></div>
          <div class="report-metric"><span class="report-metric-label">Missing anchors</span><strong>${Number(report.missing_anchor_count || 0).toLocaleString()}</strong></div>
        </div>
        <div class="entry-meta" style="margin-top:12px;">Source: ${this.escape(report.source_path || "-")}</div>
        <div class="entry-meta">Saved map: ${this.escape(report.saved_map_path || "-")}</div>
        <div class="entry-actions">
          <button style="background:#00d4ff;color:#041821;" onclick="lexApp.loadObservedMap(decodeURIComponent('${this.uri(report.saved_map_name || "")}'))">Reload Saved Map</button>
        </div>
      </article>
      ${this.renderOccurrencePreviewCard("Observed Windows", occurrences, "First observed anchor positions and their paragraph-bound windows.")}
      ${this.renderAnchorPreviewCard("Observed Anchors", observed, "Top observed anchors in this file.")}
      ${this.renderAnchorPreviewCard("Known Anchors", known, "Anchors already present in the lexicon.")}
      ${this.renderAnchorPreviewCard("Missing Anchors", missing, "Anchors not yet present in the lexicon.")}
    `;
  },

  renderOccurrencePreviewCard(title, rows, subtitle) {
    const body = rows.length
      ? rows.map((row) => {
          const windowText = Object.entries(row.window || {})
            .map(([offset, anchor]) => `${offset}:${anchor === null ? "null" : anchor}`)
            .join("  ");
          return `
            <div class="report-window">
              <div class="report-window-head">
                <span class="report-anchor">${this.escape(row.anchor || "")}</span>
                <span class="report-window-meta">paragraph ${Number(row.paragraph_id || 0)}  position ${Number(row.position || 0)}</span>
              </div>
              <div class="report-window-line">${this.escape(windowText)}</div>
            </div>
          `;
        }).join("")
      : `<div class="entry-meta">None.</div>`;
    return `
      <article class="entry-card report-card">
        <div class="entry-card-top">
          <div>
            <div class="entry-word">${this.escape(title)}</div>
            <div class="entry-meta">${this.escape(subtitle)}</div>
          </div>
        </div>
        <div class="report-list">${body}</div>
      </article>
    `;
  },

  async showObservedMaps() {
    try {
      const data = await this.api("/api/lexicon/observed-maps");
      const files = data.files || [];
      this.renderActionCards(files, "Observed Maps", `${files.length} saved maps under ${data.root || ""}`, (file) => `
        <article class="entry-card" onclick="lexApp.loadObservedMap(decodeURIComponent('${this.uri(file.name || "")}'))">
          <div class="entry-card-top">
            <div>
              <div class="entry-word">${this.escape(file.source_name || file.name || "")}</div>
              <div class="entry-meta">${this.escape(file.name || "")}</div>
            </div>
            <span class="entry-tag">${Number(file.unique_anchor_count || 0).toLocaleString()}</span>
          </div>
          <div class="entry-meta">Observations: ${Number(file.total_anchor_observations || 0).toLocaleString()}</div>
          <div class="entry-meta">Paragraphs: ${Number(file.paragraph_count || 0).toLocaleString()}</div>
        </article>
      `);
      this.clearBanner();
    } catch (error) {
      this.setBanner("error", `Observed map list failed: ${error.message}`);
    }
  },

  async loadObservedMap(name) {
    if (!name) return;
    try {
      const report = await this.api(`/api/lexicon/observed-map/${encodeURIComponent(name)}`);
      this.renderMappingReport(report);
      this.clearBanner();
    } catch (error) {
      this.setBanner("error", `Observed map reload failed: ${error.message}`);
    }
  },

  renderAnchorPreviewCard(title, rows, subtitle) {
    const body = rows.length
      ? rows.map((row) => `
          <div class="report-row">
            <span class="report-anchor">${this.escape(row.anchor || "")}</span>
            <span class="report-count">${Number(row.observations || 0).toLocaleString()}</span>
          </div>
        `).join("")
      : `<div class="entry-meta">None.</div>`;
    return `
      <article class="entry-card report-card">
        <div class="entry-card-top">
          <div>
            <div class="entry-word">${this.escape(title)}</div>
            <div class="entry-meta">${this.escape(subtitle)}</div>
          </div>
        </div>
        <div class="report-list">${body}</div>
      </article>
    `;
  },

  symbol(entry) {
    return (entry.payload && (entry.payload.hex || entry.payload.binary)) || entry.hex || entry.symbol || "-";
  },

  renderEntryCards(entries, meta) {
    this.setMeta("Results", meta);
    this.els.pager.innerHTML = "";
    if (!entries || entries.length === 0) {
      this.renderEmpty("No entries found.");
      return;
    }
    const maxFreq = Math.max(1, ...entries.map((item) => Number(item.frequency || 0)));
    this.els.results.innerHTML = entries.map((entry) => {
      const freq = Number(entry.frequency || 0);
      const pct = Math.max(5, (freq / maxFreq) * 100);
      const name = entry.display && entry.display !== entry.word ? `${entry.word} (${entry.display})` : (entry.word || "(empty)");
      return `<article class="entry-card" onclick="lexApp.showDetail(decodeURIComponent('${this.uri(entry.word || "")}'))">
        <div class="entry-card-top">
          <div>
            <div class="entry-word">${this.escape(name)}</div>
            <div class="entry-meta">Pack: ${this.escape(entry.pack || "-")}</div>
          </div>
          <span class="entry-tag">${this.escape(entry.status || "UNKNOWN")}</span>
        </div>
        <div class="entry-meta">Frequency: ${(freq || 0).toLocaleString()}</div>
        <div class="entry-symbol">${this.escape(this.symbol(entry))}</div>
        <div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div>
      </article>`;
    }).join("");
  },

  renderActionCards(entries, title, meta, renderer) {
    this.setMeta(title, meta);
    this.els.pager.innerHTML = "";
    if (!entries || entries.length === 0) {
      this.renderEmpty("Nothing to show.");
      return;
    }
    this.els.results.innerHTML = entries.map(renderer).join("");
  },

  renderPager(prevFn, nextFn, hasPrev, hasNext, label) {
    const buttons = [];
    if (hasPrev) {
      buttons.push(`<button onclick="${prevFn}">Prev</button>`);
    }
    buttons.push(`<button disabled>${label}</button>`);
    if (hasNext) {
      buttons.push(`<button onclick="${nextFn}">Next</button>`);
    }
    this.els.pager.innerHTML = buttons.join("");
  },

  async search() {
    const query = this.els.searchInput.value.trim();
    if (query.length < 2) {
      await this.showRandom();
      return;
    }
    try {
      const entries = await this.api(`/api/search_lexicon?query=${encodeURIComponent(query)}&pack=${this.pack}`);
      this.renderEntryCards(entries, `Search for "${query}" in ${this.labelForPack(this.pack)}`);
      this.clearBanner();
    } catch (error) {
      this.setBanner("error", `Search failed: ${error.message}`);
    }
  },

  async browseLetter(letter, button) {
    try {
      document.querySelectorAll(".alpha-btn").forEach((item) => item.classList.remove("active"));
      if (button) button.classList.add("active");
      const data = await this.api(`/api/lexicon/browse?letter=${letter}&limit=50&pack=${this.pack}`);
      this.renderEntryCards(data.entries || [], `${this.labelForPack(this.pack)} entries starting with ${letter} - ${Number(data.total || 0).toLocaleString()} total`);
      this.clearBanner();
    } catch (error) {
      this.setBanner("error", `Browse failed: ${error.message}`);
    }
  },

  async showRandom() {
    try {
      const data = await this.api(`/api/lexicon/sample?count=24&pack=${this.pack}`);
      this.renderEntryCards(data.entries || [], `Random sample from ${this.labelForPack(this.pack)} - ${Number(data.total || 0).toLocaleString()} total entries`);
      this.clearBanner();
    } catch (error) {
      this.setBanner("error", `Random sample failed: ${error.message}`);
    }
  },

  async showTop() {
    try {
      const data = await this.api(`/api/lexicon/top?count=30&pack=${this.pack}`);
      this.renderEntryCards(data.entries || [], `Top ${Number(data.total || 0).toLocaleString()} entries by frequency in ${this.labelForPack(this.pack)}`);
      this.clearBanner();
    } catch (error) {
      this.setBanner("error", `Top words failed: ${error.message}`);
    }
  },

  async showRecent() {
    try {
      const data = await this.api("/api/lexicon/recent?count=30");
      this.renderEntryCards(data.entries || [], `Recently mapped entries - ${Number(data.total || 0).toLocaleString()} total with timestamps`);
      this.clearBanner();
    } catch (error) {
      this.setBanner("error", `Recent browse failed: ${error.message}`);
    }
  },

  async showFiles() {
    try {
      const data = await this.api("/api/lexicon/files");
      const files = data.files || [];
      this.renderActionCards(files, "Partition Files", `${files.length} files under ${data.lexicon_root || ""}`, (file) => (
        `<article class="entry-card" onclick="lexApp.previewFile(decodeURIComponent('${this.uri(file.filename)}'), 0)">
          <div class="entry-card-top">
            <div>
              <div class="entry-word">${this.escape(file.letter)}</div>
              <div class="entry-meta">${this.escape(file.filename)}</div>
            </div>
            <span class="entry-tag">${this.size(file.size_bytes || 0)}</span>
          </div>
          <div class="entry-meta">Modified: ${file.modified ? new Date(file.modified * 1000).toLocaleString() : "-"}</div>
        </article>`
      ));
      this.clearBanner();
    } catch (error) {
      this.setBanner("error", `File list failed: ${error.message}`);
    }
  },

  async previewFile(filename, offset) {
    this.fileName = filename;
    this.fileOffset = offset;
    try {
      const data = await this.api(`/api/lexicon/file/${encodeURIComponent(filename)}?offset=${offset}&limit=50`);
      this.renderEntryCards(data.entries || [], `${filename} - entries ${offset + 1}-${Math.min(offset + (data.entries || []).length, data.total || 0)} of ${Number(data.total || 0).toLocaleString()}`);
      this.renderPager(
        `lexApp.previewFile(decodeURIComponent('${this.uri(filename)}'), ${Math.max(0, offset - 50)})`,
        `lexApp.previewFile(decodeURIComponent('${this.uri(filename)}'), ${offset + 50})`,
        offset > 0,
        offset + 50 < Number(data.total || 0),
        filename
      );
      this.clearBanner();
    } catch (error) {
      this.setBanner("error", `File preview failed: ${error.message}`);
    }
  },

  async showDetail(word) {
    if (!word) return;
    try {
      const [entry, context] = await Promise.all([
        this.api(`/api/lexicon/entry?word=${encodeURIComponent(word)}`),
        this.api("/api/616", { method: "POST", body: JSON.stringify({ word }) }),
      ]);

      const displayName = entry.display && entry.display !== entry.word ? `${entry.word} (${entry.display})` : entry.word;
      this.els.detailTitle.textContent = `Word Detail - ${entry.word}`;
      this.els.detailBody.innerHTML = `
        <div class="detail-grid">
          <div class="detail-box">
            <div class="detail-box-label">Word</div>
            <div style="font-size:20px;font-weight:800;">${this.escape(displayName || "-")}</div>
            <div style="margin-top:6px;font-size:12px;color:var(--text-secondary);">Pack: ${this.escape(entry.pack || "-")}</div>
          </div>
          <div class="detail-box">
            <div class="detail-box-label">Address</div>
            <div style="font-family:Consolas,monospace;color:var(--gpt-oss);">${this.escape(entry.hex || "-")}</div>
            <div style="margin-top:6px;font-size:12px;color:var(--text-secondary);word-break:break-all;">${this.escape(entry.binary || "-")}</div>
          </div>
          <div class="detail-box">
            <div class="detail-box-label">Status</div>
            <div style="font-size:18px;font-weight:800;">${this.escape(entry.status || "UNKNOWN")}</div>
            <div style="margin-top:6px;font-size:12px;color:var(--text-secondary);">Symbol: ${this.escape(entry.symbol || "-")}</div>
          </div>
          <div class="detail-box">
            <div class="detail-box-label">Frequency</div>
            <div style="font-size:20px;font-weight:800;color:var(--gpt-oss);">${Number(entry.frequency || 0).toLocaleString()}</div>
            <div style="margin-top:6px;font-size:12px;color:var(--text-secondary);">Mapped: ${entry.mapped_at ? new Date(entry.mapped_at).toLocaleString() : "-"}</div>
          </div>
        </div>
        <div style="margin-top:16px;">
          <h3 style="margin:0 0 10px; color:var(--gpt-oss);">6-1-6 Context</h3>
          ${this.renderContext("Before", context.before || {}, "var(--highlight)")}
          ${this.renderContext("After", context.after || {}, "var(--gpt-oss)")}
        </div>
      `;
      this.els.detailCard.classList.add("active");
      this.els.detailCard.scrollIntoView({ behavior: "smooth", block: "start" });
      this.clearBanner();
    } catch (error) {
      this.setBanner("error", `Detail load failed: ${error.message}`);
    }
  },

  renderContext(label, buckets, color) {
    const keys = Object.keys(buckets || {});
    if (keys.length === 0) {
      return `<div class="detail-box" style="margin-top:8px;">${label}: no context yet.</div>`;
    }
    return `<div style="margin-top:8px;">
      <div style="margin-bottom:8px; font-weight:700; color:${color};">${label}</div>
      <div class="context-grid">
        ${keys.sort((a, b) => Number(a) - Number(b)).map((distance) => {
          const rows = (buckets[distance] || []).slice(0, 8);
          const max = Math.max(1, ...rows.map((row) => Array.isArray(row) ? Number(row[1] || 0) : Number(row.count || 0)));
          return `<div class="context-box">
            <div class="detail-box-label">Distance ${distance}</div>
            ${rows.map((row) => {
              const word = Array.isArray(row) ? row[0] : row.word || row.display || "";
              const count = Array.isArray(row) ? Number(row[1] || 0) : Number(row.count || 0);
              const pct = Math.max(8, (count / max) * 100);
              return `<div class="context-row">
                <span class="context-word" title="${this.escape(word)}">${this.escape(word)}</span>
                <div class="context-bar"><div class="context-bar-fill" style="width:${pct}%; background:${color};"></div></div>
                <span style="font-size:11px;color:var(--text-secondary);min-width:26px;text-align:right;">${count}</span>
              </div>`;
            }).join("")}
          </div>`;
        }).join("")}
      </div>
    </div>`;
  },

  async showUnmatched() {
    try {
      const data = await this.api("/api/lexicon/unmatched?limit=100&sort=frequency");
      const entries = data.entries || [];
      this.renderActionCards(entries, "Unmatched Words", `${Number(data.unmatched_total || 0).toLocaleString()} words waiting for review`, (entry) => `
        <article class="entry-card">
          <div class="entry-card-top">
            <div class="entry-word">${this.escape(entry.word)}</div>
            <span class="entry-tag">${Number(entry.frequency || 0).toLocaleString()}x</span>
          </div>
          <div class="entry-actions">
            <button style="background:#00ff88;color:#000;" onclick="lexApp.approveUnmatched(decodeURIComponent('${this.uri(entry.word)}'))">Accept</button>
            <button style="background:#ff4444;color:#fff;" onclick="lexApp.denyUnmatched(decodeURIComponent('${this.uri(entry.word)}'))">Deny</button>
          </div>
        </article>`);
      this.els.pager.innerHTML = entries.length ? `
        <button onclick="lexApp.bulkApprove()">Approve All</button>
        <button onclick="lexApp.bulkDeny()">Deny All</button>` : "";
      this.clearBanner();
    } catch (error) {
      this.setBanner("error", `Unmatched list failed: ${error.message}`);
    }
  },

  async approveUnmatched(word) {
    await this.api("/api/lexicon/approve", { method: "POST", body: JSON.stringify({ word }) });
    this.setBanner("success", `Approved "${word}" and moved it to pending review.`);
    await this.refreshStats();
    await this.showUnmatched();
  },

  async denyUnmatched(word) {
    await this.api("/api/lexicon/ignore", { method: "POST", body: JSON.stringify({ word }) });
    this.setBanner("info", `Ignored "${word}".`);
    await this.refreshStats();
    await this.showUnmatched();
  },

  async bulkApprove() {
    const data = await this.api("/api/lexicon/unmatched/approve-all", { method: "POST" });
    this.setBanner("success", `Moved ${Number(data.moved || 0).toLocaleString()} unmatched words to pending review.`);
    await this.refreshStats();
    await this.showUnmatched();
  },

  async bulkDeny() {
    const data = await this.api("/api/lexicon/unmatched/deny-all", { method: "POST" });
    this.setBanner("info", `Denied ${Number(data.denied || 0).toLocaleString()} unmatched words.`);
    await this.refreshStats();
    await this.showUnmatched();
  },

  async showPending() {
    try {
      const data = await this.api("/api/lexicon/pending");
      const entries = data.entries || [];
      this.renderActionCards(entries, "Pending Review", `${Number(data.total || 0).toLocaleString()} words ready for slot assignment`, (entry) => `
        <article class="entry-card">
          <div class="entry-card-top">
            <div>
              <div class="entry-word">${this.escape(entry.word)}</div>
              <div class="entry-meta">Added: ${entry.added_at ? new Date(entry.added_at).toLocaleString() : "-"}</div>
            </div>
            <span class="entry-tag">${Number(entry.frequency || 0).toLocaleString()}x</span>
          </div>
          <div class="entry-actions">
            <button style="background:#00ff88;color:#000;" onclick="lexApp.assignPending(decodeURIComponent('${this.uri(entry.word)}'))">Assign Slot</button>
            <button style="background:#555;color:#fff;" onclick="lexApp.removePending(decodeURIComponent('${this.uri(entry.word)}'))">Remove</button>
          </div>
        </article>`);
      this.els.pager.innerHTML = entries.length ? `<button onclick="lexApp.assignAllPending()">Assign All Pending</button>` : "";
      this.clearBanner();
    } catch (error) {
      this.setBanner("error", `Pending list failed: ${error.message}`);
    }
  },

  async assignPending(word) {
    const data = await this.api("/api/lexicon/pending/assign", { method: "POST", body: JSON.stringify({ word }) });
    this.setBanner("success", `Assigned "${word}" to ${data.hex || "a slot"}.`);
    await this.refreshStats();
    await this.showPending();
  },

  async removePending(word) {
    await this.api(`/api/lexicon/pending/${encodeURIComponent(word)}`, { method: "DELETE" });
    this.setBanner("info", `Removed "${word}" from pending review.`);
    await this.refreshStats();
    await this.showPending();
  },

  async assignAllPending() {
    const data = await this.api("/api/lexicon/pending/assign-all", { method: "POST" });
    this.setBanner("success", `Assigned ${Number(data.assigned || 0).toLocaleString()} pending words${data.failed ? `, ${data.failed} failed` : ""}.`);
    await this.refreshStats();
    await this.showPending();
  },

  async showIgnored() {
    try {
      const data = await this.api("/api/lexicon/ignored");
      const words = data.words || [];
      this.renderActionCards(words, "Ignore List", `${Number(data.total || 0).toLocaleString()} ignored words`, (word) => `
        <article class="entry-card">
          <div class="entry-card-top">
            <div class="entry-word">${this.escape(word)}</div>
            <span class="entry-tag">ignored</span>
          </div>
          <div class="entry-actions">
            <button style="background:#333;color:#fff;" onclick="lexApp.unignore(decodeURIComponent('${this.uri(word)}'))">Restore</button>
          </div>
        </article>`);
      this.clearBanner();
    } catch (error) {
      this.setBanner("error", `Ignored list failed: ${error.message}`);
    }
  },

  async unignore(word) {
    await this.api(`/api/lexicon/ignore/${encodeURIComponent(word)}`, { method: "DELETE" });
    this.setBanner("info", `Restored "${word}" from the ignore list.`);
    await this.refreshStats();
    await this.showIgnored();
  },

  async clearCanonical() {
    if (!confirm("Clear the entire canonical lexicon and reclaim every slot to the spare pool?")) return;
    const data = await this.api("/api/lexicon/canonical", { method: "DELETE" });
    this.setBanner("success", `Cleared canonical lexicon. Reclaimed ${Number(data.slots_reclaimed || 0).toLocaleString()} slots.`);
    await this.refreshStats();
    await this.showRandom();
  },

  async returnToPool() {
    if (!confirm("Return all canonical slots to the spare pool?")) return;
    const data = await this.api("/api/lexicon/return-to-pool", { method: "POST" });
    this.setBanner("success", `Returned ${Number(data.moved || 0).toLocaleString()} slots to the pool.`);
    await this.refreshStats();
    await this.showRandom();
  },

  async importWords() {
    const wordsDir = this.els.importPath.value.trim();
    if (!wordsDir) {
      this.setBanner("error", "Enter an import directory first.");
      this.els.importPath.focus();
      return;
    }
    const data = await this.api("/api/lexicon/import", {
      method: "POST",
      body: JSON.stringify({ words_dir: wordsDir.trim() }),
    });
    this.setBanner("success", `Imported ${Number(data.imported || 0).toLocaleString()} words, skipped ${Number(data.skipped || 0).toLocaleString()}, overflow ${Number(data.no_slots || 0).toLocaleString()}.`);
    await this.refreshStats();
    await this.showRandom();
  },

  async loadTreeBrainControls() {
    try {
      const data = await this.api("/api/tree-brain/controls");
      this.treeBrainControls = data.tree_brain_controls || null;
      this.symbolPolicy = data.symbol_policy || {};
      this.renderTreeBrainControls(this.treeBrainControls);
      this.renderSymbolPolicy(this.symbolPolicy);
      this.clearBanner();
    } catch (error) {
      this.setBanner("error", `Tree-Brain controls failed to load: ${error.message}`);
    }
  },

  renderTreeBrainControls(payload) {
    const sections = (payload && payload.sections) || {};
    const sectionNames = Object.keys(sections);
    if (!sectionNames.length) {
      this.els.treeControlsGrid.innerHTML = `<div class="empty-panel">No Tree-Brain controls found.</div>`;
      return;
    }
    this.els.treeControlsGrid.innerHTML = sectionNames.map((sectionName) => {
      const section = sections[sectionName] || {};
      const fields = section.fields || {};
      return `
        <article class="control-section-card">
          <div class="section-head">
            <div>
              <h3>${this.escape(section.label || sectionName)}</h3>
              <p>${this.escape(this.labelControlSection(sectionName))}</p>
            </div>
          </div>
          <div class="control-fields">
            ${Object.entries(fields).map(([key, field]) => this.renderControlField(sectionName, key, field)).join("")}
          </div>
        </article>
      `;
    }).join("");
  },

  labelControlSection(sectionName) {
    const labels = {
      tree_limits: "Primary tree size, depth, branch width, and pruning pressure.",
      rescue_layer: "Flat oxygen layer. Samples around seeds but never builds another tree.",
      answer_regulation: "Answer length and evidence thresholds. Long answers must earn it.",
      scoring: "Evidence weights and penalties used after policy approves candidate leaves.",
      diagnostics_harness: "Fixed query harness paths for repeatable policy diagnostics.",
    };
    return labels[sectionName] || "Visible tuning controls persisted to config.";
  },

  renderControlField(sectionName, key, field) {
    const id = `control-${sectionName}-${key}`;
    const value = field.value ?? field.default ?? "";
    const defaultValue = field.default ?? "";
    const type = field.type || "text";
    const common = `id="${this.escape(id)}" data-section="${this.escape(sectionName)}" data-key="${this.escape(key)}" data-type="${this.escape(type)}"`;
    let input = "";
    if (type === "boolean") {
      input = `<input ${common} class="control-input" type="checkbox" ${value ? "checked" : ""}>`;
    } else if (type === "number") {
      const step = field.step || (Number.isInteger(Number(value)) ? 1 : 0.01);
      input = `<input ${common} class="control-input" type="number" value="${this.escape(value)}" min="${this.escape(field.min ?? "")}" max="${this.escape(field.max ?? "")}" step="${this.escape(step)}">`;
    } else {
      input = `<input ${common} class="control-input" type="text" value="${this.escape(value)}">`;
    }
    return `
      <label class="control-field" for="${this.escape(id)}">
        <div class="control-label-row">
          <span>${this.escape(field.label || key)}</span>
          <button class="mini-btn" type="button" onclick="lexApp.resetControlField('${this.uri(sectionName)}','${this.uri(key)}')">Reset</button>
        </div>
        ${input}
        <div class="control-meta">Default: ${this.escape(defaultValue)}${field.min !== undefined ? ` | Min: ${this.escape(field.min)}` : ""}${field.max !== undefined ? ` | Max: ${this.escape(field.max)}` : ""}</div>
        <div class="control-help">${this.escape(field.help || "")}</div>
      </label>
    `;
  },

  resetControlField(sectionNameEncoded, keyEncoded) {
    const sectionName = decodeURIComponent(sectionNameEncoded);
    const key = decodeURIComponent(keyEncoded);
    const field = this.treeBrainControls
      && this.treeBrainControls.sections
      && this.treeBrainControls.sections[sectionName]
      && this.treeBrainControls.sections[sectionName].fields
      && this.treeBrainControls.sections[sectionName].fields[key];
    if (!field) return;
    const input = document.querySelector(`[data-section="${CSS.escape(sectionName)}"][data-key="${CSS.escape(key)}"]`);
    if (!input) return;
    if (input.dataset.type === "boolean") {
      input.checked = Boolean(field.default);
    } else {
      input.value = field.default ?? "";
    }
  },

  collectTreeBrainControls() {
    const payload = JSON.parse(JSON.stringify(this.treeBrainControls || { sections: {} }));
    document.querySelectorAll(".control-input[data-section][data-key]").forEach((input) => {
      const sectionName = input.dataset.section;
      const key = input.dataset.key;
      const type = input.dataset.type;
      const section = payload.sections && payload.sections[sectionName];
      const field = section && section.fields && section.fields[key];
      if (!field) return;
      if (type === "boolean") {
        field.value = input.checked;
      } else if (type === "number") {
        field.value = input.value === "" ? field.default : Number(input.value);
      } else {
        field.value = input.value;
      }
    });
    return payload;
  },

  async saveTreeBrainControls() {
    try {
      const controls = this.collectTreeBrainControls();
      const data = await this.api("/api/tree-brain/controls", {
        method: "POST",
        body: JSON.stringify({ controls }),
      });
      this.treeBrainControls = data.tree_brain_controls;
      this.renderTreeBrainControls(this.treeBrainControls);
      this.setBanner("success", "Tree-Brain controls saved. Cockpit switches are now active.");
    } catch (error) {
      this.setBanner("error", `Tree-Brain controls save failed: ${error.message}`);
    }
  },

  async resetTreeBrainControls() {
    if (!confirm("Restore Tree-Brain control defaults? Symbol policy lists will not be changed.")) return;
    try {
      const data = await this.api("/api/tree-brain/controls/reset", { method: "POST" });
      this.treeBrainControls = data.tree_brain_controls;
      this.renderTreeBrainControls(this.treeBrainControls);
      this.setBanner("success", "Tree-Brain control defaults restored.");
    } catch (error) {
      this.setBanner("error", `Tree-Brain reset failed: ${error.message}`);
    }
  },

  async validateTreeBrainControls() {
    try {
      const data = await this.api("/api/tree-brain/validate", { method: "POST" });
      this.setBanner("success", data.message || "Tree-Brain controls and symbol policy are valid.");
    } catch (error) {
      this.setBanner("error", `Tree-Brain validation failed: ${error.message}`);
    }
  },

  renderSymbolPolicy(policy) {
    const entries = Object.entries(policy || {});
    if (!entries.length) {
      this.els.symbolPolicyGrid.innerHTML = `<div class="empty-panel">No symbol policy loaded.</div>`;
      return;
    }
    this.els.symbolPolicyGrid.innerHTML = entries.map(([key, value]) => {
      const isArray = Array.isArray(value);
      const label = key.replaceAll("_", " ");
      if (isArray) {
        return `
          <label class="policy-list-editor">
            <div class="control-label-row">
              <span>${this.escape(label)}</span>
              <span class="entry-tag">${value.length} items</span>
            </div>
            <textarea data-policy-key="${this.escape(key)}" data-policy-type="list" rows="8">${this.escape(value.join("\n"))}</textarea>
            <div class="control-help">One item per line or comma-separated. Policy remains the authority.</div>
          </label>
        `;
      }
      return `
        <label class="policy-list-editor">
          <div class="control-label-row"><span>${this.escape(label)}</span></div>
          <select data-policy-key="${this.escape(key)}" data-policy-type="scalar">
            ${["reject_leaf", "allow_evidence", "allow"].map((option) => (
              `<option value="${option}" ${String(value) === option ? "selected" : ""}>${option}</option>`
            )).join("")}
          </select>
          <div class="control-help">Policy switch persisted to symbol_policy.json.</div>
        </label>
      `;
    }).join("");
  },

  collectSymbolPolicy() {
    const policy = {};
    document.querySelectorAll("[data-policy-key]").forEach((input) => {
      const key = input.dataset.policyKey;
      if (input.dataset.policyType === "list") {
        policy[key] = input.value
          .split(/[\n,]/)
          .map((item) => item.trim())
          .filter((item, index, array) => item && array.indexOf(item) === index);
      } else {
        policy[key] = input.value;
      }
    });
    return policy;
  },

  async saveSymbolPolicy() {
    try {
      const policy = this.collectSymbolPolicy();
      const data = await this.api("/api/tree-brain/symbol-policy", {
        method: "POST",
        body: JSON.stringify({ policy }),
      });
      this.symbolPolicy = data.symbol_policy || policy;
      this.renderSymbolPolicy(this.symbolPolicy);
      this.setBanner("success", "Symbol policy saved. Tree now consumes the updated policy.");
    } catch (error) {
      this.setBanner("error", `Symbol policy save failed: ${error.message}`);
    }
  },

  exportTreeBrainConfig() {
    const payload = {
      exported_at: new Date().toISOString(),
      tree_brain_controls: this.collectTreeBrainControls(),
      symbol_policy: this.collectSymbolPolicy(),
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "tree-brain-control-profile.json";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    this.setBanner("success", "Tree-Brain profile exported.");
  },

  async importTreeBrainConfig() {
    const file = this.els.treeControlsImportFile.files && this.els.treeControlsImportFile.files[0];
    if (!file) return;
    try {
      const text = await file.text();
      const payload = JSON.parse(text);
      const controls = payload.tree_brain_controls || payload.controls;
      const policy = payload.symbol_policy || payload.policy;
      if (controls) {
        const savedControls = await this.api("/api/tree-brain/controls", {
          method: "POST",
          body: JSON.stringify({ controls }),
        });
        this.treeBrainControls = savedControls.tree_brain_controls;
        this.renderTreeBrainControls(this.treeBrainControls);
      }
      if (policy) {
        const savedPolicy = await this.api("/api/tree-brain/symbol-policy", {
          method: "POST",
          body: JSON.stringify({ policy }),
        });
        this.symbolPolicy = savedPolicy.symbol_policy || policy;
        this.renderSymbolPolicy(this.symbolPolicy);
      }
      this.setBanner("success", "Tree-Brain profile imported and persisted.");
    } catch (error) {
      this.setBanner("error", `Tree-Brain import failed: ${error.message}`);
    } finally {
      this.els.treeControlsImportFile.value = "";
    }
  },

  async runTreeDiagnostics() {
    this.els.treeDiagnosticsPanel.innerHTML = `<div class="empty-panel">Running fixed query diagnostics...</div>`;
    try {
      const data = await this.api("/api/tree-brain/diagnostics/run", { method: "POST" });
      this.diagnosticsReport = data.report || null;
      this.renderTreeDiagnostics(this.diagnosticsReport);
      this.setBanner("success", "Policy diagnostics harness completed.");
    } catch (error) {
      this.setBanner("error", `Policy diagnostics failed: ${error.message}`);
    }
  },

  async loadLatestTreeDiagnostics() {
    try {
      const data = await this.api("/api/tree-brain/diagnostics/latest");
      this.diagnosticsReport = data.report || null;
      this.renderTreeDiagnostics(this.diagnosticsReport);
    } catch (error) {
      this.setBanner("error", `Latest diagnostics load failed: ${error.message}`);
    }
  },

  renderTreeDiagnostics(report) {
    if (!report) {
      this.els.treeDiagnosticsPanel.innerHTML = `<div class="empty-panel">No diagnostics report loaded yet.</div>`;
      return;
    }
    const aggregate = report.aggregate || {};
    const accepted = aggregate.accepted_by_class || {};
    const rejected = aggregate.rejected_by_reason || {};
    const topAccepted = aggregate.top_accepted_symbols || [];
    const topRejected = aggregate.top_rejected_symbols || [];
    this.els.treeDiagnosticsPanel.innerHTML = `
      <div class="diagnostics-summary">
        <div class="stat-card">
          <div class="stat-label">Queries</div>
          <div class="stat-value">${Number(report.query_count || 0).toLocaleString()}</div>
          <div class="stat-note">${this.escape(report.generated_at || "")}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Tree / Policy</div>
          <div class="stat-value">${this.escape(report.tree_version || "-")}</div>
          <div class="stat-note">Policy ${this.escape(report.policy_version || "-")} | ${this.escape(report.tests_baseline || "")}</div>
        </div>
      </div>
      <div class="diagnostics-grid">
        ${this.renderDiagnosticsCountCard("Accepted by class", accepted)}
        ${this.renderDiagnosticsCountCard("Rejected by reason", rejected)}
        ${this.renderDiagnosticsSymbolCard("Top accepted symbols", topAccepted, "winner_reason")}
        ${this.renderDiagnosticsSymbolCard("Top rejected symbols", topRejected, "rejection_reason")}
      </div>
    `;
  },

  renderDiagnosticsCountCard(title, counts) {
    const rows = Object.entries(counts || {})
      .sort((a, b) => Number(b[1]) - Number(a[1]) || a[0].localeCompare(b[0]))
      .slice(0, 12);
    return `
      <article class="diagnostics-card">
        <h3>${this.escape(title)}</h3>
        <div class="diagnostics-list">
          ${rows.length ? rows.map(([key, value]) => `
            <div class="diagnostics-row">
              <span>${this.escape(key)}</span>
              <strong>${Number(value || 0).toLocaleString()}</strong>
            </div>
          `).join("") : `<div class="empty-panel">No rows.</div>`}
        </div>
      </article>
    `;
  },

  renderDiagnosticsSymbolCard(title, items, reasonKey) {
    const rows = (items || []).slice(0, 10);
    return `
      <article class="diagnostics-card">
        <h3>${this.escape(title)}</h3>
        <div class="diagnostics-list">
          ${rows.length ? rows.map((item) => `
            <div class="diagnostics-row diagnostics-row-symbol">
              <span>
                <strong>${this.escape(item.anchor || item.symbol || "")}</strong>
                <small>${this.escape(item[reasonKey] || item.reason || "")}</small>
              </span>
              <em>${Number(item.count || 0).toLocaleString()}x | ${Number(item.score || 0).toFixed(2)}</em>
            </div>
          `).join("") : `<div class="empty-panel">No rows.</div>`}
        </div>
      </article>
    `;
  },

  nextFrame() {
    return new Promise((resolve) => requestAnimationFrame(resolve));
  },

  escape(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  },

  escapeAttr(value) {
    return this.escape(value).replaceAll("`", "&#96;");
  },

  uri(value) {
    return encodeURIComponent(String(value || ""));
  },

  labelForPack(pack) {
    switch (pack) {
      case "canonical":
        return "canonical";
      case "spare":
        return "spare";
      default:
        return "all packs";
    }
  },

  size(bytes) {
    return bytes >= 1048576 ? `${(bytes / 1048576).toFixed(1)} MB` : `${Math.round(bytes / 1024)} KB`;
  },
};

window.lexApp = lexApp;
window.addEventListener("DOMContentLoaded", () => lexApp.boot());
