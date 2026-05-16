from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


FRAME_CONTRACT = "anchorworks_question_frame_inducer@1"
FRAME_LAW = "Frames are reusable transformations, not stored answers."


@dataclass(frozen=True)
class FramePattern:
    pattern_id: str
    frame_type: str
    activity: str
    template: str
    regex: re.Pattern[str]
    support_count: int = 0
    examples: tuple[str, ...] = ()


def induce_question_frame(
    question_text: str,
    *,
    corpus_path: str | Path | None = None,
    active_mode: str = "",
    source_lane: str = "",
) -> dict[str, Any]:
    """Infer the answer-shape requested by a live question.

    This module never provides factual answer authority. It turns the user's
    wording into a reusable frame that downstream source/count systems may use
    to build an answer.
    """

    question = _clean(question_text)
    patterns = _build_patterns(corpus_path)
    support_stats = _corpus_support(corpus_path)
    chosen = _choose_pattern(question, patterns)
    slots = _extract_slots(question, chosen)
    support = _support_rows(chosen, support_stats)
    confidence = _confidence(question, chosen, support)
    reasoning_frame = _fill_template(chosen.template, slots)
    return {
        "schema_version": FRAME_CONTRACT,
        "law": FRAME_LAW,
        "activity": chosen.activity,
        "frame_type": chosen.frame_type,
        "reasoning_frame": reasoning_frame,
        "slots": slots,
        "support": support,
        "confidence": confidence,
        "active_mode": active_mode,
        "source_lane": source_lane,
        "fact_answer_authority": False,
        "writes_allowed": {
            "maps": False,
            "counts": False,
            "lifetime": False,
            "lexicon": False,
        },
    }


def default_reasoning_frame_corpus() -> Path:
    return Path(r"D:\AnchorWorks_Data_Curation\frame_cloud_rules\frame_cloud_rules.json")


def _build_patterns(corpus_path: str | Path | None) -> list[FramePattern]:
    support = _frame_cloud_support(corpus_path)
    return [
        FramePattern(
            "why_causal",
            "causal_explanation",
            "educational_question",
            "Explain why <subject> happens and what evidence supports it.",
            re.compile(r"^why\s+(?P<subject>.+?)(?:\?)?$", re.I),
            support.get("why", 0),
            tuple(support.get("examples:why", ())),
        ),
        FramePattern(
            "how_process",
            "process_explanation",
            "educational_question",
            "Explain how <subject> works, including the main steps or mechanism.",
            re.compile(r"^how\s+(?:does|do|did|is|are|can|could|should)?\s*(?P<subject>.+?)(?:\?)?$", re.I),
            support.get("how", 0),
            tuple(support.get("examples:how", ())),
        ),
        FramePattern(
            "what_definition",
            "definition",
            "educational_question",
            "Identify what <subject> is and give the category or defining property.",
            re.compile(r"^what\s+(?:is|are|was|were)?\s*(?P<subject>.+?)(?:\?)?$", re.I),
            support.get("what", 0),
            tuple(support.get("examples:what", ())),
        ),
        FramePattern(
            "which_selection",
            "selection_check",
            "educational_question",
            "Select which statement or candidate fits <subject> and explain the basis.",
            re.compile(r"^which\s+(?P<subject>.+?)(?:\?)?$", re.I),
            support.get("which", 0),
            tuple(support.get("examples:which", ())),
        ),
        FramePattern(
            "who_identity",
            "identity",
            "educational_question",
            "Identify who <subject> refers to and why that identity fits.",
            re.compile(r"^who\s+(?:is|was)?\s*(?P<subject>.+?)(?:\?)?$", re.I),
            support.get("who", 0),
            tuple(support.get("examples:who", ())),
        ),
        FramePattern(
            "when_time",
            "time_lookup",
            "educational_question",
            "Identify when <subject> occurred or what time/date relation is requested.",
            re.compile(r"^when\s+(?P<subject>.+?)(?:\?)?$", re.I),
            support.get("when", 0),
            tuple(support.get("examples:when", ())),
        ),
        FramePattern(
            "where_place",
            "place_lookup",
            "educational_question",
            "Identify where <subject> is located or where the event belongs.",
            re.compile(r"^where\s+(?P<subject>.+?)(?:\?)?$", re.I),
            support.get("where", 0),
            tuple(support.get("examples:where", ())),
        ),
        FramePattern(
            "compare_two",
            "comparison",
            "educational_question",
            "Compare <left> and <right> by shared and differing properties.",
            re.compile(r"^(?:compare|contrast)\s+(?P<left>.+?)\s+(?:and|with|to)\s+(?P<right>.+?)(?:\?)?$", re.I),
            support.get("compare", 0),
            tuple(support.get("examples:compare", ())),
        ),
        FramePattern(
            "does_imply",
            "implication_check",
            "educational_question",
            "Check whether <subject> implies <relation> and explain the evidence.",
            re.compile(r"^does\s+(?P<subject>.+?)\s+(?P<relation>imply|mean|cause|prove|show)\s+(?P<object>.+?)(?:\?)?$", re.I),
            support.get("does", 0),
            tuple(support.get("examples:does", ())),
        ),
        FramePattern(
            "fallback_open",
            "open_educational_frame",
            "educational_question",
            "Determine what kind of answer <subject> requests before gathering facts.",
            re.compile(r"^(?P<subject>.+)$", re.I),
            support.get("open", 0),
            tuple(support.get("examples:open", ())),
        ),
    ]


