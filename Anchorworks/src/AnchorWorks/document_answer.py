from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .intake import extract_anchors


@dataclass
class DocumentAnswerResult:
    ok: bool
    query: str
    query_anchors: list[str]
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
        anchors = _ordered_unique(extract_anchors(query_text))
        evidence = self.store.search_observed_map_evidence(anchors, query_anchors=anchors, map_limit=12)
        passages = [
            row for row in evidence.get("source_passages") or []
            if isinstance(row, dict) and str(row.get("text") or "").strip()
        ][: max(1, int(limit or 6))]
        citations = [_citation_for_passage(row) for row in passages[:3]]
        response = render_document_passages(passages[:3])
        return DocumentAnswerResult(
            ok=bool(passages),
            query=query_text,
            query_anchors=anchors,
            response=response,
            evidence=evidence,
            citations=citations,
        )


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
        return f"{text} (block {block_id}, {line_label})"
    return f"{text} (block {block_id})"


def _citation_for_passage(row: dict[str, Any]) -> dict[str, Any]:
    source_name = str(row.get("source_name") or "")
    block_id = int(row.get("block_id", row.get("paragraph_id", 0)) or 0)
    line_start = int(row.get("line_start", 0) or 0)
    line_end = int(row.get("line_end", 0) or 0)
    line_part = f"L{line_start}" if line_start == line_end else f"L{line_start}-L{line_end}"
    if line_start <= 0:
        line_part = "L?"
    return {
        "source": "document_map",
        "citation_type": "source_locator",
        "source_name": source_name,
        "saved_map_name": row.get("saved_map_name") or "",
        "paragraph_id": int(row.get("paragraph_id", block_id) or 0),
        "block_id": block_id,
        "line_start": line_start,
        "line_end": line_end,
        "coord": f"{source_name}:block{block_id}:{line_part}",
        "score": float(row.get("score", 0.0) or 0.0),
    }


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


def _human_join(values: list[str]) -> str:
    clean = [str(value) for value in values if str(value or "").strip()]
    if not clean:
        return ""
    if len(clean) == 1:
        return clean[0]
    return ", ".join(clean[:-1]) + " and " + clean[-1]
