from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace
from pathlib import Path

from AnchorWorks.cli_shell import local_answer
from AnchorWorks.count_corpus_search import rank_corpus_documents_from_count_terms
from AnchorWorks.document_answer import DocumentAnswerAssembler
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


def test_document_answer_passage_hits_do_not_count_as_success_without_query_frame_answer() -> None:
    class FakeStore:
        def recognize_query_anchors(self, query: str) -> dict:
            anchors = ["lasers", "important", "guidance", "systems"]
            return {
                "schema_version": "anchorworks_lexicon_recognition@1",
                "query": query,
                "query_anchors": anchors,
                "represented_anchors": anchors,
                "missing_anchors": [],
                "input_kind": "question",
                "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
            }

        def search_flat_document_evidence(self, *_args, **_kwargs) -> dict:
            return {
                "source_passages": [
                    {
                        "source_name": "unrelated_source.md",
                        "saved_document_name": "unrelated_source.md",
                        "text": "Magnetic resonance calibration requires stable timing references.",
                        "raw_block_text": "Magnetic resonance calibration requires stable timing references.",
                        "block_id": 1,
                        "line_start": 1,
                        "line_end": 1,
                        "score": 1,
                    }
                ]
            }

    result = DocumentAnswerAssembler(FakeStore()).answer("why are lasers important in guidance systems?")

    assert result.ok is False
    assert result.speech == "No document-backed answer passed the query-frame check yet."


def test_auto_answer_uses_counts_not_document_answer_by_default() -> None:
    class FakeDocumentAnswer:
        def answer(self, *_args, **_kwargs):
            raise AssertionError("document answers must be explicit RAG/document mode only")

    class FakeClearSpeak:
        def query(self, query: str, *, limit: int = 6):
            return SimpleNamespace(to_dict=lambda: {
                "query": query,
                "speech": "counts refusal",
                "response": "counts refusal",
                "evidence": [],
                "citations": [],
            })

    ctx = SimpleNamespace(document_answer=FakeDocumentAnswer(), clearspeak=FakeClearSpeak())

    result = local_answer(ctx, "what is the grounded answer?")

    assert result["engine"] == "clearspeak_counts"
    assert result["evidence_mode"] == "counts"
    assert result["speech"] == "counts refusal"


def test_document_answer_requires_explicit_document_mode() -> None:
    class FakeDocumentAnswer:
        def answer(self, query: str, *, limit: int = 6):
            return SimpleNamespace(to_dict=lambda: {
                "ok": True,
                "query": query,
                "speech": "document answer",
                "response": "document answer",
                "evidence": [],
                "citations": [],
                "engine": "document_answer_assembler",
            })

    class FakeClearSpeak:
        def query(self, *_args, **_kwargs):
            raise AssertionError("explicit document mode should not fall through to counts")

    ctx = SimpleNamespace(document_answer=FakeDocumentAnswer(), clearspeak=FakeClearSpeak())

    result = local_answer(ctx, "what is the document answer?", evidence_mode="documents")

    assert result["engine"] == "document_answer_assembler"
    assert result["speech"] == "document answer"


def test_store_init_does_not_create_flat_document_cache(tmp_path: Path) -> None:
    _seed_force_root(tmp_path)

    LexiconStore(tmp_path)

    assert not (tmp_path / "State" / "flat_documents").exists()


def test_count_corpus_search_ranks_docs_from_count_supported_terms() -> None:
    query_anchors = ["laser", "guidance"]
    count_terms = [
        {"anchor": "navigation", "score": 10, "observations": 3},
        {"anchor": "target", "score": 5, "observations": 2},
    ]
    corpus_rows = [
        {"_id": "wrong", "title": "Other", "text": "soil chemistry and plant roots"},
        {"_id": "right", "title": "Laser guidance", "text": "laser navigation target guidance system"},
    ]

    ranked = rank_corpus_documents_from_count_terms(
        query_anchors=query_anchors,
        count_terms=count_terms,
        corpus_rows=corpus_rows,
        top_k=2,
    )

    assert ranked[0]["doc_id"] == "right"
    assert ranked[0]["score"] > ranked[1]["score"]
    assert "navigation" in ranked[0]["matched_count_terms"]
