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


def pattern_hash(pattern: tuple[str, ...]) -> str:
    return sha256("\n".join(pattern).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class GlyphMatch:
    glyph_id: str
    display: str
    confidence: float
    match_type: str


class VisualGlyphLexicon:
    def __init__(self, by_hash: dict[str, GlyphMatch]) -> None:
        self._by_hash = dict(by_hash)

    @classmethod
    def from_records(cls, records: list[dict[str, Any]]) -> "VisualGlyphLexicon":
        by_hash: dict[str, GlyphMatch] = {}
        for record in records:
            if record.get("promotion_status") != "approved":
                continue
            pattern = normalize_trim_pattern(list(record.get("trim_pattern") or []))
            if not pattern:
                continue
            by_hash[pattern_hash(pattern)] = GlyphMatch(
                str(record["glyph_id"]),
                str(record["display"]),
                1.0,
                "exact",
            )
        return cls(by_hash)

    def match(self, rows: list[str]) -> GlyphMatch:
        pattern = normalize_trim_pattern(rows)
        found = self._by_hash.get(pattern_hash(pattern))
        if found:
            return found
        return GlyphMatch("visual_unknown_glyph", "visual_unknown_glyph", 0.0, "unknown")

