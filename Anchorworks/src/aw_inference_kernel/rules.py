from __future__ import annotations

from typing import Any


PHYSICS_FRAME_TERMS = {
    "acceleration",
    "accelerate",
    "energy",
    "force",
    "forces",
    "gravity",
    "inertia",
    "law",
    "laws",
    "mass",
    "motion",
    "newton",
    "object",
    "physics",
    "velocity",
}


def apply_rule_gates(candidate: dict[str, Any], frame: dict[str, Any]) -> tuple[bool, str, list[dict[str, Any]]]:
    evidence = candidate.get("evidence") if isinstance(candidate.get("evidence"), dict) else {}
    steps: list[dict[str, Any]] = []

    health = evidence.get("answer_health") if isinstance(evidence.get("answer_health"), dict) else {}
    if health and str(health.get("status") or "") not in {"supported", "accepted"}:
        reason = "unsupported_answer_health"
        steps.append(_step("R_FACT_SUPPORT", candidate, "reject", reason))
        return False, reason, steps

    coherence = evidence.get("query_field_coherence") if isinstance(evidence.get("query_field_coherence"), dict) else {}
    if coherence and not bool(coherence.get("coherent", True)):
        reason = "query_field_mismatch"
        steps.append(_step("R_QUERY_FIELD", candidate, "reject", reason))
        return False, reason, steps

    rejected_reason = str(evidence.get("rejected_reason") or "").strip()
    if rejected_reason:
        steps.append(_step("R_PREVIOUS_REJECTION", candidate, "reject", rejected_reason))
        return False, rejected_reason, steps

    if str(evidence.get("pattern_health") or "healthy") == "anomalous":
        reason = "anomalous_future_shape"
        steps.append(_step("R_LOOKAHEAD_HEALTH", candidate, "reject", reason))
        return False, reason, steps

    domain_reason = _domain_gate_reason(candidate, frame, evidence)
    if domain_reason:
        steps.append(_step("R_FRAME_DOMAIN", candidate, "reject", domain_reason))
        return False, domain_reason, steps

    if frame.get("frame_type") in {"causal_explanation", "process_explanation", "implication_check", "definition", "who_entity"}:
        supporting_context = {
            str(value or "").strip().casefold()
            for value in (evidence.get("supporting_context") or [])
            if str(value or "").strip()
        }
        if not supporting_context:
            reason = "no_context_support"
            steps.append(_step("R_FACT_SUPPORT", candidate, "reject", reason))
            return False, reason, steps

    steps.append(_step("R_ADMIT_SUPPORTED_CANDIDATE", candidate, "accept", "candidate_passed_inference_gates"))
    return True, "candidate_passed_inference_gates", steps


def _domain_gate_reason(candidate: dict[str, Any], frame: dict[str, Any], evidence: dict[str, Any]) -> str:
    subject_terms = set(_split_terms(str(frame.get("subject") or "")))
    if not (subject_terms & PHYSICS_FRAME_TERMS):
        return ""
    anchor = str(candidate.get("anchor") or candidate.get("symbol") or "").strip().casefold()
    if not anchor or anchor in PHYSICS_FRAME_TERMS:
        return ""
    supporting_context = {
        str(value or "").strip().casefold()
        for value in (evidence.get("supporting_context") or [])
        if str(value or "").strip()
    }
    if len(supporting_context & subject_terms) >= 2:
        return ""
    return "off_frame_domain"


def _split_terms(text: str) -> list[str]:
    return [part for part in str(text or "").replace("?", " ").replace(".", " ").split() if part]


def _step(rule_id: str, candidate: dict[str, Any], decision: str, reason: str) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "inputs_used": [str(candidate.get("symbol") or "")],
        "decision": decision,
        "reason": reason,
        "evidence_refs": [],
    }
