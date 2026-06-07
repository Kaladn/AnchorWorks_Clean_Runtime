from __future__ import annotations

import json
import subprocess
from pathlib import Path

from AnchorWorks.symbol_count_native import build_native_symbol_counts, native_executable_path


def _exe() -> Path:
    exe = native_executable_path()
    if exe.exists():
        return exe
    return build_native_symbol_counts()


def test_native_text_ingest_merges_directly_to_awsc_cells(tmp_path: Path) -> None:
    source = tmp_path / "prepared.txt"
    source.write_text("force blorxium", encoding="utf-8")
    authority = tmp_path / "authority.json"
    authority.write_text(
        json.dumps({
            "anchors": [
                {"anchor": "force", "symbol": "0x0000000001", "authority": "canonical"},
                {"anchor": "blorxium", "symbol": "0xE000000001", "authority": "user_lexicon"},
            ],
        }),
        encoding="utf-8",
    )
    output_root = tmp_path / "counts"
    manifest = tmp_path / "manifest.json"
    missing = tmp_path / "missing.json"

    result = subprocess.run(
        [
            str(_exe()),
            "intake-text",
            "--input",
            str(source),
            "--authority",
            str(authority),
            "--merge-output",
            str(output_root),
            "--manifest",
            str(manifest),
            "--missing",
            str(missing),
            "--window-radius",
            "1",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    receipt = json.loads(result.stdout)
    assert receipt["ok"] is True
    assert receipt["updated_cell_count"] == 2
    assert (output_root / "cells" / "00" / "0000000001.cell").exists()
    assert (output_root / "cells" / "E0" / "E000000001.cell").exists()
    assert not list(tmp_path.glob("*.awss"))
    assert json.loads(manifest.read_text(encoding="utf-8"))["raw_text_in_count_spine"] is False


def test_native_directory_ingest_merges_text_like_sources_and_reports_skips(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "one.txt").write_text("force blorxium", encoding="utf-8")
    (docs / "two.md").write_text("force graph", encoding="utf-8")
    (docs / "image.png").write_bytes(b"\x89PNG\r\n")
    generated = docs / "State" / "cache"
    generated.mkdir(parents=True)
    (generated / "skip.txt").write_text("force should skip", encoding="utf-8")
    authority = tmp_path / "authority.json"
    authority.write_text(
        json.dumps({
            "anchors": [
                {"anchor": "force", "symbol": "0x0000000001", "authority": "canonical"},
                {"anchor": "blorxium", "symbol": "0xE000000001", "authority": "user_lexicon"},
            ],
        }),
        encoding="utf-8",
    )
    output_root = tmp_path / "counts"
    manifest = tmp_path / "manifest.json"
    missing = tmp_path / "missing.json"

    result = subprocess.run(
        [
            str(_exe()),
            "intake-dir",
            "--input-dir",
            str(docs),
            "--authority",
            str(authority),
            "--merge-output",
            str(output_root),
            "--manifest",
            str(manifest),
            "--missing",
            str(missing),
            "--window-radius",
            "1",
            "--source-local-missing",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    receipt = json.loads(result.stdout)
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert receipt["ok"] is True
    assert receipt["command"] == "intake-dir"
    assert manifest_payload["file_count"] == 2
    assert manifest_payload["skipped_file_count"] == 2
    assert sorted(row["reason"] for row in manifest_payload["skipped_files"]) == [
        "generated_runtime_path",
        "unsupported_suffix",
    ]
    assert (output_root / "cells" / "00" / "0000000001.cell").exists()
