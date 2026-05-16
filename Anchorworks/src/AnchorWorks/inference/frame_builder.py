from __future__ import annotations

from typing import Any

from ..question_frame_inducer import induce_question_frame
from .activity_chooser import choose_activity


FRAME_REQUIRED_SLOTS = {
    "causal_explanation": ["purpose", "mechanism", "consequence"],
    "process_explanation": ["steps", "mechanism"],
    "definition": ["category", "defining_property"],
    "implication_check": ["claim", "evidence_for", "evidence_against"],
    "comparison": ["left", "right", "basis"],
}


def build_frame(user_text: str, query_anchors: list[str], *, mode: str = "") -> dict[str, Any]:
    induced = induce_question_frame(user_text, active_mode=mode)
    activity = choose_activity(query_anchors, mode=mode)
    frame_type = str(induced.get("frame_type") or "open_educational_frame")
    slots = induced.get("slots") if isinstance(induced.get("slots"), dict) else {}
    subject = str(slots.get("subject") or "").strip()
    return {
        "schema_version": "anchorworks_inference_frame@1",
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
        "frame_support": induced.get("support") or [],
        "fact_answer_authority": False,
    }
