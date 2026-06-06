from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from .intake import DEFAULT_WINDOW_RADIUS, NULL_ANCHOR, extract_anchor_rows, split_paragraphs


def build_symbol_relation_map(
    text: str,
    *,
    symbol_by_anchor: Mapping[str, str | int],
    resolved_anchors: Mapping[str, str] | None = None,
    null_anchors: set[str] | None = None,
    window_radius: int = DEFAULT_WINDOW_RADIUS,
) -> dict[str, Any]:
    anchor_aliases = resolved_anchors or {}
    null_anchor_set = {str(anchor or "").lower() for anchor in (null_anchors or set()) if str(anchor or "")}
    paragraph_rows: list[dict[str, Any]] = []
    observed_counts: Counter[str] = Counter()

    for paragraph_id, paragraph in enumerate(split_paragraphs(text)):
        anchor_rows = extract_anchor_rows(paragraph)
        anchors = [row["anchor"] for row in anchor_rows]
        count_eligible = [
            bool(row.get("count_eligible", True)) and row["anchor"] not in null_anchor_set
            for row in anchor_rows
        ]
        resolved_stream = [anchor_aliases.get(anchor, anchor) for anchor in anchors]
        observed_counts.update(anchor for anchor, eligible in zip(resolved_stream, count_eligible) if eligible)
        paragraph_rows.append({
            "paragraph_id": paragraph_id,
            "anchor_count": len(anchors),
            "countable_anchor_count": sum(1 for eligible in count_eligible if eligible),
            "anchors": anchors,
            "resolved_anchors": resolved_stream,
            "count_eligible": count_eligible,
        })

    relation_rows = build_symbol_relation_rows(
        paragraph_rows,
        symbol_by_anchor=symbol_by_anchor,
        window_radius=window_radius,
    )
    return {
        "paragraph_count": len(paragraph_rows),
        "window_radius": window_radius,
        "paragraphs": paragraph_rows,
        "observed_counts": observed_counts,
        "symbol_relation_counts": relation_rows,
        "stats": {
            "paragraph_count": len(paragraph_rows),
            "total_anchor_observations": int(sum(observed_counts.values())),
            "unique_anchor_count": len(observed_counts),
            "unique_symbol_relations": len(relation_rows),
            "total_symbol_relation_observations": int(sum(row["observations"] for row in relation_rows)),
        },
    }


def pack_symbol_id(symbol: str | int) -> int:
    if isinstance(symbol, int):
        return symbol
    value = str(symbol or "").strip()
    if not value:
        raise ValueError("empty symbol")
    if value.lower().startswith("0x"):
        value = value[2:]
    return int(value, 16)


