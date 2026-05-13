from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AnchorField:
    source_name: str
    window_radius: int
    stream: list[str]
    positions: list[dict[str, Any]]

    @property
    def anchor_count(self) -> int:
        return len(self.stream)

    def positions_for(self, anchor: str) -> list[int]:
        return [index for index, value in enumerate(self.stream) if value == anchor]

    def neighbors_for(self, anchor: str) -> Counter[str]:
        neighbors: Counter[str] = Counter()
        for index in self.positions_for(anchor):
            start = max(0, index - self.window_radius)
            end = min(len(self.stream), index + self.window_radius + 1)
            for neighbor_index in range(start, end):
                if neighbor_index == index:
                    continue
                neighbor = self.stream[neighbor_index]
                if neighbor:
                    neighbors[neighbor] += 1
        return neighbors


def build_anchor_field_from_observed_map(observed_map: dict[str, Any]) -> AnchorField:
    stream: list[str] = []
    positions: list[dict[str, Any]] = []
    for paragraph in observed_map.get("paragraphs") or []:
        paragraph_id = int(paragraph.get("paragraph_id", 0) or 0)
        for anchor in paragraph.get("anchors") or []:
            clean = str(anchor or "").strip()
            if not clean:
                continue
            positions.append({"paragraph_id": paragraph_id, "position": len(stream), "anchor": clean})
            stream.append(clean)
    return AnchorField(
        source_name=str(observed_map.get("source_name") or ""),
        window_radius=int(observed_map.get("window_radius", 6) or 6),
        stream=stream,
        positions=positions,
    )


def _top(counter: Counter[str], limit: int, blocked: set[str]) -> list[str]:
    rows = [
        (anchor, count)
        for anchor, count in counter.items()
        if anchor not in blocked
    ]
    rows.sort(key=lambda item: (-item[1], item[0]))
    return [anchor for anchor, _count in rows[:limit]]


def _shape_summary(levels: dict[str, list[str]]) -> dict[str, Any]:
    anchors = [anchor for level in levels.values() for anchor in level]
    if not anchors:
        return {"anchor_count": 0, "null_count": 0, "non_null_ratio": 0.0}
    null_count = sum(1 for anchor in anchors if anchor == "__NULL__")
    return {
        "anchor_count": len(anchors),
        "null_count": null_count,
        "non_null_ratio": round((len(anchors) - null_count) / len(anchors), 4),
    }


def skim_three_level_cloud(
    field: AnchorField,
    seed_anchors: list[str],
    *,
    max_level_width: int = 6,
    null_stop_ratio: float = 0.75,
) -> dict[str, Any]:
    seeds = [anchor for anchor in dict.fromkeys(str(anchor).strip() for anchor in seed_anchors) if anchor]
    blocked = set(seeds)
    level_rows: dict[str, list[str]] = {"1": [], "2": [], "3": []}
    frontier = seeds
    stop_reason = ""
    support: dict[str, dict[str, int]] = defaultdict(dict)
    for level in ("1", "2", "3"):
        combined: Counter[str] = Counter()
        for anchor in frontier:
            neighbors = field.neighbors_for(anchor)
            combined.update(neighbors)
            for neighbor, count in neighbors.items():
                support.setdefault(neighbor, {})[anchor] = int(count)
        selected = _top(combined, max_level_width, blocked)
        level_rows[level] = selected
        blocked.update(selected)
        shape = _shape_summary({level: selected})
        if level == "1" and shape["anchor_count"]:
            null_ratio = shape["null_count"] / shape["anchor_count"]
            if null_ratio >= null_stop_ratio:
                stop_reason = "null_heavy_surface"
                break
        frontier = selected
        if not frontier:
            stop_reason = "frontier_empty"
            break
    if stop_reason:
        for level in ("1", "2", "3"):
            if not level_rows[level]:
                continue
            if level_rows[level] == frontier:
                continue
    return {
        "schema_version": "anchorworks_anchor_field_cloud@1",
        "source_name": field.source_name,
        "seed_anchors": seeds,
        "levels": level_rows,
        "shape": _shape_summary(level_rows),
        "support": support,
        "stop_reason": stop_reason or "level_3_cap",
        "runtime_surface": "in_memory_anchor_field",
        "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
    }
