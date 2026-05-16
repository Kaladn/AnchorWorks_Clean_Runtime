from __future__ import annotations

import tempfile
import unittest
from collections import Counter
from pathlib import Path

from AnchorWorks.clearspeak import ClearSpeakService
from AnchorWorks.answer_surface import render_anchor_answer_surface
from AnchorWorks.chat_memory_system import ChatMemorySystem
from AnchorWorks.document_answer import _fact_candidates
from AnchorWorks.inference import build_answer_plan, run_inference
from AnchorWorks.store import LexiconStore
from aw_inference_kernel import run_inference as run_external_inference
from aw_inference_kernel import solve_formula_question


def _write_json(path: Path, payload: object) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


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


class InferenceKernelTests(unittest.TestCase):
    def test_inference_rejects_off_frame_candidate_before_answer_plan(self) -> None:
        assembly = {
            "terms": [
                {
                    "anchor": "mothers",
                    "answer_health": {"status": "supported"},
                    "query_field_coherence": {"coherent": False, "reason": "candidate_detached_from_query_field"},
                    "pattern_health": "anomalous",
                    "supporting_context": ["laws"],
                },
                {
                    "anchor": "motion",
                    "answer_health": {"status": "supported"},
                    "query_field_coherence": {"coherent": True},
                    "pattern_health": "healthy",
                    "supporting_context": ["laws", "physics"],
                },
            ],
            "trace": [],
        }

        plan = run_inference("Why worry about laws of physics?", ["why", "worry", "about", "laws", "of", "physics", "?"], assembly)

        self.assertEqual(plan["schema_version"], "aw_inference_answer_plan@1")
        self.assertEqual(plan["frame"]["frame_type"], "causal_explanation")
        self.assertEqual([row["symbol"] for row in plan["accepted_candidates"]], ["motion"])
        self.assertEqual(plan["rejected_candidates"][0]["symbol"], "mothers")
        self.assertEqual(plan["rejected_candidates"][0]["reason"], "query_field_mismatch")
        self.assertFalse(plan["fact_authority"])
        self.assertFalse(plan["fact_answer_authority"])
        self.assertEqual(plan["render_shape"], "short_explanation")

    def test_external_kernel_is_the_called_package(self) -> None:
        assembly = {
            "terms": [{
                "anchor": "motion",
                "answer_health": {"status": "supported"},
                "query_field_coherence": {"coherent": True},
                "supporting_context": ["laws", "physics"],
                "score": 0.7,
            }],
        }

        plan = run_external_inference("Why worry about laws of physics?", ["why", "laws", "physics"], assembly)

        self.assertEqual(plan["schema_version"], "aw_inference_answer_plan@1")
        self.assertEqual(plan["frame"]["schema_version"], "aw_inference_frame@1")
        self.assertFalse(plan["fact_authority"])
        self.assertTrue(plan["contract"]["no_raw_topk_fallback"])
        self.assertEqual(plan["accepted_candidates"][0]["symbol"], "motion")

    def test_inference_plan_records_cloud_scores_and_rejects_physics_domain_leakage(self) -> None:
        assembly = {
            "terms": [
                {
                    "anchor": "gnp",
                    "answer_health": {"status": "supported"},
                    "supporting_context": ["laws"],
                    "score_parts": {
                        "question_fit": 0.25,
                        "rear_fit": 0.0,
                        "answer_fit": 0.0,
                        "forward_fit": 0.0,
                        "source_support": 0.8,
                    },
                    "lookahead_score": 0.0,
                    "support_offsets": ["+1"],
                },
                {
                    "anchor": "force",
                    "answer_health": {"status": "supported"},
                    "supporting_context": ["laws", "physics"],
                    "score_parts": {
                        "question_fit": 0.75,
                        "rear_fit": 0.25,
                        "answer_fit": 0.0,
                        "forward_fit": 0.25,
                        "source_support": 0.9,
                    },
                    "lookahead_score": 0.4,
                    "support_offsets": ["+1", "+2"],
                },
            ],
            "trace": [],
        }

        plan = run_inference("Why worry about laws of physics?", ["why", "worry", "laws", "physics"], assembly, mode="counts")

        self.assertEqual([row["symbol"] for row in plan["accepted_candidates"]], ["force"])
        self.assertEqual(plan["rejected_candidates"][0]["symbol"], "gnp")
        self.assertEqual(plan["rejected_candidates"][0]["reason"], "off_frame_domain")
        admitted = plan["accepted_candidates"][0]
        self.assertIn("cloud_match", admitted)
        self.assertGreater(admitted["cloud_match"]["local_cloud_score"], 0)
        self.assertGreater(admitted["cloud_match"]["layered_cloud_score"], 0)
        self.assertGreater(admitted["cloud_match"]["directional_score"], 0)
        self.assertIn("support_metrics", plan)
        self.assertEqual(plan["support_metrics"]["admitted_count"], 1)
        self.assertIn("uncertainty_notes", plan)

    def test_newton_second_law_formula_question_solves_before_evidence_lane(self) -> None:
        result = solve_formula_question("A 2 kg object is accelerating at 3 m/s². What net force is acting on it?")

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["activity"], "formula_solve")
        self.assertEqual(result["formula"], "F = ma")
        self.assertEqual(result["result"]["display"], "6 N")
        self.assertIn("The net force is 6 N", result["speech"])
        self.assertFalse(result["inference_plan"]["fact_authority"])
        self.assertTrue(result["contract"]["formula_lane_before_evidence_lane"])
        self.assertFalse(result["contract"]["documents_used"])
        self.assertFalse(result["contract"]["counts_used"])

    def test_chat_counts_mode_routes_formula_before_counts_or_documents(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            store = LexiconStore(root)
            chat = ChatMemorySystem(Path(temp_dir), ClearSpeakService(store))

            result = chat.send("A 2 kg object is accelerating at 3 m/s². What net force is acting on it?", mode="counts")

            self.assertEqual(result.mode, "formula")
            self.assertEqual(result.clearspeak["engine"], "aw_inference_formula_solver")
            self.assertIn("6 N", result.response)
            self.assertFalse(result.clearspeak["contract"]["documents_used"])
            self.assertFalse(result.clearspeak["contract"]["counts_used"])

    def test_renderer_does_not_fallback_to_raw_topk_when_kernel_rejects_all(self) -> None:
        assembly = {
            "terms": [
                {"anchor": "mothers", "score": 0.9},
                {"anchor": "american", "score": 0.8},
            ],
            "inference_plan": {
                "accepted_candidates": [],
                "rejected_candidates": [
                    {"symbol": "mothers", "reason": "off_frame_domain"},
                    {"symbol": "american", "reason": "off_frame_domain"},
                ],
                "render_shape": "insufficient_support",
                "fact_authority": False,
            },
        }

        rendered = render_anchor_answer_surface(["why", "laws", "physics"], assembly)

        self.assertEqual(rendered, "")

    def test_clearspeak_response_uses_inference_plan_terms(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            for letter, words in {
                "A": ["about"],
                "L": ["laws"],
                "M": ["mothers", "motion"],
                "O": ["of"],
                "P": ["physics"],
                "W": ["why", "worry"],
            }.items():
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [{"word": word, "status": "ASSIGNED"} for word in words])
            _write_json(root / "Structural" / "structural.json", [{"word": "?", "status": "STRUCTURAL"}])
            store = LexiconStore(root)
            _write_count_read_fixture(
                store,
                [
                    {"anchor": "laws", "offset": "+1", "neighbor": "mothers", "observations": 12},
                    {"anchor": "physics", "offset": "+1", "neighbor": "motion", "observations": 8},
                    {"anchor": "motion", "offset": "+1", "neighbor": "force", "observations": 7},
                ],
                observed_counts=Counter({"laws": 1, "physics": 1, "mothers": 1, "motion": 1}),
            )

            result = ClearSpeakService(store).query("Why worry about laws of physics?")

            self.assertIn("inference_plan", result.answer_assembly)
            self.assertNotIn("mothers", result.speech)
            self.assertIn("motion", result.speech)

    def test_clearspeak_does_not_walk_counts_from_question_glue_when_subject_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            for letter, words in {
                "I": ["is"],
                "L": ["law", "laws"],
                "M": ["mass", "motion"],
                "Q": ["question"],
                "S": ["second"],
                "W": ["what"],
            }.items():
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [{"word": word, "status": "ASSIGNED"} for word in words])
            _write_json(root / "Structural" / "structural.json", [{"word": "?", "status": "STRUCTURAL"}])
            store = LexiconStore(root)
            _write_count_read_fixture(
                store,
                [
                    {"anchor": "what", "offset": "+1", "neighbor": "law", "observations": 9},
                    {"anchor": "is", "offset": "+1", "neighbor": "motion", "observations": 8},
                    {"anchor": "law", "offset": "+1", "neighbor": "second", "observations": 7},
                    {"anchor": "motion", "offset": "+1", "neighbor": "mass", "observations": 6},
                ],
                observed_counts=Counter({"what": 1, "is": 1, "law": 1, "motion": 1}),
            )

            result = ClearSpeakService(store).query("what is intertia?")

            self.assertIn("intertia", result.missing_anchors)
            self.assertEqual(result.answer_assembly["stop_reason"], "missing_content_anchor")
            self.assertEqual(result.answer_assembly["terms"], [])
            self.assertIn("intertia", result.speech)
            self.assertNotIn("law", result.speech)
            self.assertNotIn("motion", result.speech)

    def test_clearspeak_does_not_walk_partial_missing_who_entity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            for letter, words in {
                "A": ["answer"],
                "F": ["frame"],
                "I": ["is", "induction"],
                "N": ["newton", "not"],
                "Q": ["question"],
                "T": ["text"],
                "W": ["who"],
            }.items():
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [{"word": word, "status": "ASSIGNED"} for word in words])
            store = LexiconStore(root)
            _write_count_read_fixture(
                store,
                [
                    {"anchor": "newton", "offset": "+1", "neighbor": "text", "observations": 9},
                    {"anchor": "newton", "offset": "+2", "neighbor": "frame", "observations": 8},
                    {"anchor": "is", "offset": "+1", "neighbor": "answer", "observations": 7},
                ],
                observed_counts=Counter({"newton": 1, "is": 1}),
            )

            result = ClearSpeakService(store).query("who is issac newton")

            self.assertIn("issac", result.missing_anchors)
            self.assertEqual(result.answer_assembly["stop_reason"], "missing_content_anchor")
            self.assertEqual(result.answer_assembly["terms"], [])
            self.assertIn("issac", result.speech)
            self.assertNotIn("text", result.speech)
            self.assertNotIn("frame", result.speech)

    def test_clearspeak_who_question_renders_entity_count_field(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            for letter, words in {
                "I": ["isaac", "is"],
                "L": ["law", "laws"],
                "M": ["motion", "mass"],
                "N": ["newton"],
                "W": ["who"],
            }.items():
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [{"word": word, "status": "ASSIGNED"} for word in words])
            store = LexiconStore(root)
            _write_count_read_fixture(
                store,
                [
                    {"anchor": "isaac", "offset": "+1", "neighbor": "motion", "observations": 9},
                    {"anchor": "isaac", "offset": "+2", "neighbor": "law", "observations": 8},
                    {"anchor": "newton", "offset": "+1", "neighbor": "laws", "observations": 7},
                    {"anchor": "newton", "offset": "+2", "neighbor": "mass", "observations": 6},
                ],
                observed_counts=Counter({"isaac": 1, "newton": 1}),
            )

            result = ClearSpeakService(store).query("who is isaac newton")

            self.assertIn("entity count field", result.speech)
            self.assertIn("isaac newton", result.speech.casefold())
            self.assertIn("motion", result.speech)

    def test_document_fact_candidates_ignore_question_list_code_blocks_as_answers(self) -> None:
        passages = [
            {
                "raw_block_text": "```text\nWhat is Newton's second law?\nHow does acceleration relate to force and mass?\nWhy do laws of physics matter?\n```",
                "text": "```text What is Newton's second law? How does acceleration relate to force and mass? Why do laws of physics matter? ```",
                "score": 300.0,
                "source_name": "system_doc.md",
                "block_id": 1,
                "line_start": 1,
                "line_end": 4,
            },
            {
                "raw_block_text": "```text\nnewton laws of motion\n```",
                "text": "```text newton laws of motion ```",
                "score": 280.0,
                "source_name": "system_doc.md",
                "block_id": 2,
                "line_start": 5,
                "line_end": 7,
            },
            {
                "raw_block_text": "Hard laws:",
                "text": "Hard laws:",
                "score": 260.0,
                "source_name": "system_doc.md",
                "block_id": 3,
                "line_start": 8,
                "line_end": 8,
            },
            {
                "raw_block_text": "Question: Why do laws of physics matter?\nAnswer: They help explain and predict motion, forces, and energy.",
                "text": "Question: Why do laws of physics matter? Answer: They help explain and predict motion, forces, and energy.",
                "score": 100.0,
                "source_name": "newton.md",
                "block_id": 4,
                "line_start": 10,
                "line_end": 11,
            },
        ]

        candidates = _fact_candidates(
            ["why", "worry", "laws", "physics"],
            passages,
            ["acceleration", "motion", "law"],
        )

        self.assertTrue(candidates)
        self.assertEqual(candidates[0]["kind"], "qa_answer")
        self.assertIn("explain and predict", candidates[0]["answer_text"])
        self.assertFalse(any(str(row["answer_text"]).startswith("```text") for row in candidates))
        self.assertFalse(any(str(row["answer_text"]) == "Hard laws:" for row in candidates))


if __name__ == "__main__":
    unittest.main()
