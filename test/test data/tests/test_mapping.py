from __future__ import annotations

from collections import Counter
import json
import os
import tempfile
import unittest
from pathlib import Path

from AnchorWorks.app import ChatSendBody, ClearSpeakQueryBody, IntakeEditBody, create_app, _default_data_root
from AnchorWorks.answer_surface import render_anchor_answer_surface
from AnchorWorks.chat_memory_system import ChatMemorySystem
from AnchorWorks.anchorworks_chat_archive import prepare_anchorworks_chat_archive
from AnchorWorks.clearspeak_attention import build_active_cloud_frame, choose_candidate_with_lookahead, infer_attention_frame, rank_attention_candidates
from AnchorWorks.clearspeak import ClearSpeakService
from AnchorWorks.document_answer import DocumentAnswerAssembler
from AnchorWorks.document_prep import prepare_bytes
from AnchorWorks.intake import NULL_ANCHOR, build_anchor_map, compose_anchor_stream, extract_anchor_rows, extract_anchors
from AnchorWorks.local_meta_overlay import (
    build_local_meta_count_overlay,
    load_local_meta_count_overlay,
    query_local_overlay_cloud,
    score_candidate,
)
from AnchorWorks.phrase_lexicon import PhraseLexiconStore
from AnchorWorks.store import LexiconStore
from AnchorWorks.symbol_count_cells import CANONICAL_LANE, SymbolRelation, write_symbol_cell
from AnchorWorks.symbolic_map_binary import (
    read_symbolic_map_binary,
    read_symbolic_map_locator_sidecar,
    read_symbolic_map_null_sidecar,
    read_symbolic_map_visual_sidecar,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _anchorworks_repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent if (parent / "src" / "AnchorWorks").exists() else parent / "Anchorworks"
        if (candidate / "src" / "AnchorWorks").exists():
            return candidate
    raise RuntimeError("Anchorworks repo root not found")


def _write_count_read_fixture(
    store: LexiconStore,
    relation_rows: list[dict[str, object]],
    *,
    observed_counts: Counter[str],
) -> None:
    _write_json(store.lifetime_counts_path, {
        "first_saved_at": "fixture",
        "updated_at": "fixture",
        "ingest_events": 1,
        "window_radius": 6,
        "unique_relations": len(relation_rows),
        "total_relation_observations": int(sum(int(row.get("observations", 0) or 0) for row in relation_rows)),
        "anchor_observation_counts": [
            {"anchor": anchor, "observations": observations}
            for anchor, observations in sorted(observed_counts.items())
        ],
        "co_occurrence_counts": relation_rows,
    })


class MappingTests(unittest.TestCase):
    def _shared_spares(self, count: int) -> list[dict[str, str]]:
        return [
            {
                "binary": f"{index:04b}",
                "hex": f"0x{index + 1000:03X}",
                "font_symbol": f"CHAR_{index}",
                "tone_signature": f"TONE_{index}",
                "status": "AVAILABLE",
            }
            for index in range(count)
        ]

    def test_user_side_storage_scaffold_startup_keeps_main_reference_files_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            protected_payloads = {
                root / "Canonical" / "canonical_A.json": [{"word": "anchor", "status": "ASSIGNED"}],
                root / "Structural" / "structural.json": [{"word": ".", "status": "STRUCTURAL"}],
                root / "Spare_Slots" / "spare_slots.json": self._shared_spares(2),
                root / "State" / "lifetime_co_occurrence_counts.json": {
                    "first_saved_at": "base-reference",
                    "ingest_events": 12,
                    "co_occurrence_counts": [],
                },
            }
            for path, payload in protected_payloads.items():
                _write_json(path, payload)
            before = {str(path): path.read_text(encoding="utf-8") for path in protected_payloads}

            app = create_app(root)
            route = next(route for route in app.routes if getattr(route, "path", "") == "/api/user/storage/status")
            status = route.endpoint()
            after = {str(path): path.read_text(encoding="utf-8") for path in protected_payloads}

            expected_dirs = [
                root / "State" / "user" / "user_lexicon",
                root / "State" / "user" / "user_counts",
                root / "State" / "user" / "chat_counts",
                root / "State" / "user" / "ingest_staging",
                root / "State" / "user" / "rejected_or_literal_clusters",
            ]
            expected_files = [
                root / "State" / "user" / "user_lexicon" / "anchors.json",
                root / "State" / "user" / "ingest_staging" / "manifest.json",
                root / "State" / "user" / "rejected_or_literal_clusters" / "clusters.json",
            ]

            self.assertTrue(status["ok"])
            self.assertTrue(all(path.is_dir() for path in expected_dirs))
            self.assertTrue(all(path.is_file() for path in expected_files))
            self.assertTrue(all(row["exists"] for row in status["directories"]))
            self.assertTrue(all(row["exists"] for row in status["files"]))
            self.assertEqual(before, after)

    def test_observed_maps_write_to_external_anchor_maps_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            _write_json(root / "Canonical" / "canonical_A.json", [{"word": "alpha", "status": "ASSIGNED"}])
            _write_json(root / "Structural" / "structural.json", [{"word": ".", "status": "STRUCTURAL"}])
            _write_json(root / "Spare_Slots" / "spare_slots.json", [])
            source_path = Path(temp_dir) / "sample.txt"
            source_path.write_text("alpha.", encoding="utf-8")

            store = LexiconStore(root)
            expected = (root.parent / "AnchorMaps" / "observed_maps").resolve()
            result = store.build_observed_map(source_path)
            saved_path = Path(result["saved_map_path"]).resolve()

            self.assertEqual(store.observed_maps_dir, expected)
            self.assertEqual(saved_path.parent, expected)
            self.assertTrue(saved_path.is_file())
            self.assertFalse((store.state_dir / "observed_maps" / saved_path.name).exists())

    def test_symbolic_intake_batch_groups_maps_and_builds_binary_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            _write_json(root / "Canonical" / "canonical_A.json", [{"word": "alpha", "hex": "0x0000000001"}])
            _write_json(root / "Canonical" / "canonical_B.json", [{"word": "beta", "hex": "0x0000000002"}])
            _write_json(root / "Canonical" / "canonical_G.json", [{"word": "gamma", "hex": "0x0000000003"}])
            _write_json(root / "Structural" / "structural.json", [{"word": ".", "status": "STRUCTURAL"}])
            _write_json(root / "Spare_Slots" / "spare_slots.json", [])
            group_a = Path(temp_dir) / "book_a"
            group_b = Path(temp_dir) / "book_b"
            group_a.mkdir()
            group_b.mkdir()
            sources = [
                group_a / "chapter_1.txt",
                group_a / "chapter_2.txt",
                group_b / "chapter_1.txt",
                group_b / "chapter_2.txt",
            ]
            for index, path in enumerate(sources):
                path.write_text(f"alpha beta gamma. alpha {index}.", encoding="utf-8")

            store = LexiconStore(root)
            result = store.build_symbolic_intake_batch(sources, max_workers=2, generation=21)

            self.assertTrue(result["ok"])
            self.assertEqual(result["source_count"], 4)
            self.assertEqual(result["group_count"], 2)
            self.assertEqual(result["max_workers_used"], 2)
            self.assertEqual(result["map_count"], 4)
            self.assertEqual(result["symbol_artifact_count"], 4)
            self.assertTrue(result["binary"]["ok"])
            self.assertGreater(result["binary"]["stream_record_count"], 0)
            self.assertTrue(all(Path(row["saved_map_path"]).parent == store.observed_maps_dir for row in result["maps"]))
            self.assertFalse(any((store.state_dir / "observed_maps").glob("*.observed.json")))

    def test_chunked_symbolic_intake_flushes_checkpoints_and_chunk_binaries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            _write_json(root / "Canonical" / "canonical_A.json", [{"word": "alpha", "hex": "0x0000000001"}])
            _write_json(root / "Canonical" / "canonical_B.json", [{"word": "beta", "hex": "0x0000000002"}])
            _write_json(root / "Structural" / "structural.json", [{"word": ".", "status": "STRUCTURAL"}])
            _write_json(root / "Spare_Slots" / "spare_slots.json", [])
            sources = []
            for index in range(5):
                path = Path(temp_dir) / f"chapter_{index}.txt"
                path.write_text(f"alpha beta alpha {index}.", encoding="utf-8")
                sources.append(path)

            store = LexiconStore(root)
            result = store.build_symbolic_intake_batch_chunked(
                sources,
                max_workers=1,
                generation=31,
                run_id="unit_chunked",
                chunk_file_limit=2,
            )

            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["source_count"], 5)
            self.assertEqual(result["chunk_count"], 3)
            self.assertEqual(result["completed_chunks"], 3)
            self.assertEqual(result["files_ok"], 5)
            self.assertEqual(result["files_failed"], 0)
            self.assertTrue(Path(result["manifest_path"]).is_file())
            self.assertEqual(len(list((store.ingest_staging_dir / "chunked_symbolic_intake" / "unit_chunked" / "chunks").glob("*.json"))), 3)
            self.assertTrue(all((row.get("binary") or {}).get("ok") for row in result["chunks"]))
            self.assertTrue(Path(result["chunk_binary_root"]).exists())
            self.assertFalse(any((store.state_dir / "observed_maps").glob("*.observed.json")))

    def test_different_document_types_write_symbolic_binary_maps(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            _write_json(root / "Canonical" / "canonical_A.json", [{"word": "alpha", "hex": "0x0000000001"}])
            _write_json(root / "Canonical" / "canonical_B.json", [{"word": "beta", "hex": "0x0000000002"}])
            _write_json(root / "Canonical" / "canonical_G.json", [{"word": "gamma", "hex": "0x0000000003"}])
            _write_json(root / "Structural" / "structural.json", [{"word": ".", "status": "STRUCTURAL"}])
            _write_json(root / "Spare_Slots" / "spare_slots.json", [])
            docs = {
                "sample.txt": "alpha beta gamma.",
                "sample.md": "# Alpha\n\nbeta gamma.",
                "sample.json": {"alpha": "beta gamma"},
                "sample.html": "<html><body><p>alpha beta gamma.</p></body></html>",
            }

            store = LexiconStore(root)
            for name, content in docs.items():
                path = Path(temp_dir) / name
                if isinstance(content, str):
                    path.write_text(content, encoding="utf-8")
                else:
                    path.write_text(json.dumps(content), encoding="utf-8")
                result = store.build_observed_map(path)
                symbolic_path = Path(result["symbolic_map_path"])
                loaded = read_symbolic_map_binary(symbolic_path)

                self.assertTrue(symbolic_path.is_file())
                self.assertGreater(result["symbolic_map_relation_count"], 0)
                self.assertEqual(loaded.metadata["source_name"], name)
                self.assertEqual(loaded.relation_count, result["symbolic_map_relation_count"])
                self.assertTrue(loaded.relations)

    def test_extract_anchors_keeps_words_punctuation_and_emoji_placeholder(self) -> None:
        text = "don't stop. do not stop " + chr(0x1F60A)
        self.assertEqual(
            extract_anchors(text),
            ["don't", "stop", ".", "do", "not", "stop", "__EMOJI__"],
        )

    def test_apostrophe_is_never_emitted_as_solo_anchor(self) -> None:
        text = "'em don't girls' rock 'n' roll ’ lone ’"
        anchors = extract_anchors(text)

        self.assertEqual(
            anchors,
            ["em", "don't", "girls'", "rock", "n", "roll", "lone"],
        )
        self.assertNotIn("'", anchors)
        self.assertEqual(extract_anchors("'apm 'x"), ["apm", "x"])
        self.assertNotIn("’", anchors)

    def test_anchor_identity_normalizes_curly_apostrophes_to_lexicon_form(self) -> None:
        self.assertEqual(
            extract_anchors("Earth’s orbit and women's votes"),
            ["earth's", "orbit", "and", "women's", "votes"],
        )

    def test_acronyms_decompose_to_existing_letter_and_digit_anchors(self) -> None:
        self.assertEqual(extract_anchors("AWSC v1.1 B70"), ["a", "w", "s", "c", "v", "1", ".", "1", "b", "7", "0"])

        mapping = build_anchor_map("AWSC")
        self.assertEqual(mapping["paragraphs"][0]["anchors"], ["a", "w", "s", "c"])
        self.assertEqual(mapping["paragraphs"][0]["composed_anchor_stream"], ["a", "w", "s", "c"])

    def test_build_anchor_map_respects_paragraph_boundaries(self) -> None:
        text = "do not.\n\nstop now!"
        mapping = build_anchor_map(text)

        self.assertEqual(mapping["paragraph_count"], 2)
        self.assertEqual(mapping["paragraphs"][0]["anchors"], ["do", "not", "."])
        self.assertEqual(mapping["paragraphs"][1]["anchors"], ["stop", "now", "!"])
        self.assertEqual(mapping["paragraphs"][0]["composed_anchor_streams"], [["do"], ["not"], ["."]])
        self.assertEqual(mapping["paragraphs"][0]["composed_anchor_stream"], ["do", "not", "."])
        self.assertIsNone(mapping["occurrences"][0]["window"]["+3"])

    def test_null_anchor_preserves_position_without_counts(self) -> None:
        mapping = build_anchor_map("alpha junk beta", resolved_anchors={"junk": NULL_ANCHOR}, null_anchors={"junk"})

        self.assertEqual(mapping["paragraphs"][0]["anchors"], ["alpha", "junk", "beta"])
        null_occurrence = next(row for row in mapping["occurrences"] if row["observed_anchor"] == "junk")
        self.assertEqual(null_occurrence["anchor"], NULL_ANCHOR)
        self.assertFalse(null_occurrence["count_eligible"])
        self.assertNotIn(NULL_ANCHOR, mapping["observed_counts"])
        self.assertFalse(any(row["anchor"] == NULL_ANCHOR or row["neighbor"] == NULL_ANCHOR for row in mapping["co_occurrence_counts"]))

    def test_build_anchor_map_includes_grouped_616_items_and_anchor_index(self) -> None:
        mapping = build_anchor_map("do not do")

        do_item = mapping["items"]["do"]
        not_item = mapping["items"]["not"]

        self.assertEqual(do_item["center_observations"], 2)
        self.assertEqual(do_item["before"]["1"], [{"anchor": "not", "word": "not", "count": 1}])
        self.assertEqual(do_item["before"]["2"], [{"anchor": "do", "word": "do", "count": 1}])
        self.assertEqual(do_item["after"]["1"], [{"anchor": "not", "word": "not", "count": 1}])
        self.assertEqual(do_item["after"]["2"], [{"anchor": "do", "word": "do", "count": 1}])
        self.assertEqual(do_item["total_neighbor_observations"], 4)
        self.assertEqual(not_item["center_observations"], 1)
        self.assertEqual(not_item["before"]["1"], [{"anchor": "do", "word": "do", "count": 1}])
        self.assertEqual(not_item["after"]["1"], [{"anchor": "do", "word": "do", "count": 1}])
        self.assertEqual(mapping["anchor_index"][0]["anchor"], "do")
        self.assertEqual(mapping["anchor_index"][0]["count"], 4)

    def test_clearspeak_attention_scores_by_position_and_context_support(self) -> None:
        count_index = {
            "by_anchor": {
                "sear": {
                    "+1": Counter({"meat": 10, "pan": 12}),
                    "+6": Counter({"smoke": 30}),
                },
                "meat": {
                    "-1": Counter({"sear": 10}),
                    "+1": Counter({"pan": 8}),
                },
            }
        }

        ranked = rank_attention_candidates(count_index, ["sear", "meat"], blocked={"sear", "meat"})

        self.assertEqual(ranked[0]["anchor"], "pan")
        self.assertEqual(ranked[0]["attention_math"]["kind"], "runtime_relevance_scoring")
        self.assertEqual(ranked[0]["attention_math"]["law"], "Counts store weight; context clouds store neighborhood; attention chooses relevance.")
        self.assertEqual(ranked[0]["supporting_context"], ["sear", "meat"])
        self.assertEqual(ranked[0]["support_offsets"], ["+1"])
        self.assertGreater(ranked[0]["selection_score"], ranked[1]["selection_score"])
        self.assertIn("observations_x_position_strength", ranked[0]["why_chosen"])
        self.assertIn("multi_context_support_bonus", ranked[0]["why_chosen"])

    def test_clearspeak_attention_classifies_method_frames_and_role_fit(self) -> None:
        question_frame = infer_attention_frame(["how", "do", "i", "sear", "meat", "?"])
        declaration_frame = infer_attention_frame(["this", "is", "how", "i", "sear", "meat", "."])
        count_index = {
            "by_anchor": {
                "sear": {
                    "+1": Counter({"meat": 9, "pan": 5}),
                    "+2": Counter({"heat": 4}),
                },
                "meat": {
                    "-1": Counter({"sear": 9}),
                    "+1": Counter({"pan": 5}),
                },
            }
        }

        ranked = rank_attention_candidates(
            count_index,
            ["sear", "meat"],
            blocked={"sear", "meat"},
            attention_frame=question_frame,
        )

        self.assertEqual(question_frame["frame_type"], "method_question")
        self.assertEqual(declaration_frame["frame_type"], "method_declaration")
        self.assertEqual(question_frame["role_by_anchor"]["sear"], "action_candidate")
        self.assertEqual(question_frame["role_by_anchor"]["meat"], "object_candidate")
        self.assertEqual(ranked[0]["anchor"], "pan")
        self.assertEqual(ranked[0]["frame_type"], "method_question")
        self.assertEqual(ranked[0]["role_fit"]["matched_roles"], ["action_candidate", "object_candidate"])
        self.assertGreater(ranked[0]["role_fit"]["score"], 0)
        self.assertEqual(ranked[0]["answer_health"]["status"], "supported")

    def test_active_cloud_frame_scores_candidates_with_qraf_parts_and_rejections(self) -> None:
        count_index = {
            "by_anchor": {
                "sear": {
                    "+1": Counter({"meat": 9, "pan": 8, "the": 30}),
                    "+2": Counter({"heat": 4}),
                },
                "meat": {
                    "-1": Counter({"sear": 9}),
                    "+1": Counter({"pan": 7}),
                },
                "pan": {
                    "+1": Counter({"heat": 6}),
                },
            }
        }
        frame = infer_attention_frame(["how", "do", "i", "sear", "meat", "?"])

        active = build_active_cloud_frame(
            count_index,
            question_anchors=["how", "do", "i", "sear", "meat", "?"],
            rear_context=["sear", "meat"],
            answer_so_far=[],
            forward_context=[],
            blocked={"sear", "meat"},
            attention_frame=frame,
            top_k=6,
        )

        self.assertEqual(active["schema_version"], "anchorworks_active_cloud_frame@1")
        self.assertEqual(active["weights"], {"question": 0.35, "rear": 0.25, "answer": 0.3, "forward": 0.1})
        self.assertEqual(active["combined_cloud_formula"], "C_t = wq Q + wr R + wa A_t + wf F_t")
        self.assertEqual(active["candidates"][0]["anchor"], "pan")
        self.assertIn("question_fit", active["candidates"][0]["score_parts"])
        self.assertIn("rear_fit", active["candidates"][0]["score_parts"])
        self.assertIn("answer_fit", active["candidates"][0]["score_parts"])
        self.assertIn("forward_fit", active["candidates"][0]["score_parts"])
        self.assertIn("source_support", active["candidates"][0]["score_parts"])
        self.assertGreater(active["candidates"][0]["score"], active["candidates"][1]["score"])
        self.assertTrue(any(row["anchor"] == "the" and row["reason"] == "glue_as_content" for row in active["rejected_candidates"]))

    def test_clearspeak_lookahead_rejects_anomalous_future_shape(self) -> None:
        count_index = {
            "by_anchor": {
                "seed": {
                    "+1": Counter({"loud": 10, "healthy": 4}),
                    "+2": Counter({"loud": 8}),
                },
                "loud": {
                    "+1": Counter({"of": 12, "__NULL__": 9}),
                    "+2": Counter({"the": 8}),
                },
                "healthy": {
                    "+1": Counter({"pan": 5, "surface": 4}),
                    "+2": Counter({"heat": 3}),
                },
            }
        }
        active = build_active_cloud_frame(
            count_index,
            question_anchors=["how", "seed"],
            rear_context=["seed"],
            answer_so_far=[],
            forward_context=[],
            blocked={"seed"},
            attention_frame=infer_attention_frame(["how", "seed"]),
            top_k=6,
        )

        decision = choose_candidate_with_lookahead(
            count_index,
            active["candidates"],
            seed_anchors=["seed"],
            blocked={"seed"},
            lookahead_k=3,
        )

        self.assertEqual(decision["chosen"]["anchor"], "healthy")
        by_anchor = {row["anchor"]: row for row in decision["candidates"]}
        self.assertEqual(by_anchor["loud"]["pattern_health"], "anomalous")
        self.assertEqual(by_anchor["healthy"]["pattern_health"], "healthy")

    def test_clearspeak_lookahead_rejects_query_field_drift(self) -> None:
        count_index = {
            "by_anchor": {
                "laws": {
                    "+1": Counter({"mothers": 12, "motion": 6}),
                },
                "physics": {
                    "+1": Counter({"motion": 6}),
                },
                "mothers": {
                    "+1": Counter({"children": 8, "american": 7, "however": 6}),
                },
                "motion": {
                    "+1": Counter({"force": 8, "energy": 7, "physics": 3}),
                },
            }
        }
        active = build_active_cloud_frame(
            count_index,
            question_anchors=["why", "laws", "physics"],
            rear_context=["laws", "physics"],
            answer_so_far=[],
            forward_context=[],
            blocked={"laws", "physics"},
            attention_frame=infer_attention_frame(["why", "laws", "physics"]),
            top_k=6,
        )

        decision = choose_candidate_with_lookahead(
            count_index,
            active["candidates"],
            seed_anchors=["laws", "physics"],
            blocked={"laws", "physics"},
            lookahead_k=3,
        )

        self.assertEqual(decision["chosen"]["anchor"], "motion")
        rejected = {row["anchor"]: row for row in active["rejected_candidates"]}
        self.assertEqual(rejected["mothers"]["reason"], "domain_field_drift")

    def test_answer_surface_preserves_subject_connectors_without_promoting_glue(self) -> None:
        speech = render_anchor_answer_surface(
            ["why", "worry", "about", "laws", "of", "physics", "?"],
            {"terms": [{"anchor": "motion"}, {"anchor": "law"}, {"anchor": "object"}, {"anchor": "acceleration"}]},
        )

        self.assertEqual(
            speech,
            "The answer path around laws of physics points toward motion, law, object, and acceleration.",
        )
        self.assertNotIn("worry, laws", speech)

    def test_clearspeak_answer_assembly_exposes_attention_frame(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            for letter, words in {
                "H": ["how", "heat"],
                "D": ["do"],
                "I": ["i"],
                "S": ["sear"],
                "M": ["meat"],
                "P": ["pan"],
            }.items():
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [{"word": word, "status": "ASSIGNED"} for word in words])
            _write_json(root / "Spare_Slots" / "spare_slots.json", self._shared_spares(10))
            _write_json(root / "Structural" / "structural.json", [{"word": "?", "status": "STRUCTURAL"}])
            store = LexiconStore(root)
            _write_count_read_fixture(store, 
                [
                    {"anchor": "sear", "offset": "+1", "neighbor": "pan", "observations": 7},
                    {"anchor": "meat", "offset": "+1", "neighbor": "pan", "observations": 6},
                    {"anchor": "sear", "offset": "+2", "neighbor": "heat", "observations": 5},
                    {"anchor": "pan", "offset": "+1", "neighbor": "heat", "observations": 4},
                    {"anchor": "pan", "offset": "+2", "neighbor": "surface", "observations": 3},
                ],
                observed_counts=Counter({"sear": 1, "meat": 1, "pan": 1, "heat": 1}),
            )

            result = ClearSpeakService(store).query("How do I sear meat?")

            self.assertEqual(result.answer_assembly["attention_frame"]["frame_type"], "method_question")
            self.assertEqual(result.answer_assembly["attention_frame"]["role_by_anchor"]["sear"], "action_candidate")
            self.assertEqual(result.answer_assembly["schema_version"], "clearspeak_active_cloud_answer@1")
            self.assertEqual(result.answer_assembly["contract"]["active_cloud_answer_walk"], True)
            self.assertEqual(result.answer_assembly["active_cloud_weights"], {"question": 0.35, "rear": 0.25, "answer": 0.3, "forward": 0.1})
            self.assertEqual(result.answer_assembly["trace"][0]["chosen_anchor"], "pan")
            self.assertIn("question_fit", result.answer_assembly["trace"][0]["score_parts"])
            self.assertEqual(result.answer_assembly["trace"][0]["lookahead_decision"]["chosen"]["anchor"], "pan")
            self.assertEqual(result.answer_assembly["trace"][0]["lookahead_decision"]["chosen"]["pattern_health"], "healthy")
            self.assertIn("rejected_candidates", result.answer_assembly["trace"][0])
            self.assertEqual(result.answer_assembly["attention_frame"]["role_by_anchor"]["meat"], "object_candidate")
            self.assertEqual(result.answer_assembly["terms"][0]["anchor"], "pan")
            self.assertEqual(result.answer_assembly["terms"][0]["role_fit"]["matched_roles"], ["action_candidate", "object_candidate"])

    def test_clearspeak_answer_walk_obeys_min_max_anchor_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            for letter, words in {
                "A": ["acceleration"],
                "E": ["energy"],
                "F": ["first", "force"],
                "L": ["laws", "law"],
                "M": ["motion", "mass", "move"],
                "N": ["newton"],
                "O": ["objects"],
                "S": ["second"],
                "T": ["third"],
                "W": ["what"],
            }.items():
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [{"word": word, "status": "ASSIGNED"} for word in words])
            _write_json(root / "Spare_Slots" / "spare_slots.json", self._shared_spares(16))
            _write_json(root / "Structural" / "structural.json", [])
            store = LexiconStore(root)
            _write_count_read_fixture(
                store,
                [
                    {"anchor": "newton", "offset": "+1", "neighbor": "law", "observations": 9},
                    {"anchor": "laws", "offset": "+1", "neighbor": "energy", "observations": 50},
                    {"anchor": "motion", "offset": "+2", "neighbor": "energy", "observations": 50},
                    {"anchor": "laws", "offset": "+1", "neighbor": "first", "observations": 8},
                    {"anchor": "laws", "offset": "+2", "neighbor": "second", "observations": 8},
                    {"anchor": "laws", "offset": "+3", "neighbor": "third", "observations": 8},
                    {"anchor": "motion", "offset": "+1", "neighbor": "objects", "observations": 8},
                    {"anchor": "motion", "offset": "+2", "neighbor": "force", "observations": 7},
                    {"anchor": "force", "offset": "+1", "neighbor": "mass", "observations": 7},
                    {"anchor": "mass", "offset": "+1", "neighbor": "acceleration", "observations": 7},
                    {"anchor": "acceleration", "offset": "+1", "neighbor": "move", "observations": 6},
                    {"anchor": "first", "offset": "+1", "neighbor": "force", "observations": 5},
                    {"anchor": "second", "offset": "+1", "neighbor": "mass", "observations": 5},
                    {"anchor": "third", "offset": "+1", "neighbor": "objects", "observations": 5},
                ],
                observed_counts=Counter({"newton": 1, "laws": 1, "motion": 1}),
            )

            result = ClearSpeakService(store).query("what newton laws motion", min_anchors=8, max_anchors=9)

            self.assertGreaterEqual(len(result.answer_assembly["terms"]), 8)
            self.assertLessEqual(len(result.answer_assembly["terms"]), 9)
            self.assertEqual(result.answer_assembly["length_policy"]["min_anchors"], 8)
            self.assertEqual(result.answer_assembly["length_policy"]["max_anchors"], 9)
            self.assertIn("mechanism", result.answer_assembly["slot_state"]["satisfied_slots"])
            self.assertIn("parts", result.answer_assembly["slot_state"]["satisfied_slots"])
            self.assertIn("length_state", result.answer_assembly["trace"][0])
            self.assertNotEqual(result.answer_assembly["terms"][0]["anchor"], "energy")
            self.assertIn("domain_drift_penalty", result.answer_assembly["trace"][0]["candidate_preview"][0]["penalties"])

    def test_clearspeak_can_read_external_lifetime_by_symbol_mirror(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            mirror = Path(temp_dir) / "Historical" / "State" / "lifetime_by_symbol"
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            for letter, words in {
                "S": ["sear"],
                "M": ["meat"],
                "P": ["pan"],
            }.items():
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [{"word": word, "status": "ASSIGNED"} for word in words])
            _write_json(root / "Spare_Slots" / "spare_slots.json", self._shared_spares(10))
            _write_json(root / "Structural" / "structural.json", [])
            _write_json(
                mirror / "AA" / "0xSEAR.json",
                {
                    "schema_version": "lifetime_symbol_counts@1",
                    "symbol": "0xSEAR",
                    "anchor": "sear",
                    "total_observations": 7,
                    "neighbors": {
                        "+1": [{"anchor": "pan", "symbol": "0xPAN", "count": 7}],
                    },
                },
            )
            previous = os.environ.get("ANCHORWORKS_LIFETIME_BY_SYMBOL_DIR")
            os.environ["ANCHORWORKS_LIFETIME_BY_SYMBOL_DIR"] = str(mirror)
            try:
                result = ClearSpeakService(LexiconStore(root)).query("sear")
            finally:
                if previous is None:
                    os.environ.pop("ANCHORWORKS_LIFETIME_BY_SYMBOL_DIR", None)
                else:
                    os.environ["ANCHORWORKS_LIFETIME_BY_SYMBOL_DIR"] = previous

            self.assertEqual(result.evidence[0]["anchor"], "sear")
            self.assertEqual(result.evidence[0]["neighbors"][0], {"anchor": "pan", "observations": 7})
            self.assertEqual(result.answer_assembly["terms"][0]["anchor"], "pan")

    def test_clearspeak_reads_awsc_binary_cells_as_count_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            _write_json(root / "Canonical" / "canonical_A.json", [{"word": "alpha", "hex": "0x0000000001", "status": "ASSIGNED"}])
            _write_json(root / "Canonical" / "canonical_B.json", [{"word": "beta", "hex": "0x0000000002", "status": "ASSIGNED"}])
            _write_json(root / "Canonical" / "canonical_G.json", [{"word": "gamma", "hex": "0x0000000003", "status": "ASSIGNED"}])
            _write_json(root / "Canonical" / "canonical_D.json", [{"word": "delta", "hex": "0x0000000004", "status": "ASSIGNED"}])
            _write_json(root / "Spare_Slots" / "spare_slots.json", self._shared_spares(10))
            _write_json(root / "Structural" / "structural.json", [])
            store = LexiconStore(root)
            write_symbol_cell(
                store.symbol_counts_binary_dir / "cells" / "00" / "0000000001.cell",
                symbol="0x0000000001",
                root_lane=CANONICAL_LANE,
                relations=[SymbolRelation(offset=1, neighbor_symbol="0x0000000002", count=9)],
            )
            write_symbol_cell(
                store.symbol_counts_binary_dir / "cells" / "00" / "0000000002.cell",
                symbol="0x0000000002",
                root_lane=CANONICAL_LANE,
                relations=[
                    SymbolRelation(offset=1, neighbor_symbol="0x0000000003", count=6),
                    SymbolRelation(offset=2, neighbor_symbol="0x0000000004", count=5),
                ],
            )

            result = ClearSpeakService(store).query("alpha", limit=3)

            self.assertEqual(result.speech, "The active path connects alpha with beta, gamma, and delta.")
            self.assertEqual(result.evidence[0]["anchor"], "alpha")
            self.assertEqual(result.evidence[0]["neighbors"][0]["anchor"], "beta")
            self.assertEqual(result.answer_assembly["trace"][0]["lookahead_decision"]["chosen"]["pattern_health"], "healthy")

    def test_clearspeak_reads_old_awsc_cells_through_genome_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            _write_json(root / "Canonical" / "canonical_A.json", [{"word": "alpha", "symbol": "0x1000000001"}])
            _write_json(root / "Canonical" / "canonical_B.json", [{"word": "beta", "symbol": "0x1000000002"}])
            _write_json(root / "Canonical" / "canonical_G.json", [{"word": "gamma", "symbol": "0x1000000003"}])
            _write_json(root / "Structural" / "structural.json", [])
            mapping_path = root / "Lexicon_Genome_Rebuild" / "mappings" / "old_symbol_to_genome_symbol.jsonl"
            mapping_path.parent.mkdir(parents=True, exist_ok=True)
            mapping_path.write_text(
                "\n".join(
                    json.dumps(row)
                    for row in [
                        {"anchor": "alpha", "old_symbol": "0x0000000001", "genome_symbol": "0x1000000001", "pack": "canonical"},
                        {"anchor": "beta", "old_symbol": "0x0000000002", "genome_symbol": "0x1000000002", "pack": "canonical"},
                        {"anchor": "gamma", "old_symbol": "0x0000000003", "genome_symbol": "0x1000000003", "pack": "canonical"},
                    ]
                ),
                encoding="utf-8",
            )
            store = LexiconStore(root)
            write_symbol_cell(
                store.symbol_counts_binary_dir / "cells" / "00" / "0000000001.cell",
                symbol="0x0000000001",
                root_lane=CANONICAL_LANE,
                relations=[SymbolRelation(offset=1, neighbor_symbol="0x0000000002", count=9)],
            )
            write_symbol_cell(
                store.symbol_counts_binary_dir / "cells" / "00" / "0000000002.cell",
                symbol="0x0000000002",
                root_lane=CANONICAL_LANE,
                relations=[SymbolRelation(offset=1, neighbor_symbol="0x0000000003", count=6)],
            )

            result = ClearSpeakService(store).query("alpha", limit=2)

            self.assertEqual(result.speech, "The active path connects alpha with beta and gamma.")
            self.assertEqual(result.evidence[0]["anchor"], "alpha")
            self.assertEqual(result.evidence[0]["neighbors"][0]["anchor"], "beta")
            self.assertTrue(result.answer_assembly["terms"])

    def test_anchor_rows_preserve_surface_and_fused_boundaries(self) -> None:
        fused_rows = extract_anchor_rows("state-of-the-art")
        spaced_rows = extract_anchor_rows("state - of - the - art")

        self.assertEqual([row["anchor"] for row in fused_rows], ["state", "-", "of", "-", "the", "-", "art"])
        self.assertEqual([row["anchor"] for row in spaced_rows], ["state", "-", "of", "-", "the", "-", "art"])
        self.assertEqual([row["surface"] for row in fused_rows], ["state", "-", "of", "-", "the", "-", "art"])

        fused_map = build_anchor_map("state-of-the-art")
        spaced_map = build_anchor_map("state - of - the - art")

        fused_anchor = fused_map["occurrences"][0]
        fused_hyphen = fused_map["occurrences"][1]
        spaced_hyphen = spaced_map["occurrences"][1]

        self.assertEqual(fused_anchor["anchor"], "state")
        self.assertEqual(fused_anchor["surface"], "state")
        self.assertTrue(fused_anchor["joined_left"])
        self.assertTrue(fused_anchor["joined_right"])
        self.assertEqual(fused_anchor["gap_before"], "")
        self.assertEqual(fused_anchor["gap_after"], "")
        self.assertEqual(fused_hyphen["anchor"], "-")
        self.assertTrue(fused_hyphen["joined_left"])
        self.assertTrue(fused_hyphen["joined_right"])
        self.assertFalse(spaced_hyphen["joined_left"])
        self.assertFalse(spaced_hyphen["joined_right"])
        self.assertEqual(spaced_hyphen["gap_before"], " ")
        self.assertEqual(spaced_hyphen["gap_after"], " ")

    def test_extract_anchors_preserves_fused_numeric_and_symbol_strings(self) -> None:
        anchors = extract_anchors("1997 876-RT54TX-67%% stop .")
        self.assertEqual(anchors, ["1", "9", "9", "7", "8", "7", "6", "-", "r", "t", "5", "4", "t", "x", "-", "6", "7", "%", "%", "stop", "."])

    def test_punctuation_inside_non_whitespace_runs_becomes_own_anchor(self) -> None:
        self.assertEqual(extract_anchors("high-accuracy"), ["high", "-", "accuracy"])
        self.assertEqual(extract_anchors("them)"), ["them", ")"])
        self.assertEqual(extract_anchors("(hello)"), ["(", "hello", ")"])
        self.assertEqual(extract_anchors("value=10"), ["value", "=", "1", "0"])
        self.assertEqual(extract_anchors("**Limitations:**"), ["*", "*", "limitations", ":", "*", "*"])

    def test_compose_anchor_stream_keeps_surface_and_adds_atomic_sequence(self) -> None:
        self.assertEqual(compose_anchor_stream("1997"), ["1", "9", "9", "7"])
        self.assertEqual(
            compose_anchor_stream("876-RT54TX-67%%"),
            ["8", "7", "6", "-", "r", "t", "5", "4", "t", "x", "-", "6", "7", "%", "%"],
        )
        self.assertEqual(compose_anchor_stream("dontpanic"), ["dontpanic"])
        self.assertEqual(compose_anchor_stream("don't"), ["don't"])
        self.assertEqual(compose_anchor_stream("NASA"), ["n", "a", "s", "a"])

    def test_long_mixed_export_ids_become_one_non_counting_string_literal(self) -> None:
        export_id = (
            "05b6e602532b3d075340cbcc28a8c83e4d269fb9a6179f9cc2c87c077f3584ee"
            "-2024-12-25-10-42-46-51d6578a718b4f5fb88caad3bf4ce7f1"
        )
        rows = extract_anchor_rows(export_id)
        mapping = build_anchor_map(export_id)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["anchor"], export_id)
        self.assertEqual(rows[0]["kind"], "string_literal")
        self.assertFalse(rows[0]["count_eligible"])
        self.assertEqual(rows[0]["literal_stream"], list(export_id))
        self.assertEqual(compose_anchor_stream(export_id), list(export_id))
        self.assertEqual(mapping["observed_counts"], Counter())
        self.assertEqual(mapping["co_occurrence_counts"], [])
        self.assertEqual(mapping["paragraphs"][0]["anchors"], [export_id])
        self.assertEqual(mapping["paragraphs"][0]["countable_anchor_count"], 0)
        self.assertEqual(mapping["occurrences"][0]["kind"], "string_literal")
        self.assertFalse(mapping["occurrences"][0]["count_eligible"])

    def test_document_prep_converts_structured_files_before_intake(self) -> None:
        csv_doc = prepare_bytes(
            b"Material,Density\nCopper,8.96\nTungsten,19.25\n",
            source_name="materials.csv",
            file_type="text/csv",
        )
        json_doc = prepare_bytes(
            b'{"system":"anchorworks","values":[1,2]}',
            source_name="system.json",
            file_type="application/json",
        )
        xml_doc = prepare_bytes(
            b"<root><item kind=\"metal\">Copper</item></root>",
            source_name="items.xml",
            file_type="application/xml",
        )

        self.assertEqual(csv_doc.converter, "delimited-table")
        self.assertIn("[TABLE: materials]", csv_doc.prepared_text)
        self.assertIn("Material | Density", csv_doc.prepared_text)
        self.assertEqual(json_doc.converter, "json-structure")
        self.assertIn("root.system | str | anchorworks", json_doc.prepared_text)
        self.assertEqual(xml_doc.converter, "xml-structure")
        self.assertIn("Copper", xml_doc.prepared_text)
        self.assertNotIn("[ELEMENT: item]", xml_doc.prepared_text)
        self.assertNotIn("[ATTR: kind]", xml_doc.prepared_text)

    def test_cnxml_prep_keeps_visible_text_and_drops_markup_from_anchor_inventory(self) -> None:
        doc = prepare_bytes(
            b'<document xmlns:m="http://www.w3.org/1998/Math/MathML"><para id="ch01_rques01p">Review text <m:math><m:mrow><m:mi>x</m:mi></m:mrow></m:math>.</para></document>',
            source_name="index.cnxml",
            file_type="application/xml",
        )
        anchors = extract_anchors(doc.prepared_text)

        self.assertEqual(doc.converter, "xml-structure")
        self.assertIn("Review text", doc.prepared_text)
        self.assertNotIn("mrow", anchors)
        self.assertNotIn("rques", anchors)
        self.assertNotIn("xmlns", anchors)
        self.assertIn("review", anchors)
        self.assertIn("text", anchors)

    def test_xml_prep_repairs_common_mojibake_before_anchor_extraction(self) -> None:
        doc = prepare_bytes(
            "<document><para>Earthâ€™s orbit uses Ï€ and âˆ’ signs.</para></document>".encode("utf-8"),
            source_name="index.cnxml",
            file_type="application/xml",
        )
        anchors = extract_anchors(doc.prepared_text)

        self.assertIn("Earth’s", doc.prepared_text)
        self.assertIn("π", doc.prepared_text)
        self.assertIn("−", doc.prepared_text)
        self.assertIn("earth's", anchors)
        self.assertNotIn("earthâ€™s", anchors)
        self.assertNotIn("Ï€", anchors)

    def test_xml_prep_repairs_accented_name_and_ligature_mojibake(self) -> None:
        doc = prepare_bytes(
            "<document><para>Ã§atalhÃ¶yÃ¼k and ï¬rst floor</para></document>".encode("utf-8"),
            source_name="index.cnxml",
            file_type="application/xml",
        )

        self.assertIn("çatalhöyük", doc.prepared_text)
        self.assertIn("first floor", doc.prepared_text)
        self.assertNotIn("Ã§atalhÃ¶yÃ¼k", doc.prepared_text)
        self.assertNotIn("ï¬rst", doc.prepared_text)

    def test_document_prep_strips_visual_leaders_before_anchor_extraction(self) -> None:
        doc = prepare_bytes(
            "├── Alpha\n│   └── Beta\n────\nGamma".encode("utf-8"),
            source_name="leaders.md",
            file_type="text/markdown",
        )

        self.assertNotIn("├", doc.prepared_text)
        self.assertNotIn("└", doc.prepared_text)
        self.assertNotIn("─", doc.prepared_text)
        self.assertEqual(doc.metadata["stripped_visual_leader_characters"], 11)
        self.assertEqual(extract_anchors(doc.prepared_text), ["alpha", "beta", "gamma"])

    def test_chat_bridge_formats_turns_as_paragraph_safe_blocks(self) -> None:
        payload = {
            "title": "Anchor Talk",
            "mapping": {
                "one": {
                    "message": {
                        "author": {"role": "user"},
                        "create_time": 1710000000,
                        "content": {"parts": ["alpha omega"]},
                    }
                },
                "two": {
                    "message": {
                        "author": {"role": "assistant"},
                        "create_time": 1710000001,
                        "content": {"parts": ["beta gamma"]},
                    }
                },
            },
        }
        doc = prepare_bytes(
            json.dumps(payload).encode("utf-8"),
            source_name="conversation.json",
            file_type="application/json",
        )
        mapping = build_anchor_map(doc.prepared_text)
        relation_pairs = {
            (row["anchor"], row["offset"], row["neighbor"])
            for row in mapping["co_occurrence_counts"]
        }

        self.assertEqual(doc.converter, "chat-memory-bridge")
        self.assertEqual(doc.metadata["kind"], "chat")
        self.assertEqual(doc.metadata["message_count"], 2)
        self.assertIn("[CHAT: Anchor Talk]", doc.prepared_text)
        self.assertIn("[TURN: 1]", doc.prepared_text)
        self.assertIn("[ROLE: user]", doc.prepared_text)
        self.assertIn("\n\n[TURN: 2]", doc.prepared_text)
        self.assertNotIn(("omega", "+1", "["), relation_pairs)

    def test_memory_bridge_formats_memory_items_for_intake(self) -> None:
        payload = {
            "memories": [
                {"source": "chat", "created_at": "2026-05-01", "memory": "preserve exact anchors"},
                {"source": "manual", "memory": "paragraph boundaries matter"},
            ]
        }
        doc = prepare_bytes(
            json.dumps(payload).encode("utf-8"),
            source_name="memories.json",
            file_type="application/json",
        )

        self.assertEqual(doc.converter, "chat-memory-bridge")
        self.assertEqual(doc.metadata["kind"], "memory")
        self.assertEqual(doc.metadata["memory_count"], 2)
        self.assertIn("[MEMORY_COLLECTION: memories]", doc.prepared_text)
        self.assertIn("[MEMORY_ITEM: 1]", doc.prepared_text)
        self.assertIn("preserve exact anchors", doc.prepared_text)

    def test_anchorworks_chat_archive_bridge_preserves_chat_memory_and_citations_for_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            archive = Path(temp_dir) / "OldAnchorWorks"
            data = archive / "data"
            chats = data / "chats"
            citations = data / "citations"
            notes = data / "notes"
            summaries = data / "summaries"
            lessons = data / "memory" / "lessons"
            reasoning = data / "memory" / "reasoning"
            packs = data / "chat_packs" / "packs" / "starter"

            chats.mkdir(parents=True)
            citations.mkdir(parents=True)
            notes.mkdir(parents=True)
            summaries.mkdir(parents=True)
            lessons.mkdir(parents=True)
            reasoning.mkdir(parents=True)
            packs.mkdir(parents=True)

            (chats / "2026-05-01.jsonl").write_text(
                "\n".join([
                    json.dumps({"id": 1, "sender": "user", "branch": "main", "content": "anchor maps matter", "message_uuid": "u1"}),
                    json.dumps({"id": 2, "sender": "assistant", "branch": "main", "content": "counts remain durable", "message_uuid": "a1"}),
                ]),
                encoding="utf-8",
            )
            _write_json(
                citations / "2026-05-01.citations.json",
                {
                    "by_block": {
                        "a1:b0": [
                            {
                                "cite_id": "cite_abc",
                                "coord": "2026-05-01:L2",
                                "source": "ui",
                                "subject": "durable counts",
                            }
                        ]
                    },
                    "by_id": {
                        "cite_abc": {
                            "cite_id": "cite_abc",
                            "coord": "2026-05-01:L2",
                            "source": "ui",
                            "subject": "durable counts",
                        }
                    },
                },
            )
            _write_json(
                notes / "2026-05-01.notes.json",
                {
                    "by_id": {
                        "note_abc": {
                            "note_id": "note_abc",
                            "message_id": "a1",
                            "block_id": "b0",
                            "text": "review this claim",
                        }
                    }
                },
            )
            (summaries / "2026-05-01.txt").write_text("Daily summary keeps the trail.", encoding="utf-8")
            (lessons / "2026-05-01.jsonl").write_text(json.dumps({"type": "decision", "lesson": "approve anchors first"}) + "\n", encoding="utf-8")
            (reasoning / "2026-05-01.jsonl").write_text(json.dumps({"event": "chain", "summary": "follow grounded order"}) + "\n", encoding="utf-8")
            (data / "memory" / "side_chats.json").write_text(json.dumps({"side_a": {"description": "deep branch", "main_branch": "main"}}), encoding="utf-8")
            (packs / "metadata.json").write_text(json.dumps({"pack_id": "starter", "title": "Starter Pack"}), encoding="utf-8")
            (packs / "lesson.txt").write_text("Lesson content.", encoding="utf-8")

            prepared = prepare_anchorworks_chat_archive(archive)
            self.assertEqual(prepared.converter, "anchorworks-chat-archive-bridge")
            self.assertEqual(prepared.metadata["chat_days"], 1)
            self.assertEqual(prepared.metadata["chat_messages"], 2)
            self.assertEqual(prepared.metadata["citations"], 1)
            self.assertEqual(prepared.metadata["notes"], 1)
            self.assertEqual(prepared.metadata["side_chats"], 1)
            self.assertEqual(prepared.metadata["lessons"], 1)
            self.assertEqual(prepared.metadata["reasoning_records"], 1)
            self.assertIn("[CHAT_MESSAGE]", prepared.prepared_text)
            self.assertIn("[CITATION: cite_abc]", prepared.prepared_text)
            self.assertIn("[NOTE: note_abc]", prepared.prepared_text)
            self.assertIn("[SIDE_CHAT: side_a]", prepared.prepared_text)
            self.assertIn("approve anchors first", prepared.prepared_text)
            self.assertIn("Starter Pack", prepared.prepared_text)

    def test_chat_archive_intake_prepare_does_not_map_or_count(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            _write_json(root / "Spare_Slots" / "spare_slots.json", self._shared_spares(10))
            _write_json(root / "Structural" / "structural.json", [])

            archive = Path(temp_dir) / "OldAnchorWorks" / "data" / "chats"
            archive.mkdir(parents=True)
            (archive / "2026-05-01.jsonl").write_text(
                json.dumps({"id": 1, "sender": "user", "content": "new archive anchor"}) + "\n",
                encoding="utf-8",
            )

            store = LexiconStore(root)
            before_lifetime = store._read_json(store.lifetime_counts_path, {})
            prepared = store.prepare_chat_archive_intake(Path(temp_dir) / "OldAnchorWorks")
            preview = store.preview_document_intake(
                source_name=prepared["source_name"],
                content=prepared["prepared_text"],
                file_size=prepared["original_size"],
                file_type=prepared["file_type"],
                source_path=prepared["source_path"],
            )

            self.assertEqual(prepared["converter"], "anchorworks-chat-archive-bridge")
            self.assertGreater(preview["missing_anchor_count"], 0)
            self.assertEqual(store.observed_map_files()["files"], [])
            self.assertEqual(store._read_json(store.lifetime_counts_path, {}), before_lifetime)

    def test_clearspeak_queries_lifetime_anchor_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            _write_json(root / "Canonical" / "canonical_S.json", [{"word": "stop", "status": "ASSIGNED"}])
            _write_json(root / "Canonical" / "canonical_N.json", [{"word": "not", "status": "ASSIGNED"}])
            _write_json(root / "Spare_Slots" / "spare_slots.json", self._shared_spares(10))
            _write_json(root / "Structural" / "structural.json", [])

            store = LexiconStore(root)
            _write_count_read_fixture(store, 
                [
                    {"anchor": "stop", "offset": "-1", "neighbor": "not", "observations": 3},
                    {"anchor": "stop", "offset": "+1", "neighbor": ".", "observations": 2},
                ],
                observed_counts=Counter({"stop": 4, "not": 3}),
            )

            result = ClearSpeakService(store).query("stop mystery")

            self.assertEqual(result.represented_anchors, ["stop"])
            self.assertEqual(result.missing_anchors, ["mystery"])
            self.assertIn("stop: not (3), . (2)", result.response)
            self.assertEqual(result.citations[0]["source"], "clearspeak_lifetime_counts")

    def test_clearspeak_walks_topk_without_speaking_punctuation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            _write_json(root / "Canonical" / "canonical_A.json", [{"word": "armor", "status": "ASSIGNED"}])
            _write_json(root / "Canonical" / "canonical_D.json", [{"word": "defense", "status": "ASSIGNED"}])
            _write_json(root / "Canonical" / "canonical_E.json", [{"word": "emp", "status": "ASSIGNED"}])
            _write_json(root / "Spare_Slots" / "spare_slots.json", self._shared_spares(10))
            _write_json(root / "Structural" / "structural.json", [{"word": ".", "status": "STRUCTURAL"}])

            store = LexiconStore(root)
            _write_count_read_fixture(store, 
                [
                    {"anchor": "emp", "offset": "+1", "neighbor": ".", "observations": 99},
                    {"anchor": "emp", "offset": "+2", "neighbor": "defense", "observations": 12},
                    {"anchor": "defense", "offset": "+1", "neighbor": "armor", "observations": 8},
                ],
                observed_counts=Counter({"emp": 1, "defense": 1, "armor": 1, ".": 1}),
            )

            result = ClearSpeakService(store).query("emp")

            self.assertIn("Count-assembled answer terms: defense, armor", result.response)
            self.assertIn("emp: . (99), defense (12)", result.response)
            self.assertEqual([row["anchor"] for row in result.answer_assembly["terms"][:2]], ["defense", "armor"])
            self.assertTrue(result.answer_assembly["contract"]["topk_is_walked_not_displayed"])

    def test_clearspeak_status_route_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            app = create_app(root)
            store = app.state.store
            _write_count_read_fixture(store, 
                [{"anchor": "stop", "offset": "-1", "neighbor": "not", "observations": 2}],
                observed_counts=Counter({"stop": 1, "not": 1}),
            )

            def snapshot() -> dict[str, str]:
                return {
                    str(path.relative_to(root)): path.read_text(encoding="utf-8")
                    for path in sorted(root.rglob("*"))
                    if path.is_file()
                }

            before = snapshot()
            route = next(route for route in app.routes if getattr(route, "path", "") == "/api/clearspeak/status")
            status = route.endpoint()
            after = snapshot()

            self.assertTrue(status["ok"])
            self.assertTrue(status["legacy_json_counts_removed"])
            self.assertEqual(status["runtime"], "awsc_v1_1_binary_cells")
            self.assertEqual(before, after)
            self.assertEqual(list((root / "State" / "chat_memory" / "chats").glob("*.jsonl")), [])

    def test_clearspeak_query_route_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            _write_json(root / "Canonical" / "canonical_S.json", [{"word": "stop", "status": "ASSIGNED"}])
            _write_json(root / "Canonical" / "canonical_N.json", [{"word": "not", "status": "ASSIGNED"}])
            _write_json(root / "Spare_Slots" / "spare_slots.json", self._shared_spares(10))
            _write_json(root / "Structural" / "structural.json", [])
            app = create_app(root)
            store = app.state.store
            _write_count_read_fixture(store, 
                [{"anchor": "stop", "offset": "-1", "neighbor": "not", "observations": 4}],
                observed_counts=Counter({"stop": 1, "not": 1}),
            )

            def snapshot() -> dict[str, str]:
                return {
                    str(path.relative_to(root)): path.read_text(encoding="utf-8")
                    for path in sorted(root.rglob("*"))
                    if path.is_file()
                }

            before = snapshot()
            route = next(route for route in app.routes if getattr(route, "path", "") == "/api/clearspeak/query")
            result = route.endpoint(ClearSpeakQueryBody(query="stop mystery", limit=6))
            after = snapshot()

            self.assertEqual(result["represented_anchors"], ["stop"])
            self.assertEqual(result["missing_anchors"], ["mystery"])
            self.assertEqual(result["speech"], "The active path connects stop with not.")
            self.assertEqual(result["citations"][0]["coord"], "clearspeak:lifetime:stop")
            self.assertIn("stop: not (4)", result["response"])
            self.assertEqual(before, after)
            self.assertEqual(list((root / "State" / "chat_memory" / "chats").glob("*.jsonl")), [])

    def test_document_only_clearspeak_no_support_preserves_lexicon_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            _write_json(root / "Canonical" / "canonical_H.json", [{"word": "hello", "hex": "0x042CF24DBA", "status": "ASSIGNED"}])
            _write_json(root / "Spare_Slots" / "spare_slots.json", [])
            _write_json(root / "Structural" / "structural.json", [])

            app = create_app(root)
            route = next(route for route in app.routes if getattr(route, "path", "") == "/api/clearspeak/query")
            result = route.endpoint(ClearSpeakQueryBody(query="hello", limit=6, evidence_mode="documents"))

            self.assertEqual(result["query_anchors"], ["hello"])
            self.assertEqual(result["represented_anchors"], ["hello"])
            self.assertEqual(result["missing_anchors"], [])
            self.assertTrue(result["lexicon_recognition"]["lexicon_first"])
            self.assertIn("lexicon", result["response"].lower())
            self.assertEqual(result["evidence_mode"], "documents")
            self.assertEqual(result["engine"], "document_answer_no_map_support")

    def test_chat_memory_system_logs_clearspeak_response_and_citation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            _write_json(root / "Canonical" / "canonical_S.json", [{"word": "stop", "status": "ASSIGNED"}])
            _write_json(root / "Canonical" / "canonical_N.json", [{"word": "not", "status": "ASSIGNED"}])
            _write_json(root / "Spare_Slots" / "spare_slots.json", self._shared_spares(10))
            _write_json(root / "Structural" / "structural.json", [{"word": ".", "status": "STRUCTURAL"}])

            store = LexiconStore(root)
            _write_count_read_fixture(store, 
                [{"anchor": "stop", "offset": "-1", "neighbor": "not", "observations": 2}],
                observed_counts=Counter({"stop": 1, "not": 1}),
            )
            chat = ChatMemorySystem(root, ClearSpeakService(store))
            result = chat.send("stop", mode="clearspeak", branch="main")
            history = chat.history(branch="main")
            status = chat.status()

            self.assertTrue(result.ok)
            self.assertEqual(len(history["messages"]), 2)
            self.assertEqual(history["messages"][0]["sender"], "user")
            self.assertEqual(history["messages"][1]["sender"], "assistant")
            self.assertEqual(history["messages"][1]["content"], "The active path connects stop with not.")
            self.assertEqual(result.response, "The active path connects stop with not.")
            self.assertEqual(status["chat_messages"], 2)
            self.assertEqual(status["citations"], 1)
            self.assertTrue(history["citations_by_block"])

    def test_observed_map_evidence_returns_source_passages_with_line_locators(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            _write_json(root / "Canonical" / "canonical_E.json", [{"word": "emp", "status": "ASSIGNED"}])
            _write_json(root / "Canonical" / "canonical_D.json", [{"word": "defense", "status": "ASSIGNED"}])
            _write_json(root / "Canonical" / "canonical_R.json", [{"word": "requires", "status": "ASSIGNED"}])
            _write_json(root / "Canonical" / "canonical_S.json", [{"word": "shielding", "status": "ASSIGNED"}])
            _write_json(root / "Canonical" / "canonical_A.json", [{"word": "and", "status": "ASSIGNED"}])
            _write_json(root / "Canonical" / "canonical_G.json", [{"word": "grounding", "status": "ASSIGNED"}])
            _write_json(root / "Spare_Slots" / "spare_slots.json", self._shared_spares(10))
            _write_json(root / "Structural" / "structural.json", [{"word": ".", "status": "STRUCTURAL"}])
            source_path = Path(temp_dir) / "emp_notes.txt"
            source_path.write_text(
                "unrelated opening.\n\nemp defense requires shielding and grounding.\n\nunrelated closing.",
                encoding="utf-8",
            )

            store = LexiconStore(root)
            result = store.build_observed_map(source_path)
            evidence = store.search_observed_map_evidence(["emp"], query_anchors=["emp"])
            passages = evidence["source_passages"]

            self.assertTrue(result["ok"])
            self.assertEqual(evidence["maps_with_query_symbols"], 1)
            self.assertEqual(passages[0]["block_id"], 1)
            self.assertEqual(passages[0]["line_start"], 3)
            self.assertEqual(passages[0]["line_end"], 3)
            self.assertIn("emp defense requires", passages[0]["text"])

    def test_document_answer_uses_topic_anchors_not_source_query_wrapper(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            _write_json(root / "Canonical" / "canonical_A.json", [{"word": "about", "status": "ASSIGNED"}])
            _write_json(root / "Canonical" / "canonical_D.json", [{"word": "does", "status": "ASSIGNED"}])
            _write_json(root / "Canonical" / "canonical_O.json", [{"word": "of", "status": "ASSIGNED"}])
            _write_json(root / "Canonical" / "canonical_P.json", [{"word": "powers", "status": "ASSIGNED"}])
            _write_json(
                root / "Canonical" / "canonical_S.json",
                [
                    {"word": "say", "status": "ASSIGNED"},
                    {"word": "separation", "status": "ASSIGNED"},
                    {"word": "source", "status": "ASSIGNED"},
                ],
            )
            _write_json(root / "Canonical" / "canonical_T.json", [{"word": "the", "status": "ASSIGNED"}])
            _write_json(root / "Canonical" / "canonical_W.json", [{"word": "what", "status": "ASSIGNED"}])
            _write_json(root / "Spare_Slots" / "spare_slots.json", [])
            _write_json(root / "Structural" / "structural.json", [{"word": "?", "status": "STRUCTURAL"}])

            source_path = Path(temp_dir) / "government.txt"
            source_path.write_text(
                "The source introduction says many ordinary things.\n\n"
                "Separation of powers divides government authority among branches.",
                encoding="utf-8",
            )

            store = LexiconStore(root)
            observed = store.build_observed_map(source_path)
            store.build_flat_runtime_from_observed_map(observed["saved_map_name"])

            answer = DocumentAnswerAssembler(store).answer("What does the source say about separation of powers?")

            self.assertTrue(answer.ok)
            self.assertEqual(answer.query_anchors, ["separation", "powers"])
            self.assertEqual(answer.represented_anchors, ["separation", "powers"])
            self.assertEqual(answer.missing_anchors, [])
            self.assertTrue(answer.lexicon_recognition["lexicon_first"])
            self.assertIn("what", answer.lexicon_recognition["represented_anchors"])
            self.assertIn("Separation of powers divides", answer.response)

    def test_flat_runtime_builds_block_occurrence_and_visual_link_indexes_from_observed_map(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            for letter, words in {
                "E": ["emp"],
                "D": ["defense"],
                "R": ["requires"],
                "S": ["shielding"],
                "A": ["and"],
                "G": ["grounding"],
            }.items():
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [{"word": word, "status": "ASSIGNED"} for word in words])
            _write_json(root / "Spare_Slots" / "spare_slots.json", self._shared_spares(10))
            _write_json(root / "Structural" / "structural.json", [{"word": ".", "status": "STRUCTURAL"}])
            source_path = Path(temp_dir) / "emp_notes.txt"
            source_path.write_text(
                "title line\n\nemp defense requires shielding and grounding.",
                encoding="utf-8",
            )

            store = LexiconStore(root)
            observed = store.build_observed_map(source_path)
            observed_path = Path(observed["saved_map_path"])
            payload = json.loads(observed_path.read_text(encoding="utf-8"))
            payload["paragraphs"][1]["visual_refs"] = [
                {
                    "visual_record_id": "vis_emp_graph",
                    "kind": "graph",
                    "source_path": "figures/emp_graph.png",
                    "caption_block_id": "block_2",
                    "manifest_id": "manifest_emp_graph",
                    "geometry_status": "known",
                    "recognition_status": "not_run",
                }
            ]
            observed_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

            result = store.build_flat_runtime_from_observed_map(observed["saved_map_name"])

            self.assertTrue(Path(result["symbolic_document_path"]).exists())
            self.assertTrue(Path(result["block_index_path"]).exists())
            self.assertTrue(Path(result["occurrence_index_path"]).exists())
            self.assertTrue(Path(result["visual_links_path"]).exists())
            self.assertTrue(Path(result["local_overlay_path"]).exists())
            self.assertTrue(Path(observed["saved_map_path"]).exists())
            self.assertEqual(result["block_count"], 2)
            self.assertEqual(result["visual_link_count"], 1)
            self.assertGreater(result["local_overlay_relation_count"], 0)
            self.assertEqual(result["writes_allowed"], {"maps": False, "counts": False, "lifetime": False, "lexicon": False})

            block_rows = [json.loads(line) for line in Path(result["block_index_path"]).read_text(encoding="utf-8").splitlines()]
            self.assertEqual(block_rows[1]["block_id"], "block_1")
            self.assertEqual(block_rows[1]["line_start"], 3)
            self.assertEqual(block_rows[1]["line_end"], 3)
            self.assertEqual(block_rows[1]["visual_refs"][0]["visual_record_id"], "vis_emp_graph")

            evidence = store.search_flat_document_evidence(["emp"], query_anchors=["emp"])
            passage = evidence["source_passages"][0]
            self.assertEqual(evidence["runtime_source"], "flat_symbolic_documents")
            self.assertEqual(passage["block_id"], 1)
            self.assertEqual(passage["visual_refs"][0]["visual_record_id"], "vis_emp_graph")
            overlay = load_local_meta_count_overlay(result["local_overlay_path"])
            self.assertEqual(overlay["source_id"], result["source_id"])
            self.assertEqual(overlay["locator_ref"], result["block_index_path"])
            self.assertEqual(overlay["visual_ref_locator_ref"], result["visual_links_path"])
            self.assertEqual(overlay["block_relation_index"]["block_1"]["line_start"], 3)

    def test_local_meta_overlay_builds_from_flat_doc_and_queries_neighbors(self) -> None:
        symbolic_flat_doc = {
            "schema_version": "flat_symbolic_document@2",
            "saved_document_name": "emp.symbolic.json",
            "blocks": [
                {"block_id": "block_0", "line_start": 1, "line_end": 1, "anchor_stream": ["title", "line"]},
                {"block_id": "block_1", "line_start": 3, "line_end": 3, "anchor_stream": ["emp", "defense", "requires", "shielding", "grounding"]},
            ],
        }
        locator_sidecar = {"path": "emp.blocks.jsonl"}

        overlay = build_local_meta_count_overlay("source_emp", symbolic_flat_doc, locator_sidecar, observed_map_debug="emp.observed.json")
        cloud = query_local_overlay_cloud(["emp"], overlay, top_k=3)

        self.assertEqual(overlay["schema_version"], "anchorworks_local_meta_count_overlay@1")
        self.assertEqual(overlay["symbolized_flat_doc_ref"], "emp.symbolic.json")
        self.assertEqual(overlay["locator_ref"], "emp.blocks.jsonl")
        self.assertEqual(overlay["created_from_observed_map"], "emp.observed.json")
        self.assertEqual(overlay["block_relation_index"]["block_1"]["line_start"], 3)
        self.assertEqual(overlay["local_symbol_counts"]["emp"], 1)
        self.assertEqual(cloud["neighbors"][0]["symbol"], "defense")
        self.assertEqual(cloud["neighbors"][0]["locator_refs"][0]["block_id"], "block_1")

    def test_renderer_candidate_score_matches_local_global_formula(self) -> None:
        score = score_candidate(
            local_fit=0.8,
            global_fit=0.4,
            role_fit=0.5,
            source_locator_support=1.0,
            penalties={"glue": 0.1},
        )

        self.assertEqual(score["weights"], {"local": 0.45, "global": 0.25, "role": 0.2, "source_locator": 0.1})
        self.assertAlmostEqual(score["score"], 0.56)

    def test_phrase_lexicon_is_external_and_rebuilds_anchor_phrase_refs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            for letter, entries in {
                "N": [{"word": "newton", "hex": "0x0000000001", "status": "ASSIGNED", "tone_signature": "TONE_N"}],
                "L": [{"word": "laws", "hex": "0x0000000002", "status": "ASSIGNED", "tone_signature": "TONE_L"}],
                "O": [{"word": "of", "hex": "0x0000000003", "status": "ASSIGNED", "tone_signature": "TONE_O"}],
                "M": [{"word": "motion", "hex": "0x0000000004", "status": "ASSIGNED", "tone_signature": "TONE_M"}],
            }.items():
                _write_json(root / "Canonical" / f"canonical_{letter}.json", entries)
            _write_json(root / "Spare_Slots" / "spare_slots.json", self._shared_spares(2))
            _write_json(root / "Structural" / "structural.json", [])

            store = LexiconStore(root)
            phrase_store = PhraseLexiconStore(root, store)
            phrase = phrase_store.assign_phrase(
                "newton laws of motion",
                phrase_type="concept",
                join_role_by_anchor={
                    "newton": "field_specifier",
                    "laws": "phrase_head",
                    "of": "director",
                    "motion": "field_object",
                },
            )
            memberships = phrase_store.phrase_memberships_for_anchor("laws")

            self.assertEqual(phrase["schema_version"], "anchorworks_phrase_lexicon@1")
            self.assertEqual(phrase["pack"], "phrase")
            self.assertEqual(phrase["status"], "ASSIGNED")
            self.assertEqual(phrase["symbol_schema_version"], "anchorworks_symbol_genome@1")
            self.assertEqual(phrase["symbol_category"], "specialized")
            self.assertEqual(phrase["symbol_priority"], 2)
            self.assertEqual(len(phrase["binary"]), 40)
            self.assertTrue(phrase["font_symbol"].startswith("CHAR_"))
            self.assertEqual(phrase["tone_label"], "")
            self.assertIsNone(phrase["tone_profile"])
            self.assertIn("#", phrase["visual_rune"])
            self.assertIn(".", phrase["visual_rune"])
            self.assertEqual(phrase["anchor_sequence"], ["newton", "laws", "of", "motion"])
            self.assertEqual(phrase["symbol_sequence"], ["0x0000000001", "0x0000000002", "0x0000000003", "0x0000000004"])
            self.assertEqual(memberships[0]["hex"], phrase["hex"])
            self.assertEqual(memberships[0]["role"], "phrase_head")
            laws_entry = store._find_entry("laws")[0]
            self.assertEqual(laws_entry["status"], "ASSIGNED")
            self.assertEqual(laws_entry["tone_signature"], "TONE_L")
            self.assertNotIn("phrase_refs", laws_entry)

    def test_phrase_authority_shapes_clearspeak_field_without_counting_phrase(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            for letter, entries in {
                "A": [{"word": "acceleration", "hex": "0x0000000005", "status": "ASSIGNED"}],
                "F": [{"word": "force", "hex": "0x0000000006", "status": "ASSIGNED"}],
                "L": [
                    {"word": "laws", "hex": "0x0000000002", "status": "ASSIGNED"},
                    {"word": "law", "hex": "0x0000000007", "status": "ASSIGNED"},
                ],
                "M": [
                    {"word": "motion", "hex": "0x0000000004", "status": "ASSIGNED"},
                    {"word": "mass", "hex": "0x0000000008", "status": "ASSIGNED"},
                ],
                "N": [{"word": "newton", "hex": "0x0000000001", "status": "ASSIGNED"}],
                "O": [
                    {"word": "of", "hex": "0x0000000003", "status": "ASSIGNED"},
                    {"word": "objects", "hex": "0x0000000009", "status": "ASSIGNED"},
                ],
            }.items():
                _write_json(root / "Canonical" / f"canonical_{letter}.json", entries)
            _write_json(root / "Spare_Slots" / "spare_slots.json", self._shared_spares(2))
            _write_json(root / "Structural" / "structural.json", [])
            store = LexiconStore(root)
            PhraseLexiconStore(root, store).assign_phrase(
                "newton laws of motion",
                phrase_type="concept",
                join_role_by_anchor={
                    "newton": "field_specifier",
                    "laws": "phrase_head",
                    "of": "director",
                    "motion": "field_object",
                },
            )
            _write_count_read_fixture(
                store,
                [
                    {"anchor": "laws", "offset": "+1", "neighbor": "energy", "observations": 80},
                    {"anchor": "motion", "offset": "+1", "neighbor": "energy", "observations": 80},
                    {"anchor": "newton", "offset": "+1", "neighbor": "law", "observations": 10},
                    {"anchor": "laws", "offset": "+2", "neighbor": "force", "observations": 8},
                    {"anchor": "motion", "offset": "+1", "neighbor": "objects", "observations": 8},
                    {"anchor": "force", "offset": "+1", "neighbor": "mass", "observations": 7},
                    {"anchor": "mass", "offset": "+1", "neighbor": "acceleration", "observations": 7},
                ],
                observed_counts=Counter({"newton": 1, "laws": 1, "motion": 1}),
            )

            result = ClearSpeakService(store).query("newton laws of motion", min_anchors=4, target_anchors=6, max_anchors=8)

            frame = result.answer_assembly["attention_frame"]
            self.assertEqual(frame["phrase_field"]["phrase"], "newton laws of motion")
            self.assertEqual(frame["phrase_field"]["phrase_type"], "concept")
            self.assertIn("field_specifier", frame["role_by_anchor"]["newton"])
            self.assertNotEqual(result.answer_assembly["terms"][0]["anchor"], "energy")
            self.assertEqual(result.answer_assembly["trace"][0]["candidate_preview"][0]["source_support"]["kind"], "lifetime_anchor_counts")

    def test_chat_documents_mode_uses_document_passages_and_line_citations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            for letter, words in {
                "E": ["emp"],
                "D": ["defense"],
                "R": ["requires"],
                "S": ["shielding"],
                "A": ["and"],
                "G": ["grounding"],
            }.items():
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [{"word": word, "status": "ASSIGNED"} for word in words])
            _write_json(root / "Spare_Slots" / "spare_slots.json", self._shared_spares(10))
            _write_json(root / "Structural" / "structural.json", [{"word": ".", "status": "STRUCTURAL"}])
            source_path = Path(temp_dir) / "emp_notes.txt"
            source_path.write_text(
                "title line\n\nEMP defense requires shielding and grounding.",
                encoding="utf-8",
            )

            store = LexiconStore(root)
            observed = store.build_observed_map(source_path)
            store.build_flat_runtime_from_observed_map(observed["saved_map_name"])
            chat = ChatMemorySystem(root, ClearSpeakService(store))
            result = chat.send("emp defense", mode="documents", branch="main")
            history = chat.history(branch="main")
            assistant = history["messages"][-1]

            self.assertEqual(result.mode, "documents")
            self.assertEqual(result.response, "EMP defense requires shielding and grounding.")
            self.assertIn("The source document supports", result.clearspeak["response"])
            self.assertIn("block 1, line 3", result.clearspeak["response"])
            self.assertEqual(result.clearspeak["answer_assembly"]["contract"]["flat_documents_gather_facts"], True)
            self.assertEqual(result.clearspeak["answer_assembly"]["contract"]["counts_assemble_final_path"], True)
            self.assertEqual(assistant["model_identity"]["evidence_mode"], "documents")
            self.assertEqual(assistant["model_identity"]["evidence_engine"], "document_answer_assembler")
            self.assertEqual(result.citations[0]["citation_type"], "source_locator")

    def test_chat_documents_mode_prefers_flat_runtime_and_renders_visual_refs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            for letter, words in {
                "E": ["emp"],
                "D": ["defense"],
                "R": ["requires"],
                "S": ["shielding"],
                "A": ["and"],
                "G": ["grounding"],
            }.items():
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [{"word": word, "status": "ASSIGNED"} for word in words])
            _write_json(root / "Spare_Slots" / "spare_slots.json", self._shared_spares(10))
            _write_json(root / "Structural" / "structural.json", [{"word": ".", "status": "STRUCTURAL"}])
            source_path = Path(temp_dir) / "emp_notes.txt"
            source_path.write_text(
                "title line\n\nEMP defense requires shielding and grounding.",
                encoding="utf-8",
            )

            store = LexiconStore(root)
            observed = store.build_observed_map(source_path)
            observed_path = Path(observed["saved_map_path"])
            payload = json.loads(observed_path.read_text(encoding="utf-8"))
            payload["paragraphs"][1]["visual_refs"] = [{"visual_record_id": "vis_emp_graph", "kind": "graph"}]
            observed_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            store.build_flat_runtime_from_observed_map(observed["saved_map_name"])
            observed_path.unlink()

            chat = ChatMemorySystem(root, ClearSpeakService(store))
            result = chat.send("emp defense", mode="documents", branch="main")

            self.assertEqual(result.response, "EMP defense requires shielding and grounding.")
            self.assertIn("block 1, line 3", result.clearspeak["response"])
            self.assertIn("figure vis_emp_graph", result.clearspeak["response"])
            self.assertEqual(result.clearspeak["answer_assembly"]["count_source"], "flat_fact_6_1_6_plus_local_overlay")
            self.assertEqual(result.evidence["runtime_source"], "flat_symbolic_documents")
            self.assertEqual(result.citations[0]["source"], "flat_symbolic_document")

    def test_chat_counts_mode_is_strict_counts_not_memory_stub(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            _write_json(root / "Canonical" / "canonical_S.json", [{"word": "stop", "status": "ASSIGNED"}])
            _write_json(root / "Canonical" / "canonical_N.json", [{"word": "not", "status": "ASSIGNED"}])
            _write_json(root / "Spare_Slots" / "spare_slots.json", self._shared_spares(10))
            _write_json(root / "Structural" / "structural.json", [])
            store = LexiconStore(root)
            _write_count_read_fixture(store, 
                [{"anchor": "stop", "offset": "-1", "neighbor": "not", "observations": 4}],
                observed_counts=Counter({"stop": 1, "not": 1}),
            )
            chat = ChatMemorySystem(root, ClearSpeakService(store))

            result = chat.send("stop", mode="counts", branch="main")
            assistant = chat.history(branch="main")["messages"][-1]

            self.assertEqual(result.mode, "counts")
            self.assertEqual(result.response, "The active path connects stop with not.")
            self.assertIn("stop: not (4)", result.clearspeak["response"])
            self.assertNotIn("Chat memory received", result.response)
            self.assertEqual(assistant["model_identity"]["evidence_mode"], "counts")

    def test_chat_send_returns_workbench_metadata_and_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            _write_json(root / "Canonical" / "canonical_S.json", [{"word": "stop", "status": "ASSIGNED"}])
            _write_json(root / "Canonical" / "canonical_N.json", [{"word": "not", "status": "ASSIGNED"}])
            _write_json(root / "Spare_Slots" / "spare_slots.json", self._shared_spares(10))
            _write_json(root / "Structural" / "structural.json", [])
            store = LexiconStore(root)
            _write_count_read_fixture(store, 
                [{"anchor": "stop", "offset": "-1", "neighbor": "not", "observations": 4}],
                observed_counts=Counter({"stop": 1, "not": 1}),
            )
            app = create_app(root)
            route = next(route for route in app.routes if getattr(route, "path", "") == "/api/chat/send")

            result = route.endpoint(ChatSendBody(
                message="stop",
                mode="counts",
                branch="main",
                evidence_visible=False,
            ))

            self.assertFalse(result["evidence_visible"])
            self.assertFalse(result["writes_performed"])
            self.assertEqual(result["workflow"]["step_id"], "answer_rendered")
            action_ids = {action["id"] for action in result["actions"]}
            self.assertIn("continue_working", action_ids)
            self.assertIn("show_evidence", action_ids)
            self.assertNotIn("hide_evidence", action_ids)
            assistant = result["assistant_message"]
            self.assertFalse(assistant["model_identity"]["evidence_visible"])
            self.assertEqual(assistant["workbench"]["workflow"]["workflow_id"], result["workflow"]["workflow_id"])

    def test_chat_send_treats_long_document_payload_as_intake_material_not_query(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            _write_json(root / "Canonical" / "canonical_H.json", [{"word": "here's", "status": "ASSIGNED"}])
            _write_json(root / "Canonical" / "canonical_D.json", [{"word": "deal", "status": "ASSIGNED"}])
            _write_json(root / "Canonical" / "canonical_E.json", [{"word": "energy", "status": "ASSIGNED"}])
            _write_json(root / "Spare_Slots" / "spare_slots.json", self._shared_spares(10))
            _write_json(root / "Structural" / "structural.json", [])
            store = LexiconStore(root)
            _write_count_read_fixture(
                store,
                [{"anchor": "here's", "offset": "+1", "neighbor": "energy", "observations": 99}],
                observed_counts=Counter({"here's": 1, "energy": 1}),
            )
            app = create_app(root)
            route = next(route for route in app.routes if getattr(route, "path", "") == "/api/chat/send")
            payload = (
                "Here's the deal. This is the story behind Lee and coding. "
                "We do not split words. We use anchors. "
                "No substitute lexicon. No fake lexicon. No hidden splitting. "
                "No grammar logic. No stop-word logic. No crossing paragraph blocks.\n\n"
                "```text\nanchors -> 6-1-6 windows -> counts -> context clouds\n```\n"
            ) * 8

            result = route.endpoint(ChatSendBody(message=payload, mode="clearspeak", branch="main"))

            self.assertEqual(result["mode"], "document_payload")
            self.assertIn("document-shaped payload", result["response"])
            self.assertNotIn("energy", result["response"])
            self.assertEqual(result["clearspeak"]["engine"], "chat_document_payload_guard")
            self.assertTrue(result["clearspeak"]["contract"]["clearspeak_count_walk_skipped"])

    def test_chat_stop_route_marks_response_interrupted_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(Path(temp_dir) / "Lexical Data")
            route = next(route for route in app.routes if getattr(route, "path", "") == "/api/chat/stop")

            result = route.endpoint({"workflow_id": "chat_123", "response_id": "resp_123"})

            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "interrupted")
            self.assertFalse(result["writes_performed"])

    def test_chat_action_route_executes_continue_without_chat_query(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(Path(temp_dir) / "Lexical Data")
            route = next(route for route in app.routes if getattr(route, "path", "") == "/api/chat/action")

            result = route.endpoint({
                "action_id": "continue_working",
                "workflow_id": "chat_123",
                "response_id": "resp_123",
                "payload": {},
            })

            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "awaiting_user_instruction")
            self.assertFalse(result["writes_performed"])
            self.assertFalse(result["chat_query_sent"])

    def test_chat_search_requires_all_terms_in_same_message_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            app = create_app(root)
            chats = root / "State" / "chat_memory" / "chats"
            chats.mkdir(parents=True, exist_ok=True)
            (chats / "2026-05-15.jsonl").write_text(
                "\n".join([
                    json.dumps({"id": 1, "sender": "assistant", "branch": "main", "content": "mothers children family", "message_uuid": "m1"}),
                    json.dumps({"id": 2, "sender": "assistant", "branch": "main", "content": "laws of physics motion", "message_uuid": "p1"}),
                ]) + "\n",
                encoding="utf-8",
            )
            route = next(route for route in app.routes if getattr(route, "path", "") == "/api/chat/search")

            strict = route.endpoint(query="mother physics law", branch="main")
            loose = route.endpoint(query="mother physics law", branch="main", match="any")

            self.assertEqual(strict["matches"], [])
            self.assertEqual(strict["law"], "Full-history search matches all requested terms in the same message by default; it does not merge unrelated rows.")
            self.assertEqual(len(loose["matches"]), 2)

    def test_chat_ui_exposes_workbench_controls(self) -> None:
        ui_root = _anchorworks_repo_root() / "UI"
        index_html = (ui_root / "index.html").read_text(encoding="utf-8")
        app_js = (ui_root / "assets" / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="chat-search-form"', index_html)
        self.assertIn('id="evidence-toggle"', index_html)
        self.assertIn('id="stop-response"', index_html)
        self.assertIn("Chat Workbench", index_html)
        self.assertIn("Evidence", index_html)
        self.assertIn("continue_working", app_js)
        self.assertIn("/api/chat/stop", app_js)
        self.assertIn("/api/chat/action", app_js)
        self.assertIn("/api/chat/search", app_js)
        self.assertNotIn('sendChat("Continue working.")', app_js)
        self.assertNotIn("/api/lexicon/symbolic-maps", app_js)
        self.assertNotIn("Symbolic Maps", index_html)

    def test_default_data_root_prefers_clean_runtime_from_repo(self) -> None:
        root = _default_data_root()
        self.assertEqual(root, Path("D:/AnchorWorks_Clean_Runtime"))

    def test_intake_edit_route_rewrites_anchor_spans_and_refreshes_preview(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            _write_json(root / "Canonical" / "canonical_S.json", [{"word": "stop", "status": "ASSIGNED"}])
            _write_json(root / "Canonical" / "canonical_N.json", [{"word": "not", "status": "ASSIGNED"}])
            _write_json(root / "Spare_Slots" / "spare_slots.json", self._shared_spares(10))
            _write_json(root / "Structural" / "structural.json", [{"word": ".", "status": "STRUCTURAL"}])
            app = create_app(root)
            route = next(route for route in app.routes if getattr(route, "path", "") == "/api/lexicon/intake/edit")

            result = route.endpoint(IntakeEditBody(
                source_name="sample.txt",
                content="do not stop.",
                edits=[{"original_anchor": "do", "replacement_anchor": "not", "action": "replace"}],
            ))

            self.assertTrue(result["ok"])
            self.assertEqual(result["content"], "not not stop.")
            self.assertEqual(result["edit_count"], 1)
            self.assertEqual(result["preview"]["missing_anchor_count"], 0)

    def test_ui_advertised_chat_routes_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(Path(temp_dir) / "Lexical Data")
            paths = {getattr(route, "path", "") for route in app.routes}
            for expected in {
                "/api/clearspeak/remix",
                "/api/clearspeak/cloud",
                "/api/lexicon/flat-documents",
                "/api/lexicon/flat-documents/anchorize",
                "/api/lexicon/flat-documents/anchorize-all",
                "/api/lexicon/intake/edit",
                "/api/visual-intake/files",
                "/api/visual-intake/packet/{name}",
                "/api/lexicon/symbolic-maps",
                "/api/lexicon/symbolic-map/{name}",
                "/api/binary-substrate/status",
                "/api/awsg/graphs",
                "/api/awsg/graph/{graph_name}",
                "/api/awsg/graph/{graph_name}/slice",
                "/api/flat-documents/runtime/build",
                "/api/lexicon/missing-anchor-review",
                "/api/lexicon/missing-anchor-review/sync",
                "/api/lexicon/missing-anchor-review/classify",
                "/api/chat/stop",
            }:
                self.assertIn(expected, paths)

    def test_external_api_chat_mode_logs_response_without_count_updates(self) -> None:
        class FakeModelApi:
            default_model = "qwen2.5b"

            def __init__(self) -> None:
                self.messages: list[dict[str, str]] = []

            def status(self) -> dict[str, object]:
                return {
                    "ok": True,
                    "configured": True,
                    "base_url": "http://example.invalid/v1",
                    "default_model": self.default_model,
                    "endpoint": "http://example.invalid/v1/chat/completions",
                }

            def chat(self, messages: list[dict[str, str]], *, model: str | None = None) -> dict[str, object]:
                self.messages = messages
                return {
                    "response": "Qwen lane answered from the external API.",
                    "provider": "external_api",
                    "model": model or self.default_model,
                    "requested_model": model or self.default_model,
                    "endpoint": "http://example.invalid/v1/chat/completions",
                    "response_id": "fake-response",
                    "finish_reason": "stop",
                }

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            app = create_app(root)
            fake = FakeModelApi()
            app.state.chat_memory.model_api = fake
            store = app.state.store
            before_base = store._read_json(store.lifetime_counts_path, {})
            before_user = store._read_json(store.user_counts_path, {})
            before_chat = store._read_json(store.chat_counts_path, {})

            route = next(route for route in app.routes if getattr(route, "path", "") == "/api/chat/send")
            result = route.endpoint(ChatSendBody(message="hello qwen", mode="api", branch="main", model="qwen2.5b"))
            history = app.state.chat_memory.history(branch="main")

            self.assertTrue(result["ok"])
            self.assertEqual(result["mode"], "api")
            self.assertEqual(result["model_api"]["model"], "qwen2.5b")
            self.assertEqual(history["messages"][-1]["content"], "Qwen lane answered from the external API.")
            self.assertEqual(history["messages"][-1]["model_identity"]["provider"], "external_api")
            self.assertTrue(any(row["content"] == "hello qwen" for row in fake.messages))
            self.assertEqual(store._read_json(store.lifetime_counts_path, {}), before_base)
            self.assertEqual(store._read_json(store.user_counts_path, {}), before_user)
            self.assertEqual(store._read_json(store.chat_counts_path, {}), before_chat)

    def test_live_chat_does_not_update_counts_until_finalize(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            _write_json(root / "Spare_Slots" / "spare_slots.json", self._shared_spares(200))
            _write_json(root / "Structural" / "structural.json", [])

            store = LexiconStore(root)
            chat = ChatMemorySystem(root, ClearSpeakService(store))
            before_lifetime = store._read_json(store.lifetime_counts_path, {})
            before_user_counts = store._read_json(store.user_counts_path, {})
            before_chat_counts = store._read_json(store.chat_counts_path, {})

            chat.send("alpha beta", mode="memory", branch="main")

            self.assertEqual(store._read_json(store.lifetime_counts_path, {}), before_lifetime)
            self.assertEqual(store._read_json(store.user_counts_path, {}), before_user_counts)
            self.assertEqual(store._read_json(store.chat_counts_path, {}), before_chat_counts)
            self.assertEqual(chat.status()["chat_messages"], 2)

            preview = chat.preview_finalize(branch="main")
            self.assertGreater(preview["missing_anchor_count"], 0)
            anchors = [row["anchor"] for row in preview["missing_anchors"]]
            frequencies = {row["anchor"]: int(row["observations"]) for row in preview["missing_anchors"]}
            approved = store.approve_intake_anchors(anchors, frequencies=frequencies)
            self.assertEqual(approved["failed_count"], 0)

            final = chat.finalize_day(branch="main")
            lifetime = store._read_json(store.lifetime_counts_path, {})
            user_counts = store._read_json(store.user_counts_path, {})
            chat_counts = store._read_json(store.chat_counts_path, {})

            self.assertTrue(final["ok"])
            self.assertEqual(final["count_target"], "user_chat_preview")
            self.assertEqual(lifetime, before_lifetime)
            self.assertEqual(user_counts, before_user_counts)
            self.assertEqual(chat_counts, before_chat_counts)
            self.assertTrue(final["count_write"]["legacy_json_counts_removed"])
            self.assertTrue(final["count_write"]["binary_counts_required"])
            self.assertEqual(final["chat_message_count"], 2)

    def test_chat_archive_import_stores_bridge_file_without_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            _write_json(root / "Spare_Slots" / "spare_slots.json", self._shared_spares(10))
            _write_json(root / "Structural" / "structural.json", [])

            archive = Path(temp_dir) / "OldAnchorWorks" / "data" / "chats"
            archive.mkdir(parents=True)
            (archive / "2026-05-01.jsonl").write_text(
                json.dumps({"id": 1, "sender": "user", "content": "archive bridge"}) + "\n",
                encoding="utf-8",
            )

            store = LexiconStore(root)
            before_lifetime = store._read_json(store.lifetime_counts_path, {})
            chat = ChatMemorySystem(root, ClearSpeakService(store))
            imported = chat.import_archive(Path(temp_dir) / "OldAnchorWorks")
            status = chat.status()

            self.assertTrue(imported["ok"])
            self.assertTrue(Path(imported["prepared_path"]).exists())
            self.assertEqual(status["imports"], 1)
            self.assertEqual(status["chat_messages"], 1)
            self.assertEqual(store._read_json(store.lifetime_counts_path, {}), before_lifetime)

    def test_store_persists_and_reloads_observed_map(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            _write_json(root / "Canonical" / "canonical_D.json", [{"word": "do", "status": "ASSIGNED"}])
            _write_json(root / "Canonical" / "canonical_E.json", [{"word": "__EMOJI__", "status": "ASSIGNED"}])
            _write_json(root / "Canonical" / "canonical_B.json", [{"word": "because", "status": "ASSIGNED"}])
            _write_json(root / "Canonical" / "canonical_N.json", [{"word": "not", "status": "ASSIGNED"}])
            _write_json(root / "Canonical" / "canonical_S.json", [{"word": "stop", "status": "ASSIGNED"}, {"word": "stop.", "status": "ASSIGNED"}])
            for letter in "ACFGHIJKLMOPQRTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            canonical_d = json.loads((root / "Canonical" / "canonical_D.json").read_text(encoding="utf-8"))
            canonical_d.append({"word": "don't", "status": "ASSIGNED"})
            _write_json(root / "Canonical" / "canonical_D.json", canonical_d)
            _write_json(root / "Spare_Slots" / "spare_slots.json", self._shared_spares(2))
            punctuation = [{"word": mark, "status": "STRUCTURAL"} for mark in [".", ",", "?", "!", "'", "\"", "-", ":", ";", "(", ")"]]
            _write_json(root / "Structural" / "structural.json", punctuation)

            source_path = Path(temp_dir) / "sample.txt"
            source_path.write_text("don't stop. do not stop " + chr(0x1F60A), encoding="utf-8")

            store = LexiconStore(root)
            result = store.build_observed_map(source_path)
            reloaded = store.load_observed_map(result["saved_map_name"])

            self.assertEqual(result["total_anchor_observations"], 7)
            self.assertEqual(result["unique_anchor_count"], 6)
            self.assertEqual(result["known_anchor_count"], 6)
            self.assertEqual(result["missing_anchor_count"], 0)
            self.assertEqual(reloaded["saved_map_name"], result["saved_map_name"])
            self.assertEqual(reloaded["occurrence_preview"][0]["anchor"], "don't")
            self.assertEqual(reloaded["missing_anchors_preview"], [])
            review = store.load_misspelled_review(result["misspelled_review_name"])
            self.assertEqual(review["review_count"], 0)
            retrieved = store.retrieve_from_counts("stop")
            context = store.context_map("stop")
            self.assertEqual(retrieved["maps_with_anchor"], 0)
            self.assertEqual(retrieved["total_neighbor_observations"], 0)
            self.assertEqual(context["total_windows"], 0)
            self.assertEqual(context["center_observations"], 0)

    def test_observed_maps_feed_binary_symbol_counts_without_legacy_lifetime_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            _write_json(root / "Canonical" / "canonical_D.json", [{"word": "do", "status": "ASSIGNED"}])
            _write_json(root / "Canonical" / "canonical_E.json", [{"word": "__EMOJI__", "status": "ASSIGNED"}])
            _write_json(root / "Canonical" / "canonical_N.json", [{"word": "not", "status": "ASSIGNED"}])
            _write_json(root / "Canonical" / "canonical_S.json", [{"word": "stop", "status": "ASSIGNED"}, {"word": "stop.", "status": "ASSIGNED"}])
            for letter in "ABCFGHIJKLMOPQRTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            canonical_d = json.loads((root / "Canonical" / "canonical_D.json").read_text(encoding="utf-8"))
            canonical_d.append({"word": "don't", "status": "ASSIGNED"})
            _write_json(root / "Canonical" / "canonical_D.json", canonical_d)
            _write_json(root / "Spare_Slots" / "spare_slots.json", self._shared_spares(2))
            punctuation = [{"word": mark, "status": "STRUCTURAL"} for mark in [".", ",", "?", "!", "'", "\"", "-", ":", ";", "(", ")"]]
            _write_json(root / "Structural" / "structural.json", punctuation)

            source_path = Path(temp_dir) / "sample.txt"
            source_path.write_text("don't stop. do not stop " + chr(0x1F60A), encoding="utf-8")

            store = LexiconStore(root)
            first_result = store.build_observed_map(source_path)

            self.assertFalse(store.lifetime_counts_path.exists())
            symbol_artifact = store.build_source_local_symbol_counts(first_result["saved_map_name"])
            binary = store.build_binary_symbol_counts_from_source_local(generation=5)

            self.assertTrue(symbol_artifact["ok"])
            self.assertTrue(binary["ok"])
            self.assertGreater(binary["stream_record_count"], 0)
            self.assertGreater(binary["verify"]["checked"], 0)

            Path(first_result["saved_map_path"]).unlink()
            retrieved_after_delete = store.retrieve_from_counts("stop")
            context_after_delete = store.context_map("stop")
            self.assertEqual(retrieved_after_delete["maps_scanned"], 0)
            self.assertEqual(retrieved_after_delete["maps_with_anchor"], 0)
            self.assertEqual(context_after_delete["total_windows"], 0)

    def test_awsm_block_line_locator_sidecar_survives_without_json_observed_map(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            _write_json(root / "Canonical" / "canonical_A.json", [{"word": "alpha", "status": "ASSIGNED"}])
            _write_json(root / "Canonical" / "canonical_B.json", [{"word": "beta", "status": "ASSIGNED"}])
            for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            _write_json(root / "Spare_Slots" / "spare_slots.json", [])

            source_path = Path(temp_dir) / "sample.txt"
            source_path.write_text("alpha beta\n\nbeta", encoding="utf-8")
            store = LexiconStore(root)

            result = store.build_observed_map(source_path)
            Path(result["saved_map_path"]).unlink()
            locator_rows = read_symbolic_map_locator_sidecar(result["symbolic_locator_path"])

            self.assertEqual(result["symbolic_locator_count"], 2)
            self.assertEqual(locator_rows[0]["paragraph_id"], 0)
            self.assertEqual(locator_rows[0]["block_id"], 0)
            self.assertEqual(locator_rows[0]["line_start"], 1)
            self.assertEqual(locator_rows[0]["line_end"], 1)
            self.assertEqual(locator_rows[0]["anchor_count"], 2)
            self.assertEqual(locator_rows[1]["paragraph_id"], 1)
            self.assertEqual(locator_rows[1]["block_id"], 1)
            self.assertEqual(locator_rows[1]["line_start"], 3)

    def test_awsm_null_coordinate_sidecar_survives_without_json_observed_map(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            _write_json(root / "Canonical" / "canonical_A.json", [{"word": "alpha", "status": "ASSIGNED"}])
            for letter in "BCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            _write_json(root / "Spare_Slots" / "spare_slots.json", [])

            source_path = Path(temp_dir) / "sample.txt"
            source_path.write_text("alpha junk\n\nalpha", encoding="utf-8")
            store = LexiconStore(root)

            result = store.build_observed_map(source_path, null_anchors={"junk"})
            Path(result["saved_map_path"]).unlink()
            null_rows = read_symbolic_map_null_sidecar(result["symbolic_null_path"])

            self.assertEqual(result["symbolic_null_count"], 1)
            self.assertEqual(null_rows[0]["block_id"], 0)
            self.assertEqual(null_rows[0]["line_start"], 1)
            self.assertEqual(null_rows[0]["anchor_position"], 1)
            self.assertEqual(null_rows[0]["anchor_label"], "Block 0 Ln 1 Anchor 1")
            self.assertEqual(null_rows[0]["observed_anchor"], "junk")
            self.assertEqual(null_rows[0]["resolved_anchor"], "__NULL__")
            self.assertFalse(null_rows[0]["count_eligible"])
            self.assertFalse(null_rows[0]["memory_truth"])

    def test_awsm_visual_ref_sidecar_survives_without_json_observed_map(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            _write_json(root / "Canonical" / "canonical_F.json", [{"word": "figure", "status": "ASSIGNED"}])
            _write_json(root / "Spare_Slots" / "spare_slots.json", [])

            source_path = Path(temp_dir) / "sample.html"
            source_path.write_text(
                "<html><body><p>Figure</p><img src=\"figures/emp_graph.png\" alt=\"EMP graph\" title=\"EMP figure\"></body></html>",
                encoding="utf-8",
            )
            store = LexiconStore(root)

            result = store.build_observed_map(source_path)
            Path(result["saved_map_path"]).unlink()
            visual_rows = read_symbolic_map_visual_sidecar(result["symbolic_visual_path"])

            self.assertEqual(result["symbolic_visual_count"], 1)
            self.assertEqual(visual_rows[0]["kind"], "image_reference")
            self.assertEqual(visual_rows[0]["source_path_ref"], "figures/emp_graph.png")
            self.assertEqual(visual_rows[0]["alt_text"], "EMP graph")
            self.assertEqual(visual_rows[0]["title"], "EMP figure")
            self.assertEqual(visual_rows[0]["recognition_status"], "not_run")
            self.assertEqual(visual_rows[0]["writes_allowed"], {"maps": False, "counts": False, "lifetime": False, "lexicon": False})

    def test_store_loads_binary_symbolic_map_bundle_by_observed_map_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            _write_json(root / "Canonical" / "canonical_A.json", [{"word": "alpha", "status": "ASSIGNED"}])
            for letter in "BCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            _write_json(root / "Spare_Slots" / "spare_slots.json", [])

            source_path = Path(temp_dir) / "sample.html"
            source_path.write_text("<p>alpha junk</p><img src=\"fig.png\" alt=\"Figure\">", encoding="utf-8")
            store = LexiconStore(root)

            result = store.build_observed_map(source_path, null_anchors={"junk"})
            Path(result["saved_map_path"]).unlink()
            bundle = store.load_symbolic_map_bundle(result["saved_map_name"])

            self.assertEqual(bundle["ok"], True)
            self.assertEqual(bundle["source_format"], "awsm_bundle")
            self.assertEqual(bundle["relation_count"], result["symbolic_map_relation_count"])
            self.assertEqual(bundle["locator_count"], result["symbolic_locator_count"])
            self.assertEqual(bundle["null_count"], result["symbolic_null_count"])
            self.assertEqual(bundle["visual_count"], result["symbolic_visual_count"])
            self.assertTrue(any(row["observed_anchor"] == "junk" for row in bundle["nulls"]))
            self.assertEqual(bundle["visuals"][0]["source_path_ref"], "fig.png")
            self.assertEqual(bundle["writes_allowed"], {"maps": False, "counts": False, "lifetime": False, "lexicon": False})

    def test_store_lists_symbolic_maps_as_primary_runtime_surface(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            _write_json(root / "Canonical" / "canonical_A.json", [{"word": "alpha", "status": "ASSIGNED"}])
            _write_json(root / "Canonical" / "canonical_B.json", [{"word": "beta", "status": "ASSIGNED"}])
            for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            _write_json(root / "Spare_Slots" / "spare_slots.json", [])

            source_path = Path(temp_dir) / "sample.html"
            source_path.write_text("<p>alpha beta junk</p><img src=\"fig.png\" alt=\"Figure\">", encoding="utf-8")
            store = LexiconStore(root)

            result = store.build_observed_map(source_path, null_anchors={"junk"})
            listing = store.symbolic_map_files()

            self.assertEqual(listing["source_format"], "awsm_bundle")
            self.assertEqual(listing["json_role"], "witness_debug_only")
            self.assertEqual(listing["map_count"], 1)
            self.assertEqual(listing["locator_sidecar_count"], 1)
            self.assertEqual(listing["null_sidecar_count"], 1)
            self.assertEqual(listing["visual_sidecar_count"], 1)
            self.assertEqual(listing["files"][0]["name"], result["symbolic_map_name"])
            self.assertEqual(listing["files"][0]["sidecars"], {"locators": True, "nulls": True, "visuals": True})

    def test_app_exposes_symbolic_map_bundle_routes_for_ui(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            _write_json(root / "Canonical" / "canonical_A.json", [{"word": "alpha", "status": "ASSIGNED"}])
            _write_json(root / "Canonical" / "canonical_B.json", [{"word": "beta", "status": "ASSIGNED"}])
            for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            _write_json(root / "Spare_Slots" / "spare_slots.json", [])

            source_path = Path(temp_dir) / "sample.txt"
            source_path.write_text("alpha beta", encoding="utf-8")
            store = LexiconStore(root)
            result = store.build_observed_map(source_path)

            app = create_app(root)
            paths = {getattr(route, "path", ""): getattr(route, "endpoint", None) for route in app.routes}

            listing = paths["/api/lexicon/symbolic-maps"]()
            bundle = paths["/api/lexicon/symbolic-map/{name}"](result["saved_map_name"])

            self.assertEqual(listing["map_count"], 1)
            self.assertEqual(listing["files"][0]["name"], result["symbolic_map_name"])
            self.assertEqual(bundle["source_format"], "awsm_bundle")
            self.assertEqual(bundle["symbolic_map_name"], result["symbolic_map_name"])

    def test_ingest_decomposes_unresolved_strings_before_temp_symbols(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            _write_json(
                root / "Canonical" / "canonical_D.json",
                [{"word": "do", "status": "ASSIGNED"}],
            )
            _write_json(
                root / "Canonical" / "canonical_E.json",
                [{"word": "e", "status": "ASSIGNED"}],
            )
            _write_json(
                root / "Canonical" / "canonical_M.json",
                [{"word": "m", "status": "ASSIGNED"}],
            )
            _write_json(
                root / "Canonical" / "canonical_R.json",
                [{"word": "r", "status": "ASSIGNED"}],
            )
            _write_json(
                root / "Canonical" / "canonical_S.json",
                [{"word": "s", "status": "ASSIGNED"}],
            )
            _write_json(
                root / "Canonical" / "canonical_T.json",
                [{"word": "t", "status": "ASSIGNED"}],
            )
            _write_json(
                root / "Canonical" / "canonical_Y.json",
                [{"word": "y", "status": "ASSIGNED"}],
            )
            for letter in "ABCEFGHIJKLMOPQRSTUVWXYZ":
                path = root / "Canonical" / f"canonical_{letter}.json"
                if not path.exists():
                    _write_json(path, [])
            _write_json(root / "Spare_Slots" / "spare_slots.json", [])
            _write_json(root / "Structural" / "structural.json", [{"word": ".", "status": "STRUCTURAL"}])

            source_path = Path(temp_dir) / "sample.txt"
            source_path.write_text("do mystery.", encoding="utf-8")

            store = LexiconStore(root)
            before_payload = store._read_json(store.lifetime_counts_path, {})

            result = store.build_observed_map(source_path)
            after_payload = store._read_json(store.lifetime_counts_path, {})

            self.assertEqual(before_payload, after_payload)
            self.assertTrue(Path(result["saved_map_path"]).is_file())
            self.assertEqual(result["missing_anchor_count"], 1)
            self.assertEqual(result["character_decomposed_anchor_count"], 1)
            self.assertEqual(result["character_decomposed_anchors"][0]["anchor"], "mystery")
            self.assertEqual(result["temp_symbol_count"], 0)
            self.assertEqual(result["temp_lexicon_path"], "")
            self.assertEqual(result["count_write"]["lifetime_write_skipped"], True)
            self.assertEqual(result["count_paths"], [])
            reviews = store.misspelled_review_files()["files"]
            self.assertEqual(len(reviews), 1)
            review = store.load_misspelled_review(reviews[0]["name"])
            self.assertEqual(review["review_count"], 1)
            self.assertEqual(review["rows_preview"][0]["anchor"], "mystery")
            self.assertEqual(review["rows_preview"][0]["ingest_action"], "character_decomposed")
            self.assertEqual(review["rows_preview"][0]["resolved_to"], list("mystery"))
            map_payload = json.loads(Path(result["saved_map_path"]).read_text(encoding="utf-8"))
            self.assertEqual(map_payload["temp_symbol_count"], 0)
            paragraph = map_payload["paragraphs"][0]
            self.assertEqual(paragraph["anchors"], ["do", "m", "y", "s", "t", "e", "r", "y", "."])
            self.assertEqual(paragraph["composed_anchor_stream"], ["do", "m", "y", "s", "t", "e", "r", "y", "."])

    def test_structural_companion_anchors_do_not_block_canonical_lifetime_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            _write_json(root / "Canonical" / "canonical_D.json", [{"word": "do", "status": "ASSIGNED"}])
            for letter in "ABCEFGHIJKLMOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            _write_json(root / "Spare_Slots" / "spare_slots.json", [])
            _write_json(root / "Structural" / "structural.json", [{"word": ".", "status": "STRUCTURAL"}])

            source_path = Path(temp_dir) / "sample.txt"
            source_path.write_text("do mrow do.", encoding="utf-8")

            store = LexiconStore(root)
            result = store.build_observed_map(source_path)
            self.assertEqual(result["missing_anchor_count"], 0)
            self.assertEqual(result["temp_symbol_count"], 0)
            self.assertEqual(result["companion_anchor_count"], 1)
            self.assertEqual(result["count_write"]["lifetime_write_skipped"], True)
            self.assertTrue(result["count_write"]["legacy_json_counts_removed"])
            self.assertEqual(result["count_paths"], [])
            self.assertFalse(store.lifetime_counts_path.exists())

    def test_decomposed_unknown_strings_do_not_seed_missing_anchor_registry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            _write_json(root / "Canonical" / "canonical_D.json", [{"word": "do", "status": "ASSIGNED"}])
            for letter in "ABCEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            _write_json(root / "Spare_Slots" / "spare_slots.json", self._shared_spares(5))
            _write_json(root / "Structural" / "structural.json", [{"word": ".", "status": "STRUCTURAL"}])

            source_path = Path(temp_dir) / "sample.txt"
            source_path.write_text("do mystery mystery.", encoding="utf-8")

            store = LexiconStore(root)
            before_lifetime = store._read_json(store.lifetime_counts_path, {})
            result = store.build_observed_map(source_path)

            review = store.missing_anchor_review_queue(limit=5)
            self.assertEqual(review["total_registry_anchors"], 0)
            self.assertEqual(review["entries"], [])

            sync = store.sync_missing_anchor_review_queue(limit=5)
            after_lifetime = store._read_json(store.lifetime_counts_path, {})

            self.assertEqual(before_lifetime, after_lifetime)
            self.assertEqual(sync["moved_to_unmatched"], 0)
            self.assertEqual(sync["entries"], [])
            self.assertEqual(store.unmatched(limit=5)["entries"], [])
            self.assertEqual(result["character_decomposed_anchor_count"], 1)
            self.assertEqual(result["count_write"]["lifetime_write_skipped"], True)

    def test_missing_anchor_registry_classification_splits_markup_from_words_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            _write_json(root / "Spare_Slots" / "spare_slots.json", self._shared_spares(5))
            _write_json(root / "State" / "missing_anchor_registry.json", [
                {"anchor": "mrow", "observations": 8},
                {"anchor": "stretchy", "observations": 6},
                {"anchor": "enumerated", "observations": 4},
                {"anchor": "π", "observations": 3},
                {"anchor": "cnxml", "observations": 2},
                {"anchor": "ch01mod02_review_questions_problem_01", "observations": 1},
            ])
            before_spares = (root / "Spare_Slots" / "spare_slots.json").read_text(encoding="utf-8")

            store = LexiconStore(root)
            result = store.classify_missing_anchor_registry()

            self.assertEqual(result["total_unique"], 6)
            self.assertEqual(result["lane_counts"]["math_markup"], 2)
            self.assertEqual(result["lane_counts"]["unknown_real_word_candidates"], 1)
            self.assertEqual(result["lane_counts"]["math_terms_or_symbols"], 1)
            self.assertEqual(result["lane_counts"]["structural_source_anchors"], 1)
            self.assertEqual(result["lane_counts"]["source_id_artifacts"], 1)
            self.assertEqual(result["writes_allowed"], {"maps": False, "counts": False, "lifetime": False, "lexicon": False})
            self.assertEqual((root / "Spare_Slots" / "spare_slots.json").read_text(encoding="utf-8"), before_spares)
            self.assertTrue(Path(result["summary_path"]).exists())

    def test_known_anchor_index_reads_non_ascii_canonical_letter_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            _write_json(root / "Canonical" / "canonical_A.json", [{"word": "anchor", "status": "ASSIGNED"}])
            _write_json(root / "Canonical" / "canonical_Ç.json", [{"word": "çatalhöyük", "status": "ASSIGNED"}])
            _write_json(root / "Spare_Slots" / "spare_slots.json", self._shared_spares(1))

            store = LexiconStore(root)

            self.assertIn("anchor", store._all_known_anchors())
            self.assertIn("çatalhöyük", store._all_known_anchors())

    def test_document_intake_preview_and_manual_approval_do_not_map_or_count(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            _write_json(root / "Canonical" / "canonical_D.json", [{"word": "do", "status": "ASSIGNED"}])
            for letter in "ABCEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            _write_json(root / "Spare_Slots" / "spare_slots.json", self._shared_spares(3))
            _write_json(root / "Structural" / "structural.json", [])

            store = LexiconStore(root)
            before_lifetime = store._read_json(store.lifetime_counts_path, {})
            preview = store.preview_document_intake(
                source_name="sample.txt",
                content="do newword",
                file_size=10,
                file_type="text/plain",
            )

            self.assertEqual(preview["total_anchor_observations"], 2)
            self.assertEqual(preview["unique_anchor_count"], 2)
            self.assertEqual(preview["known_anchor_count"], 1)
            self.assertEqual(preview["missing_anchor_count"], 1)
            self.assertEqual(preview["missing_anchors"][0]["anchor"], "newword")
            self.assertEqual(store.observed_map_files()["files"], [])
            self.assertEqual(store._read_json(store.lifetime_counts_path, {}), before_lifetime)

            approved = store.approve_intake_anchors(["newword", "Another", "do", "newword"], frequencies={"newword": 1, "Another": 2})
            after = store.preview_document_intake(source_name="sample.txt", content="do newword Another")
            spare_after = json.loads((root / "Spare_Slots" / "spare_slots.json").read_text(encoding="utf-8"))
            canonical_a = json.loads((root / "Canonical" / "canonical_A.json").read_text(encoding="utf-8"))
            canonical_n = json.loads((root / "Canonical" / "canonical_N.json").read_text(encoding="utf-8"))

            self.assertEqual(approved["approved_count"], 2)
            self.assertEqual(approved["skipped_count"], 1)
            self.assertEqual(approved["slots_available"], 1)
            self.assertEqual(len(spare_after), 1)
            self.assertTrue(any(row["word"] == "another" for row in canonical_a))
            self.assertTrue(any(row["word"] == "newword" for row in canonical_n))
            self.assertEqual(after["missing_anchor_count"], 0)
            self.assertEqual(store.observed_map_files()["files"], [])
            self.assertEqual(store._read_json(store.lifetime_counts_path, {}), before_lifetime)

    def test_intake_null_edits_map_strays_to_null_without_memory_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            _write_json(root / "Canonical" / "canonical_A.json", [{"word": "alpha", "status": "ASSIGNED"}])
            _write_json(root / "Canonical" / "canonical_B.json", [{"word": "beta", "status": "ASSIGNED"}])
            for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            _write_json(root / "Spare_Slots" / "spare_slots.json", self._shared_spares(3))
            _write_json(root / "Structural" / "structural.json", [])

            store = LexiconStore(root)
            result = store.build_intake_mapping(
                source_name="sample.txt",
                content="alpha junk beta",
                intake_edits=[{"original_anchor": "junk", "action": "null"}],
            )

            self.assertEqual(result["missing_anchor_count"], 0)
            self.assertEqual(result["null_anchor_count"], 1)
            self.assertEqual(result["null_occurrence_count"], 1)
            self.assertEqual(result["null_anchors"], [{"anchor": "junk", "observations": 1}])
            self.assertEqual(result["null_index_preview"][0]["anchor_label"], "Block 0 Ln 1 Anchor 1")
            self.assertEqual(result["null_index_preview"][0]["observed_anchor"], "junk")
            self.assertFalse(result["null_index_preview"][0]["memory_truth"])
            payload = json.loads(Path(result["saved_map_path"]).read_text(encoding="utf-8"))
            self.assertEqual(payload["null_index"][0]["anchor_label"], "Block 0 Ln 1 Anchor 1")
            occurrence = next(row for row in payload["occurrences"] if row["observed_anchor"] == "junk")
            self.assertEqual(occurrence["anchor"], NULL_ANCHOR)
            self.assertFalse(occurrence["count_eligible"])
            self.assertFalse(any(row["anchor"] == NULL_ANCHOR or row["neighbor"] == NULL_ANCHOR for row in payload["co_occurrence_counts"]))

    def test_intake_companion_lane_anchors_are_covered_without_canonical_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            _write_json(root / "Canonical" / "canonical_A.json", [{"word": "alpha", "status": "ASSIGNED"}])
            for letter in "BCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            _write_json(root / "Spare_Slots" / "spare_slots.json", self._shared_spares(3))
            _write_json(root / "Structural" / "structural.json", [])

            store = LexiconStore(root)
            result = store.build_intake_mapping(source_name="sample.txt", content="alpha –")

            self.assertEqual(result["raw_missing_anchor_count"], 1)
            self.assertEqual(result["missing_anchor_count"], 0)
            self.assertEqual(result["companion_anchor_count"], 1)
            self.assertTrue(result["count_write"]["lifetime_write_skipped"])
            self.assertTrue(result["count_write"]["binary_counts_required"])

    def test_batch_approval_adds_500_anchors_with_one_spare_write_and_one_index_reload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            _write_json(root / "Spare_Slots" / "spare_slots.json", self._shared_spares(600))
            _write_json(root / "Structural" / "structural.json", [])

            store = LexiconStore(root)
            store._all_known_anchors()
            before_lifetime = store._read_json(store.lifetime_counts_path, {})
            anchors = [
                f"batchword{chr(ord('A') + ((index // 26) % 26))}{chr(ord('A') + (index % 26))}"
                for index in range(500)
            ]
            frequencies = {anchor: index + 1 for index, anchor in enumerate(anchors)}

            spare_writes = 0
            index_reloads = 0
            canonical_writes = 0
            original_write_spares = store._write_spare_entries
            original_invalidate = store._invalidate_known_anchor_index
            original_write_entries = store._write_entries

            def counted_write_spares(entries: list[dict[str, object]]) -> None:
                nonlocal spare_writes
                spare_writes += 1
                original_write_spares(entries)

            def counted_invalidate() -> None:
                nonlocal index_reloads
                index_reloads += 1
                original_invalidate()

            def counted_write_entries(path: Path, entries: list[dict[str, object]]) -> None:
                nonlocal canonical_writes
                if path.parent == store.canonical_dir:
                    canonical_writes += 1
                original_write_entries(path, entries)

            store._write_spare_entries = counted_write_spares  # type: ignore[method-assign]
            store._invalidate_known_anchor_index = counted_invalidate  # type: ignore[method-assign]
            store._write_entries = counted_write_entries  # type: ignore[method-assign]

            result = store.approve_intake_anchors(anchors, frequencies=frequencies)
            spare_after = json.loads((root / "Spare_Slots" / "spare_slots.json").read_text(encoding="utf-8"))
            canonical_b = json.loads((root / "Canonical" / "canonical_B.json").read_text(encoding="utf-8"))
            coverage = store.preview_document_intake(source_name="batch.txt", content=" ".join(anchors))

            self.assertTrue(result["ok"])
            self.assertEqual(result["approved_count"], 500)
            self.assertEqual(result["slots_allocated"], 500)
            self.assertEqual(result["slots_available"], 100)
            self.assertEqual(result["lexicon_files_written"], 1)
            self.assertEqual(result["spare_pool_writes"], 1)
            self.assertEqual(result["index_reloads"], 1)
            self.assertEqual(spare_writes, 1)
            self.assertEqual(index_reloads, 1)
            self.assertEqual(canonical_writes, 1)
            self.assertEqual(len(spare_after), 100)
            self.assertEqual(len(canonical_b), 500)
            self.assertEqual(coverage["unique_anchor_count"], 500)
            self.assertEqual(coverage["known_anchor_count"], 500)
            self.assertEqual(coverage["missing_anchor_count"], 0)
            self.assertEqual(store.observed_map_files()["files"], [])
            self.assertEqual(store._read_json(store.lifetime_counts_path, {}), before_lifetime)

    def test_import_words_dir_uses_batch_assignment_and_preserves_frequencies(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            _write_json(root / "Spare_Slots" / "spare_slots.json", self._shared_spares(10))
            _write_json(root / "Structural" / "structural.json", [])
            import_dir = Path(temp_dir) / "verified_import"
            _write_json(import_dir / "verified_A.json", [
                {"word": "alpha", "frequency": 7},
                {"word": "atom", "observations": 5},
            ])
            _write_json(import_dir / "verified_B.json", ["beta"])

            store = LexiconStore(root)
            before_lifetime = store._read_json(store.lifetime_counts_path, {})
            spare_writes = 0
            original_write_spares = store._write_spare_entries

            def counted_write_spares(entries: list[dict[str, object]]) -> None:
                nonlocal spare_writes
                spare_writes += 1
                original_write_spares(entries)

            store._write_spare_entries = counted_write_spares  # type: ignore[method-assign]

            result = store.import_words_dir(import_dir)
            canonical_a = json.loads((root / "Canonical" / "canonical_A.json").read_text(encoding="utf-8"))
            canonical_b = json.loads((root / "Canonical" / "canonical_B.json").read_text(encoding="utf-8"))
            spare_after = json.loads((root / "Spare_Slots" / "spare_slots.json").read_text(encoding="utf-8"))

            self.assertEqual(result["imported"], 3)
            self.assertEqual(result["skipped"], 0)
            self.assertEqual(result["no_slots"], 0)
            self.assertEqual(result["slots_available"], 7)
            self.assertEqual(spare_writes, 1)
            self.assertEqual(len(spare_after), 7)
            self.assertEqual({row["word"] for row in canonical_a}, {"alpha", "atom"})
            self.assertEqual({row["word"] for row in canonical_b}, {"beta"})
            self.assertEqual({row["word"]: row["frequency"] for row in canonical_a}, {"alpha": 7, "atom": 5})
            self.assertEqual(store._read_json(store.lifetime_counts_path, {}), before_lifetime)

    def test_shared_spare_slots_file_supports_assignment_and_return(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            _write_json(
                root / "Spare_Slots" / "spare_slots.json",
                [
                    {"binary": "1010", "hex": "0xAAA", "font_symbol": "CHAR_A", "tone_signature": "TONE_A", "status": "AVAILABLE"},
                    {"binary": "2020", "hex": "0xBBB", "font_symbol": "CHAR_B", "tone_signature": "TONE_B", "status": "AVAILABLE"},
                ],
            )
            _write_json(root / "Structural" / "structural.json", [])

            store = LexiconStore(root)
            assigned = store._assign_word("umbrella", frequency=3)
            shared_spare = json.loads((root / "Spare_Slots" / "spare_slots.json").read_text(encoding="utf-8"))
            canonical_u = json.loads((root / "Canonical" / "canonical_U.json").read_text(encoding="utf-8"))
            files = store.files()["files"]

            self.assertEqual(assigned["word"], "umbrella")
            self.assertEqual(len(shared_spare), 1)
            self.assertEqual(store._count_available_slots(), 1)
            self.assertEqual(canonical_u[0]["word"], "umbrella")
            self.assertTrue(any(item["filename"] == "spare_slots.json" for item in files))

            returned = store.clear_canonical()
            shared_after_return = json.loads((root / "Spare_Slots" / "spare_slots.json").read_text(encoding="utf-8"))
            canonical_u_after = json.loads((root / "Canonical" / "canonical_U.json").read_text(encoding="utf-8"))

            self.assertEqual(returned["slots_reclaimed"], 1)
            self.assertEqual(len(shared_after_return), 2)
            self.assertEqual(canonical_u_after, [])

    def test_anchor_identity_always_lowercases_string_literals(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            _write_json(
                root / "Spare_Slots" / "spare_slots.json",
                [{"binary": "1010", "hex": "0xAAA", "font_symbol": "CHAR_A", "tone_signature": "TONE_A", "status": "AVAILABLE"}],
            )
            _write_json(root / "Structural" / "structural.json", [])

            store = LexiconStore(root)
            assigned = store._assign_word("NASA", frequency=7)

            self.assertEqual(assigned["word"], "nasa")
            self.assertIsNotNone(store.entry("NASA"))
            self.assertIsNotNone(store.entry("nasa"))

    def test_lowercase_string_literal_uses_normal_anchor_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            _write_json(root / "Spare_Slots" / "spare_slots.json", self._shared_spares(1))
            _write_json(root / "Structural" / "structural.json", [])

            store = LexiconStore(root)

            rows = store._build_misspelled_review_rows(Counter({"nasa": 3}), set())
            self.assertEqual(rows[0]["anchor"], "nasa")
            self.assertIsNone(rows[0]["suggested_existing"])

    def test_large_missing_set_skips_spell_suggestion_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            _write_json(root / "Spare_Slots" / "spare_slots.json", self._shared_spares(600))
            _write_json(root / "Structural" / "structural.json", [])

            store = LexiconStore(root)

            def fail(*_args, **_kwargs):
                raise AssertionError("spell suggestion should be skipped for large missing sets")

            store._suggest_existing_anchor = fail  # type: ignore[method-assign]
            missing: Counter[str] = Counter()
            for index in range(600):
                first = chr(ord("A") + (index // 26) % 26)
                second = chr(ord("a") + (index % 26))
                missing[f"Word{first}{second}"] = 1
            rows = store._build_misspelled_review_rows(missing, set())
            self.assertEqual(len(rows), 600)


if __name__ == "__main__":
    unittest.main()


