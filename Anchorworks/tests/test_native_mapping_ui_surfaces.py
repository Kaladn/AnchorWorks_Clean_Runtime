from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console

from AnchorWorks import cli_shell
from AnchorWorks.terminal_operator import _native_mapping_summary


def test_shell_help_exposes_native_mapping_command() -> None:
    assert "/map-native <path>" in cli_shell.HELP_TEXT
    assert "/intake-map <path>" in cli_shell.HELP_TEXT
    assert "/chat-today [day]" in cli_shell.HELP_TEXT
    assert "/chat-search <text>" in cli_shell.HELP_TEXT
    assert "/chat-consolidate [day]" in cli_shell.HELP_TEXT


def test_shell_intake_map_uses_native_user_count_pipeline(tmp_path: Path) -> None:
    canonical = tmp_path / "Canonical"
    canonical.mkdir()
    (canonical / "canonical_F.json").write_text(
        json.dumps([{"word": "force", "symbol": "0x0000000001"}]),
        encoding="utf-8",
    )
    structural = tmp_path / "Structural"
    structural.mkdir()
    (structural / "structural.json").write_text("[]", encoding="utf-8")
    source = tmp_path / "source.txt"
    source.write_text("force blorxium", encoding="utf-8")
    ctx = cli_shell.build_shell_context(tmp_path, console=Console(record=True))

    keep_running = cli_shell.execute_shell_line(ctx, f"/intake-map {source}")

    assert keep_running is True
    assert ctx.last_result["runtime"] == "native_cpp_intake_text"
    assert ctx.last_result["raw_text_in_count_spine"] is False


def test_shell_chat_commands_use_jsonl_and_native_consolidation(tmp_path: Path) -> None:
    canonical = tmp_path / "Canonical"
    canonical.mkdir()
    (canonical / "canonical_F.json").write_text(
        json.dumps([{"word": "force", "symbol": "0x0000000001"}]),
        encoding="utf-8",
    )
    structural = tmp_path / "Structural"
    structural.mkdir()
    (structural / "structural.json").write_text("[]", encoding="utf-8")
    ctx = cli_shell.build_shell_context(tmp_path, console=Console(record=True))
    appended = ctx.store.memory.append_chat_turn("force blorxium", conversation_id="daily")

    assert cli_shell.execute_shell_line(ctx, f"/chat-today {appended['day_id']}") is True
    assert ctx.last_result["record_count"] == 1
    assert cli_shell.execute_shell_line(ctx, f"/chat-search blorxium --day {appended['day_id']}") is True
    assert ctx.last_result["match_count"] == 1
    assert cli_shell.execute_shell_line(ctx, f"/chat-consolidate {appended['day_id']}") is True
    assert ctx.last_result["counts_written"] is True
    assert ctx.last_result["native_mapping"]["runtime"] == "native_cpp_intake_text"


def test_operator_mapping_summary_reports_native_proof() -> None:
    summary = _native_mapping_summary({
        "runtime": "native_cpp_intake_text",
        "ok": True,
        "receipt": {"updated_cell_count": 2, "record_count": 7},
        "manifest": {"missing_anchor_count": 1, "source_local_symbol_count": 1},
        "raw_text_in_count_spine": False,
        "active_binary_counts_root": "State/user/user_counts/symbol_counts_binary",
    })

    assert "runtime: native_cpp_intake_text" in summary
    assert "updated_cells: 2" in summary
    assert "raw_text_in_count_spine: False" in summary
