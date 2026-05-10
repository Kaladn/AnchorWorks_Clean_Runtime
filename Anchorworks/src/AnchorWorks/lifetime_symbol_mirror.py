from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


def load_lifetime_by_symbol_dir(path: str | Path) -> dict[str, Any]:
    root = Path(path).expanduser()
    by_anchor: dict[str, dict[str, Counter[str]]] = {}
    if not root.exists() or not root.is_dir():
        return {"by_anchor": by_anchor, "source": "lifetime_by_symbol_missing", "root": str(root)}

    file_count = 0
    relation_count = 0
    for file_path in sorted(root.rglob("*.json")):
        payload = _read_json(file_path)
        if not isinstance(payload, dict):
            continue
        anchor = str(payload.get("anchor") or "").strip().casefold()
        neighbors = payload.get("neighbors")
        if not anchor or not isinstance(neighbors, dict):
            continue
        file_count += 1
        for offset, rows in neighbors.items():
            offset_key = str(offset)
            if not _valid_offset(offset_key) or not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                neighbor = str(row.get("anchor") or "").strip().casefold()
                observations = int(row.get("count", row.get("observations", 0)) or 0)
                if not neighbor or observations <= 0:
                    continue
                by_anchor.setdefault(anchor, {}).setdefault(offset_key, Counter())[neighbor] += observations
                relation_count += 1

    return {
        "by_anchor": by_anchor,
        "source": "lifetime_by_symbol",
        "root": str(root),
        "symbol_files_loaded": file_count,
        "relation_rows_loaded": relation_count,
    }


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _valid_offset(value: str) -> bool:
    try:
        return int(str(value).replace("+", "")) != 0
    except ValueError:
        return False
