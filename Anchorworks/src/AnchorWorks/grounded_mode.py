from __future__ import annotations

import hashlib
import json
from typing import Any


def build_grounded_evidence_packet(
    *,
    query: str,
    clearspeak_payload: dict[str, Any],
    document_payload: dict[str, Any],
) -> dict[str, Any]:
    count_evidence = [row for row in (clearspeak_payload.get("evidence") or []) if isinstance(row, dict)]
    document_evidence = document_payload.get("evidence") if isinstance(document_payload.get("evidence"), dict) else {}
    passages = [row for row in (document_evidence.get("source_passages") or []) if isinstance(row, dict)]
    represented = _ordered_unique(
        list(clearspeak_payload.get("represented_anchors") or [])
        + list(document_payload.get("represented_anchors") or [])
    )
    missing = _ordered_unique(
        list(clearspeak_payload.get("missing_anchors") or [])
        + list(document_payload.get("missing_anchors") or [])
    )
    packet = {
        "schema_version": "anchorworks_grounded_evidence_packet@1",
        "query": str(query or ""),
        "represented_anchors": represented,
        "missing_anchors": missing,
        "count_evidence": count_evidence,
        "document_passages": passages[:12],
        "count_evidence_count": len(count_evidence),
        "document_evidence_count": len(passages),
        "citations": _dedupe_citations(
            list(clearspeak_payload.get("citations") or []) + list(document_payload.get("citations") or [])
        ),
        "count_speech": str(clearspeak_payload.get("speech") or clearspeak_payload.get("response") or ""),
        "document_speech": str(document_payload.get("speech") or document_payload.get("response") or ""),
        "answer_assembly": clearspeak_payload.get("answer_assembly") or {},
        "document_answer_assembly": document_payload.get("answer_assembly") or {},
        "writes_performed": False,
        "truth_boundary": {
            "aw_builds_packet": True,
            "model_does_not_create_evidence": True,
            "citations_are_refs_not_truth_by_themselves": True,
            "unsupported_claims_must_be_rejected": True,
        },
        "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
    }
    packet["packet_sha256"] = _hash_payload({key: value for key, value in packet.items() if key != "packet_sha256"})
    return packet


def render_grounded_result(packet: dict[str, Any]) -> dict[str, Any]:
    evidence_count = int(packet.get("count_evidence_count", 0) or 0) + int(packet.get("document_evidence_count", 0) or 0)
    if evidence_count <= 0:
        response = "No grounded evidence is available for that query. I will not promote an unsupported answer."
        return {
            "schema_version": "anchorworks_grounded_result@1",
            "ok": False,
            "verdict": "unsupported",
            "response": response,
            "grounded_response": response,
            "used_evidence_refs": [],
            "unsupported_claims": [str(packet.get("query") or "")],
            "shape_diff": {"changed": False, "reason": "no_evidence_packet_support"},
            "writes_performed": False,
        }

    count_speech = str(packet.get("count_speech") or "").strip()
    document_speech = str(packet.get("document_speech") or "").strip()
    response_parts = []
    if document_speech:
        response_parts.append(document_speech)
    if count_speech and count_speech not in response_parts:
        response_parts.append(count_speech)
    response = " ".join(response_parts).strip() or "Grounded evidence was found, but no lawful rendered answer was produced."
    return {
        "schema_version": "anchorworks_grounded_result@1",
        "ok": True,
        "verdict": "grounded",
        "response": response,
        "grounded_response": response,
        "used_evidence_refs": [str(row.get("coord") or row.get("source") or "") for row in packet.get("citations") or []],
        "unsupported_claims": [],
        "shape_diff": _shape_diff(packet),
        "writes_performed": False,
    }


def _shape_diff(packet: dict[str, Any]) -> dict[str, Any]:
    count = str(packet.get("count_speech") or "").strip()
    document = str(packet.get("document_speech") or "").strip()
    return {
        "changed": bool(count and document and count != document),
        "count_len": len(count.split()),
        "document_len": len(document.split()),
        "reason": "document_and_count_shapes_compared",
    }


def _dedupe_citations(citations: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in citations:
        if not isinstance(item, dict):
            continue
        key = str(item.get("coord") or item.get("source") or item)
        if key in seen:
            continue
        seen.add(key)
        rows.append(dict(item))
    return rows


def _ordered_unique(values: list[Any]) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip().casefold()
        if not text or text in seen:
            continue
        seen.add(text)
        rows.append(text)
    return rows


def _hash_payload(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
