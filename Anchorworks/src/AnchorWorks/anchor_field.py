from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

QUESTION_DIRECTORS = {
    "how": ("question_method", 1.0),
    "what": ("question_identity", 1.0),
    "why": ("question_cause", 1.0),
    "when": ("question_time", 1.0),
    "where": ("question_place", 1.0),
    "who": ("question_actor", 1.0),
}
AUXILIARY_GLUE = {"do", "does", "did", "is", "are", "was", "were", "can", "should", "would", "could"}
RELATION_GLUE = {"of", "to", "for", "with", "from", "in", "on", "by", "as", "at", "into", "over", "under"}
ARTICLE_GLUE = {"the", "a", "an"}
PRONOUN_ROLE = {"i": "speaker_subject", "me": "speaker_object", "you": "user_target", "we": "speaker_group", "it": "reference_subject", "they": "reference_group"}
PUNCTUATION = {".", ",", "?", "!", ":", ";", "(", ")", "[", "]", "{", "}", "\"", "'", "-", "/", "\\"}
CONTENT_BLOCKED_ANCHORS = AUXILIARY_GLUE | RELATION_GLUE | ARTICLE_GLUE | PUNCTUATION | set(QUESTION_DIRECTORS)


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


def build_query_frame(query_anchors: list[str]) -> dict[str, Any]:
    unique = [anchor for anchor in dict.fromkeys(str(anchor).strip().lower() for anchor in query_anchors) if anchor]
    director_rows: list[dict[str, Any]] = []
    content_seeds: list[str] = []
    frame = "statement"
    for anchor in unique:
        if anchor in QUESTION_DIRECTORS:
            role, weight = QUESTION_DIRECTORS[anchor]
            if role == "question_method":
                frame = "method_question"
            elif frame == "statement":
                frame = "question"
            director_rows.append({"anchor": anchor, "role": role, "weight": weight})
            continue
        if anchor in AUXILIARY_GLUE:
            director_rows.append({"anchor": anchor, "role": "auxiliary", "weight": 0.2})
            continue
        if anchor in RELATION_GLUE:
            director_rows.append({"anchor": anchor, "role": "relation_director", "weight": 0.35})
            continue
        if anchor in ARTICLE_GLUE:
            director_rows.append({"anchor": anchor, "role": "article_glue", "weight": 0.1})
            continue
        if anchor in PRONOUN_ROLE:
            director_rows.append({"anchor": anchor, "role": PRONOUN_ROLE[anchor], "weight": 0.4})
            continue
        if anchor in PUNCTUATION:
            director_rows.append({"anchor": anchor, "role": "punctuation", "weight": 0.0})
            continue
        content_seeds.append(anchor)
    return {
        "schema_version": "anchorworks_query_frame@1",
        "frame": frame,
        "query_anchors": unique,
        "content_seeds": content_seeds,
        "director_anchors": director_rows,
        "content_blocked_anchors": sorted(CONTENT_BLOCKED_ANCHORS),
    }


def _top(
    counter: Counter[str],
    limit: int,
    blocked: set[str],
    content_blocked: set[str] | None = None,
) -> tuple[list[str], list[str]]:
    content_blocked = content_blocked or set()
    blocked_as_content: list[str] = []
    rows = [
        (anchor, count)
        for anchor, count in counter.items()
        if anchor not in blocked and anchor not in content_blocked
    ]
    for anchor, _count in counter.items():
        if anchor not in blocked and anchor in content_blocked:
            blocked_as_content.append(anchor)
    rows.sort(key=lambda item: (-item[1], item[0]))
    return [anchor for anchor, _count in rows[:limit]], sorted(set(blocked_as_content))


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
    query_frame: dict[str, Any] | None = None,
    max_level_width: int = 6,
    null_stop_ratio: float = 0.75,
) -> dict[str, Any]:
    seeds = [anchor for anchor in dict.fromkeys(str(anchor).strip() for anchor in seed_anchors) if anchor]
    blocked = set(seeds)
    content_blocked = set(CONTENT_BLOCKED_ANCHORS)
    if query_frame:
        content_blocked.update(str(anchor) for anchor in query_frame.get("content_blocked_anchors") or [])
    level_rows: dict[str, list[str]] = {"1": [], "2": [], "3": []}
    frontier = seeds
    stop_reason = ""
    support: dict[str, dict[str, int]] = defaultdict(dict)
    blocked_as_content: set[str] = set()
    for level in ("1", "2", "3"):
        combined: Counter[str] = Counter()
        for anchor in frontier:
            neighbors = field.neighbors_for(anchor)
            combined.update(neighbors)
            for neighbor, count in neighbors.items():
                support.setdefault(neighbor, {})[anchor] = int(count)
        selected, blocked_here = _top(combined, max_level_width, blocked, content_blocked)
        blocked_as_content.update(blocked_here)
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
        "query_frame": query_frame or {},
        "blocked_as_content": sorted(blocked_as_content),
        "stop_reason": stop_reason or "level_3_cap",
        "runtime_surface": "in_memory_anchor_field",
        "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
    }
