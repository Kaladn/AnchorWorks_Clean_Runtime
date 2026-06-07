from __future__ import annotations

import json
from pathlib import Path

from AnchorWorks.store import LexiconStore
from AnchorWorks.store_modules.paths import StorePaths
from AnchorWorks.symbol_count_cells import read_symbol_cell
from AnchorWorks.symbol_genome_pool import (
    USER_LEXICON_SYMBOL_BASE,
    USER_LEXICON_SYMBOL_CAPACITY,
    SymbolGenomePool,
    symbol_genome_identity_from_index,
)


def test_user_mapping_pipeline_calls_native_and_writes_user_awsc_cells(tmp_path: Path) -> None:
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

    result = LexiconStore(tmp_path).map_document_to_user_counts_native(source, window_radius=1)

    assert result["ok"] is True
    assert result["runtime"] == "native_cpp_intake_text"
    assert result["raw_text_in_count_spine"] is False
    assert result["receipt"]["updated_cell_count"] == 2
    assert result["manifest"]["merge_output"] == result["active_binary_counts_root"]
    assert Path(result["active_binary_counts_root"], "cells", "00", "0000000001.cell").exists()
    source_local_symbols = result["missing"]["source_local_symbols"]
    assert source_local_symbols[0]["anchor"] == "blorxium"
    assert source_local_symbols[0]["symbol"].startswith("0xF")
    local_hex = source_local_symbols[0]["symbol"][2:]
    assert Path(result["active_binary_counts_root"], "cells", local_hex[:2], f"{local_hex}.cell").exists()


def test_active_lexicon_and_binary_store_paths_are_user_side(tmp_path: Path) -> None:
    store = LexiconStore(tmp_path)

    assert store.user_lexicon_path == tmp_path / "State" / "user" / "user_lexicon" / "anchors.json"
    assert store.symbol_genome_pool_dir == tmp_path / "State" / "user" / "user_lexicon" / "symbol_genome_pool"
    assert store.symbol_counts_binary_dir == tmp_path / "State" / "user" / "user_counts" / "symbol_counts_binary"
    assert store.paths.user_lexicon_path == store.user_lexicon_path
    assert store.paths.symbol_genome_pool_dir == store.symbol_genome_pool_dir
    assert store.paths.symbol_counts_binary_dir == store.symbol_counts_binary_dir
    assert store.canonical_symbol_counts_binary_dir == tmp_path / "State" / "symbol_counts_binary"
    assert store.symbol_counts_binary_dir != store.canonical_symbol_counts_binary_dir


def test_store_rejects_code_folder_as_runtime_root(tmp_path: Path) -> None:
    repo_root = tmp_path / "AnchorWorks_Clean_Runtime"
    code_root = repo_root / "Anchorworks"
    code_root.mkdir(parents=True)

    try:
        LexiconStore(code_root)
    except RuntimeError as exc:
        assert "code folder cannot be used as AnchorWorks data root" in str(exc)
    else:
        raise AssertionError("LexiconStore must reject Anchorworks code folder as data root")


def test_store_paths_binary_counts_alias_points_to_user_side(tmp_path: Path) -> None:
    paths = StorePaths(tmp_path)

    assert paths.symbol_counts_binary_dir == tmp_path / "State" / "user" / "user_counts" / "symbol_counts_binary"
    assert paths.symbol_genome_pool_dir == tmp_path / "State" / "user" / "user_lexicon" / "symbol_genome_pool"
    assert paths.canonical_symbol_counts_binary_dir == tmp_path / "State" / "symbol_counts_binary"


def test_user_symbol_genome_pool_is_ten_million_user_side_slots(tmp_path: Path) -> None:
    store = LexiconStore(tmp_path)

    status = store.symbol_genome_status()

    assert status["capacity"] == 10_000_000
    assert status["remaining"] == 10_000_000
    assert Path(status["manifest_path"]).parent == store.user_lexicon_dir / "symbol_genome_pool"
    assert status["slot_materialization"] == "cursor_manifest_only"


def test_user_symbol_genome_pool_boundary_and_no_range_collision(tmp_path: Path) -> None:
    pool = SymbolGenomePool(tmp_path / "pool", capacity=10_000_000)
    manifest = pool._read_manifest()
    manifest["next_index"] = 9_999_999
    manifest["assigned_count"] = 9_999_999
    pool._write_manifest(manifest)

    last = pool.allocate("last-user-slot", authority="user_lexicon")

    assert last["allocation_index"] == 9_999_999
    assert last["symbol_index"] == USER_LEXICON_SYMBOL_BASE + 9_999_999
    assert last["symbol_index"] < USER_LEXICON_SYMBOL_BASE + USER_LEXICON_SYMBOL_CAPACITY
    try:
        pool.allocate("overflow", authority="user_lexicon")
    except ValueError as exc:
        assert "symbol genome pool exhausted" in str(exc)
    else:
        raise AssertionError("user-side 10M pool must reject allocation 10,000,001")


