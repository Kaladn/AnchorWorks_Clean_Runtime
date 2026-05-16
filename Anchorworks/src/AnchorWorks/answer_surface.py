from __future__ import annotations

from typing import Any

from .intake import extract_anchors


QUESTION_DIRECTORS = {"what", "why", "how", "when", "where", "who", "which"}
SURFACE_GLUE = {
    "a", "an", "the",
    "about", "above", "after", "against", "along", "among", "around", "as", "at",
    "before", "behind", "below", "between", "by", "for", "from", "in", "into",
    "of", "on", "onto", "over", "through", "to", "under", "with", "within",
    "and", "or", "but", "however", "such", "than", "then", "therefore",
    "is", "are", "was", "were", "be", "being", "been", "do", "does", "did",
    "can", "could", "should", "would", "may", "might", "must",
}
SURFACE_CONNECTORS = {
    "and", "or",
    "of", "to", "for", "from", "in", "into", "on", "with", "within", "through", "between", "by", "as",
}
SUBJECT_BOUNDARY_CONNECTORS = {"about", "around", "regarding", "concerning"}
SURFACE_AUXILIARY = {
    "is", "are", "was", "were", "be", "being", "been", "do", "does", "did",
    "can", "could", "should", "would", "may", "might", "must",
}


def render_anchor_answer_surface(
    query_anchors: list[str],
    answer_assembly: dict[str, Any],
    *,
    fallback_subjects: list[str] | None = None,
    source_label: str = "count path",
) -> str:
    """Render a chosen AnchorWorks answer path as speech without inventing facts."""

    observed = _clean_list(query_anchors)
    subjects = _subject_surface(observed) or _subject_surface(_clean_list(fallback_subjects or []))
    terms = _answer_surface_terms(answer_assembly)
    if not terms:
        return ""

    subject_text = subjects or "the query"
    term_text = _human_join(terms[:8])
    frame = _frame_type(observed)

    if frame == "why":
        return f"The answer path around {subject_text} points toward {term_text}."
    if frame == "how":
        return f"The answer path for {subject_text} moves through {term_text}."
    if frame == "who":
        subject_text = subject_text.replace(" and ", " ")
        return f"{subject_text.capitalize()} is represented as an entity count field connected with {term_text}."
    if frame == "what":
        return f"{subject_text.capitalize()} is most strongly connected with {term_text}."
    if frame == "agreement":
        return f"The active path around {subject_text} supports {term_text}."
    return f"The active path connects {subject_text} with {term_text}."


def _answer_terms(answer_assembly: dict[str, Any]) -> list[str]:
    rows = [row for row in answer_assembly.get("terms", []) if isinstance(row, dict)]
    terms = [
        str(row.get("anchor") or "").strip().casefold()
        for row in rows
        if str(row.get("anchor") or "").strip()
    ]
    return _ordered_unique([term for term in terms if not _blocked_surface_anchor(term)])


def _answer_surface_terms(answer_assembly: dict[str, Any]) -> list[str]:
    plan = answer_assembly.get("inference_plan")
    if isinstance(plan, dict):
        accepted = plan.get("accepted_candidates")
        if isinstance(accepted, list):
            planned_terms = [
                str(row.get("symbol") or row.get("anchor") or "").strip().casefold()
                for row in accepted
                if isinstance(row, dict) and str(row.get("symbol") or row.get("anchor") or "").strip()
            ]
            if planned_terms:
                return _ordered_unique([term for term in planned_terms if not _blocked_answer_term(term)])
            return []

    rows = [row for row in answer_assembly.get("terms", []) if isinstance(row, dict)]
    terms = [
        str(row.get("anchor") or "").strip().casefold()
        for row in rows
        if str(row.get("anchor") or "").strip()
    ]
    return _ordered_unique([term for term in terms if not _blocked_answer_term(term)])


