from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .symbol_genome import (
    SYMBOL_GENOME_CATEGORY_CODES,
    SYMBOL_GENOME_SCHEMA_VERSION,
    symbol_to_visual_grid,
    visual_grid_to_ascii,
)


SYMBOL_GENOME_POOL_SCHEMA_VERSION = "anchorworks_symbol_genome_pool@1"
MAX_40_BIT_SYMBOL_COUNT = 1 << 40
DEFAULT_SYMBOL_GENOME_CAPACITY = 10_000_000
USER_LEXICON_SYMBOL_BASE = 0xE000000000
USER_LEXICON_SYMBOL_CAPACITY = 500_000_000
SOURCE_LOCAL_SYMBOL_BASE = 0xF000000000
AUTHORITY_SYMBOL_RANGES = {
    "canonical": (0, USER_LEXICON_SYMBOL_BASE),
    "user_lexicon": (USER_LEXICON_SYMBOL_BASE, USER_LEXICON_SYMBOL_CAPACITY),
    "source_local": (SOURCE_LOCAL_SYMBOL_BASE, MAX_40_BIT_SYMBOL_COUNT - SOURCE_LOCAL_SYMBOL_BASE),
    "source_local_coordinate": (SOURCE_LOCAL_SYMBOL_BASE, MAX_40_BIT_SYMBOL_COUNT - SOURCE_LOCAL_SYMBOL_BASE),
}


