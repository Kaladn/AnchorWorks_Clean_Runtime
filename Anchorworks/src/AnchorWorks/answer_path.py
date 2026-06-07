from __future__ import annotations

from typing import Any

from .document_answer import _clean_fact_answer_text, _fact_candidates


def choose_answer_block_path(
    query_anchors: list[str],
    passages: list[dict[str, Any]],
    answer_terms: list[str] | None = None,
    *,
    limit: int = 6,
) -> dict[str, Any]:
    """Choose a whole answer block from already-gathered document candidates."""

    candidates = _fact_candidates(query_anchors, passages, answer_terms or [])
    selected = candidates[0] if candidates else {}
    speech = _clean_fact_answer_text(str(selected.get("answer_text") or "")) if selected else ""
    return {
        "ok": bool(selected),
        "schema_version": "anchorworks_answer_block_path@1",
        "strategy": "answer_block_path",
        "query_anchors": [
            str(anchor or "").strip().casefold()
            for anchor in query_anchors
            if str(anchor or "").strip()
        ],
        "selected": selected,
        "candidate_count": len(candidates),
        "candidates": candidates[: max(1, int(limit or 6))],
        "speech": speech,
        "law": "Round up candidate answer blocks; use existing document candidate scoring; render the highest valid whole block.",
    }
