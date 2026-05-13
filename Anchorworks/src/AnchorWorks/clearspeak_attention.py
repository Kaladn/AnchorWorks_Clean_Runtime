from __future__ import annotations

from collections import Counter
from typing import Any


ATTENTION_CONTRACT = "anchorworks_clearspeak_attention@1"
ATTENTION_LAW = "Counts store weight; context clouds store neighborhood; attention chooses relevance."
MULTI_CONTEXT_SUPPORT_BONUS = 8.0
ROLE_SUPPORT_BONUS = 6.0
ACTIVE_CLOUD_WEIGHTS = {
    "question": 0.35,
    "rear": 0.25,
    "answer": 0.30,
    "forward": 0.10,
}
ACTIVE_SCORE_WEIGHTS = {
    "question_fit": 0.30,
    "rear_fit": 0.25,
    "answer_fit": 0.25,
    "forward_fit": 0.15,
    "source_support": 0.05,
}
ANSWER_SLOT_KEYWORDS = {
    "category": {"law", "laws", "principle", "principles", "rule", "rules"},
    "mechanism": {"force", "forces", "mass", "acceleration", "accelerate", "motion", "move", "object", "objects"},
    "parts": {"first", "second", "third", "three", "pair", "pairs"},
}
NEWTON_MOTION_FIELD_TERMS = {
    "acceleration",
    "accelerate",
    "equal",
    "first",
    "force",
    "forces",
    "inertia",
    "law",
    "laws",
    "mass",
    "motion",
    "move",
    "moves",
    "object",
    "objects",
    "opposite",
    "pair",
    "pairs",
    "second",
    "third",
    "three",
}


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
    "about",
    "able",
    "also",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "for",
    "following",
    "from",
    "had",
    "has",
    "have",
    "how",
    "i",
    "if",
    "in",
    "information",
    "into",
    "is",
    "it",
    "learning",
    "may",
    "more",
    "one",
    "of",
    "on",
    "only",
    "or",
    "other",
    "our",
    "own",
    "questions",
    "should",
    "source",
    "that",
    "the",
    "their",
    "these",
    "they",
    "this",
    "to",
    "was",
    "were",
    "we",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
    "would",
    "will",
    "using",
    "your",
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


