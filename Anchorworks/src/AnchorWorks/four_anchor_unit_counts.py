from __future__ import annotations

import hashlib
import json
import os
import struct
import zlib
from collections import Counter
from pathlib import Path
from typing import Any


MAGIC = b"AWU4"
VERSION = 1
HEADER_SIZE = 32
ROW_SIZE = 26
UNIT_SIZE = 4
DEFAULT_WINDOW_RADIUS = 6

_HEADER = struct.Struct("<4sHHQQII")
_ROW = struct.Struct("<QQbBQ")


def build_four_anchor_units(
    anchors: list[str],
    *,
    partial_policy: str = "drop",
) -> dict[str, Any]:
    clean_anchors = [str(anchor or "").strip().casefold() for anchor in anchors if str(anchor or "").strip()]
    if partial_policy != "drop":
        raise ValueError("only partial_policy='drop' is supported in v1")
    units: list[dict[str, Any]] = []
    full_length = (len(clean_anchors) // UNIT_SIZE) * UNIT_SIZE
    for start in range(0, full_length, UNIT_SIZE):
        unit_anchors = clean_anchors[start : start + UNIT_SIZE]
        units.append(_unit_record(unit_index=len(units), anchor_start=start, anchors=unit_anchors))
    return {
        "schema_version": "anchorworks_four_anchor_units@1",
        "unit_size": UNIT_SIZE,
        "partial_policy": partial_policy,
        "anchor_count": len(clean_anchors),
        "unit_count": len(units),
        "units": units,
        "partial_tail": clean_anchors[full_length:],
        "truth_boundary": {
            "fixed_ordered_groups_from_document_start": True,
            "semantic_grouping": False,
            "sentence_splitting": False,
            "partial_tail_not_counted": True,
        },
    }


def build_four_anchor_unit_counts(
    anchors: list[str],
    *,
    source_id: str = "",
    window_radius: int = DEFAULT_WINDOW_RADIUS,
    partial_policy: str = "drop",
) -> dict[str, Any]:
    units_payload = build_four_anchor_units(anchors, partial_policy=partial_policy)
    units = list(units_payload["units"])
    radius = int(window_radius)
    if radius <= 0:
        raise ValueError("window_radius must be positive")

    relation_counter: Counter[tuple[int, int, int]] = Counter()
    for center_index, center in enumerate(units):
        for offset in range(-radius, radius + 1):
            if offset == 0:
                continue
            neighbor_index = center_index + offset
            if neighbor_index < 0 or neighbor_index >= len(units):
                continue
            relation_counter[(int(center["unit_id"]), offset, int(units[neighbor_index]["unit_id"]))] += 1

    relation_counts = [
        {
            "center_unit_id": center_unit_id,
            "center_unit_symbol": _unit_symbol(center_unit_id),
            "offset": _offset_key(offset),
            "neighbor_unit_id": neighbor_unit_id,
            "neighbor_unit_symbol": _unit_symbol(neighbor_unit_id),
            "observations": observations,
        }
        for (center_unit_id, offset, neighbor_unit_id), observations in sorted(
            relation_counter.items(),
            key=lambda item: (item[0][0], item[0][1], item[0][2]),
        )
    ]

    windows: list[dict[str, Any]] = []
    for center_index in range(radius, len(units) - radius):
        windows.append(
            {
                "schema_version": "anchorworks_four_anchor_unit_window@1",
                "window_shape": f"{radius}-1-{radius} over unit4",
                "center_index": center_index,
                "left_units": units[center_index - radius : center_index],
                "center_unit": units[center_index],
                "right_units": units[center_index + 1 : center_index + radius + 1],
            }
        )

    return {
        "schema_version": "anchorworks_four_anchor_unit_counts@1",
        "count_layer": "four_anchor_unit_sibling",
        "source_id": str(source_id or ""),
        "unit_size": UNIT_SIZE,
        "window_radius": radius,
        "window_shape": f"{radius}-1-{radius} over unit4",
        "anchor_count": units_payload["anchor_count"],
        "unit_count": len(units),
        "full_window_count": len(windows),
        "units": units,
        "windows": windows,
        "relation_counts": relation_counts,
        "partial_tail": units_payload["partial_tail"],
        "truth_boundary": {
            "sibling_to_solo_anchor_counts": True,
            "solo_anchor_counts_unchanged": True,
            "unit_anchor_is_four_ordered_anchors": True,
            "semantic_grouping": False,
            "lexicon_promotion": False,
        },
        "writes_allowed": {"solo_counts": False, "unit4_counts": True, "lexicon": False, "lifetime": False},
    }


def write_four_anchor_unit_counts_binary(
    *,
    root: Path | str,
    count_payload: dict[str, Any],
    shard_id: str,
) -> dict[str, Any]:
    shard_root = Path(root) / "four_anchor_unit_counts" / "shards" / str(shard_id)
    shard_root.mkdir(parents=True, exist_ok=True)
    rows = [
        (
            int(row["center_unit_id"]),
            int(row["neighbor_unit_id"]),
            _parse_offset(row["offset"]),
            0,
            int(row["observations"]),
        )
        for row in count_payload.get("relation_counts") or []
    ]
    payload = b"".join(_ROW.pack(*row) for row in rows)
    checksum = zlib.crc32(payload) & 0xFFFFFFFF
    header = _HEADER.pack(MAGIC, VERSION, HEADER_SIZE, len(rows), ROW_SIZE, len(payload), checksum)
    if len(header) != HEADER_SIZE:
        raise AssertionError("AWU4 header layout must be 32 bytes")
    binary_path = shard_root / f"{shard_id}.awu4"
    temp_path = binary_path.with_name(f"{binary_path.name}.tmp")
    temp_path.write_bytes(header + payload)
    os.replace(temp_path, binary_path)
    binary_sha = _hash_file(binary_path)
    manifest = {
        "schema_version": "anchorworks_four_anchor_unit_counts_binary_manifest@1",
        "shard_id": str(shard_id),
        "count_layer": "four_anchor_unit_sibling",
        "binary_path": str(binary_path),
        "binary_sha256": binary_sha,
        "unit_size": int(count_payload.get("unit_size") or UNIT_SIZE),
        "window_radius": int(count_payload.get("window_radius") or DEFAULT_WINDOW_RADIUS),
        "window_shape": str(count_payload.get("window_shape") or "6-1-6 over unit4"),
        "unit_count": int(count_payload.get("unit_count") or 0),
        "relation_count": len(rows),
        "units": list(count_payload.get("units") or []),
        "truth_boundary": {
            "sibling_to_solo_anchor_counts": True,
            "solo_anchor_counts_unchanged": True,
            "binary_rows_are_unit_relations": True,
        },
        "writes_allowed": {"solo_counts": False, "unit4_counts": True, "lexicon": False, "lifetime": False},
    }
    manifest_path = shard_root / f"{shard_id}.awu4_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "schema_version": "anchorworks_four_anchor_unit_counts_binary_write@1",
        "shard_id": str(shard_id),
        "manifest_path": str(manifest_path),
        "binary_path": str(binary_path),
        "binary_sha256": binary_sha,
        "relation_count": len(rows),
    }


