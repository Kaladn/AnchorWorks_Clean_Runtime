from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "anchorworks_local_meta_count_overlay@1"


@dataclass(frozen=True)
class RendererCloudInput:
    query_symbols: list[str]
    source_local_cloud: dict[str, Any]
    global_awsc_cloud: dict[str, Any]
    locator_refs: list[dict[str, Any]]
    weights: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_local_meta_count_overlay(
    source_id: str,
    symbolized_flat_doc: dict[str, Any],
    locator_sidecar: str | Path | dict[str, Any],
    observed_map_debug: str | None = None,
) -> dict[str, Any]:
    local_symbol_counts: Counter[str] = Counter()
    relation_counts: Counter[tuple[str, str, str]] = Counter()
    block_relation_index: dict[str, dict[str, Any]] = {}
    top_local: dict[str, list[dict[str, Any]]] = {}

    for block in _flat_doc_blocks(symbolized_flat_doc):
        block_id = str(block.get("block_id") or f"block_{len(block_relation_index)}")
        symbols = _block_symbols(block)
        line_start = int(block.get("line_start", 0) or 0)
        line_end = int(block.get("line_end", line_start) or line_start)
        block_relations: Counter[tuple[str, str, str]] = Counter()
        for index, symbol in enumerate(symbols):
            local_symbol_counts[symbol] += 1
            for neighbor_index in range(max(0, index - 6), min(len(symbols), index + 7)):
                if neighbor_index == index:
                    continue
                offset_value = neighbor_index - index
                offset = f"+{offset_value}" if offset_value > 0 else str(offset_value)
                neighbor = symbols[neighbor_index]
                relation_counts[(symbol, offset, neighbor)] += 1
                block_relations[(symbol, offset, neighbor)] += 1
        block_relation_index[block_id] = {
            "block_id": block_id,
            "line_start": line_start,
            "line_end": line_end,
            "symbol_count": len(symbols),
            "relation_count": int(sum(block_relations.values())),
            "symbols": symbols,
        }

    by_root: dict[str, Counter[str]] = {}
    for (symbol, _offset, neighbor), count in relation_counts.items():
        by_root.setdefault(symbol, Counter())[neighbor] += int(count)
    for symbol, counter in by_root.items():
        top_local[symbol] = [
            {"symbol": neighbor, "count": int(count)}
            for neighbor, count in counter.most_common(12)
        ]

    overlay = {
        "schema_version": SCHEMA_VERSION,
        "source_id": str(source_id),
        "symbolized_flat_doc_ref": _flat_doc_ref(symbolized_flat_doc),
        "locator_ref": _locator_ref(locator_sidecar),
        "visual_ref_locator_ref": _visual_ref_locator_ref(symbolized_flat_doc),
        "local_relation_counts": [
            {"symbol": symbol, "offset": offset, "neighbor_symbol": neighbor, "count": int(count)}
            for (symbol, offset, neighbor), count in sorted(relation_counts.items())
        ],
        "local_symbol_counts": dict(sorted(local_symbol_counts.items())),
        "top_local_neighbors": top_local,
        "block_relation_index": block_relation_index,
        "created_from_observed_map": str(observed_map_debug or ""),
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
    }
    overlay["checksum"] = _checksum_payload(overlay)
    return overlay


def load_local_meta_count_overlay(path: str | Path) -> dict[str, Any]:
    overlay = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_local_meta_count_overlay(overlay)
    return overlay


def validate_local_meta_count_overlay(overlay: dict[str, Any]) -> bool:
    if overlay.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("invalid local overlay schema version")
    required = {
        "source_id",
        "symbolized_flat_doc_ref",
        "locator_ref",
        "local_relation_counts",
        "local_symbol_counts",
        "top_local_neighbors",
        "block_relation_index",
        "created_at",
        "checksum",
    }
    missing = sorted(key for key in required if key not in overlay)
    if missing:
        raise ValueError("local overlay missing fields: " + ", ".join(missing))
    expected = _checksum_payload(overlay)
    if str(overlay.get("checksum") or "") != expected:
        raise ValueError("local overlay checksum mismatch")
    return True


