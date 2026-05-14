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


def promote_genome_rebuild_to_live(
    data_root: str | Path,
    *,
    rebuild_root: str | Path | None = None,
    backup_root: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(data_root).expanduser().resolve()
    rebuild = Path(rebuild_root).expanduser().resolve() if rebuild_root else root / "Lexicon_Genome_Rebuild"
    if not rebuild.exists():
        raise FileNotFoundError(rebuild)
    manifest_path = rebuild / "reports" / "rebuild_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not manifest.get("ok"):
        raise ValueError("cannot promote a failed genome rebuild")

    backup = Path(backup_root).expanduser().resolve() if backup_root else root / "Lexicon_Backups" / f"pre_genome_swap_{_timestamp_slug()}"
    backup.mkdir(parents=True, exist_ok=False)
    for lane in ["Canonical", "Structural"]:
        source = root / lane
        if source.exists():
            shutil.copytree(source, backup / lane)

    live_canonical = root / "Canonical"
    live_structural = root / "Structural"
    live_canonical.mkdir(parents=True, exist_ok=True)
    live_structural.mkdir(parents=True, exist_ok=True)
    for path in live_canonical.glob("canonical_*.json"):
        path.unlink()
    structural_path = live_structural / "structural.json"
    if structural_path.exists():
        structural_path.unlink()

    promoted_canonical_rows = 0
    live_canonical_by_letter: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in sorted((rebuild / "Canonical").glob("*.json")):
        rows = [_live_row_from_rebuild(row) for row in json.loads(path.read_text(encoding="utf-8"))]
        promoted_canonical_rows += len(rows)
        for row in rows:
            live_canonical_by_letter[_live_letter_for_word(row["word"])].append(row)
    for letter, rows in sorted(live_canonical_by_letter.items()):
        rows.sort(key=lambda item: (str(item.get("word", "")).casefold(), str(item.get("word", ""))))
        _write_json(live_canonical / f"canonical_{letter}.json", rows)

    promoted_structural_rows = 0
    structural_rows = []
    rebuilt_structural_path = rebuild / "Structural" / "structural.json"
    if rebuilt_structural_path.exists():
        structural_rows = [_live_row_from_rebuild(row) for row in json.loads(rebuilt_structural_path.read_text(encoding="utf-8"))]
        promoted_structural_rows = len(structural_rows)
        _write_json(structural_path, structural_rows)

    verification = verify_live_genome_lexicon(root)
    report = {
        "ok": verification["ok"],
        "schema_version": "anchorworks_lexicon_genome_live_promotion@1",
        "promoted_at": _utc_now(),
        "data_root": str(root),
        "rebuild_root": str(rebuild),
        "backup_root": str(backup),
        "canonical_rows": promoted_canonical_rows,
        "structural_rows": promoted_structural_rows,
        **verification,
    }
    reports_root = rebuild / "reports"
    _write_json(reports_root / "live_promotion_report.json", report)
    return report


def verify_live_genome_lexicon(data_root: str | Path) -> dict[str, Any]:
    root = Path(data_root).expanduser().resolve()
    paths = sorted((root / "Canonical").glob("canonical_*.json"))
    structural_path = root / "Structural" / "structural.json"
    if structural_path.exists():
        paths.append(structural_path)
    rows: list[dict[str, Any]] = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            rows.extend(row for row in payload if isinstance(row, dict))
    symbols: list[str] = []
    missing_word = 0
    tone_count = 0
    font_count = 0
    frequency_count = 0
    extra_field_count = 0
    for row in rows:
        if set(row) != {"word", "symbol"}:
            extra_field_count += 1
        if not str(row.get("word") or "").strip():
            missing_word += 1
        if "tone_signature" in row:
            tone_count += 1
        if "font_symbol" in row:
            font_count += 1
        if "frequency" in row:
            frequency_count += 1
        symbol = str(row.get("symbol") or "")
        symbols.append(symbol)
    duplicate_symbols = len(symbols) - len(set(symbols))
    ok = (
        rows
        and duplicate_symbols == 0
        and missing_word == 0
        and tone_count == 0
        and font_count == 0
        and frequency_count == 0
        and extra_field_count == 0
    )
    return {
        "live_rows": len(rows),
        "duplicate_symbols": duplicate_symbols,
        "missing_word": missing_word,
        "tone_signature_count": tone_count,
        "font_symbol_count": font_count,
        "frequency_count": frequency_count,
        "non_minimal_row_count": extra_field_count,
        "ok": bool(ok),
    }


def _live_row_from_rebuild(row: dict[str, Any]) -> dict[str, Any]:
    anchor = str(row.get("anchor") or row.get("display") or "").strip()
    genome_hex = str(row.get("genome_hex") or row.get("genome_symbol") or "").strip()
    genome_binary = str(row.get("genome_binary") or "").strip()
    if not anchor or not genome_hex or not genome_binary:
        raise ValueError(f"cannot promote incomplete rebuild row: {row}")
    return {
        "word": anchor,
        "symbol": genome_hex,
    }


def _live_letter_for_word(word: str) -> str:
    for char in str(word or "").strip().lower():
        if char.isalpha():
            return char.upper()
    return "A"


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


def _timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
