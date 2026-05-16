from __future__ import annotations

from typing import Any

from .activity_chooser import choose_activity


QUESTION_DIRECTORS = {"what", "why", "how", "when", "where", "who", "which", "does", "do", "is", "are"}
SUBJECT_GLUE = {
    "a", "an", "the", "about", "of", "to", "for", "from", "in", "on", "with", "and", "or",
    "is", "are", "was", "were", "be", "being", "been", "do", "does", "did", "why", "what", "how",
    "who", "when", "where", "which", "?",
}
FRAME_REQUIRED_SLOTS = {
    "causal_explanation": ["purpose", "mechanism", "consequence"],
    "process_explanation": ["steps", "mechanism"],
    "definition": ["category", "defining_property"],
    "implication_check": ["claim", "evidence_for", "evidence_against"],
    "comparison": ["left", "right", "basis"],
    "who_entity": ["entity", "identity_support"],
}


def build_frame(user_text: str, query_anchors: list[str], *, mode: str = "") -> dict[str, Any]:
    anchors = _clean(query_anchors)
    frame_type = _frame_type(anchors)
    activity = choose_activity(anchors, mode=mode)
    subject = _subject(anchors)
    slots = {"subject": subject} if subject else {}
    return {
        "schema_version": "aw_inference_frame@1",
        "activity": activity["activity"],
        "activity_reason": activity["reason"],
        "question_type": frame_type,
        "frame_type": frame_type,
        "subject": subject,
        "slots": slots,
        "required_slots": FRAME_REQUIRED_SLOTS.get(frame_type, ["support"]),
        "constraints": [
            "frame_rules_may_fire_from_input_shape",
            "fact_rules_require_evidence",
            "renderer_speaks_answer_plan_only",
        ],
        "frame_support": [{
            "pattern": _leading_pattern(anchors),
            "confidence": 0.75 if anchors else 0.0,
            "fact_authority": False,
        }],
        "fact_authority": False,
        "fact_answer_authority": False,
    }


def _frame_type(anchors: list[str]) -> str:
    if not anchors:
        return "open_educational_frame"
    if anchors[0] == "why":
        return "causal_explanation"
    if anchors[0] == "how":
        return "process_explanation"
    if anchors[0] == "who":
        return "who_entity"
    if anchors[0] in {"what", "which"}:
        return "definition"
    if anchors[0] in {"does", "do", "is", "are"}:
        return "implication_check"
    if "compare" in anchors:
        return "comparison"
    return "open_educational_frame"


def _subject(anchors: list[str]) -> str:
    kept = [anchor for anchor in anchors if anchor not in SUBJECT_GLUE and not any(char.isdigit() for char in anchor)]
    return " ".join(kept[:8])


def _leading_pattern(anchors: list[str]) -> str:
    if not anchors:
        return "empty"
    return anchors[0] + "_question_shape"


def _clean(values: list[str]) -> list[str]:
    return [str(value or "").strip().casefold() for value in values if str(value or "").strip()]