def build_active_cloud_frame(
    count_index: dict[str, Any],
    *,
    question_anchors: list[str],
    rear_context: list[str],
    answer_so_far: list[str],
    forward_context: list[str],
    blocked: set[str] | None = None,
    attention_frame: dict[str, Any] | None = None,
    top_k: int = 6,
    limit_per_anchor: int = 32,
) -> dict[str, Any]:
    """Build and score the active Q/R/A/F cloud for one answer step."""

    frame = attention_frame or infer_attention_frame(question_anchors)
    blocked_set = {str(anchor or "").strip().casefold() for anchor in (blocked or set())}
    clouds = {
        "question": _clean_list(question_anchors),
        "rear": _clean_list(rear_context),
        "answer": _clean_list(answer_so_far),
        "forward": _clean_list(forward_context),
    }
    candidate_rows: dict[str, dict[str, Any]] = {}
    rejected: dict[tuple[str, str], dict[str, Any]] = {}

    for cloud_name, anchors in clouds.items():
        for root in anchors:
            retrieved = retrieve_from_count_index(count_index, root, limit=limit_per_anchor)
            offsets = retrieved.get("offsets") if isinstance(retrieved.get("offsets"), dict) else {}
            for offset, rows in offsets.items():
                distance = offset_distance(str(offset))
                position_strength = 1.0 / max(distance, 1)
                for row in rows or []:
                    anchor = str(row.get("anchor") or "").strip().casefold()
                    observations = int(row.get("observations", 0) or 0)
                    if not anchor or observations <= 0:
                        continue
                    gate_reason = _candidate_gate_reason(anchor, blocked_set)
                    if gate_reason:
                        rejected.setdefault((anchor, gate_reason), {
                            "anchor": anchor,
                            "reason": gate_reason,
                            "supporting_cloud": cloud_name,
                            "supporting_anchor": root,
                        })
                        continue
                    current = candidate_rows.setdefault(anchor, {
                        "anchor": anchor,
                        "raw_observations": 0,
                        "weighted_observations": 0.0,
                        "cloud_support": {
                            "question": set(),
                            "rear": set(),
                            "answer": set(),
                            "forward": set(),
                        },
                        "support_offsets": set(),
                    })
                    current["raw_observations"] += observations
                    current["weighted_observations"] += observations * position_strength * ACTIVE_CLOUD_WEIGHTS[cloud_name]
                    current["cloud_support"][cloud_name].add(root)
                    current["support_offsets"].add(str(offset))

    candidates: list[dict[str, Any]] = []
    for anchor, row in candidate_rows.items():
        score_parts = {
            "question_fit": _support_fit(row["cloud_support"]["question"], clouds["question"]),
            "rear_fit": _support_fit(row["cloud_support"]["rear"], clouds["rear"]),
            "answer_fit": _support_fit(row["cloud_support"]["answer"], clouds["answer"]),
            "forward_fit": _support_fit(row["cloud_support"]["forward"], clouds["forward"]),
            "source_support": min(1.0, float(row["raw_observations"]) / 10.0),
        }
        penalties = _candidate_penalties(anchor, row, clouds, frame)
        score = (
            ACTIVE_SCORE_WEIGHTS["question_fit"] * score_parts["question_fit"]
            + ACTIVE_SCORE_WEIGHTS["rear_fit"] * score_parts["rear_fit"]
            + ACTIVE_SCORE_WEIGHTS["answer_fit"] * score_parts["answer_fit"]
            + ACTIVE_SCORE_WEIGHTS["forward_fit"] * score_parts["forward_fit"]
            + ACTIVE_SCORE_WEIGHTS["source_support"] * score_parts["source_support"]
            + min(0.25, float(row["weighted_observations"]) / 100.0)
            - penalties["total"]
        )
        supporting_context = _ordered_supporting_context(row["cloud_support"], clouds)
        role_fit = _role_fit(frame, supporting_context)
        score += min(0.10, float(role_fit["score"]) / 100.0)
        score -= _phrase_field_drift_penalty(anchor, frame)
        candidates.append({
            "anchor": anchor,
            "score": round(score, 6),
            "selection_score": round(score, 6),
            "score_parts": {key: round(value, 6) for key, value in score_parts.items()},
            "penalties": penalties,
            "raw_observations": int(row["raw_observations"]),
            "weighted_observations": round(float(row["weighted_observations"]), 6),
            "supporting_context": supporting_context,
            "cloud_support": {key: sorted(value) for key, value in row["cloud_support"].items()},
            "support_offsets": sorted(row["support_offsets"], key=offset_sort_key),
            "role_fit": role_fit,
            "source_support": {
                "kind": "lifetime_anchor_counts",
                "score": round(score_parts["source_support"], 6),
                "evidence_required_for_claim": True,
            },
            "answer_health": {
                "status": "supported",
                "reason": "candidate_supported_by_active_cloud",
            },
            "attention_math": attention_math_contract(),
            "frame_type": frame["frame_type"],
            "why_chosen": [
                "candidate_in_active_cloud",
                "Q/R/A/F_score_parts",
                "gates_passed_before_score",
                "path_trace_required",
            ],
        })

    candidates.sort(key=lambda item: (-float(item["score"]), -int(item["raw_observations"]), str(item["anchor"])))
    for index, row in enumerate(candidates, start=1):
        row["candidate_rank"] = index
    return {
        "schema_version": "anchorworks_active_cloud_frame@1",
        "combined_cloud_formula": "C_t = wq Q + wr R + wa A_t + wf F_t",
        "weights": dict(ACTIVE_CLOUD_WEIGHTS),
        "score_weights": dict(ACTIVE_SCORE_WEIGHTS),
        "clouds": clouds,
        "attention_frame": frame,
        "candidates": candidates[: max(1, int(top_k or 6))],
        "candidate_count": len(candidates),
        "rejected_candidates": sorted(rejected.values(), key=lambda item: (item["reason"], item["anchor"])),
        "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
    }


