from __future__ import annotations

from typing import Any

from AnchorWorks.truevision_language.contracts import (
    build_glyph_state_record,
    build_language_state_packet,
    build_textual_cloud_record,
)
from AnchorWorks.truevision_language.transforms import apply_language_transform_rules
from AnchorWorks.visual_glyph_lexicon import VisualGlyphLexicon, normalize_trim_pattern, pattern_hash


def ingest_glyph_pattern_frame(
    *,
    source_id: str,
    frame_id: str,
    glyph_inputs: list[dict[str, Any]],
    glyph_lexicon: VisualGlyphLexicon,
) -> dict[str, Any]:
    """Convert observed glyph patterns into language state and cloud records."""

    ordered_inputs = sorted(
        list(glyph_inputs),
        key=lambda item: (
            int(item.get("order", 0) or 0),
            float((item.get("bbox") or {}).get("y", 0) or 0),
            float((item.get("bbox") or {}).get("x", 0) or 0),
        ),
    )
    glyph_records: list[dict[str, Any]] = []
    displays: list[str] = []
    unknown_glyphs: list[str] = []
    previous_bbox: dict[str, Any] | None = None

    for index, item in enumerate(ordered_inputs):
        pattern = [str(row) for row in item.get("pattern") or []]
        bbox = dict(item.get("bbox") or {})
        if _has_word_gap(previous_bbox, bbox):
            displays.append(" ")
        trimmed = normalize_trim_pattern(pattern)
        if not trimmed:
            glyph_symbol = " "
            confidence = 1.0
            recognition_status = "separator"
        else:
            match = glyph_lexicon.match(pattern)
            glyph_symbol = match.display
            confidence = match.confidence
            recognition_status = "unknown" if match.glyph_id == "visual_unknown_glyph" else "recognized"
            if match.glyph_id == "visual_unknown_glyph":
                unknown_glyphs.append(match.glyph_id)
        displays.append(glyph_symbol)
        glyph_records.append(
            build_glyph_state_record(
                source_id=source_id,
                frame_id=frame_id,
                glyph_id=f"{frame_id}:glyph:{index:06d}",
                glyph_symbol=glyph_symbol,
                bbox=bbox,
                confidence=confidence,
                state_hash=pattern_hash(trimmed),
                recognition_status=recognition_status,
            )
        )
        previous_bbox = bbox

    ordered_symbols = _display_chars_to_symbols(displays)
    packet = build_language_state_packet(
        source_id=source_id,
        frame_id=frame_id,
        glyph_records=glyph_records,
        ordered_symbols=ordered_symbols,
        packet_hash=pattern_hash(tuple(ordered_symbols)),
    )
    if unknown_glyphs:
        packet["render_allowed"] = False
        packet["truth_boundary"]["unknown_glyphs_block_render"] = True

    transform = apply_language_transform_rules(ordered_symbols)
    cloud = build_textual_cloud_record(
        packet=packet,
        cloud_terms=list(transform.get("content_symbols") or []),
        cloud_edges=_cloud_edges(transform),
    )
    if unknown_glyphs:
        cloud["render_allowed"] = False
        cloud["truth_boundary"]["unknown_glyphs_block_render"] = True

    return {
        "schema_version": "anchorworks_truevision_language_ingest@1",
        "source_id": str(source_id),
        "frame_id": str(frame_id),
        "glyph_records": glyph_records,
        "packet": packet,
        "transform": transform,
        "cloud": cloud,
        "unknown_glyphs": sorted(set(unknown_glyphs)),
        "truth_boundary": {
            "state_recorded_not_copied": True,
            "glyph_lexicon_names_marks": True,
            "transform_rules_from_renderer": True,
            "text_is_derived_from_glyph_state": True,
            "ocr_is_not_authority": True,
        },
    }


def _display_chars_to_symbols(displays: list[str]) -> list[str]:
    symbols: list[str] = []
    current: list[str] = []
    for display in displays:
        char = str(display or "")
        if char == "visual_unknown_glyph":
            _flush_current(symbols, current)
            symbols.append("visual_unknown_glyph")
            continue
        if not char or char.isspace():
            _flush_current(symbols, current)
            continue
        if char in {".", ",", "?", "!", ":", ";", "(", ")", "[", "]", "{", "}", "\"", "-", "/", "\\"}:
            _flush_current(symbols, current)
            symbols.append(char)
            continue
        current.append(char.casefold())
    _flush_current(symbols, current)
    return symbols


def _flush_current(symbols: list[str], current: list[str]) -> None:
    if current:
        symbols.append("".join(current))
        current.clear()


def _cloud_edges(transform: dict[str, Any]) -> list[dict[str, Any]]:
    symbols = list(transform.get("ordered_symbols") or [])
    content = set(transform.get("content_symbols") or [])
    edges: list[dict[str, Any]] = []
    for index, symbol in enumerate(symbols):
        role = "content" if symbol in content else "director"
        edges.append({"from": symbol, "to": f"position:{index}", "kind": "symbol_position", "role": role})
        if index:
            edges.append({"from": symbols[index - 1], "to": symbol, "kind": "ordered_neighbor"})
    return edges


def _has_word_gap(previous_bbox: dict[str, Any] | None, bbox: dict[str, Any]) -> bool:
    if not previous_bbox:
        return False
    try:
        previous_right = float(previous_bbox.get("x", 0)) + float(previous_bbox.get("w", 0))
        gap = float(bbox.get("x", 0)) - previous_right
        previous_width = max(1.0, float(previous_bbox.get("w", 1)))
        current_width = max(1.0, float(bbox.get("w", 1)))
    except (TypeError, ValueError):
        return False
    return gap > max(4.0, 1.5 * min(previous_width, current_width))
