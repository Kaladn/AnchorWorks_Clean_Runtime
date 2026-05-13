from __future__ import annotations

from typing import Any

from .visual_glyph_lexicon import VisualGlyphLexicon
from .visual_mark_anomaly import MarkComponent, detect_visual_mark_anomalies


def _component_key(component: dict[str, Any]) -> tuple[int, int]:
    x1, y1, _x2, _y2 = component["bounds"]
    return int(y1), int(x1)


def reconstruct_from_known_components(
    lexicon: VisualGlyphLexicon,
    components: list[dict[str, Any]],
    *,
    word_gap_pixels: int,
) -> dict[str, Any]:
    ordered = sorted(components, key=_component_key)
    matched: list[MarkComponent] = []
    output_parts: list[str] = []
    previous_bounds: tuple[int, int, int, int] | None = None
    for raw in ordered:
        bounds = tuple(int(value) for value in raw["bounds"])
        pattern = list(raw["pattern"])
        match = lexicon.match(pattern)
        matched.append(
            MarkComponent(
                component_id=str(raw["component_id"]),
                bounds=bounds,
                pattern=tuple(pattern),
                display=match.display,
                confidence=match.confidence,
            )
        )
        if match.display != "visual_unknown_glyph":
            if previous_bounds is not None:
                gap = bounds[0] - previous_bounds[2]
                if gap >= word_gap_pixels:
                    output_parts.append(" ")
            output_parts.append(match.display)
        previous_bounds = bounds
    anomalies = detect_visual_mark_anomalies(matched, expected_word_gap_pixels=word_gap_pixels)
    blocking = [row for row in anomalies if row.get("blocking")]
    unknown_count = sum(1 for row in matched if row.display == "visual_unknown_glyph")
    text_candidate = "" if blocking else "".join(output_parts)
    return {
        "schema_version": "anchorworks_visual_text_candidate@1",
        "text_candidate": text_candidate,
        "components_seen": len(components),
        "unknown_glyphs": unknown_count,
        "anomalies": anomalies,
        "blocking_anomalies": len(blocking),
        "resolved_anchor": "__NULL__" if blocking else "",
        "count_eligible": not blocking,
        "memory_truth": not blocking,
    }
