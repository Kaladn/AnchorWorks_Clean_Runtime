from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .common import StorePower


CHAT_TURN_SCHEMA = "anchorworks_chat_turn@1"
CHAT_CONSOLIDATION_SCHEMA = "anchorworks_daily_chat_consolidation@1"


class MemoryStore(StorePower):
    """Daily JSONL working chat plus explicit native count consolidation."""

    def _day_id(self, day_id: str | None = None) -> str:
        text = str(day_id or "").strip()
        if text:
            return text
        return datetime.now(timezone.utc).date().isoformat()

    def chat_log_path(self, day_id: str | None = None) -> Path:
        return self.facade.chat_logs_dir / f"{self._day_id(day_id)}.jsonl"

    def append_chat_turn(
        self,
        text: str,
        *,
        conversation_id: str = "",
        role: str = "user",
        day_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        day = self._day_id(day_id)
        path = self.chat_log_path(day)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.facade._lock:
            turn_index = self._record_count(path) + 1
            raw_text = str(text or "")
            clean_text = raw_text.strip()
            created_at = datetime.now(timezone.utc).isoformat()
            record = {
                "schema_version": CHAT_TURN_SCHEMA,
                "created_at": created_at,
                "day_id": day,
                "conversation_id": str(conversation_id or "default"),
                "turn_index": turn_index,
                "turn_id": f"{day}-t{turn_index:06d}",
                "block_id": f"b{turn_index:06d}",
                "line_id": f"l{turn_index:06d}",
                "role": str(role or "user"),
                "raw_text": raw_text,
                "clean_text": clean_text,
                "metadata": metadata or {},
                "counts_written": False,
                "counts_write_rule": "jsonl_only_until_daily_consolidation",
            }
            with path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
                handle.write("\n")
        return {
            "ok": True,
            "chat_recorded": True,
            "day_id": day,
            "path": str(path),
            "chat_log_path": str(path),
            "turn_id": record["turn_id"],
            "block_id": record["block_id"],
            "line_id": record["line_id"],
            "record_count": turn_index,
            "record": record,
        }

    def today_chat_log(self, *, day_id: str | None = None, limit: int | None = None) -> dict[str, Any]:
        day = self._day_id(day_id)
        path = self.chat_log_path(day)
        records = self._read_records(path)
        if limit is not None and int(limit) > 0:
            records = records[-int(limit):]
        return {
            "ok": True,
            "day_id": day,
            "path": str(path),
            "record_count": len(self._read_records(path)),
            "records": records,
            "counts_written": False,
            "memory_role": "working_jsonl_provenance",
        }

    def search_today_chat(
        self,
        query: str,
        *,
        day_id: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        day = self._day_id(day_id)
        needle = str(query or "").casefold().strip()
        matches: list[dict[str, Any]] = []
        for record in self._read_records(self.chat_log_path(day)):
            haystack = f"{record.get('raw_text') or ''}\n{record.get('clean_text') or ''}".casefold()
            if needle and needle not in haystack:
                continue
            matches.append(record)
            if len(matches) >= max(int(limit or 20), 1):
                break
        return {
            "ok": True,
            "day_id": day,
            "query": query,
            "match_count": len(matches),
            "matches": matches,
            "counts_written": False,
        }

    def consolidate_day_chat(
        self,
        *,
        day_id: str | None = None,
        window_radius: int = 6,
        generation: int = 0,
    ) -> dict[str, Any]:
        day = self._day_id(day_id)
        source_path = self.chat_log_path(day)
        records = self._read_records(source_path)
        if not records:
            raise ValueError(f"No chat records found for {day}.")
        prepared_path = self.facade.chat_log_prepared_dir / f"{day}.txt"
        receipt_path = self.facade.chat_log_receipts_dir / f"{day}.consolidation.json"
        prepared_text = "".join(f"{str(record.get('clean_text') or '').strip()}\n" for record in records if str(record.get("clean_text") or "").strip())
        prepared_path.parent.mkdir(parents=True, exist_ok=True)
        prepared_path.write_text(prepared_text, encoding="utf-8")

        native_mapping = self.facade.map_document_to_user_counts_native(
            prepared_path,
            window_radius=window_radius,
            generation=generation,
        )
        receipt = {
            "schema_version": CHAT_CONSOLIDATION_SCHEMA,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "ok": bool(native_mapping.get("ok")),
            "day_id": day,
            "source_jsonl_path": str(source_path),
            "prepared_text_path": str(prepared_path),
            "receipt_path": str(receipt_path),
            "record_count": len(records),
            "counts_written": bool(native_mapping.get("ok")),
            "runtime": "native_cpp_daily_chat_consolidation",
            "native_mapping": native_mapping,
        }
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
        return receipt

    def _record_count(self, path: Path) -> int:
        if not path.exists():
            return 0
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())

    def _read_records(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        records: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                records.append(record)
        return records
