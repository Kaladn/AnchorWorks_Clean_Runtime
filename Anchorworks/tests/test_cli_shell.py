from __future__ import annotations

from types import SimpleNamespace

from AnchorWorks.cli_shell import (
    ShellContext,
    execute_shell_line,
    intake_readiness_from_preview,
    local_answer,
    operator_surface_snapshot,
    parse_shell_line,
    render_evidence_rows,
)


class FakeAnswer:
    def __init__(self, payload):
        self._payload = payload

    def to_dict(self):
        return dict(self._payload)


class FakeDocumentAnswer:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def answer(self, query, limit=6):
        self.calls.append((query, limit))
        return FakeAnswer(self.payload)


class FakeClearSpeak:
    def __init__(self):
        self.calls = []

    def status(self):
        return {"ok": True, "name": "ClearSpeak", "count_source": "test"}

    def query(self, query, limit=6):
        self.calls.append((query, limit))
        return FakeAnswer({"speech": "raw count fallback", "engine": "raw"})


def test_parse_plain_text_as_ask():
    parsed = parse_shell_line("what is truevision?")

    assert parsed.command == "ask"
    assert parsed.args == "what is truevision?"


def test_parse_slash_command():
    parsed = parse_shell_line("/cloud truevision")

    assert parsed.command == "cloud"
    assert parsed.args == "truevision"


def test_local_answer_prefers_document_answer_before_raw_counts():
    document_answer = FakeDocumentAnswer({
        "ok": True,
        "speech": "Truevision is a visual state path.",
        "engine": "document_answer_assembler",
    })
    clearspeak = FakeClearSpeak()
    ctx = ShellContext(
        store=SimpleNamespace(),
        clearspeak=clearspeak,
        document_answer=document_answer,
        data_root=None,
    )

    result = local_answer(ctx, "what is truevision?", limit=6)

    assert result["speech"] == "Truevision is a visual state path."
    assert result["engine"] == "document_answer_assembler"
    assert document_answer.calls == [("what is truevision?", 6)]
    assert clearspeak.calls == []


def test_execute_shell_line_quit_returns_false():
    ctx = ShellContext(
        store=SimpleNamespace(),
        clearspeak=FakeClearSpeak(),
        document_answer=FakeDocumentAnswer({"ok": False}),
        data_root=None,
    )

    assert execute_shell_line(ctx, "/quit") is False


def test_render_evidence_rows_accepts_dict_evidence():
    rows = render_evidence_rows({
        "evidence": {
            "source": "flat_symbolic_document",
            "source_name": "law_packet",
            "text": "force includes magnetism",
        },
        "citations": {
            "source": "doc",
            "coord": "block 1",
        },
    })

    assert rows[0][0] == "evidence"
    assert rows[0][1] == "flat_symbolic_document"
    assert rows[1][0] == "citation"


def test_intake_readiness_marks_missing_anchors_blocked():
    readiness = intake_readiness_from_preview({
        "paragraph_count": 2,
        "known_anchor_count": 5,
        "missing_anchor_count": 3,
        "missing_anchor_observations": 7,
    })

    assert readiness["status"] == "blocked_missing_anchors"
    assert readiness["ready"] is False
    assert readiness["missing_anchor_count"] == 3


def test_intake_readiness_marks_visual_preview_held():
    readiness = intake_readiness_from_preview({
        "visual_preview_only": True,
        "known_anchor_count": 4,
        "missing_anchor_count": 0,
    })

    assert readiness["status"] == "visual_held"
    assert readiness["ready"] is False


def test_intake_readiness_marks_clean_preview_ready():
    readiness = intake_readiness_from_preview({
        "paragraph_count": 1,
        "known_anchor_count": 4,
        "missing_anchor_count": 0,
    })

    assert readiness["status"] == "ready"
    assert readiness["ready"] is True


def test_operator_surface_snapshot_uses_runtime_status_methods():
    store = SimpleNamespace(
        user_storage_status=lambda: {"state_dir": "state"},
        binary_substrate_status=lambda: {"source_local_counts": {"exists": True}},
        counts_status=lambda: {"maps": 3},
        flat_document_files=lambda: {"raw_files": [1, 2], "symbolic_files": [1]},
        missing_anchor_review_queue=lambda limit=1: {"entries": [1], "total_registry_anchors": 9},
    )
    ctx = ShellContext(
        store=store,
        clearspeak=FakeClearSpeak(),
        document_answer=FakeDocumentAnswer({"ok": False}),
        data_root=None,
    )

    snapshot = operator_surface_snapshot(ctx)

    assert snapshot["clearspeak"]["ok"] is True
    assert snapshot["documents"]["raw_files"] == 2
    assert snapshot["documents"]["symbolic_files"] == 1
    assert snapshot["missing_review"]["queued_preview"] == 1
