from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .symbolic_map_binary import read_symbolic_map_bundle


PHRASE_CANDIDATE_SCHEMA_VERSION = "anchorworks_phrase_candidates@1"
PHRASE_CANDIDATE_ROW_VERSION = "anchorworks_phrase_candidate@1"

_GLUE_ANCHORS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
}


def build_phrase_candidates_from_symbolic_docs(
    symbolic_docs: list[dict[str, Any]],
    *,
    min_length: int = 2,
    max_length: int = 5,
    min_count: int = 2,
    max_candidates: int = 5000,
) -> dict[str, Any]:
    """Build review-only phrase candidates from already-symbolized flat docs."""
    min_len = max(2, int(min_length or 2))
    max_len = max(min_len, int(max_length or min_len))
    min_occurrences = max(1, int(min_count or 1))
    sequences: dict[tuple[str, ...], dict[str, Any]] = {}

    for doc in symbolic_docs:
        _collect_doc_sequences(sequences, doc, min_len=min_len, max_len=max_len)

    candidates = [
        _candidate_row(record)
        for record in sequences.values()
        if int(record["occurrence_count"]) >= min_occurrences
    ]
    candidates.sort(key=lambda row: (-float(row["score"]), -int(row["occurrence_count"]), row["phrase"]))
    if max_candidates > 0:
        candidates = candidates[: int(max_candidates)]
    return {
        "schema_version": PHRASE_CANDIDATE_SCHEMA_VERSION,
        "created_at": _utc_now(),
        "source": "corpus_symbolized_flat_docs",
        "candidate_count": len(candidates),
        "settings": {
            "min_length": min_len,
            "max_length": max_len,
            "min_count": min_occurrences,
            "max_candidates": int(max_candidates),
        },
        "writes_allowed": {"canonical": False, "phrase_lexicon": False, "counts": False, "lifetime": False},
        "candidates": candidates,
    }


def build_phrase_candidates_from_observed_map_dir(
    observed_map_dir: str | Path,
    *,
    symbolic_map_dir: str | Path | None = None,
    min_length: int = 2,
    max_length: int = 5,
    min_count: int = 2,
    max_candidates: int = 5000,
    limit: int | None = None,
) -> dict[str, Any]:
    """Offline candidate build from debug observed maps plus AWSM symbol authority."""
    min_len = max(2, int(min_length or 2))
    max_len = max(min_len, int(max_length or min_len))
    min_occurrences = max(1, int(min_count or 1))
    root = Path(observed_map_dir).expanduser().resolve()
    symbolic_root = Path(symbolic_map_dir).expanduser().resolve() if symbolic_map_dir else None
    sequences: dict[tuple[str, ...], dict[str, Any]] = {}
    processed = 0
    skipped = 0
    for path in sorted(root.glob("*.json"), key=lambda item: item.name.lower()):
        if limit is not None and processed >= int(limit):
            break
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            doc = _symbolic_doc_from_observed_map(payload, observed_map_path=path, symbolic_root=symbolic_root)
        except Exception:
            skipped += 1
            continue
        _collect_doc_sequences(sequences, doc, min_len=min_len, max_len=max_len)
        processed += 1
    candidates = [
        _candidate_row(record)
        for record in sequences.values()
        if int(record["occurrence_count"]) >= min_occurrences
    ]
    candidates.sort(key=lambda row: (-float(row["score"]), -int(row["occurrence_count"]), row["phrase"]))
    if max_candidates > 0:
        candidates = candidates[: int(max_candidates)]
    return {
        "schema_version": PHRASE_CANDIDATE_SCHEMA_VERSION,
        "created_at": _utc_now(),
        "source": "corpus_observed_maps_offline_with_awsm_authority",
        "observed_map_root": str(root),
        "symbolic_map_root": str(symbolic_root or ""),
        "observed_map_count": processed,
        "skipped_map_count": skipped,
        "candidate_count": len(candidates),
        "settings": {
            "min_length": min_len,
            "max_length": max_len,
            "min_count": min_occurrences,
            "max_candidates": int(max_candidates),
        },
        "writes_allowed": {"canonical": False, "phrase_lexicon": False, "counts": False, "lifetime": False},
        "candidates": candidates,
    }


