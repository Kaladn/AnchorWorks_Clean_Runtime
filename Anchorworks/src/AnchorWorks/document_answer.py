from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .intake import extract_anchors


@dataclass
class DocumentAnswerResult:
    ok: bool
    query: str
    query_anchors: list[str]
    represented_anchors: list[str]
    missing_anchors: list[str]
    lexicon_recognition: dict[str, Any]
    response: str
    evidence: dict[str, Any]
    citations: list[dict[str, Any]]
    evidence_mode: str = "documents"
    engine: str = "document_answer_assembler"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DocumentAnswerAssembler:
    def __init__(self, store: Any) -> None:
        self.store = store

    def answer(self, query: str, *, limit: int = 6) -> DocumentAnswerResult:
        query_text = str(query or "").strip()
        recognition = self._recognize(query_text)
        anchors = recognition["query_anchors"]
        focus_anchors = _document_focus_anchors(anchors)
        represented_focus = [anchor for anchor in focus_anchors if anchor in set(recognition["represented_anchors"])]
        missing_focus = [anchor for anchor in focus_anchors if anchor in set(recognition["missing_anchors"])]
        evidence = self.store.search_flat_document_evidence(
            focus_anchors,
            query_anchors=focus_anchors,
            max_files=4096,
        )
        if not evidence.get("source_passages"):
            evidence = self.store.search_observed_map_evidence(focus_anchors, query_anchors=focus_anchors, map_limit=12)
        passages = [
            row for row in evidence.get("source_passages") or []
            if isinstance(row, dict) and str(row.get("text") or "").strip()
        ][: max(1, int(limit or 6))]
        citations = [_citation_for_passage(row) for row in passages[:3]]
        response = render_document_passages(passages[:3])
        return DocumentAnswerResult(
            ok=bool(passages),
            query=query_text,
            query_anchors=focus_anchors,
            represented_anchors=represented_focus,
            missing_anchors=missing_focus,
            lexicon_recognition=recognition,
            response=response,
            evidence=evidence,
            citations=citations,
        )

    def _recognize(self, query: str) -> dict[str, Any]:
        if hasattr(self.store, "recognize_query_anchors"):
            return self.store.recognize_query_anchors(query)
        anchors = _ordered_unique(extract_anchors(query))
        return {
            "schema_version": "anchorworks_lexicon_recognition@1",
            "query": str(query or ""),
            "query_anchors": anchors,
            "represented_anchors": anchors,
            "missing_anchors": [],
            "recognition_layer": "lexicon",
            "lexicon_first": True,
            "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
        }


def render_document_passages(passages: list[dict[str, Any]]) -> str:
    selected = [
        _passage_with_locator(row)
        for row in passages
        if isinstance(row, dict) and str(row.get("text") or "").strip()
    ]
    selected = [row for row in selected if row]
    if not selected:
        return ""
    source_names: list[str] = []
    for row in passages:
        name = str(row.get("source_name") or "").strip()
        if name and name not in source_names:
            source_names.append(name)
    source_phrase = ""
    if source_names:
        source_phrase = " Source-local document evidence: " + _human_join(source_names[:2]) + "."
    if len(selected) == 1:
        return "The source document supports this answer: " + selected[0] + source_phrase
    points = " ".join(f"{index}. {snippet}" for index, snippet in enumerate(selected, start=1))
    return "The source document supports these points: " + points + source_phrase


def _passage_with_locator(row: dict[str, Any]) -> str:
    text = _clean_passage_sentence(str(row.get("text") or ""))
    if not text:
        return ""
    block_id = int(row.get("block_id", row.get("paragraph_id", 0)) or 0)
    line_start = int(row.get("line_start", 0) or 0)
    line_end = int(row.get("line_end", 0) or 0)
    if line_start > 0 and line_end > 0:
        line_label = f"line {line_start}" if line_start == line_end else f"lines {line_start}-{line_end}"
        return f"{text} (block {block_id}, {line_label}{_visual_ref_suffix(row)})"
    return f"{text} (block {block_id}{_visual_ref_suffix(row)})"


def _citation_for_passage(row: dict[str, Any]) -> dict[str, Any]:
    source_name = str(row.get("source_name") or "")
    block_id = int(row.get("block_id", row.get("paragraph_id", 0)) or 0)
    line_start = int(row.get("line_start", 0) or 0)
    line_end = int(row.get("line_end", 0) or 0)
    line_part = f"L{line_start}" if line_start == line_end else f"L{line_start}-L{line_end}"
    if line_start <= 0:
        line_part = "L?"
    return {
        "source": str(row.get("source") or "document_map"),
        "citation_type": "source_locator",
        "source_name": source_name,
        "saved_map_name": row.get("saved_map_name") or "",
        "saved_document_name": row.get("saved_document_name") or "",
        "paragraph_id": int(row.get("paragraph_id", block_id) or 0),
        "block_id": block_id,
        "line_start": line_start,
        "line_end": line_end,
        "coord": f"{source_name}:block{block_id}:{line_part}",
        "score": float(row.get("score", 0.0) or 0.0),
        "visual_refs": row.get("visual_refs") or [],
    }


def _visual_ref_suffix(row: dict[str, Any]) -> str:
    refs = [
        ref for ref in row.get("visual_refs") or []
        if isinstance(ref, dict) and str(ref.get("visual_record_id") or "").strip()
    ]
    if not refs:
        return ""
    first = refs[0]
    kind = str(first.get("kind") or "").strip()
    visual_id = str(first.get("visual_record_id") or "").strip()
    kind_suffix = f" ({kind})" if kind and kind != "figure" else ""
    return f", figure {visual_id}{kind_suffix}"


def _clean_passage_sentence(text: str, max_chars: int = 280) -> str:
    clean = " ".join(str(text or "").split())
    if not clean:
        return ""
    if len(clean) <= max_chars:
        return clean
    cut = clean[:max_chars].rsplit(" ", 1)[0].rstrip(" ,;:")
    return cut + "."


def _ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        clean = str(value or "").strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        out.append(clean)
    return out


_DOCUMENT_QUERY_STOP_ANCHORS = {
    "",
    ".",
    ",",
    "?",
    "!",
    ":",
    ";",
    "(",
    ")",
    "a",
    "an",
    "and",
    "are",
    "as",
    "ask",
    "about",
    "does",
    "do",
    "document",
    "find",
    "for",
    "from",
    "give",
    "in",
    "is",
    "me",
    "mention",
    "mentions",
    "of",
    "on",
    "passage",
    "passages",
    "say",
    "says",
    "show",
    "source",
    "sources",
    "tell",
    "the",
    "to",
    "what",
    "where",
}


def _document_focus_anchors(anchors: list[str]) -> list[str]:
    focused = [
        anchor for anchor in anchors
        if str(anchor or "").strip().casefold() not in _DOCUMENT_QUERY_STOP_ANCHORS
    ]
    return focused or anchors


def _human_join(values: list[str]) -> str:
    clean = [str(value) for value in values if str(value or "").strip()]
    if not clean:
        return ""
    if len(clean) == 1:
        return clean[0]
    return ", ".join(clean[:-1]) + " and " + clean[-1]
