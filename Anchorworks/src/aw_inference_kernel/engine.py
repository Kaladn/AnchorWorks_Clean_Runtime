from __future__ import annotations

from typing import Any

from .answer_plan import build_answer_plan as _build_answer_plan
from .candidate_collector import collect_candidates
from .cloud_scoring import score_candidate_cloud
from .frame_builder import build_frame
from .rules import apply_rule_gates


def run_inference(
    user_text: str,
    query_anchors: list[str],
    answer_assembly: dict[str, Any],
    *,
    mode: str = "",
) -> dict[str, Any]:
    frame = build_frame(user_text, query_anchors, mode=mode)
    candidates = collect_candidates(answer_assembly)
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    inference_steps: list[dict[str, Any]] = [
        {
            "rule_id": "R_FRAME_FROM_INPUT_SHAPE",
            "inputs_used": list(query_anchors),
            "decision": "build_frame",
            "reason": "frame_rules_may_fire_from_input_shape",
            "evidence_refs": [],
        }
    ]

    for candidate in candidates:
        cloud_match = score_candidate_cloud(candidate)
        passed, reason, steps = apply_rule_gates(candidate, frame)
        inference_steps.extend(steps)
        shaped = {
            "symbol": candidate["symbol"],
            "anchor": candidate["anchor"],
            "lane": candidate["lane"],
            "role": candidate["role"],
            "support_score": candidate["support_score"],
            "candidate_rank": candidate["candidate_rank"],
            "status": "accepted" if passed else "rejected",
            "reason": reason,
            "evidence": candidate.get("evidence") or {},
            "cloud_match": cloud_match,
        }
        if passed:
            accepted.append(shaped)
        else:
            rejected.append(shaped)

    return _build_answer_plan(
        frame=frame,
        accepted_candidates=accepted,
        rejected_candidates=rejected,
        inference_steps=inference_steps,
    )


def build_answer_plan(*args: Any, **kwargs: Any) -> dict[str, Any]:
    if args or "user_text" in kwargs:
        return run_inference(*args, **kwargs)
    return _build_answer_plan(**kwargs)
