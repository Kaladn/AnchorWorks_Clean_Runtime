from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable


@dataclass
class ChatArchivePrepared:
    source_name: str
    source_path: str
    file_type: str
    original_size: int
    sha256: str
    converter: str
    prepared_text: str
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class _ArchiveLayout:
    archive_root: Path
    data_root: Path
    chats_dir: Path
    citations_dir: Path
    notes_dir: Path
    summaries_dir: Path
    memory_dir: Path
    maps_dir: Path
    chat_packs_dir: Path
    clearspeak_archived_chats_dir: Path
    citation_db_path: Path


def prepare_anchorworks_chat_archive(root_path: Path) -> ChatArchivePrepared:
    root = Path(root_path).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(root)
    if not root.is_dir():
        raise NotADirectoryError(root)

    layout = _detect_layout(root)
    warnings: list[str] = []
    sections: list[str] = [
        f"[SOURCE: {root.name}]",
        "[TYPE: anchorworks_chat_memory_archive]",
        f"[ARCHIVE_ROOT: {_one_line(layout.archive_root)}]",
        f"[DATA_ROOT: {_one_line(layout.data_root)}]",
    ]
    stats: dict[str, int] = {
        "chat_days": 0,
        "chat_messages": 0,
        "citations": 0,
        "notes": 0,
        "side_chats": 0,
        "summaries": 0,
        "lessons": 0,
        "reasoning_records": 0,
        "chat_maps": 0,
        "citation_db_rows": 0,
        "chat_pack_files": 0,
        "clearspeak_archived_chat_files": 0,
        "structural_memory_files": 0,
    }
    source_files: list[Path] = []

    chat_text, chat_stats, chat_files = _render_chat_days(layout.chats_dir, warnings)
    sections.extend(chat_text)
    _merge_stats(stats, chat_stats)
    source_files.extend(chat_files)

    citation_text, citation_stats, citation_files = _render_sidecar_collection(
        layout.citations_dir,
        suffix="*.citations.json",
        section_name="CHAT_CITATIONS",
        item_name="CITATION",
        warning_prefix="citation sidecar",
    )
    sections.extend(citation_text)
    stats["citations"] += citation_stats.get("items", 0)
    source_files.extend(citation_files)

    note_text, note_stats, note_files = _render_sidecar_collection(
        layout.notes_dir,
        suffix="*.notes.json",
        section_name="CHAT_NOTES",
        item_name="NOTE",
        warning_prefix="note sidecar",
    )
    sections.extend(note_text)
    stats["notes"] += note_stats.get("items", 0)
    source_files.extend(note_files)

    side_text, side_count, side_files = _render_side_chats(layout.memory_dir / "side_chats.json", warnings)
    sections.extend(side_text)
    stats["side_chats"] += side_count
    source_files.extend(side_files)

    summary_text, summary_count, summary_files = _render_text_tree(
        layout.summaries_dir,
        section_name="CHAT_SUMMARIES",
        record_name="SUMMARY_FILE",
        patterns=("*.txt", "*.md"),
        warnings=warnings,
    )
    sections.extend(summary_text)
    stats["summaries"] += summary_count
    source_files.extend(summary_files)

    lessons_text, lessons_count, lesson_files = _render_jsonl_tree(
        layout.memory_dir / "lessons",
        section_name="CHAT_LESSONS",
        record_name="LESSON",
        warnings=warnings,
    )
    sections.extend(lessons_text)
    stats["lessons"] += lessons_count
    source_files.extend(lesson_files)

    reasoning_text, reasoning_count, reasoning_files = _render_jsonl_tree(
        layout.memory_dir / "reasoning",
        section_name="CHAT_REASONING",
        record_name="REASONING_RECORD",
        warnings=warnings,
    )
    sections.extend(reasoning_text)
    stats["reasoning_records"] += reasoning_count
    source_files.extend(reasoning_files)

    structural_text, structural_count, structural_files = _render_text_tree(
        layout.memory_dir / "structural",
        section_name="STRUCTURAL_MEMORY",
        record_name="STRUCTURAL_MEMORY_FILE",
        patterns=("*.jsonl", "*.json", "*.txt"),
        warnings=warnings,
    )
    sections.extend(structural_text)
    stats["structural_memory_files"] += structural_count
    source_files.extend(structural_files)

    map_text, map_count, map_files = _render_json_tree(
        layout.maps_dir,
        section_name="CHAT_MAPS",
        record_name="CHAT_MAP_FILE",
        warnings=warnings,
    )
    sections.extend(map_text)
    stats["chat_maps"] += map_count
    source_files.extend(map_files)

    db_text, db_rows, db_files = _render_citation_db(layout.citation_db_path, warnings)
    sections.extend(db_text)
    stats["citation_db_rows"] += db_rows
    source_files.extend(db_files)

    pack_text, pack_count, pack_files = _render_chat_pack_files(layout.chat_packs_dir, warnings)
    sections.extend(pack_text)
    stats["chat_pack_files"] += pack_count
    source_files.extend(pack_files)

    lake_text, lake_count, lake_files = _render_text_tree(
        layout.clearspeak_archived_chats_dir,
        section_name="CLEARSPEAK_ARCHIVED_CHAT_INDEX",
        record_name="CLEARSPEAK_ARCHIVED_CHAT_FILE",
        patterns=("*.json", "*.jsonl", "*.txt", "*.md"),
        warnings=warnings,
    )
    sections.extend(lake_text)
    stats["clearspeak_archived_chat_files"] += lake_count
    source_files.extend(lake_files)

    prepared_text = "\n\n".join(section for section in sections if section.strip()).strip() + "\n"
    source_files = _dedupe_paths(source_files)
    digest = _archive_digest(root, source_files, prepared_text)
    original_size = sum(_safe_size(path) for path in source_files)

    return ChatArchivePrepared(
        source_name=f"{root.name}.anchorworks-chat-archive.txt",
        source_path=str(root),
        file_type="anchorworks-chat-archive",
        original_size=original_size,
        sha256=digest,
        converter="anchorworks-chat-archive-bridge",
        prepared_text=prepared_text,
        warnings=warnings,
        metadata={
            "bridge": "anchorworks_chat_archive",
            "archive_root": str(layout.archive_root),
            "data_root": str(layout.data_root),
            "source_file_count": len(source_files),
            **stats,
        },
    )


