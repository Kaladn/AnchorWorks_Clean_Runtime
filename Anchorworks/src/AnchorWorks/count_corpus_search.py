from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .clearspeak_attention import blocked_answer_anchor
from .intake import extract_anchors


def rank_corpus_documents_from_count_terms(
    *,
    query_anchors: list[str],
    count_terms: list[dict[str, Any]],
    corpus_rows: Iterable[dict[str, Any]],
    top_k: int = 10,
) -> list[dict[str, Any]]:
    query_set = {
        str(anchor or "").strip().casefold()
        for anchor in query_anchors
        if str(anchor or "").strip() and not blocked_answer_anchor(str(anchor or "").strip().casefold())
    }
    term_weights: dict[str, float] = {}
    for row in count_terms:
        anchor = str(row.get("anchor") or "").strip().casefold()
        if not anchor or blocked_answer_anchor(anchor):
            continue
        weight = float(row.get("score", 0.0) or 0.0)
        observations = float(row.get("observations", 0.0) or 0.0)
        term_weights[anchor] = max(term_weights.get(anchor, 0.0), weight + observations)

    ranked: list[dict[str, Any]] = []
    for row in corpus_rows:
        doc_id = str(row.get("_id") or row.get("doc_id") or row.get("id") or "").strip()
        title = str(row.get("title") or "")
        text = str(row.get("text") or "")
        anchors = {
            str(anchor or "").strip().casefold()
            for anchor in extract_anchors(f"{title}\n{text}")
            if str(anchor or "").strip()
        }
        query_hits = sorted(query_set & anchors)
        count_hits = sorted(anchor for anchor in term_weights if anchor in anchors)
        score = float(len(query_hits) * 1000.0)
        score += sum(term_weights[anchor] for anchor in count_hits)
        if score <= 0:
            ranked.append({
                "doc_id": doc_id,
                "score": 0.0,
                "matched_query_anchors": [],
                "matched_count_terms": [],
            })
            continue
        ranked.append({
            "doc_id": doc_id,
            "score": round(score, 6),
            "matched_query_anchors": query_hits,
            "matched_count_terms": count_hits,
        })

    ranked.sort(key=lambda item: (-float(item["score"]), str(item["doc_id"])))
    return ranked[: max(1, int(top_k or 10))]
