from __future__ import annotations

import os
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

MAGIC = b"AWSC"
VERSION = 1
HEADER_SIZE = 38
SYMBOL_SIZE = 5
ROW_SIZE = 16
MAX_SYMBOL = (1 << 40) - 1

CANONICAL_LANE = 0
COMPANION_LANE = 1
SOURCE_LOCAL_LANE = 2
NULL_EXCLUSION_LANE = 3

_HEADER_TAIL = struct.Struct(">BQII8s")
_ROW = struct.Struct(">b5sQBB")


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
        if not 0 <= int(self.lane) <= 255:
            raise ValueError("relation lane must fit uint8")
        if not 0 <= int(self.flags) <= 255:
            raise ValueError("relation flags must fit uint8")


@dataclass(frozen=True)
class SymbolCell:
    symbol: bytes
    anchor_observations: int
    relations: list[SymbolRelation]
    flags: int = 0


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
    anchor_observations: int,
    relations: list[SymbolRelation],
    flags: int = 0,
) -> None:
    if anchor_observations < 0:
        raise ValueError("anchor observations must be non-negative")
    if not 0 <= int(flags) <= 255:
        raise ValueError("cell flags must fit uint8")
    symbol_bytes = symbol_to_bytes(symbol)
    merged_relations = _merge_relations(relations)
    payload = b"".join(_pack_relation(row) for row in merged_relations)
    checksum = zlib.crc32(payload) & 0xFFFFFFFF
    header = (
        MAGIC
        + struct.pack(">HH", VERSION, HEADER_SIZE)
        + symbol_bytes
        + _HEADER_TAIL.pack(int(flags), int(anchor_observations), len(merged_relations), checksum, b"\x00" * 8)
    )
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
    version, header_size = struct.unpack(">HH", raw[4:8])
    if version != VERSION:
        raise ValueError("unsupported symbol cell version")
    if header_size != HEADER_SIZE:
        raise ValueError("unsupported symbol cell header size")
    symbol = raw[8:13]
    flags, anchor_observations, relation_count, checksum, _reserved = _HEADER_TAIL.unpack(raw[13:HEADER_SIZE])
    payload = raw[HEADER_SIZE:]
    expected_size = relation_count * ROW_SIZE
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
        anchor_observations=anchor_observations,
        relations=relations,
        flags=flags,
    )


def merge_symbol_cell(
    path: str | Path,
    *,
    symbol: bytes | str | int,
    anchor_observations_delta: int,
    relations: list[SymbolRelation],
) -> None:
    if anchor_observations_delta < 0:
        raise ValueError("anchor observations delta must be non-negative")
    output_path = Path(path)
    symbol_bytes = symbol_to_bytes(symbol)
    if output_path.exists():
        existing = read_symbol_cell(output_path)
        if existing.symbol != symbol_bytes:
            raise ValueError("cannot merge a different root symbol into this cell")
        flags = existing.flags
        observations = existing.anchor_observations + anchor_observations_delta
        all_relations = existing.relations + list(relations)
    else:
        flags = 0
        observations = anchor_observations_delta
        all_relations = list(relations)
    write_symbol_cell(
        output_path,
        symbol=symbol_bytes,
        anchor_observations=observations,
        relations=all_relations,
        flags=flags,
    )


def corrupt_cell_for_test(path: str | Path) -> None:
    cell_path = Path(path)
    raw = bytearray(cell_path.read_bytes())
    if len(raw) <= HEADER_SIZE:
        raw[-1] ^= 0x01
    else:
        raw[-1] ^= 0x01
    cell_path.write_bytes(raw)


def _merge_relations(relations: list[SymbolRelation]) -> list[SymbolRelation]:
    counts: dict[tuple[int, bytes, int, int], int] = {}
    order: list[tuple[int, bytes, int, int]] = []
    for row in relations:
        key = (int(row.offset), symbol_to_bytes(row.neighbor_symbol), int(row.lane), int(row.flags))
        if key not in counts:
            order.append(key)
        counts[key] = counts.get(key, 0) + int(row.count)
    return [
        SymbolRelation(offset=offset, neighbor_symbol=neighbor, count=count, lane=lane, flags=flags)
        for offset, neighbor, lane, flags in order
        for count in [counts[(offset, neighbor, lane, flags)]]
        if count > 0
    ]


def _pack_relation(row: SymbolRelation) -> bytes:
    return _ROW.pack(
        int(row.offset),
        symbol_to_bytes(row.neighbor_symbol),
        int(row.count),
        int(row.lane),
        int(row.flags),
    )


def _unpack_relation(raw: bytes) -> SymbolRelation:
    offset, neighbor_symbol, count, lane, flags = _ROW.unpack(raw)
    return SymbolRelation(
        offset=offset,
        neighbor_symbol=neighbor_symbol,
        count=count,
        lane=lane,
        flags=flags,
    )
