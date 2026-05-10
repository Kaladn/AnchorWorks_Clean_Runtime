from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .document_prep import prepare_file
from .intake import NULL_ANCHOR, extract_anchor_rows


def audit_source_directory(source_dir: Path) -> dict[str, Any]:
    root = Path(source_dir).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(root)
    if not root.is_dir():
        raise NotADirectoryError(root)

    by_extension: Counter[str] = Counter()
    by_converter: Counter[str] = Counter()
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    file_rows: list[dict[str, Any]] = []
    null_observations = 0
    companion_observations = 0

    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: str(item).lower()):
        suffix = path.suffix.lower() or "[none]"
        by_extension[suffix] += 1
        try:
            prepared = prepare_file(path)
        except Exception as exc:
            failures.append({"path": str(path), "extension": suffix, "error": str(exc)})
            continue
        rows = extract_anchor_rows(prepared.prepared_text)
        null_count = sum(1 for row in rows if row.get("anchor") == NULL_ANCHOR)
        companion_count = sum(1 for row in rows if not row.get("count_eligible", True))
        null_observations += null_count
        companion_observations += companion_count
        by_converter[prepared.converter] += 1
        if prepared.warnings:
            warnings.append({"path": str(path), "warnings": prepared.warnings})
        file_rows.append({
            "path": str(path),
            "extension": suffix,
            "converter": prepared.converter,
            "size_bytes": prepared.original_size,
            "warnings": prepared.warnings,
            "null_observations": null_count,
            "companion_or_noncounting_observations": companion_count,
        })

    return {
        "ok": not failures,
        "source_dir": str(root),
        "files_seen": sum(by_extension.values()),
        "files_prepared": len(file_rows),
        "failure_count": len(failures),
        "by_extension": dict(sorted(by_extension.items())),
        "by_converter": dict(sorted(by_converter.items())),
        "warnings": warnings,
        "failures": failures,
        "null_observations": null_observations,
        "companion_or_noncounting_observations": companion_observations,
        "files": file_rows,
    }


def rebuild_readiness_report(*, source_dir: Path, state_dir: Path) -> dict[str, Any]:
    sources = Path(source_dir).expanduser().resolve()
    state = Path(state_dir).expanduser().resolve()
    observed_maps = state / "observed_maps"
    flat_symbolic = state / "flat_documents" / "symbolic"
    symbol_counts = state / "source_local_symbol_counts"
    cleanup_ledger = state / "ingest_staging" / "cleanup_ledger" / "cleanup_ledger.json"

    raw_files = [path for path in sources.rglob("*") if path.is_file()] if sources.exists() else []
    map_files = list(observed_maps.glob("*.observed.json")) if observed_maps.exists() else []
    flat_files = list(flat_symbolic.glob("*.symbolic.json")) if flat_symbolic.exists() else []
    symbol_count_files = list(symbol_counts.glob("*.symbol_counts.json")) if symbol_counts.exists() else []

    return {
        "ok": sources.exists() and cleanup_ledger.exists(),
        "raw_sources": {"path": str(sources), "exists": sources.exists(), "file_count": len(raw_files)},
        "observed_maps": {"path": str(observed_maps), "exists": observed_maps.exists(), "file_count": len(map_files)},
        "flat_symbolic_documents": {"path": str(flat_symbolic), "exists": flat_symbolic.exists(), "file_count": len(flat_files)},
        "source_local_symbol_counts": {"path": str(symbol_counts), "exists": symbol_counts.exists(), "file_count": len(symbol_count_files)},
        "cleanup_ledger": {"path": str(cleanup_ledger), "exists": cleanup_ledger.exists()},
        "rebuild_needed": len(map_files) != len(raw_files) or len(flat_files) != len(map_files),
        "manual_map_move": "manual_only",
    }
