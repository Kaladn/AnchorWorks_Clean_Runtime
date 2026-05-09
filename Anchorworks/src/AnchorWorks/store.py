from __future__ import annotations

import hashlib
import json
import logging
import random
import re
import threading
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .anchorworks_chat_archive import prepare_anchorworks_chat_archive
from .document_prep import prepare_bytes, prepare_file
from .intake import (
    DEFAULT_WINDOW_RADIUS,
    EMOJI_ANCHOR,
    build_anchor_map,
    build_context_views,
    compose_anchor_stream,
    extract_anchor_rows,
    split_paragraphs,
)
from .positional_resonance import (
    build_source_local_resonance_index,
    write_jsonl,
)


logger = logging.getLogger(__name__)
_SPELL_SUGGESTION_WORD_RE = re.compile(r"^[A-Za-z]+(?:['’][A-Za-z]+)*$")
_SPELL_SUGGESTION_MISSING_LIMIT = 512
TEMP_SYMBOL_VERSION = "temp_symbol@1"
TEMP_SYMBOL_PREFIX = "U"
TEMP_SYMBOL_HEX_LENGTH = 11

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_visual_preview_content(content: str) -> bool:
    if not content:
        return False
    markers = (
        "[TYPE: image]",
        "Visual_Record_ID:",
        "Authority: source_local_visual_evidence",
        "Approval_Status: preview_only",
        "Writes_Allowed: maps=false counts=false lifetime=false lexicon=false",
    )
    return all(marker in content for marker in markers)


def _normalize_with_source_index(text: str) -> tuple[str, list[int]]:
    normalized_chars: list[str] = []
    source_index: list[int] = []
    previous_space = False
    for index, char in enumerate(str(text or "").replace("\r\n", "\n").replace("\r", "\n")):
        if char.isspace():
            if previous_space:
                continue
            normalized_chars.append(" ")
            source_index.append(index)
            previous_space = True
            continue
        normalized_chars.append(char)
        source_index.append(index)
        previous_space = False
    return "".join(normalized_chars).strip(), source_index


