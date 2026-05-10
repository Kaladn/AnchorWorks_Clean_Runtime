from __future__ import annotations

from collections import Counter
from typing import Any


ATTENTION_CONTRACT = "anchorworks_clearspeak_attention@1"
ATTENTION_LAW = "Counts store weight; context clouds store neighborhood; attention chooses relevance."
MULTI_CONTEXT_SUPPORT_BONUS = 8.0
ROLE_SUPPORT_BONUS = 6.0


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
    attention_frame: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Rank answer candidates from weighted anchor neighborhoods.

    This is the current ClearSpeak attention layer: it does not create truth and
    it does not cite proof. It chooses which observed neighbors are relevant to
    the active context.
    """
    frame = attention_frame or infer_attention_frame(context)
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
                    "frame_type": frame["frame_type"],
                    "role_fit": {
                        "score": 0.0,
                        "matched_roles": [],
                        "supporting_anchors": [],
                    },
                    "lane_fit": {
                        "lane": "counts",
                        "score": 1.0,
                    },
                    "query_echo_penalty": 0.0,
                    "glue_penalty": 0.0,
                    "source_support": {
                        "kind": "lifetime_anchor_counts",
                        "evidence_required_for_claim": True,
                    },
                    "answer_health": {
                        "status": "supported",
                        "reason": "candidate_has_observed_count_support",
                    },
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
        role_fit = _role_fit(frame, row["supporting_context"])
        row["role_fit"] = role_fit
        row["selection_score"] = round(
            float(row["selection_score"])
            + (support_count * MULTI_CONTEXT_SUPPORT_BONUS)
            + float(role_fit["score"]),
            4,
        )
        row["why_chosen"] = [
            f"raw_observations={row['raw_observations']}",
            f"context_support={support_count}",
            "observations_x_position_strength",
            "multi_context_support_bonus",
            "role_frame_fit",
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
        "role_aware_candidate_score": "base_candidate_score + role_fit_score",
        "selected_anchor_reenters_context": True,
        "counts_create_truth": False,
        "clouds_cite_proof": False,
    }


def infer_attention_frame(anchors: list[str]) -> dict[str, Any]:
    observed = [str(anchor or "").strip().casefold() for anchor in anchors if str(anchor or "").strip()]
    frame_type = _frame_type(observed)
    content = content_anchors(observed)
    role_by_anchor: dict[str, str] = {}
    role_trace: list[dict[str, str]] = []

    for anchor in observed:
        role = _surface_role(anchor, frame_type)
        if role:
            role_by_anchor.setdefault(anchor, role)
            role_trace.append({"anchor": anchor, "role": role})

    if frame_type in {"method_question", "method_declaration"}:
        if content:
            role_by_anchor[content[0]] = "action_candidate"
        if len(content) > 1:
            role_by_anchor[content[1]] = "object_candidate"

    for anchor in content:
        role_by_anchor.setdefault(anchor, "content_anchor")

    return {
        "schema_version": "anchorworks_attention_frame@1",
        "frame_type": frame_type,
        "observed_anchors": observed,
        "content_anchors": content,
        "role_by_anchor": role_by_anchor,
        "role_trace": role_trace,
        "authority": "runtime_attention_shape",
        "writes_allowed": {
            "maps": False,
            "counts": False,
            "lifetime": False,
            "lexicon": False,
        },
    }


def content_anchors(anchors: list[str]) -> list[str]:
    content = [anchor for anchor in anchors if not blocked_answer_anchor(anchor)]
    return content or anchors


def _frame_type(anchors: list[str]) -> str:
    if "how" in anchors and "this" in anchors and "is" in anchors:
        return "method_declaration"
    if anchors and anchors[0] == "how":
        return "method_question"
    if "?" in anchors and "how" in anchors:
        return "method_question"
    if anchors and anchors[0] in {"what", "why", "when", "where", "which", "who"}:
        return "question"
    return "open_context"


def _surface_role(anchor: str, frame_type: str) -> str:
    if anchor == "how":
        return "method_marker" if frame_type == "method_declaration" else "question_marker"
    if anchor == "i":
        return "speaker_marker"
    if anchor == "this":
        return "declaration_marker"
    if anchor in {"do", "does", "did", "is", "are", "was", "were"}:
        return "glue_direction"
    if anchor == "?":
        return "question_punctuation"
    if anchor == ".":
        return "statement_punctuation"
    return ""


def _role_fit(frame: dict[str, Any], supporting_context: list[str]) -> dict[str, Any]:
    role_by_anchor = frame.get("role_by_anchor") if isinstance(frame.get("role_by_anchor"), dict) else {}
    matched: list[str] = []
    supporting: list[str] = []
    for anchor in supporting_context:
        role = str(role_by_anchor.get(anchor) or "")
        if not role or role in matched:
            continue
        matched.append(role)
        supporting.append(anchor)
    score = len(matched) * ROLE_SUPPORT_BONUS
    if "action_candidate" in matched and "object_candidate" in matched:
        score += ROLE_SUPPORT_BONUS
    return {
        "score": round(score, 4),
        "matched_roles": matched,
        "supporting_anchors": supporting,
    }


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