def query_local_overlay_cloud(query_symbols: list[str], overlay: dict[str, Any], top_k: int = 6) -> dict[str, Any]:
    validate_local_meta_count_overlay(overlay)
    query = [str(symbol or "").strip().casefold() for symbol in query_symbols if str(symbol or "").strip()]
    relation_rows = [row for row in overlay.get("local_relation_counts") or [] if isinstance(row, dict)]
    locator_refs = _locator_refs_for_symbols(query, overlay)
    totals: Counter[str] = Counter()
    support: dict[str, set[str]] = {}
    for row in relation_rows:
        symbol = str(row.get("symbol") or "").strip().casefold()
        neighbor = str(row.get("neighbor_symbol") or "").strip().casefold()
        count = int(row.get("count", 0) or 0)
        if count <= 0 or symbol not in set(query):
            continue
        totals[neighbor] += count
        support.setdefault(neighbor, set()).add(symbol)
    neighbors = [
        {
            "symbol": symbol,
            "count": int(count),
            "supporting_query_symbols": sorted(support.get(symbol, set())),
            "locator_refs": _locator_refs_for_symbols([symbol], overlay),
        }
        for symbol, count in totals.most_common(max(1, int(top_k or 6)))
    ]
    return {
        "schema_version": "anchorworks_local_overlay_cloud@1",
        "query_symbols": query,
        "neighbors": neighbors,
        "locator_refs": locator_refs,
        "count_source": "local_meta_overlay",
    }


def score_candidate(
    *,
    local_fit: float,
    global_fit: float,
    role_fit: float,
    source_locator_support: float,
    penalties: dict[str, float] | None = None,
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    active_weights = weights or {"local": 0.45, "global": 0.25, "role": 0.20, "source_locator": 0.10}
    penalty_total = sum(float(value or 0.0) for value in (penalties or {}).values())
    score = (
        active_weights["local"] * float(local_fit)
        + active_weights["global"] * float(global_fit)
        + active_weights["role"] * float(role_fit)
        + active_weights["source_locator"] * float(source_locator_support)
        - penalty_total
    )
    return {
        "score": round(score, 6),
        "weights": dict(active_weights),
        "penalty_total": round(penalty_total, 6),
    }


def renderer_cloud_input(
    *,
    query_symbols: list[str],
    source_local_cloud: dict[str, Any],
    global_awsc_cloud: dict[str, Any] | None = None,
    locator_refs: list[dict[str, Any]] | None = None,
    weights: dict[str, float] | None = None,
) -> RendererCloudInput:
    return RendererCloudInput(
        query_symbols=query_symbols,
        source_local_cloud=source_local_cloud,
        global_awsc_cloud=global_awsc_cloud or {},
        locator_refs=locator_refs or [],
        weights=weights or {"local": 0.45, "global": 0.25, "role": 0.20, "source_locator": 0.10},
    )


def _flat_doc_blocks(symbolized_flat_doc: dict[str, Any]) -> list[dict[str, Any]]:
    blocks = [row for row in symbolized_flat_doc.get("blocks") or [] if isinstance(row, dict)]
    if blocks:
        return blocks
    paragraphs = [row for row in symbolized_flat_doc.get("paragraphs") or [] if isinstance(row, dict)]
    return [
        {
            **row,
            "block_id": f"block_{int(row.get('paragraph_id', index) or index)}",
            "anchor_stream": row.get("resolved_anchors") or row.get("anchors") or [],
        }
        for index, row in enumerate(paragraphs)
    ]


def _block_symbols(block: dict[str, Any]) -> list[str]:
    raw = block.get("symbol_stream") or block.get("anchor_stream") or block.get("symbols") or []
    return [str(symbol or "").strip().casefold() for symbol in raw if str(symbol or "").strip()]


def _flat_doc_ref(symbolized_flat_doc: dict[str, Any]) -> str:
    return str(
        symbolized_flat_doc.get("saved_document_name")
        or symbolized_flat_doc.get("symbolized_flat_doc_ref")
        or symbolized_flat_doc.get("source_name")
        or ""
    )


def _locator_ref(locator_sidecar: str | Path | dict[str, Any]) -> str:
    if isinstance(locator_sidecar, dict):
        return str(locator_sidecar.get("path") or locator_sidecar.get("locator_ref") or "")
    return str(locator_sidecar)


def _visual_ref_locator_ref(symbolized_flat_doc: dict[str, Any]) -> str:
    return str(symbolized_flat_doc.get("visual_links_path") or symbolized_flat_doc.get("visual_ref_locator_ref") or "")


def _locator_refs_for_symbols(symbols: list[str], overlay: dict[str, Any]) -> list[dict[str, Any]]:
    symbol_set = {str(symbol or "").strip().casefold() for symbol in symbols if str(symbol or "").strip()}
    refs: list[dict[str, Any]] = []
    for block in (overlay.get("block_relation_index") or {}).values():
        if not isinstance(block, dict):
            continue
        block_symbols = {str(symbol or "").strip().casefold() for symbol in block.get("symbols") or []}
        if not symbol_set & block_symbols:
            continue
        refs.append({
            "block_id": str(block.get("block_id") or ""),
            "line_start": int(block.get("line_start", 0) or 0),
            "line_end": int(block.get("line_end", 0) or 0),
        })
    return refs


def _checksum_payload(overlay: dict[str, Any]) -> str:
    payload = {key: value for key, value in overlay.items() if key != "checksum"}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
