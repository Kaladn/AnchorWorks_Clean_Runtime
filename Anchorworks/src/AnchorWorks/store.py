from __future__ import annotations

import hashlib
import ctypes
import gc
import json
import logging
import os
import random
import re
import threading
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .anchorworks_chat_archive import prepare_anchorworks_chat_archive
from .anchor_classification import classify_unknown_anchor_rows, write_classified_unknown_report, write_math_lexicon
from .document_prep import prepare_bytes, prepare_file
from .intake import (
    DEFAULT_WINDOW_RADIUS,
    EMOJI_ANCHOR,
    NULL_ANCHOR,
    build_anchor_map,
    build_context_views,
    compose_anchor_stream,
    extract_anchor_rows,
    split_paragraphs,
)
from .local_meta_overlay import build_local_meta_count_overlay, load_local_meta_count_overlay
from .positional_resonance import (
    build_source_local_resonance_index,
    write_jsonl,
)
from .symbol_relation_counts import build_source_local_symbol_table, build_symbol_relation_rows
from .symbol_count_native import (
    merge_symbol_stream,
    verify_binary_counts,
    write_awss_from_symbol_count_artifacts,
)
from .symbolic_map_binary import (
    SymbolicMapRelation,
    read_symbolic_map_binary,
    read_symbolic_map_bundle,
    write_symbolic_map_locator_sidecar,
    write_symbolic_map_null_sidecar,
    write_symbolic_map_visual_sidecar,
    write_symbolic_map_binary,
)
from .store_modules.admin import AdminStore
from .store_modules.authority import AuthorityStore
from .store_modules.evidence import EvidenceStore
from .store_modules.intake import IntakeStore
from .store_modules.memory import MemoryStore
from .store_modules.paths import StorePaths, anchor_maps_root_for
from .store_modules.visual import VisualStore


logger = logging.getLogger(__name__)
_SPELL_SUGGESTION_WORD_RE = re.compile(r"^[A-Za-z]+(?:['’][A-Za-z]+)*$")
_SPELL_SUGGESTION_MISSING_LIMIT = 512
TEMP_SYMBOL_VERSION = "temp_symbol@1"
TEMP_SYMBOL_PREFIX = "U"
TEMP_SYMBOL_HEX_LENGTH = 11
COMPANION_AUTHORITY_LANES = {"math_terms_or_symbols", "math_markup", "domain_notation_anchors", "structural_source_anchors"}
NULL_SYMBOL_LANES = {"null_symbol_anchors", "source_id_artifacts"}

def _anchor_maps_root_for(data_root: Path) -> Path:
    return anchor_maps_root_for(data_root)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _current_process_rss_bytes() -> int:
    if os.name == "nt":
        class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
                ("PrivateUsage", ctypes.c_size_t),
            ]

        counters = PROCESS_MEMORY_COUNTERS_EX()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS_EX)
        if ctypes.windll.psapi.GetProcessMemoryInfo(  # type: ignore[attr-defined]
            ctypes.windll.kernel32.GetCurrentProcess(),  # type: ignore[attr-defined]
            ctypes.byref(counters),
            counters.cb,
        ):
            return int(counters.WorkingSetSize)
        return 0
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF)
        return int(usage.ru_maxrss) * 1024
    except Exception:
        return 0


def _memory_status(rss_bytes: int, soft_warning_gb: float, emergency_flush_gb: float, abort_gb: float) -> str:
    if rss_bytes <= 0:
        return "unknown"
    gib = rss_bytes / (1024 * 1024 * 1024)
    if gib >= float(abort_gb):
        return "abort_after_chunk"
    if gib >= float(emergency_flush_gb):
        return "emergency_flush"
    if gib >= float(soft_warning_gb):
        return "soft_warning"
    return "ok"


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


def _build_observed_map_worker(args: tuple[str, str, str, list[str]]) -> dict[str, Any]:
    data_root, source_path, count_target, null_anchor_rows = args
    store = LexiconStore(Path(data_root))
    null_anchors = set(null_anchor_rows) if null_anchor_rows else None
    return store.build_observed_map(Path(source_path), count_target=count_target, null_anchors=null_anchors)