def _detect_layout(root: Path) -> _ArchiveLayout:
    data_root = root / "data" if (root / "data").is_dir() else root
    return _ArchiveLayout(
        archive_root=root,
        data_root=data_root,
        chats_dir=data_root / "chats",
        citations_dir=data_root / "citations",
        notes_dir=data_root / "notes",
        summaries_dir=data_root / "summaries",
        memory_dir=data_root / "memory",
        maps_dir=data_root / "maps",
        chat_packs_dir=data_root / "chat_packs",
        clearspeak_archived_chats_dir=data_root / "indexes" / ("lake" + "speak") / "index" / "chunks" / "chats",
        citation_db_path=data_root / "citations.db",
    )


def _render_chat_days(chats_dir: Path, warnings: list[str]) -> tuple[list[str], dict[str, int], list[Path]]:
    if not chats_dir.exists():
        return (["[CHAT_THREADS]\n[STATUS: not_found]"], {"chat_days": 0, "chat_messages": 0}, [])

    sections = [f"[CHAT_THREADS]\n[PATH: {_one_line(chats_dir)}]"]
    files = sorted(chats_dir.glob("*.jsonl"))
    source_files: list[Path] = []
    message_count = 0

    for path in files:
        source_files.append(path)
        day = path.stem
        rows = _read_jsonl(path, warnings, "chat log")
        sections.append(f"[CHAT_DAY: {_one_line(day)}]\n[CHAT_FILE: {_one_line(path.name)}]\n[MESSAGE_COUNT: {len(rows)}]")
        for line_number, row in rows:
            if not isinstance(row, dict):
                sections.append(
                    "\n".join([
                        f"[CHAT_RAW_LINE: {line_number}]",
                        _clean_multiline(row),
                    ])
                )
                continue
            message_count += 1
            sections.append(_render_chat_message(day, line_number, row))

    return sections, {"chat_days": len(files), "chat_messages": message_count}, source_files


