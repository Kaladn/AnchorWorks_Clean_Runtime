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


def render_anchor_answer_surface(
    query_anchors: list[str],
    answer_assembly: dict[str, Any],
    *,
    fallback_subjects: list[str] | None = None,
    source_label: str = "count path",
) -> str:
    """Render a chosen AnchorWorks answer path as speech without inventing facts."""

    observed = _clean_list(query_anchors)
    subjects = _content_subjects(observed) or _content_subjects(fallback_subjects or [])
    terms = _answer_terms(answer_assembly)
    if not terms:
        return ""

    subject_text = _human_join(subjects[:3]) if subjects else "the query"
    term_text = _human_join(terms[:8])
    frame = _frame_type(observed)

    if frame == "why":
        return f"For {subject_text}, the {source_label} points toward {term_text}."
    if frame == "how":
        return f"For {subject_text}, the {source_label} moves through {term_text}."
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


def _frame_type(anchors: list[str]) -> str:
    observed = _clean_list(anchors)
    if not observed:
        return "open"
    if observed[0] == "why":
        return "why"
    if observed[0] == "how":
        return "how"
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