def choose_candidate_with_lookahead(
    count_index: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    seed_anchors: list[str],
    blocked: set[str] | None = None,
    lookahead_k: int = 6,
    min_future_content: int = 2,
    max_future_glue_ratio: float = 0.50,
    max_future_null_ratio: float = 0.25,
) -> dict[str, Any]:
    """Choose a candidate only after checking whether its future still has shape."""

    blocked_set = {str(anchor or "").strip().casefold() for anchor in (blocked or set())}
    seed_set = {str(anchor or "").strip().casefold() for anchor in seed_anchors if str(anchor or "").strip()}
    scored: list[dict[str, Any]] = []
    for row in candidates:
        anchor = str(row.get("anchor") or "").strip().casefold()
        future = _lookahead_health(
            count_index,
            anchor,
            seed_set=seed_set,
            blocked=blocked_set | {anchor},
            lookahead_k=lookahead_k,
            min_future_content=min_future_content,
            max_future_glue_ratio=max_future_glue_ratio,
            max_future_null_ratio=max_future_null_ratio,
        )
        current_score = float(row.get("score", row.get("selection_score", 0.0)) or 0.0)
        anomaly_penalty = 0.55 if future["pattern_health"] == "anomalous" else 0.0
        scored.append({
            **row,
            "current_score": round(current_score, 6),
            "lookahead_score": future["lookahead_score"],
            "final_score": round(current_score + float(future["lookahead_score"]) - anomaly_penalty, 6),
            "anomaly_penalty": anomaly_penalty,
            **future,
        })
    scored.sort(key=lambda item: (-float(item["final_score"]), int(item.get("candidate_rank", 9999)), str(item.get("anchor") or "")))
    chosen = next((row for row in scored if row.get("pattern_health") == "healthy"), scored[0] if scored else {})
    return {
        "schema_version": "clearspeak_topk_lookahead@1",
        "chosen": chosen,
        "candidates": scored,
        "lookahead": {
            "lookahead_k": lookahead_k,
            "min_future_content": min_future_content,
            "max_future_glue_ratio": max_future_glue_ratio,
            "max_future_null_ratio": max_future_null_ratio,
        },
        "law": "A top-K anchor is chosen only if its future still has shape; fallback preserves current top-K when no healthy future exists.",
    }


def build_answer_length_policy(
    *,
    limit: int = 6,
    min_anchors: int | None = None,
    target_anchors: int | None = None,
    max_anchors: int | None = None,
) -> dict[str, Any]:
    max_count = max(1, int(max_anchors if max_anchors is not None else limit or 6))
    min_count = max(0, int(min_anchors if min_anchors is not None else 0))
    if min_count > max_count:
        min_count = max_count
    target_count = int(target_anchors if target_anchors is not None else max(min_count, min(max_count, int(limit or max_count))))
    target_count = max(min_count, min(max_count, target_count))
    return {
        "schema_version": "anchorworks_answer_length_policy@1",
        "min_anchors": min_count,
        "target_anchors": target_count,
        "max_anchors": max_count,
        "stop_law": "Before min, continue; after target, stop only when required slots are satisfied or max is reached.",
    }


def answer_slot_state(frame: dict[str, Any], seed_anchors: list[str], emitted_anchors: list[str]) -> dict[str, Any]:
    content = set(_clean_list(frame.get("content_anchors") or seed_anchors))
    emitted = set(_clean_list(emitted_anchors))
    required = _required_answer_slots(frame, content)
    satisfied: list[str] = []
    slot_hits: dict[str, list[str]] = {}

    if "subject" in required and content:
        satisfied.append("subject")
        slot_hits["subject"] = sorted(content)
    for slot, keywords in ANSWER_SLOT_KEYWORDS.items():
        hits = sorted((content | emitted) & keywords)
        if slot == "parts":
            if len(set(hits) & {"first", "second", "third", "three"}) >= 2:
                satisfied.append(slot)
                slot_hits[slot] = hits
        elif hits:
            satisfied.append(slot)
            slot_hits[slot] = hits

    missing = [slot for slot in required if slot not in set(satisfied)]
    return {
        "schema_version": "anchorworks_answer_slot_state@1",
        "required_slots": required,
        "satisfied_slots": satisfied,
        "missing_slots": missing,
        "slot_hits": slot_hits,
        "all_required_satisfied": not missing,
    }


def answer_length_state(policy: dict[str, Any], emitted_count: int, slot_state: dict[str, Any]) -> dict[str, Any]:
    min_count = int(policy.get("min_anchors", 0) or 0)
    target_count = int(policy.get("target_anchors", min_count) or min_count)
    max_count = int(policy.get("max_anchors", target_count) or target_count)
    below_min = emitted_count < min_count
    at_target = emitted_count >= target_count
    at_max = emitted_count >= max_count
    slots_satisfied = bool(slot_state.get("all_required_satisfied", True))
    stop_allowed = (not below_min) and (slots_satisfied or at_max) and (at_target or at_max)
    if at_max:
        reason = "max_anchor_count_reached"
    elif below_min:
        reason = "below_min_anchor_count"
    elif not slots_satisfied:
        reason = "required_slots_missing"
    elif not at_target:
        reason = "below_target_anchor_count"
    else:
        reason = "stop_allowed"
    return {
        "schema_version": "anchorworks_answer_length_state@1",
        "emitted_count": emitted_count,
        "below_min": below_min,
        "at_target": at_target,
        "at_max": at_max,
        "stop_allowed": stop_allowed,
        "reason": reason,
    }


