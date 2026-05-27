from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class ChatLogReader:
    def __init__(self, data_root: Path | str) -> None:
        self.root = Path(data_root).expanduser().resolve() / "State" / "chat_memory"
        self.chats_dir = self.root / "chats"

    def get_conversation(self, *, day: str, branch: str = "main", limit: int = 200) -> dict[str, Any]:
        entries: list[dict[str, Any]] = []
        quarantine: list[dict[str, Any]] = []
        for line_number, row in enumerate(_read_jsonl(self.chats_dir / f"{day}.jsonl"), start=1):
            if not isinstance(row, dict):
                quarantine.append({"line_number": line_number, "reason": "invalid_json_row", "row": row})
                continue
            reason = verify_chat_entry(row)
            if reason:
                quarantine.append({"line_number": line_number, "reason": reason, "row": row})
                continue
            if branch and branch != "all" and str(row.get("branch") or "main") != branch:
                continue
            entries.append(row)
        return {
            "ok": True,
            "day": day,
            "branch": branch or "all",
            "entries": entries[-max(1, int(limit or 200)):],
            "quarantine": quarantine,
        }

    def get_entry_by_id(self, entry_id: str, *, day: str | None = None) -> dict[str, Any] | None:
        paths = [self.chats_dir / f"{day}.jsonl"] if day else sorted(self.chats_dir.glob("*.jsonl"), reverse=True)
        for path in paths:
            for row in _read_jsonl(path):
                if isinstance(row, dict) and str(row.get("message_uuid") or "") == str(entry_id):
                    if verify_chat_entry(row):
                        return None
                    return row
        return None

    def search_by_keyword(self, keyword: str, *, day: str | None = None, limit: int = 50) -> dict[str, Any]:
        needle = str(keyword or "").casefold().strip()
        matches: list[dict[str, Any]] = []
        quarantine: list[dict[str, Any]] = []
        paths = [self.chats_dir / f"{day}.jsonl"] if day else sorted(self.chats_dir.glob("*.jsonl"), reverse=True)
        for path in paths:
            for line_number, row in enumerate(_read_jsonl(path), start=1):
                if not isinstance(row, dict):
                    continue
                reason = verify_chat_entry(row)
                if reason:
                    quarantine.append({"line_number": line_number, "path": str(path), "reason": reason})
                    continue
                if needle and needle in str(row.get("content") or "").casefold():
                    matches.append(row)
        return {"ok": True, "matches": matches[: max(1, int(limit or 50))], "quarantine": quarantine}


def verify_chat_entry(row: dict[str, Any]) -> str:
    stored = str(row.get("integrity_hash") or "")
    if not stored:
        return "missing_integrity_hash"
    calculated = chat_entry_integrity_hash(row)
    if stored != calculated:
        return "integrity_hash_mismatch"
    if str(row.get("hash") or "") and str(row.get("hash")) != calculated[:12]:
        return "short_hash_mismatch"
    return ""


def chat_entry_integrity_hash(row: dict[str, Any]) -> str:
    payload = {key: value for key, value in row.items() if key not in {"hash", "integrity_hash"}}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


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
