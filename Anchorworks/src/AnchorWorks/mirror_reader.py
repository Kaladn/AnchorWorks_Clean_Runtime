from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class MirrorReader:
    def __init__(self, data_root: Path | str) -> None:
        self.root = Path(data_root).expanduser().resolve() / "State" / "chat_memory" / "mirrors"

    def get_entry_mirror(self, entry_id: str, *, day: str) -> dict[str, Any]:
        out = {
            "entry_id": str(entry_id),
            "l2_context": {},
            "l3_lessons": [],
            "l4_reasoning": {},
        }
        for row in _read_jsonl(self.root / f"{day}.mirror.jsonl"):
            if not isinstance(row, dict) or str(row.get("entry_id") or "") != str(entry_id):
                continue
            if isinstance(row.get("l2_context"), dict):
                out["l2_context"] = dict(row["l2_context"])
            if isinstance(row.get("l3_lessons"), list):
                out["l3_lessons"].extend(row["l3_lessons"])
            if isinstance(row.get("l4_reasoning"), dict):
                out["l4_reasoning"] = dict(row["l4_reasoning"])
        return out

    def entries_with_citation(self, citation_id: str, *, day: str) -> list[str]:
        hits: list[str] = []
        for row in _read_jsonl(self.root / f"{day}.mirror.jsonl"):
            context = row.get("l2_context") if isinstance(row, dict) else {}
            hooks = context.get("citation_hooks") if isinstance(context, dict) else []
            entry_id = str(row.get("entry_id") or "")
            if citation_id in hooks and entry_id and entry_id not in hits:
                hits.append(entry_id)
        return hits


def _read_jsonl(path: Path) -> list[Any]:
    if not path.exists():
        return []
    rows: list[Any] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            rows.append({"raw": line})
    return rows
