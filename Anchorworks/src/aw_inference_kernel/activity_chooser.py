from __future__ import annotations


SYSTEM_TERMS = {"status", "server", "ui", "settings", "lexicon", "counts", "ingest", "intake"}
DOCUMENT_TERMS = {"source", "document", "docs", "citation", "evidence", "passage"}


def choose_activity(query_anchors: list[str], mode: str = "") -> dict[str, str]:
    mode_name = str(mode or "").strip().casefold()
    anchors = {str(anchor or "").strip().casefold() for anchor in query_anchors}
    if mode_name in {"documents", "document", "maps", "mapped"} or anchors & DOCUMENT_TERMS:
        return {"activity": "document_question", "reason": "document_lane_requested_or_named"}
    if mode_name in {"counts", "count", "clearspeak"}:
        return {"activity": "count_question", "reason": "count_lane_requested"}
    if anchors & SYSTEM_TERMS:
        return {"activity": "system_question", "reason": "system_terms_present"}
    return {"activity": "educational_question", "reason": "default_question_activity"}
