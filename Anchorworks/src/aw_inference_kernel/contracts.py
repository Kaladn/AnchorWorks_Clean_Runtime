from __future__ import annotations

from typing import Any, TypedDict


class InferenceInput(TypedDict, total=False):
    trace_id: str
    question_text: str
    user_text: str
    query_symbols: list[str]
    query_anchors: list[str]
    recognized_anchors: list[str]
    missing_anchors: list[str]
    answer_assembly: dict[str, Any]
    source_facts: list[dict[str, Any]]
    count_candidates: list[dict[str, Any]]
    local_overlay_candidates: list[dict[str, Any]]
    mode: str
    active_context: dict[str, Any]
    available_lanes: list[str]
    constraints: dict[str, Any]


class Frame(TypedDict, total=False):
    schema_version: str
    question_type: str
    frame_type: str
    activity: str
    activity_reason: str
    subject: str
    slots: dict[str, Any]
    required_slots: list[str]
    constraints: list[str]
    frame_support: list[dict[str, Any]]
    fact_authority: bool
    fact_answer_authority: bool


class Candidate(TypedDict, total=False):
    symbol: str
    anchor: str
    lane: str
    role: str
    evidence: dict[str, Any]
    support_score: float
    status: str
    reason: str
    candidate_rank: int


class InferenceStep(TypedDict, total=False):
    rule_id: str
    inputs_used: list[str]
    decision: str
    reason: str
    evidence_refs: list[dict[str, Any]]


class AnswerPlan(TypedDict, total=False):
    schema_version: str
    activity: str
    frame: Frame
    direct_answer: str
    supporting_facts: list[str]
    accepted_candidates: list[Candidate]
    rejected_candidates: list[Candidate]
    missing_slots: list[str]
    render_shape: str
    confidence: float
    inference_steps: list[InferenceStep]
    fact_authority: bool
    fact_answer_authority: bool
    render_allowed: bool
    stop_reason: str