class SymbolGenomePool:
    def __init__(self, root: str | Path, *, capacity: int = DEFAULT_SYMBOL_GENOME_CAPACITY) -> None:
        self.root = Path(root).expanduser().resolve()
        self.manifest_path = self.root / "manifest.json"
        self.capacity = int(capacity)
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.manifest_path.exists():
            self._write_manifest(self._default_manifest())

    def status(self) -> dict[str, Any]:
        manifest = self._read_manifest()
        capacity = int(manifest.get("capacity") or self.capacity)
        next_index = int(manifest.get("next_index") or 0)
        return {
            **manifest,
            "capacity": capacity,
            "next_index": next_index,
            "assigned_count": int(manifest.get("assigned_count") or next_index),
            "remaining": max(0, capacity - next_index),
            "manifest_path": str(self.manifest_path),
            "lexicon_pack": False,
        }

    def allocate(
        self,
        label: str,
        *,
        authority: str,
        category: str = "specialized",
        priority: int = 2,
    ) -> dict[str, Any]:
        clean_label = str(label or "").strip().casefold()
        clean_authority = str(authority or "").strip().casefold()
        if not clean_label:
            raise ValueError("symbol label is required")
        if not clean_authority:
            raise ValueError("symbol authority is required")
        if category not in SYMBOL_GENOME_CATEGORY_CODES:
            raise ValueError(f"unknown symbol genome category: {category}")

        manifest = self._read_manifest()
        capacity = int(manifest.get("capacity") or self.capacity)
        next_index = int(manifest.get("next_index") or 0)
        if next_index >= capacity or next_index >= MAX_40_BIT_SYMBOL_COUNT:
            raise ValueError("symbol genome pool exhausted")

        identity = symbol_genome_identity_from_index(
            clean_label,
            authority=clean_authority,
            allocation_index=next_index,
            category=category,
            priority=priority,
        )
        manifest["next_index"] = next_index + 1
        manifest["assigned_count"] = int(manifest.get("assigned_count") or 0) + 1
        manifest["updated_at"] = _utc_now()
        manifest["last_allocation"] = {
            "allocation_index": next_index,
            "label": clean_label,
            "authority": clean_authority,
            "hex": identity["hex"],
            "allocated_at": manifest["updated_at"],
        }
        self._write_manifest(manifest)
        return identity

    def checkpoint(self, reason: str = "") -> dict[str, Any]:
        manifest = self._read_manifest()
        now = _utc_now()
        manifest["updated_at"] = now
        manifest["last_checkpoint_at"] = now
        manifest["last_checkpoint_reason"] = str(reason or "")
        manifest.setdefault("checkpoints", []).append({
            "checkpoint_at": now,
            "reason": str(reason or ""),
            "next_index": int(manifest.get("next_index") or 0),
            "assigned_count": int(manifest.get("assigned_count") or 0),
        })
        self._write_manifest(manifest)
        return self.status()

    def _default_manifest(self) -> dict[str, Any]:
        now = _utc_now()
        return {
            "schema_version": SYMBOL_GENOME_POOL_SCHEMA_VERSION,
            "created_at": now,
            "updated_at": now,
            "capacity": self.capacity,
            "next_index": 0,
            "assigned_count": 0,
            "generator": "cursor_backed_40_bit_symbol_genome",
            "lexicon_pack": False,
            "records_materialized": False,
            "slot_materialization": "cursor_manifest_only",
            "checkpoint_contract": "manifest cursor is authority; generated symbols are not copied into spare lexicon files",
            "checkpoints": [],
        }

    def _read_manifest(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            payload = self._default_manifest()
            self._write_manifest(payload)
        if not isinstance(payload, dict) or payload.get("schema_version") != SYMBOL_GENOME_POOL_SCHEMA_VERSION:
            raise ValueError("invalid symbol genome pool manifest")
        changed = False
        next_index = int(payload.get("next_index") or 0)
        if next_index > self.capacity:
            raise ValueError("symbol genome pool cursor exceeds configured capacity")
        if int(payload.get("capacity") or 0) != self.capacity:
            payload["capacity"] = self.capacity
            changed = True
        if payload.get("generator") != "cursor_backed_40_bit_symbol_genome":
            payload["generator"] = "cursor_backed_40_bit_symbol_genome"
            changed = True
        if payload.get("slot_materialization") != "cursor_manifest_only":
            payload["slot_materialization"] = "cursor_manifest_only"
            changed = True
        if payload.get("records_materialized") is not False:
            payload["records_materialized"] = False
            changed = True
        if changed:
            payload["updated_at"] = _utc_now()
            self._write_manifest(payload)
        return payload

    def _write_manifest(self, payload: dict[str, Any]) -> None:
        self.manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def symbol_genome_identity_from_index(
    label: str,
    *,
    authority: str,
    allocation_index: int,
    category: str = "specialized",
    priority: int = 2,
) -> dict[str, Any]:
    if allocation_index < 0 or allocation_index >= MAX_40_BIT_SYMBOL_COUNT:
        raise ValueError("allocation index must fit in 40 bits")
    clean_authority = str(authority or "").strip().casefold()
    symbol_index = _symbol_index_for_authority(clean_authority, int(allocation_index))
    category_code = SYMBOL_GENOME_CATEGORY_CODES[category]
    clean_priority = max(0, min(7, int(priority)))
    symbol_bytes = int(symbol_index).to_bytes(5, "big")
    grid = symbol_to_visual_grid(symbol_bytes)
    hex_value = "0x" + symbol_bytes.hex().upper()
    return {
        "schema_version": SYMBOL_GENOME_SCHEMA_VERSION,
        "label": str(label or "").strip().casefold(),
        "authority": clean_authority,
        "allocation_index": int(allocation_index),
        "symbol_index": int(symbol_index),
        "category": category,
        "category_code": category_code,
        "priority": clean_priority,
        "encoding": "cursor_40_bit",
        "symbol_length_bytes": 5,
        "symbol_bytes": list(symbol_bytes),
        "hex": hex_value,
        "symbol": hex_value,
        "binary": "".join(f"{byte:08b}" for byte in symbol_bytes),
        "font_symbol": "CHAR_" + "".join(f"{byte:08b}" for byte in symbol_bytes[:2]),
        "visual_grid": grid,
        "visual_rune": visual_grid_to_ascii(grid),
        "tone_label": "",
        "tone_profile": None,
    }


def _symbol_index_for_authority(authority: str, allocation_index: int) -> int:
    base, capacity = AUTHORITY_SYMBOL_RANGES.get(authority, AUTHORITY_SYMBOL_RANGES["canonical"])
    if allocation_index < 0 or allocation_index >= capacity:
        raise ValueError(f"{authority or 'canonical'} symbol range exhausted")
    symbol_index = base + allocation_index
    if symbol_index < 0 or symbol_index >= MAX_40_BIT_SYMBOL_COUNT:
        raise ValueError("symbol index must fit in 40 bits")
    return symbol_index


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
