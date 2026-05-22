from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


SCHEMA_VERSION = "anchorworks_truevision_language_state@1"


def build_glyph_state_record(
    *,
    source_id: str,
    frame_id: str,
    glyph_id: str,
    glyph_symbol: str,
    bbox: dict[str, int | float],
    confidence: float,
    state_hash: str = "",
    recognition_status: str = "recognized",
) -> dict[str, Any]:
    """Record one observed glyph as visual language state, not copied text."""

    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "glyph_state",
        "source_id": str(source_id),
        "frame_id": str(frame_id),
        "glyph_id": str(glyph_id),
        "glyph_symbol": str(glyph_symbol),
        "bbox": dict(bbox),
        "confidence": float(confidence),
        "state_hash": str(state_hash),
        "recognition_status": str(recognition_status),
        "state_recorded_not_copied": True,
        "truth_boundary": {
            "glyphs_are_observed_marks": True,
            "text_is_derived": True,
            "ocr_is_not_authority": True,
        },
        "created_at_utc": _utc_now(),
    }


def build_language_state_packet(
    *,
    source_id: str,
    frame_id: str,
    glyph_records: list[dict[str, Any]],
    ordered_symbols: list[str],
    packet_hash: str = "",
) -> dict[str, Any]:
    """Group glyph states into an ordered language-state packet."""

    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "language_state_packet",
        "source_id": str(source_id),
        "frame_id": str(frame_id),
        "glyph_record_count": len(glyph_records),
        "glyph_record_refs": [str(row.get("glyph_id") or "") for row in glyph_records],
        "ordered_symbols": [str(symbol) for symbol in ordered_symbols],
        "packet_hash": str(packet_hash),
        "state_recorded_not_copied": True,
        "render_allowed": bool(ordered_symbols),
        "truth_boundary": {
            "packet_uses_glyph_state": True,
            "raw_text_not_copied": True,
            "missing_glyphs_remain_missing": True,
        },
        "created_at_utc": _utc_now(),
    }


def build_textual_cloud_record(
    *,
    packet: dict[str, Any],
    cloud_terms: list[str],
    cloud_edges: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a textual cloud from accepted language state."""

    ordered_symbols = [str(symbol) for symbol in packet.get("ordered_symbols") or []]
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "textual_cloud",
        "source_id": str(packet.get("source_id") or ""),
        "frame_id": str(packet.get("frame_id") or ""),
        "language_state_packet_ref": str(packet.get("packet_hash") or ""),
        "ordered_symbols": ordered_symbols,
        "cloud_terms": [str(term) for term in cloud_terms],
        "cloud_edges": list(cloud_edges or []),
        "state_recorded_not_copied": True,
        "render_allowed": bool(cloud_terms),
        "truth_boundary": {
            "cloud_derived_from_language_state": True,
            "cloud_is_not_fact_authority": True,
            "renderer_must_replay_state": True,
        },
        "created_at_utc": _utc_now(),
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