def _lookahead_health(
    count_index: dict[str, Any],
    anchor: str,
    *,
    seed_set: set[str],
    blocked: set[str],
    lookahead_k: int,
    min_future_content: int,
    max_future_glue_ratio: float,
    max_future_null_ratio: float,
) -> dict[str, Any]:
    retrieved = retrieve_from_count_index(count_index, anchor, limit=max(lookahead_k * 4, 8))
    offsets = retrieved.get("offsets") if isinstance(retrieved.get("offsets"), dict) else {}
    future_counts: Counter[str] = Counter()
    total = 0
    glue_total = 0
    null_total = 0
    for _offset, rows in offsets.items():
        for item in rows or []:
            neighbor = str(item.get("anchor") or "").strip().casefold()
            observations = int(item.get("observations", 0) or 0)
            if not neighbor or observations <= 0:
                continue
            total += observations
            if neighbor == "__null__":
                null_total += observations
                continue
            if blocked_answer_anchor(neighbor):
                glue_total += observations
                continue
            if neighbor in blocked:
                continue
            future_counts[neighbor] += observations
    if total <= 0:
        return {
            "future_cloud": [],
            "future_content_count": 0,
            "future_glue_ratio": 1.0,
            "future_null_ratio": 1.0,
            "backlink_support": 0,
            "lookahead_score": -1.0,
            "pattern_health": "anomalous",
            "rejected_reason": "future_cloud_empty",
        }
    future_rows = [
        anchor_name
        for anchor_name, _count in sorted(future_counts.items(), key=lambda item: (-item[1], item[0]))[:lookahead_k]
    ]
    non_seed_content = [item for item in future_rows if item not in seed_set]
    backlink_support = sum(1 for item in future_counts if item in seed_set)
    glue_ratio = glue_total / total
    null_ratio = null_total / total
    content_count = len(non_seed_content)
    anomalous = (
        content_count < min_future_content
        or glue_ratio > max_future_glue_ratio
        or null_ratio > max_future_null_ratio
    )
    lookahead_score = (content_count / max(1, lookahead_k)) + (0.12 * backlink_support) - (0.6 * glue_ratio) - (0.8 * null_ratio)
    return {
        "future_cloud": future_rows,
        "future_content_count": content_count,
        "future_glue_ratio": round(glue_ratio, 6),
        "future_null_ratio": round(null_ratio, 6),
        "backlink_support": backlink_support,
        "lookahead_score": round(lookahead_score, 6),
        "pattern_health": "anomalous" if anomalous else "healthy",
        "rejected_reason": "future_cloud_null_or_glue_heavy" if anomalous else "",
    }


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
        "active_cloud_formula": "C_t = wq Q + wr R + wa A_t + wf F_t",
        "active_cloud_weights": dict(ACTIVE_CLOUD_WEIGHTS),
        "active_candidate_score": "0.30*question_fit + 0.25*rear_fit + 0.25*answer_fit + 0.15*forward_fit + 0.05*source_support - penalties",
        "selected_anchor_reenters_context": True,
        "counts_create_truth": False,
        "clouds_cite_proof": False,
    }


