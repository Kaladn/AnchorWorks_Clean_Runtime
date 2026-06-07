from __future__ import annotations

from AnchorWorks.document_answer import (
    DOCUMENT_WALK_TOP_K,
    DocumentAnswerAssembler,
    _fact_candidates,
    render_grounded_document_answer,
)


def test_document_walk_top_k_is_three() -> None:
    assert DOCUMENT_WALK_TOP_K == 3


def test_fact_candidates_require_full_multi_anchor_query_coverage() -> None:
    passages = [
        {
            "raw_block_text": "The squid pushes water backward and the water pushes the squid forward.",
            "text": "The squid pushes water backward and the water pushes the squid forward.",
            "source_name": "motion_lesson.md",
            "block_id": 1,
            "score": 1000,
        },
        {
            "raw_block_text": "Water is a compound made of the elements hydrogen and oxygen.",
            "text": "Water is a compound made of the elements hydrogen and oxygen.",
            "source_name": "chemistry_lesson.md",
            "block_id": 2,
            "score": 1,
        },
    ]

    candidates = _fact_candidates(["elements", "water"], passages, [])

    assert candidates
    assert candidates[0]["source_name"] == "chemistry_lesson.md"
    assert candidates[0]["content_query_hits"] == ["elements", "water"]
    assert all(candidate["source_name"] != "motion_lesson.md" for candidate in candidates)


def test_fact_candidates_allow_single_content_anchor_queries() -> None:
    passages = [
        {
            "raw_block_text": "The squid pushes water backward and the water pushes the squid forward.",
            "text": "The squid pushes water backward and the water pushes the squid forward.",
            "source_name": "motion_lesson.md",
            "block_id": 1,
            "score": 1,
        },
    ]

    candidates = _fact_candidates(["squid"], passages, [])

    assert candidates
    assert candidates[0]["source_name"] == "motion_lesson.md"
    assert candidates[0]["content_query_hits"] == ["squid"]


def test_render_grounded_document_answer_does_not_leak_count_path_when_no_fact_matches() -> None:
    speech = render_grounded_document_answer(
        "What are the elements of water?",
        ["elements", "water"],
        [
            {
                "raw_block_text": "The squid pushes water backward and the water pushes the squid forward.",
                "text": "The squid pushes water backward and the water pushes the squid forward.",
                "source_name": "motion_lesson.md",
                "block_id": 1,
                "score": 1000,
            }
        ],
        {
            "terms": [{"anchor": "pushes"}, {"anchor": "squid"}],
            "gathered_fact_frame": {
                "selected_fact": {},
                "candidate_facts": [],
            },
        },
    )

    assert speech == ""


def test_document_answer_assembler_does_not_render_weak_evidence_when_frame_fails() -> None:
    class Store:
        def recognize_query_anchors(self, query: str) -> dict:
            return {
                "query_anchors": ["what", "are", "the", "elements", "of", "water", "?"],
                "represented_anchors": ["elements", "water"],
                "missing_anchors": [],
            }

        def search_flat_document_evidence(self, anchors: list[str], *, query_anchors: list[str], max_files: int) -> dict:
            return {
                "source_passages": [
                    {
                        "raw_block_text": "The squid pushes water backward and the water pushes the squid forward.",
                        "text": "The squid pushes water backward and the water pushes the squid forward.",
                        "source_name": "motion_lesson.md",
                        "block_id": 1,
                        "score": 1000,
                    }
                ]
            }

    result = DocumentAnswerAssembler(Store()).answer("What are the elements of water?")

    assert result.speech == "No document-backed answer passed the query-frame check yet."
    assert result.answer_assembly["answer_block_path"]["ok"] is False
    assert result.answer_assembly["gathered_fact_frame"]["selected_fact"] == {}
