from __future__ import annotations

from typing import Any, TypedDict


class InferenceInput(TypedDict, total=False):
    user_text: str
    query_anchors: list[str]
    answer_assembly: dict[str, Any]
    mode: str
    active_context: dict[str, Any]
    available_lanes: list[str]


class Frame(TypedDict, total=False):
    question_type: str
    frame_type: str
    activity: str
    subject: str
    required_slots: list[str]
    constraints: list[str]


class Candidate(TypedDict, total=False):
    symbol: str
    lane: str
    role: str
    evidence: dict[str, Any]
    support_score: float
    status: str
    reason: str


class InferenceStep(TypedDict, total=False):
    rule_id: str
    inputs_used: list[str]
    decision: str
    reason: str
    evidence_refs: list[dict[str, Any]]


class AnswerPlan(TypedDict, total=False):
    schema_version: str
    direct_answer: str
    supporting_facts: list[str]
    accepted_candidates: list[Candidate]
    rejected_candidates: list[Candidate]
    missing_slots: list[str]
    render_shape: str
    confidence: float
    frame: Frame
    inference_steps: list[InferenceStep]
    fact_answer_authority: bool
