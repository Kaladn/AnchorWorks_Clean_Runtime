from __future__ import annotations

import json
import subprocess
from pathlib import Path

from AnchorWorks.store import LexiconStore
from AnchorWorks.symbol_count_native import build_native_symbol_counts, native_executable_path


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPO_ROOT / "src" / "AnchorWorks"


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


def _native_exe() -> Path:
    exe = native_executable_path()
    if exe.exists():
        return exe
    return build_native_symbol_counts()


def test_counts_are_one_native_binary_file_with_no_cell_or_json_count_fallbacks(tmp_path: Path) -> None:
    cell_extension = "." + "cell"
    merge_word = "merge"
    cell_word = "cell"
    counts_word = "counts"
    forbidden_source = [
        f'"{cell_extension}"',
        f"'{cell_extension}'",
        "--" + merge_word + "-output",
        merge_word + "-stream",
        merge_word + "-symbol-stream",
        "updated_" + cell_word + "_count",
        "symbol_" + counts_word + "_binary_dir",
        "canonical_symbol_" + counts_word + "_binary_dir",
        "user_count_" + "acknowledgement",
        "lifetime_co_occurrence_" + counts_word + ".json",
        "read_" + cell_word + "(",
        "write_" + cell_word + "(",
        "verify_" + "root(",
        "score_binary_" + counts_word + "(",
        "inspect_" + cell_word + "(",
        "verify_binary_" + counts_word + "(",
        "symbol_count_" + cell_word + "s",
    ]
    offenders: list[str] = []
    for path in SOURCE_ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".py", ".cpp", ".h", ".txt", ".md"}:
            continue
        text = path.read_text(encoding="utf-8")
        for snippet in forbidden_source:
            if snippet in text:
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {snippet}")
    assert offenders == []

    _seed_force_root(tmp_path)
    source = tmp_path / "source.txt"
    source.write_text("force blorxium", encoding="utf-8")
    store = LexiconStore(tmp_path)

    result = store.map_document_to_user_counts_native(source, window_radius=1)

    count_path = Path(result["active_binary_counts_path"])
    assert result["ok"] is True
    assert result["runtime"] == "native_cpp_intake_text"
    assert result["receipt"]["record_count"] == 2
    assert count_path == tmp_path / "State" / "user" / "user_counts" / "symbol_counts.bin"
    assert count_path.exists()
    assert count_path.stat().st_size == 48
    assert list(count_path.parent.glob("*.json")) == []
    assert list(count_path.parent.rglob("*" + cell_extension)) == []
    assert not (count_path.parent / "symbol_counts_binary").exists()

    scored = subprocess.run(
        [
            str(_native_exe()),
            "score-stream",
            "--input",
            str(count_path),
            "--context",
            "0x0000000001",
            "--top-k",
            "8",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(scored.stdout)
    assert payload["ok"] is True
    assert payload["command"] == "score-stream"
    assert payload["record_count"] == 2
    assert payload["candidate_count"] >= 1
