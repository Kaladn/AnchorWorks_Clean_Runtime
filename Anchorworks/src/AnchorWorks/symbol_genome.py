from __future__ import annotations

import hashlib
from typing import Any


SYMBOL_GENOME_SCHEMA_VERSION = "anchorworks_symbol_genome@1"
SYMBOL_GENOME_CATEGORY_CODES = {
    "core": 0b000,
    "specialized": 0b001,
    "future": 0b010,
}


def generate_symbol_genome_identity(
    label: str,
    *,
    category: str = "specialized",
    priority: int = 4,
) -> dict[str, Any]:
    clean_label = str(label or "").strip().casefold()
    if not clean_label:
        raise ValueError("symbol genome label is required")
    if category not in SYMBOL_GENOME_CATEGORY_CODES:
        raise ValueError(f"unknown symbol genome category: {category}")
    clean_priority = max(0, min(7, int(priority)))
    category_code = SYMBOL_GENOME_CATEGORY_CODES[category]
    byte1 = (category_code << 5) | (clean_priority << 2)
    digest = hashlib.sha256(clean_label.encode("utf-8")).digest()
    symbol_bytes = bytes([byte1]) + digest[:4]
    grid = symbol_to_visual_grid(symbol_bytes)
    return {
        "schema_version": SYMBOL_GENOME_SCHEMA_VERSION,
        "label": clean_label,
        "category": category,
        "category_code": category_code,
        "priority": clean_priority,
        "symbol_length_bytes": 5,
        "symbol_bytes": list(symbol_bytes),
        "hex": "0x" + symbol_bytes.hex().upper(),
        "symbol": "0x" + symbol_bytes.hex().upper(),
        "binary": "".join(f"{byte:08b}" for byte in symbol_bytes),
        "font_symbol": "CHAR_" + "".join(f"{byte:08b}" for byte in symbol_bytes[:2]),
        "visual_grid": grid,
        "visual_rune": visual_grid_to_ascii(grid),
        "integrity_hash": hashlib.sha256(clean_label.encode("utf-8") + symbol_bytes).hexdigest(),
    }


def symbol_to_visual_grid(symbol_bytes: bytes) -> list[list[int]]:
    if len(symbol_bytes) != 5:
        raise ValueError("symbol genome requires exactly 5 bytes")
    symbol_int = int.from_bytes(symbol_bytes, "big")
    grid = [[0 for _col in range(8)] for _row in range(8)]
    for index in range(40):
        bit = (symbol_int >> index) & 1
        if bit:
            row = (index * 7 + symbol_int) % 8
            col = (index * 11 + (symbol_int >> 8)) % 8
            grid[row][col] = 1
    corners = [(0, 0), (0, 7), (7, 0), (7, 7)]
    for index, (row, col) in enumerate(corners):
        if (symbol_int >> (index * 8)) & 1:
            grid[row][col] = 1
    if symbol_bytes[0] < 0x20:
        grid[3][3] = 1
        grid[3][4] = 1
        grid[4][3] = 1
        grid[4][4] = 1
    return grid


def visual_grid_to_ascii(grid: list[list[int]]) -> str:
    return "\n".join("".join("#" if cell else "." for cell in row) for row in grid)
