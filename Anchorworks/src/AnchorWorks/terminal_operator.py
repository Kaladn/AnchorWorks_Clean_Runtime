from __future__ import annotations

from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Input, Static, TabbedContent, TabPane

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

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="body"):
            with TabbedContent(initial="chat"):
                with TabPane("Chat", id="chat"):
                    yield Static("AnchorWorks conversation runtime is ready.", id="chat-output")
                with TabPane("Evidence Trace", id="evidence"):
                    yield Static("No receipt yet.", id="evidence-output")
                with TabPane("Intake Jobs", id="intake"):
                    yield Static("Use CLI intake jobs or future job controls here.", id="intake-output")
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
        receipt = self.conversation_engine.answer(event.value)
        self.last_receipt = receipt
        self.query_one("#chat-output", Static).update(str(receipt.get("speech") or ""))
        self.query_one("#evidence-output", Static).update(_receipt_summary(receipt))
        event.input.value = ""

    def _counts_summary(self) -> str:
        try:
            status = self.store.binary_substrate_status()
        except Exception as exc:
            return f"Count status error: {exc}"
        return f"AWSC cells: {status.get('awsc_cell_count', 0)}\nAWSS exists: {status.get('awss_stream_exists', False)}"

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
