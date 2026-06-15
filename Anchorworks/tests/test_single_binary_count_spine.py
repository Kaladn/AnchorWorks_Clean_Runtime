from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace
from pathlib import Path

from AnchorWorks.cli_shell import local_answer
from AnchorWorks.clearspeak_attention import build_native_search_attention, build_renderer_handoff, render_from_handoff
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
    assert result["manifest"]["missing_anchor_count"] == 0
    assert result["manifest"]["source_local_symbol_count"] == 0
    assert result["intake_law"] == [
        "native_anchor_scan",
        "user_lexicon_admission",
        "native_symbol_count_append",
    ]
    assert result["pre_admitted_user_anchors"]["method"] == "native_missing_scan_loop"
    assert result["pre_admitted_user_anchors"]["passes"][0]["missing_anchor_count"] == 1
    assert result["pre_admitted_user_anchors"]["approved_count"] == 1
    assert result["pre_admitted_user_anchors"]["approved"][0]["word"] == "blorxium"
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

    user_entries = json.loads((tmp_path / "State" / "user" / "user_lexicon" / "anchors.json").read_text(encoding="utf-8"))
    user_by_word = {row["word"]: row for row in user_entries}
    assert user_by_word["force"]["authority"] == "user_lexicon"
    assert user_by_word["force"]["source_authority"] == "canonical_seed"
    assert user_by_word["blorxium"]["authority"] == "user_lexicon"

    authority_rows = json.loads(Path(result["authority_path"]).read_text(encoding="utf-8"))["anchors"]
    authority_by_anchor = {row["anchor"]: row for row in authority_rows}
    assert authority_by_anchor["force"]["authority"] == "user_lexicon"
    assert authority_by_anchor["blorxium"]["authority"] == "user_lexicon"


def test_user_binary_state_checkpoint_stays_outside_active_count_spine(tmp_path: Path) -> None:
    _seed_force_root(tmp_path)
    store = LexiconStore(tmp_path)
    store.ensure_user_lexicon_seeded()
    store.symbol_counts_binary_file.write_bytes(b"123456789012345678901234")

    result = store.checkpoint_user_binary_state(reason="unit_test")

    checkpoint_dir = Path(result["checkpoint_dir"])
    assert result["ok"] is True
    assert Path(result["count_backup_path"]).exists()
    assert Path(result["lexicon_backup_path"]).exists()
    assert checkpoint_dir.parent == tmp_path / "State" / "user" / "binary_state_backups"
    assert list((tmp_path / "State" / "user" / "user_counts").glob("*.json")) == []


def test_native_ingest_can_emit_aw_markdown_copy_with_block_line_coordinates(tmp_path: Path) -> None:
    _seed_force_root(tmp_path)
    source = tmp_path / "rag_source.txt"
    source.write_text(
        "force alpha\nsecond line\n\nthird block beta\nline two beta\nline three beta",
        encoding="utf-8",
    )
    store = LexiconStore(tmp_path)

    result = store.map_document_to_user_counts_native(source, window_radius=1, create_aw_md_copy=True)

    aw_copy = result["aw_copy"]
    assert aw_copy["created"] is True
    assert aw_copy["format"] == "anchorworks_aw_md_blocks@1"
    assert Path(aw_copy["path"]).exists()
    md_text = Path(aw_copy["path"]).read_text(encoding="utf-8")
    assert "source_file: rag_source.txt" in md_text
    assert "block_id: 0" in md_text
    assert "block_lines: 1-2" in md_text
    assert "doc_lines: 1-2" in md_text
    assert "block_id: 1" in md_text
    assert "block_lines: 1-3" in md_text
    assert "doc_lines: 4-6" in md_text

    blocks = result["manifest"]["blocks"]
    assert blocks[0]["source_file"] == "rag_source.txt"
    assert blocks[0]["block_id"] == 0
    assert blocks[0]["block_line_start"] == 1
    assert blocks[0]["block_line_end"] == 2
    assert blocks[0]["document_line_start"] == 1
    assert blocks[0]["document_line_end"] == 2
    assert blocks[0]["doc_line_start"] == 1
    assert blocks[0]["doc_line_end"] == 2
    assert blocks[1]["block_line_start"] == 1
    assert blocks[1]["block_line_end"] == 3
    assert blocks[1]["document_line_start"] == 4
    assert blocks[1]["document_line_end"] == 6
    assert blocks[1]["doc_line_start"] == 4
    assert blocks[1]["doc_line_end"] == 6


