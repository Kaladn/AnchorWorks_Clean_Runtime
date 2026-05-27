from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .chat_models import L2Context, L3Lesson, L4ReasoningHooks


class MirrorWriter:
    def __init__(self, data_root: Path | str) -> None:
        self.root = Path(data_root).expanduser().resolve() / "State" / "chat_memory" / "mirrors"
        self.root.mkdir(parents=True, exist_ok=True)

    def write_l2(self, entry_id: str, context: L2Context, *, day: str | None = None) -> dict[str, Any]:
        payload = context.to_dict()
        if len(payload["subcontext_pointers"]) > 5:
            raise ValueError("L2 context allows at most 5 subcontext pointers")
        return self._append(day, entry_id, {"l2_context": payload})

    def write_l3(self, entry_id: str, lesson: L3Lesson, *, day: str | None = None) -> dict[str, Any]:
        payload = lesson.to_dict()
        if not payload["lesson_id"]:
            payload["lesson_id"] = f"lesson_{uuid4().hex[:12]}"
        return self._append(day, entry_id, {"l3_lessons": [payload]})

    def write_l4(self, entry_id: str, hooks: L4ReasoningHooks, *, day: str | None = None) -> dict[str, Any]:
        return self._append(day, entry_id, {"l4_reasoning": hooks.to_dict()})

    def _append(self, day: str | None, entry_id: str, layer_payload: dict[str, Any]) -> dict[str, Any]:
        row = {
            "schema_version": "anchorworks_chat_mirror@1",
            "entry_id": str(entry_id),
            "created_at_utc": _utc_now(),
            **layer_payload,
        }
        path = self.root / f"{day or _today()}.mirror.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        return {"ok": True, "mirror_path": str(path), "row": row}


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
