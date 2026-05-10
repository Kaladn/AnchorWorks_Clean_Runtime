from __future__ import annotations

from collections import Counter
from typing import Any


ATTENTION_CONTRACT = "anchorworks_clearspeak_attention@1"
ATTENTION_LAW = "Counts store weight; context clouds store neighborhood; attention chooses relevance."
MULTI_CONTEXT_SUPPORT_BONUS = 8.0


_ANSWER_EXCLUSION_SET = {
    "",
    ".",
    ",",
    "?",
    "!",
    ":",
    ";",
    "(",
    ")",
    "[",
    "]",
    "{",
    "}",
    "a",
    "an",
    "and",
    "are",
    "as",
    "be",
    "but",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "for",
    "from",
    "had",
    "has",
    "have",
    "how",
    "i",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "our",
    "should",
    "source",
    "that",
    "the",
    "their",
    "this",
    "to",
    "was",
    "we",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
    "would",
    "you",
}


def rank_attention_candidates(
    count_index: dict[str, Any],
    context: list[str],
    *,
    blocked: set[str] | None = None,
    limit_per_anchor: int = 32,
) -> list[dict[str, Any]]:
    """Rank answer candidates from weighted anchor neighborhoods.

    This is the current ClearSpeak attention layer: it does not create truth and
    it does not cite proof. It chooses which observed neighbors are relevant to
    the active context.
    """
    excluded = set(blocked or set())
    candidates: dict[str, dict[str, Any]] = {}
    for context_anchor in context[-50:]:
        retrieved = retrieve_from_count_index(count_index, context_anchor, limit=limit_per_anchor)
        offsets = retrieved.get("offsets") if isinstance(retrieved.get("offsets"), dict) else {}
        for offset, rows in offsets.items():
            distance = offset_distance(str(offset))
            position_strength = 1.0 / max(distance, 1)
            for row in rows or []:
                anchor = str(row.get("anchor") or "").strip()
                if not anchor or anchor in excluded or blocked_answer_anchor(anchor):
                    continue
                observations = int(row.get("observations", 0) or 0)
                if observations <= 0:
                    continue
                current = candidates.setdefault(anchor, {
                    "anchor": anchor,
                    "selection_score": 0.0,
                    "raw_observations": 0,
                    "supporting_context": [],
                    "support_offsets": [],
                    "why_chosen": [],
                    "attention_math": attention_math_contract(),
                })
                current["selection_score"] += observations * position_strength
                current["raw_observations"] += observations
                if context_anchor not in current["supporting_context"]:
                    current["supporting_context"].append(context_anchor)
                if str(offset) not in current["support_offsets"]:
                    current["support_offsets"].append(str(offset))

    ranked = list(candidates.values())
    for row in ranked:
        support_count = len(row["supporting_context"])
        row["selection_score"] = round(
            float(row["selection_score"]) + (support_count * MULTI_CONTEXT_SUPPORT_BONUS),
            4,
        )
        row["why_chosen"] = [
            f"raw_observations={row['raw_observations']}",
            f"context_support={support_count}",
            "observations_x_position_strength",
            "multi_context_support_bonus",
            "selected_anchor_reenters_context",
        ]
    ranked.sort(key=lambda row: (-float(row["selection_score"]), -int(row["raw_observations"]), str(row["anchor"])))
    return ranked


def attention_math_contract() -> dict[str, Any]:
    return {
        "schema_version": ATTENTION_CONTRACT,
        "kind": "runtime_relevance_scoring",
        "law": ATTENTION_LAW,
        "cloud_role": "stored_neighborhood",
        "attention_role": "choose_relevance_for_active_context",
        "position_strength": "1 / absolute_offset_distance",
        "candidate_score": "sum(observations * position_strength) + supporting_context_count * 8",
        "selected_anchor_reenters_context": True,
        "counts_create_truth": False,
        "clouds_cite_proof": False,
    }


def content_anchors(anchors: list[str]) -> list[str]:
    content = [anchor for anchor in anchors if not blocked_answer_anchor(anchor)]
    return content or anchors


def blocked_answer_anchor(anchor: str) -> bool:
    clean = str(anchor or "").strip().casefold()
    if clean in _ANSWER_EXCLUSION_SET:
        return True
    if len(clean) == 1 and not clean.isalnum():
        return True
    return bool(clean) and all(char.isdigit() for char in clean)


def retrieve_from_count_index(count_index: dict[str, Any], anchor: str, limit: int = 25) -> dict[str, Any]:
    surface = str(anchor or "").strip().lower()
    offsets = (count_index.get("by_anchor") or {}).get(surface) or {}
    total_by_neighbor: Counter[str] = Counter()
    by_offset: dict[str, Counter[str]] = {}
    for offset, counter in offsets.items():
        if not isinstance(counter, Counter):
            counter = Counter(counter or {})
        for neighbor, observations in counter.items():
            count = int(observations or 0)
            if count <= 0:
                continue
            total_by_neighbor[str(neighbor)] += count
            by_offset.setdefault(str(offset), Counter())[str(neighbor)] += count
    neighbor_rows = [
        {"anchor": neighbor, "observations": count}
        for neighbor, count in sorted(total_by_neighbor.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]
    offset_rows = {
        offset: [
            {"anchor": neighbor, "observations": count}
            for neighbor, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit]
        ]
        for offset, counter in sorted(by_offset.items(), key=lambda item: (offset_sort_key(item[0]), item[0]))
    }
    return {
        "anchor": surface,
        "neighbor_count": len(total_by_neighbor),
        "total_neighbor_observations": int(sum(total_by_neighbor.values())),
        "neighbors": neighbor_rows,
        "offsets": offset_rows,
    }


def offset_distance(offset: str) -> int:
    try:
        return abs(int(str(offset).replace("+", "")))
    except ValueError:
        return 6


def offset_sort_key(offset: str) -> int:
    try:
        return int(str(offset).replace("+", ""))
    except ValueError:
        return 0
