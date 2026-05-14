from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from AnchorWorks.phrase_candidates import (
    build_phrase_candidates_from_symbolic_docs,
    build_phrase_candidates_from_observed_map_dir,
    write_phrase_candidate_review,
)
from AnchorWorks.store import LexiconStore
from AnchorWorks.symbolic_map_binary import write_symbolic_map_binary


class PhraseCandidateTests(unittest.TestCase):
    def test_builds_candidates_from_symbolized_flat_docs_only(self) -> None:
        docs = [
            {
                "schema_version": "flat_symbolic_document@2",
                "source_id": "source_a",
                "source_name": "a.md",
                "saved_document_name": "a.symbolic.json",
                "blocks": [
                    {
                        "block_id": "block_0",
                        "anchor_stream": ["newton", "laws", "of", "motion", "describe", "motion"],
                        "symbol_stream": [
                            "0x0000000001",
                            "0x0000000002",
                            "0x0000000003",
                            "0x0000000004",
                            "0x0000000005",
                            "0x0000000004",
                        ],
                        "line_start": 1,
                        "line_end": 1,
                    }
                ],
            },
            {
                "schema_version": "flat_symbolic_document@2",
                "source_id": "source_b",
                "source_name": "b.md",
                "saved_document_name": "b.symbolic.json",
                "blocks": [
                    {
                        "block_id": "block_0",
                        "anchor_stream": ["newton", "laws", "of", "motion", "connect", "force"],
                        "symbol_stream": [
                            "0x0000000001",
                            "0x0000000002",
                            "0x0000000003",
                            "0x0000000004",
                            "0x0000000006",
                            "0x0000000007",
                        ],
                        "line_start": 2,
                        "line_end": 2,
                    }
                ],
            },
        ]

        result = build_phrase_candidates_from_symbolic_docs(docs, min_count=2, max_length=4)

        phrase_by_text = {row["phrase"]: row for row in result["candidates"]}
        candidate = phrase_by_text["newton laws of motion"]
        self.assertEqual(result["schema_version"], "anchorworks_phrase_candidates@1")
        self.assertEqual(candidate["anchor_sequence"], ["newton", "laws", "of", "motion"])
        self.assertEqual(candidate["symbol_sequence"], ["0x0000000001", "0x0000000002", "0x0000000003", "0x0000000004"])
        self.assertEqual(candidate["occurrence_count"], 2)
        self.assertEqual(candidate["source_count"], 2)
        self.assertEqual(candidate["promotion_status"], "REVIEW_CANDIDATE")
        self.assertEqual(candidate["writes_allowed"], {"canonical": False, "phrase_lexicon": False, "counts": False, "lifetime": False})
        self.assertGreater(candidate["score"], phrase_by_text["laws of motion"]["score"])

    def test_rejects_glue_only_candidates_and_keeps_glue_inside_content_phrase(self) -> None:
        docs = [
            {
                "source_id": "source_glue",
                "blocks": [
                    {
                        "block_id": "block_0",
                        "anchor_stream": ["of", "the", "and", "field", "of", "motion", "field", "of", "motion"],
                        "symbol_stream": [
                            "0x0000000003",
                            "0x0000000008",
                            "0x0000000009",
                            "0x000000000A",
                            "0x0000000003",
                            "0x0000000004",
                            "0x000000000A",
                            "0x0000000003",
                            "0x0000000004",
                        ],
                    }
                ],
            }
        ]

        result = build_phrase_candidates_from_symbolic_docs(docs, min_count=2, max_length=3)
        phrases = {row["phrase"] for row in result["candidates"]}

        self.assertNotIn("of the", phrases)
        self.assertIn("field of motion", phrases)

    def test_review_write_does_not_mutate_authority_or_counts(self) -> None:
        docs = [
            {
                "source_id": "source_a",
                "blocks": [
                    {
                        "block_id": "block_0",
                        "anchor_stream": ["alpha", "beta", "alpha", "beta"],
                        "symbol_stream": ["0x0000000001", "0x0000000002", "0x0000000001", "0x0000000002"],
                    }
                ],
            }
        ]

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            canonical = root / "Canonical"
            awsc = root / "State" / "symbol_counts_binary"
            phrase_lexicon = root / "Phrase_Lexicon"
            canonical.mkdir(parents=True)
            awsc.mkdir(parents=True)
            phrase_lexicon.mkdir(parents=True)
            (canonical / "canonical_A.json").write_text("[]", encoding="utf-8")
            (awsc / "sentinel.cell").write_bytes(b"unchanged")

            review = build_phrase_candidates_from_symbolic_docs(docs, min_count=2, max_length=2)
            written = write_phrase_candidate_review(root / "State" / "phrase_candidates", review)

            self.assertTrue(Path(written["jsonl_path"]).exists())
            self.assertTrue(Path(written["manifest_path"]).exists())
            self.assertEqual((canonical / "canonical_A.json").read_text(encoding="utf-8"), "[]")
            self.assertEqual((awsc / "sentinel.cell").read_bytes(), b"unchanged")
            self.assertEqual(list(phrase_lexicon.glob("*.json")), [])
            row = json.loads(Path(written["jsonl_path"]).read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(row["promotion_status"], "REVIEW_CANDIDATE")

    def test_store_builds_phrase_review_from_current_flat_symbolic_docs(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = LexiconStore(root)
            symbolic = {
                "schema_version": "flat_symbolic_document@2",
                "source_id": "source_store",
                "source_name": "store.md",
                "saved_document_name": "store.symbolic.json",
                "blocks": [
                    {
                        "block_id": "block_0",
                        "anchor_stream": ["alpha", "beta", "gamma", "alpha", "beta", "gamma"],
                        "symbol_stream": [
                            "0x0000000001",
                            "0x0000000002",
                            "0x0000000003",
                            "0x0000000001",
                            "0x0000000002",
                            "0x0000000003",
                        ],
                    }
                ],
            }
            store._write_json(store.flat_documents_symbolic_dir / "store.symbolic.json", symbolic)

            result = store.build_phrase_candidate_review(min_count=2, max_length=3)

            self.assertTrue(Path(result["jsonl_path"]).exists())
            self.assertTrue(Path(result["manifest_path"]).exists())
            self.assertEqual(result["candidate_count"], 3)
            self.assertEqual(list(store.phrases.phrase_dir.glob("*.json")), [])

    def test_offline_observed_map_candidates_use_awsm_symbol_authority(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            observed_dir = root / "observed_maps"
            symbolic_dir = root / "symbolic_maps"
            observed_dir.mkdir()
            symbolic_dir.mkdir()
            metadata = {
                "schema_version": "anchorworks_symbolic_map_binary_metadata@1",
                "symbol_authority": [
                    {"anchor": "R1", "symbol": "0x0000000001", "authority": "canonical"},
                    {"anchor": "R2", "symbol": "0x0000000002", "authority": "canonical"},
                    {"anchor": "R3", "symbol": "0x0000000003", "authority": "canonical"},
                    {"anchor": "__NULL__", "symbol": "0xF000000000", "authority": "source_local"},
                ],
            }
            write_symbolic_map_binary(symbolic_dir / "doc.observed.awsm", metadata=metadata, relations=[])
            observed = {
                "source_id": "doc_source",
                "source_name": "doc.md",
                "symbolic_map_path": str(symbolic_dir / "doc.observed.awsm"),
                "paragraphs": [
                    {
                        "paragraph_id": 0,
                        "anchors": ["alpha", "beta", "gamma", "alpha", "beta", "gamma", "."],
                        "resolved_anchors": ["R1", "R2", "R3", "R1", "R2", "R3", "__NULL__"],
                    }
                ],
            }
            (observed_dir / "doc.observed.json").write_text(json.dumps(observed), encoding="utf-8")

            result = build_phrase_candidates_from_observed_map_dir(observed_dir, symbolic_map_dir=symbolic_dir, min_count=2, max_length=3)

            phrase_by_text = {row["phrase"]: row for row in result["candidates"]}
            self.assertEqual(result["observed_map_count"], 1)
            self.assertIn("alpha beta gamma", phrase_by_text)
            self.assertEqual(phrase_by_text["alpha beta gamma"]["symbol_sequence"], ["0x0000000001", "0x0000000002", "0x0000000003"])
            self.assertNotIn("gamma .", phrase_by_text)


if __name__ == "__main__":
    unittest.main()
