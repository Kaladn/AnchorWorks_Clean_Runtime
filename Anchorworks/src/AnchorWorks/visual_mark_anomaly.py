from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MarkComponent:
    component_id: str
    bounds: tuple[int, int, int, int]
    pattern: tuple[str, ...]
    display: str
    confidence: float


def _overlaps(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    return ax1 < bx2 and ax2 > bx1 and ay1 < by2 and ay2 > by1


def detect_visual_mark_anomalies(
    components: list[MarkComponent],
    *,
    expected_word_gap_pixels: int = 8,
    max_word_gap_multiplier: int = 4,
) -> list[dict[str, Any]]:
    anomalies: list[dict[str, Any]] = []
    for component in components:
        if component.display == "visual_unknown_glyph":
            anomalies.append(
                {
                    "kind": "visual_unknown_glyph",
                    "component_id": component.component_id,
                    "blocking": True,
                    "reason": "unknown mark cannot become text",
                }
            )
        if component.confidence < 1.0 and component.display != "visual_unknown_glyph":
            anomalies.append(
                {
                    "kind": "low_confidence_glyph",
                    "component_id": component.component_id,
                    "blocking": True,
                    "reason": "foundation pass requires exact glyph matches",
                }
            )
    ordered = sorted(components, key=lambda item: (item.bounds[1], item.bounds[0]))
    for index, left in enumerate(ordered):
        for right in ordered[index + 1 :]:
            if _overlaps(left.bounds, right.bounds):
                anomalies.append(
                    {
                        "kind": "component_overlap",
                        "component_id": left.component_id,
                        "other_component_id": right.component_id,
                        "blocking": True,
                        "reason": "overlapping visual marks cannot be ordered safely",
                    }
                )
        if index + 1 < len(ordered):
            right = ordered[index + 1]
            same_line = abs(right.bounds[1] - left.bounds[1]) <= max(1, (left.bounds[3] - left.bounds[1]) // 2)
            gap = right.bounds[0] - left.bounds[2]
            if same_line and gap > expected_word_gap_pixels * max_word_gap_multiplier:
                anomalies.append(
                    {
                        "kind": "spacing_anomaly",
                        "component_id": left.component_id,
                        "other_component_id": right.component_id,
                        "blocking": False,
                        "gap_pixels": gap,
                        "reason": "gap is much larger than approved word spacing",
                    }
                )
    return anomalies