def _render_chat_message(day: str, line_number: int, row: dict[str, Any]) -> str:
    content = _content_to_text(row.get("content", ""))
    metadata_lines = [
        "[CHAT_MESSAGE]",
        f"[DAY: {_one_line(day)}]",
        f"[LINE: {line_number}]",
    ]
    for label, key in [
        ("ID", "id"),
        ("MESSAGE_UUID", "message_uuid"),
        ("CONVERSATION_UUID", "conversation_uuid"),
        ("PARENT", "parent"),
        ("BRANCH", "branch"),
        ("FORK_POINT", "fork_point"),
        ("SENDER", "sender"),
        ("ACTOR", "actor"),
        ("SEAT", "seat"),
        ("MODEL", "model"),
        ("KIND", "kind"),
        ("TIMESTAMP", "timestamp"),
        ("HASH", "hash"),
        ("INTEGRITY_HASH", "integrity_hash"),
        ("ENVELOPE_VERSION", "envelope_version"),
    ]:
        if key in row and row.get(key) not in (None, ""):
            metadata_lines.append(f"[{label}: {_one_line(row.get(key))}]")

    model_identity = row.get("model_identity")
    if isinstance(model_identity, dict):
        metadata_lines.append(f"[MODEL_IDENTITY: {_json_line(model_identity)}]")

    return "\n".join(metadata_lines + ["", "[CHAT_CONTENT_START]", _clean_multiline(content), "[CHAT_CONTENT_END]"])