def infer_attention_frame(anchors: list[str], phrase_field: dict[str, Any] | None = None) -> dict[str, Any]:
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
    phrase_payload = _phrase_field_payload(phrase_field)
    if phrase_payload:
        for anchor, role in phrase_payload.get("join_role_by_anchor", {}).items():
            role_by_anchor[anchor] = role

    frame = {
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
    if phrase_payload:
        frame["phrase_field"] = phrase_payload
    return frame


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


def _required_answer_slots(frame: dict[str, Any], content: set[str]) -> list[str]:
    frame_type = str(frame.get("frame_type") or "")
    if isinstance(frame.get("phrase_field"), dict):
        return ["subject", "category", "mechanism", "parts"]
    if frame_type in {"question", "open_context"} and {"newton", "laws", "motion"} & content:
        return ["subject", "category", "mechanism", "parts"]
    if frame_type == "method_question":
        return ["subject", "mechanism"]
    if frame_type == "question":
        return ["subject", "category"]
    return []


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
    if clean.startswith("<") or clean.endswith(">") or "xml" in clean:
        return True
    if len(clean) == 1 and not clean.isalnum():
        return True
    return bool(clean) and all(char.isdigit() for char in clean)


def _clean_list(anchors: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for anchor in anchors:
        clean = str(anchor or "").strip().casefold()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        out.append(clean)
    return out


def _candidate_gate_reason(anchor: str, blocked: set[str]) -> str:
    clean = str(anchor or "").strip().casefold()
    if clean in blocked:
        return "query_echo"
    if clean in _ANSWER_EXCLUSION_SET:
        return "glue_as_content"
    if clean and any((not char.isalnum()) and char not in {"'", "-"} for char in clean):
        return "punctuation_as_content"
    if len(clean) == 1 and not clean.isalnum():
        return "punctuation_as_content"
    if clean and all(char.isdigit() for char in clean):
        return "number_as_content"
    return ""


def _support_fit(supporting: set[str], cloud: list[str]) -> float:
    if not cloud:
        return 0.0
    return min(1.0, len(set(supporting)) / max(1, len(set(cloud))))


def _candidate_penalties(anchor: str, row: dict[str, Any], clouds: dict[str, list[str]], frame: dict[str, Any]) -> dict[str, float]:
    penalties = {
        "glue_as_content_penalty": 0.0,
        "unsupported_jump_penalty": 0.0,
        "repetition_penalty": 0.0,
        "contradiction_penalty": 0.0,
        "source_mismatch_penalty": 0.0,
        "query_echo_penalty": 0.0,
        "domain_drift_penalty": 0.0,
    }
    if anchor in set(clouds["question"]):
        penalties["query_echo_penalty"] = 0.50
    if clouds["answer"] and anchor in set(clouds["answer"]):
        penalties["repetition_penalty"] = 0.75
    if not row["cloud_support"]["question"] and not row["cloud_support"]["answer"]:
        penalties["unsupported_jump_penalty"] = 0.20
    content = set(_clean_list(frame.get("content_anchors") or []))
    penalties["domain_drift_penalty"] = _phrase_field_drift_penalty(anchor, frame)
    if not penalties["domain_drift_penalty"] and {"newton", "laws", "motion"} & content and anchor not in NEWTON_MOTION_FIELD_TERMS:
        penalties["domain_drift_penalty"] = 0.45
    penalties["total"] = round(sum(penalties.values()), 6)
    return penalties


def _phrase_field_payload(phrase_field: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(phrase_field, dict):
        return None
    sequence = [str(anchor or "").strip().casefold() for anchor in phrase_field.get("anchor_sequence") or [] if str(anchor or "").strip()]
    if not sequence:
        return None
    return {
        "schema_version": "anchorworks_phrase_field@1",
        "phrase": str(phrase_field.get("phrase") or " ".join(sequence)),
        "hex": str(phrase_field.get("hex") or phrase_field.get("symbol") or ""),
        "phrase_type": str(phrase_field.get("phrase_type") or ""),
        "anchor_sequence": sequence,
        "join_role_by_anchor": {
            str(anchor or "").strip().casefold(): str(role)
            for anchor, role in (phrase_field.get("join_role_by_anchor") or {}).items()
            if str(anchor or "").strip()
        },
        "authority": "phrase_lexicon",
    }


def _phrase_field_drift_penalty(anchor: str, frame: dict[str, Any]) -> float:
    phrase = frame.get("phrase_field") if isinstance(frame.get("phrase_field"), dict) else {}
    sequence = set(_clean_list((phrase or {}).get("anchor_sequence") or []))
    if not sequence:
        return 0.0
    field_terms = sequence | NEWTON_MOTION_FIELD_TERMS
    return 0.45 if str(anchor or "").strip().casefold() not in field_terms else 0.0


def _ordered_supporting_context(cloud_support: dict[str, set[str]], clouds: dict[str, list[str]]) -> list[str]:
    ordered: list[str] = []
    for cloud_name in ("question", "rear", "answer", "forward"):
        support = cloud_support.get(cloud_name) or set()
        for anchor in clouds.get(cloud_name) or []:
            if anchor in support and anchor not in ordered:
                ordered.append(anchor)
    return ordered


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
