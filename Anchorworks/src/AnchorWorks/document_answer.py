from __future__ import annotations

from dataclasses import asdict, dataclass
from collections import Counter
from typing import Any

from .clearspeak_attention import (
    ACTIVE_CLOUD_WEIGHTS,
    attention_math_contract,
    build_active_cloud_frame,
    choose_candidate_with_lookahead,
    content_anchors,
    infer_attention_frame,
)
from .answer_surface import render_anchor_answer_surface
from .intake import extract_anchors
from .local_meta_overlay import query_local_overlay_cloud, renderer_cloud_input


@dataclass
class DocumentAnswerResult:
    ok: bool
    query: str
    query_anchors: list[str]
    represented_anchors: list[str]
    missing_anchors: list[str]
    lexicon_recognition: dict[str, Any]
    speech: str
    response: str
    answer_assembly: dict[str, Any]
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
        overlays = self._load_local_overlays(passages)
        answer_assembly = (
            build_document_overlay_answer(focus_anchors, overlays, limit=limit)
            if overlays
            else build_document_cloud_answer(focus_anchors, passages, limit=limit)
        )
        speech = render_answer_assembly_speech(focus_anchors, answer_assembly) or response
        return DocumentAnswerResult(
            ok=bool(passages),
            query=query_text,
            query_anchors=focus_anchors,
            represented_anchors=represented_focus,
            missing_anchors=missing_focus,
            lexicon_recognition=recognition,
            speech=speech,
            response=response,
            answer_assembly=answer_assembly,
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

    def _load_local_overlays(self, passages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not hasattr(self.store, "load_local_overlay_for_symbolic_document"):
            return []
        overlays: list[dict[str, Any]] = []
        seen: set[str] = set()
        for passage in passages:
            name = str(passage.get("saved_document_name") or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            try:
                overlay = self.store.load_local_overlay_for_symbolic_document(name)
            except Exception:
                overlay = None
            if isinstance(overlay, dict):
                overlays.append(overlay)
        return overlays


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


def build_document_cloud_answer(query_anchors: list[str], passages: list[dict[str, Any]], *, limit: int = 6) -> dict[str, Any]:
    count_index = _document_passage_count_index(passages)
    return _walk_document_count_index(query_anchors, count_index, limit=limit)


def build_document_overlay_answer(query_anchors: list[str], overlays: list[dict[str, Any]], *, limit: int = 6) -> dict[str, Any]:
    count_index = _document_overlay_count_index(query_anchors, overlays)
    answer = _walk_document_count_index(query_anchors, count_index, limit=limit)
    answer["source_local_cloud"] = count_index.get("source_local_cloud") or {}
    answer["renderer_cloud_input"] = count_index.get("renderer_cloud_input") or {}
    return answer


def _walk_document_count_index(query_anchors: list[str], count_index: dict[str, Any], *, limit: int = 6) -> dict[str, Any]:
    represented = _ordered_unique([str(anchor or "").strip().casefold() for anchor in query_anchors if str(anchor or "").strip()])
    seeds = content_anchors(represented)
    if not seeds:
        return _empty_document_answer_assembly("no_content_seed")
    attention_frame = infer_attention_frame(represented)
    rear_context = list(seeds[-6:])
    answer_so_far: list[str] = []
    forward_context: list[str] = []
    selected: list[dict[str, Any]] = []
    selected_anchors: set[str] = set()
    trace: list[dict[str, Any]] = []
    blocked = set(seeds)
    for step in range(max(1, int(limit or 6))):
        active_cloud = build_active_cloud_frame(
            count_index,
            question_anchors=represented,
            rear_context=rear_context,
            answer_so_far=answer_so_far,
            forward_context=forward_context,
            blocked=blocked | selected_anchors,
            attention_frame=attention_frame,
            top_k=6,
        )
        pool = active_cloud["candidates"]
        if not pool:
            return {
                "schema_version": "document_cloud_answer@1",
                "seed_anchors": seeds,
                "terms": selected,
                "trace": trace,
                "stop_reason": "no_supported_candidate" if selected else "no_candidate_pool",
                "attention_frame": attention_frame,
                "active_cloud_weights": dict(ACTIVE_CLOUD_WEIGHTS),
                "attention_math": attention_math_contract(),
                "count_source": str(count_index.get("count_source") or "source_local_document_cloud"),
            }
        lookahead_decision = choose_candidate_with_lookahead(
            count_index,
            pool,
            seed_anchors=seeds,
            blocked=blocked | selected_anchors,
            lookahead_k=6,
        )
        winner = lookahead_decision.get("chosen") or pool[0]
        selected.append({**winner, "selection_step": step + 1})
        selected_anchors.add(winner["anchor"])
        before_rear = list(rear_context)
        before_answer = list(answer_so_far)
        answer_so_far = answer_so_far[-49:] + [winner["anchor"]]
        rear_context = (answer_so_far[-6:] + seeds)[-12:]
        forward_context = _forward_context_from_count_index(count_index, winner["anchor"])
        trace.append({
            "step": step + 1,
            "chosen_anchor": winner["anchor"],
            "candidate_rank": winner.get("candidate_rank", 1),
            "score": winner["score"],
            "score_parts": winner.get("score_parts") or {},
            "penalties": winner.get("penalties") or {},
            "supporting_context": winner["supporting_context"],
            "rear_context_before": before_rear,
            "answer_so_far_before": before_answer,
            "rear_context_after": rear_context,
            "answer_so_far_after": answer_so_far,
            "forward_context_after": forward_context,
            "lookahead_decision": lookahead_decision,
            "candidate_preview": pool[:6],
            "rejected_candidates": active_cloud.get("rejected_candidates") or [],
        })
    return {
        "schema_version": "document_cloud_answer@1",
        "seed_anchors": seeds,
        "terms": selected,
        "trace": trace,
        "stop_reason": "answer_limit_reached",
        "attention_frame": attention_frame,
        "active_cloud_weights": dict(ACTIVE_CLOUD_WEIGHTS),
        "attention_math": attention_math_contract(),
        "count_source": str(count_index.get("count_source") or "source_local_document_cloud"),
    }


def render_answer_assembly_speech(query_anchors: list[str], answer_assembly: dict[str, Any]) -> str:
    return render_anchor_answer_surface(
        query_anchors,
        answer_assembly,
        fallback_subjects=query_anchors,
        source_label="document cloud path",
    )


def _document_passage_count_index(passages: list[dict[str, Any]], *, window_radius: int = 6) -> dict[str, Any]:
    by_anchor: dict[str, dict[str, Counter[str]]] = {}
    for row in passages:
        anchors = [str(anchor or "").strip().casefold() for anchor in extract_anchors(str(row.get("text") or "")) if str(anchor or "").strip()]
        for index, anchor in enumerate(anchors):
            for neighbor_index in range(max(0, index - window_radius), min(len(anchors), index + window_radius + 1)):
                if neighbor_index == index:
                    continue
                offset_value = neighbor_index - index
                offset = f"+{offset_value}" if offset_value > 0 else str(offset_value)
                by_anchor.setdefault(anchor, {}).setdefault(offset, Counter())[anchors[neighbor_index]] += 1
    return {
        "by_anchor": by_anchor,
        "count_source": "source_local_document_cloud",
        "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
    }


def _document_overlay_count_index(query_anchors: list[str], overlays: list[dict[str, Any]]) -> dict[str, Any]:
    by_anchor: dict[str, dict[str, Counter[str]]] = {}
    query_symbols = [str(anchor or "").strip().casefold() for anchor in query_anchors if str(anchor or "").strip()]
    clouds: list[dict[str, Any]] = []
    locator_refs: list[dict[str, Any]] = []
    for overlay in overlays:
        cloud = query_local_overlay_cloud(query_symbols, overlay, top_k=6)
        clouds.append(cloud)
        locator_refs.extend([row for row in cloud.get("locator_refs") or [] if isinstance(row, dict)])
        for row in overlay.get("local_relation_counts") or []:
            if not isinstance(row, dict):
                continue
            anchor = str(row.get("symbol") or "").strip().casefold()
            offset = str(row.get("offset") or "")
            neighbor = str(row.get("neighbor_symbol") or "").strip().casefold()
            count = int(row.get("count", 0) or 0)
            if not anchor or not offset or not neighbor or count <= 0:
                continue
            by_anchor.setdefault(anchor, {}).setdefault(offset, Counter())[neighbor] += count
    cloud_input = renderer_cloud_input(
        query_symbols=query_symbols,
        source_local_cloud={"schema_version": "anchorworks_source_local_overlay_cloud@1", "clouds": clouds},
        global_awsc_cloud={},
        locator_refs=locator_refs,
    ).to_dict()
    return {
        "by_anchor": by_anchor,
        "count_source": "local_meta_overlay",
        "source_local_cloud": cloud_input["source_local_cloud"],
        "renderer_cloud_input": cloud_input,
        "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
    }


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


def _forward_context_from_count_index(count_index: dict[str, Any], anchor: str, limit: int = 6) -> list[str]:
    offsets = ((count_index.get("by_anchor") or {}).get(str(anchor or "").strip().casefold()) or {})
    forward = Counter()
    for offset, rows in offsets.items():
        try:
            offset_value = int(str(offset).replace("+", ""))
        except ValueError:
            offset_value = 0
        if offset_value <= 0:
            continue
        for neighbor, count in Counter(rows or {}).items():
            if int(count or 0) > 0:
                forward[str(neighbor)] += int(count)
    return [anchor for anchor, _count in forward.most_common(limit)]


def _empty_document_answer_assembly(reason: str) -> dict[str, Any]:
    return {
        "schema_version": "document_cloud_answer@1",
        "seed_anchors": [],
        "terms": [],
        "trace": [],
        "stop_reason": reason,
        "count_source": "source_local_document_cloud",
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