def _choose_pattern(question: str, patterns: list[FramePattern]) -> FramePattern:
    for pattern in patterns:
        if pattern.pattern_id != "fallback_open" and pattern.regex.match(question):
            return pattern
    return patterns[-1]


def _extract_slots(question: str, pattern: FramePattern) -> dict[str, str]:
    match = pattern.regex.match(question)
    slots = {key: _clean(value) for key, value in (match.groupdict() if match else {}).items() if value}
    if "subject" not in slots:
        slots["subject"] = question.rstrip("?")
    if pattern.frame_type == "implication_check" and "object" in slots:
        slots["relation_object"] = slots["object"]
    slots["requested_output"] = pattern.frame_type
    return slots


def _fill_template(template: str, slots: dict[str, str]) -> str:
    rendered = template
    for key, value in slots.items():
        rendered = rendered.replace(f"<{key}>", value)
    rendered = re.sub(r"<[^>]+>", "the requested item", rendered)
    return rendered


def _confidence(question: str, pattern: FramePattern, support: list[dict[str, Any]]) -> float:
    base = 0.55 if pattern.pattern_id == "fallback_open" else 0.72
    if question.endswith("?"):
        base += 0.05
    if pattern.support_count:
        base += min(0.18, pattern.support_count / 5000.0)
    if support:
        base += 0.03
    return round(min(base, 0.95), 3)


def _support_rows(pattern: FramePattern, support_stats: dict[str, Any]) -> list[dict[str, Any]]:
    examples = list(pattern.examples[:3])
    return [
        {
            "pattern": pattern.pattern_id,
            "source_examples": int(pattern.support_count),
            "confidence_source": "reasoning_frame_corpus_pattern_count",
            "example_questions": examples,
            "source_artifact": str(support_stats.get("source_artifact") or ""),
            "scan_source_corpus_live": bool(support_stats.get("scan_source_corpus_live", False)),
        }
    ]


def _corpus_support(corpus_path: str | Path | None) -> dict[str, Any]:
    return _frame_cloud_support(corpus_path)


@lru_cache(maxsize=8)
def _cached_frame_cloud_support(path_text: str) -> dict[str, Any]:
    path = Path(path_text)
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    support: dict[str, Any] = {}
    for rule in payload.get("rules") or []:
        cloud_key = str(rule.get("cloud_key") or "")
        if not cloud_key:
            continue
        support[cloud_key] = int(rule.get("source_examples") or 0)
        support[f"examples:{cloud_key}"] = [
            str(item.get("question") or "")
            for item in (rule.get("example_pairs") or [])[:3]
            if isinstance(item, dict) and str(item.get("question") or "")
        ]
        support[f"rule:{cloud_key}"] = rule
    support["source_artifact"] = str(path)
    support["scan_source_corpus_live"] = False
    return support


def _frame_cloud_support(corpus_path: str | Path | None) -> dict[str, Any]:
    path = Path(corpus_path) if corpus_path else default_reasoning_frame_corpus()
    return _cached_frame_cloud_support(str(path))


def _corpus_support(corpus_path: str | Path | None) -> dict[str, Any]:
    return _frame_cloud_support(corpus_path)


def _load_csv_frame_rows(path: Path) -> list[dict[str, str]]:
    # Retained only for offline tooling compatibility. Runtime uses frame_cloud_rules.json.
    import csv

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [{"question": row.get("Question", ""), "frame": row.get("Answer_Frame", "")} for row in reader]


def _load_plain_frame_rows(path: Path) -> list[dict[str, str]]:
    # Retained only for offline tooling compatibility. Runtime uses frame_cloud_rules.json.
    rows: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("Question:"):
            current = {"question": line.split(":", 1)[1].strip()}
        elif line.startswith("Reasoning Frame:") and current:
            current["frame"] = line.split(":", 1)[1].strip()
        elif line.strip() == "---" and current:
            rows.append(current)
            current = {}
    if current:
        rows.append(current)
    return rows


def _pattern_key(question: str) -> str:
    lowered = question.casefold()
    for key in ("why", "how", "what", "which", "who", "when", "where", "does"):
        if lowered.startswith(key + " "):
            return key
    if lowered.startswith(("compare ", "contrast ")):
        return "compare"
    return "open"


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())