def test_native_search_maps_count_evidence_to_aw_block_coordinates(tmp_path: Path) -> None:
    _seed_force_root(tmp_path)
    source = tmp_path / "rag_source.txt"
    source.write_text(
        "Document ID: docA\nforce alpha\nsecond line\n\nDocument ID: docB\nthird block beta\nline two beta",
        encoding="utf-8",
    )
    store = LexiconStore(tmp_path)

    result = store.map_document_to_user_counts_native(source, window_radius=1, create_aw_md_copy=True)
    searched = subprocess.run(
        [
            str(_native_exe()),
            "search-aw",
            "--query",
            "beta",
            "--authority",
            result["authority_path"],
            "--counts",
            result["active_binary_counts_path"],
            "--manifest",
            result["manifest_path"],
            "--rag-copy",
            result["aw_copy"]["path"],
            "--top-k",
            "5",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(searched.stdout)
    assert payload["ok"] is True
    assert payload["command"] == "search-aw"
    assert payload["query_anchors"] == ["beta"]
    assert payload["represented_anchors"] == ["beta"]
    assert payload["missing_anchors"] == []
    assert payload["represented_anchor_count"] == 1
    assert payload["count_candidate_count"] >= 1
    assert payload["hits"]

    first_hit = payload["hits"][0]
    assert first_hit["doc_id"] == "docB"
    assert first_hit["source_file"] == "rag_source.txt"
    assert first_hit["block_id"] == 1
    assert first_hit["block_line_start"] == 1
    assert first_hit["block_line_end"] == 3
    assert first_hit["document_line_start"] == 5
    assert first_hit["document_line_end"] == 7
    assert first_hit["rag_copy"] == result["aw_copy"]["path"]
    assert first_hit["query_anchor_hits"] == ["beta"]


def test_native_search_ranks_sharp_claim_anchors_above_broad_topic_overlap(tmp_path: Path) -> None:
    _seed_force_root(tmp_path)
    source = tmp_path / "rag_source.txt"
    source.write_text(
        "\n\n".join(
            [
                "Document ID: broad\n"
                "Title: Alpha thalassemia trait subjects with anemia\n"
                "Abstract: Alpha thalassemia trait subjects with anemia were reviewed.",
                "Document ID: filler1\n"
                "Title: Anemia subjects\n"
                "Abstract: Subjects with anemia and trait markers were counted.",
                "Document ID: filler2\n"
                "Title: Alpha trait\n"
                "Abstract: Alpha trait subjects with thalassemia were counted.",
                "Document ID: sharp\n"
                "Title: Increased microerythrocyte count in homozygous alpha thalassaemia\n"
                "Abstract: Homozygous alpha thalassaemia includes microerythrocyte count and severe anaemia protection.",
            ]
        ),
        encoding="utf-8",
    )
    store = LexiconStore(tmp_path)

    result = store.map_document_to_user_counts_native(source, window_radius=1, create_aw_md_copy=True)
    searched = subprocess.run(
        [
            str(_native_exe()),
            "search-aw",
            "--query",
            "microerythrocyte severe homozygous alpha anemia thalassemia trait subjects",
            "--authority",
            result["authority_path"],
            "--counts",
            result["active_binary_counts_path"],
            "--manifest",
            result["manifest_path"],
            "--rag-copy",
            result["aw_copy"]["path"],
            "--top-k",
            "4",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(searched.stdout)

    assert payload["hits"][0]["doc_id"] == "sharp"
    assert "anaemia" in payload["hits"][0]["query_anchor_hits"]
    assert "thalassaemia" in payload["hits"][0]["query_anchor_hits"]


def test_native_block_index_search_uses_count_signal_without_manifest_scan(tmp_path: Path) -> None:
    _seed_force_root(tmp_path)
    source = tmp_path / "rag_source.txt"
    source.write_text(
        "\n\n".join(
            [
                "Document ID: broad\n"
                "Title: Alpha thalassemia trait subjects with anemia\n"
                "Abstract: Alpha thalassemia trait subjects with anemia were reviewed.",
                "Document ID: sharp\n"
                "Title: Increased microerythrocyte count in homozygous alpha thalassaemia\n"
                "Abstract: Homozygous alpha thalassaemia includes microerythrocyte count and severe anaemia protection.",
            ]
        ),
        encoding="utf-8",
    )
    store = LexiconStore(tmp_path)
    result = store.map_document_to_user_counts_native(source, window_radius=1, create_aw_md_copy=True)
    block_index = tmp_path / "State" / "user" / "native_indexes" / "rag_source.awbi"
    block_index.parent.mkdir(parents=True)

    indexed = subprocess.run(
        [
            str(_native_exe()),
            "build-aw-index",
            "--manifest",
            result["manifest_path"],
            "--authority",
            result["authority_path"],
            "--output",
            str(block_index),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    index_payload = json.loads(indexed.stdout)
    assert index_payload["ok"] is True
    assert index_payload["command"] == "build-aw-index"
    assert index_payload["block_count"] == 2
    assert index_payload["authority_anchor_count"] > 0
    assert block_index.exists()
    assert block_index.read_bytes()[:8] == b"AWBI0001"

    searched = subprocess.run(
        [
            str(_native_exe()),
            "search-aw",
            "--query",
            "microerythrocyte severe homozygous alpha anemia thalassemia trait subjects",
            "--counts",
            result["active_binary_counts_path"],
            "--block-index",
            str(block_index),
            "--rag-copy",
            result["aw_copy"]["path"],
            "--top-k",
            "2",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(searched.stdout)

    assert payload["search_surface"] == "native_block_index"
    assert payload["hits"][0]["doc_id"] == "sharp"
    assert payload["hits"][0]["query_anchor_hits"] == [
        "alpha",
        "anaemia",
        "homozygous",
        "microerythrocyte",
        "severe",
        "thalassaemia",
    ]


def test_attention_admits_native_search_coordinates_without_creating_truth() -> None:
    native_payload = {
        "ok": True,
        "command": "search-aw",
        "query": "microerythrocyte count",
        "query_anchors": ["microerythrocyte", "count"],
        "represented_anchor_count": 2,
        "count_candidate_count": 4,
        "hits": [
            {
                "doc_id": "18174210",
                "source_file": "beir_scifact_corpus_aw_intake.txt",
                "block_id": 2813,
                "block_line_start": 1,
                "block_line_end": 3,
                "document_line_start": 11253,
                "document_line_end": 11255,
                "rag_copy": "beir_scifact_corpus_aw_intake.txt.aw.md",
                "score": 8158,
                "query_anchor_hits": ["microerythrocyte", "count"],
                "count_candidate_anchor_hits": ["severe", "homozygous", "thalassaemia"],
            },
            {
                "doc_id": "noise",
                "source_file": "beir_scifact_corpus_aw_intake.txt",
                "block_id": 1,
                "block_line_start": 1,
                "block_line_end": 1,
                "document_line_start": 1,
                "document_line_end": 1,
                "rag_copy": "beir_scifact_corpus_aw_intake.txt.aw.md",
                "score": 2,
                "query_anchor_hits": ["count"],
                "count_candidate_anchor_hits": ["the", ".", "1"],
            },
        ],
    }

    attention = build_native_search_attention(native_payload, top_k=5)

    assert attention["schema_version"] == "anchorworks_attention_frame@2"
    assert attention["observed_data_truth"] is True
    assert attention["world_truth_claim"] is False
    assert attention["world_truth_promoted"] is False
    assert attention["writes_allowed"] == {"maps": False, "counts": False, "lifetime": False, "lexicon": False}
    assert attention["admitted_blocks"][0]["doc_id"] == "18174210"
    assert attention["admitted_blocks"][0]["block_id"] == 2813
    assert attention["admitted_blocks"][0]["document_line_start"] == 11253
    assert attention["admitted_blocks"][0]["document_line_end"] == 11255
    assert [row["anchor"] for row in attention["focus_candidates"][:3]] == ["severe", "homozygous", "thalassaemia"]
    assert all(row["anchor"] not in {"the", ".", "1"} for row in attention["focus_candidates"])


def test_n0_attention_rejects_regex_pollution_but_preserves_evidence_coordinates() -> None:
    native_payload = {
        "ok": True,
        "command": "search-aw",
        "query": "role glioma treatment response",
        "query_anchors": ["role", "glioma", "treatment", "response"],
        "represented_anchors": ["role", "glioma", "treatment", "response"],
        "missing_anchors": [],
        "represented_anchor_count": 4,
        "count_candidate_count": 8,
        "hits": [
            {
                "doc_id": "doc1",
                "source_file": "source.md",
                "block_id": 7,
                "block_line_start": 1,
                "block_line_end": 4,
                "document_line_start": 70,
                "document_line_end": 73,
                "rag_copy": "source.md.aw.md",
                "score": 200,
                "query_anchor_hits": ["role", "glioma"],
                "count_candidate_anchor_hits": ["the", "of", "in", "glioma-42", "treatment", "response", "tumor"],
            }
        ],
    }

    attention = build_native_search_attention(native_payload, top_k=8)

    assert attention["admission_status"] == "admitted"
    assert attention["admitted_blocks"][0]["doc_id"] == "doc1"
    assert attention["answer_forward_evidence"][0]["doc_id"] == "doc1"
    assert {row["anchor"] for row in attention["focus_candidates"]} == {"tumor"}
    assert attention["n0_attention"]["rejected_count"] == 6
    rejected = {(row["anchor"], row["reason"]) for row in attention["n0_attention"]["rejected"]}
    assert ("the", "glue_or_noncontent") in rejected
    assert ("glioma-42", "regex_attention_pollution") in rejected
    assert ("treatment", "query_echo") in rejected


def test_n0_attention_rejects_section_metadata_as_focus_authority() -> None:
    native_payload = {
        "ok": True,
        "command": "search-aw",
        "query": "microerythrocyte count",
        "query_anchors": ["microerythrocyte", "count"],
        "represented_anchors": ["microerythrocyte", "count"],
        "missing_anchors": [],
        "represented_anchor_count": 2,
        "count_candidate_count": 8,
        "hits": [
            {
                "doc_id": "18174210",
                "source_file": "source.md",
                "block_id": 2813,
                "block_line_start": 1,
                "block_line_end": 3,
                "document_line_start": 11253,
                "document_line_end": 11255,
                "rag_copy": "source.md.aw.md",
                "score": 1000,
                "query_anchor_hits": ["microerythrocyte"],
                "count_candidate_anchor_hits": [
                    "abstract",
                    "document",
                    "id",
                    "methods",
                    "study",
                    "title",
                    "observed",
                    "ci",
                    "confidence",
                    "interval",
                    "findings",
                    "than",
                    "after",
                    "anaemia",
                ],
            }
        ],
    }

    attention = build_native_search_attention(native_payload, top_k=8)

    assert [row["anchor"] for row in attention["focus_candidates"]] == ["anaemia"]
    rejected = {(row["anchor"], row["reason"]) for row in attention["n0_attention"]["rejected"]}
    assert ("abstract", "metadata_or_section_label") in rejected
    assert ("document", "metadata_or_section_label") in rejected
    assert ("methods", "metadata_or_section_label") in rejected
    assert ("observed", "low_signal_general_term") in rejected
    assert ("ci", "low_signal_general_term") in rejected
    assert ("confidence", "low_signal_general_term") in rejected
    assert ("interval", "low_signal_general_term") in rejected


def test_n0_attention_only_focuses_strongest_query_overlap_blocks() -> None:
    native_payload = {
        "ok": True,
        "command": "search-aw",
        "query": "microerythrocyte count severe anemia",
        "query_anchors": ["microerythrocyte", "count", "severe", "anemia"],
        "represented_anchors": ["microerythrocyte", "count", "severe", "anemia"],
        "missing_anchors": [],
        "represented_anchor_count": 4,
        "count_candidate_count": 6,
        "hits": [
            {
                "doc_id": "strong",
                "source_file": "source.md",
                "block_id": 1,
                "block_line_start": 1,
                "block_line_end": 3,
                "document_line_start": 10,
                "document_line_end": 12,
                "rag_copy": "source.md.aw.md",
                "score": 1000,
                "query_anchor_hits": ["microerythrocyte", "count", "severe"],
                "count_candidate_anchor_hits": ["anaemia"],
            },
            {
                "doc_id": "weak",
                "source_file": "source.md",
                "block_id": 2,
                "block_line_start": 1,
                "block_line_end": 3,
                "document_line_start": 20,
                "document_line_end": 22,
                "rag_copy": "source.md.aw.md",
                "score": 900,
                "query_anchor_hits": ["severe"],
                "count_candidate_anchor_hits": ["necrosis", "patients"],
            },
        ],
    }

    attention = build_native_search_attention(native_payload, top_k=5)

    assert [block["doc_id"] for block in attention["admitted_blocks"]] == ["strong"]
    assert [block["doc_id"] for block in attention["answer_forward_evidence"]] == ["strong", "weak"]
    assert [row["anchor"] for row in attention["focus_candidates"]] == ["anaemia"]
    assert attention["n0_attention"]["deferred_block_count"] == 1


def test_n0_attention_user_regex_can_deny_admit_boost_and_normalize_focus(tmp_path: Path) -> None:
    regex_path = tmp_path / "State" / "user" / "attention" / "n0_attention_regex.json"
    regex_path.parent.mkdir(parents=True)
    regex_path.write_text(
        json.dumps(
            {
                "schema_version": "anchorworks_n0_attention_regex@1",
                "deny_focus_patterns": [{"pattern": "^tumor$", "reason": "user_denied_domain_noise"}],
                "admit_focus_patterns": [{"pattern": "^glioblastoma$", "reason": "user_admitted_domain_signal"}],
                "boost_focus_patterns": [{"pattern": "^anemia$", "boost": 25.0, "reason": "user_boosted_domain_term"}],
                "normalize_focus_patterns": [{"pattern": "^anaemia$", "replace": "anemia", "reason": "user_normalized_variant"}],
            }
        ),
        encoding="utf-8",
    )
    native_payload = {
        "ok": True,
        "command": "search-aw",
        "query": "microerythrocyte count",
        "query_anchors": ["microerythrocyte", "count"],
        "represented_anchors": ["microerythrocyte", "count"],
        "missing_anchors": [],
        "represented_anchor_count": 2,
        "count_candidate_count": 4,
        "hits": [
            {
                "doc_id": "18174210",
                "source_file": "source.md",
                "block_id": 2813,
                "block_line_start": 1,
                "block_line_end": 3,
                "document_line_start": 11253,
                "document_line_end": 11255,
                "rag_copy": "source.md.aw.md",
                "score": 1000,
                "query_anchor_hits": ["microerythrocyte"],
                "count_candidate_anchor_hits": ["anaemia", "observed", "tumor", "glioblastoma"],
            }
        ],
    }

    attention = build_native_search_attention(native_payload, top_k=5, n0_regex_path=regex_path)

    assert [row["anchor"] for row in attention["focus_candidates"]] == ["anemia", "glioblastoma"]
    assert attention["focus_candidates"][0]["user_regex"]["boost"] == 25.0
    assert attention["focus_candidates"][0]["source_anchor"] == "anaemia"
    assert attention["answer_forward_evidence"][0]["doc_id"] == "18174210"
    rejected = {(row["anchor"], row["reason"]) for row in attention["n0_attention"]["rejected"]}
    assert ("tumor", "user_denied_domain_noise") in rejected
    assert ("observed", "low_signal_general_term") in rejected
    assert attention["n0_attention"]["user_regex"]["path"] == str(regex_path)
    assert attention["n0_attention"]["user_regex"]["writes_allowed"] == {
        "maps": False,
        "counts": False,
        "lifetime": False,
        "lexicon": False,
    }


def test_empty_or_missing_user_n0_attention_regex_is_noop(tmp_path: Path) -> None:
    native_payload = {
        "ok": True,
        "command": "search-aw",
        "query": "microerythrocyte count",
        "query_anchors": ["microerythrocyte", "count"],
        "represented_anchors": ["microerythrocyte", "count"],
        "missing_anchors": [],
        "represented_anchor_count": 2,
        "count_candidate_count": 2,
        "hits": [
            {
                "doc_id": "18174210",
                "source_file": "source.md",
                "block_id": 2813,
                "block_line_start": 1,
                "block_line_end": 3,
                "document_line_start": 11253,
                "document_line_end": 11255,
                "rag_copy": "source.md.aw.md",
                "score": 1000,
                "query_anchor_hits": ["microerythrocyte"],
                "count_candidate_anchor_hits": ["anaemia", "cell"],
            }
        ],
    }
    empty_path = tmp_path / "State" / "user" / "attention" / "n0_attention_regex.json"
    empty_path.parent.mkdir(parents=True)
    empty_path.write_text(
        json.dumps(
            {
                "schema_version": "anchorworks_n0_attention_regex@1",
                "deny_focus_patterns": [],
                "admit_focus_patterns": [],
                "boost_focus_patterns": [],
                "normalize_focus_patterns": [],
            }
        ),
        encoding="utf-8",
    )
    missing_path = tmp_path / "State" / "user" / "attention" / "missing_n0_attention_regex.json"

    baseline = build_native_search_attention(native_payload, top_k=5)
    empty_config = build_native_search_attention(native_payload, top_k=5, n0_regex_path=empty_path)
    missing_config = build_native_search_attention(native_payload, top_k=5, n0_regex_path=missing_path)

    assert [row["anchor"] for row in empty_config["focus_candidates"]] == [
        row["anchor"] for row in baseline["focus_candidates"]
    ]
    assert [row["anchor"] for row in missing_config["focus_candidates"]] == [
        row["anchor"] for row in baseline["focus_candidates"]
    ]
    assert empty_config["n0_attention"]["user_regex"]["loaded"] is True
    assert missing_config["n0_attention"]["user_regex"]["loaded"] is False


def test_verified_attention_handoff_restores_full_language_for_renderer() -> None:
    native_payload = {
        "ok": True,
        "command": "search-aw",
        "query": "role glioma treatment response",
        "query_anchors": ["role", "glioma", "treatment", "response"],
        "represented_anchors": ["role", "glioma", "treatment", "response"],
        "missing_anchors": [],
        "represented_anchor_count": 4,
        "count_candidate_count": 6,
        "hits": [
            {
                "doc_id": "doc1",
                "source_file": "source.md",
                "block_id": 7,
                "block_line_start": 1,
                "block_line_end": 4,
                "document_line_start": 70,
                "document_line_end": 73,
                "rag_copy": "source.md.aw.md",
                "score": 200,
                "query_anchor_hits": ["role", "glioma"],
                "count_candidate_anchor_hits": ["the", "of", "in", "glioma-42", "tumor"],
            }
        ],
    }
    attention = build_native_search_attention(native_payload, top_k=5)

    handoff = build_renderer_handoff(attention, native_payload)

    assert handoff["schema_version"] == "anchorworks_renderer_handoff@1"
    assert handoff["mode"] == "rag"
    assert handoff["verified"] is True
    assert handoff["render_may_use_full_language"] is True
    assert handoff["world_truth_claim"] is False
    assert handoff["observed_data_truth"] is True
    assert handoff["focus_anchors"] == ["tumor"]
    assert handoff["renderer_terms"] == ["the", "of", "in", "glioma-42", "tumor"]
    assert handoff["evidence_blocks"][0]["doc_id"] == "doc1"
    assert handoff["evidence_blocks"][0]["document_line_start"] == 70
    assert handoff["attention_rejected_terms"] == [
        {"anchor": "the", "reason": "glue_or_noncontent"},
        {"anchor": "of", "reason": "glue_or_noncontent"},
        {"anchor": "in", "reason": "glue_or_noncontent"},
        {"anchor": "glioma-42", "reason": "regex_attention_pollution"},
    ]
    assert handoff["writes_allowed"] == {"maps": False, "counts": False, "lifetime": False, "lexicon": False}


def test_clearspeak_render_from_handoff_cites_coordinates_without_world_truth() -> None:
    handoff = {
        "schema_version": "anchorworks_renderer_handoff@1",
        "mode": "counts",
        "verified": True,
        "verification_failures": [],
        "render_may_use_full_language": True,
        "observed_data_truth": True,
        "world_truth_claim": False,
        "query": "role glioma treatment response",
        "focus_anchors": ["tumor"],
        "renderer_terms": ["the", "role", "of", "glioma", "in", "tumor", "response"],
        "evidence_blocks": [
            {
                "doc_id": "doc1",
                "source_file": "source.md",
                "block_id": 7,
                "block_line_start": 1,
                "block_line_end": 4,
                "document_line_start": 70,
                "document_line_end": 73,
                "rag_copy": "source.md.aw.md",
            }
        ],
        "attention_rejected_terms": [
            {"anchor": "the", "reason": "glue_or_noncontent"},
            {"anchor": "of", "reason": "glue_or_noncontent"},
            {"anchor": "in", "reason": "glue_or_noncontent"},
        ],
        "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
    }

    rendered = render_from_handoff(handoff)

    assert rendered["ok"] is True
    assert rendered["world_truth_claim"] is False
    assert rendered["observed_data_truth"] is True
    assert rendered["focus_anchors"] == ["tumor"]
    assert "the role of glioma in tumor response" in rendered["speech"]
    assert "doc1 block 7 lines 70-73" in rendered["speech"]
    assert rendered["citations"] == [
        {
            "doc_id": "doc1",
            "source_file": "source.md",
            "block_id": 7,
            "document_line_start": 70,
            "document_line_end": 73,
            "rag_copy": "source.md.aw.md",
            "citation_type": "observed_data_coordinate",
        }
    ]
    assert rendered["attention_rejected_terms"] == handoff["attention_rejected_terms"]
    assert rendered["writes_allowed"] == {"maps": False, "counts": False, "lifetime": False, "lexicon": False}


def test_renderer_does_not_dump_unordered_candidate_terms_as_english() -> None:
    handoff = {
        "schema_version": "anchorworks_renderer_handoff@1",
        "mode": "counts",
        "verified": True,
        "verification_failures": [],
        "render_may_use_full_language": True,
        "observed_data_truth": True,
        "world_truth_claim": False,
        "query": "microerythrocyte count",
        "focus_anchors": ["anaemia", "associated", "cell"],
        "renderer_terms": [
            "%",
            "(",
            ")",
            "+",
            ",",
            "-",
            ".",
            "/",
            "0",
            "1",
            "2",
            "4",
            "5",
            "7",
            "8",
            "9",
            ":",
            ";",
            "<",
            "=",
            ">",
            "[",
            "a",
            "abstract",
            "acute",
            "addition",
            "adult",
            "anaemia",
            "associated",
            "cell",
        ],
        "evidence_blocks": [
            {
                "doc_id": "18174210",
                "source_file": "source.md",
                "block_id": 2813,
                "block_line_start": 1,
                "block_line_end": 3,
                "document_line_start": 11253,
                "document_line_end": 11255,
                "rag_copy": "source.md.aw.md",
            }
        ],
        "attention_rejected_terms": [],
        "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
    }

    rendered = render_from_handoff(handoff)

    assert "a abstract acute addition adult" not in rendered["speech"]
    assert "abstract" not in rendered["speech"]
    assert "anaemia, associated, cell" in rendered["speech"]
    assert rendered["world_truth_claim"] is False


def test_rag_mode_returns_observed_blocks_without_speaking() -> None:
    handoff = {
        "schema_version": "anchorworks_renderer_handoff@1",
        "mode": "rag",
        "verified": True,
        "verification_failures": [],
        "render_may_use_full_language": True,
        "observed_data_truth": True,
        "world_truth_claim": False,
        "query": "microerythrocyte count",
        "focus_anchors": ["anaemia"],
        "renderer_terms": ["a", "abstract", "anaemia"],
        "evidence_blocks": [
            {
                "doc_id": "18174210",
                "source_file": "beir_scifact_corpus_aw_intake.txt",
                "block_id": 2813,
                "block_line_start": 1,
                "block_line_end": 3,
                "document_line_start": 11253,
                "document_line_end": 11255,
                "rag_copy": "beir_scifact_corpus_aw_intake.txt.aw.md",
                "query_anchor_hits": ["microerythrocyte", "count"],
            }
        ],
        "attention_rejected_terms": [],
        "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
    }

    rendered = render_from_handoff(handoff)

    assert rendered["ok"] is True
    assert rendered["mode"] == "rag"
    assert rendered["renderer"] == "block_surface"
    assert rendered["speech"] == ""
    assert rendered["blocks"] == handoff["evidence_blocks"]
    assert rendered["citations"][0]["doc_id"] == "18174210"
    assert rendered["world_truth_claim"] is False


def test_attention_refuses_partial_query_content_overlap_without_slop() -> None:
    native_payload = {
        "ok": True,
        "command": "search-aw",
        "query": "impossible moon cheese flarnivore",
        "query_anchors": ["impossible", "moon", "cheese", "flarnivore"],
        "represented_anchors": ["impossible", "moon"],
        "missing_anchors": ["cheese", "flarnivore"],
        "represented_anchor_count": 2,
        "count_candidate_count": 5,
        "hits": [
            {
                "doc_id": "slop",
                "source_file": "beir_scifact_corpus_aw_intake.txt",
                "block_id": 99,
                "block_line_start": 1,
                "block_line_end": 3,
                "document_line_start": 100,
                "document_line_end": 102,
                "rag_copy": "beir_scifact_corpus_aw_intake.txt.aw.md",
                "score": 100,
                "query_anchor_hits": ["moon"],
                "count_candidate_anchor_hits": ["methods", "cases"],
            }
        ],
    }

    attention = build_native_search_attention(native_payload, top_k=5)

    assert attention["observed_data_truth"] is False
    assert attention["world_truth_claim"] is False
    assert attention["admission_status"] == "refused"
    assert attention["refusal_reason"] == "missing_query_content_anchor"
    assert attention["missing_content_anchors"] == ["cheese", "flarnivore"]
    assert attention["admitted_blocks"] == []
    assert attention["focus_candidates"] == []


def test_python_does_not_define_count_search_or_benchmark_compute_paths() -> None:
    forbidden_paths = {
        SOURCE_ROOT / "count_corpus_search.py",
    }
    existing_forbidden_paths = [str(path.relative_to(REPO_ROOT)) for path in forbidden_paths if path.exists()]
    assert existing_forbidden_paths == []

    forbidden_source = [
        "def retrieve_from_counts(",
        "def _binary_relation_rows_for_anchor(",
        "def rank_corpus_documents_from_count_terms(",
        "def search_flat_document_evidence(",
        "def search_observed_map_evidence(",
        "qrels",
        "beir",
        "scifact",
    ]
    offenders: list[str] = []
    for path in SOURCE_ROOT.rglob("*.py"):
        if path.name == "symbol_count_native.py":
            continue
        text = path.read_text(encoding="utf-8")
        for snippet in forbidden_source:
            if snippet in text:
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {snippet}")
    assert offenders == []

    native_wrapper = (SOURCE_ROOT / "symbol_count_native.py").read_text(encoding="utf-8")
    assert "source_local_missing: bool = True" not in native_wrapper
    assert "SOURCE_LOCAL_TEMP_LANE,\n        USER_LEXICON_LANE" not in native_wrapper


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
