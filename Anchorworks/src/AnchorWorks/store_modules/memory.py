from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .common import StorePower


class MemoryStore(StorePower):
    """Explicit chat memory ownership."""

    def record_chat_turn(
        self,
        *,
        conversation_id: str,
        user_text: str,
        receipt: dict[str, Any],
    ) -> dict[str, Any]:
        facade = self.facade
        memory_dir = Path(getattr(facade, "chat_memory_dir", facade.paths.chat_memory_dir))
        memory_dir.mkdir(parents=True, exist_ok=True)
        clean_id = self._safe_conversation_id(conversation_id)
        path = memory_dir / f"{clean_id}.jsonl"
        row = {
            "schema_version": "anchorworks_explicit_chat_memory_turn@1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "conversation_id": clean_id,
            "user_text": str(user_text or ""),
            "assistant_text": str(receipt.get("speech") or receipt.get("response") or ""),
            "input_kind": str(receipt.get("input_kind") or ""),
            "frame_type": str(receipt.get("frame_type") or ""),
            "selected_engine_path": str(receipt.get("selected_engine_path") or ""),
            "evidence_lane": str(receipt.get("evidence_lane") or ""),
            "represented_anchors": list(receipt.get("represented_anchors") or []),
            "missing_anchors": list(receipt.get("missing_anchors") or []),
            "counts_written": False,
            "lifetime_written": False,
            "lexicon_written": False,
            "requires_finalize_for_intake": True,
        }
        line = json.dumps(row, ensure_ascii=False, sort_keys=True)
        lock = getattr(facade, "_lock", None)
        if lock is None:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        else:
            with lock:
                with path.open("a", encoding="utf-8") as handle:
                    handle.write(line + "\n")
        return {
            "ok": True,
            "chat_recorded": True,
            "conversation_id": clean_id,
            "chat_memory_path": str(path),
            "counts_written": False,
            "lifetime_written": False,
            "requires_finalize_for_intake": True,
        }

    @staticmethod
    def _safe_conversation_id(conversation_id: str) -> str:
        value = str(conversation_id or "").strip()
        if not value:
            value = "default"
        value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value)
        value = value.strip("._-")
        return value or "default"