def _render_sidecar_collection(
    sidecar_dir: Path,
    *,
    suffix: str,
    section_name: str,
    item_name: str,
    warning_prefix: str,
) -> tuple[list[str], dict[str, int], list[Path]]:
    if not sidecar_dir.exists():
        return ([f"[{section_name}]\n[STATUS: not_found]"], {"items": 0}, [])

    sections = [f"[{section_name}]\n[PATH: {_one_line(sidecar_dir)}]"]
    files = sorted(sidecar_dir.glob(suffix))
    source_files: list[Path] = []
    item_count = 0

    for path in files:
        source_files.append(path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            sections.append(f"[{section_name}_FILE: {_one_line(path.name)}]\n[ERROR: {_one_line(exc)}]")
            continue

        records = _sidecar_records(payload)
        item_count += len(records)
        sections.append(f"[{section_name}_FILE: {_one_line(path.name)}]\n[ITEM_COUNT: {len(records)}]")
        for index, record in enumerate(records, start=1):
            sections.append(_render_record(item_name, record, fallback_index=index))

    return sections, {"items": item_count}, source_files


def _sidecar_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []

    by_id = payload.get("by_id")
    if isinstance(by_id, dict):
        return [item for item in by_id.values() if isinstance(item, dict)]

    by_block = payload.get("by_block")
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    if isinstance(by_block, dict):
        for block_key, values in by_block.items():
            if not isinstance(values, list):
                continue
            for item in values:
                if not isinstance(item, dict):
                    continue
                key = str(item.get("cite_id") or item.get("note_id") or item.get("coord") or f"{block_key}:{len(records)}")
                if key in seen:
                    continue
                seen.add(key)
                merged = dict(item)
                merged.setdefault("block_key", block_key)
                records.append(merged)
    return records


def _render_side_chats(path: Path, warnings: list[str]) -> tuple[list[str], int, list[Path]]:
    if not path.exists():
        return (["[SIDE_CHATS]\n[STATUS: not_found]"], 0, [])
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        warnings.append(f"side chat file failed: {path}: {exc}")
        return ([f"[SIDE_CHATS]\n[ERROR: {_one_line(exc)}]"], 0, [path])

    records = _records_from_any(payload)
    sections = [f"[SIDE_CHATS]\n[PATH: {_one_line(path)}]\n[ITEM_COUNT: {len(records)}]"]
    sections.extend(_render_record("SIDE_CHAT", record, fallback_index=index) for index, record in enumerate(records, start=1))
    return sections, len(records), [path]


def _render_text_tree(
    root: Path,
    *,
    section_name: str,
    record_name: str,
    patterns: tuple[str, ...],
    warnings: list[str],
) -> tuple[list[str], int, list[Path]]:
    if not root.exists():
        return ([f"[{section_name}]\n[STATUS: not_found]"], 0, [])

    files = _glob_many(root, patterns)
    sections = [f"[{section_name}]\n[PATH: {_one_line(root)}]\n[FILE_COUNT: {len(files)}]"]
    source_files: list[Path] = []
    for path in files:
        source_files.append(path)
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                content = path.read_text(encoding="cp1252")
            except Exception as exc:
                warnings.append(f"{section_name} read failed: {path}: {exc}")
                continue
        except Exception as exc:
            warnings.append(f"{section_name} read failed: {path}: {exc}")
            continue
        sections.append(
            "\n".join([
                f"[{record_name}: {_one_line(_relative(path, root))}]",
                f"[SIZE_BYTES: {_safe_size(path)}]",
                "",
                _clean_multiline(content),
            ])
        )
    return sections, len(files), source_files


def _render_json_tree(
    root: Path,
    *,
    section_name: str,
    record_name: str,
    warnings: list[str],
) -> tuple[list[str], int, list[Path]]:
    if not root.exists():
        return ([f"[{section_name}]\n[STATUS: not_found]"], 0, [])

    files = _glob_many(root, ("*.json", "*.jsonl"))
    sections = [f"[{section_name}]\n[PATH: {_one_line(root)}]\n[FILE_COUNT: {len(files)}]"]
    source_files: list[Path] = []
    for path in files:
        source_files.append(path)
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as exc:
            warnings.append(f"{section_name} read failed: {path}: {exc}")
            continue
        sections.append(
            "\n".join([
                f"[{record_name}: {_one_line(_relative(path, root))}]",
                f"[SIZE_BYTES: {_safe_size(path)}]",
                "",
                _clean_multiline(content),
            ])
        )
    return sections, len(files), source_files


def _render_jsonl_tree(
    root: Path,
    *,
    section_name: str,
    record_name: str,
    warnings: list[str],
) -> tuple[list[str], int, list[Path]]:
    if not root.exists():
        return ([f"[{section_name}]\n[STATUS: not_found]"], 0, [])

    files = sorted(root.glob("*.jsonl"))
    sections = [f"[{section_name}]\n[PATH: {_one_line(root)}]\n[FILE_COUNT: {len(files)}]"]
    source_files: list[Path] = []
    count = 0
    for path in files:
        source_files.append(path)
        rows = _read_jsonl(path, warnings, section_name)
        sections.append(f"[{section_name}_FILE: {_one_line(path.name)}]\n[ITEM_COUNT: {len(rows)}]")
        for line_number, row in rows:
            count += 1
            if isinstance(row, dict):
                record = dict(row)
                record.setdefault("line", line_number)
                sections.append(_render_record(record_name, record, fallback_index=count))
            else:
                sections.append(f"[{record_name}: {count}]\n[LINE: {line_number}]\n{_clean_multiline(row)}")
    return sections, count, source_files


def _render_citation_db(path: Path, warnings: list[str]) -> tuple[list[str], int, list[Path]]:
    if not path.exists():
        return (["[CITATION_DATABASE]\n[STATUS: not_found]"], 0, [])

    sections = [f"[CITATION_DATABASE]\n[PATH: {_one_line(path)}]"]
    rows_total = 0
    try:
        with sqlite3.connect(path) as conn:
            conn.row_factory = sqlite3.Row
            table_names = [
                row["name"]
                for row in conn.execute(
                    "select name from sqlite_master where type='table' order by name"
                ).fetchall()
            ]
            for table_name in table_names:
                safe_table = table_name.replace('"', '""')
                rows = [dict(row) for row in conn.execute(f'select * from "{safe_table}"').fetchall()]
                rows_total += len(rows)
                sections.append(f"[CITATION_DB_TABLE: {_one_line(table_name)}]\n[ROW_COUNT: {len(rows)}]")
                for index, row in enumerate(rows, start=1):
                    sections.append(_render_record("CITATION_DB_ROW", row, fallback_index=index))
    except Exception as exc:
        warnings.append(f"citation db read failed: {path}: {exc}")
        sections.append(f"[ERROR: {_one_line(exc)}]")
    return sections, rows_total, [path]


def _render_chat_pack_files(root: Path, warnings: list[str]) -> tuple[list[str], int, list[Path]]:
    if not root.exists():
        return (["[CHAT_PACKS]\n[STATUS: not_found]"], 0, [])

    patterns = ("metadata.json", "instructor.txt", "lesson.txt", "questions.json", "README.md", "readme.md", "*.session.json", "*.json")
    files = _glob_many(root, patterns)
    sections = [f"[CHAT_PACKS]\n[PATH: {_one_line(root)}]\n[FILE_COUNT: {len(files)}]"]
    source_files: list[Path] = []
    for path in files:
        if path.name.lower() == "side_chats.json":
            continue
        source_files.append(path)
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as exc:
            warnings.append(f"chat pack read failed: {path}: {exc}")
            continue
        sections.append(
            "\n".join([
                f"[CHAT_PACK_FILE: {_one_line(_relative(path, root))}]",
                f"[SIZE_BYTES: {_safe_size(path)}]",
                "",
                _clean_multiline(content),
            ])
        )
    return sections, len(source_files), source_files


def _render_record(name: str, record: dict[str, Any], *, fallback_index: int) -> str:
    lines = [f"[{name}: {_one_line(record.get('cite_id') or record.get('note_id') or record.get('id') or record.get('entry_id') or fallback_index)}]"]
    content_keys = {"content", "text", "body", "note", "summary", "lesson", "details"}
    content_parts: list[str] = []

    for key in sorted(record):
        value = record.get(key)
        if value in (None, ""):
            continue
        label = str(key).upper()
        if key in content_keys and isinstance(value, str):
            content_parts.append(f"[{label}_START]\n{_clean_multiline(value)}\n[{label}_END]")
            continue
        if isinstance(value, (dict, list)):
            lines.append(f"[{label}: {_json_line(value)}]")
        else:
            lines.append(f"[{label}: {_one_line(value)}]")

    return "\n".join(lines + ([""] + content_parts if content_parts else []))


def _read_jsonl(path: Path, warnings: list[str], label: str) -> list[tuple[int, Any]]:
    rows: list[tuple[int, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception as exc:
        warnings.append(f"{label} read failed: {path}: {exc}")
        return rows

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            rows.append((line_number, json.loads(line)))
        except json.JSONDecodeError:
            rows.append((line_number, line))
    return rows


def _records_from_any(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        if all(isinstance(value, dict) for value in payload.values()):
            return [dict(value, id=key) if "id" not in value else value for key, value in payload.items()]
        for key in ("items", "side_chats", "sessions", "records"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [payload]
    return []


def _glob_many(root: Path, patterns: Iterable[str]) -> list[Path]:
    files: dict[str, Path] = {}
    for pattern in patterns:
        for path in root.rglob(pattern):
            if path.is_file():
                files[str(path.resolve())] = path
    return sorted(files.values(), key=lambda item: str(item).lower())


def _merge_stats(target: dict[str, int], incoming: dict[str, int]) -> None:
    for key, value in incoming.items():
        target[key] = int(target.get(key, 0)) + int(value or 0)


def _dedupe_paths(paths: Iterable[Path]) -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []
    for path in paths:
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
    return out


def _archive_digest(root: Path, source_files: list[Path], prepared_text: str) -> str:
    hasher = hashlib.sha256()
    hasher.update(str(root).encode("utf-8", errors="ignore"))
    for path in source_files:
        hasher.update(str(path).encode("utf-8", errors="ignore"))
        try:
            hasher.update(path.read_bytes())
        except Exception:
            hasher.update(str(_safe_size(path)).encode("ascii"))
    hasher.update(prepared_text.encode("utf-8", errors="ignore"))
    return hasher.hexdigest()


def _safe_size(path: Path) -> int:
    try:
        return int(path.stat().st_size)
    except OSError:
        return 0


def _relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _content_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(_content_to_text(item) for item in value if _content_to_text(item))
    if isinstance(value, dict):
        for key in ("text", "content", "body", "message"):
            if key in value:
                return _content_to_text(value.get(key))
        if isinstance(value.get("parts"), list):
            return _content_to_text(value["parts"])
    return str(value)


def _json_line(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _one_line(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _clean_multiline(value: Any) -> str:
    return "\n".join(line.rstrip() for line in str(value or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")).strip()

