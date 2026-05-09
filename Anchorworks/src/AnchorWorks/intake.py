from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping
from typing import Any


DEFAULT_WINDOW_RADIUS = 6
EMOJI_ANCHOR = "__EMOJI__"
NULL_ANCHOR = "__NULL__"
_JOINED_APOSTROPHES = {"'", "\u2019"}
_REGIONAL_INDICATOR_START = 0x1F1E6
_REGIONAL_INDICATOR_END = 0x1F1FF
_EMOJI_MODIFIER_START = 0x1F3FB
_EMOJI_MODIFIER_END = 0x1F3FF
_VARIATION_SELECTORS = {"\uFE0E", "\uFE0F"}
_ZERO_WIDTH_JOINER = "\u200D"
_STRING_LITERAL_MIN_LENGTH = 32


def split_paragraphs(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return [paragraph for paragraph in re.split(r"\n\s*\n+", normalized) if paragraph.strip()]


def extract_anchor_rows(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for match in re.finditer(r"\S+", text):
        start = match.start()
        rows.extend(_decompose_non_whitespace_run(match.group(0), start))

    return rows


def extract_anchors(text: str) -> list[str]:
    return [row["anchor"] for row in extract_anchor_rows(text)]


def compose_anchor_stream(anchor: str) -> list[str]:
    if anchor == EMOJI_ANCHOR:
        return [EMOJI_ANCHOR]

    anchor = _normalize_anchor_identity(anchor)
    if _is_string_literal_surface(anchor):
        return list(anchor)

    parts: list[str] = []
    index = 0
    while index < len(anchor):
        char = anchor[index]
        if char.isalpha() or _is_surface_inline_apostrophe(anchor, index):
            start = index
            index += 1
            while index < len(anchor) and (anchor[index].isalpha() or _is_surface_inline_apostrophe(anchor, index)):
                index += 1
            parts.append(anchor[start:index])
            continue

        parts.append(char)
        index += 1

    return parts or [anchor]


def count_observed_anchors(text: str) -> Counter[str]:
    return Counter(extract_anchors(text))


def _decompose_non_whitespace_run(surface: str, surface_start: int) -> list[dict[str, Any]]:
    if _is_string_literal_surface(surface):
        normalized = _normalize_anchor_identity(surface)
        return [{
            "anchor": normalized,
            "surface": surface,
            "start": surface_start,
            "end": surface_start + len(surface),
            "kind": "string_literal",
            "count_eligible": False,
            "literal_stream": list(normalized),
        }]

    rows: list[dict[str, Any]] = []
    index = 0

    while index < len(surface):
        char = surface[index]

        if _is_emoji_base(char):
            end = _consume_emoji_sequence(surface, index)
            rows.append(_anchor_row(EMOJI_ANCHOR, surface[index:end], surface_start + index, surface_start + end))
            index = end
            continue

        if char.isdigit():
            rows.append(_anchor_row(char, char, surface_start + index, surface_start + index + 1))
            index += 1
            continue

        if char.isalpha() or _is_surface_inline_apostrophe(surface, index):
            start = index
            index += 1
            while index < len(surface) and (surface[index].isalpha() or _is_surface_inline_apostrophe(surface, index)):
                index += 1
            chunk = surface[start:index]
            if not _is_apostrophe_only_run(chunk):
                rows.append(_anchor_row(chunk, chunk, surface_start + start, surface_start + index))
            continue

        if char not in _JOINED_APOSTROPHES:
            rows.append(_anchor_row(char, char, surface_start + index, surface_start + index + 1))
        index += 1

    return rows


def _anchor_row(anchor: str, surface: str, start: int, end: int) -> dict[str, Any]:
    return {
        "anchor": _normalize_anchor_identity(anchor),
        "surface": surface,
        "start": start,
        "end": end,
        "kind": "anchor",
        "count_eligible": True,
    }


def _is_string_literal_surface(surface: str) -> bool:
    value = str(surface or "").strip()
    if len(value) < _STRING_LITERAL_MIN_LENGTH:
        return False
    if any(char.isspace() for char in value):
        return False
    has_alpha = any(char.isalpha() for char in value)
    has_digit = any(char.isdigit() for char in value)
    return has_alpha and has_digit


def _normalize_anchor_identity(anchor: str) -> str:
    if anchor == EMOJI_ANCHOR:
        return EMOJI_ANCHOR
    return str(anchor or "").replace("\u2018", "'").replace("\u2019", "'").lower()


def build_anchor_map(
    text: str,
    window_radius: int = DEFAULT_WINDOW_RADIUS,
    resolved_anchors: Mapping[str, str] | None = None,
    null_anchors: set[str] | None = None,
) -> dict[str, Any]:
    anchor_aliases = resolved_anchors or {}
    null_anchor_set = {str(anchor or "").lower() for anchor in (null_anchors or set()) if str(anchor or "")}
    paragraphs = split_paragraphs(text)
    paragraph_rows: list[dict[str, Any]] = []
    occurrences: list[dict[str, Any]] = []
    relation_counts: Counter[tuple[str, str, str]] = Counter()
    observed_counts: Counter[str] = Counter()

    for paragraph_id, paragraph in enumerate(paragraphs):
        anchor_rows = extract_anchor_rows(paragraph)
        anchors = [row["anchor"] for row in anchor_rows]
        count_eligible = [
            bool(row.get("count_eligible", True)) and row["anchor"] not in null_anchor_set
            for row in anchor_rows
        ]
        resolved_stream = [anchor_aliases.get(anchor, anchor) for anchor in anchors]
        composed_streams = [compose_anchor_stream(anchor) for anchor in anchors]
        paragraph_rows.append({
            "paragraph_id": paragraph_id,
            "anchor_count": len(anchors),
            "countable_anchor_count": sum(1 for eligible in count_eligible if eligible),
            "anchors": anchors,
            "resolved_anchors": resolved_stream,
            "composed_anchor_streams": composed_streams,
            "composed_anchor_stream": [part for stream in composed_streams for part in stream],
            "text": paragraph,
        })
        observed_counts.update(anchor for anchor, eligible in zip(resolved_stream, count_eligible) if eligible)

        for position, row in enumerate(anchor_rows):
            observed_anchor = row["anchor"]
            anchor = resolved_stream[position]
            composed_anchor_stream = composed_streams[position]
            current_count_eligible = count_eligible[position]
            window: dict[str, str | None] = {}
            for offset in range(-window_radius, window_radius + 1):
                offset_key = _offset_key(offset)
                if offset == 0:
                    window[offset_key] = anchor
                    continue

                neighbor_index = position + offset
                if 0 <= neighbor_index < len(anchors):
                    neighbor = anchors[neighbor_index]
                    window[offset_key] = neighbor
                    if current_count_eligible and count_eligible[neighbor_index]:
                        relation_counts[(anchor, offset_key, neighbor)] += 1
                else:
                    window[offset_key] = None

            previous_end = anchor_rows[position - 1]["end"] if position > 0 else 0
            next_start = anchor_rows[position + 1]["start"] if position + 1 < len(anchor_rows) else len(paragraph)
            gap_before = paragraph[previous_end:row["start"]]
            gap_after = paragraph[row["end"]:next_start]
            occurrences.append({
                "anchor": anchor,
                "observed_anchor": observed_anchor,
                "surface": row["surface"],
                "kind": row.get("kind", "anchor"),
                "count_eligible": current_count_eligible,
                "literal_stream": row.get("literal_stream", []),
                "composed_anchor_stream": composed_anchor_stream,
                "position": position,
                "paragraph_id": paragraph_id,
                "start": row["start"],
                "end": row["end"],
                "gap_before": gap_before,
                "gap_after": gap_after,
                "joined_left": gap_before == "",
                "joined_right": gap_after == "",
                "window": window,
            })

    relation_rows = [
        {
            "anchor": anchor,
            "offset": offset,
            "neighbor": neighbor,
            "observations": count,
        }
        for (anchor, offset, neighbor), count in sorted(
            relation_counts.items(),
            key=lambda item: (-item[1], item[0][0], item[0][1], item[0][2]),
        )
    ]
    items, anchor_index = build_context_views(
        relation_rows,
        observed_counts=observed_counts,
        window_radius=window_radius,
    )
    total_anchor_observations = int(sum(observed_counts.values()))
    total_relation_observations = int(sum(row["observations"] for row in relation_rows))

    return {
        "paragraph_count": len(paragraph_rows),
        "window_radius": window_radius,
        "paragraphs": paragraph_rows,
        "occurrences": occurrences,
        "observed_counts": observed_counts,
        "co_occurrence_counts": relation_rows,
        "items": items,
        "anchor_index": anchor_index,
        "stats": {
            "paragraph_count": len(paragraph_rows),
            "total_anchor_observations": total_anchor_observations,
            "unique_anchor_count": len(observed_counts),
            "unique_relations": len(relation_rows),
            "total_relation_observations": total_relation_observations,
        },
    }


def build_context_views(
    relation_rows: list[dict[str, Any]],
    observed_counts: Mapping[str, int] | None = None,
    window_radius: int = DEFAULT_WINDOW_RADIUS,
    top_k: int = 6,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    observed_map = Counter(observed_counts or {})
    anchors = set(observed_map)
    buckets: dict[str, dict[str, dict[str, Counter[str]]]] = {}

    def ensure_anchor(anchor: str) -> dict[str, dict[str, Counter[str]]]:
        row = buckets.get(anchor)
        if row is None:
            row = {
                "before": {str(distance): Counter() for distance in range(1, window_radius + 1)},
                "after": {str(distance): Counter() for distance in range(1, window_radius + 1)},
            }
            buckets[anchor] = row
        return row

    for relation in relation_rows:
        anchor = relation.get("anchor")
        offset = relation.get("offset")
        neighbor = relation.get("neighbor")
        count = int(relation.get("observations", 0) or 0)
        if not isinstance(anchor, str) or not isinstance(offset, str) or not isinstance(neighbor, str):
            continue
        if count <= 0 or offset == "0":
            continue

        try:
            distance_value = abs(int(offset))
        except ValueError:
            continue
        if distance_value < 1 or distance_value > window_radius:
            continue

        direction = "before" if offset.startswith("-") else "after"
        distance = str(distance_value)
        ensure_anchor(anchor)[direction][distance][neighbor] += count
        anchors.add(anchor)

    items: dict[str, dict[str, Any]] = {}
    anchor_index: list[dict[str, Any]] = []

    for anchor in sorted(anchors):
        anchor_buckets = ensure_anchor(anchor)
        before = _bucket_rows(anchor_buckets["before"], top_k=top_k)
        after = _bucket_rows(anchor_buckets["after"], top_k=top_k)
        total_neighbor_observations = (
            sum(sum(counter.values()) for counter in anchor_buckets["before"].values())
            + sum(sum(counter.values()) for counter in anchor_buckets["after"].values())
        )
        item = {
            "anchor": anchor,
            "center_anchor": anchor,
            "center_observations": int(observed_map.get(anchor, 0)),
            "before": before,
            "after": after,
            "total_neighbor_observations": int(total_neighbor_observations),
        }
        items[anchor] = item
        anchor_index.append({
            "anchor": anchor,
            "count": int(total_neighbor_observations),
            "center_observations": int(observed_map.get(anchor, 0)),
        })

    anchor_index.sort(key=lambda item: (-int(item["count"]), item["anchor"]))
    return items, anchor_index


def _bucket_rows(
    bucket_map: Mapping[str, Counter[str]],
    top_k: int,
) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for distance, counter in sorted(bucket_map.items(), key=lambda item: int(item[0])):
        out[distance] = [
            {
                "anchor": anchor,
                "word": anchor,
                "count": count,
            }
            for anchor, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:top_k]
        ]
    return out


def _is_inline_apostrophe(text: str, index: int) -> bool:
    if text[index] not in _JOINED_APOSTROPHES:
        return False
    prev_is_alnum = index > 0 and text[index - 1].isalnum()
    next_is_alnum = index + 1 < len(text) and text[index + 1].isalnum()
    return prev_is_alnum or next_is_alnum


def _is_surface_inline_apostrophe(surface: str, index: int) -> bool:
    if surface[index] not in _JOINED_APOSTROPHES:
        return False
    prev_is_alnum = index > 0 and surface[index - 1].isalnum()
    next_is_alnum = index + 1 < len(surface) and surface[index + 1].isalnum()
    if prev_is_alnum and next_is_alnum:
        return True
    return prev_is_alnum and surface[index - 1].casefold() == "s"


def _is_apostrophe_only_run(surface: str) -> bool:
    return bool(surface) and all(char in _JOINED_APOSTROPHES for char in surface)


def _extract_pure_emoji_run_rows(surface: str, surface_start: int) -> list[dict[str, Any]] | None:
    if not surface:
        return None

    rows: list[dict[str, Any]] = []
    index = 0
    while index < len(surface):
        char = surface[index]
        if not _is_emoji_base(char):
            return None

        end = _consume_emoji_sequence(surface, index)
        rows.append({
            "anchor": EMOJI_ANCHOR,
            "surface": surface[index:end],
            "start": surface_start + index,
            "end": surface_start + end,
        })
        index = end

    return rows


def _consume_emoji_sequence(text: str, start: int) -> int:
    index = start + 1

    if _is_regional_indicator(text[start]):
        while index < len(text) and _is_regional_indicator(text[index]):
            index += 1
        return index

    while index < len(text):
        char = text[index]
        if _is_emoji_modifier(char) or char in _VARIATION_SELECTORS:
            index += 1
            continue
        if char == _ZERO_WIDTH_JOINER and index + 1 < len(text) and _is_emoji_base(text[index + 1]):
            index += 2
            continue
        break

    return index


def _is_emoji_base(char: str) -> bool:
    codepoint = ord(char)
    if _is_regional_indicator(char):
        return True
    if 0x1F300 <= codepoint <= 0x1FAFF:
        return True
    if 0x2600 <= codepoint <= 0x27BF:
        return True
    return False


def _is_regional_indicator(char: str) -> bool:
    codepoint = ord(char)
    return _REGIONAL_INDICATOR_START <= codepoint <= _REGIONAL_INDICATOR_END


def _is_emoji_modifier(char: str) -> bool:
    codepoint = ord(char)
    return _EMOJI_MODIFIER_START <= codepoint <= _EMOJI_MODIFIER_END


def _offset_key(offset: int) -> str:
    if offset > 0:
        return f"+{offset}"
    return str(offset)