def build_source_local_symbol_table(
    anchors: Sequence[str],
    *,
    canonical_symbol_by_anchor: Mapping[str, str | int],
    symbol_authority_by_anchor: Mapping[str, Any] | None = None,
    source_id: str,
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    symbol_by_anchor: dict[str, str] = {}
    authority_rows: list[dict[str, Any]] = []
    authority_map = symbol_authority_by_anchor or {}
    seen = sorted({str(anchor) for anchor in anchors if str(anchor)})
    for anchor in seen:
        authority_entry = authority_map.get(anchor)
        if authority_entry is not None:
            display, authority = _symbol_authority_entry(authority_entry)
            symbol_by_anchor[anchor] = display
        else:
            canonical_symbol = canonical_symbol_by_anchor.get(anchor)
            if canonical_symbol is not None:
                display = _display_symbol(canonical_symbol)
                symbol_by_anchor[anchor] = display
                authority = "canonical"
            else:
                display = _source_local_symbol(anchor, source_id)
                symbol_by_anchor[anchor] = display
                authority = "source_local"
        authority_rows.append({
            "anchor": anchor,
            "symbol": display,
            "authority": authority,
        })
    return symbol_by_anchor, authority_rows


def _symbol_authority_entry(value: Any) -> tuple[str, str]:
    if isinstance(value, dict):
        symbol = value.get("symbol") or value.get("hex")
        authority = value.get("authority") or "canonical"
    elif isinstance(value, (tuple, list)) and len(value) >= 2:
        symbol, authority = value[0], value[1]
    else:
        symbol = value
        authority = "canonical"
    display = _display_symbol(symbol)
    if not display:
        raise ValueError("symbol authority entry requires a symbol")
    clean_authority = str(authority or "canonical").strip().casefold()
    return display, clean_authority


def build_symbol_relation_rows(
    paragraphs: Sequence[Mapping[str, Any]],
    *,
    symbol_by_anchor: Mapping[str, str | int],
    window_radius: int = DEFAULT_WINDOW_RADIUS,
) -> list[dict[str, Any]]:
    relation_counts: Counter[tuple[int, str, int]] = Counter()
    display_by_id: dict[int, str] = {}
    packed_by_anchor: dict[str, int | None] = {}

    for paragraph in paragraphs:
        anchors = list(paragraph.get("resolved_anchors") or paragraph.get("anchors") or [])
        eligibility = list(paragraph.get("count_eligible") or [True] * len(anchors))
        limit = min(len(anchors), len(eligibility))
        anchors = anchors[:limit]
        eligibility = eligibility[:limit]

        symbol_ids: list[int | None] = []
        countable: list[bool] = []
        for anchor, eligible in zip(anchors, eligibility):
            anchor_text = str(anchor)
            symbol_id = _resolve_symbol_id(anchor_text, symbol_by_anchor, packed_by_anchor, display_by_id)
            is_countable = bool(eligible) and anchor_text != NULL_ANCHOR and symbol_id is not None
            symbol_ids.append(symbol_id)
            countable.append(is_countable)

        for position, symbol_id in enumerate(symbol_ids):
            if symbol_id is None or not countable[position]:
                continue
            for offset in range(-window_radius, window_radius + 1):
                if offset == 0:
                    continue
                neighbor_index = position + offset
                if neighbor_index < 0 or neighbor_index >= len(symbol_ids):
                    continue
                neighbor_id = symbol_ids[neighbor_index]
                if neighbor_id is None or not countable[neighbor_index]:
                    continue
                relation_counts[(symbol_id, _offset_key(offset), neighbor_id)] += 1

    return [
        {
            "symbol_id": symbol_id,
            "symbol_anchor": display_by_id.get(symbol_id, f"0x{symbol_id:010X}"),
            "offset": offset,
            "neighbor_symbol_id": neighbor_id,
            "neighbor_symbol_anchor": display_by_id.get(neighbor_id, f"0x{neighbor_id:010X}"),
            "observations": observations,
        }
        for (symbol_id, offset, neighbor_id), observations in sorted(
            relation_counts.items(),
            key=lambda item: (-item[1], item[0][0], item[0][1], item[0][2]),
        )
    ]


def _offset_key(offset: int) -> str:
    return f"+{offset}" if offset > 0 else str(offset)


def _display_symbol(symbol: str | int) -> str:
    if isinstance(symbol, int):
        return f"0x{symbol:010X}"
    value = str(symbol or "").strip()
    if not value:
        return ""
    return value if value.lower().startswith("0x") else f"0x{value.upper()}"


def _source_local_symbol(anchor: str, source_id: str) -> str:
    digest = hashlib.sha1(f"{source_id}\n{anchor}".encode("utf-8")).hexdigest().upper()
    return f"0xF{digest[:9]}"


def _resolve_symbol_id(
    anchor: str,
    symbol_by_anchor: Mapping[str, str | int],
    packed_by_anchor: dict[str, int | None],
    display_by_id: dict[int, str],
) -> int | None:
    if anchor in packed_by_anchor:
        return packed_by_anchor[anchor]
    symbol = symbol_by_anchor.get(anchor)
    if symbol is None:
        packed_by_anchor[anchor] = None
        return None
    packed = pack_symbol_id(symbol)
    packed_by_anchor[anchor] = packed
    display_by_id[packed] = _display_symbol(symbol)
    return packed
