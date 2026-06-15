from __future__ import annotations

from collections import Counter

from AnchorWorks.clearspeak import ClearSpeakService


class _CountSearchStore:
    def recognize_query_anchors(self, query: str) -> dict:
        return {
            "query_anchors": ["what", "are", "the", "elements", "of", "water", "?"],
            "represented_anchors": ["what", "are", "the", "elements", "of", "water"],
            "represented_content_anchors": ["elements", "water"],
            "missing_anchors": [],
            "missing_content_anchors": [],
            "input_kind": "question",
        }

    def match_phrase_authority(self, represented: list[str]) -> dict:
        return {}


class _CountSearchService(ClearSpeakService):
    def _load_count_index(self, seed_anchors: list[str] | None = None) -> dict:
        return {
            "by_anchor": {
                "elements": {
                    "+1": Counter({"hydrogen": 8, "oxygen": 7, "water": 3}),
                    "+2": Counter({"compound": 3}),
                },
                "water": {
                    "-1": Counter({"elements": 3}),
                    "+1": Counter({"compound": 6, "hydrogen": 5, "oxygen": 5}),
                },
                "hydrogen": {
                    "+1": Counter({"oxygen": 4, "compound": 2}),
                    "-1": Counter({"elements": 4, "water": 2}),
                },
                "oxygen": {
                    "-1": Counter({"hydrogen": 4, "elements": 3, "water": 2}),
                    "+1": Counter({"compound": 2}),
                },
                "compound": {
                    "-1": Counter({"water": 3, "hydrogen": 2, "oxygen": 2}),
                },
            }
        }


def test_clearspeak_count_search_gathers_answer_terms_beyond_query_anchors() -> None:
    result = _CountSearchService(_CountSearchStore()).query(
        "What are the elements of water?",
        limit=4,
        min_anchors=2,
        target_anchors=3,
        max_anchors=4,
    )

    chosen = result.answer_assembly["answer_path"]["chosen_anchors"]

    assert "hydrogen" in chosen
    assert "oxygen" in chosen
    assert result.answer_assembly["stop_reason"] != "no_candidate_pool"
