from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any


def normalize_trim_pattern(rows: list[str]) -> tuple[str, ...]:
    cleaned = [str(row) for row in rows if "1" in str(row)]
    if not cleaned:
        return tuple()
    left = min(row.index("1") for row in cleaned)
    right = max(row.rindex("1") for row in cleaned)
    return tuple(row[left : right + 1] for row in cleaned)


def scale_normalize_pattern(pattern: tuple[str, ...]) -> tuple[str, ...]:
    rows: list[str] = []
    for row in pattern:
        if not rows or rows[-1] != row:
            rows.append(row)
    if not rows:
        return tuple()

    columns: list[str] = []
    for index in range(len(rows[0])):
        column = "".join(row[index] for row in rows)
        if not columns or columns[-1] != column:
            columns.append(column)
    if not columns:
        return tuple(rows)
    return tuple("".join(column[row_index] for column in columns) for row_index in range(len(rows)))


def pattern_hash(pattern: tuple[str, ...]) -> str:
    return sha256("\n".join(pattern).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class GlyphMatch:
    glyph_id: str
    display: str
    confidence: float
    match_type: str


class VisualGlyphLexicon:
    def __init__(self, by_hash: dict[str, GlyphMatch], by_scaled_hash: dict[str, GlyphMatch] | None = None) -> None:
        self._by_hash = dict(by_hash)
        self._by_scaled_hash = dict(by_scaled_hash or {})

    @classmethod
    def from_records(cls, records: list[dict[str, Any]]) -> "VisualGlyphLexicon":
        by_hash: dict[str, GlyphMatch] = {}
        scaled_candidates: dict[str, GlyphMatch] = {}
        scaled_collisions: set[str] = set()
        for record in records:
            if record.get("promotion_status") != "approved":
                continue
            pattern = normalize_trim_pattern(list(record.get("trim_pattern") or []))
            if not pattern:
                continue
            match = GlyphMatch(
                str(record["glyph_id"]),
                str(record["display"]),
                1.0,
                "exact",
            )
            by_hash[pattern_hash(pattern)] = match
            scaled_hash = pattern_hash(scale_normalize_pattern(pattern))
            if scaled_hash in scaled_candidates and scaled_candidates[scaled_hash].display != match.display:
                scaled_collisions.add(scaled_hash)
            else:
                scaled_candidates[scaled_hash] = GlyphMatch(
                    match.glyph_id,
                    match.display,
                    0.9,
                    "scale_normalized",
                )
        by_scaled_hash = {
            key: value for key, value in scaled_candidates.items() if key not in scaled_collisions
        }
        return cls(by_hash, by_scaled_hash)

    def match(self, rows: list[str]) -> GlyphMatch:
        pattern = normalize_trim_pattern(rows)
        found = self._by_hash.get(pattern_hash(pattern))
        if found:
            return found
        scaled = scale_normalize_pattern(pattern)
        found = self._by_scaled_hash.get(pattern_hash(scaled))
        if found:
            return found
        return GlyphMatch("visual_unknown_glyph", "visual_unknown_glyph", 0.0, "unknown")
