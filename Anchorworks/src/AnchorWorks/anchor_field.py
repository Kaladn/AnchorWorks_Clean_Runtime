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
CONTENT_BLOCKED_ANCHORS = AUXILIARY_GLUE | RELATION_GLUE | ARTICLE_GLUE | PUNCTUATION | set(QUESTION_DIRECTORS) | {"__NULL__"}


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


def _candidate_counter(
    field: AnchorField,
    anchors: list[str],
    blocked: set[str],
    content_blocked: set[str],
) -> tuple[Counter[str], set[str]]:
    combined: Counter[str] = Counter()
    blocked_as_content: set[str] = set()
    for anchor in anchors:
        neighbors = field.neighbors_for(anchor)
        combined.update(neighbors)
    for anchor in list(combined):
        if anchor in blocked:
            del combined[anchor]
            continue
        if anchor in content_blocked:
            blocked_as_content.add(anchor)
            del combined[anchor]
    return combined, blocked_as_content


def _future_health(
    field: AnchorField,
    candidate: str,
    *,
    seed_set: set[str],
    content_blocked: set[str],
    lookahead_k: int,
    min_future_content: int,
    max_future_glue_ratio: float,
    max_future_null_ratio: float,
) -> dict[str, Any]:
    future_raw = field.neighbors_for(candidate)
    total = sum(future_raw.values())
    if total <= 0:
        return {
            "future_cloud": [],
            "lookahead_score": -1.0,
            "future_content_count": 0,
            "future_glue_ratio": 1.0,
            "future_null_ratio": 1.0,
            "pattern_health": "anomalous",
            "rejected_reason": "future_cloud_empty",
        }
    future_glue = sum(count for anchor, count in future_raw.items() if anchor in content_blocked)
    future_null = sum(count for anchor, count in future_raw.items() if anchor == "__NULL__")
    future_counter = Counter({anchor: count for anchor, count in future_raw.items() if anchor not in content_blocked})
    future_rows = _top(future_counter, lookahead_k, {candidate}, set())[0]
    future_non_seed_rows = [anchor for anchor in future_rows if anchor not in seed_set]
    backlink_support = sum(1 for anchor in future_raw if anchor in seed_set)
    glue_ratio = future_glue / total if total else 1.0
    null_ratio = future_null / total if total else 1.0
    content_count = len(future_non_seed_rows)
    anomalous = (
        content_count < min_future_content
        or glue_ratio > max_future_glue_ratio
        or null_ratio > max_future_null_ratio
    )
    lookahead_score = (content_count / max(1, lookahead_k)) + (0.12 * backlink_support) - (0.6 * glue_ratio) - (0.8 * null_ratio)
    return {
        "future_cloud": future_rows,
        "lookahead_score": round(lookahead_score, 4),
        "future_content_count": content_count,
        "future_glue_ratio": round(glue_ratio, 4),
        "future_null_ratio": round(null_ratio, 4),
        "backlink_support": backlink_support,
        "pattern_health": "anomalous" if anomalous else "healthy",
        "rejected_reason": "future_cloud_null_or_glue_heavy" if anomalous else "",
    }


def choose_topk_with_lookahead(
    field: AnchorField,
    seed_anchors: list[str],
    *,
    query_frame: dict[str, Any] | None = None,
    top_k: int = 6,
    lookahead_k: int = 6,
    min_future_content: int = 2,
    max_future_glue_ratio: float = 0.45,
    max_future_null_ratio: float = 0.2,
) -> dict[str, Any]:
    seeds = [anchor for anchor in dict.fromkeys(str(anchor).strip() for anchor in seed_anchors) if anchor]
    content_blocked = set(CONTENT_BLOCKED_ANCHORS)
    if query_frame:
        content_blocked.update(str(anchor) for anchor in query_frame.get("content_blocked_anchors") or [])
    current_counter, blocked_as_content = _candidate_counter(field, seeds, set(seeds), content_blocked)
    current_total = max(1, max(current_counter.values()) if current_counter else 1)
    current_rows = current_counter.most_common(top_k * 3)
    candidates: list[dict[str, Any]] = []
    for rank, (anchor, count) in enumerate(current_rows, start=1):
        future = _future_health(
            field,
            anchor,
            seed_set=set(seeds),
            content_blocked=content_blocked,
            lookahead_k=lookahead_k,
            min_future_content=min_future_content,
            max_future_glue_ratio=max_future_glue_ratio,
            max_future_null_ratio=max_future_null_ratio,
        )
        current_score = count / current_total
        anomaly_penalty = 0.55 if future["pattern_health"] == "anomalous" else 0.0
        final_score = current_score + float(future["lookahead_score"]) - anomaly_penalty
        candidates.append(
            {
                "anchor": anchor,
                "rank": rank,
                "current_count": int(count),
                "current_score": round(current_score, 4),
                "final_score": round(final_score, 4),
                "anomaly_penalty": anomaly_penalty,
                **future,
            }
        )
    candidates.sort(key=lambda row: (-float(row["final_score"]), int(row["rank"]), str(row["anchor"])))
    chosen = next((row for row in candidates if row["pattern_health"] == "healthy"), candidates[0] if candidates else {})
    return {
        "schema_version": "anchorworks_anchor_topk_lookahead@1",
        "seed_anchors": seeds,
        "query_frame": query_frame or {},
        "chosen": chosen,
        "candidates": candidates[:top_k],
        "blocked_as_content": sorted(blocked_as_content),
        "lookahead": {
            "top_k": top_k,
            "lookahead_k": lookahead_k,
            "min_future_content": min_future_content,
            "max_future_glue_ratio": max_future_glue_ratio,
            "max_future_null_ratio": max_future_null_ratio,
        },
        "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
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
        raw_total = sum(combined.values())
        raw_null_ratio = (combined.get("__NULL__", 0) / raw_total) if raw_total else 0.0
        if level == "1" and raw_total and raw_null_ratio >= null_stop_ratio:
            level_rows[level] = ["__NULL__"] if "__NULL__" in combined else []
            blocked_as_content.add("__NULL__")
            stop_reason = "null_heavy_surface"
            break
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
