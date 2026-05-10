from __future__ import annotations

import os
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

MAGIC = b"AWSC"
VERSION = 0x0101
HEADER_SIZE = 64
SYMBOL_SIZE = 5
ROW_SIZE = 16
MAX_SYMBOL = (1 << 40) - 1

CANONICAL_LANE = 0
MATH_COMPANION_LANE = 1
STRUCTURAL_COMPANION_LANE = 2
SOURCE_SPECIFIC_LANE = 3
SOURCE_LOCAL_TEMP_LANE = 4
USER_LEXICON_LANE = 5
RESERVED_ERROR_LANE = 255
VALID_RELATION_LANES = {
    CANONICAL_LANE,
    MATH_COMPANION_LANE,
    STRUCTURAL_COMPANION_LANE,
    SOURCE_SPECIFIC_LANE,
    SOURCE_LOCAL_TEMP_LANE,
    USER_LEXICON_LANE,
    RESERVED_ERROR_LANE,
}

SPEAK_BLOCKED_FLAG = 1 << 0
SOURCE_LOCAL_ONLY_FLAG = 1 << 1
COMPANION_FLAG = 1 << 2
USER_SCOPE_FLAG = 1 << 3
AUDIT_ONLY_FLAG = 1 << 4
OVERFLOW_RELATED_FLAG = 1 << 5

_HEADER_PREFIX = struct.Struct("<HHQQQ")
_HEADER_TAIL = struct.Struct("<BHIHHIIQ")
_ROW = struct.Struct("<5sbBBQ")


@dataclass(frozen=True)
class SymbolRelation:
    offset: int
    neighbor_symbol: bytes | str | int
    count: int
    lane: int = CANONICAL_LANE
    flags: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "neighbor_symbol", symbol_to_bytes(self.neighbor_symbol))
        if not -128 <= int(self.offset) <= 127:
            raise ValueError("relation offset must fit int8")
        if int(self.count) < 0:
            raise ValueError("relation count must be non-negative")
        if int(self.lane) not in VALID_RELATION_LANES:
            raise ValueError("relation lane is not valid for AWSC relation memory")
        if not 0 <= int(self.flags) <= 255:
            raise ValueError("relation flags must fit uint8")


@dataclass(frozen=True)
class SymbolCell:
    symbol: bytes
    root_lane: int
    generation: int
    wal_frame: int
    total_size: int
    payload_size: int
    overflow_offset: int
    flags: int
    relations: list[SymbolRelation]


def symbol_to_bytes(symbol: bytes | str | int) -> bytes:
    if isinstance(symbol, bytes):
        if len(symbol) != SYMBOL_SIZE:
            raise ValueError("symbol bytes must be exactly 5 bytes")
        return symbol
    if isinstance(symbol, int):
        value = symbol
    else:
        text = str(symbol or "").strip()
        if not text:
            raise ValueError("empty symbol")
        if text.lower().startswith("0x"):
            text = text[2:]
        value = int(text, 16)
    if value < 0 or value > MAX_SYMBOL:
        raise ValueError("symbol must fit 40 bits")
    return value.to_bytes(SYMBOL_SIZE, "big")


def write_symbol_cell(
    path: str | Path,
    *,
    symbol: bytes | str | int,
    relations: list[SymbolRelation],
    root_lane: int = CANONICAL_LANE,
    generation: int = 0,
    wal_frame: int = 0,
    flags: int = 0,
    overflow_offset: int = 0,
) -> None:
    _validate_lane(root_lane)
    _validate_uint(generation, 64, "generation")
    _validate_uint(wal_frame, 64, "WAL frame")
    _validate_uint(flags, 16, "cell flags")
    _validate_uint(overflow_offset, 64, "overflow offset")
    symbol_bytes = symbol_to_bytes(symbol)
    merged_relations = _merge_relations(relations)
    payload = b"".join(_pack_relation(row) for row in merged_relations)
    payload_size = len(payload)
    total_size = HEADER_SIZE + payload_size
    checksum = zlib.crc32(payload) & 0xFFFFFFFF
    header = (
        MAGIC
        + _HEADER_PREFIX.pack(VERSION, HEADER_SIZE, total_size, int(generation), int(wal_frame))
        + symbol_bytes
        + _HEADER_TAIL.pack(
            int(root_lane),
            int(flags),
            len(merged_relations),
            ROW_SIZE,
            0,
            payload_size,
            checksum,
            int(overflow_offset),
        )
    )
    if len(header) != HEADER_SIZE:
        raise AssertionError("AWSC header layout must be exactly 64 bytes")
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_name(f"{output_path.name}.tmp")
    temp_path.write_bytes(header + payload)
    os.replace(temp_path, output_path)