class LexiconStore:
    def __init__(self, data_root: Path) -> None:
        self.root = Path(data_root).expanduser().resolve()
        self.canonical_dir = self.root / "Canonical"
        self.spare_dir = self.root / "Spare_Slots"
        self.spare_slots_path = self.spare_dir / "spare_slots.json"
        self.structural_file = self.root / "Structural" / "structural.json"
        self.state_dir = self.root / "State"
        self.user_state_dir = self.state_dir / "user"
        self.user_lexicon_dir = self.user_state_dir / "user_lexicon"
        self.user_counts_dir = self.user_state_dir / "user_counts"
        self.chat_counts_dir = self.user_state_dir / "chat_counts"
        self.ingest_staging_dir = self.user_state_dir / "ingest_staging"
        self.rejected_or_literal_clusters_dir = self.user_state_dir / "rejected_or_literal_clusters"
        self.observed_maps_dir = self.state_dir / "observed_maps"
        self.misspelled_reviews_dir = self.state_dir / "misspelled_reviews"
        self.temp_lexicons_dir = self.state_dir / "temp_lexicons" / "source_local"
        self.source_local_preview_counts_dir = self.state_dir / "source_local_preview_counts"
        self.source_local_occurrences_dir = self.state_dir / "source_local_occurrences"
        self.source_local_resonance_dir = self.state_dir / "source_local_resonance"
        self.visual_intake_dir = self.state_dir / "visual_intake"
        self.visual_intake_packets_dir = self.visual_intake_dir / "packets"
        self.visual_intake_manifests_dir = self.visual_intake_dir / "manifests"
        self.visual_intake_region_maps_dir = self.visual_intake_dir / "region_maps"
        self.visual_intake_recognition_layers_dir = self.visual_intake_dir / "recognition_layers"
        self.flat_documents_dir = self.state_dir / "flat_documents"
        self.flat_documents_raw_dir = self.flat_documents_dir / "raw"
        self.flat_documents_symbolic_dir = self.flat_documents_dir / "symbolic"
        self.flat_documents_block_index_dir = self.flat_documents_dir / "block_index"
        self.flat_documents_visual_links_dir = self.flat_documents_dir / "visual_links"
        self.flat_documents_occurrence_index_dir = self.flat_documents_dir / "occurrence_index"
        self.intake_uploads_dir = self.state_dir / "intake_uploads"
        self.lifetime_counts_path = self.state_dir / "lifetime_co_occurrence_counts.json"
        self.missing_anchor_registry_path = self.state_dir / "missing_anchor_registry.json"
        self.unmatched_path = self.state_dir / "unmatched_words.json"
        self.pending_path = self.state_dir / "pending_words.json"
        self.ignored_path = self.state_dir / "ignored_words.json"
        self.custom_entries_path = self.user_state_dir / "custom_entries.json"
        self.user_lexicon_path = self.user_lexicon_dir / "anchors.json"
        self.user_counts_path = self.user_counts_dir / "lifetime_co_occurrence_counts.json"
        self.chat_counts_path = self.chat_counts_dir / "chat_co_occurrence_counts.json"
        self.ingest_staging_manifest_path = self.ingest_staging_dir / "manifest.json"
        self.rejected_or_literal_clusters_path = self.rejected_or_literal_clusters_dir / "clusters.json"
        self._known_anchor_index: set[str] | None = None
        self._known_anchor_spell_index: dict[tuple[str, tuple[bool, int], int], list[str]] | None = None
        self._spare_entries_cache: list[dict[str, Any]] | None = None
        self._spare_entries_cache_key: tuple[tuple[str, int | None, int | None], ...] | None = None
        self._lock = threading.RLock()

        self.spare_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.user_state_dir.mkdir(parents=True, exist_ok=True)
        self.user_lexicon_dir.mkdir(parents=True, exist_ok=True)
        self.user_counts_dir.mkdir(parents=True, exist_ok=True)
        self.chat_counts_dir.mkdir(parents=True, exist_ok=True)
        self.ingest_staging_dir.mkdir(parents=True, exist_ok=True)
        self.rejected_or_literal_clusters_dir.mkdir(parents=True, exist_ok=True)
        self.observed_maps_dir.mkdir(parents=True, exist_ok=True)
        self.misspelled_reviews_dir.mkdir(parents=True, exist_ok=True)
        self.temp_lexicons_dir.mkdir(parents=True, exist_ok=True)
        self.source_local_preview_counts_dir.mkdir(parents=True, exist_ok=True)
        self.source_local_occurrences_dir.mkdir(parents=True, exist_ok=True)
        self.source_local_resonance_dir.mkdir(parents=True, exist_ok=True)
        self.visual_intake_packets_dir.mkdir(parents=True, exist_ok=True)
        self.visual_intake_manifests_dir.mkdir(parents=True, exist_ok=True)
        self.visual_intake_region_maps_dir.mkdir(parents=True, exist_ok=True)
        self.visual_intake_recognition_layers_dir.mkdir(parents=True, exist_ok=True)
        self.flat_documents_raw_dir.mkdir(parents=True, exist_ok=True)
        self.flat_documents_symbolic_dir.mkdir(parents=True, exist_ok=True)
        self.flat_documents_block_index_dir.mkdir(parents=True, exist_ok=True)
        self.flat_documents_visual_links_dir.mkdir(parents=True, exist_ok=True)
        self.flat_documents_occurrence_index_dir.mkdir(parents=True, exist_ok=True)
        self.intake_uploads_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_state_file(self.unmatched_path, [])
        self._ensure_state_file(self.pending_path, [])
        self._ensure_state_file(self.ignored_path, [])
        self._ensure_state_file(self.lifetime_counts_path, {})
        self._ensure_state_file(self.missing_anchor_registry_path, [])
        self._ensure_state_file(self.custom_entries_path, {})
        self._ensure_state_file(self.user_lexicon_path, [])
        self._ensure_state_file(self.user_counts_path, {})
        self._ensure_state_file(self.chat_counts_path, {})
        self._ensure_state_file(self.ingest_staging_manifest_path, {"items": []})
        self._ensure_state_file(self.rejected_or_literal_clusters_path, [])

    def _ensure_state_file(self, path: Path, default: Any) -> None:
        if not path.exists():
            path.write_text(json.dumps(default, ensure_ascii=False, indent=2), encoding="utf-8")

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

    def user_storage_status(self) -> dict[str, Any]:
        directories = {
            "user_lexicon": self.user_lexicon_dir,
            "user_counts": self.user_counts_dir,
            "chat_counts": self.chat_counts_dir,
            "ingest_staging": self.ingest_staging_dir,
            "rejected_or_literal_clusters": self.rejected_or_literal_clusters_dir,
        }
        files = {
            "user_lexicon": self.user_lexicon_path,
            "user_counts": self.user_counts_path,
            "chat_counts": self.chat_counts_path,
            "ingest_staging_manifest": self.ingest_staging_manifest_path,
            "rejected_or_literal_clusters": self.rejected_or_literal_clusters_path,
        }
        return {
            "ok": True,
            "root": str(self.user_state_dir),
            "directories": [
                {"name": name, "path": str(path), "exists": path.is_dir()}
                for name, path in directories.items()
            ],
            "files": [
                {
                    "name": name,
                    "path": str(path),
                    "exists": path.is_file(),
                    "size_bytes": path.stat().st_size if path.exists() else 0,
                }
                for name, path in files.items()
            ],
            "protected_paths": {
                "main_lexicon": str(self.canonical_dir),
                "base_counts": str(self.lifetime_counts_path),
            },
        }

    def _read_entries(self, path: Path) -> list[dict[str, Any]]:
        data = self._read_json(path, [])
        return data if isinstance(data, list) else []

    def _write_entries(self, path: Path, entries: list[dict[str, Any]]) -> None:
        self._write_json(path, entries)

    def _invalidate_known_anchor_index(self) -> None:
        self._known_anchor_index = None
        self._known_anchor_spell_index = None

    def _invalidate_spare_entries_cache(self) -> None:
        self._spare_entries_cache = None
        self._spare_entries_cache_key = None

    def _load_pending(self) -> list[dict[str, Any]]:
        data = self._read_json(self.pending_path, [])
        out: list[dict[str, Any]] = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    word = self.normalize_anchor(item.get("word", ""))
                    if word:
                        out.append({
                            "word": word,
                            "frequency": int(item.get("frequency", 0) or 0),
                            "added_at": item.get("added_at") or _utc_now(),
                        })
                elif isinstance(item, str):
                    word = self.normalize_anchor(item)
                    if word:
                        out.append({"word": word, "frequency": 0, "added_at": _utc_now()})
        return out

    def _write_pending(self, entries: list[dict[str, Any]]) -> None:
        self._write_json(self.pending_path, entries)

    def _load_unmatched(self) -> list[dict[str, Any]]:
        data = self._read_json(self.unmatched_path, [])
        out: list[dict[str, Any]] = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    word = self.normalize_anchor(item.get("word", ""))
                    if word:
                        out.append({
                            "word": word,
                            "frequency": int(item.get("frequency", 0) or 0),
                            "first_seen": item.get("first_seen") or _utc_now(),
                        })
                elif isinstance(item, str):
                    word = self.normalize_anchor(item)
                    if word:
                        out.append({"word": word, "frequency": 0, "first_seen": _utc_now()})
        return out

    def _write_unmatched(self, entries: list[dict[str, Any]]) -> None:
        self._write_json(self.unmatched_path, entries)

    def _load_missing_anchor_registry(self) -> list[dict[str, Any]]:
        data = self._read_json(self.missing_anchor_registry_path, [])
        rows: list[dict[str, Any]] = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    anchor = item.get("anchor")
                    if isinstance(anchor, str) and anchor:
                        rows.append({
                            "anchor": anchor,
                            "observations": int(item.get("observations", 0) or 0),
                            "first_seen": item.get("first_seen") or _utc_now(),
                            "last_seen": item.get("last_seen") or _utc_now(),
                        })
        return rows

    def _write_missing_anchor_registry(self, entries: list[dict[str, Any]]) -> None:
        self._write_json(self.missing_anchor_registry_path, entries)

    def _register_missing_anchors(self, missing_counts: Counter[str]) -> None:
        if not missing_counts:
            return

        with self._lock:
            existing_rows = self._load_missing_anchor_registry()
            existing = {row["anchor"]: row for row in existing_rows}
            timestamp = _utc_now()

            for anchor, count in missing_counts.items():
                row = existing.get(anchor)
                if row is None:
                    existing[anchor] = {
                        "anchor": anchor,
                        "observations": int(count),
                        "first_seen": timestamp,
                        "last_seen": timestamp,
                    }
                    continue

                row["observations"] = int(row.get("observations", 0) or 0) + int(count)
                row["last_seen"] = timestamp

            rows = sorted(existing.values(), key=lambda item: (-int(item["observations"]), item["anchor"]))
            self._write_missing_anchor_registry(rows)

    def _load_ignored(self) -> list[str]:
        data = self._read_json(self.ignored_path, [])
        if not isinstance(data, list):
            return []
        return sorted({self.normalize_anchor(item) for item in data if self.normalize_anchor(item)})

    def _write_ignored(self, words: list[str]) -> None:
        self._write_json(self.ignored_path, sorted({self.normalize_anchor(word) for word in words if self.normalize_anchor(word)}))

    def normalize_word(self, word: str) -> str:
        return str(word or "").strip().lower()

    def normalize_anchor(self, word: str) -> str:
        anchor = str(word or "").strip()
        if anchor == EMOJI_ANCHOR:
            return EMOJI_ANCHOR
        return anchor.lower()

    def _letter_for_word(self, word: str) -> str:
        for char in self.normalize_anchor(word):
            if char.isalpha():
                return char.upper()
        return "A"

    def _legacy_spare_paths(self) -> list[Path]:
        return [path for path in (self.spare_dir / f"pool_{letter}.json" for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ") if path.exists()]

    def _active_spare_paths(self) -> list[Path]:
        if self.spare_slots_path.exists():
            return [self.spare_slots_path]
        legacy_paths = self._legacy_spare_paths()
        if legacy_paths:
            return legacy_paths
        return [self.spare_slots_path]

    def _spare_entries_cache_signature(self, paths: list[Path]) -> tuple[tuple[str, int | None, int | None], ...]:
        signature: list[tuple[str, int | None, int | None]] = []
        for path in paths:
            if path.exists():
                stat = path.stat()
                signature.append((str(path), stat.st_mtime_ns, stat.st_size))
            else:
                signature.append((str(path), None, None))
        return tuple(signature)

    def _read_spare_entries(self) -> list[dict[str, Any]]:
        paths = self._active_spare_paths()
        signature = self._spare_entries_cache_signature(paths)
        if self._spare_entries_cache is not None and self._spare_entries_cache_key == signature:
            return list(self._spare_entries_cache)

        entries: list[dict[str, Any]] = []
        for path in paths:
            entries.extend(self._read_entries(path))
        self._spare_entries_cache = list(entries)
        self._spare_entries_cache_key = signature
        return entries

    def _write_spare_entries(self, entries: list[dict[str, Any]]) -> None:
        self._write_entries(self.spare_slots_path, entries)
        self._spare_entries_cache = list(entries)
        self._spare_entries_cache_key = self._spare_entries_cache_signature([self.spare_slots_path])

    def _pack_paths(self, pack: str) -> list[tuple[str, Path]]:
        selected = (pack or "all").lower()
        paths: list[tuple[str, Path]] = []
        if selected in {"all", "canonical"}:
            paths.extend(("canonical", self.canonical_dir / f"canonical_{letter}.json") for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        if selected in {"all", "structural"} and self.structural_file.exists():
            paths.append(("structural", self.structural_file))
        if selected in {"all", "spare"}:
            paths.extend(("spare", path) for path in self._active_spare_paths())
        return paths

    def _preview_entry(self, raw: dict[str, Any], pack: str) -> dict[str, Any]:
        hex_value = raw.get("hex") or raw.get("symbol") or ""
        return {
            "word": raw.get("word", "") or "",
            "display": raw.get("display") or raw.get("word", "") or "",
            "status": raw.get("status", ""),
            "frequency": int(raw.get("frequency", 0) or 0),
            "hex": hex_value,
            "binary": raw.get("binary", ""),
            "font_symbol": raw.get("font_symbol", ""),
            "tone_signature": raw.get("tone_signature", ""),
            "mapped_at": raw.get("mapped_at"),
            "pack": raw.get("pack") or pack,
            "symbol": raw.get("symbol") or hex_value,
            "payload": {
                "hex": hex_value,
                "binary": raw.get("binary", ""),
                "font_symbol": raw.get("font_symbol", ""),
                "tone_signature": raw.get("tone_signature", ""),
            },
        }

    def _find_entry(self, word: str) -> tuple[dict[str, Any], str, Path] | None:
        target = self.normalize_anchor(word)
        if not target:
            return None
        structural = self._read_entries(self.structural_file)
        for entry in structural:
            if self.normalize_anchor(entry.get("word", "")) == target:
                return entry, "structural", self.structural_file
        letter = self._letter_for_word(target)
        path = self.canonical_dir / f"canonical_{letter}.json"
        for entry in self._read_entries(path):
            if self.normalize_anchor(entry.get("word", "")) == target:
                return entry, "canonical", path
        return None

    def _all_known_anchors(self) -> set[str]:
        if self._known_anchor_index is not None:
            return self._known_anchor_index

        known: set[str] = set()
        for pack_name, path in self._pack_paths("all"):
            if pack_name == "spare":
                continue
            for entry in self._read_entries(path):
                word = entry.get("word")
                if isinstance(word, str) and word:
                    normalized = self.normalize_anchor(word)
                    if normalized:
                        known.add(normalized)

        self._known_anchor_index = known
        return known

    def _known_anchor_spell_buckets(self) -> dict[tuple[str, tuple[bool, int], int], list[str]]:
        if self._known_anchor_spell_index is not None:
            return self._known_anchor_spell_index

        buckets: dict[tuple[str, tuple[bool, int], int], list[str]] = {}
        for anchor in self._all_known_anchors():
            if not anchor or not any(char.isalpha() for char in anchor):
                continue
            key = (
                self._letter_for_word(anchor).lower(),
                self._anchor_case_signature(anchor),
                len(anchor),
            )
            buckets.setdefault(key, []).append(anchor)

        self._known_anchor_spell_index = buckets
        return buckets

    def _extract_document_anchor_inventory(self, text: str) -> dict[str, Any]:
        paragraphs = split_paragraphs(text)
        ordered_anchors: list[str] = []
        paragraph_rows: list[dict[str, Any]] = []
        observed_counts: Counter[str] = Counter()

        for paragraph_id, paragraph in enumerate(paragraphs):
            anchor_rows = extract_anchor_rows(paragraph)
            anchors = [row["anchor"] for row in anchor_rows]
            composed_streams = [compose_anchor_stream(anchor) for anchor in anchors]
            ordered_anchors.extend(anchors)
            observed_counts.update(anchors)
            paragraph_rows.append({
                "paragraph_id": paragraph_id,
                "anchor_count": len(anchors),
                "anchors": anchors,
                "composed_anchor_streams": composed_streams,
                "composed_anchor_stream": [part for stream in composed_streams for part in stream],
                "text": paragraph,
            })

        return {
            "paragraph_count": len(paragraph_rows),
            "paragraphs": paragraph_rows,
            "ordered_anchors": ordered_anchors,
            "observed_counts": observed_counts,
        }

    def preview_document_intake(
        self,
        *,
        source_name: str,
        content: str,
        file_size: int = 0,
        file_type: str = "",
        source_path: str = "",
    ) -> dict[str, Any]:
        if _is_visual_preview_content(content):
            return {
                "ok": True,
                "source_name": source_name or "document",
                "source_path": source_path or "",
                "file_type": file_type or "",
                "file_size": int(file_size or len(content.encode("utf-8"))),
                "real_lexicon_path": str(self.root),
                "paragraph_count": 0,
                "total_anchor_observations": 0,
                "unique_anchor_count": 0,
                "known_anchor_count": 0,
                "missing_anchor_count": 0,
                "known_anchor_observations": 0,
                "missing_anchor_observations": 0,
                "unique_anchors": [],
                "missing_anchors": [],
                "visual_preview_only": True,
                "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
                "reason": "visual_intake_preview_only",
            }

        inventory = self._extract_document_anchor_inventory(content)
        observed_counts: Counter[str] = inventory["observed_counts"]
        known_anchors = set(self._all_known_anchors())
        missing_counts = Counter({
            anchor: count for anchor, count in observed_counts.items() if anchor not in known_anchors
        })
        known_counts = Counter({
            anchor: count for anchor, count in observed_counts.items() if anchor in known_anchors
        })
        unique_rows = [
            {
                "anchor": anchor,
                "observations": int(count),
                "known": anchor in known_anchors,
            }
            for anchor, count in sorted(observed_counts.items(), key=lambda item: (-item[1], item[0]))
        ]

        return {
            "ok": True,
            "source_name": source_name or "document",
            "source_path": source_path or "",
            "file_type": file_type or "",
            "file_size": int(file_size or len(content.encode("utf-8"))),
            "real_lexicon_path": str(self.root),
            "paragraph_count": int(inventory["paragraph_count"]),
            "total_anchor_observations": int(sum(observed_counts.values())),
            "unique_anchor_count": len(observed_counts),
            "known_anchor_count": len(known_counts),
            "missing_anchor_count": len(missing_counts),
            "known_anchor_observations": int(sum(known_counts.values())),
            "missing_anchor_observations": int(sum(missing_counts.values())),
            "unique_anchors": unique_rows,
            "missing_anchors": self._anchor_rows(missing_counts),
        }

    def edit_intake_content(
        self,
        *,
        source_name: str,
        content: str,
        edits: list[dict[str, Any]],
        file_type: str = "edited-intake-text",
        source_path: str = "",
    ) -> dict[str, Any]:
        updated = str(content or "")
        applied: list[dict[str, Any]] = []
        for edit in edits or []:
            original = self.normalize_anchor(str(edit.get("original_anchor") or ""))
            replacement = str(edit.get("replacement_anchor") or "")
            action = str(edit.get("action") or "replace").strip().lower()
            if not original or action not in {"replace", "delete"}:
                continue
            rows = [
                row for row in extract_anchor_rows(updated)
                if self.normalize_anchor(str(row.get("anchor") or "")) == original
            ]
            if not rows:
                continue
            next_text = updated
            for row in sorted(rows, key=lambda item: int(item.get("start", 0) or 0), reverse=True):
                start = int(row.get("start", 0) or 0)
                end = int(row.get("end", start) or start)
                next_text = next_text[:start] + ("" if action == "delete" else replacement) + next_text[end:]
            updated = next_text
            applied.append({
                "original_anchor": original,
                "replacement_anchor": replacement,
                "action": action,
                "occurrences": len(rows),
            })
        preview = self.preview_document_intake(
            source_name=source_name,
            content=updated,
            file_size=len(updated.encode("utf-8")),
            file_type=file_type,
            source_path=source_path,
        )
        return {
            "ok": True,
            "source_name": source_name,
            "content": updated,
            "edits": applied,
            "edit_count": len(applied),
            "preview": preview,
        }

    def approve_intake_anchors(
        self,
        anchors: list[str],
        frequencies: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        frequency_map = {
            self.normalize_anchor(anchor): int(count or 0)
            for anchor, count in (frequencies or {}).items()
            if self.normalize_anchor(anchor)
        }
        approved: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []
        seen: set[str] = set()
        slots_available = 0
        lexicon_files_written = 0
        spare_pool_writes = 0
        index_reloads = 0

        with self._lock:
            known_anchors = set(self._all_known_anchors())
            requested: list[str] = []

            for raw_anchor in anchors:
                anchor = self.normalize_anchor(raw_anchor)
                if not anchor or anchor in seen:
                    continue
                seen.add(anchor)

                if anchor in known_anchors:
                    skipped.append({"anchor": anchor, "reason": "already_in_lexicon"})
                    continue

                requested.append(anchor)

            pool_entries = self._read_spare_entries()
            available_indexes = [
                index
                for index, item in enumerate(pool_entries)
                if str(item.get("status", "")).upper() == "AVAILABLE"
            ]
            slots_available = len(available_indexes)
            if len(available_indexes) < len(requested):
                failed.extend(
                    {
                        "anchor": anchor,
                        "reason": f"not enough available spare slots ({len(available_indexes)} available for {len(requested)} requested)",
                    }
                    for anchor in requested
                )
                requested = []

            canonical_by_letter: dict[str, list[dict[str, Any]]] = {}
            changed_letters: set[str] = set()
            pool_remove_indexes: list[int] = []
            timestamp = _utc_now()

            for anchor, slot_index in zip(requested, available_indexes):

                slot = pool_entries[slot_index]
                pool_remove_indexes.append(slot_index)
                letter = self._letter_for_word(anchor)
                canonical_path = self.canonical_dir / f"canonical_{letter}.json"
                if letter not in canonical_by_letter:
                    canonical_by_letter[letter] = self._read_entries(canonical_path)

                new_entry = {
                    "binary": slot.get("binary", ""),
                    "hex": slot.get("hex") or slot.get("symbol", ""),
                    "font_symbol": slot.get("font_symbol", ""),
                    "tone_signature": slot.get("tone_signature", ""),
                    "status": "ASSIGNED",
                    "word": anchor,
                    "display": anchor,
                    "symbol": slot.get("hex") or slot.get("symbol", ""),
                    "mapped_at": timestamp,
                    "pack": "canonical",
                    "frequency": int(frequency_map.get(anchor, 0) or 0),
                }
                canonical_by_letter[letter].append(new_entry)
                changed_letters.add(letter)
                known_anchors.add(anchor)
                approved.append({
                    "ok": True,
                    "word": anchor,
                    "hex": new_entry["hex"],
                    "symbol": new_entry["symbol"],
                })

            if approved:
                remove_set = set(pool_remove_indexes)
                pool_entries = [entry for index, entry in enumerate(pool_entries) if index not in remove_set]
                for letter in sorted(changed_letters):
                    canonical_path = self.canonical_dir / f"canonical_{letter}.json"
                    canonical_entries = canonical_by_letter[letter]
                    canonical_entries.sort(key=lambda item: (str(item.get("word", "")).casefold(), str(item.get("word", ""))))
                    self._write_entries(canonical_path, canonical_entries)
                    lexicon_files_written += 1
                self._write_spare_entries(pool_entries)
                spare_pool_writes = 1
                self._invalidate_known_anchor_index()
                self._all_known_anchors()
                index_reloads = 1
            slots_available = len(available_indexes) - len(pool_remove_indexes)

        return {
            "ok": not failed,
            "approved_count": len(approved),
            "skipped_count": len(skipped),
            "failed_count": len(failed),
            "slots_allocated": len(approved),
            "slots_available": slots_available,
            "lexicon_files_written": lexicon_files_written,
            "spare_pool_writes": spare_pool_writes,
            "index_reloads": index_reloads,
            "approved": approved,
            "skipped": skipped,
            "failed": failed,
            "real_lexicon_path": str(self.root),
        }

    def build_intake_mapping(
        self,
        *,
        source_name: str,
        content: str,
        count_target: str = "base",
    ) -> dict[str, Any]:
        if _is_visual_preview_content(content):
            raise ValueError("visual intake preview is source-local evidence only; use a future visual approval route before mapping/counting")
        staged_path = self._intake_upload_path(source_name=source_name, content=content)
        staged_path.write_text(content, encoding="utf-8")
        return self.build_observed_map(staged_path, count_target=count_target)

    def _anchor_case_signature(self, anchor: str) -> tuple[bool, int]:
        return (anchor[:1].isupper(), sum(1 for char in anchor if char.isupper()))

    def _bounded_edit_distance(self, left: str, right: str, max_distance: int = 1) -> int:
        if abs(len(left) - len(right)) > max_distance:
            return max_distance + 1

        previous = list(range(len(right) + 1))
        for index, left_char in enumerate(left, start=1):
            current = [index]
            row_min = current[0]
            for right_index, right_char in enumerate(right, start=1):
                substitution = previous[right_index - 1] + (0 if left_char == right_char else 1)
                insertion = current[right_index - 1] + 1
                deletion = previous[right_index] + 1
                cost = min(substitution, insertion, deletion)
                current.append(cost)
                row_min = min(row_min, cost)
            if row_min > max_distance:
                return max_distance + 1
            previous = current
        return previous[-1]

    def _suggest_existing_anchor(self, anchor: str, known_anchors: set[str]) -> str | None:
        if not anchor:
            return None
        if not any(char.isalpha() for char in anchor):
            return None

        case_signature = self._anchor_case_signature(anchor)
        first_alpha = self._letter_for_word(anchor).lower()
        spell_buckets = self._known_anchor_spell_buckets()
        candidates: list[tuple[int, int, str]] = []

        for length in range(max(1, len(anchor) - 1), len(anchor) + 2):
            for known_anchor in spell_buckets.get((first_alpha, case_signature, length), []):
                if known_anchor == anchor:
                    continue
                distance = self._bounded_edit_distance(anchor, known_anchor, max_distance=1)
                if distance <= 1:
                    candidates.append((distance, abs(len(anchor) - len(known_anchor)), known_anchor))

        if not candidates:
            return None

        candidates.sort(key=lambda item: (item[0], item[1], item[2]))
        best = candidates[0]
        if len(candidates) > 1 and candidates[1][:2] == best[:2]:
            return None
        return best[2]

    def _should_attempt_spell_suggestion(self, anchor: str, missing_unique_count: int) -> bool:
        if missing_unique_count > _SPELL_SUGGESTION_MISSING_LIMIT:
            return False
        if not _SPELL_SUGGESTION_WORD_RE.fullmatch(anchor or ""):
            return False
        if len(anchor) > 1 and anchor.isupper():
            return False
        return True

    def _precompute_spell_suggestions(
        self,
        missing_counts: Counter[str],
        known_anchors: set[str],
    ) -> dict[str, str]:
        suggestions: dict[str, str] = {}
        missing_unique_count = len(missing_counts)
        for anchor in missing_counts:
            if not self._should_attempt_spell_suggestion(anchor, missing_unique_count):
                continue
            suggestion = self._suggest_existing_anchor(anchor, known_anchors)
            if suggestion is not None:
                suggestions[anchor] = suggestion
        return suggestions

    def _resolve_missing_anchors(
        self,
        missing_counts: Counter[str],
        known_anchors: set[str],
        suggestions: dict[str, str] | None = None,
    ) -> tuple[dict[str, str], list[dict[str, Any]], list[dict[str, Any]], Counter[str]]:
        resolved: dict[str, str] = {}
        corrections: list[dict[str, Any]] = []
        additions: list[dict[str, Any]] = []
        unresolved: Counter[str] = Counter()
        suggestion_map = suggestions or {}

        for anchor, observations in missing_counts.items():
            suggestion = suggestion_map.get(anchor)
            if suggestion is not None:
                resolved[anchor] = suggestion
                corrections.append({
                    "anchor": anchor,
                    "resolved_to": suggestion,
                    "observations": int(observations),
                    "action": "spell_corrected_to_existing",
                })
                continue

            try:
                additions.append(self._assign_surface_anchor(anchor, frequency=int(observations)))
                resolved[anchor] = anchor
                known_anchors.add(anchor)
            except Exception:
                unresolved[anchor] = int(observations)

        return resolved, corrections, additions, unresolved

    def _build_misspelled_review_rows(
        self,
        missing_counts: Counter[str],
        known_anchors: set[str],
        suggestions: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        suggestion_map = suggestions or {}
        for anchor, observations in sorted(missing_counts.items(), key=lambda item: (-item[1], item[0])):
            suggestion = suggestion_map.get(anchor)
            rows.append({
                "anchor": anchor,
                "observations": int(observations),
                "suggested_existing": suggestion,
                "review_kind": "possible_misspelling" if suggestion else "missing_anchor",
                "ingest_action": "pending_review",
                "resolved_to": None,
            })
        return rows

    def _write_misspelled_review(
        self,
        source_path: Path,
        inventory: dict[str, Any],
        review_rows: list[dict[str, Any]],
    ) -> Path:
        payload = {
            "saved_at": _utc_now(),
            "source_path": str(source_path),
            "source_name": source_path.name,
            "paragraph_count": int(inventory.get("paragraph_count", 0) or 0),
            "total_anchor_observations": int(sum((inventory.get("observed_counts") or Counter()).values())),
            "unique_anchor_count": len(inventory.get("observed_counts") or {}),
            "review_count": len(review_rows),
            "rows": review_rows,
        }
        review_path = self._misspelled_review_path(source_path)
        self._write_json(review_path, payload)
        return review_path

    def _read_source_text(self, source_path: Path) -> str:
        return prepare_file(source_path).prepared_text

    def prepare_intake_document(
        self,
        raw: bytes,
        *,
        source_name: str,
        file_type: str = "",
        source_path: str = "",
    ) -> dict[str, Any]:
        prepared = prepare_bytes(
            raw,
            source_name=source_name,
            source_path=source_path,
            file_type=file_type,
        )
        payload = prepared.to_dict()
        visual_intake = self._persist_visual_intake_packet(payload)
        if visual_intake:
            payload.setdefault("metadata", {})["visual_intake"] = visual_intake
        return payload

    def _visual_safe_stem(self, source_name: str, visual_record_id: str) -> str:
        original = Path(source_name or "visual").stem
        safe_stem = "".join(
            char if char.isalnum() or char in {"-", "_"} else "_"
            for char in original
        ).strip("_")
        if not safe_stem:
            safe_stem = "visual"
        return f"{safe_stem}-{visual_record_id}"

    def _persist_visual_intake_packet(self, prepared: dict[str, Any]) -> dict[str, Any] | None:
        metadata = prepared.get("metadata")
        if not isinstance(metadata, dict):
            return None
        visual_manifest = metadata.get("visual_manifest")
        visual_region_map = metadata.get("visual_region_map")
        visual_recognition_layer = metadata.get("visual_recognition_layer")
        if not all(isinstance(item, dict) for item in (visual_manifest, visual_region_map, visual_recognition_layer)):
            return None

        source = visual_manifest.get("source") if isinstance(visual_manifest, dict) else {}
        visual_record_id = str((source or {}).get("visual_record_id") or "").strip()
        if not visual_record_id:
            return None
        region_map_id = str(visual_region_map.get("region_map_id") or visual_record_id).strip()
        recognition_layer_id = str(visual_recognition_layer.get("recognition_layer_id") or visual_record_id).strip()
        safe_stem = self._visual_safe_stem(str(prepared.get("source_name") or "visual"), visual_record_id)

        manifest_path = self.visual_intake_manifests_dir / f"{safe_stem}.manifest.json"
        region_map_path = self.visual_intake_region_maps_dir / f"{safe_stem}-{region_map_id}.region_map.json"
        recognition_layer_path = self.visual_intake_recognition_layers_dir / f"{safe_stem}-{recognition_layer_id}.recognition_layer.json"
        packet_path = self.visual_intake_packets_dir / f"{safe_stem}.visual_packet.json"

        writes_allowed = {"maps": False, "counts": False, "lifetime": False, "lexicon": False}
        packet = {
            "schema_version": "anchorworks_visual_intake_packet@1",
            "saved_at": _utc_now(),
            "source_name": str(prepared.get("source_name") or ""),
            "source_path": str(prepared.get("source_path") or ""),
            "file_type": str(prepared.get("file_type") or ""),
            "original_size": int(prepared.get("original_size") or 0),
            "sha256": str(prepared.get("sha256") or ""),
            "converter": str(prepared.get("converter") or ""),
            "visual_record_id": visual_record_id,
            "region_map_id": region_map_id,
            "recognition_layer_id": recognition_layer_id,
            "authority": "source_local_visual_evidence",
            "approval_status": "preview_only",
            "writes_allowed": writes_allowed,
            "visual_manifest": visual_manifest,
            "visual_region_map": visual_region_map,
            "visual_recognition_layer": visual_recognition_layer,
            "trace": {
                "source": "lexicon_intake_prepare",
                "write_intent": "source_local_visual_intake_packet",
                "promotion_required": True,
            },
        }

        self._write_json(manifest_path, visual_manifest)
        self._write_json(region_map_path, visual_region_map)
        self._write_json(recognition_layer_path, visual_recognition_layer)
        self._write_json(packet_path, packet)

        return {
            "schema_version": "anchorworks_visual_intake_packet@1",
            "visual_record_id": visual_record_id,
            "region_map_id": region_map_id,
            "recognition_layer_id": recognition_layer_id,
            "packet_path": str(packet_path),
            "manifest_path": str(manifest_path),
            "region_map_path": str(region_map_path),
            "recognition_layer_path": str(recognition_layer_path),
            "authority": "source_local_visual_evidence",
            "approval_status": "preview_only",
            "writes_allowed": writes_allowed,
        }

    def visual_intake_files(self) -> dict[str, Any]:
        packets: list[dict[str, Any]] = []
        for path in sorted(self.visual_intake_packets_dir.glob("*.visual_packet.json"), key=lambda item: item.name.lower()):
            data = self._read_json(path, {})
            source = data.get("visual_manifest", {}).get("source", {}) if isinstance(data, dict) else {}
            packets.append({
                "name": path.name,
                "path": str(path),
                "size_bytes": path.stat().st_size,
                "visual_record_id": str(data.get("visual_record_id") or ""),
                "source_name": str(data.get("source_name") or ""),
                "file_type": str(data.get("file_type") or ""),
                "width": source.get("width"),
                "height": source.get("height"),
                "aspect_ratio": source.get("aspect_ratio"),
                "approval_status": str(data.get("approval_status") or "preview_only"),
            })
        return {
            "ok": True,
            "root": str(self.visual_intake_dir),
            "packet_count": len(packets),
            "packets": packets,
        }

    def load_visual_intake_packet(self, name: str) -> dict[str, Any]:
        packet_path = (self.visual_intake_packets_dir / Path(name).name).resolve()
        if packet_path.parent != self.visual_intake_packets_dir.resolve():
            raise ValueError("invalid visual packet name")
        if not packet_path.exists() or not packet_path.is_file():
            raise FileNotFoundError(packet_path)
        data = self._read_json(packet_path, {})
        if not isinstance(data, dict):
            raise ValueError("invalid visual packet")
        data["packet_path"] = str(packet_path)
        return data

    def prepare_chat_archive_intake(self, archive_root: Path) -> dict[str, Any]:
        prepared = prepare_anchorworks_chat_archive(archive_root)
        return prepared.to_dict()

    def _observed_map_path(self, source_path: Path) -> Path:
        digest = hashlib.sha1(str(source_path).encode("utf-8")).hexdigest()[:12]
        safe_name = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in source_path.stem).strip("_")
        if not safe_name:
            safe_name = "observed"
        return self.observed_maps_dir / f"{safe_name}-{digest}.observed.json"

    def _misspelled_review_path(self, source_path: Path) -> Path:
        digest = hashlib.sha1(str(source_path).encode("utf-8")).hexdigest()[:12]
        safe_name = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in source_path.stem).strip("_")
        if not safe_name:
            safe_name = "review"
        return self.misspelled_reviews_dir / f"{safe_name}-{digest}.misspellings.json"

    def _intake_upload_path(self, *, source_name: str, content: str) -> Path:
        original = Path(source_name or "document.txt").name
        suffix = ".prepared.txt"
        safe_stem = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in Path(original).stem).strip("_")
        if not safe_stem:
            safe_stem = "document"
        digest = hashlib.sha1((original + "\n" + content).encode("utf-8")).hexdigest()[:12]
        return self.intake_uploads_dir / f"{safe_stem}-{digest}{suffix}"

    def _resolve_observed_map_name(self, name: str) -> Path:
        filename = Path(name).name
        target = (self.observed_maps_dir / filename).resolve()
        if target.parent != self.observed_maps_dir.resolve():
            raise FileNotFoundError(name)
        return target

    def _flat_runtime_stem(self, source_name: str, source_id: str) -> str:
        safe_name = "".join(
            char if char.isalnum() or char in {"-", "_"} else "_"
            for char in Path(source_name or "document").stem
        ).strip("_")
        if not safe_name:
            safe_name = "document"
        return f"{safe_name}-{source_id[:12]}"

    def _resolve_misspelled_review_name(self, name: str) -> Path:
        filename = Path(name).name
        target = (self.misspelled_reviews_dir / filename).resolve()
        if target.parent != self.misspelled_reviews_dir.resolve():
            raise FileNotFoundError(name)
        return target

    def _anchor_rows(self, counts: Counter[str]) -> list[dict[str, Any]]:
        return [
            {"anchor": anchor, "observations": count}
            for anchor, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        ]

    def _temp_symbol_for_anchor(self, source_id: str, anchor: str, salt: int = 0) -> str:
        seed = f"{TEMP_SYMBOL_VERSION}::{source_id}::{anchor}::{salt}"
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest().upper()
        return f"{TEMP_SYMBOL_PREFIX}{digest[:TEMP_SYMBOL_HEX_LENGTH]}"

    def _temp_lexicon_path(self, source_path: Path) -> Path:
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", source_path.stem).strip("._") or "source"
        digest = hashlib.sha256(str(source_path).encode("utf-8")).hexdigest()[:12]
        return self.temp_lexicons_dir / f"{safe_name}-{digest}.temp_lexicon.json"

    def _source_local_preview_counts_path(self, source_path: Path) -> Path:
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", source_path.stem).strip("._") or "source"
        digest = hashlib.sha256(str(source_path).encode("utf-8")).hexdigest()[:12]
        return self.source_local_preview_counts_dir / f"{safe_name}-{digest}.preview_counts.json"

    def _build_temp_symbol_entries(self, source_path: Path, missing_counts: Counter[str]) -> tuple[dict[str, str], list[dict[str, Any]]]:
        source_id = hashlib.sha256(str(source_path).encode("utf-8")).hexdigest()
        used: set[str] = set()
        symbol_map: dict[str, str] = {}
        entries: list[dict[str, Any]] = []
        for anchor, observations in sorted(missing_counts.items(), key=lambda item: item[0]):
            salt = 0
            symbol = self._temp_symbol_for_anchor(source_id, anchor, salt)
            while symbol in used:
                salt += 1
                symbol = self._temp_symbol_for_anchor(source_id, anchor, salt)
            used.add(symbol)
            symbol_map[anchor] = symbol
            entries.append({
                "word": anchor,
                "display": anchor,
                "symbol": symbol,
                "hex": symbol,
                "status": "TEMP_UNKNOWN",
                "pack": "temp",
                "authority": "source_local_coordinate",
                "scope": "source_local",
                "source_id": source_id,
                "source_name": source_path.name,
                "observations": int(observations),
                "temp_symbol_version": TEMP_SYMBOL_VERSION,
                "lifetime_eligible": False,
                "speak_eligible": False,
                "promotion_required": True,
                "created_at": _utc_now(),
            })
        return symbol_map, entries

    def _relation_count_rows(self, counts: Counter[tuple[str, str, str]]) -> list[dict[str, Any]]:
        return [
            {
                "anchor": anchor,
                "offset": offset,
                "neighbor": neighbor,
                "observations": observations,
            }
            for (anchor, offset, neighbor), observations in sorted(
                counts.items(),
                key=lambda item: (-item[1], item[0][0], item[0][1], item[0][2]),
            )
        ]

    def _load_relation_counts_file(self, path: Path) -> tuple[Counter[tuple[str, str, str]], Counter[str], dict[str, Any]]:
        payload = self._read_json(path, {})
        counter: Counter[tuple[str, str, str]] = Counter()
        observed_counts: Counter[str] = Counter()
        metadata = {
            "first_saved_at": None,
            "updated_at": None,
            "ingest_events": 0,
            "window_radius": DEFAULT_WINDOW_RADIUS,
        }

        if isinstance(payload, dict):
            metadata["first_saved_at"] = payload.get("first_saved_at")
            metadata["updated_at"] = payload.get("updated_at")
            metadata["ingest_events"] = int(payload.get("ingest_events", 0) or 0)
            metadata["window_radius"] = int(payload.get("window_radius", DEFAULT_WINDOW_RADIUS) or DEFAULT_WINDOW_RADIUS)

            rows = payload.get("co_occurrence_counts") or []
            if isinstance(rows, list):
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    anchor = row.get("anchor")
                    offset = row.get("offset")
                    neighbor = row.get("neighbor")
                    observations = int(row.get("observations", 0) or 0)
                    if not isinstance(anchor, str) or not isinstance(offset, str) or not isinstance(neighbor, str):
                        continue
                    if observations <= 0:
                        continue
                    counter[(anchor, offset, neighbor)] += observations

            observed_rows = payload.get("anchor_observation_counts") or []
            if isinstance(observed_rows, list):
                for row in observed_rows:
                    if not isinstance(row, dict):
                        continue
                    anchor = row.get("anchor")
                    observations = int(row.get("observations", 0) or 0)
                    if not isinstance(anchor, str) or observations <= 0:
                        continue
                    observed_counts[anchor] += observations

        return counter, observed_counts, metadata

    def _load_lifetime_relation_counts(self) -> tuple[Counter[tuple[str, str, str]], Counter[str], dict[str, Any]]:
        return self._load_relation_counts_file(self.lifetime_counts_path)

    def _load_combined_relation_counts(self) -> tuple[Counter[tuple[str, str, str]], Counter[str]]:
        base_counter, base_observed, _ = self._load_relation_counts_file(self.lifetime_counts_path)
        user_counter, user_observed, _ = self._load_relation_counts_file(self.user_counts_path)
        combined_counter = Counter(base_counter)
        combined_counter.update(user_counter)
        combined_observed = Counter(base_observed)
        combined_observed.update(user_observed)
        return combined_counter, combined_observed

    def _update_relation_counts_file(
        self,
        path: Path,
        relation_rows: list[dict[str, Any]],
        observed_counts: Counter[str] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            counter, observed_counter, metadata = self._load_relation_counts_file(path)

            for row in relation_rows:
                if not isinstance(row, dict):
                    continue
                anchor = row.get("anchor")
                offset = row.get("offset")
                neighbor = row.get("neighbor")
                observations = int(row.get("observations", 0) or 0)
                if not isinstance(anchor, str) or not isinstance(offset, str) or not isinstance(neighbor, str):
                    continue
                if observations <= 0:
                    continue
                counter[(anchor, offset, neighbor)] += observations

            if observed_counts:
                for anchor, observations in observed_counts.items():
                    if not isinstance(anchor, str):
                        continue
                    observed_counter[anchor] += int(observations or 0)

            timestamp = _utc_now()
            first_saved_at = metadata["first_saved_at"] or timestamp
            relation_count_rows = self._relation_count_rows(counter)
            items, anchor_index = build_context_views(
                relation_count_rows,
                observed_counts=observed_counter,
                window_radius=DEFAULT_WINDOW_RADIUS,
            )
            payload = {
                "first_saved_at": first_saved_at,
                "updated_at": timestamp,
                "ingest_events": int(metadata["ingest_events"]) + 1,
                "window_radius": DEFAULT_WINDOW_RADIUS,
                "unique_relations": len(counter),
                "total_relation_observations": int(sum(counter.values())),
                "anchor_observation_counts": self._anchor_rows(observed_counter),
                "co_occurrence_counts": relation_count_rows,
                "items": items,
                "anchor_index": anchor_index,
            }
            self._write_json(path, payload)
            return payload

    def _update_lifetime_relation_counts(
        self,
        relation_rows: list[dict[str, Any]],
        observed_counts: Counter[str] | None = None,
    ) -> dict[str, Any]:
        return self._update_relation_counts_file(
            self.lifetime_counts_path,
            relation_rows,
            observed_counts=observed_counts,
        )

    def _update_user_chat_relation_counts(
        self,
        relation_rows: list[dict[str, Any]],
        observed_counts: Counter[str] | None = None,
    ) -> dict[str, Any]:
        user_payload = self._update_relation_counts_file(
            self.user_counts_path,
            relation_rows,
            observed_counts=observed_counts,
        )
        chat_payload = self._update_relation_counts_file(
            self.chat_counts_path,
            relation_rows,
            observed_counts=observed_counts,
        )
        return {
            "user_counts_path": str(self.user_counts_path),
            "chat_counts_path": str(self.chat_counts_path),
            "user_ingest_events": int(user_payload.get("ingest_events", 0) or 0),
            "chat_ingest_events": int(chat_payload.get("ingest_events", 0) or 0),
            "user_total_relation_observations": int(user_payload.get("total_relation_observations", 0) or 0),
            "chat_total_relation_observations": int(chat_payload.get("total_relation_observations", 0) or 0),
        }

    def counts_status(self) -> dict[str, Any]:
        base_counter, base_observed, base_metadata = self._load_relation_counts_file(self.lifetime_counts_path)
        user_counter, user_observed, user_metadata = self._load_relation_counts_file(self.user_counts_path)
        combined_counter = Counter(base_counter)
        combined_counter.update(user_counter)
        combined_observed = Counter(base_observed)
        combined_observed.update(user_observed)
        return {
            "counts_path": str(self.lifetime_counts_path),
            "user_counts_path": str(self.user_counts_path),
            "base_ingest_events": int(base_metadata.get("ingest_events", 0) or 0),
            "user_ingest_events": int(user_metadata.get("ingest_events", 0) or 0),
            "ingest_events": int(base_metadata.get("ingest_events", 0) or 0) + int(user_metadata.get("ingest_events", 0) or 0),
            "base_unique_relations": len(base_counter),
            "user_unique_relations": len(user_counter),
            "unique_relations": len(combined_counter),
            "base_total_relation_observations": int(sum(base_counter.values())),
            "user_total_relation_observations": int(sum(user_counter.values())),
            "total_relation_observations": int(sum(combined_counter.values())),
            "anchor_count": len(combined_observed),
            "relation_rows": len(combined_counter),
        }

    def observed_map_files(self) -> dict[str, Any]:
        files: list[dict[str, Any]] = []
        for path in sorted(self.observed_maps_dir.glob("*.observed.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            stat = path.stat()
            payload = self._read_json(path, {})
            files.append({
                "name": path.name,
                "path": str(path),
                "source_name": payload.get("source_name") or "",
                "source_path": payload.get("source_path") or "",
                "paragraph_count": int(payload.get("paragraph_count", 0) or 0),
                "unique_anchor_count": int(payload.get("unique_anchor_count", 0) or 0),
                "total_anchor_observations": int(payload.get("total_anchor_observations", 0) or 0),
                "modified": stat.st_mtime,
                "size_bytes": stat.st_size,
            })
        return {"root": str(self.observed_maps_dir), "files": files}

    def misspelled_review_files(self) -> dict[str, Any]:
        files: list[dict[str, Any]] = []
        for path in sorted(self.misspelled_reviews_dir.glob("*.misspellings.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            stat = path.stat()
            payload = self._read_json(path, {})
            files.append({
                "name": path.name,
                "path": str(path),
                "source_name": payload.get("source_name") or "",
                "source_path": payload.get("source_path") or "",
                "paragraph_count": int(payload.get("paragraph_count", 0) or 0),
                "unique_anchor_count": int(payload.get("unique_anchor_count", 0) or 0),
                "review_count": int(payload.get("review_count", 0) or 0),
                "modified": stat.st_mtime,
                "size_bytes": stat.st_size,
            })
        return {"root": str(self.misspelled_reviews_dir), "files": files}

    def retrieve_from_counts(self, anchor: str, limit: int = 25) -> dict[str, Any]:
        surface = self.normalize_anchor(anchor)
        counter, _ = self._load_combined_relation_counts()
        total_by_neighbor: Counter[str] = Counter()
        by_offset: dict[str, Counter[str]] = {}
        for (anchor, offset, neighbor), observations in counter.items():
            if anchor != surface or observations <= 0:
                continue
            total_by_neighbor[neighbor] += observations
            by_offset.setdefault(offset, Counter())[neighbor] += observations

        neighbor_rows = [
            {"anchor": neighbor, "observations": count}
            for neighbor, count in sorted(total_by_neighbor.items(), key=lambda item: (-item[1], item[0]))[:limit]
        ]
        offset_rows = {
            offset: [
                {"anchor": neighbor, "observations": count}
                for neighbor, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit]
            ]
            for offset, counter in sorted(by_offset.items(), key=lambda item: (int(item[0]), item[0]))
        }
        return {
            "anchor": surface,
            "maps_scanned": len(list(self.observed_maps_dir.glob("*.observed.json"))),
            "maps_with_anchor": 1 if total_by_neighbor else 0,
            "neighbor_count": len(total_by_neighbor),
            "total_neighbor_observations": int(sum(total_by_neighbor.values())),
            "neighbors": neighbor_rows,
            "offsets": offset_rows,
        }

    def search_observed_map_evidence(
        self,
        anchors: list[str],
        *,
        query_anchors: list[str] | None = None,
        map_limit: int = 12,
        max_map_bytes: int = 128 * 1024 * 1024,
    ) -> dict[str, Any]:
        query_set = {self.normalize_anchor(anchor) for anchor in anchors if self.normalize_anchor(anchor)}
        query_anchor_set = {self.normalize_anchor(anchor) for anchor in (query_anchors or []) if self.normalize_anchor(anchor)}
        if not query_set and query_anchor_set:
            query_set = set(query_anchor_set)
        source_passages: list[dict[str, Any]] = []
        map_hits: list[dict[str, Any]] = []
        maps_scanned = 0
        maps_skipped: list[dict[str, Any]] = []
        max_maps = max(1, min(int(map_limit or 12), 100))

        for path in sorted(self.observed_maps_dir.glob("*.observed.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            if maps_scanned >= max_maps:
                break
            stat = path.stat()
            if stat.st_size > max_map_bytes:
                maps_skipped.append({"saved_map_name": path.name, "reason": "map_file_too_large_for_interactive_scan", "size_bytes": int(stat.st_size)})
                continue
            payload = self._read_json(path, {})
            if not isinstance(payload, dict):
                continue
            maps_scanned += 1
            locators = payload.get("paragraph_line_locators")
            if not isinstance(locators, dict):
                locators = self._paragraph_line_locators(payload)
            passage_rows: list[dict[str, Any]] = []
            for paragraph in payload.get("paragraphs") or []:
                if not isinstance(paragraph, dict):
                    continue
                paragraph_anchors = {self.normalize_anchor(anchor) for anchor in paragraph.get("anchors") or []}
                paragraph_anchors.update(self.normalize_anchor(anchor) for anchor in paragraph.get("resolved_anchors") or [])
                text = str(paragraph.get("text") or "")
                text_anchors = {self.normalize_anchor(row["anchor"]) for row in extract_anchor_rows(text)}
                hits = sorted((query_set | query_anchor_set) & (paragraph_anchors | text_anchors))
                if not hits:
                    continue
                paragraph_id = int(paragraph.get("paragraph_id", len(passage_rows)) or 0)
                locator = locators.get(str(paragraph_id)) or locators.get(paragraph_id) or {}
                score = float(len(hits) * 100 + len(hits) / max(1, int(paragraph.get("anchor_count", 1) or 1)))
                passage_rows.append({
                    "source_name": payload.get("source_name") or "",
                    "source_path": payload.get("source_path") or "",
                    "saved_map_name": path.name,
                    "paragraph_id": paragraph_id,
                    "block_id": int(locator.get("block_id", paragraph_id) or 0),
                    "line_start": int(locator.get("line_start", 0) or 0),
                    "line_end": int(locator.get("line_end", 0) or 0),
                    "score": score,
                    "anchor_hits": hits,
                    "anchor_count": int(paragraph.get("anchor_count", 0) or 0),
                    "text": text.strip(),
                })
            if passage_rows:
                passage_rows.sort(key=lambda row: (-float(row.get("score", 0.0) or 0.0), int(row.get("paragraph_id", 0) or 0)))
                source_passages.extend(passage_rows[:8])
                map_hits.append({
                    "saved_map_name": path.name,
                    "source_name": payload.get("source_name") or "",
                    "source_path": payload.get("source_path") or "",
                    "passage_count": len(passage_rows),
                    "top_score": float(passage_rows[0].get("score", 0.0) or 0.0),
                })

        source_passages.sort(key=lambda row: (-float(row.get("score", 0.0) or 0.0), str(row.get("source_name") or ""), int(row.get("paragraph_id", 0) or 0)))
        return {
            "query_anchors": sorted(query_anchor_set or query_set),
            "maps_scanned": maps_scanned,
            "maps_with_query_symbols": len(map_hits),
            "map_hits": map_hits,
            "maps_skipped": maps_skipped,
            "source_passages": source_passages[:12],
        }

    def _paragraph_line_locators(self, payload: dict[str, Any]) -> dict[int, dict[str, int]]:
        source_path = Path(str(payload.get("source_path") or ""))
        if not source_path.exists() or not source_path.is_file():
            return {}
        try:
            source_text = source_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return {}
        paragraphs = [row for row in payload.get("paragraphs") or [] if isinstance(row, dict)]
        if not paragraphs:
            return {}
        normalized_source, source_index = _normalize_with_source_index(source_text)
        if not normalized_source or not source_index:
            return {}
        locators: dict[int, dict[str, int]] = {}
        cursor = 0
        for paragraph in paragraphs:
            paragraph_id = int(paragraph.get("paragraph_id", len(locators)) or 0)
            normalized_paragraph, _ = _normalize_with_source_index(str(paragraph.get("text") or ""))
            if not normalized_paragraph:
                continue
            found = normalized_source.find(normalized_paragraph, cursor)
            if found < 0:
                found = normalized_source.find(normalized_paragraph)
            if found < 0:
                continue
            raw_start = source_index[min(found, len(source_index) - 1)]
            raw_end_index = min(found + len(normalized_paragraph) - 1, len(source_index) - 1)
            raw_end = source_index[raw_end_index]
            locators[paragraph_id] = {
                "block_id": paragraph_id,
                "line_start": source_text.count("\n", 0, raw_start) + 1,
                "line_end": source_text.count("\n", 0, raw_end) + 1,
            }
            cursor = found + len(normalized_paragraph)
        return locators

    def load_observed_map(self, name: str) -> dict[str, Any]:
        path = self._resolve_observed_map_name(name)
        if not path.exists():
            raise FileNotFoundError(name)
        payload = self._read_json(path, {})
        if not isinstance(payload, dict):
            raise ValueError(f"invalid observed map: {path.name}")

        return {
            "ok": True,
            "source_path": payload.get("source_path") or "",
            "source_name": payload.get("source_name") or "",
            "saved_map_path": str(path),
            "saved_map_name": path.name,
            "paragraph_count": int(payload.get("paragraph_count", 0) or 0),
            "window_radius": int(payload.get("window_radius", 0) or 0),
            "total_anchor_observations": int(payload.get("total_anchor_observations", 0) or 0),
            "unique_anchor_count": int(payload.get("unique_anchor_count", 0) or 0),
            "known_anchor_count": int(payload.get("known_anchor_count", 0) or 0),
            "missing_anchor_count": int(payload.get("missing_anchor_count", 0) or 0),
            "known_anchor_observations": int(payload.get("known_anchor_observations", 0) or 0),
            "missing_anchor_observations": int(payload.get("missing_anchor_observations", 0) or 0),
            "registered_missing_anchors": len(payload.get("missing_anchors") or []),
            "known_anchors_preview": (payload.get("known_anchors") or [])[:25],
            "missing_anchors_preview": (payload.get("missing_anchors") or [])[:25],
            "observed_anchors_preview": (payload.get("observed_anchors") or [])[:25],
            "occurrence_preview": (payload.get("occurrences") or [])[:12],
            "co_occurrence_preview": (payload.get("co_occurrence_counts") or [])[:12],
            "anchor_index_preview": (payload.get("anchor_index") or [])[:25],
            "context_items_preview": list((payload.get("items") or {}).values())[:12],
            "temp_symbol_count": int(payload.get("temp_symbol_count", 0) or 0),
            "temp_lexicon_path": payload.get("temp_lexicon_path") or "",
            "source_local_preview_counts_path": payload.get("source_local_preview_counts_path") or "",
        }

    def flat_document_files(self) -> dict[str, Any]:
        raw_files = []
        for path in sorted(self.flat_documents_raw_dir.glob("*"), key=lambda item: item.name.lower()):
            if path.is_file():
                raw_files.append({"name": path.name, "path": str(path), "size_bytes": path.stat().st_size})
        symbolic_files = []
        for path in sorted(self.flat_documents_symbolic_dir.glob("*.symbolic.json"), key=lambda item: item.name.lower()):
            payload = self._read_json(path, {})
            symbolic_files.append({
                "name": path.name,
                "path": str(path),
                "source_name": payload.get("source_name") or "",
                "total_anchor_observations": int(payload.get("total_anchor_observations", 0) or 0),
                "unique_anchor_count": int(payload.get("unique_anchor_count", 0) or 0),
            })
        return {
            "ok": True,
            "raw_root": str(self.flat_documents_raw_dir),
            "symbolic_root": str(self.flat_documents_symbolic_dir),
            "block_index_root": str(self.flat_documents_block_index_dir),
            "visual_links_root": str(self.flat_documents_visual_links_dir),
            "occurrence_index_root": str(self.flat_documents_occurrence_index_dir),
            "raw_files": raw_files,
            "symbolic_files": symbolic_files,
        }

    def load_flat_document(self, name: str) -> dict[str, Any]:
        filename = Path(name).name
        raw_path = (self.flat_documents_raw_dir / filename).resolve()
        symbolic_path = (self.flat_documents_symbolic_dir / filename).resolve()
        if raw_path.parent == self.flat_documents_raw_dir.resolve() and raw_path.exists() and raw_path.is_file():
            return {"ok": True, "name": raw_path.name, "path": str(raw_path), "content": raw_path.read_text(encoding="utf-8", errors="replace")}
        if symbolic_path.parent == self.flat_documents_symbolic_dir.resolve() and symbolic_path.exists() and symbolic_path.is_file():
            return {"ok": True, **self._read_json(symbolic_path, {})}
        raise FileNotFoundError(name)

    def anchorize_flat_document(self, source_path: Path | None = None, *, name: str = "") -> dict[str, Any]:
        raw_root = self.flat_documents_raw_dir.resolve()
        source = Path(source_path).expanduser().resolve() if source_path else (raw_root / Path(name).name).resolve()
        if source.parent != raw_root:
            raise ValueError("flat document source must live under the raw flat document root")
        if not source.exists() or not source.is_file():
            raise FileNotFoundError(source.name)
        prepared = prepare_file(source)
        inventory = self._extract_document_anchor_inventory(prepared.prepared_text)
        observed_counts: Counter[str] = inventory["observed_counts"]
        known_anchors = set(self._all_known_anchors())
        missing = sorted(anchor for anchor in observed_counts if anchor not in known_anchors)
        if missing:
            raise ValueError("flat document has unresolved anchors: " + ", ".join(missing[:12]))
        mapping = build_anchor_map(prepared.prepared_text, window_radius=DEFAULT_WINDOW_RADIUS)
        target = self.flat_documents_symbolic_dir / f"{source.stem}.symbolic.json"
        payload = {
            "schema_version": "flat_symbolic_document@1",
            "saved_at": _utc_now(),
            "source_path": str(source),
            "source_name": source.name,
            "saved_document_name": target.name,
            "paragraph_count": mapping["paragraph_count"],
            "window_radius": mapping["window_radius"],
            "total_anchor_observations": int(sum(mapping["observed_counts"].values())),
            "unique_anchor_count": len(mapping["observed_counts"]),
            "paragraphs": mapping["paragraphs"],
            "occurrences": mapping["occurrences"],
            "anchor_index": mapping["anchor_index"],
            "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
        }
        self._write_json(target, payload)
        return {"ok": True, "saved_document_name": target.name, "saved_document_path": str(target), **payload}

    def build_flat_runtime_from_observed_map(self, observed_map_name: str) -> dict[str, Any]:
        path = self._resolve_observed_map_name(observed_map_name)
        if not path.exists():
            raise FileNotFoundError(observed_map_name)
        payload = self._read_json(path, {})
        if not isinstance(payload, dict):
            raise ValueError(f"invalid observed map: {path.name}")

        source_name = str(payload.get("source_name") or Path(str(payload.get("source_path") or "document")).name or "document")
        source_path = str(payload.get("source_path") or "")
        source_hash = str((payload.get("document_prep") or {}).get("sha256") or hashlib.sha256(source_path.encode("utf-8")).hexdigest())
        source_id = hashlib.sha1((source_path + "\n" + source_hash + "\n" + path.name).encode("utf-8")).hexdigest()
        stem = self._flat_runtime_stem(source_name, source_id)

        symbolic_path = self.flat_documents_symbolic_dir / f"{stem}.symbolic.json"
        block_index_path = self.flat_documents_block_index_dir / f"{stem}.blocks.jsonl"
        occurrence_index_path = self.flat_documents_occurrence_index_dir / f"{stem}.occurrences.jsonl"
        visual_links_path = self.flat_documents_visual_links_dir / f"{stem}.visual_links.jsonl"

        paragraphs = [row for row in payload.get("paragraphs") or [] if isinstance(row, dict)]
        occurrences = [row for row in payload.get("occurrences") or [] if isinstance(row, dict)]
        occurrence_rows: list[dict[str, Any]] = []
        for occurrence in occurrences:
            paragraph_id = int(occurrence.get("paragraph_id", 0) or 0)
            occurrence_rows.append({
                "schema_version": "flat_symbolic_occurrence@1",
                "source_id": source_id,
                "source_name": source_name,
                "source_path": source_path,
                "source_hash": source_hash,
                "block_id": f"block_{paragraph_id}",
                "block_ordinal": paragraph_id,
                "line_start": int(occurrence.get("line_start", 0) or 0),
                "line_end": int(occurrence.get("line_end", 0) or 0),
                "anchor": str(occurrence.get("anchor") or ""),
                "observed_anchor": str(occurrence.get("observed_anchor") or occurrence.get("anchor") or ""),
                "surface": str(occurrence.get("surface") or ""),
                "position": int(occurrence.get("position", 0) or 0),
                "start": int(occurrence.get("start", 0) or 0),
                "end": int(occurrence.get("end", 0) or 0),
                "count_eligible": bool(occurrence.get("count_eligible", True)),
            })

        occurrences_by_paragraph: dict[int, list[dict[str, Any]]] = {}
        for occurrence in occurrence_rows:
            occurrences_by_paragraph.setdefault(int(occurrence["block_ordinal"]), []).append(occurrence)

        block_rows: list[dict[str, Any]] = []
        visual_link_rows: list[dict[str, Any]] = []
        for paragraph in paragraphs:
            paragraph_id = int(paragraph.get("paragraph_id", len(block_rows)) or 0)
            visual_refs = [
                ref for ref in paragraph.get("visual_refs") or []
                if isinstance(ref, dict) and str(ref.get("visual_record_id") or "").strip()
            ]
            block_row = {
                "schema_version": "flat_symbolic_block@1",
                "source_id": source_id,
                "source_name": source_name,
                "source_path": source_path,
                "source_hash": source_hash,
                "observed_map_name": path.name,
                "block_id": f"block_{paragraph_id}",
                "block_ordinal": paragraph_id,
                "paragraph_id": paragraph_id,
                "line_count": max(0, int(paragraph.get("line_end", 0) or 0) - int(paragraph.get("line_start", 0) or 0) + 1)
                if int(paragraph.get("line_start", 0) or 0) > 0 else 0,
                "line_start": int(paragraph.get("line_start", 0) or 0),
                "line_end": int(paragraph.get("line_end", 0) or 0),
                "raw_text": str(paragraph.get("text") or ""),
                "anchor_stream": list(paragraph.get("resolved_anchors") or paragraph.get("anchors") or []),
                "symbol_stream": list(paragraph.get("composed_anchor_stream") or []),
                "visual_refs": visual_refs,
                "occurrence_count": len(occurrences_by_paragraph.get(paragraph_id, [])),
                "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
            }
            block_rows.append(block_row)
            for ref in visual_refs:
                visual_link_rows.append({
                    "schema_version": "flat_symbolic_visual_link@1",
                    "source_id": source_id,
                    "source_name": source_name,
                    "source_path": source_path,
                    "source_hash": source_hash,
                    "block_id": block_row["block_id"],
                    "block_ordinal": paragraph_id,
                    "line_start": block_row["line_start"],
                    "line_end": block_row["line_end"],
                    "visual_record_id": str(ref.get("visual_record_id") or ""),
                    "kind": str(ref.get("kind") or ""),
                    "source_path_ref": str(ref.get("source_path") or ""),
                    "caption_block_id": str(ref.get("caption_block_id") or ""),
                    "manifest_id": str(ref.get("manifest_id") or ""),
                    "geometry_status": str(ref.get("geometry_status") or "held"),
                    "recognition_status": str(ref.get("recognition_status") or "not_run"),
                    "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
                })

        symbolic = {
            "schema_version": "flat_symbolic_document@2",
            "saved_at": _utc_now(),
            "source_id": source_id,
            "source_path": source_path,
            "source_name": source_name,
            "source_hash": source_hash,
            "saved_document_name": symbolic_path.name,
            "observed_map_name": path.name,
            "observed_map_path": str(path),
            "block_count": len(block_rows),
            "occurrence_count": len(occurrence_rows),
            "visual_link_count": len(visual_link_rows),
            "paragraph_count": int(payload.get("paragraph_count", len(block_rows)) or len(block_rows)),
            "window_radius": int(payload.get("window_radius", DEFAULT_WINDOW_RADIUS) or DEFAULT_WINDOW_RADIUS),
            "total_anchor_observations": int(payload.get("total_anchor_observations", len(occurrence_rows)) or 0),
            "unique_anchor_count": int(payload.get("unique_anchor_count", 0) or 0),
            "blocks": block_rows,
            "occurrences": occurrence_rows,
            "visual_links": visual_link_rows,
            "block_index_path": str(block_index_path),
            "occurrence_index_path": str(occurrence_index_path),
            "visual_links_path": str(visual_links_path),
            "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
        }

        self._write_json(symbolic_path, symbolic)
        write_jsonl(block_index_path, block_rows)
        write_jsonl(occurrence_index_path, occurrence_rows)
        write_jsonl(visual_links_path, visual_link_rows)

        return {
            "ok": True,
            "source_id": source_id,
            "source_name": source_name,
            "source_path": source_path,
            "source_hash": source_hash,
            "observed_map_name": path.name,
            "observed_map_path": str(path),
            "symbolic_document_name": symbolic_path.name,
            "symbolic_document_path": str(symbolic_path),
            "block_index_path": str(block_index_path),
            "occurrence_index_path": str(occurrence_index_path),
            "visual_links_path": str(visual_links_path),
            "block_count": len(block_rows),
            "occurrence_count": len(occurrence_rows),
            "visual_link_count": len(visual_link_rows),
            "writes_allowed": symbolic["writes_allowed"],
        }

    def search_flat_document_evidence(
        self,
        anchors: list[str],
        *,
        query_anchors: list[str] | None = None,
        max_files: int = 32,
        max_index_bytes: int = 64 * 1024 * 1024,
    ) -> dict[str, Any]:
        query_set = {self.normalize_anchor(anchor) for anchor in anchors or [] if self.normalize_anchor(anchor)}
        query_anchor_set = {self.normalize_anchor(anchor) for anchor in query_anchors or [] if self.normalize_anchor(anchor)}
        if not query_set and not query_anchor_set:
            return {
                "runtime_source": "flat_symbolic_documents",
                "query_anchors": [],
                "files_scanned": 0,
                "files_with_query_symbols": 0,
                "files_skipped": [],
                "source_passages": [],
            }

        files_scanned = 0
        files_skipped: list[dict[str, Any]] = []
        file_hits: list[dict[str, Any]] = []
        source_passages: list[dict[str, Any]] = []
        for path in sorted(self.flat_documents_block_index_dir.glob("*.blocks.jsonl"), key=lambda item: item.stat().st_mtime, reverse=True):
            if files_scanned >= max_files:
                break
            stat = path.stat()
            if stat.st_size > max_index_bytes:
                files_skipped.append({"block_index_name": path.name, "reason": "block_index_too_large_for_interactive_scan", "size_bytes": int(stat.st_size)})
                continue
            files_scanned += 1
            block_hits: list[dict[str, Any]] = []
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    block = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(block, dict):
                    continue
                block_anchors = {self.normalize_anchor(anchor) for anchor in block.get("anchor_stream") or []}
                text = str(block.get("raw_text") or "")
                text_anchors = {self.normalize_anchor(row["anchor"]) for row in extract_anchor_rows(text)}
                hits = sorted((query_set | query_anchor_set) & (block_anchors | text_anchors))
                if not hits:
                    continue
                anchor_count = max(1, len(block_anchors | text_anchors))
                score = float(len(hits) * 100 + len(hits) / anchor_count)
                block_id_text = str(block.get("block_id") or "block_0")
                try:
                    block_number = int(block_id_text.rsplit("_", 1)[-1])
                except ValueError:
                    block_number = int(block.get("block_ordinal", 0) or 0)
                block_hits.append({
                    "source": "flat_symbolic_document",
                    "source_name": block.get("source_name") or "",
                    "source_path": block.get("source_path") or "",
                    "source_id": block.get("source_id") or "",
                    "source_hash": block.get("source_hash") or "",
                    "saved_document_name": path.name.replace(".blocks.jsonl", ".symbolic.json"),
                    "block_id": block_number,
                    "block_label": block_id_text,
                    "paragraph_id": int(block.get("paragraph_id", block_number) or 0),
                    "line_start": int(block.get("line_start", 0) or 0),
                    "line_end": int(block.get("line_end", 0) or 0),
                    "score": score,
                    "anchor_hits": hits,
                    "anchor_count": len(block_anchors),
                    "text": text.strip(),
                    "visual_refs": block.get("visual_refs") or [],
                })
            if block_hits:
                block_hits.sort(key=lambda row: (-float(row.get("score", 0.0) or 0.0), int(row.get("block_id", 0) or 0)))
                source_passages.extend(block_hits[:8])
                file_hits.append({
                    "block_index_name": path.name,
                    "passage_count": len(block_hits),
                    "top_score": float(block_hits[0].get("score", 0.0) or 0.0),
                })

        source_passages.sort(key=lambda row: (-float(row.get("score", 0.0) or 0.0), str(row.get("source_name") or ""), int(row.get("block_id", 0) or 0)))
        return {
            "runtime_source": "flat_symbolic_documents",
            "query_anchors": sorted(query_anchor_set or query_set),
            "files_scanned": files_scanned,
            "files_with_query_symbols": len(file_hits),
            "file_hits": file_hits,
            "files_skipped": files_skipped,
            "source_passages": source_passages[:12],
        }

    def build_source_local_resonance(self, observed_map_name: str) -> dict[str, Any]:
        path = self._resolve_observed_map_name(observed_map_name)
        if not path.exists():
            raise FileNotFoundError(observed_map_name)
        payload = self._read_json(path, {})
        if not isinstance(payload, dict):
            raise ValueError(f"invalid observed map: {path.name}")

        index = build_source_local_resonance_index(payload)
        source_id = index["source_id"]
        safe_stem = index["safe_source_stem"]
        short_source = source_id[:12]
        occurrence_path = self.source_local_occurrences_dir / f"{safe_stem}-{short_source}.occurrences.jsonl"
        profile_path = self.source_local_resonance_dir / f"{safe_stem}-{short_source}.positional_profiles.jsonl"
        directional_path = self.source_local_resonance_dir / f"{safe_stem}-{short_source}.directional_resonance.jsonl"
        cloud_path = self.source_local_resonance_dir / f"{safe_stem}-{short_source}.context_clouds.jsonl"
        summary_path = self.source_local_resonance_dir / f"{safe_stem}-{short_source}.summary.json"

        write_jsonl(occurrence_path, index["occurrences"])
        write_jsonl(profile_path, index["positional_profiles"])
        write_jsonl(directional_path, index["directional_resonance"])
        write_jsonl(cloud_path, index["context_clouds"])

        summary = {
            **index["summary"],
            "saved_at": _utc_now(),
            "observed_map_name": path.name,
            "observed_map_path": str(path),
            "occurrence_path": str(occurrence_path),
            "positional_profiles_path": str(profile_path),
            "directional_resonance_path": str(directional_path),
            "context_clouds_path": str(cloud_path),
            "summary_path": str(summary_path),
        }
        self._write_json(summary_path, summary)

        return {
            "ok": True,
            "source_id": source_id,
            "source_name": summary.get("source_name") or "",
            "source_path": summary.get("source_path") or "",
            "observed_map_name": path.name,
            "occurrence_path": str(occurrence_path),
            "positional_profiles_path": str(profile_path),
            "directional_resonance_path": str(directional_path),
            "context_clouds_path": str(cloud_path),
            "summary_path": str(summary_path),
            "occurrence_records": int(summary["occurrence_records"]),
            "positional_profile_rows": int(summary["positional_profile_rows"]),
            "directional_resonance_rows": int(summary["directional_resonance_rows"]),
            "context_cloud_rows": int(summary["context_cloud_rows"]),
            "writes_allowed": summary["writes_allowed"],
            "authority": summary["authority"],
        }

    def load_misspelled_review(self, name: str) -> dict[str, Any]:
        path = self._resolve_misspelled_review_name(name)
        if not path.exists():
            raise FileNotFoundError(name)
        payload = self._read_json(path, {})
        if not isinstance(payload, dict):
            raise ValueError(f"invalid misspelled review: {path.name}")

        return {
            "ok": True,
            "source_path": payload.get("source_path") or "",
            "source_name": payload.get("source_name") or "",
            "saved_review_path": str(path),
            "saved_review_name": path.name,
            "paragraph_count": int(payload.get("paragraph_count", 0) or 0),
            "total_anchor_observations": int(payload.get("total_anchor_observations", 0) or 0),
            "unique_anchor_count": int(payload.get("unique_anchor_count", 0) or 0),
            "review_count": int(payload.get("review_count", 0) or 0),
            "rows_preview": (payload.get("rows") or [])[:50],
        }

    def distribution(self) -> dict[str, Any]:
        canonical = 0
        structural = 0
        letters = {letter: 0 for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"}

        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            canonical_entries = self._read_entries(self.canonical_dir / f"canonical_{letter}.json")
            canonical += len(canonical_entries)
            letters[letter] += len(canonical_entries)

        structural_entries = self._read_entries(self.structural_file)
        structural = len(structural_entries)
        spare = sum(1 for entry in self._read_spare_entries() if str(entry.get("status", "")).upper() == "AVAILABLE")

        return {
            "total": canonical + structural,
            "canonical": canonical,
            "domain_packs": {},
            "structural": structural,
            "spare_slots": spare,
            "letters": letters,
        }

    def search(self, query: str, pack: str = "all", limit: int = 50) -> list[dict[str, Any]]:
        needle = self.normalize_word(query)
        if len(needle) < 2:
            return []
        results: list[dict[str, Any]] = []
        for pack_name, path in self._pack_paths(pack):
            for entry in self._read_entries(path):
                haystacks = [
                    self.normalize_word(entry.get("word", "")),
                    self.normalize_word(entry.get("display", "")),
                    self.normalize_word(entry.get("hex", "")),
                    self.normalize_word(entry.get("binary", "")),
                    self.normalize_word(entry.get("tone_signature", "")),
                    self.normalize_word(entry.get("status", "")),
                ]
                if any(needle in hay for hay in haystacks if hay):
                    results.append(self._preview_entry(entry, pack_name))
                    if len(results) >= limit:
                        return results
        return results

    def browse(self, letter: str, limit: int = 50, pack: str = "all") -> dict[str, Any]:
        letter = (letter or "A").strip().upper()[:1]
        entries: list[dict[str, Any]] = []
        total = 0
        if pack in {"all", "canonical"}:
            path = self.canonical_dir / f"canonical_{letter}.json"
            batch = self._read_entries(path)
            total += len(batch)
            entries.extend(self._preview_entry(entry, "canonical") for entry in batch[:limit])
        if pack == "spare" and len(entries) < limit:
            batch = self._read_spare_entries()
            total += len(batch)
            remaining = max(0, limit - len(entries))
            entries.extend(self._preview_entry(entry, "spare") for entry in batch[:remaining])
        return {"letter": letter, "total": total, "entries": entries[:limit]}

    def sample(self, count: int = 24, pack: str = "all") -> dict[str, Any]:
        chosen: list[dict[str, Any]] = []
        seen = 0
        for pack_name, path in self._pack_paths(pack):
            if pack_name == "spare" and pack != "spare":
                continue
            for entry in self._read_entries(path):
                seen += 1
                preview = self._preview_entry(entry, pack_name)
                if len(chosen) < count:
                    chosen.append(preview)
                else:
                    index = random.randint(0, seen - 1)
                    if index < count:
                        chosen[index] = preview
        return {"total": seen, "entries": chosen}

    def top(self, count: int = 30, pack: str = "all") -> dict[str, Any]:
        ranked: list[dict[str, Any]] = []
        for pack_name, path in self._pack_paths(pack):
            if pack_name == "spare" and pack != "spare":
                continue
            for entry in self._read_entries(path):
                ranked.append(self._preview_entry(entry, pack_name))
        ranked.sort(key=lambda item: (-int(item.get("frequency", 0) or 0), item.get("word", "") or item.get("hex", "")))
        return {"total": min(count, len(ranked)), "entries": ranked[:count]}

    def recent(self, count: int = 30) -> dict[str, Any]:
        entries: list[dict[str, Any]] = []
        for pack_name, path in self._pack_paths("all"):
            if pack_name == "spare":
                continue
            for entry in self._read_entries(path):
                if entry.get("mapped_at"):
                    entries.append(self._preview_entry(entry, pack_name))
        entries.sort(key=lambda item: item.get("mapped_at") or "", reverse=True)
        return {"total": len(entries), "entries": entries[:count]}

    def files(self) -> dict[str, Any]:
        files: list[dict[str, Any]] = []
        for folder, pattern, pack in [
            (self.canonical_dir, "canonical_{}.json", "canonical"),
        ]:
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                path = folder / pattern.format(letter)
                if path.exists():
                    stat = path.stat()
                    files.append({
                        "filename": path.name,
                        "letter": f"{letter} - {pack}",
                        "size_bytes": stat.st_size,
                        "modified": stat.st_mtime,
                    })
        for path in self._active_spare_paths():
            if path.exists():
                stat = path.stat()
                label = "* - spare" if path == self.spare_slots_path else f"{path.stem.rsplit('_', 1)[-1].upper()} - spare"
                files.append({
                    "filename": path.name,
                    "letter": label,
                    "size_bytes": stat.st_size,
                    "modified": stat.st_mtime,
                })
        if self.structural_file.exists():
            stat = self.structural_file.stat()
            files.append({
                "filename": self.structural_file.name,
                "letter": "# - structural",
                "size_bytes": stat.st_size,
                "modified": stat.st_mtime,
            })
        return {"lexicon_root": str(self.root), "files": files}

    def preview_file(self, filename: str, offset: int = 0, limit: int = 50) -> dict[str, Any]:
        target: Path | None = None
        for _, path in self._pack_paths("all"):
            if path.name == filename:
                target = path
                break
        if target is None:
            raise FileNotFoundError(filename)
        entries = self._read_entries(target)
        pack = "structural"
        if filename.startswith("canonical_"):
            pack = "canonical"
        elif filename == self.spare_slots_path.name or filename.startswith("pool_"):
            pack = "spare"
        preview = [self._preview_entry(entry, pack) for entry in entries[offset: offset + limit]]
        return {"filename": filename, "offset": offset, "limit": limit, "total": len(entries), "entries": preview}

    def entry(self, word: str) -> dict[str, Any] | None:
        found = self._find_entry(word)
        if found is None:
            return None
        raw, pack, _ = found
        preview = self._preview_entry(raw, pack)
        preview.update({
            "display": raw.get("display") or raw.get("word") or "",
            "wordnet": raw.get("wordnet"),
            "aliases": raw.get("aliases") or [],
            "categories": raw.get("categories") or ([raw.get("category")] if raw.get("category") else []),
            "notes": raw.get("notes"),
        })
        return preview

    def context_map(self, word: str) -> dict[str, Any]:
        surface = self.normalize_anchor(word)
        counter, observed_counts = self._load_combined_relation_counts()
        relation_rows = self._relation_count_rows(counter)
        items, _ = build_context_views(
            relation_rows,
            observed_counts=observed_counts,
            window_radius=DEFAULT_WINDOW_RADIUS,
        )

        item = items.get(surface) if isinstance(items, dict) else None
        if isinstance(item, dict):
            return {
                "word": surface,
                "before": item.get("before") or {},
                "after": item.get("after") or {},
                "total_windows": int(item.get("total_neighbor_observations", 0) or 0),
                "center_observations": int(item.get("center_observations", 0) or 0),
                "window_radius": DEFAULT_WINDOW_RADIUS,
            }

        return {
            "word": surface,
            "before": {},
            "after": {},
            "total_windows": 0,
            "center_observations": 0,
            "window_radius": DEFAULT_WINDOW_RADIUS,
        }

    def build_observed_map(self, source_path: Path, *, count_target: str = "base") -> dict[str, Any]:
        source_path = Path(source_path).expanduser().resolve()
        if not source_path.exists():
            raise FileNotFoundError(source_path)
        if source_path.is_dir():
            raise IsADirectoryError(source_path)

        prepared = prepare_file(source_path)
        if isinstance(prepared.metadata, dict) and prepared.metadata.get("visual_manifest"):
            raise ValueError("visual intake preview is source-local evidence only; use a future visual approval route before mapping/counting")
        text = prepared.prepared_text
        inventory = self._extract_document_anchor_inventory(text)
        observed_counts: Counter[str] = inventory["observed_counts"]
        known_anchors = set(self._all_known_anchors())
        unique_anchors = sorted(observed_counts)

        resolution_map: dict[str, str] = {anchor: anchor for anchor in unique_anchors if anchor in known_anchors}
        missing_counts: Counter[str] = Counter({
            anchor: count for anchor, count in observed_counts.items() if anchor not in known_anchors
        })
        suggestions = self._precompute_spell_suggestions(missing_counts, known_anchors)
        review_rows = self._build_misspelled_review_rows(missing_counts, known_anchors, suggestions=suggestions)
        review_index = {row["anchor"]: row for row in review_rows}

        corrections: list[dict[str, Any]] = []
        additions: list[dict[str, Any]] = []
        unresolved_counts: Counter[str] = Counter(missing_counts)

        unresolved_anchor_count = len(unresolved_counts)
        temp_symbol_map, temp_entries = self._build_temp_symbol_entries(source_path, unresolved_counts)
        resolution_map.update(temp_symbol_map)
        for anchor, temp_symbol in temp_symbol_map.items():
            row = review_index.get(anchor)
            if row is not None:
                row["ingest_action"] = "temp_symbolized"
                row["resolved_to"] = temp_symbol
                row["temp_symbol_version"] = TEMP_SYMBOL_VERSION

        review_path = self._write_misspelled_review(source_path, inventory, review_rows)
        if unresolved_anchor_count > 0:
            self._register_missing_anchors(unresolved_counts)
            logger.info("LEXICON INCOMPLETE: using source-local temp symbols for unresolved anchors")
        else:
            logger.info("LEXICON COMPLETE: proceeding to mapping")

        mapping = build_anchor_map(
            text,
            window_radius=DEFAULT_WINDOW_RADIUS,
            resolved_anchors=resolution_map,
        )
        line_locators = self._paragraph_line_locators({
            "source_path": str(source_path),
            "paragraphs": mapping["paragraphs"],
        })
        for paragraph in mapping["paragraphs"]:
            locator = line_locators.get(int(paragraph.get("paragraph_id", 0) or 0))
            if locator:
                paragraph.update(locator)
        for occurrence in mapping["occurrences"]:
            locator = line_locators.get(int(occurrence.get("paragraph_id", 0) or 0))
            if locator:
                occurrence["block_id"] = locator["block_id"]
                occurrence["line_start"] = locator["line_start"]
                occurrence["line_end"] = locator["line_end"]
        resolved_counts: Counter[str] = mapping["observed_counts"]
        temp_symbols_present = bool(temp_entries)
        if temp_symbols_present:
            count_write = {
                "count_target": count_target,
                "count_paths": [],
                "lifetime_write_skipped": True,
                "reason": "source_local_temp_symbols_present",
            }
        elif count_target == "base":
            self._update_lifetime_relation_counts(
                mapping["co_occurrence_counts"],
                observed_counts=resolved_counts,
            )
            count_write = {
                "count_target": "base",
                "count_paths": [str(self.lifetime_counts_path)],
                "lifetime_write_skipped": False,
            }
        elif count_target == "user_chat":
            user_write = self._update_user_chat_relation_counts(
                mapping["co_occurrence_counts"],
                observed_counts=resolved_counts,
            )
            count_write = {
                "count_target": "user_chat",
                "count_paths": [user_write["user_counts_path"], user_write["chat_counts_path"]],
                **user_write,
            }
        else:
            raise ValueError(f"unknown count target: {count_target}")

        observed_rows = [
            {
                "anchor": anchor,
                "observations": count,
                "known": anchor in known_anchors,
                "resolved_to": resolution_map.get(anchor, anchor),
            }
            for anchor, count in sorted(observed_counts.items(), key=lambda item: (-item[1], item[0]))
        ]

        known_counts: Counter[str] = Counter({
            anchor: count for anchor, count in observed_counts.items() if anchor in known_anchors
        })

        temp_lexicon_path: Path | None = None
        source_local_preview_counts_path: Path | None = None
        if temp_entries:
            temp_lexicon_path = self._temp_lexicon_path(source_path)
            self._write_json(temp_lexicon_path, {
                "saved_at": _utc_now(),
                "source_path": str(source_path),
                "source_name": source_path.name,
                "temp_symbol_version": TEMP_SYMBOL_VERSION,
                "authority": "source_local_coordinate",
                "entries": temp_entries,
            })
            source_local_preview_counts_path = self._source_local_preview_counts_path(source_path)
            self._write_json(source_local_preview_counts_path, {
                "saved_at": _utc_now(),
                "source_path": str(source_path),
                "source_name": source_path.name,
                "count_scope": "source_local_preview",
                "temp_symbol_version": TEMP_SYMBOL_VERSION,
                "anchor_observation_counts": self._anchor_rows(resolved_counts),
                "co_occurrence_counts": mapping["co_occurrence_counts"],
                "items": mapping["items"],
                "anchor_index": mapping["anchor_index"],
            })

        payload = {
            "saved_at": _utc_now(),
            "source_path": str(source_path),
            "source_name": source_path.name,
            "paragraph_count": mapping["paragraph_count"],
            "window_radius": mapping["window_radius"],
            "total_anchor_observations": int(sum(observed_counts.values())),
            "unique_anchor_count": len(observed_counts),
            "known_anchor_count": len(known_counts),
            "missing_anchor_count": len(missing_counts),
            "known_anchor_observations": int(sum(known_counts.values())),
            "missing_anchor_observations": int(sum(missing_counts.values())),
            "paragraphs": mapping["paragraphs"],
            "paragraph_line_locators": {str(key): value for key, value in line_locators.items()},
            "occurrences": mapping["occurrences"],
            "co_occurrence_counts": mapping["co_occurrence_counts"],
            "items": mapping["items"],
            "anchor_index": mapping["anchor_index"],
            "stats": mapping["stats"],
            "known_anchors": self._anchor_rows(known_counts),
            "missing_anchors": self._anchor_rows(missing_counts),
            "observed_anchors": observed_rows,
            "spell_corrections": corrections,
            "lexicon_additions": additions,
            "temp_symbol_count": len(temp_entries),
            "temp_symbols": temp_entries,
            "temp_lexicon_path": str(temp_lexicon_path) if temp_lexicon_path else "",
            "source_local_preview_counts_path": str(source_local_preview_counts_path) if source_local_preview_counts_path else "",
            "document_prep": {
                key: value
                for key, value in prepared.to_dict().items()
                if key != "prepared_text"
            },
            "count_target": count_write["count_target"],
            "count_paths": count_write["count_paths"],
            "count_write": count_write,
        }

        map_path = self._observed_map_path(source_path)
        self._write_json(map_path, payload)

        return {
            "ok": True,
            "source_path": str(source_path),
            "source_name": source_path.name,
            "saved_map_path": str(map_path),
            "saved_map_name": map_path.name,
            "paragraph_count": payload["paragraph_count"],
            "window_radius": payload["window_radius"],
            "total_anchor_observations": payload["total_anchor_observations"],
            "unique_anchor_count": payload["unique_anchor_count"],
            "known_anchor_count": payload["known_anchor_count"],
            "missing_anchor_count": payload["missing_anchor_count"],
            "known_anchor_observations": payload["known_anchor_observations"],
            "missing_anchor_observations": payload["missing_anchor_observations"],
            "registered_missing_anchors": len(missing_counts),
            "known_anchors_preview": payload["known_anchors"][:25],
            "missing_anchors_preview": payload["missing_anchors"][:25],
            "observed_anchors_preview": payload["observed_anchors"][:25],
            "occurrence_preview": payload["occurrences"][:12],
            "co_occurrence_preview": payload["co_occurrence_counts"][:12],
            "anchor_index_preview": payload["anchor_index"][:25],
            "context_items_preview": list(payload["items"].values())[:12],
            "document_prep": payload["document_prep"],
            "count_target": count_write["count_target"],
            "count_paths": count_write["count_paths"],
            "count_write": count_write,
            "temp_symbol_count": len(temp_entries),
            "temp_lexicon_path": str(temp_lexicon_path) if temp_lexicon_path else "",
            "source_local_preview_counts_path": str(source_local_preview_counts_path) if source_local_preview_counts_path else "",
            "misspelled_review_path": str(review_path),
            "misspelled_review_name": review_path.name,
            "misspelled_review_preview": review_rows[:25],
        }

    def unmatched(self, letter: str | None = None, limit: int = 100) -> dict[str, Any]:
        entries = self._load_unmatched()
        if letter:
            needle = self.normalize_word(letter)[:1]
            entries = [item for item in entries if self.normalize_word(item["word"]).startswith(needle)]
        entries.sort(key=lambda item: (-int(item.get("frequency", 0) or 0), item["word"]))
        return {"unmatched_total": len(entries), "entries": entries[:limit]}

    def approve_unmatched(self, word: str) -> dict[str, Any]:
        surface = self.normalize_anchor(word)
        if not surface:
            raise ValueError("word required")
        if self._find_entry(surface):
            raise ValueError("word already exists in lexicon")
        with self._lock:
            unmatched = self._load_unmatched()
            pending = self._load_pending()
            picked = next((item for item in unmatched if item["word"] == surface), None)
            unmatched = [item for item in unmatched if item["word"] != surface]
            if not any(item["word"] == surface for item in pending):
                pending.append({
                    "word": surface,
                    "frequency": int((picked or {}).get("frequency", 0) or 0),
                    "added_at": _utc_now(),
                })
            self._write_unmatched(unmatched)
            self._write_pending(pending)
        return {"ok": True, "word": surface}

    def ignore_word(self, word: str) -> dict[str, Any]:
        surface = self.normalize_anchor(word)
        if not surface:
            raise ValueError("word required")
        with self._lock:
            ignored = self._load_ignored()
            if surface not in ignored:
                ignored.append(surface)
            self._write_ignored(ignored)
            self._write_unmatched([item for item in self._load_unmatched() if item["word"] != surface])
            self._write_pending([item for item in self._load_pending() if item["word"] != surface])
        return {"ok": True, "word": surface}

    def unignore_word(self, word: str) -> dict[str, Any]:
        surface = self.normalize_anchor(word)
        with self._lock:
            ignored = [item for item in self._load_ignored() if item != surface]
            self._write_ignored(ignored)
        return {"ok": True, "word": surface}

    def ignored(self, letter: str | None = None) -> dict[str, Any]:
        words = self._load_ignored()
        if letter:
            needle = self.normalize_word(letter)[:1]
            words = [word for word in words if self.normalize_word(word).startswith(needle)]
        return {"total": len(words), "words": words}

    def missing_anchor_review_queue(
        self,
        *,
        limit: int = 100,
        min_observations: int = 1,
        letter: str | None = None,
    ) -> dict[str, Any]:
        known = set(self._all_known_anchors())
        ignored = set(self._load_ignored())
        pending = {row["word"] for row in self._load_pending()}
        unmatched = {row["word"] for row in self._load_unmatched()}
        letter_prefix = self.normalize_word(letter or "")[:1]
        minimum = max(1, int(min_observations or 1))
        rows: list[dict[str, Any]] = []
        skipped_known = 0
        skipped_ignored = 0

        for row in self._load_missing_anchor_registry():
            anchor = self.normalize_anchor(row.get("anchor") or "")
            observations = int(row.get("observations", 0) or 0)
            if not anchor or observations < minimum:
                continue
            if letter_prefix and not self.normalize_word(anchor).startswith(letter_prefix):
                continue
            if anchor in known:
                skipped_known += 1
                continue
            if anchor in ignored:
                skipped_ignored += 1
                continue
            if anchor in pending:
                status = "pending"
            elif anchor in unmatched:
                status = "unmatched"
            else:
                status = "unreviewed"
            rows.append({
                "anchor": anchor,
                "observations": observations,
                "first_seen": row.get("first_seen") or "",
                "last_seen": row.get("last_seen") or "",
                "review_status": status,
                "known": False,
                "ignored": False,
            })

        rows.sort(key=lambda item: (-int(item["observations"]), item["anchor"]))
        capped_limit = max(1, int(limit or 100))
        return {
            "ok": True,
            "total_registry_anchors": len(self._load_missing_anchor_registry()),
            "reviewable_total": len(rows),
            "returned": min(len(rows), capped_limit),
            "skipped_known": skipped_known,
            "skipped_ignored": skipped_ignored,
            "min_observations": minimum,
            "entries": rows[:capped_limit],
            "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
        }

    def sync_missing_anchor_review_queue(
        self,
        *,
        limit: int = 1000,
        min_observations: int = 1,
        letter: str | None = None,
    ) -> dict[str, Any]:
        review = self.missing_anchor_review_queue(
            limit=limit,
            min_observations=min_observations,
            letter=letter,
        )
        candidates = [
            row for row in review.get("entries") or []
            if row.get("review_status") == "unreviewed"
        ]
        moved: list[dict[str, Any]] = []
        with self._lock:
            unmatched = self._load_unmatched()
            existing = {row["word"] for row in unmatched}
            timestamp = _utc_now()
            for row in candidates:
                anchor = self.normalize_anchor(row.get("anchor") or "")
                if not anchor or anchor in existing:
                    continue
                entry = {
                    "word": anchor,
                    "frequency": int(row.get("observations", 0) or 0),
                    "first_seen": row.get("first_seen") or timestamp,
                    "added_at": timestamp,
                    "source": "missing_anchor_registry",
                }
                unmatched.append(entry)
                existing.add(anchor)
                moved.append(entry)
            unmatched.sort(key=lambda item: (-int(item.get("frequency", 0) or 0), item["word"]))
            self._write_unmatched(unmatched)
        return {
            "ok": True,
            "moved_to_unmatched": len(moved),
            "reviewable_total": review.get("reviewable_total", 0),
            "entries": moved,
            "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
        }

    def pending(self) -> dict[str, Any]:
        entries = self._load_pending()
        entries.sort(key=lambda item: item.get("added_at") or "", reverse=True)
        return {"total": len(entries), "entries": entries}

    def remove_pending(self, word: str) -> dict[str, Any]:
        surface = self.normalize_anchor(word)
        with self._lock:
            pending = [item for item in self._load_pending() if item["word"] != surface]
            self._write_pending(pending)
        return {"ok": True, "word": surface}

    def _count_available_slots(self) -> int:
        return sum(1 for item in self._read_spare_entries() if str(item.get("status", "")).upper() == "AVAILABLE")

    def _assign_surface_anchor(self, anchor: str, frequency: int = 0) -> dict[str, Any]:
        surface_anchor = self.normalize_anchor(anchor)
        if not surface_anchor:
            raise ValueError("anchor required")
        if surface_anchor in self._all_known_anchors():
            raise ValueError("anchor already exists in lexicon")

        letter = self._letter_for_word(surface_anchor)
        canonical_path = self.canonical_dir / f"canonical_{letter}.json"
        pool_entries = self._read_spare_entries()
        canonical_entries = self._read_entries(canonical_path)

        slot_index = next(
            (index for index, item in enumerate(pool_entries) if str(item.get("status", "")).upper() == "AVAILABLE"),
            None,
        )
        if slot_index is None:
            raise ValueError("no available spare slots")

        slot = pool_entries.pop(slot_index)
        new_entry = {
            "binary": slot.get("binary", ""),
            "hex": slot.get("hex") or slot.get("symbol", ""),
            "font_symbol": slot.get("font_symbol", ""),
            "tone_signature": slot.get("tone_signature", ""),
            "status": "ASSIGNED",
            "word": surface_anchor,
            "display": surface_anchor,
            "symbol": slot.get("hex") or slot.get("symbol", ""),
            "mapped_at": _utc_now(),
            "pack": "canonical",
            "frequency": int(frequency or 0),
        }
        canonical_entries.append(new_entry)
        canonical_entries.sort(key=lambda item: (str(item.get("word", "")).casefold(), str(item.get("word", ""))))
        self._write_spare_entries(pool_entries)
        self._write_entries(canonical_path, canonical_entries)
        self._invalidate_known_anchor_index()
        return {
            "ok": True,
            "anchor": surface_anchor,
            "hex": new_entry["hex"],
            "symbol": new_entry["symbol"],
            "slots_available": self._count_available_slots(),
            "action": "added_to_lexicon",
        }

    def _assign_word(self, word: str, frequency: int = 0) -> dict[str, Any]:
        surface = self.normalize_anchor(word)
        if self._find_entry(surface):
            raise ValueError("word already exists in lexicon")
        letter = self._letter_for_word(surface)
        canonical_path = self.canonical_dir / f"canonical_{letter}.json"
        pool_entries = self._read_spare_entries()
        canonical_entries = self._read_entries(canonical_path)

        slot_index = next(
            (index for index, item in enumerate(pool_entries) if str(item.get("status", "")).upper() == "AVAILABLE"),
            None,
        )
        if slot_index is None:
            raise ValueError("no available spare slots")

        slot = pool_entries.pop(slot_index)
        new_entry = {
            "binary": slot.get("binary", ""),
            "hex": slot.get("hex") or slot.get("symbol", ""),
            "font_symbol": slot.get("font_symbol", ""),
            "tone_signature": slot.get("tone_signature", ""),
            "status": "ASSIGNED",
            "word": surface,
            "display": surface,
            "symbol": slot.get("hex") or slot.get("symbol", ""),
            "mapped_at": _utc_now(),
            "pack": "canonical",
            "frequency": int(frequency or 0),
        }
        canonical_entries.append(new_entry)
        canonical_entries.sort(key=lambda item: (str(item.get("word", "")).casefold(), str(item.get("word", ""))))
        self._write_spare_entries(pool_entries)
        self._write_entries(canonical_path, canonical_entries)
        self._invalidate_known_anchor_index()
        return {
            "ok": True,
            "word": surface,
            "hex": new_entry["hex"],
            "symbol": new_entry["symbol"],
            "slots_available": self._count_available_slots(),
        }

    def assign_pending(self, word: str) -> dict[str, Any]:
        surface = self.normalize_anchor(word)
        with self._lock:
            pending = self._load_pending()
            item = next((entry for entry in pending if entry["word"] == surface), None)
            if item is None:
                raise ValueError("pending word not found")
            result = self._assign_word(surface, frequency=int(item.get("frequency", 0) or 0))
            pending = [entry for entry in pending if entry["word"] != surface]
            self._write_pending(pending)
            return result

    def assign_all_pending(self) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        assigned = 0
        failed = 0
        for item in list(self._load_pending()):
            try:
                result = self.assign_pending(item["word"])
                results.append(result)
                assigned += 1
            except Exception as exc:
                results.append({"ok": False, "word": item["word"], "detail": str(exc)})
                failed += 1
        return {"assigned": assigned, "failed": failed, "results": results}

    def approve_all_unmatched(self) -> dict[str, Any]:
        moved = 0
        for item in list(self._load_unmatched()):
            self.approve_unmatched(item["word"])
            moved += 1
        return {"moved": moved}

    def deny_all_unmatched(self) -> dict[str, Any]:
        denied = 0
        for item in list(self._load_unmatched()):
            self.ignore_word(item["word"])
            denied += 1
        return {"denied": denied}

    def clear_canonical(self) -> dict[str, Any]:
        moved = 0
        with self._lock:
            pool_entries = self._read_spare_entries()
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                canonical_path = self.canonical_dir / f"canonical_{letter}.json"
                canonical_entries = self._read_entries(canonical_path)
                if not canonical_entries:
                    continue
                for entry in canonical_entries:
                    if entry.get("hex") or entry.get("symbol"):
                        pool_entries.append({
                            "binary": entry.get("binary", ""),
                            "hex": entry.get("hex") or entry.get("symbol", ""),
                            "font_symbol": entry.get("font_symbol", ""),
                            "tone_signature": entry.get("tone_signature", ""),
                            "status": "AVAILABLE",
                        })
                        moved += 1
                self._write_entries(canonical_path, [])
            self._write_spare_entries(pool_entries)
            self._invalidate_known_anchor_index()
        return {
            "purged": moved,
            "slots_reclaimed": moved,
            "slots_available": self._count_available_slots(),
            "pool_available": self._count_available_slots(),
            "moved": moved,
        }

    def return_to_pool(self) -> dict[str, Any]:
        return self.clear_canonical()

    def import_words_dir(self, words_dir: Path) -> dict[str, Any]:
        words_dir = Path(words_dir).expanduser().resolve()
        requested_by_letter: dict[str, list[str]] = {letter: [] for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"}
        frequencies: dict[str, int] = {}
        seen_global: set[str] = set()

        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            path = words_dir / f"verified_{letter}.json"
            if path.exists():
                data = self._read_json(path, [])
                entries: list[tuple[str, int]] = []
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, str):
                            entries.append((item, 0))
                        elif isinstance(item, dict):
                            value = item.get("word") or item.get("display")
                            if value:
                                entries.append((str(value), int(item.get("frequency", item.get("observations", 0)) or 0)))
                seen_letter: set[str] = set()
                for raw_word, frequency in entries:
                    word = self.normalize_anchor(raw_word)
                    if not word or word in seen_letter or word in seen_global:
                        continue
                    seen_letter.add(word)
                    seen_global.add(word)
                    requested_by_letter[letter].append(word)
                    frequencies[word] = int(frequency or 0)

        requested = [word for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" for word in requested_by_letter[letter]]
        result = self.approve_intake_anchors(requested, frequencies=frequencies)
        approved_words = {row.get("word") for row in result.get("approved", [])}
        skipped_words = {row.get("anchor") for row in result.get("skipped", [])}
        failed_words = {row.get("anchor") for row in result.get("failed", [])}
        letters: list[dict[str, Any]] = []
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            words = requested_by_letter[letter]
            letters.append({
                "letter": letter,
                "bound": sum(1 for word in words if word in approved_words),
                "skipped": sum(1 for word in words if word in skipped_words),
                "no_slots": sum(1 for word in words if word in failed_words),
            })

        return {
            "imported": int(result.get("approved_count", 0) or 0),
            "skipped": int(result.get("skipped_count", 0) or 0),
            "no_slots": int(result.get("failed_count", 0) or 0),
            "slots_available": self._count_available_slots(),
            "spare_pool_writes": int(result.get("spare_pool_writes", 0) or 0),
            "lexicon_files_written": int(result.get("lexicon_files_written", 0) or 0),
            "index_reloads": int(result.get("index_reloads", 0) or 0),
            "letters": letters,
        }
