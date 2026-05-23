from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from .occular_tensor_store import default_tensor_brain_root, load_occular_tensor_shard


OCCULAR_INDEX_SCHEMA_VERSION = "anchorworks_occular_tensor_shard_index@1"


def occular_cloud_root(root: Path | str | None = None) -> Path:
    base = Path(root) if root is not None else default_tensor_brain_root()
    return base / "occular_cloud"


def build_occular_shard_index(
    *,
    root: Path | str | None = None,
    manifest_paths: list[Path | str] | None = None,
    recognition_grade: str = "controlled_glyph_fixture",
) -> dict[str, Any]:
    cloud_root = occular_cloud_root(root)
    cloud_root.mkdir(parents=True, exist_ok=True)
    manifests = [Path(path) for path in (manifest_paths or _find_manifest_paths(cloud_root))]
    records = [_index_record(path, recognition_grade=recognition_grade) for path in manifests]
    records.sort(key=lambda row: row["shard_id"])
    index = {
        "schema_version": OCCULAR_INDEX_SCHEMA_VERSION,
        "index_path": str(cloud_root / "shard_index.json"),
        "created_at": _utc_now(),
        "record_count": len(records),
        "records": records,
        "truth_boundary": {
            "index_is_locator_not_authority": True,
            "tensor_hashes_verify_shards": True,
            "query_loads_candidate_shards_only": True,
        },
        "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
    }
    index["index_sha256"] = _hash_payload({"records": records})
    Path(index["index_path"]).write_text(json.dumps(index, indent=2, sort_keys=True), encoding="utf-8")
    return index


def load_occular_shard_index(*, root: Path | str | None = None, index_path: Path | str | None = None) -> dict[str, Any]:
    path = Path(index_path) if index_path is not None else occular_cloud_root(root) / "shard_index.json"
    return json.loads(path.read_text(encoding="utf-8"))


def query_occular_tensor_cloud(
    *,
    root: Path | str | None = None,
    query_symbols: list[str],
    top_k: int = 10,
    index_path: Path | str | None = None,
    write_receipt: bool = True,
    allow_full_scan: bool = False,
) -> dict[str, Any]:
    started = time.perf_counter()
    index = load_occular_shard_index(root=root, index_path=index_path)
    query = [str(symbol) for symbol in query_symbols if str(symbol)]
    if not query:
        raise ValueError("query_symbols must contain at least one symbol")
    query_set = set(query)
    candidates = _candidate_index_records(index["records"], query_set=query_set, allow_full_scan=allow_full_scan)
    skipped = [row["shard_id"] for row in index["records"] if row not in candidates]
    results: list[dict[str, Any]] = []
    loaded_ids: list[str] = []

    for record in candidates:
        loaded = load_occular_tensor_shard(record["manifest_path"])
        loaded_ids.append(record["shard_id"])
        results.extend(_score_shard(loaded, query=query, query_set=query_set, shard_record=record))

    results.sort(key=lambda row: (-row["score"], -row["center_match_count"], -row["context_match_count"], row["shard_id"], row["row_index"]))
    elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)
    response = {
        "schema_version": "anchorworks_occular_tensor_query@1",
        "query_symbols": query,
        "top_k_requested": int(top_k),
        "top_k": results[: int(top_k)],
        "loaded_shard_ids": loaded_ids,
        "skipped_shard_ids": skipped,
        "elapsed_ms": elapsed_ms,
        "index_sha256": index.get("index_sha256", ""),
        "truth_boundary": {
            "query_reads_tensor_shards": True,
            "query_does_not_mutate_authority": True,
            "scores_are_local_cloud_fit": True,
        },
        "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
    }
    response["query_sha256"] = _hash_payload({key: value for key, value in response.items() if key != "receipt_path"})
    if write_receipt:
        receipt_path = _write_query_receipt(root=root, response=response)
        response["receipt_path"] = str(receipt_path)
    else:
        response["receipt_path"] = ""
    return response