def _ordered_unique(values: Any) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        clean = str(value or "").strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        out.append(clean)
    return out


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
        self.paths = StorePaths(self.root)
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
        self.anchor_maps_root = _anchor_maps_root_for(self.root)
        self.observed_maps_dir = self.anchor_maps_root / "observed_maps"
        self.symbolic_maps_dir = self.anchor_maps_root / "symbolic_maps"
        self.misspelled_reviews_dir = self.state_dir / "misspelled_reviews"
        self.temp_lexicons_dir = self.state_dir / "temp_lexicons" / "source_local"
        self.source_local_symbol_counts_dir = self.state_dir / "source_local_symbol_counts"
        self.symbol_counts_binary_dir = self.state_dir / "symbol_counts_binary"
        self.symbol_streams_dir = self.state_dir / "symbol_streams"
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
        self.flat_documents_local_overlays_dir = self.flat_documents_dir / "local_overlays"
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
        self._canonical_anchor_index: set[str] | None = None
        self._canonical_symbol_index: dict[str, str] | None = None
        self._known_anchor_spell_index: dict[tuple[str, tuple[bool, int], int], list[str]] | None = None
        self._spare_entries_cache: list[dict[str, Any]] | None = None
        self._spare_entries_cache_key: tuple[tuple[str, int | None, int | None], ...] | None = None
        self._lock = threading.RLock()
        self.authority = AuthorityStore(self)
        self.evidence = EvidenceStore(self)
        self.memory = MemoryStore(self)
        self.intake_power = IntakeStore(self)
        self.visual = VisualStore(self)
        self.admin = AdminStore(self)

        self.spare_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.user_state_dir.mkdir(parents=True, exist_ok=True)
        self.user_lexicon_dir.mkdir(parents=True, exist_ok=True)
        self.user_counts_dir.mkdir(parents=True, exist_ok=True)
        self.chat_counts_dir.mkdir(parents=True, exist_ok=True)
        self.ingest_staging_dir.mkdir(parents=True, exist_ok=True)
        self.rejected_or_literal_clusters_dir.mkdir(parents=True, exist_ok=True)
        self.observed_maps_dir.mkdir(parents=True, exist_ok=True)
        self.symbolic_maps_dir.mkdir(parents=True, exist_ok=True)
        self.misspelled_reviews_dir.mkdir(parents=True, exist_ok=True)
        self.temp_lexicons_dir.mkdir(parents=True, exist_ok=True)
        self.source_local_symbol_counts_dir.mkdir(parents=True, exist_ok=True)
        self.symbol_counts_binary_dir.mkdir(parents=True, exist_ok=True)
        self.symbol_streams_dir.mkdir(parents=True, exist_ok=True)
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
        self.flat_documents_local_overlays_dir.mkdir(parents=True, exist_ok=True)
        self.intake_uploads_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_state_file(self.unmatched_path, [])
        self._ensure_state_file(self.pending_path, [])
        self._ensure_state_file(self.ignored_path, [])
        self._ensure_state_file(self.missing_anchor_registry_path, [])
        self._ensure_state_file(self.custom_entries_path, {})
        self._ensure_state_file(self.user_lexicon_path, [])
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
                "binary_counts": str(self.symbol_counts_binary_dir),
            },
        }

    def _read_entries(self, path: Path) -> list[dict[str, Any]]:
        data = self._read_json(path, [])
        return data if isinstance(data, list) else []

    def _write_entries(self, path: Path, entries: list[dict[str, Any]]) -> None:
        self._write_json(path, entries)

    def _invalidate_known_anchor_index(self) -> None:
        self._known_anchor_index = None
        self._canonical_anchor_index = None
        self._canonical_symbol_index = None
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
            canonical_paths = sorted(self.canonical_dir.glob("canonical_*.json"))
            if canonical_paths:
                paths.extend(("canonical", path) for path in canonical_paths)
            else:
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

    def recognize_query_anchors(self, text: str) -> dict[str, Any]:
        observed = _ordered_unique(row["anchor"] for row in extract_anchor_rows(str(text or "")) if row.get("anchor"))
        known = self._all_known_anchors()
        represented = [anchor for anchor in observed if anchor in known]
        missing = [anchor for anchor in observed if anchor not in known]
        return {
            "schema_version": "anchorworks_lexicon_recognition@1",
            "query": str(text or ""),
            "query_anchors": observed,
            "represented_anchors": represented,
            "missing_anchors": missing,
            "recognition_layer": "lexicon",
            "lexicon_first": True,
            "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
        }

    def _canonical_anchors(self) -> set[str]:
        if self._canonical_anchor_index is not None:
            return self._canonical_anchor_index

        canonical: set[str] = set()
        for _, path in self._pack_paths("canonical"):
            for entry in self._read_entries(path):
                word = entry.get("word")
                if isinstance(word, str) and word:
                    normalized = self.normalize_anchor(word)
                    if normalized:
                        canonical.add(normalized)

        self._canonical_anchor_index = canonical
        return canonical

    def _canonical_symbol_by_anchor(self) -> dict[str, str]:
        if self._canonical_symbol_index is not None:
            return dict(self._canonical_symbol_index)
        out: dict[str, str] = {}
        for _, path in self._pack_paths("canonical"):
            for entry in self._read_entries(path):
                anchor = self.normalize_anchor(entry.get("word", ""))
                symbol = str(entry.get("hex") or entry.get("symbol") or "").strip()
                if anchor and symbol:
                    out[anchor] = symbol
        self._canonical_symbol_index = dict(out)
        return out

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
        count_target: str = "binary_source_local",
        intake_edits: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if _is_visual_preview_content(content):
            raise ValueError("visual intake preview is source-local evidence only; use a future visual approval route before mapping/counting")
        null_anchors = {
            self.normalize_anchor(str(edit.get("original_anchor") or ""))
            for edit in (intake_edits or [])
            if str(edit.get("action") or "").strip().lower() == "null"
            and self.normalize_anchor(str(edit.get("original_anchor") or ""))
        }
        staged_path = self._intake_upload_path(source_name=source_name, content=content)
        staged_path.write_text(content, encoding="utf-8")
        return self.build_observed_map(staged_path, count_target=count_target, null_anchors=null_anchors)

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

    def _symbolic_map_path(self, source_path: Path) -> Path:
        digest = hashlib.sha1(str(source_path).encode("utf-8")).hexdigest()[:12]
        safe_name = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in source_path.stem).strip("_")
        if not safe_name:
            safe_name = "symbolic"
        return self.symbolic_maps_dir / f"{safe_name}-{digest}.awsm"

    def _symbolic_locator_path(self, source_path: Path) -> Path:
        digest = hashlib.sha1(str(source_path).encode("utf-8")).hexdigest()[:12]
        safe_name = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in source_path.stem).strip("_")
        if not safe_name:
            safe_name = "symbolic"
        return self.symbolic_maps_dir / f"{safe_name}-{digest}.locators.awsl"

    def _symbolic_null_path(self, source_path: Path) -> Path:
        digest = hashlib.sha1(str(source_path).encode("utf-8")).hexdigest()[:12]
        safe_name = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in source_path.stem).strip("_")
        if not safe_name:
            safe_name = "symbolic"
        return self.symbolic_maps_dir / f"{safe_name}-{digest}.nulls.awsn"

    def _symbolic_visual_path(self, source_path: Path) -> Path:
        digest = hashlib.sha1(str(source_path).encode("utf-8")).hexdigest()[:12]
        safe_name = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in source_path.stem).strip("_")
        if not safe_name:
            safe_name = "symbolic"
        return self.symbolic_maps_dir / f"{safe_name}-{digest}.visuals.awsv"

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

    def _resolve_symbolic_map_name(self, name: str) -> Path:
        filename = Path(name).name
        if filename.endswith(".observed.json"):
            filename = filename[: -len(".observed.json")] + ".awsm"
        target = (self.symbolic_maps_dir / filename).resolve()
        if target.parent != self.symbolic_maps_dir.resolve():
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

    def _null_occurrence_index(self, occurrences: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for occurrence in occurrences:
            if occurrence.get("anchor") != NULL_ANCHOR:
                continue
            block_id = int(occurrence.get("block_id", occurrence.get("paragraph_id", 0)) or 0)
            line_start = int(occurrence.get("line_start", 0) or 0)
            position = int(occurrence.get("position", 0) or 0)
            rows.append({
                "schema_version": "anchorworks_null_index@1",
                "block_id": block_id,
                "line_start": line_start,
                "line_end": int(occurrence.get("line_end", line_start) or line_start),
                "anchor_position": position,
                "anchor_label": f"Block {block_id} Ln {line_start} Anchor {position}",
                "observed_anchor": occurrence.get("observed_anchor", ""),
                "surface": occurrence.get("surface", ""),
                "resolved_anchor": NULL_ANCHOR,
                "count_eligible": False,
                "memory_truth": False,
            })
        rows.sort(key=lambda row: (int(row["block_id"]), int(row["line_start"]), int(row["anchor_position"]), str(row["observed_anchor"])))
        return rows

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

    def _load_combined_relation_counts(self) -> tuple[Counter[tuple[str, str, str]], Counter[str]]:
        base_counter, base_observed, _ = self._load_relation_counts_file(self.lifetime_counts_path)
        user_counter, user_observed, _ = self._load_relation_counts_file(self.user_counts_path)
        combined_counter = Counter(base_counter)
        combined_counter.update(user_counter)
        combined_observed = Counter(base_observed)
        combined_observed.update(user_observed)
        return combined_counter, combined_observed

    def _canonical_lifetime_relation_rows(
        self,
        relation_rows: list[dict[str, Any]],
        canonical_counts: Counter[str],
    ) -> list[dict[str, Any]]:
        canonical_anchors = set(canonical_counts)
        out: list[dict[str, Any]] = []
        for row in relation_rows:
            if not isinstance(row, dict):
                continue
            anchor = row.get("anchor")
            neighbor = row.get("neighbor")
            observations = int(row.get("observations", 0) or 0)
            if not isinstance(anchor, str) or not isinstance(neighbor, str) or observations <= 0:
                continue
            if anchor not in canonical_anchors or neighbor not in canonical_anchors:
                continue
            out.append(dict(row))
        return out

    def _symbol_relation_fates(
        self,
        relation_rows: list[dict[str, Any]],
        authority_by_anchor: dict[str, str],
    ) -> dict[str, int]:
        fates = Counter()
        for row in relation_rows:
            if not isinstance(row, dict):
                continue
            anchor = str(row.get("anchor") or "")
            neighbor = str(row.get("neighbor") or "")
            observations = int(row.get("observations", 0) or 0)
            if observations <= 0:
                continue
            anchor_authority = authority_by_anchor.get(anchor, "unresolved")
            neighbor_authority = authority_by_anchor.get(neighbor, "unresolved")
            if anchor_authority == "canonical" and neighbor_authority == "canonical":
                fates["canonical_to_canonical"] += observations
            elif "unresolved" in {anchor_authority, neighbor_authority}:
                fates["unresolved_relation"] += observations
            elif "source_local" in {anchor_authority, neighbor_authority}:
                fates["source_local_relation"] += observations
            else:
                fates["other_relation"] += observations
        return dict(sorted(fates.items()))

    def _symbol_relation_fates_from_symbol_rows(
        self,
        relation_rows: list[dict[str, Any]],
        authority_by_symbol: dict[str, str],
    ) -> dict[str, int]:
        fates = Counter()
        for row in relation_rows:
            if not isinstance(row, dict):
                continue
            root = str(row.get("symbol_anchor") or "")
            neighbor = str(row.get("neighbor_symbol_anchor") or "")
            observations = int(row.get("observations", 0) or 0)
            if observations <= 0:
                continue
            root_authority = authority_by_symbol.get(root, "unresolved")
            neighbor_authority = authority_by_symbol.get(neighbor, "unresolved")
            if root_authority == "canonical" and neighbor_authority == "canonical":
                fates["canonical_to_canonical"] += observations
            elif "unresolved" in {root_authority, neighbor_authority}:
                fates["unresolved_relation"] += observations
            elif "source_local" in {root_authority, neighbor_authority}:
                fates["source_local_relation"] += observations
            else:
                fates["other_relation"] += observations
        return dict(sorted(fates.items()))

    def counts_status(self) -> dict[str, Any]:
        cells_root = self.symbol_counts_binary_dir / "cells"
        cell_paths = list(cells_root.glob("*/*.cell")) if cells_root.exists() else []
        stream_path = self.symbol_streams_dir / "source_local_symbol_counts.awss"
        return {
            "runtime": "awsc_v1_1_binary_cells",
            "binary_counts_root": str(self.symbol_counts_binary_dir),
            "symbol_stream_path": str(stream_path),
            "symbol_stream_exists": stream_path.exists(),
            "cell_count": len(cell_paths),
            "legacy_json_counts_removed": True,
            "ingest_events": 0,
            "unique_relations": 0,
            "total_relation_observations": 0,
            "anchor_count": len(cell_paths),
            "relation_rows": 0,
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

    def symbolic_map_files(self) -> dict[str, Any]:
        files: list[dict[str, Any]] = []
        symbolic_paths = sorted(self.symbolic_maps_dir.glob("*.awsm"), key=lambda item: item.stat().st_mtime, reverse=True)
        for path in symbolic_paths:
            stat = path.stat()
            locator_path = path.with_suffix(".locators.awsl")
            null_path = path.with_suffix(".nulls.awsn")
            visual_path = path.with_suffix(".visuals.awsv")
            files.append({
                "name": path.name,
                "path": str(path),
                "modified": stat.st_mtime,
                "size_bytes": stat.st_size,
                "locator_name": locator_path.name if locator_path.exists() else "",
                "locator_path": str(locator_path) if locator_path.exists() else "",
                "null_name": null_path.name if null_path.exists() else "",
                "null_path": str(null_path) if null_path.exists() else "",
                "visual_name": visual_path.name if visual_path.exists() else "",
                "visual_path": str(visual_path) if visual_path.exists() else "",
                "sidecars": {
                    "locators": locator_path.exists(),
                    "nulls": null_path.exists(),
                    "visuals": visual_path.exists(),
                },
            })
        return {
            "ok": True,
            "schema_version": "anchorworks_symbolic_map_inventory@1",
            "source_format": "awsm_bundle",
            "root": str(self.symbolic_maps_dir),
            "map_count": len(symbolic_paths),
            "locator_sidecar_count": len(list(self.symbolic_maps_dir.glob("*.locators.awsl"))),
            "null_sidecar_count": len(list(self.symbolic_maps_dir.glob("*.nulls.awsn"))),
            "visual_sidecar_count": len(list(self.symbolic_maps_dir.glob("*.visuals.awsv"))),
            "json_role": "witness_debug_only",
            "files": files,
            "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
        }

    def binary_substrate_status(self) -> dict[str, Any]:
        stream_path = self.symbol_streams_dir / "source_local_symbol_counts.awss"
        cells_root = self.symbol_counts_binary_dir / "cells"
        cell_count = sum(1 for _ in cells_root.glob("*/*.cell")) if cells_root.exists() else 0
        symbolic_inventory = self.symbolic_map_files()
        return {
            "ok": True,
            "schema_version": "anchorworks_binary_substrate_status@1",
            "anchor_maps_root": str(self.anchor_maps_root),
            "observed_maps_root": str(self.observed_maps_dir),
            "symbolic_maps_root": str(self.symbolic_maps_dir),
            "json_observed_map_count": len(list(self.observed_maps_dir.glob("*.observed.json"))),
            "json_role": "witness_debug_only",
            "awsm_map_count": symbolic_inventory["map_count"],
            "awsl_locator_count": symbolic_inventory["locator_sidecar_count"],
            "awsn_null_count": symbolic_inventory["null_sidecar_count"],
            "awsv_visual_count": symbolic_inventory["visual_sidecar_count"],
            "awss_stream_path": str(stream_path),
            "awss_stream_exists": stream_path.exists(),
            "awss_stream_size_bytes": stream_path.stat().st_size if stream_path.exists() else 0,
            "awsc_cells_root": str(cells_root),
            "awsc_cell_count": cell_count,
            "runtime_law": "AWSM serves; JSON witnesses; AWSC counts.",
        }

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
            "local_overlay_root": str(self.flat_documents_local_overlays_dir),
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

    def load_local_overlay_for_symbolic_document(self, saved_document_name: str) -> dict[str, Any] | None:
        clean = str(saved_document_name or "").strip()
        suffix = ".symbolic.json"
        if not clean.endswith(suffix):
            return None
        overlay_name = clean[: -len(suffix)] + ".local_overlay.awlo.json"
        overlay_path = (self.flat_documents_local_overlays_dir / overlay_name).resolve()
        if overlay_path.parent != self.flat_documents_local_overlays_dir.resolve():
            return None
        if not overlay_path.exists() or not overlay_path.is_file():
            return None
        return load_local_meta_count_overlay(overlay_path)

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
        local_overlay_path = self.flat_documents_local_overlays_dir / f"{stem}.local_overlay.awlo.json"

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
        local_overlay = build_local_meta_count_overlay(
            source_id,
            symbolic,
            block_index_path,
            observed_map_debug=path.name,
        )
        self._write_json(local_overlay_path, local_overlay)

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
            "local_overlay_path": str(local_overlay_path),
            "block_count": len(block_rows),
            "occurrence_count": len(occurrence_rows),
            "visual_link_count": len(visual_link_rows),
            "local_overlay_relation_count": len(local_overlay["local_relation_counts"]),
            "writes_allowed": symbolic["writes_allowed"],
        }

    def build_source_local_symbol_counts(self, observed_map_name: str) -> dict[str, Any]:
        symbolic_path = self._resolve_symbolic_map_name(observed_map_name)
        if symbolic_path.exists():
            return self._build_source_local_symbol_counts_from_awsm(symbolic_path)

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
        target = self.source_local_symbol_counts_dir / f"{stem}.symbol_counts.json"

        paragraphs = [row for row in payload.get("paragraphs") or [] if isinstance(row, dict)]
        anchors: list[str] = []
        for paragraph in paragraphs:
            anchors.extend(str(anchor) for anchor in (paragraph.get("resolved_anchors") or paragraph.get("anchors") or []) if str(anchor))

        symbol_by_anchor, symbol_authority = build_source_local_symbol_table(
            anchors,
            canonical_symbol_by_anchor=self._canonical_symbol_by_anchor(),
            source_id=source_id,
        )
        relation_rows = build_symbol_relation_rows(
            paragraphs,
            symbol_by_anchor=symbol_by_anchor,
            window_radius=int(payload.get("window_radius", DEFAULT_WINDOW_RADIUS) or DEFAULT_WINDOW_RADIUS),
        )
        authority_by_symbol = {
            str(row.get("symbol") or ""): str(row.get("authority") or "")
            for row in symbol_authority
        }
        for row in relation_rows:
            row["lane"] = 4 if authority_by_symbol.get(str(row.get("neighbor_symbol_anchor") or "")) == "source_local" else 0
            row["flags"] = 0
        source_local_symbols = sum(1 for row in symbol_authority if row.get("authority") == "source_local")
        canonical_symbols = sum(1 for row in symbol_authority if row.get("authority") == "canonical")
        relation_fates = self._symbol_relation_fates_from_symbol_rows(relation_rows, authority_by_symbol)
        out = {
            "schema_version": "anchorworks_source_local_symbol_counts@1",
            "saved_at": _utc_now(),
            "source_id": source_id,
            "source_name": source_name,
            "source_path": source_path,
            "source_hash": source_hash,
            "source_format": "observed_json",
            "observed_map_name": path.name,
            "observed_map_path": str(path),
            "window_radius": int(payload.get("window_radius", DEFAULT_WINDOW_RADIUS) or DEFAULT_WINDOW_RADIUS),
            "symbol_authority": symbol_authority,
            "canonical_symbol_count": canonical_symbols,
            "source_local_symbol_count": source_local_symbols,
            "relation_fates": relation_fates,
            "symbol_relation_counts": relation_rows,
            "unique_symbol_relations": len(relation_rows),
            "total_symbol_relation_observations": int(sum(row["observations"] for row in relation_rows)),
            "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
        }
        self._write_json(target, out)
        return {
            "ok": True,
            "source_id": source_id,
            "source_name": source_name,
            "source_path": source_path,
            "source_format": "observed_json",
            "observed_map_name": path.name,
            "symbol_counts_name": target.name,
            "symbol_counts_path": str(target),
            "canonical_symbol_count": canonical_symbols,
            "source_local_symbol_count": source_local_symbols,
            "relation_fates": relation_fates,
            "unique_symbol_relations": len(relation_rows),
            "total_symbol_relation_observations": out["total_symbol_relation_observations"],
            "writes_allowed": out["writes_allowed"],
        }

    def _build_source_local_symbol_counts_from_awsm(self, symbolic_path: Path) -> dict[str, Any]:
        symbolic = read_symbolic_map_binary(symbolic_path)
        metadata = symbolic.metadata
        symbol_authority = [row for row in metadata.get("symbol_authority") or [] if isinstance(row, dict)]
        if not symbol_authority:
            raise ValueError(f"symbolic map lacks symbol authority table: {symbolic_path.name}")

        source_name = str(metadata.get("source_name") or "document")
        source_path = str(metadata.get("source_path") or "")
        source_hash = str(metadata.get("source_hash") or hashlib.sha256(source_path.encode("utf-8")).hexdigest())
        observed_map_name = str(metadata.get("observed_map_name") or (symbolic_path.stem + ".observed.json"))
        source_id = str(
            metadata.get("source_id")
            or hashlib.sha1((source_path + "\n" + source_hash + "\n" + observed_map_name).encode("utf-8")).hexdigest()
        )
        stem = self._flat_runtime_stem(source_name, source_id)
        target = self.source_local_symbol_counts_dir / f"{stem}.symbol_counts.json"

        authority_by_symbol = {
            str(row.get("symbol") or ""): str(row.get("authority") or "")
            for row in symbol_authority
        }
        relation_rows: list[dict[str, Any]] = []
        for row in symbolic.relations:
            root_display = f"0x{row.root_symbol_id:010X}"
            neighbor_display = f"0x{row.neighbor_symbol_id:010X}"
            observations = int(row.count)
            if observations <= 0:
                continue
            relation_rows.append({
                "symbol_id": int(row.root_symbol_id),
                "symbol_anchor": root_display,
                "offset": f"+{row.offset}" if row.offset > 0 else str(row.offset),
                "neighbor_symbol_id": int(row.neighbor_symbol_id),
                "neighbor_symbol_anchor": neighbor_display,
                "observations": observations,
                "lane": int(row.lane),
                "flags": int(row.flags),
            })

        canonical_symbols = sum(1 for row in symbol_authority if row.get("authority") == "canonical")
        source_local_symbols = sum(1 for row in symbol_authority if row.get("authority") == "source_local")
        relation_fates = self._symbol_relation_fates_from_symbol_rows(relation_rows, authority_by_symbol)
        out = {
            "schema_version": "anchorworks_source_local_symbol_counts@1",
            "saved_at": _utc_now(),
            "source_id": source_id,
            "source_name": source_name,
            "source_path": source_path,
            "source_hash": source_hash,
            "source_format": "awsm",
            "observed_map_name": observed_map_name,
            "symbolic_map_name": symbolic_path.name,
            "symbolic_map_path": str(symbolic_path),
            "window_radius": int(metadata.get("window_radius", DEFAULT_WINDOW_RADIUS) or DEFAULT_WINDOW_RADIUS),
            "symbol_authority": symbol_authority,
            "canonical_symbol_count": canonical_symbols,
            "source_local_symbol_count": source_local_symbols,
            "relation_fates": relation_fates,
            "symbol_relation_counts": relation_rows,
            "unique_symbol_relations": len(relation_rows),
            "total_symbol_relation_observations": int(sum(row["observations"] for row in relation_rows)),
            "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
        }
        self._write_json(target, out)
        return {
            "ok": True,
            "source_id": source_id,
            "source_name": source_name,
            "source_path": source_path,
            "source_format": "awsm",
            "observed_map_name": observed_map_name,
            "symbolic_map_name": symbolic_path.name,
            "symbol_counts_name": target.name,
            "symbol_counts_path": str(target),
            "canonical_symbol_count": canonical_symbols,
            "source_local_symbol_count": source_local_symbols,
            "relation_fates": out["relation_fates"],
            "unique_symbol_relations": len(relation_rows),
            "total_symbol_relation_observations": out["total_symbol_relation_observations"],
            "writes_allowed": out["writes_allowed"],
        }

    def load_symbolic_map_bundle(self, name: str) -> dict[str, Any]:
        symbolic_path = self._resolve_symbolic_map_name(name)
        if not symbolic_path.exists():
            raise FileNotFoundError(name)
        bundle = read_symbolic_map_bundle(symbolic_path)
        return {
            "ok": True,
            "schema_version": "anchorworks_symbolic_map_bundle@1",
            "source_format": "awsm_bundle",
            "symbolic_map_name": symbolic_path.name,
            "symbolic_map_path": str(symbolic_path),
            "metadata": bundle.map.metadata,
            "relation_count": bundle.map.relation_count,
            "relations": [
                {
                    "root_symbol_id": row.root_symbol_id,
                    "neighbor_symbol_id": row.neighbor_symbol_id,
                    "offset": row.offset,
                    "lane": row.lane,
                    "flags": row.flags,
                    "count": row.count,
                }
                for row in bundle.map.relations
            ],
            "locator_count": len(bundle.locators),
            "locators": bundle.locators,
            "null_count": len(bundle.nulls),
            "nulls": bundle.nulls,
            "visual_count": len(bundle.visuals),
            "visuals": bundle.visuals,
            "paths": bundle.paths,
            "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
        }

    def build_binary_symbol_counts_from_source_local(
        self,
        *,
        limit: int | None = None,
        generation: int = 0,
        artifact_names: list[str] | None = None,
    ) -> dict[str, Any]:
        if artifact_names is None:
            artifact_paths = sorted(self.source_local_symbol_counts_dir.glob("*.symbol_counts.json"))
        else:
            artifact_paths = []
            root = self.source_local_symbol_counts_dir.resolve()
            for name in artifact_names:
                target = (self.source_local_symbol_counts_dir / Path(name).name).resolve()
                if target.parent != root:
                    raise FileNotFoundError(name)
                artifact_paths.append(target)
            artifact_paths = sorted(artifact_paths, key=lambda item: item.name.lower())
        if limit is not None:
            artifact_paths = artifact_paths[: max(0, int(limit))]
        if not artifact_paths:
            raise FileNotFoundError("no source-local symbol count artifacts found")
        missing = [str(path) for path in artifact_paths if not path.exists()]
        if missing:
            raise FileNotFoundError(f"missing source-local symbol count artifacts: {missing[:3]}")
        stream_path = self.symbol_streams_dir / "source_local_symbol_counts.awss"
        stream = write_awss_from_symbol_count_artifacts(artifact_paths, stream_path)
        merge = merge_symbol_stream(
            stream_path,
            self.symbol_counts_binary_dir,
            generation=int(generation),
        )
        verify = verify_binary_counts(self.symbol_counts_binary_dir)
        return {
            "ok": bool(merge.get("ok")) and bool(verify.get("ok")),
            "schema_version": "anchorworks_binary_symbol_counts_build@1",
            "artifact_count": len(artifact_paths),
            "stream_path": str(stream_path),
            "stream_record_count": int(stream.get("record_count", 0) or 0),
            "stream_observation_count": int(stream.get("observation_count", 0) or 0),
            "stream_size_bytes": stream_path.stat().st_size if stream_path.exists() else 0,
            "binary_counts_root": str(self.symbol_counts_binary_dir),
            "verify": verify,
            "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
        }

    def build_symbolic_intake_batch(
        self,
        source_paths: list[str | Path],
        *,
        max_workers: int | None = None,
        generation: int = 0,
        null_anchors: set[str] | None = None,
    ) -> dict[str, Any]:
        normalized_paths = [Path(path).expanduser().resolve() for path in source_paths]
        if not normalized_paths:
            raise ValueError("at least one source path is required")
        for path in normalized_paths:
            if not path.exists():
                raise FileNotFoundError(path)
            if not path.is_file():
                raise IsADirectoryError(path)

        groups: dict[str, list[Path]] = {}
        for path in normalized_paths:
            groups.setdefault(str(path.parent), []).append(path)

        worker_count = max(1, min(int(max_workers or (os.cpu_count() or 1)), len(normalized_paths)))
        worker_args = [
            (str(self.root), str(path), "binary_source_local", sorted(null_anchors or set()))
            for group_name in sorted(groups)
            for path in sorted(groups[group_name], key=lambda item: item.name.lower())
        ]

        map_results: list[dict[str, Any]] = []
        if worker_count == 1:
            map_results = [_build_observed_map_worker(args) for args in worker_args]
        else:
            with ProcessPoolExecutor(max_workers=worker_count) as executor:
                future_by_path = {executor.submit(_build_observed_map_worker, args): args[1] for args in worker_args}
                for future in as_completed(future_by_path):
                    map_results.append(future.result())
            map_results.sort(key=lambda row: str(row.get("source_path") or "").lower())

        symbol_artifacts = [
            self.build_source_local_symbol_counts(str(row["saved_map_name"]))
            for row in map_results
        ]
        binary = self.build_binary_symbol_counts_from_source_local(
            generation=generation,
            artifact_names=[str(row["symbol_counts_name"]) for row in symbol_artifacts],
        )
        return {
            "ok": bool(binary.get("ok")),
            "schema_version": "anchorworks_symbolic_intake_batch@1",
            "source_count": len(normalized_paths),
            "group_count": len(groups),
            "groups": [
                {"group": group, "source_count": len(paths)}
                for group, paths in sorted(groups.items())
            ],
            "max_workers_used": worker_count,
            "map_root": str(self.observed_maps_dir),
            "map_count": len(map_results),
            "maps": map_results,
            "symbol_artifact_count": len(symbol_artifacts),
            "symbol_artifacts": symbol_artifacts,
            "binary": binary,
            "writes_allowed": {"maps": True, "counts": False, "lifetime": False, "lexicon": False},
        }

    def build_symbolic_intake_batch_chunked(
        self,
        source_paths: list[str | Path],
        *,
        max_workers: int | None = None,
        generation: int = 0,
        null_anchors: set[str] | None = None,
        run_id: str | None = None,
        chunk_file_limit: int = 250,
        soft_warning_gb: float = 32.0,
        emergency_flush_gb: float = 36.0,
        abort_gb: float = 39.0,
        write_chunk_binaries: bool = True,
    ) -> dict[str, Any]:
        normalized_paths = [Path(path).expanduser().resolve() for path in source_paths]
        if not normalized_paths:
            raise ValueError("at least one source path is required")
        for path in normalized_paths:
            if not path.exists():
                raise FileNotFoundError(path)
            if not path.is_file():
                raise IsADirectoryError(path)

        safe_run_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(run_id or f"chunked_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}")).strip("._") or "chunked"
        run_root = self.ingest_staging_dir / "chunked_symbolic_intake" / safe_run_id
        chunks_root = run_root / "chunks"
        chunk_binary_root = self.state_dir / "symbol_counts_binary_chunks" / safe_run_id
        run_root.mkdir(parents=True, exist_ok=True)
        chunks_root.mkdir(parents=True, exist_ok=True)
        if write_chunk_binaries:
            chunk_binary_root.mkdir(parents=True, exist_ok=True)

        file_limit = max(1, int(chunk_file_limit))
        worker_count = max(1, int(max_workers or (os.cpu_count() or 1)))
        chunks = [
            normalized_paths[index : index + file_limit]
            for index in range(0, len(normalized_paths), file_limit)
        ]
        manifest_path = run_root / "manifest.json"
        stop_path = run_root / "STOP"
        started = time.perf_counter()
        chunk_rows: list[dict[str, Any]] = []
        failed_files: list[dict[str, Any]] = []
        stopped_reason = ""
        completed_chunk_ids: set[str] = set()
        if manifest_path.exists():
            try:
                existing = json.loads(manifest_path.read_text(encoding="utf-8"))
                for row in existing.get("chunks") or []:
                    if not isinstance(row, dict):
                        continue
                    chunk_id = str(row.get("chunk_id") or "")
                    if chunk_id and int(row.get("files_failed", 0) or 0) == 0:
                        completed_chunk_ids.add(chunk_id)
                        chunk_rows.append(row)
                for error in existing.get("failed_files") or []:
                    if isinstance(error, dict):
                        failed_files.append(error)
            except Exception:
                completed_chunk_ids = set()
                chunk_rows = []
                failed_files = []

        for chunk_index, chunk_paths in enumerate(chunks, start=1):
            chunk_id = f"chunk_{chunk_index:04d}"
            if stop_path.exists():
                stopped_reason = "stop_requested_before_chunk"
                break
            if chunk_id in completed_chunk_ids:
                continue
            chunk_started = time.perf_counter()
            rss_start = _current_process_rss_bytes()
            chunk_manifest_path = chunks_root / f"{chunk_id}.json"
            chunk_workers = max(1, min(worker_count, len(chunk_paths)))
            worker_args = [
                (str(self.root), str(path), "binary_source_local", sorted(null_anchors or set()))
                for path in chunk_paths
            ]

            map_results: list[dict[str, Any]] = []
            map_errors: list[dict[str, Any]] = []
            if chunk_workers == 1:
                for args in worker_args:
                    try:
                        map_results.append(_build_observed_map_worker(args))
                    except Exception as exc:
                        error = {"source_path": args[1], "stage": "map", "error": str(exc)}
                        map_errors.append(error)
                        failed_files.append(error)
            else:
                with ProcessPoolExecutor(max_workers=chunk_workers) as executor:
                    future_by_path = {executor.submit(_build_observed_map_worker, args): args[1] for args in worker_args}
                    for future in as_completed(future_by_path):
                        source_path = future_by_path[future]
                        try:
                            map_results.append(future.result())
                        except Exception as exc:
                            error = {"source_path": source_path, "stage": "map", "error": str(exc)}
                            map_errors.append(error)
                            failed_files.append(error)
                map_results.sort(key=lambda row: str(row.get("source_path") or "").lower())

            symbol_artifacts: list[dict[str, Any]] = []
            symbol_errors: list[dict[str, Any]] = []
            for row in map_results:
                try:
                    symbol_artifacts.append(self.build_source_local_symbol_counts(str(row["saved_map_name"])))
                except Exception as exc:
                    error = {
                        "source_path": str(row.get("source_path") or ""),
                        "observed_map_name": str(row.get("saved_map_name") or ""),
                        "stage": "source_local_symbol_counts",
                        "error": str(exc),
                    }
                    symbol_errors.append(error)
                    failed_files.append(error)

            binary: dict[str, Any] | None = None
            binary_error = ""
            if write_chunk_binaries and symbol_artifacts:
                try:
                    artifact_paths = [self.source_local_symbol_counts_dir / str(row["symbol_counts_name"]) for row in symbol_artifacts]
                    stream_path = run_root / "symbol_streams" / f"{chunk_id}.awss"
                    stream = write_awss_from_symbol_count_artifacts(artifact_paths, stream_path)
                    output_root = chunk_binary_root / chunk_id
                    merge = merge_symbol_stream(stream_path, output_root, generation=int(generation))
                    verify = verify_binary_counts(output_root)
                    binary = {
                        "ok": bool(merge.get("ok")) and bool(verify.get("ok")),
                        "stream_path": str(stream_path),
                        "stream_record_count": int(stream.get("record_count", 0) or 0),
                        "stream_observation_count": int(stream.get("observation_count", 0) or 0),
                        "stream_size_bytes": stream_path.stat().st_size if stream_path.exists() else 0,
                        "binary_counts_root": str(output_root),
                        "verify": verify,
                    }
                except Exception as exc:
                    binary_error = str(exc)

            del worker_args
            gc.collect()
            rss_end = _current_process_rss_bytes()
            peak_rss = max(rss_start, rss_end)
            elapsed = time.perf_counter() - chunk_started
            chunk_row = {
                "chunk_id": chunk_id,
                "source_count": len(chunk_paths),
                "files_ok": len(symbol_artifacts),
                "files_failed": len(map_errors) + len(symbol_errors),
                "source_paths": [str(path) for path in chunk_paths],
                "map_count": len(map_results),
                "maps": [
                    {
                        "source_path": str(row.get("source_path") or ""),
                        "saved_map_name": str(row.get("saved_map_name") or ""),
                        "symbolic_map_name": str(row.get("symbolic_map_name") or ""),
                    }
                    for row in map_results
                ],
                "symbol_artifact_count": len(symbol_artifacts),
                "symbol_artifacts": [
                    {
                        "source_path": str(row.get("source_path") or ""),
                        "symbol_counts_name": str(row.get("symbol_counts_name") or ""),
                        "unique_symbol_relations": int(row.get("unique_symbol_relations", 0) or 0),
                        "total_symbol_relation_observations": int(row.get("total_symbol_relation_observations", 0) or 0),
                    }
                    for row in symbol_artifacts
                ],
                "binary": binary,
                "binary_error": binary_error,
                "errors": map_errors + symbol_errors,
                "elapsed_seconds": round(elapsed, 6),
                "rss_start_bytes": rss_start,
                "rss_end_bytes": rss_end,
                "peak_rss_bytes": peak_rss,
                "memory_status": _memory_status(peak_rss, soft_warning_gb, emergency_flush_gb, abort_gb),
            }
            chunk_manifest_path.write_text(json.dumps(chunk_row, indent=2, ensure_ascii=False), encoding="utf-8")
            chunk_rows.append(chunk_row)

            manifest = {
                "schema_version": "anchorworks_chunked_symbolic_intake_run@1",
                "run_id": safe_run_id,
                "status": "running",
                "source_count": len(normalized_paths),
                "chunk_count": len(chunks),
                "completed_chunks": len(chunk_rows),
                "chunk_file_limit": file_limit,
                "memory_budget": {
                    "soft_warning_gb": soft_warning_gb,
                    "emergency_flush_gb": emergency_flush_gb,
                    "abort_gb": abort_gb,
                },
                "chunk_binary_root": str(chunk_binary_root) if write_chunk_binaries else "",
                "chunks": chunk_rows,
                "failed_files": failed_files,
                "writes_allowed": {"maps": True, "counts": False, "lifetime": False, "lexicon": False},
            }
            manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
            if peak_rss >= int(float(abort_gb) * 1024 * 1024 * 1024):
                stopped_reason = "abort_gb_reached_after_safe_chunk_flush"
                break
            if stop_path.exists():
                stopped_reason = "stop_requested_after_safe_chunk_flush"
                break

        total_elapsed = time.perf_counter() - started
        ok = not stopped_reason and not failed_files and all((row.get("binary") or {}).get("ok", True) for row in chunk_rows)
        final = {
            "schema_version": "anchorworks_chunked_symbolic_intake_run@1",
            "run_id": safe_run_id,
            "status": "stopped" if stopped_reason else "completed",
            "ok": bool(ok),
            "stopped_reason": stopped_reason,
            "source_count": len(normalized_paths),
            "chunk_count": len(chunks),
            "completed_chunks": len(chunk_rows),
            "files_ok": sum(int(row.get("files_ok", 0) or 0) for row in chunk_rows),
            "files_failed": len(failed_files),
            "manifest_path": str(manifest_path),
            "run_root": str(run_root),
            "map_root": str(self.observed_maps_dir),
            "source_local_symbol_counts_root": str(self.source_local_symbol_counts_dir),
            "chunk_binary_root": str(chunk_binary_root) if write_chunk_binaries else "",
            "elapsed_seconds": round(total_elapsed, 6),
            "chunks": chunk_rows,
            "failed_files": failed_files,
            "writes_allowed": {"maps": True, "counts": False, "lifetime": False, "lexicon": False},
        }
        manifest_path.write_text(json.dumps(final, indent=2, ensure_ascii=False), encoding="utf-8")
        return final

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
                anchor_rows = extract_anchor_rows(text)
                ordered_text_anchors = [
                    self.normalize_anchor(row["anchor"])
                    for row in anchor_rows
                    if self.normalize_anchor(row["anchor"])
                ]
                text_anchors = set(ordered_text_anchors)
                hits = sorted((query_set | query_anchor_set) & (block_anchors | text_anchors))
                if not hits:
                    continue
                anchor_count = max(1, len(block_anchors | text_anchors))
                score = float(len(hits) * 100 + len(hits) / anchor_count)
                proximity_span = _query_proximity_span(ordered_text_anchors, list(query_anchor_set or query_set))
                if proximity_span is not None:
                    score += max(0.0, 90.0 - float(proximity_span * 12))
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
                    "text": _query_centered_snippet(text, anchor_rows, list(query_anchor_set or query_set)) or text.strip(),
                    "raw_block_text": text.strip(),
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

    def build_observed_map(
        self,
        source_path: Path,
        *,
        count_target: str = "binary_source_local",
        null_anchors: set[str] | None = None,
    ) -> dict[str, Any]:
        source_path = Path(source_path).expanduser().resolve()
        if not source_path.exists():
            raise FileNotFoundError(source_path)
        if source_path.is_dir():
            raise IsADirectoryError(source_path)

        map_path = self._observed_map_path(source_path)
        symbolic_map_path = self._symbolic_map_path(source_path)
        symbolic_locator_path = self._symbolic_locator_path(source_path)
        symbolic_null_path = self._symbolic_null_path(source_path)
        symbolic_visual_path = self._symbolic_visual_path(source_path)
        observed_map_name = map_path.name
        prepared = prepare_file(source_path)
        source_id = hashlib.sha1((str(source_path) + "\n" + prepared.sha256 + "\n" + observed_map_name).encode("utf-8")).hexdigest()
        if isinstance(prepared.metadata, dict) and prepared.metadata.get("visual_manifest"):
            raise ValueError("visual intake preview is source-local evidence only; use a future visual approval route before mapping/counting")
        text = prepared.prepared_text
        inventory = self._extract_document_anchor_inventory(text)
        observed_counts: Counter[str] = inventory["observed_counts"]
        known_anchors = set(self._all_known_anchors())
        null_anchor_set = {self.normalize_anchor(anchor) for anchor in (null_anchors or set()) if self.normalize_anchor(anchor)}
        unique_anchors = sorted(observed_counts)

        resolution_map: dict[str, str] = {anchor: anchor for anchor in unique_anchors if anchor in known_anchors}
        for anchor in null_anchor_set:
            if anchor in observed_counts:
                resolution_map[anchor] = NULL_ANCHOR
        raw_missing_counts: Counter[str] = Counter({
            anchor: count for anchor, count in observed_counts.items() if anchor not in known_anchors and anchor not in null_anchor_set
        })
        classified_missing = classify_unknown_anchor_rows(self._anchor_rows(raw_missing_counts))
        companion_counts: Counter[str] = Counter()
        classified_null_counts: Counter[str] = Counter()
        missing_counts: Counter[str] = Counter()
        for lane, rows in (classified_missing.get("lanes") or {}).items():
            for row in rows:
                anchor = self.normalize_anchor(str(row.get("anchor") or ""))
                if not anchor:
                    continue
                observations = int(row.get("observations", 0) or 0)
                if lane in COMPANION_AUTHORITY_LANES:
                    companion_counts[anchor] += observations
                    resolution_map[anchor] = anchor
                elif lane in NULL_SYMBOL_LANES:
                    classified_null_counts[anchor] += observations
                    null_anchor_set.add(anchor)
                    resolution_map[anchor] = NULL_ANCHOR
                else:
                    missing_counts[anchor] += observations

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
            null_anchors=null_anchor_set,
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
        null_index = self._null_occurrence_index(mapping["occurrences"])
        resolved_counts: Counter[str] = mapping["observed_counts"]
        known_counts: Counter[str] = Counter({
            anchor: count for anchor, count in observed_counts.items() if anchor in known_anchors
        })
        temp_symbols_present = bool(temp_entries)
        source_local_only_present = temp_symbols_present or bool(companion_counts) or bool(null_anchor_set)
        symbolic_anchors: list[str] = []
        for paragraph in mapping["paragraphs"]:
            symbolic_anchors.extend(str(anchor) for anchor in paragraph.get("resolved_anchors", []) if str(anchor))
        symbol_by_anchor, symbol_authority = build_source_local_symbol_table(
            symbolic_anchors,
            canonical_symbol_by_anchor=self._canonical_symbol_by_anchor(),
            source_id=source_id,
        )
        authority_by_symbol = {
            str(row.get("symbol") or ""): str(row.get("authority") or "")
            for row in symbol_authority
            if isinstance(row, dict)
        }
        symbolic_relation_rows = build_symbol_relation_rows(
            mapping["paragraphs"],
            symbol_by_anchor=symbol_by_anchor,
            window_radius=DEFAULT_WINDOW_RADIUS,
        )
        if count_target not in {"binary_source_local", "user_chat_preview"}:
            raise ValueError("legacy JSON count targets are removed on the binary spine branch")
        count_write = {
            "count_target": count_target,
            "count_paths": [],
            "lifetime_write_skipped": True,
            "legacy_json_counts_removed": True,
            "binary_counts_required": True,
            "reason": "observed_map_only_binary_symbol_counts_post_step_required",
        }

        observed_rows = [
            {
                "anchor": anchor,
                "observations": count,
                "known": anchor in known_anchors,
                "resolved_to": resolution_map.get(anchor, anchor),
                "null_mapped": anchor in null_anchor_set,
            }
            for anchor, count in sorted(observed_counts.items(), key=lambda item: (-item[1], item[0]))
        ]

        temp_lexicon_path: Path | None = None
        if source_local_only_present:
            temp_lexicon_path = self._temp_lexicon_path(source_path)
            self._write_json(temp_lexicon_path, {
                "saved_at": _utc_now(),
                "source_path": str(source_path),
                "source_name": source_path.name,
                "temp_symbol_version": TEMP_SYMBOL_VERSION,
                "authority": "source_local_coordinate",
                "entries": temp_entries,
                "companion_authority_anchors": self._anchor_rows(companion_counts),
                "null_anchors": self._anchor_rows(Counter({
                    anchor: observed_counts[anchor]
                    for anchor in null_anchor_set
                    if anchor in observed_counts
                })),
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
            "companion_anchor_count": len(companion_counts),
            "missing_anchor_count": len(missing_counts),
            "null_anchor_count": len([anchor for anchor in null_anchor_set if anchor in observed_counts]),
            "null_occurrence_count": len(null_index),
            "known_anchor_observations": int(sum(known_counts.values())),
            "companion_anchor_observations": int(sum(companion_counts.values())),
            "missing_anchor_observations": int(sum(missing_counts.values())),
            "null_anchor_observations": int(sum(observed_counts.get(anchor, 0) for anchor in null_anchor_set)),
            "raw_missing_anchor_count": len(raw_missing_counts),
            "raw_missing_anchor_observations": int(sum(raw_missing_counts.values())),
            "paragraphs": mapping["paragraphs"],
            "paragraph_line_locators": {str(key): value for key, value in line_locators.items()},
            "occurrences": mapping["occurrences"],
            "null_index": null_index,
            "co_occurrence_counts": mapping["co_occurrence_counts"],
            "items": mapping["items"],
            "anchor_index": mapping["anchor_index"],
            "stats": mapping["stats"],
            "known_anchors": self._anchor_rows(known_counts),
            "companion_authority_anchors": self._anchor_rows(companion_counts),
            "missing_anchors": self._anchor_rows(missing_counts),
            "null_anchors": self._anchor_rows(Counter({
                anchor: observed_counts[anchor]
                for anchor in null_anchor_set
                if anchor in observed_counts
            })),
            "observed_anchors": observed_rows,
            "spell_corrections": corrections,
            "lexicon_additions": additions,
            "classified_missing_lanes": {
                "lane_counts": classified_missing.get("lane_counts", {}),
                "lane_observations": classified_missing.get("lane_observations", {}),
            },
            "temp_symbol_count": len(temp_entries),
            "temp_symbols": temp_entries,
            "temp_lexicon_path": str(temp_lexicon_path) if temp_lexicon_path else "",
            "document_prep": {
                key: value
                for key, value in prepared.to_dict().items()
                if key != "prepared_text"
            },
            "count_target": count_write["count_target"],
            "count_paths": count_write["count_paths"],
            "count_write": count_write,
        }

        locator_rows = [
            {
                "paragraph_id": int(paragraph.get("paragraph_id", 0) or 0),
                "block_id": int(paragraph.get("block_id", paragraph.get("paragraph_id", 0)) or 0),
                "line_start": int(paragraph.get("line_start", 0) or 0),
                "line_end": int(paragraph.get("line_end", paragraph.get("line_start", 0)) or paragraph.get("line_start", 0) or 0),
                "anchor_count": int(paragraph.get("anchor_count", len(paragraph.get("resolved_anchors") or paragraph.get("anchors") or [])) or 0),
                "countable_anchor_count": int(paragraph.get("countable_anchor_count", 0) or 0),
            }
            for paragraph in mapping["paragraphs"]
            if isinstance(paragraph, dict)
        ]
        visual_rows: list[dict[str, Any]] = []
        document_film = (prepared.metadata or {}).get("document_film") if isinstance(prepared.metadata, dict) else None
        if isinstance(document_film, dict):
            for frame in document_film.get("frames") or []:
                if not isinstance(frame, dict):
                    continue
                manifest = frame.get("visual_manifest") if isinstance(frame.get("visual_manifest"), dict) else {}
                source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
                page_number = int(frame.get("page_number") or source.get("page_number") or 0)
                frame_index = int(frame.get("frame_index") if frame.get("frame_index") is not None else source.get("frame_index", 0) or 0)
                visual_rows.append({
                    "block_id": f"page_{page_number}" if page_number else "",
                    "block_ordinal": page_number,
                    "line_start": page_number,
                    "line_end": page_number,
                    "visual_record_id": str(frame.get("visual_record_id") or source.get("visual_record_id") or ""),
                    "kind": "pdf_page_frame",
                    "source_path_ref": str(frame.get("source_path_ref") or ""),
                    "page_index": int(frame.get("page_index") if frame.get("page_index") is not None else source.get("page_index", -1) or -1),
                    "page_number": page_number,
                    "frame_index": frame_index,
                    "frame_timestamp_ms": int(frame.get("frame_timestamp_ms") if frame.get("frame_timestamp_ms") is not None else source.get("frame_timestamp_ms", 0) or 0),
                    "width": source.get("width", frame.get("width")),
                    "height": source.get("height", frame.get("height")),
                    "aspect_ratio": str(source.get("aspect_ratio") or frame.get("aspect_ratio") or "unknown"),
                    "file_format": str(source.get("file_format") or frame.get("file_format") or "unknown"),
                    "color_mode": str(source.get("color_mode") or frame.get("color_mode") or "unknown"),
                    "manifest_id": str(frame.get("visual_record_id") or source.get("visual_record_id") or ""),
                    "geometry_status": str(frame.get("geometry_status") or "known"),
                    "recognition_status": "not_run",
                    "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
                })
        for ref in (prepared.metadata or {}).get("visual_refs") or []:
            if isinstance(ref, dict) and str(ref.get("source_path") or ref.get("source_path_ref") or ref.get("visual_record_id") or "").strip():
                visual_rows.append({
                    "block_id": "",
                    "block_ordinal": 0,
                    "line_start": 0,
                    "line_end": 0,
                    **ref,
                })
        for paragraph in mapping["paragraphs"]:
            if not isinstance(paragraph, dict):
                continue
            paragraph_id = int(paragraph.get("paragraph_id", 0) or 0)
            for ref in paragraph.get("visual_refs") or []:
                if isinstance(ref, dict) and str(ref.get("visual_record_id") or ref.get("source_path") or ref.get("source_path_ref") or "").strip():
                    visual_rows.append({
                        "block_id": f"block_{paragraph_id}",
                        "block_ordinal": paragraph_id,
                        "line_start": int(paragraph.get("line_start", 0) or 0),
                        "line_end": int(paragraph.get("line_end", paragraph.get("line_start", 0)) or paragraph.get("line_start", 0) or 0),
                        **ref,
                    })

        write_symbolic_map_binary(
            symbolic_map_path,
            metadata={
                "schema_version": "anchorworks_symbolic_map_binary_metadata@1",
                "source_path": str(source_path),
                "source_name": source_path.name,
                "source_hash": prepared.sha256,
                "source_id": source_id,
                "observed_map_name": observed_map_name,
                "paragraph_count": mapping["paragraph_count"],
                "window_radius": mapping["window_radius"],
                "anchor_observations": int(sum(observed_counts.values())),
                "symbol_authority_count": len(symbol_authority),
                "symbol_authority": symbol_authority,
            },
            relations=[
                SymbolicMapRelation(
                    root_symbol_id=int(row["symbol_id"]),
                    neighbor_symbol_id=int(row["neighbor_symbol_id"]),
                    offset=int(str(row["offset"]).replace("+", "")),
                    lane=4 if authority_by_symbol.get(str(row["neighbor_symbol_anchor"])) == "source_local" else 0,
                    flags=0,
                    count=int(row["observations"]),
                )
                for row in symbolic_relation_rows
            ],
        )
        write_symbolic_map_locator_sidecar(symbolic_locator_path, locator_rows)
        write_symbolic_map_null_sidecar(symbolic_null_path, null_index)
        write_symbolic_map_visual_sidecar(symbolic_visual_path, visual_rows)
        payload["symbolic_map_path"] = str(symbolic_map_path)
        payload["symbolic_map_relation_count"] = len(symbolic_relation_rows)
        payload["symbolic_locator_path"] = str(symbolic_locator_path)
        payload["symbolic_locator_count"] = len(locator_rows)
        payload["symbolic_null_path"] = str(symbolic_null_path)
        payload["symbolic_null_count"] = len(null_index)
        payload["symbolic_visual_path"] = str(symbolic_visual_path)
        payload["symbolic_visual_count"] = len(visual_rows)
        self._write_json(map_path, payload)

        return {
            "ok": True,
            "source_path": str(source_path),
            "source_name": source_path.name,
            "saved_map_path": str(map_path),
            "saved_map_name": map_path.name,
            "symbolic_map_path": str(symbolic_map_path),
            "symbolic_map_name": symbolic_map_path.name,
            "symbolic_map_relation_count": len(symbolic_relation_rows),
            "symbolic_locator_path": str(symbolic_locator_path),
            "symbolic_locator_name": symbolic_locator_path.name,
            "symbolic_locator_count": len(locator_rows),
            "symbolic_null_path": str(symbolic_null_path),
            "symbolic_null_name": symbolic_null_path.name,
            "symbolic_null_count": len(null_index),
            "symbolic_visual_path": str(symbolic_visual_path),
            "symbolic_visual_name": symbolic_visual_path.name,
            "symbolic_visual_count": len(visual_rows),
            "paragraph_count": payload["paragraph_count"],
            "window_radius": payload["window_radius"],
            "total_anchor_observations": payload["total_anchor_observations"],
            "unique_anchor_count": payload["unique_anchor_count"],
            "known_anchor_count": payload["known_anchor_count"],
            "companion_anchor_count": payload["companion_anchor_count"],
            "missing_anchor_count": payload["missing_anchor_count"],
            "null_anchor_count": payload["null_anchor_count"],
            "null_occurrence_count": payload["null_occurrence_count"],
            "known_anchor_observations": payload["known_anchor_observations"],
            "companion_anchor_observations": payload["companion_anchor_observations"],
            "missing_anchor_observations": payload["missing_anchor_observations"],
            "null_anchor_observations": payload["null_anchor_observations"],
            "raw_missing_anchor_count": payload["raw_missing_anchor_count"],
            "raw_missing_anchor_observations": payload["raw_missing_anchor_observations"],
            "registered_missing_anchors": len(missing_counts),
            "known_anchors_preview": payload["known_anchors"][:25],
            "companion_authority_anchors_preview": payload["companion_authority_anchors"][:25],
            "missing_anchors_preview": payload["missing_anchors"][:25],
            "null_anchors": payload["null_anchors"],
            "null_anchors_preview": payload["null_anchors"][:25],
            "null_index_preview": payload["null_index"][:25],
            "classified_missing_lanes": payload["classified_missing_lanes"],
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

    def classify_missing_anchor_registry(self) -> dict[str, Any]:
        output_dir = self.state_dir / "ingest_staging" / "anchor_inventory" / "classified_unknown_lanes"
        result = write_classified_unknown_report(self._load_missing_anchor_registry(), output_dir)
        result["math_lexicon"] = write_math_lexicon(output_dir / "math_lexicon.json")
        return result

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


def _query_proximity_span(text_anchors: list[str], query_anchors: list[str]) -> int | None:
    wanted = [anchor for anchor in dict.fromkeys(query_anchors) if anchor]
    if len(wanted) < 2:
        return None
    positions: dict[str, list[int]] = {anchor: [] for anchor in wanted}
    for index, anchor in enumerate(text_anchors):
        if anchor in positions:
            positions[anchor].append(index)
    if any(not values for values in positions.values()):
        return None
    best: int | None = None
    for start_anchor in wanted:
        for start in positions[start_anchor]:
            window_positions = [start]
            for anchor in wanted:
                if anchor == start_anchor:
                    continue
                nearest = min(positions[anchor], key=lambda pos: abs(pos - start))
                window_positions.append(nearest)
            span = max(window_positions) - min(window_positions) + 1
            if best is None or span < best:
                best = span
    return best


def _query_centered_snippet(text: str, anchor_rows: list[dict[str, Any]], query_anchors: list[str], max_chars: int = 520) -> str:
    wanted = [anchor for anchor in dict.fromkeys(query_anchors) if anchor]
    if not text or not anchor_rows or not wanted:
        return ""
    positions: dict[str, list[int]] = {anchor: [] for anchor in wanted}
    for index, row in enumerate(anchor_rows):
        anchor = str(row.get("anchor") or "").strip().lower()
        if anchor in positions:
            positions[anchor].append(index)
    present = [anchor for anchor in wanted if positions.get(anchor)]
    if not present:
        return ""

    best_rows: list[int] = []
    if len(present) == len(wanted) and len(wanted) > 1:
        best_span: int | None = None
        for start_anchor in wanted:
            for start in positions[start_anchor]:
                row_indexes = [start]
                for anchor in wanted:
                    if anchor == start_anchor:
                        continue
                    nearest = min(positions[anchor], key=lambda pos: abs(pos - start))
                    row_indexes.append(nearest)
                span = max(row_indexes) - min(row_indexes) + 1
                if best_span is None or span < best_span:
                    best_span = span
                    best_rows = row_indexes
    else:
        best_rows = [positions[present[0]][0]]

    if not best_rows:
        return ""
    start_char = min(int(anchor_rows[index].get("start", 0) or 0) for index in best_rows)
    end_char = max(int(anchor_rows[index].get("end", 0) or 0) for index in best_rows)
    extra = max(80, int((max_chars - max(0, end_char - start_char)) / 2))
    left = max(0, start_char - extra)
    right = min(len(text), end_char + extra)
    snippet = " ".join(text[left:right].split())
    if not snippet:
        return ""
    if left > 0:
        snippet = "... " + snippet
    if right < len(text):
        snippet = snippet + " ..."
    return snippet
