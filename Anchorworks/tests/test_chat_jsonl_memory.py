from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from AnchorWorks.app import create_app
from AnchorWorks.clearspeak import ClearSpeakService
from AnchorWorks.conversation import ConversationEngine
from AnchorWorks.document_answer import DocumentAnswerAssembler
from AnchorWorks.store import LexiconStore


def _seed_force_root(root: Path) -> None:
    canonical = root / "Canonical"
    canonical.mkdir()
    (canonical / "canonical_F.json").write_text(
        json.dumps([{"word": "force", "symbol": "0x0000000001"}]),
        encoding="utf-8",
    )
    structural = root / "Structural"
    structural.mkdir()
    (structural / "structural.json").write_text("[]", encoding="utf-8")


def test_record_chat_appends_today_jsonl_without_count_writes(tmp_path: Path) -> None:
    _seed_force_root(tmp_path)
    store = LexiconStore(tmp_path)
    engine = ConversationEngine(store, ClearSpeakService(store), DocumentAnswerAssembler(store))

    result = engine.answer("hello there", conversation_id="daily", record_chat=True)

    memory = result["memory_write_status"]
    assert memory["chat_recorded"] is True
    assert memory["counts_written"] is False
    assert memory["daily_consolidation_required"] is True
    assert "chat_record_blocked" not in memory
    assert result["writes_allowed"] == {"chat": True, "counts": False, "lifetime": False, "lexicon": False}

    log_path = Path(memory["chat_log_path"])
    rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["schema_version"] == "anchorworks_chat_turn@1"
    assert rows[0]["conversation_id"] == "daily"
    assert rows[0]["block_id"] == "b000001"
    assert rows[0]["line_id"] == "l000001"
    assert rows[0]["raw_text"] == "hello there"
    assert rows[0]["clean_text"] == "hello there"
    assert not (tmp_path / "State" / "user" / "chat_counts").exists()


def test_record_chat_false_does_not_create_jsonl(tmp_path: Path) -> None:
    _seed_force_root(tmp_path)
    store = LexiconStore(tmp_path)
    engine = ConversationEngine(store, ClearSpeakService(store), DocumentAnswerAssembler(store))

    result = engine.answer("hello there", conversation_id="daily", record_chat=False)

    assert result["memory_write_status"]["chat_recorded"] is False
    assert list(store.chat_logs_dir.glob("*.jsonl")) == []
    assert not (tmp_path / "State" / "user" / "chat_counts").exists()


def test_conversation_greeting_reflects_user_greeting_not_hardcoded_morning(tmp_path: Path) -> None:
    _seed_force_root(tmp_path)
    store = LexiconStore(tmp_path)
    engine = ConversationEngine(store, ClearSpeakService(store), DocumentAnswerAssembler(store))

    result = engine.answer("good afternoon", conversation_id="daily", record_chat=True)

    assert result["input_kind"] == "conversation"
    assert "afternoon" in result["speech"].casefold()
    assert "good morning" not in result["speech"].casefold()
    assert result["memory_write_status"]["counts_written"] is False


def test_chat_today_and_search_read_jsonl_working_record(tmp_path: Path) -> None:
    _seed_force_root(tmp_path)
    store = LexiconStore(tmp_path)
    first = store.memory.append_chat_turn("force question", conversation_id="daily")
    store.memory.append_chat_turn("plain answer", conversation_id="daily")

    today = store.memory.today_chat_log(day_id=first["day_id"])
    search = store.memory.search_today_chat("force", day_id=first["day_id"])

    assert today["record_count"] == 2
    assert [row["block_id"] for row in today["records"]] == ["b000001", "b000002"]
    assert search["match_count"] == 1
    assert search["matches"][0]["clean_text"] == "force question"


def test_daily_chat_consolidation_runs_native_user_counts(tmp_path: Path) -> None:
    _seed_force_root(tmp_path)
    store = LexiconStore(tmp_path)
    appended = store.memory.append_chat_turn("force blorxium", conversation_id="daily")

    receipt = store.memory.consolidate_day_chat(day_id=appended["day_id"], window_radius=1)

    assert receipt["ok"] is True
    assert receipt["counts_written"] is True
    assert receipt["record_count"] == 1
    assert receipt["native_mapping"]["runtime"] == "native_cpp_intake_text"
    assert receipt["native_mapping"]["raw_text_in_count_spine"] is False
    assert Path(receipt["receipt_path"]).exists()
    assert Path(receipt["prepared_text_path"]).read_text(encoding="utf-8") == "force blorxium\n"
    assert (store.symbol_counts_binary_dir / "cells" / "00" / "0000000001.cell").exists()
    source_local_symbol = receipt["native_mapping"]["missing"]["source_local_symbols"][0]["symbol"][2:]
    assert (store.symbol_counts_binary_dir / "cells" / source_local_symbol[:2] / f"{source_local_symbol}.cell").exists()


def test_chat_api_exposes_jsonl_working_record_and_native_consolidation(tmp_path: Path) -> None:
    _seed_force_root(tmp_path)
    client = TestClient(create_app(tmp_path))

    send = client.post(
        "/api/chat/send",
        json={"text": "force blorxium", "conversation_id": "daily", "record_chat": True},
    )
    assert send.status_code == 200
    day_id = send.json()["memory_write_status"]["day_id"]

    today = client.get("/api/chat/today", params={"day_id": day_id})
    assert today.status_code == 200
    assert today.json()["record_count"] == 1

    search = client.post("/api/chat/search-today", json={"query": "blorxium", "day_id": day_id})
    assert search.status_code == 200
    assert search.json()["match_count"] == 1

    consolidate = client.post("/api/chat/consolidate-day", json={"day_id": day_id, "window_radius": 1})
    assert consolidate.status_code == 200
    payload = consolidate.json()
    assert payload["counts_written"] is True
    assert payload["native_mapping"]["runtime"] == "native_cpp_intake_text"