def _index_record(manifest_path: Path, *, recognition_grade: str) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    block_metadata = list(manifest.get("block_metadata") or [])
    symbol_table = list(manifest.get("symbol_table") or [])
    source_ids = sorted({str(row.get("source_ref") or "") for row in block_metadata if str(row.get("source_ref") or "")})
    unique_center_count = _unique_center_count(manifest_path)
    return {
        "shard_id": str(manifest["shard_id"]),
        "manifest_path": str(manifest_path),
        "tensor_path": str(manifest["tensor_path"]),
        "source_ids": source_ids,
        "symbol_count": len(symbol_table),
        "window_count": int(manifest["window_count"]),
        "unique_center_count": unique_center_count,
        "backend": str(manifest.get("backend") or ""),
        "device": str(manifest.get("device") or manifest.get("backend") or ""),
        "sha256": str(manifest["tensor_sha256"]),
        "created_at": _utc_now(),
        "recognition_grade": str(recognition_grade),
        "symbol_presence": sorted(symbol for symbol in symbol_table if symbol != "__PAD__"),
    }


def _unique_center_count(manifest_path: Path) -> int:
    loaded = load_occular_tensor_shard(manifest_path)
    centers = loaded["arrays"]["center_windows"]
    if centers.size == 0:
        return 0
    return int(np.unique(centers, axis=0).shape[0])


def _candidate_index_records(
    records: list[dict[str, Any]],
    *,
    query_set: set[str],
    allow_full_scan: bool,
) -> list[dict[str, Any]]:
    if allow_full_scan:
        return list(records)
    candidates: list[dict[str, Any]] = []
    for record in records:
        presence = set(record.get("symbol_presence") or [])
        if query_set.intersection(presence):
            candidates.append(record)
    return candidates


def _score_shard(
    loaded: dict[str, Any],
    *,
    query: list[str],
    query_set: set[str],
    shard_record: dict[str, Any],
) -> list[dict[str, Any]]:
    manifest = loaded["manifest"]
    arrays = loaded["arrays"]
    symbol_table = list(manifest["symbol_table"])
    block_metadata = list(manifest["block_metadata"])
    scored: list[dict[str, Any]] = []

    for row_index, center_ids in enumerate(arrays["center_windows"]):
        center = [_symbol_from_id(symbol_table, int(symbol_id)) for symbol_id in center_ids]
        left = [
            [_symbol_from_id(symbol_table, int(symbol_id)) for symbol_id in cloud]
            for cloud in arrays["left_context"][row_index]
        ]
        right = [
            [_symbol_from_id(symbol_table, int(symbol_id)) for symbol_id in cloud]
            for cloud in arrays["right_context"][row_index]
        ]
        center_matches = [symbol for symbol in center if symbol in query_set]
        context_flat = [symbol for cloud in left + right for symbol in cloud]
        context_matches = [symbol for symbol in context_flat if symbol in query_set]
        ordered_center_bonus = 1.0 if center == query else 0.0
        center_match_count = len(center_matches)
        context_match_count = len(context_matches)
        if center_match_count == 0 and context_match_count == 0:
            continue
        if ordered_center_bonus:
            score = 1.0
        else:
            score = round(
                (center_match_count / max(1, len(query))) * 0.75
                + (context_match_count / max(1, len(query))) * 0.20,
                6,
            )
        block = block_metadata[int(arrays["block_indices"][row_index])]
        scored.append(
            {
                "schema_version": "anchorworks_occular_tensor_query_candidate@1",
                "shard_id": shard_record["shard_id"],
                "row_index": int(row_index),
                "score": min(score, 1.0),
                "center_match_count": center_match_count,
                "context_match_count": context_match_count,
                "center_symbols": center,
                "left_context_clouds": left,
                "right_context_clouds": right,
                "block_id": block["block_id"],
                "source_ref": block.get("source_ref") or "",
                "visual_ref": block.get("visual_ref") or {},
                "tensor_sha256": shard_record["sha256"],
                "recognition_grade": shard_record.get("recognition_grade", ""),
            }
        )
    return scored


def _write_query_receipt(*, root: Path | str | None, response: dict[str, Any]) -> Path:
    receipts = occular_cloud_root(root) / "receipts" / "queries"
    receipts.mkdir(parents=True, exist_ok=True)
    filename = f"occular_query_{_utc_filename()}_{response['query_sha256'][:12]}.json"
    path = receipts / filename
    path.write_text(json.dumps(response, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _find_manifest_paths(cloud_root: Path) -> list[Path]:
    shards = cloud_root / "shards"
    if not shards.exists():
        return []
    return sorted(shards.glob("*/*.occular_tensor_manifest.json"))


def _symbol_from_id(symbol_table: list[str], symbol_id: int) -> str:
    if symbol_id <= 0 or symbol_id >= len(symbol_table):
        raise ValueError(f"invalid occular tensor symbol id: {symbol_id}")
    return str(symbol_table[symbol_id])


def _hash_payload(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _utc_filename() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