def load_symbolic_flat_docs(symbolic_dir: str | Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    root = Path(symbolic_dir).expanduser().resolve()
    for path in sorted(root.glob("*.symbolic.json"), key=lambda item: item.name.lower()):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            docs.append(payload)
        if limit is not None and len(docs) >= int(limit):
            break
    return docs


def build_phrase_candidates_from_symbolic_dir(
    symbolic_dir: str | Path,
    *,
    min_length: int = 2,
    max_length: int = 5,
    min_count: int = 2,
    max_candidates: int = 5000,
    limit: int | None = None,
) -> dict[str, Any]:
    docs = load_symbolic_flat_docs(symbolic_dir, limit=limit)
    result = build_phrase_candidates_from_symbolic_docs(
        docs,
        min_length=min_length,
        max_length=max_length,
        min_count=min_count,
        max_candidates=max_candidates,
    )
    result["symbolic_doc_count"] = len(docs)
    result["symbolic_root"] = str(Path(symbolic_dir).expanduser().resolve())
    return result


def write_phrase_candidate_review_from_observed_maps(
    observed_map_dir: str | Path,
    output_dir: str | Path,
    *,
    symbolic_map_dir: str | Path | None = None,
    min_length: int = 2,
    max_length: int = 5,
    min_count: int = 2,
    max_candidates: int = 5000,
    limit: int | None = None,
) -> dict[str, Any]:
    review = build_phrase_candidates_from_observed_map_dir(
        observed_map_dir,
        symbolic_map_dir=symbolic_map_dir,
        min_length=min_length,
        max_length=max_length,
        min_count=min_count,
        max_candidates=max_candidates,
        limit=limit,
    )
    written = write_phrase_candidate_review(output_dir, review)
    return {
        **written,
        "candidate_count": int(review.get("candidate_count", 0) or 0),
        "observed_map_count": int(review.get("observed_map_count", 0) or 0),
        "skipped_map_count": int(review.get("skipped_map_count", 0) or 0),
        "writes_allowed": review["writes_allowed"],
    }


def write_phrase_candidate_review(output_dir: str | Path, review: dict[str, Any]) -> dict[str, Any]:
    if review.get("schema_version") != PHRASE_CANDIDATE_SCHEMA_VERSION:
        raise ValueError("invalid phrase candidate review schema")
    root = Path(output_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    jsonl_path = root / "phrase_candidates.jsonl"
    manifest_path = root / "phrase_candidates_manifest.json"
    rows = [row for row in review.get("candidates") or [] if isinstance(row, dict)]
    jsonl_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "anchorworks_phrase_candidate_review_manifest@1",
        "created_at": _utc_now(),
        "candidate_count": len(rows),
        "jsonl_path": str(jsonl_path),
        "writes_allowed": {"canonical": False, "phrase_lexicon": False, "counts": False, "lifetime": False},
        "checksum": _file_checksum(jsonl_path),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "jsonl_path": str(jsonl_path), "manifest_path": str(manifest_path), **manifest}


def _candidate_row(record: dict[str, Any]) -> dict[str, Any]:
    anchor_sequence = [str(anchor) for anchor in record["anchor_sequence"]]
    symbol_sequence = [str(symbol) for symbol in record["symbol_sequence"]]
    occurrence_count = int(record["occurrence_count"])
    sources = sorted(str(source) for source in record["sources"] if str(source))
    source_names = sorted(str(name) for name in record["source_names"] if str(name))
    score_parts = _score_parts(anchor_sequence, occurrence_count, len(sources), record["left_boundary"], record["right_boundary"])
    score = round(sum(score_parts.values()), 6)
    return {
        "schema_version": PHRASE_CANDIDATE_ROW_VERSION,
        "phrase": " ".join(anchor_sequence),
        "phrase_id": _phrase_candidate_id(anchor_sequence, symbol_sequence),
        "anchor_sequence": anchor_sequence,
        "symbol_sequence": symbol_sequence,
        "length": len(anchor_sequence),
        "occurrence_count": occurrence_count,
        "source_count": len(sources),
        "source_ids": sources[:25],
        "source_names": source_names[:25],
        "boundary_stability": {
            "left": _counter_preview(record["left_boundary"]),
            "right": _counter_preview(record["right_boundary"]),
        },
        "score": score,
        "score_parts": {key: round(value, 6) for key, value in score_parts.items()},
        "promotion_status": "REVIEW_CANDIDATE",
        "candidate_source": str(record.get("candidate_source") or "corpus_symbolized_flat_docs"),
        "candidate_kind": _candidate_kind(anchor_sequence),
        "sample_refs": record["block_refs"][:12],
        "writes_allowed": {"canonical": False, "phrase_lexicon": False, "counts": False, "lifetime": False},
    }


def _collect_doc_sequences(
    sequences: dict[tuple[str, ...], dict[str, Any]],
    doc: dict[str, Any],
    *,
    min_len: int,
    max_len: int,
) -> None:
    source_id = str(doc.get("source_id") or doc.get("saved_document_name") or doc.get("source_name") or "").strip()
    source_name = str(doc.get("source_name") or doc.get("saved_document_name") or "").strip()
    for block in _symbolic_blocks(doc):
        anchors, symbols = _block_anchor_symbol_stream(block)
        if len(anchors) < min_len or len(symbols) != len(anchors):
            continue
        for index in range(0, len(anchors)):
            for length in range(min_len, max_len + 1):
                end = index + length
                if end > len(anchors):
                    break
                anchor_sequence = tuple(anchors[index:end])
                if _is_glue_only(anchor_sequence):
                    continue
                symbol_sequence = tuple(symbols[index:end])
                key = anchor_sequence
                record = sequences.setdefault(
                    key,
                    {
                        "anchor_sequence": list(anchor_sequence),
                        "symbol_sequence": list(symbol_sequence),
                        "occurrence_count": 0,
                        "sources": set(),
                        "source_names": set(),
                        "block_refs": [],
                        "left_boundary": Counter(),
                        "right_boundary": Counter(),
                        "candidate_source": str(doc.get("candidate_source") or "corpus_symbolized_flat_docs"),
                    },
                )
                record["occurrence_count"] += 1
                if source_id:
                    record["sources"].add(source_id)
                if source_name:
                    record["source_names"].add(source_name)
                record["block_refs"].append({
                    "source_id": source_id,
                    "source_name": source_name,
                    "block_id": str(block.get("block_id") or ""),
                    "line_start": int(block.get("line_start", 0) or 0),
                    "line_end": int(block.get("line_end", 0) or 0),
                    "start_index": index,
                    "end_index": end - 1,
                })
                left = anchors[index - 1] if index > 0 else "<START>"
                right = anchors[end] if end < len(anchors) else "<END>"
                record["left_boundary"][left] += 1
                record["right_boundary"][right] += 1


def _score_parts(
    anchor_sequence: list[str],
    occurrence_count: int,
    source_count: int,
    left_boundary: Counter[str],
    right_boundary: Counter[str],
) -> dict[str, float]:
    length = len(anchor_sequence)
    glue_count = sum(1 for anchor in anchor_sequence if anchor in _GLUE_ANCHORS)
    content_count = max(0, length - glue_count)
    edge_glue_count = int(anchor_sequence[0] in _GLUE_ANCHORS) + int(anchor_sequence[-1] in _GLUE_ANCHORS)
    boundary_stability = _boundary_stability(left_boundary, occurrence_count) + _boundary_stability(right_boundary, occurrence_count)
    return {
        "occurrence_weight": float(occurrence_count) * 2.0,
        "source_diversity": float(source_count) * 3.0,
        "length_specificity": float(length) * 1.5,
        "content_density": float(content_count) / float(length),
        "boundary_stability": boundary_stability,
        "glue_penalty": -1.25 * float(glue_count) if glue_count == length else -0.25 * float(glue_count),
        "edge_glue_penalty": -4.0 * float(edge_glue_count),
        "thin_content_penalty": -3.0 if content_count <= 1 else 0.0,
    }


def _boundary_stability(counter: Counter[str], occurrence_count: int) -> float:
    if occurrence_count <= 0 or not counter:
        return 0.0
    most_common = counter.most_common(1)[0][1]
    return float(most_common) / float(occurrence_count)


def _symbolic_blocks(doc: dict[str, Any]) -> list[dict[str, Any]]:
    blocks = [block for block in doc.get("blocks") or [] if isinstance(block, dict)]
    if blocks:
        return blocks
    paragraphs = [row for row in doc.get("paragraphs") or [] if isinstance(row, dict)]
    return [
        {
            **row,
            "block_id": f"block_{int(row.get('paragraph_id', index) or index)}",
            "anchor_stream": row.get("resolved_anchors") or row.get("anchors") or [],
            "symbol_stream": row.get("symbol_stream") or row.get("composed_anchor_stream") or [],
        }
        for index, row in enumerate(paragraphs)
    ]


def _symbolic_doc_from_observed_map(payload: dict[str, Any], *, observed_map_path: Path, symbolic_root: Path | None) -> dict[str, Any]:
    symbolic_path = _resolve_symbolic_map_path(payload, observed_map_path=observed_map_path, symbolic_root=symbolic_root)
    symbol_by_resolved_anchor = _symbol_by_resolved_anchor(symbolic_path)
    blocks: list[dict[str, Any]] = []
    for paragraph in [row for row in payload.get("paragraphs") or [] if isinstance(row, dict)]:
        anchors = list(paragraph.get("anchors") or [])
        resolved = list(paragraph.get("resolved_anchors") or [])
        stream_anchors: list[str] = []
        stream_symbols: list[str] = []
        for surface, resolved_anchor in zip(anchors, resolved):
            clean_surface = _clean_anchor(surface)
            clean_resolved = str(resolved_anchor or "").strip()
            if not _is_phrase_surface_anchor(clean_surface):
                continue
            if clean_resolved == "__NULL__":
                continue
            symbol = symbol_by_resolved_anchor.get(clean_resolved)
            if not symbol:
                continue
            stream_anchors.append(clean_surface)
            stream_symbols.append(symbol)
        paragraph_id = int(paragraph.get("paragraph_id", len(blocks)) or 0)
        blocks.append({
            "block_id": f"block_{paragraph_id}",
            "line_start": int(paragraph.get("line_start", 0) or 0),
            "line_end": int(paragraph.get("line_end", 0) or 0),
            "anchor_stream": stream_anchors,
            "symbol_stream": stream_symbols,
        })
    return {
        "schema_version": "flat_symbolic_document@observed-map-offline",
        "source_id": str(payload.get("source_id") or (payload.get("document_prep") or {}).get("sha256") or observed_map_path.stem),
        "source_name": str(payload.get("source_name") or observed_map_path.name),
        "saved_document_name": observed_map_path.name,
        "candidate_source": "corpus_observed_maps_offline_with_awsm_authority",
        "blocks": blocks,
    }


def _resolve_symbolic_map_path(payload: dict[str, Any], *, observed_map_path: Path, symbolic_root: Path | None) -> Path:
    raw = str(payload.get("symbolic_map_path") or "").strip()
    if raw:
        path = Path(raw)
        if path.exists():
            return path
    if symbolic_root is not None:
        candidate = symbolic_root / observed_map_path.name.replace(".observed.json", ".awsm")
        if candidate.exists():
            return candidate
    raise FileNotFoundError("matching AWSM symbolic map not found for " + observed_map_path.name)


def _symbol_by_resolved_anchor(symbolic_map_path: Path) -> dict[str, str]:
    bundle = read_symbolic_map_bundle(symbolic_map_path)
    out: dict[str, str] = {}
    for row in bundle.map.metadata.get("symbol_authority") or []:
        if not isinstance(row, dict):
            continue
        anchor = str(row.get("anchor") or "").strip()
        symbol = _clean_symbol(row.get("symbol"))
        if anchor and symbol:
            out[anchor] = symbol
    return out


def _block_anchor_symbol_stream(block: dict[str, Any]) -> tuple[list[str], list[str]]:
    raw_anchors = list(block.get("anchor_stream") or block.get("anchors") or [])
    raw_symbols = list(block.get("symbol_stream") or block.get("symbols") or [])
    anchors: list[str] = []
    symbols: list[str] = []
    for raw_anchor, raw_symbol in zip(raw_anchors, raw_symbols):
        anchor = _clean_anchor(raw_anchor)
        symbol = _clean_symbol(raw_symbol)
        if not _is_phrase_surface_anchor(anchor) or not symbol:
            continue
        anchors.append(anchor)
        symbols.append(symbol)
    return anchors, symbols


def _is_glue_only(anchor_sequence: tuple[str, ...]) -> bool:
    return all(anchor in _GLUE_ANCHORS for anchor in anchor_sequence)


def _clean_anchor(value: Any) -> str:
    return str(value or "").strip().casefold()


def _clean_symbol(value: Any) -> str:
    return str(value or "").strip().casefold()


def _is_phrase_surface_anchor(anchor: str) -> bool:
    if not anchor or anchor == "__null__" or anchor.startswith("u") and len(anchor) >= 8:
        return False
    return any(char.isalnum() for char in anchor)


def _candidate_kind(anchor_sequence: list[str]) -> str:
    glue_count = sum(1 for anchor in anchor_sequence if anchor in _GLUE_ANCHORS)
    if glue_count == 0:
        return "concept_candidate"
    if anchor_sequence[0] in _GLUE_ANCHORS or anchor_sequence[-1] in _GLUE_ANCHORS:
        return "director_or_structural_candidate"
    return "concept_with_director_candidate"


def _counter_preview(counter: Counter[str]) -> list[dict[str, Any]]:
    return [{"anchor": key, "count": int(value)} for key, value in counter.most_common(6)]


def _phrase_candidate_id(anchor_sequence: list[str], symbol_sequence: list[str]) -> str:
    seed = "\x1f".join(anchor_sequence) + "\x1e" + "\x1f".join(symbol_sequence)
    return "0x" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:10].upper()


def _file_checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