def read_symbol_cell(path: str | Path) -> SymbolCell:
    raw = Path(path).read_bytes()
    if len(raw) < HEADER_SIZE:
        raise ValueError("symbol cell is shorter than header")
    if raw[:4] != MAGIC:
        raise ValueError("invalid symbol cell magic")
    version, header_size, total_size, generation, wal_frame = _HEADER_PREFIX.unpack(raw[4:32])
    if version != VERSION:
        raise ValueError("unsupported symbol cell version")
    if header_size != HEADER_SIZE:
        raise ValueError("unsupported symbol cell header size")
    if total_size != len(raw):
        raise ValueError("symbol cell total size mismatch")
    symbol = raw[32:37]
    root_lane, flags, row_count, row_size, _reserved, payload_size, checksum, overflow_offset = (
        _HEADER_TAIL.unpack(raw[37:HEADER_SIZE])
    )
    _validate_lane(root_lane)
    if row_size != ROW_SIZE:
        raise ValueError("unsupported symbol cell row size")
    payload = raw[HEADER_SIZE:]
    expected_size = row_count * ROW_SIZE
    if payload_size != expected_size:
        raise ValueError("symbol cell payload size field mismatch")
    if len(payload) != expected_size:
        raise ValueError("symbol cell payload size mismatch")
    actual_checksum = zlib.crc32(payload) & 0xFFFFFFFF
    if actual_checksum != checksum:
        raise ValueError("symbol cell CRC mismatch")
    relations = [
        _unpack_relation(payload[index : index + ROW_SIZE])
        for index in range(0, len(payload), ROW_SIZE)
    ]
    return SymbolCell(
        symbol=symbol,
        root_lane=root_lane,
        generation=generation,
        wal_frame=wal_frame,
        total_size=total_size,
        payload_size=payload_size,
        overflow_offset=overflow_offset,
        flags=flags,
        relations=relations,
    )


def merge_symbol_cell(
    path: str | Path,
    *,
    symbol: bytes | str | int,
    relations: list[SymbolRelation],
    root_lane: int = CANONICAL_LANE,
    generation: int = 0,
    wal_frame: int = 0,
    flags: int = 0,
    overflow_offset: int = 0,
) -> None:
    output_path = Path(path)
    symbol_bytes = symbol_to_bytes(symbol)
    if output_path.exists():
        existing = read_symbol_cell(output_path)
        if existing.symbol != symbol_bytes:
            raise ValueError("cannot merge a different root symbol into this cell")
        if existing.root_lane != root_lane:
            raise ValueError("cannot merge a different root lane into this cell")
        all_relations = existing.relations + list(relations)
        flags = existing.flags | int(flags)
        overflow_offset = int(overflow_offset or existing.overflow_offset)
        wal_frame = int(wal_frame or existing.wal_frame)
    else:
        all_relations = list(relations)
    write_symbol_cell(
        output_path,
        symbol=symbol_bytes,
        root_lane=root_lane,
        generation=generation,
        wal_frame=wal_frame,
        flags=flags,
        overflow_offset=overflow_offset,
        relations=all_relations,
    )


def corrupt_cell_for_test(path: str | Path) -> None:
    cell_path = Path(path)
    raw = bytearray(cell_path.read_bytes())
    if len(raw) <= HEADER_SIZE:
        raw[-1] ^= 0x01
    else:
        raw[-1] ^= 0x01
    cell_path.write_bytes(raw)


def _validate_lane(lane: int) -> None:
    if int(lane) not in VALID_RELATION_LANES:
        raise ValueError("lane is not valid for AWSC relation memory")


def _validate_uint(value: int, bits: int, name: str) -> None:
    maximum = (1 << bits) - 1
    if int(value) < 0 or int(value) > maximum:
        raise ValueError(f"{name} must fit uint{bits}")


def _merge_relations(relations: list[SymbolRelation]) -> list[SymbolRelation]:
    counts: dict[tuple[int, bytes, int, int], int] = {}
    for row in relations:
        key = (int(row.offset), symbol_to_bytes(row.neighbor_symbol), int(row.lane), int(row.flags))
        counts[key] = counts.get(key, 0) + int(row.count)
    merged = [
        SymbolRelation(offset=offset, neighbor_symbol=neighbor, count=count, lane=lane, flags=flags)
        for (offset, neighbor, lane, flags), count in counts.items()
        if count > 0
    ]
    return sorted(
        merged,
        key=lambda row: (
            int(row.offset),
            -int(row.count),
            symbol_to_bytes(row.neighbor_symbol),
            int(row.lane),
        ),
    )


def _pack_relation(row: SymbolRelation) -> bytes:
    return _ROW.pack(
        symbol_to_bytes(row.neighbor_symbol),
        int(row.offset),
        int(row.lane),
        int(row.flags),
        int(row.count),
    )


def _unpack_relation(raw: bytes) -> SymbolRelation:
    neighbor_symbol, offset, lane, flags, count = _ROW.unpack(raw)
    return SymbolRelation(
        offset=offset,
        neighbor_symbol=neighbor_symbol,
        count=count,
        lane=lane,
        flags=flags,
    )
