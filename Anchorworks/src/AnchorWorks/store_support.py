from __future__ import annotations

import hashlib
import ctypes
import gc
import json
import logging
import os
import random
import re
import shutil
import threading
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .anchor_field import build_query_frame
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
from .phrase_lexicon import PhraseLexiconStore
from .phrase_candidates import (
    build_phrase_candidates_from_symbolic_dir,
    write_phrase_candidate_review,
    write_phrase_candidate_review_from_observed_maps,
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
from .symbol_genome_pool import SymbolGenomePool
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
CONVERSATIONAL_ANCHORS = {"hello", "hi", "hey", "thanks", "thank", "morning", "good", "yo"}
USER_LEXICON_SYMBOL_BASE = 0xE000000000
USER_LEXICON_SYMBOL_CAPACITY = 500_000_000
INFO_TRANSFER_ANCHORS = {
    "remember",
    "consider",
    "context",
    "note",
    "keep",
    "mind",
    "means",
    "meaning",
    "type",
    "flow",
    "rules",
    "engagement",
}
CORRECTION_ANCHORS = {"no", "not", "wrong", "correct", "correction", "actually", "instead"}
PLANNING_ANCHORS = {"plan", "next", "later", "tomorrow", "todo", "build", "need", "needs"}

def _anchor_maps_root_for(data_root: Path) -> Path:
    return anchor_maps_root_for(data_root)


def _query_input_kind(observed: list[str], query_frame: dict[str, Any]) -> str:
    frame = str(query_frame.get("frame") or "").strip().casefold()
    observed_set = {str(anchor or "").strip().casefold() for anchor in observed if str(anchor or "").strip()}
    if "?" in observed_set or frame in {"question", "method_question"}:
        return "question"
    if observed_set and observed_set <= CONVERSATIONAL_ANCHORS:
        return "conversation"
    if observed_set & CONVERSATIONAL_ANCHORS and len(observed_set) <= 3:
        return "conversation"
    if _is_correction_input(observed_set):
        return "correction"
    if _is_planning_input(observed_set):
        return "planning_note"
    if _is_info_transfer_input(observed_set):
        return "info_transfer"
    return "statement"


def _is_correction_input(observed_set: set[str]) -> bool:
    if not observed_set:
        return False
    if {"not", "correct"} <= observed_set:
        return True
    if {"wrong"} & observed_set:
        return True
    if "actually" in observed_set and len(observed_set) >= 3:
        return True
    return False


def _is_planning_input(observed_set: set[str]) -> bool:
    if not observed_set:
        return False
    if "plan" in observed_set or "todo" in observed_set:
        return True
    if "next" in observed_set and (observed_set & {"build", "need", "needs", "later", "tomorrow"}):
        return True
    return False


def _is_info_transfer_input(observed_set: set[str]) -> bool:
    if not observed_set:
        return False
    if {"keep", "mind"} <= observed_set:
        return True
    if {"not", "everything", "question"} <= observed_set:
        return True
    if "remember" in observed_set or "consider" in observed_set:
        return True
    if len(observed_set & INFO_TRANSFER_ANCHORS) >= 2:
        return True
    return False


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
    from .store import LexiconStore

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


__all__ = [name for name in globals() if not name.startswith("__")]
