from __future__ import annotations

from typing import Any


CLOUD_SCORE_WEIGHTS = {
    "question_fit": 0.30,
    "rear_fit": 0.25,
    "answer_fit": 0.25,
    "forward_fit": 0.15,
    "source_support": 0.05,
}


def score_candidate_cloud(candidate: dict[str, Any]) -> dict[str, Any]:
    evidence = candidate.get("evidence") if isinstance(candidate.get("evidence"), dict) else {}
    score_parts = evidence.get("score_parts") if isinstance(evidence.get("score_parts"), dict) else {}
    local_score = 0.0
    for key, weight in CLOUD_SCORE_WEIGHTS.items():
        local_score += float(score_parts.get(key, 0.0) or 0.0) * weight

    lookahead = max(0.0, float(evidence.get("lookahead_score", 0.0) or 0.0))
    layered_score = min(1.0, lookahead)

    support_offsets = [str(value or "") for value in (evidence.get("support_offsets") or []) if str(value or "")]
    directional_score = _directional_score(support_offsets)
    context_count = len({str(value or "").casefold() for value in (evidence.get("supporting_context") or []) if str(value or "")})
    support_strength = min(1.0, (context_count / 3.0) + float(score_parts.get("source_support", 0.0) or 0.0) * 0.25)
    final_score = (
        local_score * 0.45
        + layered_score * 0.20
        + directional_score * 0.20
        + support_strength * 0.15
    )
    return {
        "schema_version": "anchorworks_cloud_match_score@1",
        "local_cloud_score": round(local_score, 6),
        "layered_cloud_score": round(layered_score, 6),
        "directional_score": round(directional_score, 6),
        "support_strength": round(support_strength, 6),
        "final_cloud_score": round(final_score, 6),
        "selected_from": "translated_clearbox_cloud_scoring_shape",
        "fact_authority": False,
    }


def build_support_metrics(accepted: list[dict[str, Any]], rejected: list[dict[str, Any]]) -> dict[str, Any]:
    admitted_scores = [
        float((row.get("cloud_match") or {}).get("final_cloud_score", 0.0) or 0.0)
        for row in accepted
        if isinstance(row.get("cloud_match"), dict)
    ]
    rejected_reasons: dict[str, int] = {}
    for row in rejected:
        reason = str(row.get("reason") or "unknown")
        rejected_reasons[reason] = rejected_reasons.get(reason, 0) + 1
    return {
        "schema_version": "anchorworks_answer_support_metrics@1",
        "admitted_count": len(accepted),
        "rejected_count": len(rejected),
        "mean_cloud_score": round(sum(admitted_scores) / max(1, len(admitted_scores)), 6) if admitted_scores else 0.0,
        "rejected_reasons": rejected_reasons,
        "fact_authority": False,
    }


def build_uncertainty_notes(accepted: list[dict[str, Any]], rejected: list[dict[str, Any]]) -> list[str]:
    notes: list[str] = []
    if not accepted:
        notes.append("no_admitted_answer_path")
    if rejected:
        notes.append("some_count_candidates_rejected_by_inference")
    weak = [
        row for row in accepted
        if float((row.get("cloud_match") or {}).get("final_cloud_score", 0.0) or 0.0) < 0.35
    ]
    if weak:
        notes.append("weak_cloud_match_support")
    return notes


def _directional_score(offsets: list[str]) -> float:
    if not offsets:
        return 0.0
    parsed: list[int] = []
    for offset in offsets:
        try:
            parsed.append(int(str(offset).replace("+", "")))
        except ValueError:
            continue
    if not parsed:
        return 0.0
    has_forward = any(value > 0 for value in parsed)
    has_backward = any(value < 0 for value in parsed)
    base = 0.5 if (has_forward or has_backward) else 0.0
    if has_forward and has_backward:
        base += 0.25
    close_bonus = min(0.25, sum(1.0 / max(1, abs(value)) for value in parsed) / max(1, len(parsed)))
    return min(1.0, base + close_bonus)
