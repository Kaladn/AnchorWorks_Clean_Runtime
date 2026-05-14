from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .symbol_genome import generate_symbol_genome_identity


PHRASE_SCHEMA_VERSION = "anchorworks_phrase_lexicon@1"


class PhraseLexiconStore:
    def __init__(self, root: str | Path, anchor_store: Any) -> None:
        self.root = Path(root).expanduser().resolve()
        self.anchor_store = anchor_store
        self.phrase_dir = self.root / "Phrase_Lexicon"
        self.phrase_dir.mkdir(parents=True, exist_ok=True)

    def assign_phrase(
        self,
        phrase: str,
        *,
        phrase_type: str = "concept",
        join_role_by_anchor: dict[str, str] | None = None,
        source_support: dict[str, Any] | None = None,
        notes: str = "",
    ) -> dict[str, Any]:
        anchor_sequence = _phrase_anchor_sequence(phrase)
        if not anchor_sequence:
            raise ValueError("phrase requires at least one anchor")
        symbol_sequence = [self._anchor_symbol(anchor) for anchor in anchor_sequence]
        phrase_text = " ".join(anchor_sequence)
        identity = generate_symbol_genome_identity(phrase_text, category="specialized", priority=2)
        phrase_hex = str(identity["hex"])
        entry = {
            "schema_version": PHRASE_SCHEMA_VERSION,
            "phrase": phrase_text,
            "display": phrase_text,
            "binary": identity["binary"],
            "font_symbol": identity["font_symbol"],
            "tone_label": "",
            "tone_profile": None,
            "status": "ASSIGNED",
            "authority": "phrase",
            "pack": "phrase",
            "hex": phrase_hex,
            "symbol": phrase_hex,
            "symbol_schema_version": identity["schema_version"],
            "symbol_category": identity["category"],
            "symbol_priority": identity["priority"],
            "symbol_bytes": identity["symbol_bytes"],
            "visual_grid": identity["visual_grid"],
            "visual_rune": identity["visual_rune"],
            "integrity_hash": identity["integrity_hash"],
            "anchor_sequence": anchor_sequence,
            "symbol_sequence": symbol_sequence,
            "join_role_by_anchor": {
                str(anchor).casefold(): str(role)
                for anchor, role in (join_role_by_anchor or {}).items()
                if str(anchor or "").strip()
            },
            "phrase_type": str(phrase_type or "concept"),
            "source_support": source_support or {
                "occurrences": 0,
                "source_count": 0,
                "last_built_from": "",
            },
            "notes": str(notes or ""),
            "mapped_at": _utc_now(),
            "writes_allowed": {"canonical": False, "counts": False, "lifetime": False},
        }
        self._write_phrase(entry)
        return entry

    def phrase_memberships_for_anchor(self, anchor: str) -> list[dict[str, Any]]:
        clean = str(anchor or "").strip().casefold()
        if not clean:
            return []
        memberships: list[dict[str, Any]] = []
        for entry in self.phrases():
            sequence = [str(item or "").strip().casefold() for item in entry.get("anchor_sequence") or []]
            if clean not in sequence:
                continue
            memberships.append({
                "phrase": str(entry.get("phrase") or ""),
                "hex": str(entry.get("hex") or entry.get("symbol") or ""),
                "status": str(entry.get("status") or ""),
                "phrase_type": str(entry.get("phrase_type") or ""),
                "role": str((entry.get("join_role_by_anchor") or {}).get(clean) or ""),
                "anchor_index": sequence.index(clean),
            })
        memberships.sort(key=lambda row: (row["phrase"], row["hex"]))
        return memberships

    def match_phrase(self, anchors: list[str]) -> dict[str, Any] | None:
        query = [str(anchor or "").strip().casefold() for anchor in anchors if str(anchor or "").strip()]
        if not query:
            return None
        best: dict[str, Any] | None = None
        best_score = -1
        for entry in self.phrases():
            if str(entry.get("status") or "").upper() != "ASSIGNED":
                continue
            sequence = [str(item or "").strip().casefold() for item in entry.get("anchor_sequence") or []]
            if not sequence:
                continue
            cursor = 0
            matched = 0
            for anchor in query:
                if cursor < len(sequence) and anchor == sequence[cursor]:
                    cursor += 1
                    matched += 1
            if matched < max(2, len(sequence) - 1):
                continue
            score = matched * 10 + len(sequence)
            if score > best_score:
                best = entry
                best_score = score
        return best

    def phrases(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for path in sorted(self.phrase_dir.glob("*.json"), key=lambda item: item.name.lower()):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and payload.get("schema_version") == PHRASE_SCHEMA_VERSION:
                out.append(payload)
        return out

    def _anchor_symbol(self, anchor: str) -> str:
        if not hasattr(self.anchor_store, "_find_entry"):
            raise ValueError("anchor store cannot resolve phrase anchors")
        found = self.anchor_store._find_entry(anchor)
        if not found:
            raise ValueError(f"phrase anchor is not assigned: {anchor}")
        entry = found[0]
        symbol = str(entry.get("hex") or entry.get("symbol") or "").strip()
        if not symbol:
            raise ValueError(f"phrase anchor has no symbol: {anchor}")
        return symbol

    def _write_phrase(self, entry: dict[str, Any]) -> None:
        phrase_hex = str(entry.get("hex") or "").replace("0x", "")
        path = self.phrase_dir / f"phrase_{phrase_hex}.json"
        path.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")


def _phrase_anchor_sequence(phrase: str) -> list[str]:
    return [part.strip().casefold() for part in str(phrase or "").split() if part.strip()]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
