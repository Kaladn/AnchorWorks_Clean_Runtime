from __future__ import annotations

from typing import Any

from .cloud_scoring import build_support_metrics, build_uncertainty_notes


def build_answer_plan(
    *,
    frame: dict[str, Any],
    accepted_candidates: list[dict[str, Any]],
    rejected_candidates: list[dict[str, Any]],
    inference_steps: list[dict[str, Any]],
) -> dict[str, Any]:
    missing_slots = _missing_slots(frame, accepted_candidates)
    confidence = _confidence(accepted_candidates, rejected_candidates, missing_slots)
    direct_answer = _direct_answer(frame, accepted_candidates)
    render_allowed = bool(accepted_candidates and not missing_slots)
    support_metrics = build_support_metrics(accepted_candidates, rejected_candidates)
    uncertainty_notes = build_uncertainty_notes(accepted_candidates, rejected_candidates)
    return {
        "schema_version": "aw_inference_answer_plan@1",
        "activity": str(frame.get("activity") or ""),
        "frame": frame,
        "direct_answer": direct_answer,
        "supporting_facts": [row["symbol"] for row in accepted_candidates],
        "accepted_candidates": accepted_candidates,
        "rejected_candidates": rejected_candidates,
        "missing_slots": missing_slots,
        "render_shape": _render_shape(frame, accepted_candidates),
        "confidence": confidence,
        "support_metrics": support_metrics,
        "uncertainty_notes": uncertainty_notes,
        "inference_steps": inference_steps,
        "fact_authority": False,
        "fact_answer_authority": False,
        "render_allowed": render_allowed,
        "stop_reason": "plan_complete" if render_allowed else "insufficient_admitted_support",
        "contract": {
            "search_finds": True,
            "counts_weigh": True,
            "inference_admits": True,
            "renderer_speaks": True,
            "facts_require_evidence": True,
            "no_raw_topk_fallback": True,
            "topk_walked": True,
        },
    }


def _missing_slots(frame: dict[str, Any], accepted_candidates: list[dict[str, Any]]) -> list[str]:
    if not accepted_candidates:
        return list(frame.get("required_slots") or ["support"])
    return []


def _confidence(
    accepted_candidates: list[dict[str, Any]],
    rejected_candidates: list[dict[str, Any]],
    missing_slots: list[str],
) -> float:
    if not accepted_candidates:
        return 0.0
    score = sum(float(row.get("support_score") or 0.0) for row in accepted_candidates) / max(1, len(accepted_candidates))
    score = min(0.92, 0.55 + score * 0.3)
    if rejected_candidates:
        score -= min(0.12, len(rejected_candidates) * 0.03)
    if missing_slots:
        score -= 0.2
    return round(max(0.0, score), 3)


def _direct_answer(frame: dict[str, Any], accepted_candidates: list[dict[str, Any]]) -> str:
    if not accepted_candidates:
        return ""
    subject = str(frame.get("subject") or "").strip()
    anchors = [row["symbol"] for row in accepted_candidates[:6]]
    if subject:
        return f"{subject} is supported by " + ", ".join(anchors) + "."
    return "The supported path is " + ", ".join(anchors) + "."


def _render_shape(frame: dict[str, Any], accepted_candidates: list[dict[str, Any]]) -> str:
    if not accepted_candidates:
        return "insufficient_support"
    if frame.get("frame_type") in {"causal_explanation", "process_explanation", "implication_check", "definition", "who_entity"}:
        return "short_explanation"
    return "path_summary"
