from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
from typing import Any


ATTENTION_CONTRACT = "anchorworks_attention_frame@2"
ATTENTION_LAW = (
    "Counts store observed data truth as symbolic weight. AW coordinates prove where it was observed. "
    "Attention admits relevant observed evidence; it does not promote evidence into world truth."
)

ACTIVE_CLOUD_WEIGHTS = {
    "question": 0.40,
    "rear": 0.20,
    "answer": 0.30,
    "forward": 0.10,
}

ACTIVE_SCORE_WEIGHTS = {
    "query_support": 0.40,
    "context_support": 0.20,
    "answer_support": 0.20,
    "coordinate_support": 0.15,
    "source_support": 0.05,
}

_BLOCKED_CONTENT = {
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
    "from",
    "had",
    "has",
    "have",
    "how",
    "i",
    "if",
    "in",
    "is",
    "it",
    "may",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
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

_METADATA_OR_SECTION_LABELS = {
    "abstract",
    "background",
    "conclusion",
    "conclusions",
    "data",
    "document",
    "id",
    "introduction",
    "line",
    "methods",
    "objective",
    "objectives",
    "purpose",
    "result",
    "results",
    "source",
    "study",
    "title",
}

_LOW_SIGNAL_GENERAL_TERMS = {
    "against",
    "after",
    "acute",
    "addition",
    "adult",
    "afforded",
    "all",
    "among",
    "approximately",
    "assess",
    "been",
    "being",
    "benefit",
    "between",
    "case",
    "cases",
    "caused",
    "ci",
    "confidence",
    "control",
    "during",
    "findings",
    "found",
    "greater",
    "high",
    "included",
    "increased",
    "interval",
    "lower",
    "new",
    "observed",
    "performed",
    "reported",
    "showed",
    "significant",
    "significantly",
    "total",
    "than",
    "using",
    "values",
    "well",
    "we",
}

_ATTENTION_ANCHOR_PATTERN = re.compile(r"^[a-z][a-z']{1,63}$")


def build_native_search_attention(
    native_search: dict[str, Any],
    *,
    top_k: int = 12,
    n0_regex_path: str | Path | None = None,
) -> dict[str, Any]:
    """Admit a focused evidence set from the native search coordinate receipt.

    Input is the native `search-aw` payload. This function does not score the
    binary count stream and does not read documents. It only chooses which
    already-returned symbols/blocks deserve attention.
    """

    query_anchors = _clean_list(native_search.get("query_anchors") or [])
    represented_anchors = _clean_list(native_search.get("represented_anchors") or [])
    missing_anchors = _clean_list(native_search.get("missing_anchors") or [])
    user_regex = _load_user_n0_regex(n0_regex_path or native_search.get("n0_regex_path") or native_search.get("attention_regex_path"))
    if not represented_anchors and int(native_search.get("represented_anchor_count", 0) or 0) == len(query_anchors):
        represented_anchors = list(query_anchors)
    missing_content = [anchor for anchor in missing_anchors if not blocked_answer_anchor(anchor)]
    if missing_content:
        return {
            "schema_version": ATTENTION_CONTRACT,
            "law": ATTENTION_LAW,
            "admission_status": "refused",
            "refusal_reason": "missing_query_content_anchor",
            "observed_data_truth": False,
            "world_truth_claim": False,
            "world_truth_promoted": False,
            "query": str(native_search.get("query") or ""),
            "query_anchors": query_anchors,
            "represented_anchors": represented_anchors,
            "missing_anchors": missing_anchors,
            "missing_content_anchors": missing_content,
            "represented_anchor_count": int(native_search.get("represented_anchor_count", 0) or 0),
            "count_candidate_count": int(native_search.get("count_candidate_count", 0) or 0),
            "admitted_blocks": [],
            "focus_candidates": [],
            "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
        }
    candidate_rows: dict[str, dict[str, Any]] = {}
    admitted_blocks: list[dict[str, Any]] = []
    answer_forward_evidence: list[dict[str, Any]] = []
    deferred_blocks: list[dict[str, Any]] = []
    n0_rejected: list[dict[str, Any]] = []
    raw_hits = [hit for hit in (native_search.get("hits") or []) if isinstance(hit, dict)]
    max_query_overlap = 0
    for hit in raw_hits:
        max_query_overlap = max(max_query_overlap, len(_clean_list(hit.get("query_anchor_hits") or [])))

    for hit in raw_hits:
        query_hits = _clean_list(hit.get("query_anchor_hits") or [])
        candidate_hits = _clean_list(hit.get("count_candidate_anchor_hits") or [])
        block_score = float(hit.get("score", 0.0) or 0.0)
        coordinate = {
            "doc_id": str(hit.get("doc_id") or ""),
            "source_file": str(hit.get("source_file") or ""),
            "block_id": int(hit.get("block_id", 0) or 0),
            "block_line_start": int(hit.get("block_line_start", 0) or 0),
            "block_line_end": int(hit.get("block_line_end", 0) or 0),
            "document_line_start": int(hit.get("document_line_start", 0) or 0),
            "document_line_end": int(hit.get("document_line_end", 0) or 0),
            "rag_copy": str(hit.get("rag_copy") or ""),
            "query_anchor_hits": query_hits,
            "score": block_score,
        }
        if query_hits:
            answer_forward_evidence.append(coordinate)
        if query_hits and len(query_hits) < max_query_overlap:
            deferred_blocks.append(coordinate)
            continue
        if query_hits:
            admitted_blocks.append(coordinate)
        for source_anchor in candidate_hits:
            anchor, normalize_trace = _apply_user_normalize(source_anchor, user_regex)
            user_admit: dict[str, Any] = {}
            user_deny = _user_regex_match(anchor, user_regex.get("deny_focus_patterns"))
            if user_deny:
                reason = user_deny.get("reason") or "user_denied_focus"
            else:
                reason = _candidate_gate_reason(anchor, set(query_anchors))
                if not reason:
                    user_admit = _user_regex_match(anchor, user_regex.get("admit_focus_patterns"))
            if reason:
                n0_rejected.append({
                    "anchor": anchor,
                    "source_anchor": source_anchor,
                    "reason": reason,
                    "block_id": coordinate["block_id"],
                    "doc_id": coordinate["doc_id"],
                })
                continue
            current = candidate_rows.setdefault(anchor, {
                "anchor": anchor,
                "source_anchor": source_anchor,
                "first_seen": len(candidate_rows),
                "attention_score": 0.0,
                "selection_score": 0.0,
                "supporting_blocks": [],
                "supporting_query_anchors": set(),
                "raw_observations": 0,
                "user_regex": {
                    "normalized": bool(normalize_trace),
                    "normalization": normalize_trace,
                    "boost": 0.0,
                    "admit_reason": user_admit.get("reason", ""),
                },
                "why_chosen": [],
            })
            boost_match = _user_regex_match(anchor, user_regex.get("boost_focus_patterns"))
            boost = float((boost_match or {}).get("boost", 0.0) or 0.0)
            if user_admit:
                boost += float(user_admit.get("boost", 3.0) or 3.0)
            current["user_regex"]["boost"] += boost
            if boost_match and boost_match.get("reason"):
                current["user_regex"]["boost_reason"] = boost_match.get("reason")
            current["attention_score"] += max(1.0, block_score / 1000.0) + len(query_hits) + boost
            current["raw_observations"] += 1
            current["supporting_query_anchors"].update(query_hits)
            current["supporting_blocks"].append(coordinate)

    focus_candidates = list(candidate_rows.values())
    for row in focus_candidates:
        support_count = len(row["supporting_query_anchors"])
        row["attention_score"] = round(float(row["attention_score"]) + support_count, 6)
        row["selection_score"] = row["attention_score"]
        row["supporting_query_anchors"] = sorted(row["supporting_query_anchors"])
        row["supporting_blocks"] = _dedupe_coordinates(row["supporting_blocks"])
        row["why_chosen"] = [
            "native_count_candidate_seen_in_admitted_block",
            "block_has_query_anchor_overlap",
            "coordinate_support_preserved",
        ]
    focus_candidates.sort(key=lambda item: (-float(item["attention_score"]), int(item.get("first_seen", 0)), str(item["anchor"])))

    return {
        "schema_version": ATTENTION_CONTRACT,
        "law": ATTENTION_LAW,
        "admission_status": "admitted" if admitted_blocks or focus_candidates else "empty",
        "refusal_reason": "",
        "observed_data_truth": bool(admitted_blocks or focus_candidates),
        "world_truth_claim": False,
        "world_truth_promoted": False,
        "query": str(native_search.get("query") or ""),
        "query_anchors": query_anchors,
        "represented_anchors": represented_anchors,
        "missing_anchors": missing_anchors,
        "missing_content_anchors": [],
        "represented_anchor_count": int(native_search.get("represented_anchor_count", 0) or 0),
        "count_candidate_count": int(native_search.get("count_candidate_count", 0) or 0),
        "admitted_blocks": _dedupe_coordinates(admitted_blocks)[: max(1, int(top_k or 1))],
        "answer_forward_evidence": _dedupe_coordinates(answer_forward_evidence),
        "focus_candidates": focus_candidates[: max(1, int(top_k or 1))],
        "n0_attention": {
            "schema_version": "anchorworks_n0_attention@1",
            "law": "n0_attention rejects attention pollution before focus admission without erasing evidence or counts.",
            "rejected_count": len(n0_rejected),
            "rejected": n0_rejected,
            "deferred_block_count": len(_dedupe_coordinates(deferred_blocks)),
            "deferred_blocks": _dedupe_coordinates(deferred_blocks),
            "user_regex": _user_regex_report(user_regex),
            "answer_forward_ops_may_use_evidence": True,
        },
        "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
    }


def build_renderer_handoff(attention: dict[str, Any], native_search: dict[str, Any]) -> dict[str, Any]:
    """Verify attention output and prepare a renderer-facing payload.

    n0_attention denies focus authority, not language availability. This handoff
    restores full native candidate terms to the renderer while preserving the
    attention focus set and evidence coordinates.
    """

    verified, failures = _verify_attention_payload(attention)
    evidence_blocks = list(attention.get("answer_forward_evidence") or attention.get("admitted_blocks") or [])
    focus_anchors = [str(row.get("anchor") or "") for row in attention.get("focus_candidates") or [] if row.get("anchor")]
    renderer_terms: list[str] = []
    for hit in native_search.get("hits") or []:
        if not isinstance(hit, dict):
            continue
        for anchor in hit.get("count_candidate_anchor_hits") or []:
            clean = str(anchor or "").strip().casefold()
            if clean and clean not in renderer_terms:
                renderer_terms.append(clean)
    rejected_terms = [
        {"anchor": str(row.get("source_anchor") or row.get("anchor") or ""), "reason": str(row.get("reason") or "")}
        for row in attention.get("n0_attention", {}).get("rejected", []) or []
    ]
    return {
        "schema_version": "anchorworks_renderer_handoff@1",
        "mode": str(native_search.get("mode") or "rag"),
        "verified": verified,
        "verification_failures": failures,
        "render_may_use_full_language": True,
        "renderer_role": "compose_from_verified_observed_evidence",
        "observed_data_truth": bool(attention.get("observed_data_truth")),
        "world_truth_claim": False,
        "world_truth_promoted": False,
        "query": str(attention.get("query") or native_search.get("query") or ""),
        "focus_anchors": focus_anchors,
        "renderer_terms": renderer_terms,
        "evidence_blocks": evidence_blocks,
        "attention_rejected_terms": rejected_terms,
        "n0_attention": attention.get("n0_attention") or {},
        "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
    }


def render_from_handoff(handoff: dict[str, Any]) -> dict[str, Any]:
    """Render a verified observed-data handoff without promoting world truth."""

    mode = str(handoff.get("mode") or "counts").strip().casefold()
    if not handoff.get("verified"):
        return {
            "schema_version": "anchorworks_handoff_render@1",
            "mode": mode,
            "renderer": "refusal_surface",
            "ok": False,
            "speech": "No verified observed-data handoff passed the renderer gate.",
            "citations": [],
            "focus_anchors": [],
            "attention_rejected_terms": list(handoff.get("attention_rejected_terms") or []),
            "observed_data_truth": False,
            "world_truth_claim": False,
            "verification_failures": list(handoff.get("verification_failures") or ["handoff_not_verified"]),
            "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
        }

    if mode == "rag":
        blocks = list(handoff.get("evidence_blocks") or [])
        return {
            "schema_version": "anchorworks_handoff_render@1",
            "mode": "rag",
            "renderer": "block_surface",
            "ok": True,
            "speech": "",
            "blocks": blocks,
            "citations": [_citation_from_block(block) for block in blocks if isinstance(block, dict)],
            "focus_anchors": list(handoff.get("focus_anchors") or []),
            "attention_rejected_terms": list(handoff.get("attention_rejected_terms") or []),
            "observed_data_truth": bool(handoff.get("observed_data_truth")),
            "world_truth_claim": False,
            "world_truth_promoted": False,
            "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
        }

    renderer_terms = _clean_list(list(handoff.get("renderer_terms") or []))
    focus_anchors = _clean_list(list(handoff.get("focus_anchors") or []))
    phrase_terms = renderer_terms if _renderer_terms_are_phrase_like(renderer_terms, focus_anchors) else (focus_anchors or renderer_terms)
    phrase = _renderer_phrase(phrase_terms, allow_list_style=(phrase_terms == focus_anchors and bool(focus_anchors)))
    citations = [_citation_from_block(block) for block in (handoff.get("evidence_blocks") or []) if isinstance(block, dict)]
    coordinate_text = _coordinate_phrase(citations)
    if phrase and coordinate_text:
        speech = f"Observed data supports the phrase '{phrase}' at {coordinate_text}."
    elif coordinate_text:
        speech = f"Observed data is available at {coordinate_text}."
    else:
        speech = "Observed data passed attention, but no source coordinate was available for rendering."
    return {
        "schema_version": "anchorworks_handoff_render@1",
        "mode": "counts",
        "renderer": "language_surface",
        "ok": True,
        "speech": speech,
        "citations": citations,
        "focus_anchors": focus_anchors,
        "attention_rejected_terms": list(handoff.get("attention_rejected_terms") or []),
        "observed_data_truth": bool(handoff.get("observed_data_truth")),
        "world_truth_claim": False,
        "world_truth_promoted": False,
        "render_may_use_full_language": True,
        "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
    }


def rank_attention_candidates(
    count_index: dict[str, Any],
    context: list[str],
    *,
    blocked: set[str] | None = None,
    limit_per_anchor: int = 32,
    attention_frame: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    frame = attention_frame or infer_attention_frame(context)
    blocked_set = {str(item or "").strip().casefold() for item in (blocked or set())}
    candidates: dict[str, dict[str, Any]] = {}
    for root in _clean_list(context)[-50:]:
        retrieved = retrieve_from_count_index(count_index, root, limit=limit_per_anchor)
        for offset, rows in (retrieved.get("offsets") or {}).items():
            strength = 1.0 / max(1, offset_distance(str(offset)))
            for row in rows or []:
                anchor = str(row.get("anchor") or "").strip().casefold()
                observations = int(row.get("observations", 0) or 0)
                gate = _candidate_gate_reason(anchor, blocked_set)
                if gate or observations <= 0:
                    continue
                current = candidates.setdefault(anchor, _candidate_seed(anchor, frame))
                current["raw_observations"] += observations
                current["selection_score"] += observations * strength
                current["supporting_context"].add(root)
                current["support_offsets"].add(str(offset))
    ranked = [_finalize_candidate(row, frame) for row in candidates.values()]
    ranked.sort(key=lambda item: (-float(item["selection_score"]), -int(item["raw_observations"]), item["anchor"]))
    for index, row in enumerate(ranked, start=1):
        row["candidate_rank"] = index
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
    frame = attention_frame or infer_attention_frame(question_anchors)
    blocked_set = {str(item or "").strip().casefold() for item in (blocked or set())}
    clouds = {
        "question": _clean_list(question_anchors),
        "rear": _clean_list(rear_context),
        "answer": _clean_list(answer_so_far),
        "forward": _clean_list(forward_context),
    }
    candidates: dict[str, dict[str, Any]] = {}
    rejected: list[dict[str, Any]] = []

    for cloud_name, roots in clouds.items():
        for root in roots:
            retrieved = retrieve_from_count_index(count_index, root, limit=limit_per_anchor)
            for offset, rows in (retrieved.get("offsets") or {}).items():
                strength = ACTIVE_CLOUD_WEIGHTS[cloud_name] / max(1, offset_distance(str(offset)))
                for row in rows or []:
                    anchor = str(row.get("anchor") or "").strip().casefold()
                    observations = int(row.get("observations", 0) or 0)
                    reason = _candidate_gate_reason(anchor, blocked_set)
                    if reason or observations <= 0:
                        if anchor:
                            rejected.append({"anchor": anchor, "reason": reason or "no_observations"})
                        continue
                    current = candidates.setdefault(anchor, _candidate_seed(anchor, frame))
                    current["raw_observations"] += observations
                    current["selection_score"] += observations * strength
                    current["supporting_context"].add(root)
                    current["support_offsets"].add(str(offset))
                    current["cloud_support"][cloud_name].add(root)

    rows = [_finalize_candidate(row, frame) for row in candidates.values()]
    rows.sort(key=lambda item: (-float(item["selection_score"]), -int(item["raw_observations"]), item["anchor"]))
    for index, row in enumerate(rows, start=1):
        row["candidate_rank"] = index
    return {
        "schema_version": "anchorworks_active_cloud_frame@2",
        "law": ATTENTION_LAW,
        "combined_cloud_formula": "attention = weighted symbolic neighborhood admission",
        "weights": dict(ACTIVE_CLOUD_WEIGHTS),
        "score_weights": dict(ACTIVE_SCORE_WEIGHTS),
        "clouds": clouds,
        "attention_frame": frame,
        "candidates": rows[: max(1, int(top_k or 1))],
        "candidate_count": len(rows),
        "rejected_candidates": _dedupe_rejections(rejected),
        "observed_data_truth": bool(rows),
        "world_truth_claim": False,
        "world_truth_promoted": False,
        "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
    }


def choose_candidate_with_lookahead(
    count_index: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    seed_anchors: list[str],
    blocked: set[str] | None = None,
    lookahead_k: int = 6,
    min_future_content: int = 1,
    max_future_glue_ratio: float = 0.75,
    max_future_null_ratio: float = 0.50,
) -> dict[str, Any]:
    blocked_set = {str(item or "").strip().casefold() for item in (blocked or set())}
    scored: list[dict[str, Any]] = []
    for row in candidates:
        anchor = str(row.get("anchor") or "").strip().casefold()
        future = _future_health(
            count_index,
            anchor,
            blocked=blocked_set | {anchor},
            lookahead_k=lookahead_k,
            min_future_content=min_future_content,
            max_future_glue_ratio=max_future_glue_ratio,
            max_future_null_ratio=max_future_null_ratio,
        )
        current = float(row.get("selection_score", row.get("score", 0.0)) or 0.0)
        scored.append({
            **row,
            "current_score": round(current, 6),
            "lookahead_score": future["lookahead_score"],
            "final_score": round(current + float(future["lookahead_score"]), 6),
            **future,
        })
    scored.sort(key=lambda item: (-float(item["final_score"]), int(item.get("candidate_rank", 9999)), item["anchor"]))
    chosen = next((row for row in scored if row.get("pattern_health") == "healthy"), {})
    return {
        "schema_version": "anchorworks_attention_lookahead@2",
        "chosen": chosen,
        "candidates": scored,
        "path_health": "healthy" if chosen else "blocked",
        "stop_reason": "" if chosen else "no_admissible_future",
        "observed_data_truth": bool(scored),
        "world_truth_claim": False,
        "world_truth_promoted": False,
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
    min_count = min(min_count, max_count)
    target_count = int(target_anchors if target_anchors is not None else max(min_count, min(max_count, limit or max_count)))
    target_count = max(min_count, min(max_count, target_count))
    return {
        "schema_version": "anchorworks_answer_length_policy@2",
        "min_anchors": min_count,
        "target_anchors": target_count,
        "max_anchors": max_count,
        "stop_law": "stop only after minimum, target, and required slot conditions allow it",
    }


def answer_slot_state(frame: dict[str, Any], seed_anchors: list[str], emitted_anchors: list[str]) -> dict[str, Any]:
    required = list(frame.get("required_slots") or [])
    content = set(_clean_list(frame.get("content_anchors") or seed_anchors))
    emitted = set(_clean_list(emitted_anchors))
    satisfied: list[str] = []
    if "subject" in required and content:
        satisfied.append("subject")
    if "answer_content" in required and (emitted - content):
        satisfied.append("answer_content")
    missing = [slot for slot in required if slot not in set(satisfied)]
    return {
        "schema_version": "anchorworks_answer_slot_state@2",
        "required_slots": required,
        "satisfied_slots": satisfied,
        "missing_slots": missing,
        "slot_hits": {"content": sorted(content), "emitted": sorted(emitted)},
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
        "schema_version": "anchorworks_answer_length_state@2",
        "emitted_count": emitted_count,
        "below_min": below_min,
        "at_target": at_target,
        "at_max": at_max,
        "stop_allowed": stop_allowed,
        "reason": reason,
    }


def attention_math_contract() -> dict[str, Any]:
    return {
        "schema_version": ATTENTION_CONTRACT,
        "kind": "runtime_focus_admission",
        "law": ATTENTION_LAW,
        "counts_create_observed_data_truth": True,
        "counts_create_world_truth": False,
        "attention_role": "admit ranked focus from observed symbolic evidence",
        "coordinate_role": "preserve doc/block/line location for later proof",
        "active_cloud_weights": dict(ACTIVE_CLOUD_WEIGHTS),
        "active_score_weights": dict(ACTIVE_SCORE_WEIGHTS),
    }


def infer_attention_frame(anchors: list[str], phrase_field: dict[str, Any] | None = None) -> dict[str, Any]:
    observed = _clean_list(anchors)
    content = content_anchors(observed)
    required_slots = ["subject", "answer_content"] if content else []
    frame = {
        "schema_version": "anchorworks_attention_frame@2",
        "frame_type": _frame_type(observed),
        "observed_anchors": observed,
        "content_anchors": content,
        "required_slots": required_slots,
        "role_by_anchor": {anchor: "content_anchor" for anchor in content},
        "role_trace": [{"anchor": anchor, "role": "content_anchor"} for anchor in content],
        "authority": "runtime_attention_shape",
        "observed_data_truth": bool(observed),
        "world_truth_claim": False,
        "world_truth_promoted": False,
        "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
    }
    if isinstance(phrase_field, dict) and phrase_field:
        frame["phrase_field"] = phrase_field
    return frame


def content_anchors(anchors: list[str]) -> list[str]:
    content = [anchor for anchor in _clean_list(anchors) if not blocked_answer_anchor(anchor)]
    return content or _clean_list(anchors)


def blocked_answer_anchor(anchor: str) -> bool:
    clean = str(anchor or "").strip().casefold()
    if clean in _BLOCKED_CONTENT:
        return True
    if clean and all(ch.isdigit() for ch in clean):
        return True
    if len(clean) == 1 and not clean.isalnum():
        return True
    if clean.startswith("<") or clean.endswith(">") or "xml" in clean:
        return True
    return False


def retrieve_from_count_index(count_index: dict[str, Any], anchor: str, limit: int = 25) -> dict[str, Any]:
    surface = str(anchor or "").strip().casefold()
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
            clean_neighbor = str(neighbor).strip().casefold()
            total_by_neighbor[clean_neighbor] += count
            by_offset.setdefault(str(offset), Counter())[clean_neighbor] += count
    neighbors = [
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
        "neighbors": neighbors,
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


def _candidate_seed(anchor: str, frame: dict[str, Any]) -> dict[str, Any]:
    return {
        "anchor": anchor,
        "score": 0.0,
        "selection_score": 0.0,
        "raw_observations": 0,
        "supporting_context": set(),
        "support_offsets": set(),
        "cloud_support": {"question": set(), "rear": set(), "answer": set(), "forward": set()},
        "score_parts": {},
        "penalties": {},
        "role_fit": {"score": 0.0, "matched_roles": [], "supporting_anchors": []},
        "source_support": {"kind": "native_symbol_counts", "evidence_required_for_claim": True},
        "answer_health": {"status": "supported", "reason": "candidate_has_observed_symbolic_support"},
        "attention_math": attention_math_contract(),
        "frame_type": frame.get("frame_type", "open_context"),
        "why_chosen": [],
    }


def _finalize_candidate(row: dict[str, Any], frame: dict[str, Any]) -> dict[str, Any]:
    support = sorted(row["supporting_context"])
    offsets = sorted(row["support_offsets"], key=offset_sort_key)
    breadth_bonus = len(support) * 2.0
    final_score = round(float(row["selection_score"]) + breadth_bonus, 6)
    return {
        **row,
        "score": final_score,
        "selection_score": final_score,
        "supporting_context": support,
        "support_offsets": offsets,
        "cloud_support": {key: sorted(value) for key, value in row["cloud_support"].items()},
        "score_parts": {
            "symbolic_weight": round(float(row["selection_score"]), 6),
            "support_breadth_bonus": breadth_bonus,
        },
        "role_fit": _role_fit(frame, support),
        "why_chosen": [
            "observed_in_native_count_neighborhood",
            "passed_attention_gate",
            "ranked_by_weight_and_context_breadth",
        ],
    }


def _future_health(
    count_index: dict[str, Any],
    anchor: str,
    *,
    blocked: set[str],
    lookahead_k: int,
    min_future_content: int,
    max_future_glue_ratio: float,
    max_future_null_ratio: float,
) -> dict[str, Any]:
    retrieved = retrieve_from_count_index(count_index, anchor, limit=max(lookahead_k * 4, 8))
    total = 0
    glue = 0
    content: Counter[str] = Counter()
    for rows in (retrieved.get("offsets") or {}).values():
        for row in rows:
            neighbor = str(row.get("anchor") or "").strip().casefold()
            observations = int(row.get("observations", 0) or 0)
            if observations <= 0:
                continue
            total += observations
            if blocked_answer_anchor(neighbor) or neighbor in blocked:
                glue += observations
                continue
            content[neighbor] += observations
    if total <= 0:
        return {
            "future_cloud": [],
            "future_content_count": 0,
            "future_glue_ratio": 1.0,
            "future_null_ratio": 1.0,
            "lookahead_score": -1.0,
            "pattern_health": "anomalous",
            "rejected_reason": "future_cloud_empty",
        }
    future = [anchor_name for anchor_name, _count in content.most_common(lookahead_k)]
    glue_ratio = glue / max(1, total)
    null_ratio = 0.0 if future else 1.0
    healthy = len(future) >= min_future_content and glue_ratio <= max_future_glue_ratio and null_ratio <= max_future_null_ratio
    return {
        "future_cloud": future,
        "future_content_count": len(future),
        "future_glue_ratio": round(glue_ratio, 6),
        "future_null_ratio": round(null_ratio, 6),
        "lookahead_score": round((len(future) / max(1, lookahead_k)) - glue_ratio - null_ratio, 6),
        "pattern_health": "healthy" if healthy else "anomalous",
        "rejected_reason": "" if healthy else "future_content_below_min",
    }


def _role_fit(frame: dict[str, Any], support: list[str]) -> dict[str, Any]:
    role_by_anchor = frame.get("role_by_anchor") if isinstance(frame.get("role_by_anchor"), dict) else {}
    matched: list[str] = []
    supporting: list[str] = []
    for anchor in support:
        role = str(role_by_anchor.get(anchor) or "")
        if role and role not in matched:
            matched.append(role)
            supporting.append(anchor)
    return {"score": float(len(matched)), "matched_roles": matched, "supporting_anchors": supporting}


def _candidate_gate_reason(anchor: str, blocked: set[str]) -> str:
    clean = str(anchor or "").strip().casefold()
    if not clean:
        return "empty_anchor"
    if clean in blocked:
        return "query_echo"
    if blocked_answer_anchor(clean):
        return "glue_or_noncontent"
    if clean in _METADATA_OR_SECTION_LABELS:
        return "metadata_or_section_label"
    if clean in _LOW_SIGNAL_GENERAL_TERMS:
        return "low_signal_general_term"
    if not _ATTENTION_ANCHOR_PATTERN.match(clean):
        return "regex_attention_pollution"
    return ""


def _verify_attention_payload(attention: dict[str, Any]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    if attention.get("schema_version") != ATTENTION_CONTRACT:
        failures.append("wrong_attention_schema")
    if bool(attention.get("world_truth_claim")):
        failures.append("world_truth_claim_not_allowed")
    if bool(attention.get("world_truth_promoted")):
        failures.append("world_truth_promotion_not_allowed")
    if attention.get("admission_status") == "admitted" and not attention.get("admitted_blocks"):
        failures.append("admitted_without_blocks")
    if attention.get("admission_status") == "refused" and attention.get("focus_candidates"):
        failures.append("refused_with_focus_candidates")
    writes = attention.get("writes_allowed") if isinstance(attention.get("writes_allowed"), dict) else {}
    for key in ("maps", "counts", "lifetime", "lexicon"):
        if bool(writes.get(key)):
            failures.append(f"write_not_allowed:{key}")
    return not failures, failures


def _renderer_phrase(terms: list[str], limit: int = 12, *, allow_list_style: bool = False) -> str:
    out: list[str] = []
    for term in terms:
        clean = str(term or "").strip().casefold()
        if not clean:
            continue
        if len(clean) == 1 and not clean.isalnum():
            continue
        if all(ch.isdigit() for ch in clean):
            continue
        out.append(clean)
        if len(out) >= limit:
            break
    if allow_list_style:
        return ", ".join(out)
    return " ".join(out)


def _renderer_terms_are_phrase_like(terms: list[str], focus_anchors: list[str]) -> bool:
    clean_terms = _clean_list(terms)
    if not clean_terms:
        return False
    meaningful_terms = [
        term for term in clean_terms
        if not (len(term) == 1 and not term.isalnum()) and not all(ch.isdigit() for ch in term)
    ]
    if any(term in _METADATA_OR_SECTION_LABELS for term in meaningful_terms[:8]):
        return False
    if len([term for term in meaningful_terms[:10] if term in _LOW_SIGNAL_GENERAL_TERMS]) >= 3:
        return False
    focus = set(_clean_list(focus_anchors))
    if focus and not (focus & set(clean_terms)):
        return False
    content_terms = [term for term in meaningful_terms if not blocked_answer_anchor(term)]
    return len(content_terms) >= 2


def _citation_from_block(block: dict[str, Any]) -> dict[str, Any]:
    return {
        "doc_id": str(block.get("doc_id") or ""),
        "source_file": str(block.get("source_file") or ""),
        "block_id": int(block.get("block_id", 0) or 0),
        "document_line_start": int(block.get("document_line_start", 0) or 0),
        "document_line_end": int(block.get("document_line_end", 0) or 0),
        "rag_copy": str(block.get("rag_copy") or ""),
        "citation_type": "observed_data_coordinate",
    }


def _coordinate_phrase(citations: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for row in citations[:3]:
        doc_id = str(row.get("doc_id") or "unknown_doc")
        block_id = int(row.get("block_id", 0) or 0)
        start = int(row.get("document_line_start", 0) or 0)
        end = int(row.get("document_line_end", 0) or 0)
        parts.append(f"{doc_id} block {block_id} lines {start}-{end}")
    return "; ".join(parts)


def _load_user_n0_regex(path_value: Any) -> dict[str, Any]:
    empty = {
        "path": "",
        "loaded": False,
        "deny_focus_patterns": [],
        "admit_focus_patterns": [],
        "boost_focus_patterns": [],
        "normalize_focus_patterns": [],
    }
    if not path_value:
        return empty
    path = Path(path_value)
    if not path.exists():
        return {**empty, "path": str(path)}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {**empty, "path": str(path)}
    return {
        "path": str(path),
        "loaded": True,
        "schema_version": str(payload.get("schema_version") or "anchorworks_n0_attention_regex@1"),
        "deny_focus_patterns": _regex_rows(payload.get("deny_focus_patterns")),
        "admit_focus_patterns": _regex_rows(payload.get("admit_focus_patterns")),
        "boost_focus_patterns": _regex_rows(payload.get("boost_focus_patterns")),
        "normalize_focus_patterns": _regex_rows(payload.get("normalize_focus_patterns")),
    }


def _regex_rows(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return rows
    for row in value:
        if not isinstance(row, dict):
            continue
        pattern = str(row.get("pattern") or "").strip()
        if not pattern:
            continue
        rows.append(dict(row, pattern=pattern))
    return rows


def _user_regex_match(anchor: str, rows: Any) -> dict[str, Any]:
    clean = str(anchor or "").strip().casefold()
    if not isinstance(rows, list):
        return {}
    for row in rows:
        try:
            if re.search(str(row.get("pattern") or ""), clean):
                return row
        except re.error:
            continue
    return {}


def _apply_user_normalize(anchor: str, user_regex: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    clean = str(anchor or "").strip().casefold()
    for row in user_regex.get("normalize_focus_patterns") or []:
        try:
            pattern = str(row.get("pattern") or "")
            if re.search(pattern, clean):
                replacement = str(row.get("replace") or clean).strip().casefold()
                if replacement:
                    return replacement, {
                        "pattern": pattern,
                        "replace": replacement,
                        "reason": str(row.get("reason") or "user_normalized_focus_anchor"),
                    }
        except re.error:
            continue
    return clean, {}


def _user_regex_report(user_regex: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": str(user_regex.get("schema_version") or "anchorworks_n0_attention_regex@1"),
        "path": str(user_regex.get("path") or ""),
        "loaded": bool(user_regex.get("loaded")),
        "mode": "additive_not_takeover",
        "rules": {
            "deny_count": len(user_regex.get("deny_focus_patterns") or []),
            "admit_count": len(user_regex.get("admit_focus_patterns") or []),
            "boost_count": len(user_regex.get("boost_focus_patterns") or []),
            "normalize_count": len(user_regex.get("normalize_focus_patterns") or []),
        },
        "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
    }


def _frame_type(anchors: list[str]) -> str:
    if not anchors:
        return "empty"
    if anchors[0] in {"what", "why", "when", "where", "which", "who", "how"} or "?" in anchors:
        return "question"
    return "open_context"


def _clean_list(values: list[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = str(value or "").strip().casefold()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        out.append(clean)
    return out


def _dedupe_coordinates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, int, int, int]] = set()
    for row in rows:
        key = (
            str(row.get("doc_id") or ""),
            int(row.get("block_id", 0) or 0),
            int(row.get("document_line_start", 0) or 0),
            int(row.get("document_line_end", 0) or 0),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _dedupe_rejections(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (str(row.get("anchor") or ""), str(row.get("reason") or ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out
