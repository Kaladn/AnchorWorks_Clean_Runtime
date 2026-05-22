from __future__ import annotations

from typing import Any

from .cloud_scoring import score_candidate_cloud
from .rules import apply_rule_gates


def walk_candidates(
    candidates: list[dict[str, Any]],
    frame: dict[str, Any],
    *,
    max_steps: int = 6,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    active_context = _seed_context(frame)
    pending = list(candidates)
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    inference_steps: list[dict[str, Any]] = []

    while pending and len(accepted) < max_steps:
        ranked: list[tuple[float, dict[str, Any], dict[str, Any], str, list[dict[str, Any]]]] = []
        next_pending: list[dict[str, Any]] = []
        deferred: list[tuple[dict[str, Any], dict[str, Any]]] = []
        selected: tuple[float, dict[str, Any], dict[str, Any], str, list[dict[str, Any]]] | None = None

        for candidate in pending:
            cloud_match = score_candidate_cloud(candidate)
            passed, reason, steps = apply_rule_gates(candidate, frame)
            inference_steps.extend(steps)
            if not passed:
                rejected.append(_shape_candidate(candidate, cloud_match, "rejected", reason))
                continue

            context_fit = _context_fit(candidate, active_context)
            if context_fit <= 0.0:
                deferred.append((candidate, cloud_match))
                continue

            walk_score = _walk_score(candidate, cloud_match, context_fit)
            ranked.append((walk_score, candidate, cloud_match, "candidate_passed_active_cloud_walk", steps))

        if ranked:
            ranked.sort(key=lambda row: row[0], reverse=True)
            selected = ranked[0]

        if selected is None:
            for candidate, cloud_match in deferred:
                rejected.append(_shape_candidate(candidate, cloud_match, "rejected", "no_active_cloud_fit"))
                inference_steps.append(_walk_step(candidate, "reject", "no_active_cloud_fit", active_context))
            break

        selected_score, selected_candidate, selected_cloud, reason, _steps = selected
        shaped = _shape_candidate(selected_candidate, selected_cloud, "accepted", reason)
        shaped["walk_score"] = round(selected_score, 6)
        shaped["active_context_before"] = sorted(active_context)
        accepted.append(shaped)
        active_context.update(_candidate_terms(selected_candidate))
        active_context.add(str(selected_candidate.get("anchor") or selected_candidate.get("symbol") or "").casefold())
        inference_steps.append(_walk_step(selected_candidate, "accept", reason, active_context))

        selected_symbol = str(selected_candidate.get("symbol") or "").casefold()
        for _score, candidate, _cloud, _reason, _steps in ranked[1:]:
            if str(candidate.get("symbol") or "").casefold() != selected_symbol:
                next_pending.append(candidate)
        for candidate, _cloud_match in deferred:
            if str(candidate.get("symbol") or "").casefold() != selected_symbol:
                next_pending.append(candidate)
        pending = next_pending

    for candidate in pending:
        if not any(row["symbol"] == candidate.get("symbol") for row in accepted + rejected):
            cloud_match = score_candidate_cloud(candidate)
            rejected.append(_shape_candidate(candidate, cloud_match, "rejected", "not_selected_by_active_cloud_walk"))
            inference_steps.append(_walk_step(candidate, "reject", "not_selected_by_active_cloud_walk", active_context))

    return accepted, rejected, inference_steps


def _seed_context(frame: dict[str, Any]) -> set[str]:
    context: set[str] = set()
    subject = str(frame.get("subject") or "")
    context.update(_split_terms(subject))
    slots = frame.get("slots") if isinstance(frame.get("slots"), dict) else {}
    for value in slots.values():
        context.update(_split_terms(str(value or "")))
    return {value for value in context if value}


def _context_fit(candidate: dict[str, Any], active_context: set[str]) -> float:
    terms = _candidate_terms(candidate)
    if not terms or not active_context:
        return 0.0
    overlap = terms & active_context
    return len(overlap) / max(1, min(len(terms), len(active_context)))


def _candidate_terms(candidate: dict[str, Any]) -> set[str]:
    evidence = candidate.get("evidence") if isinstance(candidate.get("evidence"), dict) else {}
    terms = {
        str(value or "").strip().casefold()
        for value in (evidence.get("supporting_context") or [])
        if str(value or "").strip()
    }
    anchor = str(candidate.get("anchor") or "").strip().casefold()
    if anchor:
        terms.add(anchor)
    return terms


def _walk_score(candidate: dict[str, Any], cloud_match: dict[str, Any], context_fit: float) -> float:
    support_score = float(candidate.get("support_score") or 0.0)
    cloud_score = float(cloud_match.get("final_cloud_score") or 0.0)
    rank = max(1, int(candidate.get("candidate_rank") or 1))
    rank_pressure = 1.0 / rank
    return support_score * 0.40 + context_fit * 0.35 + cloud_score * 0.20 + rank_pressure * 0.05


def _shape_candidate(candidate: dict[str, Any], cloud_match: dict[str, Any], status: str, reason: str) -> dict[str, Any]:
    return {
        "symbol": candidate["symbol"],
        "anchor": candidate["anchor"],
        "lane": candidate["lane"],
        "role": candidate["role"],
        "support_score": candidate["support_score"],
        "candidate_rank": candidate["candidate_rank"],
        "status": status,
        "reason": reason,
        "evidence": candidate.get("evidence") or {},
        "cloud_match": cloud_match,
    }


def _walk_step(candidate: dict[str, Any], decision: str, reason: str, active_context: set[str]) -> dict[str, Any]:
    return {
        "rule_id": "R_ACTIVE_CLOUD_WALK_SELECT",
        "inputs_used": [str(candidate.get("symbol") or "")],
        "decision": decision,
        "reason": reason,
        "evidence_refs": [],
        "active_context": sorted(active_context),
    }


def _split_terms(text: str) -> set[str]:
    return {
        part.strip().casefold()
        for part in str(text or "").replace("?", " ").replace(".", " ").split()
        if part.strip()
    }