def test_user_symbol_range_never_collides_with_canonical_or_source_local() -> None:
    first = symbol_genome_identity_from_index("first", authority="user_lexicon", allocation_index=0)
    last = symbol_genome_identity_from_index("last", authority="user_lexicon", allocation_index=9_999_999)
    canonical_edge = symbol_genome_identity_from_index("canonical-edge", authority="canonical", allocation_index=USER_LEXICON_SYMBOL_BASE - 1)
    source_local_first = symbol_genome_identity_from_index("source", authority="source_local", allocation_index=0)

    assert first["symbol_index"] == USER_LEXICON_SYMBOL_BASE
    assert first["symbol_index"] < last["symbol_index"]
    assert canonical_edge["symbol_index"] < first["symbol_index"]
    assert last["symbol_index"] < source_local_first["symbol_index"]


def test_user_count_seed_creates_empty_cells_for_all_canonical_symbols(tmp_path: Path) -> None:
    canonical = tmp_path / "Canonical"
    canonical.mkdir()
    (canonical / "canonical_F.json").write_text(
        json.dumps([
            {"word": "force", "symbol": "0x0000000001"},
            {"word": "frame", "symbol": "0x1000000718"},
        ]),
        encoding="utf-8",
    )
    structural = tmp_path / "Structural"
    structural.mkdir()
    (structural / "structural.json").write_text("[]", encoding="utf-8")
    store = LexiconStore(tmp_path)

    result = store.ensure_user_symbol_counts_seeded()

    assert result["canonical_placeholder_cells_created"] == 2
    low_cell = store.symbol_counts_binary_dir / "cells" / "00" / "0000000001.cell"
    high_cell = store.symbol_counts_binary_dir / "cells" / "10" / "1000000718.cell"
    assert low_cell.exists()
    assert high_cell.exists()
    assert read_symbol_cell(low_cell).relations == []
    assert read_symbol_cell(high_cell).relations == []
    assert result["acknowledgement"]["canonical_authority_placeholder_seed"] is True


def test_user_count_seed_uses_canonical_symbols_not_anchor_deduplication(tmp_path: Path) -> None:
    canonical = tmp_path / "Canonical"
    canonical.mkdir()
    (canonical / "canonical_F.json").write_text(
        json.dumps([
            {"word": "force", "symbol": "0x0000000001"},
            {"word": "force", "symbol": "0x40021FB596"},
        ]),
        encoding="utf-8",
    )
    structural = tmp_path / "Structural"
    structural.mkdir()
    (structural / "structural.json").write_text("[]", encoding="utf-8")
    store = LexiconStore(tmp_path)

    result = store.ensure_user_symbol_counts_seeded()

    assert result["canonical_placeholder_cells_created"] == 2
    assert (store.symbol_counts_binary_dir / "cells" / "00" / "0000000001.cell").exists()
    assert (store.symbol_counts_binary_dir / "cells" / "40" / "40021FB596.cell").exists()


def test_user_count_seed_includes_canonical_structural_symbols(tmp_path: Path) -> None:
    canonical = tmp_path / "Canonical"
    canonical.mkdir()
    (canonical / "canonical_F.json").write_text(
        json.dumps([{"word": "force", "symbol": "0x0000000001"}]),
        encoding="utf-8",
    )
    (canonical / "structural.json").write_text(
        json.dumps([{"word": "{", "symbol": "0x40021FB596"}]),
        encoding="utf-8",
    )
    structural = tmp_path / "Structural"
    structural.mkdir()
    (structural / "structural.json").write_text("[]", encoding="utf-8")
    store = LexiconStore(tmp_path)

    result = store.ensure_user_symbol_counts_seeded()

    assert result["canonical_placeholder_cells_created"] == 2
    assert (store.symbol_counts_binary_dir / "cells" / "40" / "40021FB596.cell").exists()


def test_user_lexicon_seed_copies_canonical_and_structural_symbols_once(tmp_path: Path) -> None:
    canonical = tmp_path / "Canonical"
    canonical.mkdir()
    (canonical / "canonical_M.json").write_text(
        json.dumps([
            {"word": "magnetism", "symbol": "0x10000260AB"},
            {"word": "magnetism", "symbol": "0x10000260AB"},
        ]),
        encoding="utf-8",
    )
    structural = tmp_path / "Structural"
    structural.mkdir()
    (structural / "structural.json").write_text(
        json.dumps([{"word": "?", "symbol": "0x4000000001"}]),
        encoding="utf-8",
    )
    store = LexiconStore(tmp_path)

    first = store.ensure_user_lexicon_seeded()
    second = store.ensure_user_lexicon_seeded()

    assert first["canonical_entries_seeded"] == 2
    assert second["canonical_entries_seeded"] == 0
    entries = json.loads(store.user_lexicon_path.read_text(encoding="utf-8"))
    assert [(row["word"], row["symbol"], row["authority"]) for row in entries] == [
        ("?", "0x4000000001", "canonical_seed"),
        ("magnetism", "0x10000260AB", "canonical_seed"),
    ]
    found = store._find_entry("magnetism")
    assert found is not None
    assert found[0]["symbol"] == "0x10000260AB"
    assert found[1] == "user"