def read_four_anchor_unit_counts_binary(manifest_path: Path | str) -> dict[str, Any]:
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    binary_path = Path(manifest["binary_path"])
    if _hash_file(binary_path) != manifest["binary_sha256"]:
        raise ValueError("four-anchor unit count binary hash mismatch")
    raw = binary_path.read_bytes()
    if len(raw) < HEADER_SIZE:
        raise ValueError("four-anchor unit count binary is shorter than header")
    magic, version, header_size, row_count, row_size, payload_size, checksum = _HEADER.unpack(raw[:HEADER_SIZE])
    if magic != MAGIC:
        raise ValueError("invalid four-anchor unit count magic")
    if version != VERSION or header_size != HEADER_SIZE:
        raise ValueError("unsupported four-anchor unit count binary version")
    if row_size != ROW_SIZE:
        raise ValueError("unsupported four-anchor unit count row size")
    payload = raw[HEADER_SIZE:]
    if len(payload) != payload_size or len(payload) != row_count * row_size:
        raise ValueError("four-anchor unit count payload size mismatch")
    if (zlib.crc32(payload) & 0xFFFFFFFF) != checksum:
        raise ValueError("four-anchor unit count CRC mismatch")
    rows = [
        _ROW.unpack(payload[index : index + ROW_SIZE])
        for index in range(0, len(payload), ROW_SIZE)
    ]
    return {
        "schema_version": "anchorworks_four_anchor_unit_counts_binary_loaded@1",
        "manifest": manifest,
        "relation_count": int(row_count),
        "relations": [
            {
                "center_unit_id": center,
                "center_unit_symbol": _unit_symbol(center),
                "neighbor_unit_id": neighbor,
                "neighbor_unit_symbol": _unit_symbol(neighbor),
                "offset": _offset_key(offset),
                "flags": flags,
                "observations": observations,
            }
            for center, neighbor, offset, flags, observations in rows
        ],
        "truth_boundary": manifest.get("truth_boundary") or {},
        "writes_allowed": manifest.get("writes_allowed") or {},
    }


def _unit_record(*, unit_index: int, anchor_start: int, anchors: list[str]) -> dict[str, Any]:
    unit_id = _unit_id(anchors)
    return {
        "schema_version": "anchorworks_four_anchor_unit@1",
        "unit_index": int(unit_index),
        "anchor_start": int(anchor_start),
        "anchor_end": int(anchor_start + len(anchors) - 1),
        "anchors": list(anchors),
        "unit_key": " ".join(anchors),
        "unit_id": unit_id,
        "unit_symbol": _unit_symbol(unit_id),
        "unit_hash": hashlib.sha256("\x1f".join(anchors).encode("utf-8")).hexdigest(),
    }


def _unit_id(anchors: list[str]) -> int:
    digest = hashlib.sha256("\x1f".join(anchors).encode("utf-8")).digest()
    value = int.from_bytes(digest[:8], "big")
    return value or 1


def _unit_symbol(unit_id: int) -> str:
    return f"unit4_{int(unit_id):016X}"


def _offset_key(offset: int) -> str:
    return f"+{offset}" if int(offset) > 0 else str(int(offset))


def _parse_offset(offset: Any) -> int:
    return int(str(offset).replace("+", ""))


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
