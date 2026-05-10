from __future__ import annotations

import json
import os
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MAGIC = b"AWSM"
VERSION = 0x0100
HEADER_SIZE = 64
RELATION_ROW_SIZE = 24

_HEADER = struct.Struct("<4sHHQQIIIII")
_RELATION_ROW = struct.Struct("<5s5sbBHHQ")
if _RELATION_ROW.size != RELATION_ROW_SIZE:
    raise AssertionError("AWSM relation row layout must be exactly 24 bytes")


@dataclass(frozen=True)
class SymbolicMapRelation:
    root_symbol_id: int
    neighbor_symbol_id: int
    offset: int
    lane: int
    flags: int
    count: int


@dataclass(frozen=True)
class SymbolicMapBinary:
    metadata: dict[str, Any]
    relations: list[SymbolicMapRelation]
    metadata_size: int
    relation_count: int


def write_symbolic_map_binary(
    path: str | Path,
    *,
    metadata: dict[str, Any],
    relations: list[SymbolicMapRelation],
) -> None:
    metadata_bytes = json.dumps(metadata, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    relation_bytes = b"".join(_pack_relation(row) for row in relations)
    total_size = HEADER_SIZE + len(metadata_bytes) + len(relation_bytes)
    header = _HEADER.pack(
        MAGIC,
        VERSION,
        HEADER_SIZE,
        total_size,
        len(metadata_bytes),
        len(relations),
        RELATION_ROW_SIZE,
        zlib.crc32(metadata_bytes) & 0xFFFFFFFF,
        zlib.crc32(relation_bytes) & 0xFFFFFFFF,
        0,
    )
    header = header + bytes(HEADER_SIZE - len(header))
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output.with_name(f"{output.name}.tmp")
    temp_path.write_bytes(header + metadata_bytes + relation_bytes)
    os.replace(temp_path, output)


def read_symbolic_map_binary(path: str | Path) -> SymbolicMapBinary:
    raw = Path(path).read_bytes()
    if len(raw) < HEADER_SIZE:
        raise ValueError("symbolic map binary is shorter than header")
    magic, version, header_size, total_size, metadata_size, relation_count, row_size, metadata_crc, relation_crc, _reserved = _HEADER.unpack(
        raw[:_HEADER.size]
    )
    if magic != MAGIC:
        raise ValueError("invalid symbolic map binary magic")
    if version != VERSION:
        raise ValueError("unsupported symbolic map binary version")
    if header_size != HEADER_SIZE:
        raise ValueError("unsupported symbolic map binary header size")
    if total_size != len(raw):
        raise ValueError("symbolic map binary total size mismatch")
    if row_size != RELATION_ROW_SIZE:
        raise ValueError("unsupported symbolic map relation row size")
    metadata_start = HEADER_SIZE
    relation_start = HEADER_SIZE + metadata_size
    metadata_bytes = raw[metadata_start:relation_start]
    relation_bytes = raw[relation_start:]
    if zlib.crc32(metadata_bytes) & 0xFFFFFFFF != metadata_crc:
        raise ValueError("symbolic map metadata CRC mismatch")
    if zlib.crc32(relation_bytes) & 0xFFFFFFFF != relation_crc:
        raise ValueError("symbolic map relation CRC mismatch")
    if len(relation_bytes) != relation_count * RELATION_ROW_SIZE:
        raise ValueError("symbolic map relation payload size mismatch")
    relations = [
        _unpack_relation(relation_bytes[index : index + RELATION_ROW_SIZE])
        for index in range(0, len(relation_bytes), RELATION_ROW_SIZE)
    ]
    return SymbolicMapBinary(
        metadata=json.loads(metadata_bytes.decode("utf-8")),
        relations=relations,
        metadata_size=metadata_size,
        relation_count=relation_count,
    )


def _pack_relation(row: SymbolicMapRelation) -> bytes:
    if row.root_symbol_id < 0 or row.neighbor_symbol_id < 0:
        raise ValueError("symbol ids must be non-negative")
    if not -128 <= row.offset <= 127:
        raise ValueError("offset must fit int8")
    if not 0 <= row.lane <= 255:
        raise ValueError("lane must fit uint8")
    if not 0 <= row.flags <= 65535:
        raise ValueError("flags must fit uint16")
    if row.count < 0:
        raise ValueError("count must be non-negative")
    return _RELATION_ROW.pack(
        _symbol_bytes(row.root_symbol_id),
        _symbol_bytes(row.neighbor_symbol_id),
        int(row.offset),
        int(row.lane),
        int(row.flags),
        0,
        int(row.count),
    )


def _unpack_relation(raw: bytes) -> SymbolicMapRelation:
    root, neighbor, offset, lane, flags, _reserved, count = _RELATION_ROW.unpack(raw)
    return SymbolicMapRelation(
        root_symbol_id=int.from_bytes(root, "big"),
        neighbor_symbol_id=int.from_bytes(neighbor, "big"),
        offset=offset,
        lane=lane,
        flags=flags,
        count=count,
    )


def _symbol_bytes(symbol_id: int) -> bytes:
    if symbol_id < 0 or symbol_id > (1 << 40) - 1:
        raise ValueError("symbol id must fit 40 bits")
    return int(symbol_id).to_bytes(5, "big")
