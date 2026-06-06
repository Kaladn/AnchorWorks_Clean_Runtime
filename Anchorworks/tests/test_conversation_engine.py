from __future__ import annotations

from pathlib import Path

from AnchorWorks.app import create_app
from AnchorWorks.conversation import ConversationEngine


def test_conversation_engine_greeting_receipt_does_not_write_memory():
    app = create_app(Path(r"D:\AnchorWorks_Clean_Runtime"))
    engine: ConversationEngine = app.state.conversation_engine

    receipt = engine.answer("good morning")

    assert receipt["schema_version"] == "anchorworks_conversation_receipt@1"
    assert receipt["input_kind"] == "conversation"
    assert receipt["evidence_lane"] == "conversation_style"
    assert receipt["memory_write_status"]["counts_written"] is False
    assert receipt["memory_write_status"]["chat_recorded"] is False
    assert receipt["speech"]


def test_conversation_engine_correction_is_context_not_count_walk():
    app = create_app(Path(r"D:\AnchorWorks_Clean_Runtime"))
    receipt = app.state.conversation_engine.answer("no, that is not correct")

    assert receipt["input_kind"] == "correction"
    assert receipt["evidence_lane"] == "no_source_support"
    assert receipt["memory_write_status"]["counts_written"] is False
    assert receipt["selected_engine_path"] == "conversation_context_ack"


def test_conversation_engine_question_receipt_has_required_trace_fields():
    app = create_app(Path(r"D:\AnchorWorks_Clean_Runtime"))
    receipt = app.state.conversation_engine.answer("What is magnetism?")

    for key in [
        "represented_anchors",
        "missing_anchors",
        "frame_type",
        "selected_engine_path",
        "evidence_lane",
        "accepted_candidates",
        "rejected_candidates",
        "speech",
        "memory_write_status",
    ]:
        assert key in receipt
    assert receipt["memory_write_status"]["counts_written"] is False


def test_chat_send_api_returns_conversation_receipt():
    app = create_app(Path(r"D:\AnchorWorks_Clean_Runtime"))
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.post("/api/chat/send", json={"text": "good morning"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "anchorworks_conversation_receipt@1"
    assert payload["memory_write_status"]["counts_written"] is False


def test_chat_send_does_not_record_memory(tmp_path):
    app = create_app(tmp_path)
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.post(
        "/api/chat/send",
        json={
            "text": "good morning",
            "conversation_id": "operator-session",
            "record_chat": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    status = payload["memory_write_status"]
    assert status["chat_record_requested"] is True
    assert status["chat_recorded"] is False
    assert status["chat_record_blocked"] == "awaiting_whiteboard_memory_scaffold"
    assert status["counts_written"] is False
    assert status["lifetime_written"] is False
    removed_placeholder_dir = tmp_path / "State" / "user" / ("chat_" + "memory")
    assert not removed_placeholder_dir.exists()
    assert not (tmp_path / "State" / "lifetime_co_occurrence_counts.json").exists()