def _frame_type(anchors: list[str]) -> str:
    observed = _clean_list(anchors)
    if not observed:
        return "open"
    if observed[0] == "why":
        return "why"
    if observed[0] == "how":
        return "how"
    if observed[0] == "who":
        return "who"
    if observed[0] in {"what", "which", "who", "where", "when"}:
        return "what"
    if any(anchor in {"agree", "agreement"} for anchor in observed):
        return "agreement"
    return "open"


def _content_subjects(anchors: list[str]) -> list[str]:
    return _ordered_unique(
        anchor
        for anchor in _clean_list(anchors)
        if not _blocked_surface_anchor(anchor) and anchor not in QUESTION_DIRECTORS
    )


def _subject_surface(anchors: list[str]) -> str:
    observed = _clean_list(anchors)
    if not observed:
        return ""
    for index, anchor in enumerate(observed):
        if anchor in SUBJECT_BOUNDARY_CONNECTORS and index + 1 < len(observed):
            candidate = _surface_phrase(observed[index + 1:])
            if candidate:
                return candidate if _contains_surface_connector(candidate) else _human_join(_content_subjects(observed[index + 1:])[:3])
    candidate = _surface_phrase(observed)
    return candidate if _contains_surface_connector(candidate) else _human_join(_content_subjects(observed)[:3])


def _surface_phrase(anchors: list[str]) -> str:
    out: list[str] = []
    previous_content = False
    for anchor in anchors:
        clean = str(anchor or "").strip().casefold()
        if not clean or clean in QUESTION_DIRECTORS or clean in SURFACE_AUXILIARY:
            continue
        if clean in {"?", ".", ",", ":", ";", "!", "(", ")", "[", "]", "{", "}", "\"", "'", "__null__"}:
            continue
        if any(char.isdigit() for char in clean):
            continue
        if clean in SUBJECT_BOUNDARY_CONNECTORS:
            out = []
            previous_content = False
            continue
        if clean in SURFACE_CONNECTORS:
            if previous_content:
                out.append(clean)
                previous_content = False
            continue
        if clean in SURFACE_GLUE:
            continue
        out.append(clean)
        previous_content = True
    while out and out[-1] in SURFACE_CONNECTORS:
        out.pop()
    return " ".join(out[:8])


def _clean_list(values: list[str] | tuple[str, ...]) -> list[str]:
    cleaned: list[str] = []
    for value in values or []:
        if isinstance(value, str):
            parts = [value]
        else:
            parts = extract_anchors(str(value or ""))
        for part in parts:
            clean = str(part or "").strip().casefold()
            if clean:
                cleaned.append(clean)
    return cleaned


def _blocked_surface_anchor(anchor: str) -> bool:
    if not anchor:
        return True
    if anchor in QUESTION_DIRECTORS or anchor in SURFACE_GLUE:
        return True
    if anchor in {"?", ".", ",", ":", ";", "!", "(", ")", "[", "]", "{", "}", "\"", "'", "__null__"}:
        return True
    if any(char.isdigit() for char in anchor):
        return True
    return False


def _blocked_answer_term(anchor: str) -> bool:
    if not anchor:
        return True
    if anchor in QUESTION_DIRECTORS:
        return True
    if anchor in {"?", ".", ",", ":", ";", "!", "(", ")", "[", "]", "{", "}", "\"", "'", "__null__"}:
        return True
    if any(char.isdigit() for char in anchor):
        return True
    if anchor in SURFACE_GLUE and anchor not in SURFACE_CONNECTORS:
        return True
    return False


def _contains_surface_connector(text: str) -> bool:
    words = set(str(text or "").split())
    return bool(words & SURFACE_CONNECTORS)


def _ordered_unique(values: list[str] | Any) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        clean = str(value or "").strip().casefold()
        if clean and clean not in seen:
            seen.add(clean)
            out.append(clean)
    return out


def _human_join(values: list[str]) -> str:
    cleaned = [value for value in values if value]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return ", ".join(cleaned[:-1]) + f", and {cleaned[-1]}"
