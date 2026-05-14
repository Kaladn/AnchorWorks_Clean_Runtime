from __future__ import annotations

import hashlib
import json
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .symbol_genome_native import allocate_symbol_genome_batch, build_native_symbol_genome


ALLOWED_REBUILT_FIELDS = {
    "anchor",
    "display",
    "genome_symbol",
    "genome_hex",
    "genome_binary",
    "status",
    "pack",
    "created_at",
    "category",
    "source_old_hex",
    "source_old_symbol",
}


def build_lexicon_genome_rebuild(
    data_root: str | Path,
    *,
    output_root: str | Path | None = None,
    native_allocator: str | Path | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    root = Path(data_root).expanduser().resolve()
    out = Path(output_root).expanduser().resolve() if output_root else root / "Lexicon_Genome_Rebuild"
    if out.exists():
        shutil.rmtree(out)
    (out / "Canonical").mkdir(parents=True)
    (out / "Structural").mkdir(parents=True)
    (out / "mappings").mkdir(parents=True)
    (out / "reports").mkdir(parents=True)
    (out / "working").mkdir(parents=True)

    source_hashes_before = _source_hashes(root)
    source_rows = _read_source_rows(root)
    unique_rows, duplicate_anchor_rows = _dedupe_by_anchor(source_rows)
    if limit is not None:
        unique_rows = unique_rows[: int(limit)]
    duplicate_old_symbols = _duplicate_old_symbol_report(source_rows)

    allocator_input = out / "working" / "allocator_input.tsv"
    allocator_output = out / "working" / "allocator_output.tsv"
    allocator_input.write_text(
        "".join(f"{index}\t{row['pack']}\t{row['anchor']}\n" for index, row in enumerate(unique_rows)),
        encoding="utf-8",
    )
    exe = Path(native_allocator) if native_allocator else build_native_symbol_genome()
    allocation_report = allocate_symbol_genome_batch(
        allocator_input,
        allocator_output,
        category="core",
        priority=4,
        executable=exe,
    )
    allocations = _read_allocations(allocator_output)
    if len(allocations) != len(unique_rows):
        raise ValueError("native allocator row count mismatch")
    shutil.rmtree(out / "working")

    created_at = _utc_now()
    rebuilt_rows: list[dict[str, Any]] = []
    for row, allocation in zip(unique_rows, allocations):
        rebuilt_rows.append({
            "anchor": row["anchor"],
            "display": row["display"],
            "genome_symbol": allocation["genome_hex"],
            "genome_hex": allocation["genome_hex"],
            "genome_binary": allocation["genome_binary"],
            "status": "ASSIGNED",
            "pack": row["pack"],
            "created_at": created_at,
            "category": "core",
            "source_old_hex": row.get("source_old_hex", ""),
            "source_old_symbol": row.get("source_old_symbol", ""),
        })

    canonical_rows = [row for row in rebuilt_rows if row["pack"] == "canonical"]
    structural_rows = [row for row in rebuilt_rows if row["pack"] == "structural"]
    _write_canonical_packs(out / "Canonical", canonical_rows)
    _write_json(out / "Structural" / "structural.json", structural_rows)
    _write_mappings(out / "mappings", rebuilt_rows)
    _write_json(out / "reports" / "duplicate_old_symbols.json", duplicate_old_symbols)
    _write_json(out / "reports" / "duplicate_anchors.json", {
        "duplicate_anchor_count": len(duplicate_anchor_rows),
        "duplicates": duplicate_anchor_rows,
    })

    verification = verify_rebuilt_lexicon(out)
    source_hashes_after = _source_hashes(root)
    source_untouched = source_hashes_before == source_hashes_after
    rebuilt_count_matches = verification["rebuilt_rows"] == len(rebuilt_rows)
    manifest = {
        "ok": verification["ok"] and source_untouched and rebuilt_count_matches,
        "schema_version": "anchorworks_lexicon_genome_rebuild@1",
        "created_at": created_at,
        "source_root": str(root),
        "output_root": str(out),
        "generator": "native_cpp_symbol_genome_allocator",
        "allocator_executable": str(exe),
        "allocator_report": allocation_report,
        "source_rows": len(source_rows),
        "unique_rows": len(unique_rows),
        "canonical_rows": len(canonical_rows),
        "structural_rows": len(structural_rows),
        "duplicate_anchor_count": len(duplicate_anchor_rows),
        "duplicate_old_symbol_count": duplicate_old_symbols["duplicate_old_symbol_count"],
        "original_sources_untouched": source_untouched,
        "rebuilt_count_matches_allocated": rebuilt_count_matches,
        **verification,
    }
    _write_json(out / "reports" / "rebuild_manifest.json", manifest)
    return manifest


def load_rebuilt_rows(output_root: str | Path) -> list[dict[str, Any]]:
    out = Path(output_root)
    rows: list[dict[str, Any]] = []
    for path in sorted((out / "Canonical").glob("*.json")) + sorted((out / "Structural").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            rows.extend(row for row in payload if isinstance(row, dict))
    return rows


def verify_rebuilt_lexicon(output_root: str | Path) -> dict[str, Any]:
    rows = load_rebuilt_rows(output_root)
    genome_symbols: list[str] = []
    genome_hexes: list[str] = []
    bad_binary = 0
    extra_fields: set[str] = set()
    tone_signature_count = 0
    font_symbol_count = 0
    bad_status_count = 0
    hex_symbol_mismatch = 0
    for row in rows:
        extra_fields.update(set(row) - ALLOWED_REBUILT_FIELDS)
        if "tone_signature" in row:
            tone_signature_count += 1
        if "font_symbol" in row:
            font_symbol_count += 1
        if row.get("status") != "ASSIGNED":
            bad_status_count += 1
        genome_symbol = str(row.get("genome_symbol") or "")
        genome_hex = str(row.get("genome_hex") or "")
        if genome_symbol != genome_hex:
            hex_symbol_mismatch += 1
        genome_symbols.append(genome_symbol)
        genome_hexes.append(genome_hex)
        try:
            if len(str(row.get("genome_binary") or "")) != 40:
                bad_binary += 1
            elif int(genome_hex[2:], 16) != int(str(row.get("genome_binary")), 2):
                bad_binary += 1
        except Exception:
            bad_binary += 1
    duplicate_genome_symbols = len(genome_symbols) - len(set(genome_symbols))
    duplicate_genome_hex = len(genome_hexes) - len(set(genome_hexes))
    ok = (
        duplicate_genome_symbols == 0
        and duplicate_genome_hex == 0
        and bad_binary == 0
        and not extra_fields
        and tone_signature_count == 0
        and font_symbol_count == 0
        and bad_status_count == 0
        and hex_symbol_mismatch == 0
    )
    return {
        "ok": ok,
        "rebuilt_rows": len(rows),
        "duplicate_genome_symbols": duplicate_genome_symbols,
        "duplicate_genome_hex": duplicate_genome_hex,
        "hex_symbol_mismatch": hex_symbol_mismatch,
        "bad_binary_count": bad_binary,
        "extra_fields": sorted(extra_fields),
        "tone_signature_absent": tone_signature_count == 0,
        "font_symbol_absent": font_symbol_count == 0,
        "bad_status_count": bad_status_count,
    }


def _read_source_rows(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    canonical_root = root / "Canonical"
    structural_root = root / "Structural"
    if canonical_root.exists():
        for path in sorted(canonical_root.glob("*.json")):
            if path.name.lower() == "structural.json":
                continue
            rows.extend(_read_pack_file(path, "canonical"))
    if structural_root.exists():
        for path in sorted(structural_root.glob("*.json")):
            rows.extend(_read_pack_file(path, "structural"))
    return rows


def _read_pack_file(path: Path, pack: str) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []
    rows = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        anchor = str(row.get("anchor") or row.get("word") or row.get("display") or "").strip()
        if not anchor:
            continue
        rows.append({
            "anchor": anchor,
            "display": str(row.get("display") or anchor).strip(),
            "pack": pack,
            "source_file": str(path),
            "source_old_hex": str(row.get("hex") or "").strip(),
            "source_old_symbol": str(row.get("symbol") or row.get("hex") or "").strip(),
        })
    return rows


def _dedupe_by_anchor(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_anchor: dict[str, dict[str, Any]] = {}
    duplicates: list[dict[str, Any]] = []
    for row in rows:
        key = row["anchor"].casefold()
        if key not in by_anchor:
            by_anchor[key] = row
            continue
        duplicates.append({
            "anchor": row["anchor"],
            "kept_pack": by_anchor[key]["pack"],
            "duplicate_pack": row["pack"],
            "kept_old_symbol": by_anchor[key].get("source_old_symbol", ""),
            "duplicate_old_symbol": row.get("source_old_symbol", ""),
        })
    return sorted(by_anchor.values(), key=lambda item: (item["pack"], item["anchor"].casefold(), item["anchor"])), duplicates


def _duplicate_old_symbol_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        old_symbol = str(row.get("source_old_symbol") or row.get("source_old_hex") or "").strip()
        if not old_symbol:
            continue
        groups[old_symbol].append({
            "anchor": row["anchor"],
            "display": row["display"],
            "pack": row["pack"],
            "source_file": row["source_file"],
        })
    duplicates = [
        {"old_symbol": symbol, "rows": members, "count": len(members)}
        for symbol, members in sorted(groups.items())
        if len(members) > 1
    ]
    return {
        "duplicate_old_symbol_count": len(duplicates),
        "duplicates": duplicates,
    }


def _read_allocations(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 4:
            raise ValueError(f"invalid allocator output line: {line}")
        rows.append({
            "row_index": int(parts[0]),
            "allocation_index": int(parts[1]),
            "genome_hex": parts[2],
            "genome_binary": parts[3],
        })
    return rows


def _write_canonical_packs(root: Path, rows: list[dict[str, Any]]) -> None:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        first = (row["anchor"][:1] or "_").upper()
        grouped[first].append(row)
    for first, members in sorted(grouped.items()):
        safe = f"{_safe_pack_prefix(first)}_U{ord(first):04X}"
        _write_json(root / f"canonical_{safe}.json", members)


def _safe_pack_prefix(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value) or "_"


def _write_mappings(root: Path, rows: list[dict[str, Any]]) -> None:
    with (root / "anchor_to_genome_symbol.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps({
                "anchor": row["anchor"],
                "genome_symbol": row["genome_symbol"],
                "pack": row["pack"],
            }, ensure_ascii=False) + "\n")
    with (root / "old_symbol_to_genome_symbol.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps({
                "old_symbol": row["source_old_symbol"],
                "genome_symbol": row["genome_symbol"],
                "anchor": row["anchor"],
                "pack": row["pack"],
            }, ensure_ascii=False) + "\n")
    with (root / "old_hex_to_genome_hex.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps({
                "old_hex": row["source_old_hex"],
                "genome_hex": row["genome_hex"],
                "anchor": row["anchor"],
                "pack": row["pack"],
            }, ensure_ascii=False) + "\n")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _source_hashes(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for source_root in [root / "Canonical", root / "Structural"]:
        if not source_root.exists():
            continue
        for path in sorted(source_root.glob("*.json")):
            hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
