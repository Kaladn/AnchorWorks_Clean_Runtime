from __future__ import annotations

from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Input, Select, Static, TabbedContent, TabPane

from .app import _default_data_root
from .clearspeak import ClearSpeakService
from .conversation import ConversationEngine
from .document_answer import DocumentAnswerAssembler
from .store import LexiconStore


class AnchorWorksOperatorApp(App):
    CSS = """
    Screen { layout: vertical; }
    #body { height: 1fr; }
    Static { padding: 1; }
    Input { dock: bottom; }
    """

    PANEL_TITLES = (
        "Chat",
        "Evidence Trace",
        "Intake Jobs",
        "Missing Anchor Review",
        "Counts/Binary Status",
        "Corpus Library",
        "Operator Surface",
    )

    def __init__(self, data_root: str | Path | None = None) -> None:
        super().__init__()
        self.data_root = Path(data_root or _default_data_root()).expanduser().resolve()
        self.store = LexiconStore(self.data_root)
        self.clearspeak = ClearSpeakService(self.store)
        self.document_answer = DocumentAnswerAssembler(self.store)
        self.conversation_engine = ConversationEngine(self.store, self.clearspeak, self.document_answer)
        self.last_receipt: dict[str, Any] = {}
        self.intake_action = "mapping"

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="body"):
            with TabbedContent(initial="chat"):
                with TabPane("Chat", id="chat"):
                    yield Static("AnchorWorks conversation runtime is ready.", id="chat-output")
                with TabPane("Evidence Trace", id="evidence"):
                    yield Static("No receipt yet.", id="evidence-output")
                with TabPane("Intake Jobs", id="intake"):
                    yield Select(
                        [
                            ("Mapping: document/directory to user AWSC counts", "mapping"),
                            ("Audit: source directory readiness", "audit"),
                        ],
                        value="mapping",
                        id="intake-action",
                    )
                    yield Static("Mapping selected. Enter a file or directory path below.", id="intake-output")
                    yield Input(placeholder="Path for selected intake action", id="intake-path")
                with TabPane("Missing Anchor Review", id="missing"):
                    yield Static(self._missing_summary(), id="missing-output")
                with TabPane("Counts/Binary Status", id="counts"):
                    yield Static(self._counts_summary(), id="counts-output")
                with TabPane("Corpus Library", id="corpus"):
                    yield Static("Conversation corpus normalizer accepts txt, srt, vtt, json, jsonl, csv.", id="corpus-output")
                with TabPane("Operator Surface", id="operator"):
                    yield Static(self._operator_summary(), id="operator-output")
            yield Input(placeholder="Ask AnchorWorks or enter an operator note", id="chat-input")
        yield Footer()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "intake-path":
            self._handle_intake_path(event.value)
            event.input.value = ""
            return
        receipt = self.conversation_engine.answer(event.value)
        self.last_receipt = receipt
        self.query_one("#chat-output", Static).update(str(receipt.get("speech") or ""))
        self.query_one("#evidence-output", Static).update(_receipt_summary(receipt))
        event.input.value = ""

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "intake-action":
            return
        self.intake_action = str(event.value or "mapping")
        if self.intake_action == "mapping":
            text = "Mapping selected. Enter a file or directory path below."
        else:
            text = "Audit selected. Enter a source directory path below."
        self.query_one("#intake-output", Static).update(text)

    def _handle_intake_path(self, value: str) -> None:
        text = str(value or "").strip()
        if not text:
            self.query_one("#intake-output", Static).update("Path required.")
            return
        try:
            if self.intake_action == "mapping":
                result = self.store.map_path_to_user_counts_native(Path(text))
                self.query_one("#intake-output", Static).update(_native_mapping_summary(result))
                self.query_one("#counts-output", Static).update(self._counts_summary())
            else:
                from .intake_audit import audit_source_directory

                result = audit_source_directory(Path(text))
                self.query_one("#intake-output", Static).update(str(result))
            self.last_receipt = result
        except Exception as exc:
            self.query_one("#intake-output", Static).update(f"Intake action error: {exc}")

    def _counts_summary(self) -> str:
        try:
            status = self.store.binary_substrate_status()
        except Exception as exc:
            return f"Count status error: {exc}"
        return f"AWSC cells: {status.get('awsc_cell_count', 0)}\nRuntime: native C++ count ingest"

    def _missing_summary(self) -> str:
        try:
            queue = self.store.missing_anchor_review_queue(limit=5)
        except Exception as exc:
            return f"Missing review error: {exc}"
        return f"Total missing anchors: {queue.get('total_registry_anchors', 0)}\nPreview rows: {len(queue.get('entries') or [])}"

    def _operator_summary(self) -> str:
        return f"data_root: {self.data_root}\nui_runtime: terminal_operator_console\nchat_runtime: conversation_engine"


def run_operator(data_root: str | Path | None = None) -> None:
    AnchorWorksOperatorApp(data_root=data_root).run()


def _receipt_summary(receipt: dict[str, Any]) -> str:
    return "\n".join([
        f"engine: {receipt.get('selected_engine_path', '')}",
        f"lane: {receipt.get('evidence_lane', '')}",
        f"frame: {receipt.get('frame_type', '')}",
        f"represented: {', '.join(receipt.get('represented_anchors') or [])}",
        f"missing: {', '.join(receipt.get('missing_anchors') or [])}",
    ])


def _native_mapping_summary(result: dict[str, Any]) -> str:
    receipt = result.get("receipt") or {}
    manifest = result.get("manifest") or {}
    return "\n".join([
        f"runtime: {result.get('runtime', '')}",
        f"ok: {result.get('ok')}",
        f"updated_cells: {receipt.get('updated_cell_count', 0)}",
        f"records: {receipt.get('record_count', 0)}",
        f"missing_names: {manifest.get('missing_anchor_count', 0)}",
        f"source_local_symbols: {manifest.get('source_local_symbol_count', 0)}",
        f"raw_text_in_count_spine: {result.get('raw_text_in_count_spine')}",
        f"counts_root: {result.get('active_binary_counts_root', '')}",
    ])
