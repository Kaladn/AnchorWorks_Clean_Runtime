from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .anchorworks_chat_archive import prepare_anchorworks_chat_archive
from .clearspeak import ClearSpeakService
from .document_answer import DocumentAnswerAssembler
from .model_api_client import ModelApiClient


@dataclass
class ChatSendResult:
    ok: bool
    mode: str
    user_message: dict[str, Any]
    assistant_message: dict[str, Any]
    response: str
    clearspeak: dict[str, Any] | None = None
    memory_context: dict[str, Any] | None = None
    model_api: dict[str, Any] | None = None
    citations: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ChatMemorySystem:
    def __init__(self, data_root: Path, clearspeak: ClearSpeakService, model_api: ModelApiClient | None = None) -> None:
        self.store = clearspeak.store
        self.root = Path(data_root).expanduser().resolve() / "State" / "chat_memory"
        self.chats_dir = self.root / "chats"
        self.citations_dir = self.root / "citations"
        self.notes_dir = self.root / "notes"
        self.summaries_dir = self.root / "summaries"
        self.memory_dir = self.root / "memory"
        self.lessons_dir = self.memory_dir / "lessons"
        self.reasoning_dir = self.memory_dir / "reasoning"
        self.imports_dir = self.root / "imports"
        self.side_chats_path = self.memory_dir / "side_chats.json"
        self.clearspeak = clearspeak
        self.document_answer = DocumentAnswerAssembler(self.store)
        self.model_api = model_api or ModelApiClient()

        for path in [
            self.chats_dir,
            self.citations_dir,
            self.notes_dir,
            self.summaries_dir,
            self.lessons_dir,
            self.reasoning_dir,
            self.imports_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)
        if not self.side_chats_path.exists():
            self._write_json(self.side_chats_path, {})

    def status(self) -> dict[str, Any]:
        chat_files = sorted(self.chats_dir.glob("*.jsonl"))
        message_count = sum(len(self._read_jsonl(path)) for path in chat_files)
        return {
            "ok": True,
            "root": str(self.root),
            "chat_days": len(chat_files),
            "chat_messages": message_count,
            "citations": self._count_sidecar_items(self.citations_dir, "*.citations.json"),
            "notes": self._count_sidecar_items(self.notes_dir, "*.notes.json"),
            "summaries": len(list(self.summaries_dir.glob("*.txt"))),
            "lessons": sum(len(self._read_jsonl(path)) for path in self.lessons_dir.glob("*.jsonl")),
            "reasoning_records": sum(len(self._read_jsonl(path)) for path in self.reasoning_dir.glob("*.jsonl")),
            "side_chats": len(self._read_json(self.side_chats_path, {})),
            "imports": len(list(self.imports_dir.glob("*.archive.json"))),
            "clearspeak": self.clearspeak.status(),
            "model_api": self.model_api.status(),
        }

    def history(self, day: str | None = None, branch: str = "main", limit: int = 200) -> dict[str, Any]:
        target_day = day or _today()
        rows = self._read_jsonl(self._day_path(target_day))
        filtered = [
            row for row in rows
            if not branch or branch == "all" or str(row.get("branch") or "main") == branch
        ]
        limited = filtered[-max(1, int(limit or 200)):]
        return {
            "ok": True,
            "day": target_day,
            "branch": branch or "all",
            "messages": limited,
            "citations_by_block": self._load_sidecar_by_block(self._citation_path(target_day)),
            "notes_by_block": self._load_sidecar_by_block(self._note_path(target_day)),
        }

    def preview_finalize(self, day: str | None = None, branch: str = "main") -> dict[str, Any]:
        target_day = day or _today()
        source_name, content, message_count = self._chat_ingest_source(target_day, branch or "main")
        preview = self.store.preview_document_intake(
            source_name=source_name,
            content=content,
            file_size=len(content.encode("utf-8")),
            file_type="anchorworks-chat-transcript",
            source_path=str(self._day_path(target_day)),
        )
        preview["chat_day"] = target_day
        preview["chat_branch"] = branch or "main"
        preview["chat_message_count"] = message_count
        preview["chat_ingest_source_name"] = source_name
        preview["prepared_text"] = content
        return preview

    def finalize_day(self, day: str | None = None, branch: str = "main") -> dict[str, Any]:
        target_day = day or _today()
        source_name, content, message_count = self._chat_ingest_source(target_day, branch or "main")
        if message_count <= 0:
            raise ValueError("no chat messages available to finalize")
        result = self.store.build_intake_mapping(
            source_name=source_name,
            content=content,
            count_target="user_chat",
        )
        self.add_reasoning(
            event="chat_finalize",
            summary=f"Finalized chat day {target_day} branch {branch or 'main'} into user-side anchor counts.",
            refs=[result.get("saved_map_name", "")],
        )
        result["chat_day"] = target_day
        result["chat_branch"] = branch or "main"
        result["chat_message_count"] = message_count
        result["chat_ingest_source_name"] = source_name
        return result

    def send(self, message: str, mode: str = "clearspeak", branch: str = "main", model: str = "") -> ChatSendResult:
        clean_message = str(message or "").strip()
        if not clean_message:
            raise ValueError("message required")

        target_branch = branch or "main"
        mode_name = (mode or "clearspeak").strip().lower()
        if mode_name in {"api", "external", "model"} and not self.model_api.status().get("configured"):
            raise ValueError("external model API key is not configured")

        memory_context = self.memory_context()
        user_message = self.log_message(
            sender="user",
            content=clean_message,
            branch=target_branch,
            actor="user",
            seat="operator",
        )

        clearspeak_payload: dict[str, Any] | None = None
        model_api_payload: dict[str, Any] | None = None
        citations: list[dict[str, Any]] = []
        if mode_name in {"counts", "count"}:
            clearspeak_result = self.clearspeak.query(clean_message)
            clearspeak_payload = clearspeak_result.to_dict()
            clearspeak_payload["evidence_mode"] = "counts"
            clearspeak_payload["engine"] = "clearspeak_counts"
            clearspeak_payload["contract"] = {
                "counts_mode_never_calls_documents": True,
                "document_mode_never_pretends_to_be_counts": True,
                "memory_writes": False,
            }
            response = clearspeak_payload["response"]
            citations = clearspeak_payload.get("citations") or []
            actor = "clearspeak"
            engine = "clearspeak_counts"
            provider = "anchorworks"
            mode_name = "counts"
        elif mode_name in {"clearspeak", "auto", "documents", "document", "maps", "mapped", "mapped_documents"}:
            requested_documents = mode_name in {"documents", "document", "maps", "mapped", "mapped_documents"}
            document_result = self.document_answer.answer(clean_message)
            document_payload = document_result.to_dict()
            if document_result.ok:
                clearspeak_payload = document_payload
                response = document_result.response
                citations = document_result.citations
                actor = "clearspeak"
                engine = document_result.engine
                provider = "anchorworks"
                mode_name = "documents" if requested_documents else "clearspeak"
            elif requested_documents:
                clearspeak_payload = {
                    **document_payload,
                    "response": "Document Mode found no source-local map support for that question. Counts were not used as a substitute.",
                    "evidence_mode": "documents",
                    "engine": "document_answer_no_map_support",
                    "contract": {
                        "counts_used_as_substitute": False,
                        "document_mode_never_pretends_to_be_counts": True,
                        "memory_writes": False,
                    },
                }
                response = clearspeak_payload["response"]
                citations = []
                actor = "clearspeak"
                engine = "document_answer_no_map_support"
                provider = "anchorworks"
                mode_name = "documents"
            else:
                clearspeak_result = self.clearspeak.query(clean_message)
                clearspeak_payload = clearspeak_result.to_dict()
                clearspeak_payload["evidence_mode"] = "counts"
                clearspeak_payload["engine"] = "clearspeak_counts"
                clearspeak_payload["document_fallback_reason"] = "no_source_local_map_support"
                response = clearspeak_payload["response"]
                citations = clearspeak_payload.get("citations") or []
                actor = "clearspeak"
                engine = "clearspeak_counts"
                provider = "anchorworks"
        elif mode_name == "clearspeak":
            clearspeak_result = self.clearspeak.query(clean_message)
            clearspeak_payload = clearspeak_result.to_dict()
            response = clearspeak_payload["response"]
            citations = clearspeak_payload.get("citations") or []
            actor = "clearspeak"
            engine = "clearspeak"
            provider = "anchorworks"
        elif mode_name in {"api", "external", "model"}:
            model_api_payload = self.model_api.chat(
                self._model_api_messages(branch=target_branch, memory_context=memory_context),
                model=model,
            )
            response = model_api_payload["response"]
            actor = "external_model"
            engine = str(model_api_payload.get("model") or model or self.model_api.default_model)
            provider = "external_api"
            mode_name = "api"
        else:
            response = self._compose_memory_response(clean_message, memory_context)
            actor = "chat_memory"
            engine = "chat_memory"
            provider = "anchorworks"

        assistant_message = self.log_message(
            sender="assistant",
            content=response,
            branch=target_branch,
            parent=user_message.get("message_uuid"),
            actor=actor,
            seat="local",
            model_identity={
                "provider": provider,
                "engine": engine,
                "evidence_mode": str((clearspeak_payload or {}).get("evidence_mode") or ("counts" if "count" in engine else "")),
                "evidence_engine": str((clearspeak_payload or {}).get("engine") or engine),
            },
        )

        for citation in citations:
            self.attach_citation(
                day=assistant_message["day"],
                message_id=assistant_message["message_uuid"],
                block_id="b0",
                block_ordinal=0,
                coord=str(citation.get("coord") or ""),
                subject=str(citation.get("anchor") or citation.get("source_name") or "ClearSpeak evidence"),
                note=f"observations: {citation.get('observations', 0)}",
                source=str(citation.get("source") or "clearspeak"),
            )

        return ChatSendResult(
            ok=True,
            mode=mode_name,
            user_message=user_message,
            assistant_message=assistant_message,
            response=response,
            clearspeak=clearspeak_payload,
            memory_context=memory_context,
            model_api=model_api_payload,
            citations=citations,
        )

    def _model_api_messages(self, *, branch: str, memory_context: dict[str, Any]) -> list[dict[str, str]]:
        recent = self.history(branch=branch, limit=16).get("messages") or []
        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    "You are the AnchorWorks external model lane. Answer the user clearly. "
                    "Do not claim to update the lexicon, counts, citations, notes, or ingestion state."
                ),
            }
        ]
        summaries = memory_context.get("summaries") or []
        lessons = memory_context.get("lessons") or []
        reasoning = memory_context.get("reasoning") or []
        if summaries or lessons or reasoning:
            messages.append({
                "role": "system",
                "content": (
                    f"Memory context available: {len(summaries)} summaries, "
                    f"{len(lessons)} lessons, {len(reasoning)} reasoning records."
                ),
            })

        for row in recent:
            if row.get("kind") != "CHAT":
                continue
            sender = row.get("sender")
            if sender not in {"user", "assistant"}:
                continue
            content = str(row.get("content") or "").strip()
            if not content:
                continue
            messages.append({
                "role": "assistant" if sender == "assistant" else "user",
                "content": content,
            })
        return messages

    def _chat_ingest_source(self, day: str, branch: str) -> tuple[str, str, int]:
        history = self.history(day=day, branch=branch, limit=100000)
        messages = history.get("messages") or []
        source_name = f"chat-{day}-{_safe_name(branch or 'main')}.anchorworks-chat.txt"
        lines = [
            "[SOURCE: AnchorWorks Chat Memory]",
            "[TYPE: finalized_chat_transcript]",
            f"[CHAT_DAY: {day}]",
            f"[CHAT_BRANCH: {branch or 'main'}]",
            f"[MESSAGE_COUNT: {len(messages)}]",
        ]
        for message in messages:
            lines.extend([
                "",
                "[CHAT_MESSAGE]",
                f"[MESSAGE_UUID: {_one_line(message.get('message_uuid'))}]",
                f"[ID: {_one_line(message.get('id'))}]",
                f"[PARENT: {_one_line(message.get('parent'))}]",
                f"[SENDER: {_one_line(message.get('sender'))}]",
                f"[ACTOR: {_one_line(message.get('actor'))}]",
                f"[SEAT: {_one_line(message.get('seat'))}]",
                f"[KIND: {_one_line(message.get('kind'))}]",
                f"[TIME: {_one_line(message.get('timestamp'))}]",
                "",
                "[CONTENT_START]",
                _clean_multiline(message.get("content") or ""),
                "[CONTENT_END]",
            ])
        return source_name, "\n".join(lines).strip() + "\n", len(messages)

    def log_message(
        self,
        *,
        sender: str,
        content: str,
        branch: str = "main",
        parent: str | None = None,
        actor: str = "",
        seat: str = "",
        kind: str = "CHAT",
        model_identity: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        day = _today()
        path = self._day_path(day)
        rows = self._read_jsonl(path)
        next_id = 1 + max([int(row.get("id", 0) or 0) for row in rows] or [0])
        timestamp = _utc_now()
        message_uuid = str(uuid4())
        record = {
            "id": next_id,
            "parent": parent,
            "branch": branch or "main",
            "sender": sender,
            "actor": actor or sender,
            "seat": seat or "",
            "content": content,
            "timestamp": timestamp,
            "message_uuid": message_uuid,
            "conversation_uuid": f"{day}:{branch or 'main'}",
            "kind": kind,
            "envelope_version": "anchorworks-chat-memory-v1",
            "day": day,
        }
        if model_identity:
            record["model_identity"] = model_identity
        record["hash"] = _short_hash(record)
        record["integrity_hash"] = _full_hash(record)
        self._append_jsonl(path, record)
        return record

    def memory_context(self, days: int = 7) -> dict[str, Any]:
        summaries = self._recent_summary_rows(days)
        lessons = self._recent_jsonl_rows(self.lessons_dir, days)
        reasoning = self._recent_jsonl_rows(self.reasoning_dir, min(days, 3))
        return {
            "summaries": summaries,
            "lessons": lessons,
            "reasoning": reasoning,
            "side_chats": list(self._read_json(self.side_chats_path, {}).values()),
        }

    def create_side_chat(
        self,
        *,
        source_day: str,
        message_id: str,
        description: str = "",
        main_branch: str = "main",
    ) -> dict[str, Any]:
        side_id = f"side_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"
        payload = self._read_json(self.side_chats_path, {})
        row = {
            "side_chat_id": side_id,
            "main_branch": main_branch or "main",
            "side_branch": side_id,
            "source_day": source_day,
            "source_message_id": message_id,
            "description": description,
            "created_at": _utc_now(),
        }
        payload[side_id] = row
        self._write_json(self.side_chats_path, payload)
        self.log_message(
            sender="system",
            content=f"Side chat started: {side_id}\nSource: {source_day} {message_id}\n{description}",
            branch=main_branch or "main",
            kind="SIDE_CHAT_LINK",
            actor="system",
        )
        return {"ok": True, **row}

    def attach_citation(
        self,
        *,
        day: str,
        message_id: str,
        block_id: str,
        block_ordinal: int,
        coord: str,
        subject: str = "",
        note: str = "",
        source: str = "ui",
    ) -> dict[str, Any]:
        if not coord:
            raise ValueError("coord required")
        path = self._citation_path(day)
        payload = self._read_sidecar(path)
        cite_id = f"cite_{uuid4().hex[:16]}"
        key = f"{message_id}:{block_id}"
        record = {
            "cite_id": cite_id,
            "coord": coord,
            "source": source,
            "subject": subject,
            "note": note,
            "day": day,
            "message_id": message_id,
            "block_id": block_id,
            "block_ordinal": int(block_ordinal or 0),
            "created_at": _utc_now(),
        }
        payload["by_id"][cite_id] = record
        payload["by_block"].setdefault(key, []).append(record)
        self._write_json(path, payload)
        return {"ok": True, "cite": record}

    def attach_note(
        self,
        *,
        day: str,
        message_id: str,
        block_id: str,
        block_ordinal: int,
        text: str,
    ) -> dict[str, Any]:
        if not text.strip():
            raise ValueError("note text required")
        path = self._note_path(day)
        payload = self._read_sidecar(path)
        note_id = f"note_{uuid4().hex[:16]}"
        key = f"{message_id}:{block_id}"
        record = {
            "note_id": note_id,
            "text": text,
            "day": day,
            "message_id": message_id,
            "block_id": block_id,
            "block_ordinal": int(block_ordinal or 0),
            "created_at": _utc_now(),
        }
        payload["by_id"][note_id] = record
        payload["by_block"].setdefault(key, []).append(record)
        self._write_json(path, payload)
        return {"ok": True, "note": record}

    def save_summary(self, day: str, text: str) -> dict[str, Any]:
        target_day = day or _today()
        path = self.summaries_dir / f"{target_day}.txt"
        path.write_text(str(text or "").strip() + "\n", encoding="utf-8")
        return {"ok": True, "day": target_day, "path": str(path)}

    def add_lesson(self, text: str, lesson_type: str = "fact", significance: str = "") -> dict[str, Any]:
        row = {
            "id": f"lesson_{uuid4().hex[:12]}",
            "type": lesson_type or "fact",
            "lesson": text,
            "significance": significance,
            "created_at": _utc_now(),
        }
        self._append_jsonl(self.lessons_dir / f"{_today()}.jsonl", row)
        return {"ok": True, "lesson": row}

    def add_reasoning(self, event: str, summary: str, refs: list[str] | None = None) -> dict[str, Any]:
        row = {
            "id": f"reason_{uuid4().hex[:12]}",
            "event": event or "reasoning",
            "summary": summary,
            "refs": refs or [],
            "created_at": _utc_now(),
        }
        self._append_jsonl(self.reasoning_dir / f"{_today()}.jsonl", row)
        return {"ok": True, "reasoning": row}

    def import_archive(self, archive_root: Path) -> dict[str, Any]:
        prepared = prepare_anchorworks_chat_archive(archive_root)
        digest = prepared.sha256[:16]
        text_path = self.imports_dir / f"{digest}.prepared.txt"
        meta_path = self.imports_dir / f"{digest}.archive.json"
        text_path.write_text(prepared.prepared_text, encoding="utf-8")
        self._write_json(meta_path, {key: value for key, value in prepared.to_dict().items() if key != "prepared_text"})
        self._copy_archive_fragments(Path(archive_root).expanduser().resolve(), digest)
        self.log_message(
            sender="system",
            content=f"Imported AnchorWorks archive bridge file: {prepared.source_name}\n{prepared.metadata}",
            kind="CHAT_ARCHIVE_IMPORT",
            actor="system",
        )
        return {
            "ok": True,
            "prepared_path": str(text_path),
            "metadata_path": str(meta_path),
            "prepared": prepared.to_dict(),
        }

    def _copy_archive_fragments(self, archive_root: Path, digest: str) -> None:
        source_data = archive_root / "data" if (archive_root / "data").is_dir() else archive_root
        target = self.imports_dir / digest
        target.mkdir(parents=True, exist_ok=True)
        for name in ["chats", "citations", "notes", "summaries", "memory", "maps", "chat_packs"]:
            src = source_data / name
            if not src.exists():
                continue
            dst = target / name
            if dst.exists():
                shutil.rmtree(dst)
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

    def _compose_memory_response(self, message: str, memory_context: dict[str, Any]) -> str:
        summary_count = len(memory_context.get("summaries") or [])
        lesson_count = len(memory_context.get("lessons") or [])
        reasoning_count = len(memory_context.get("reasoning") or [])
        return "\n".join([
            "Chat memory received and stored the message.",
            f"Recent summaries: {summary_count}",
            f"Recent lessons: {lesson_count}",
            f"Recent reasoning records: {reasoning_count}",
            "Switch to ClearSpeak mode to answer directly from lifetime anchor counts.",
        ])

    def _recent_summary_rows(self, days: int) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for day in _recent_days(days):
            path = self.summaries_dir / f"{day}.txt"
            if path.exists():
                rows.append({"day": day, "summary": path.read_text(encoding="utf-8").strip()})
        return rows

    def _recent_jsonl_rows(self, directory: Path, days: int) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for day in _recent_days(days):
            for row in self._read_jsonl(directory / f"{day}.jsonl"):
                if isinstance(row, dict):
                    rows.append({"day": day, **row})
        return rows

    def _day_path(self, day: str) -> Path:
        return self.chats_dir / f"{day}.jsonl"

    def _citation_path(self, day: str) -> Path:
        return self.citations_dir / f"{day}.citations.json"

    def _note_path(self, day: str) -> Path:
        return self.notes_dir / f"{day}.notes.json"

    def _read_sidecar(self, path: Path) -> dict[str, Any]:
        payload = self._read_json(path, {})
        if not isinstance(payload, dict):
            payload = {}
        payload.setdefault("by_block", {})
        payload.setdefault("by_id", {})
        return payload

    def _load_sidecar_by_block(self, path: Path) -> dict[str, Any]:
        return self._read_sidecar(path).get("by_block", {})

    def _count_sidecar_items(self, directory: Path, pattern: str) -> int:
        count = 0
        for path in directory.glob(pattern):
            payload = self._read_sidecar(path)
            count += len(payload.get("by_id", {}))
        return count

    def _read_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def _write_json(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read_jsonl(self, path: Path) -> list[Any]:
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

    def _append_jsonl(self, path: Path, row: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _recent_days(days: int) -> list[str]:
    today = datetime.now(timezone.utc).date()
    return [(today - timedelta(days=index)).isoformat() for index in range(max(1, int(days or 1)))]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_name(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in str(value or "main")).strip("_")
    return cleaned or "main"


def _one_line(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _clean_multiline(value: Any) -> str:
    return "\n".join(line.rstrip() for line in str(value or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")).strip()


def _short_hash(row: dict[str, Any]) -> str:
    return _full_hash(row)[:12]


def _full_hash(row: dict[str, Any]) -> str:
    payload = {key: value for key, value in row.items() if key not in {"hash", "integrity_hash"}}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
