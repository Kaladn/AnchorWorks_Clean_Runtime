from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any


MASS_RE = re.compile(r"(?P<value>[+-]?\d+(?:\.\d+)?)\s*(?:kg|kilogram|kilograms)\b", re.IGNORECASE)
ACCEL_RE = re.compile(
    r"(?P<value>[+-]?\d+(?:\.\d+)?)\s*(?:m\s*/\s*s(?:\^?2|²)|meters?\s+per\s+second\s+squared)",
    re.IGNORECASE,
)
FORCE_TERMS = {"force", "net force", "newton", "newtons"}
ACCEL_TERMS = {"accelerating", "acceleration", "accelerate"}
MASS_TERMS = {"kg", "kilogram", "kilograms", "mass"}


def solve_formula_question(text: str, query_anchors: list[str] | None = None) -> dict[str, Any] | None:
    """Solve narrow deterministic formula frames before retrieval/count walking."""

    query = str(text or "").strip()
    if not query:
        return None
    lower = query.casefold()
    anchors = {str(anchor or "").strip().casefold() for anchor in (query_anchors or []) if str(anchor or "").strip()}
    if not _looks_like_newton_second_law_force_question(lower, anchors):
        return None

    mass_match = MASS_RE.search(query)
    accel_match = ACCEL_RE.search(query)
    if not mass_match or not accel_match:
        return None
    try:
        mass = Decimal(mass_match.group("value"))
        acceleration = Decimal(accel_match.group("value"))
    except (InvalidOperation, AttributeError):
        return None
    force = mass * acceleration
    force_text = _format_decimal(force)
    mass_text = _format_decimal(mass)
    acceleration_text = _format_decimal(acceleration)
    speech = (
        f"The net force is {force_text} N. Using Newton's second law, F = ma, "
        f"so F = {mass_text} kg x {acceleration_text} m/s^2 = {force_text} N."
    )
    return {
        "schema_version": "aw_formula_answer@1",
        "ok": True,
        "activity": "formula_solve",
        "frame": {
            "schema_version": "aw_inference_frame@1",
            "activity": "formula_solve",
            "frame_type": "physics_formula_newton_second_law",
            "subject": "net force",
            "required_slots": ["mass", "acceleration", "formula", "result"],
            "fact_authority": False,
        },
        "speech": speech,
        "response": speech,
        "formula": "F = ma",
        "given": {
            "mass_kg": float(mass),
            "acceleration_m_per_s2": float(acceleration),
        },
        "result": {
            "force_newtons": float(force),
            "display": f"{force_text} N",
        },
        "inference_plan": {
            "schema_version": "aw_inference_answer_plan@1",
            "activity": "formula_solve",
            "render_allowed": True,
            "render_shape": "formula_solution",
            "fact_authority": False,
            "fact_answer_authority": False,
            "stop_reason": "formula_frame_solved",
            "accepted_candidates": [
                {"symbol": "force", "role": "solve_for", "status": "accepted", "reason": "question_asks_net_force"},
                {"symbol": "mass", "role": "given", "status": "accepted", "reason": "mass_value_with_kg_present"},
                {"symbol": "acceleration", "role": "given", "status": "accepted", "reason": "acceleration_value_with_m_per_s2_present"},
                {"symbol": "newton_second_law", "role": "formula", "status": "accepted", "reason": "mass_acceleration_force_frame"},
            ],
            "rejected_candidates": [],
            "inference_steps": [
                {
                    "rule_id": "R_FORMULA_FRAME_BEFORE_EVIDENCE",
                    "inputs_used": sorted(anchors) or [],
                    "decision": "route_formula_solve",
                    "reason": "numeric_physics_units_and_force_question_detected",
                    "evidence_refs": [],
                },
                {
                    "rule_id": "R_NEWTON_SECOND_LAW",
                    "inputs_used": ["mass_kg", "acceleration_m_per_s2"],
                    "decision": "solve",
                    "reason": "F_equals_m_times_a",
                    "evidence_refs": [],
                },
            ],
            "contract": {
                "formula_lane_before_evidence_lane": True,
                "counts_not_used_as_formula_authority": True,
                "documents_not_selected_by_units_only": True,
                "fact_authority": False,
            },
        },
        "evidence_mode": "formula",
        "engine": "aw_inference_formula_solver",
        "citations": [],
        "evidence": [],
        "contract": {
            "formula_lane_before_evidence_lane": True,
            "counts_used": False,
            "documents_used": False,
            "memory_writes": False,
        },
    }


def _looks_like_newton_second_law_force_question(lower: str, anchors: set[str]) -> bool:
    has_force = any(term in lower for term in FORCE_TERMS) or bool(anchors & {"force", "newton", "newtons"})
    has_mass = any(term in lower for term in MASS_TERMS) or bool(anchors & {"mass", "kg", "kilogram", "kilograms"})
    has_accel = any(term in lower for term in ACCEL_TERMS) or bool(anchors & {"accelerating", "acceleration", "accelerate"})
    has_question_shape = "what" in anchors or "?" in lower or "acting on" in lower
    return has_force and has_mass and has_accel and has_question_shape


def _format_decimal(value: Decimal) -> str:
    normalized = value.normalize()
    text = format(normalized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"
