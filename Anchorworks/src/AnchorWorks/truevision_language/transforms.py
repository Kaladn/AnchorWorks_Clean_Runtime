from __future__ import annotations

from typing import Any

from AnchorWorks.anchor_field import build_query_frame


def apply_language_transform_rules(ordered_symbols: list[str]) -> dict[str, Any]:
    """Apply the same content/director split used by the renderer query path."""

    symbols = [str(symbol or "").strip().casefold() for symbol in ordered_symbols if str(symbol or "").strip()]
    query_frame = build_query_frame(symbols)
    punctuation = [
        str(row.get("anchor") or "")
        for row in query_frame.get("director_anchors", [])
        if isinstance(row, dict) and row.get("role") == "punctuation"
    ]
    content_symbols = [
        symbol
        for symbol in list(query_frame.get("content_seeds") or [])
        if symbol != "visual_unknown_glyph"
    ]
    return {
        "schema_version": "anchorworks_truevision_language_transform@1",
        "ordered_symbols": symbols,
        "content_symbols": content_symbols,
        "director_symbols": list(query_frame.get("director_anchors") or []),
        "punctuation_symbols": punctuation,
        "blocked_symbols": ["visual_unknown_glyph"] if "visual_unknown_glyph" in symbols else [],
        "query_frame": query_frame,
        "rules_source": "AnchorWorks.anchor_field.build_query_frame",
        "truth_boundary": {
            "transform_rules_from_renderer": True,
            "content_symbols_may_feed_cloud": True,
            "director_symbols_shape_rendering": True,
            "punctuation_is_direction_not_content": True,
            "unknown_glyphs_are_not_content": True,
        },
    }
