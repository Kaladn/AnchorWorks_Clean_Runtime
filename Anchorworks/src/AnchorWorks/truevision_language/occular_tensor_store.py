from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import numpy as np

from .occular_cloud import DEFAULT_BLOCKED_SYMBOLS, OccularCloudConfig, _center_hash


OCCULAR_TENSOR_SCHEMA_VERSION = "anchorworks_occular_tensor_shard_manifest@1"
PAD_SYMBOL = "__PAD__"
PAD_ID = 0


def default_tensor_brain_root() -> Path:
    configured = os.environ.get("ANCHORWORKS_TENSOR_BRAIN_ROOT")
    if configured:
        return Path(configured)
    return Path("D:/AnchorWorks_Tensor_Brain")


def write_occular_tensor_shard(
    *,
    root: Path | str | None = None,
    shard_id: str,
    blocks: list[dict[str, Any]],
    config: OccularCloudConfig | None = None,
    blocked_symbols: set[str] | None = None,
    backend: str = "cpu",
) -> dict[str, Any]:
    cfg = config or OccularCloudConfig()
    shard_root = (Path(root) if root is not None else default_tensor_brain_root()) / "occular_cloud" / "shards" / str(shard_id)
    shard_root.mkdir(parents=True, exist_ok=True)

    packed = pack_occular_tensor_shard(blocks=blocks, config=cfg, blocked_symbols=blocked_symbols)
    tensor_path = shard_root / f"{shard_id}.occular_tensor.npz"
    np.savez_compressed(
        tensor_path,
        center_windows=packed["center_windows"],
        left_context=packed["left_context"],
        right_context=packed["right_context"],
        block_indices=packed["block_indices"],
        center_starts=packed["center_starts"],
    )
    tensor_hash = _hash_file(tensor_path)
    manifest = {
        "schema_version": OCCULAR_TENSOR_SCHEMA_VERSION,
        "shard_id": str(shard_id),
        "tensor_path": str(tensor_path),
        "tensor_sha256": tensor_hash,
        "config": cfg.to_dict(),
        "backend": str(backend),
        "symbol_table": packed["symbol_table"],
        "block_metadata": packed["block_metadata"],
        "blocked_symbols": packed["blocked_symbols"],
        "window_count": int(packed["center_windows"].shape[0]),
        "arrays": {
            "center_windows": list(packed["center_windows"].shape),
            "left_context": list(packed["left_context"].shape),
            "right_context": list(packed["right_context"].shape),
            "block_indices": list(packed["block_indices"].shape),
            "center_starts": list(packed["center_starts"].shape),
        },
        "truth_boundary": {
            "symbols_are_tensor_ids": True,
            "lexicon_remains_authority": True,
            "gpu_execution_not_authority": True,
            "tensor_store_not_lifetime_memory": True,
        },
        "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
    }
    manifest_path = shard_root / f"{shard_id}.occular_tensor_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "schema_version": "anchorworks_occular_tensor_shard_write@1",
        "shard_id": str(shard_id),
        "manifest_path": str(manifest_path),
        "tensor_path": str(tensor_path),
        "tensor_sha256": tensor_hash,
        "window_count": manifest["window_count"],
    }


def pack_occular_tensor_shard(
    *,
    blocks: list[dict[str, Any]],
    config: OccularCloudConfig | None = None,
    blocked_symbols: set[str] | None = None,
) -> dict[str, Any]:
    cfg = config or OccularCloudConfig()
    blocked = set(DEFAULT_BLOCKED_SYMBOLS)
    blocked.update(str(symbol) for symbol in (blocked_symbols or set()) if str(symbol))
    symbol_to_id: dict[str, int] = {PAD_SYMBOL: PAD_ID}
    id_to_symbol: list[str] = [PAD_SYMBOL]
    block_metadata: list[dict[str, Any]] = []
    blocked_seen: set[str] = set()
    center_windows: list[list[int]] = []
    left_context: list[list[list[int]]] = []
    right_context: list[list[list[int]]] = []
    block_indices: list[int] = []
    center_starts: list[int] = []

    for block_index, block in enumerate(blocks):
        block_id = str(block.get("block_id") or f"block-{block_index + 1}")
        block_metadata.append(
            {
                "block_id": block_id,
                "source_ref": block.get("source_ref") or "",
                "visual_ref": block.get("visual_ref") or {},
            }
        )
        symbols = [str(symbol) for symbol in block.get("symbols") or []]
        eligibility = list(block.get("count_eligible") or [True] * len(symbols))
        eligible_ids: list[int] = []
        for index, symbol in enumerate(symbols):
            is_eligible = bool(eligibility[index]) if index < len(eligibility) else True
            if not is_eligible or symbol in blocked:
                blocked_seen.add(symbol)
                continue
            eligible_ids.append(_symbol_id(symbol, symbol_to_id, id_to_symbol))

        start = cfg.context_span_each_side
        end = len(eligible_ids) - cfg.context_span_each_side - cfg.center_size + 1
        if end <= start:
            continue
        for center_start in range(start, end):
            left_span = eligible_ids[center_start - cfg.context_span_each_side : center_start]
            right_start = center_start + cfg.center_size
            right_span = eligible_ids[right_start : right_start + cfg.context_span_each_side]
            center_windows.append(eligible_ids[center_start : center_start + cfg.center_size])
            left_context.append(_chunk_ids(left_span, cfg.context_clouds_each_side, cfg.context_cloud_size))
            right_context.append(_chunk_ids(right_span, cfg.context_clouds_each_side, cfg.context_cloud_size))
            block_indices.append(block_index)
            center_starts.append(center_start)

    return {
        "center_windows": np.asarray(center_windows, dtype=np.int64).reshape((-1, cfg.center_size)),
        "left_context": np.asarray(left_context, dtype=np.int64).reshape(
            (-1, cfg.context_clouds_each_side, cfg.context_cloud_size)
        ),
        "right_context": np.asarray(right_context, dtype=np.int64).reshape(
            (-1, cfg.context_clouds_each_side, cfg.context_cloud_size)
        ),
        "block_indices": np.asarray(block_indices, dtype=np.int32),
        "center_starts": np.asarray(center_starts, dtype=np.int64),
        "symbol_table": id_to_symbol,
        "block_metadata": block_metadata,
        "blocked_symbols": sorted(blocked_seen),
    }


def load_occular_tensor_shard(manifest_path: Path | str) -> dict[str, Any]:
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    tensor_path = Path(manifest["tensor_path"])
    if _hash_file(tensor_path) != manifest["tensor_sha256"]:
        raise ValueError("occular tensor shard hash mismatch")
    loaded = np.load(tensor_path, allow_pickle=False)
    return {
        "schema_version": "anchorworks_occular_tensor_shard_loaded@1",
        "manifest": manifest,
        "arrays": {name: loaded[name] for name in loaded.files},
    }


def build_occular_counts_from_tensor_shard(shard: dict[str, Any]) -> dict[str, Any]:
    manifest = shard["manifest"]
    arrays = shard["arrays"]
    symbol_table = list(manifest["symbol_table"])
    block_metadata = list(manifest["block_metadata"])
    config = manifest["config"]
    records: list[dict[str, Any]] = []
    counts: dict[str, dict[str, Any]] = {}

    for row_index, center_ids in enumerate(arrays["center_windows"]):
        center = [_symbol_from_id(symbol_table, int(symbol_id)) for symbol_id in center_ids]
        left_clouds = [
            [_symbol_from_id(symbol_table, int(symbol_id)) for symbol_id in cloud]
            for cloud in arrays["left_context"][row_index]
        ]
        right_clouds = [
            [_symbol_from_id(symbol_table, int(symbol_id)) for symbol_id in cloud]
            for cloud in arrays["right_context"][row_index]
        ]
        block = block_metadata[int(arrays["block_indices"][row_index])]
        center_key = " ".join(center)
        record = {
            "schema_version": "anchorworks_occular_cloud_record@1",
            "window_shape": config["window_shape"],
            "center_key": center_key,
            "center_hash": _center_hash(center),
            "center_symbols": center,
            "left_context_clouds": left_clouds,
            "right_context_clouds": right_clouds,
            "block_id": block["block_id"],
            "source_ref": block.get("source_ref") or "",
            "visual_ref": block.get("visual_ref") or {},
        }
        records.append(record)
        count = counts.setdefault(
            center_key,
            {
                "center_symbols": center,
                "center_hash": record["center_hash"],
                "observations": 0,
                "source_blocks": [],
            },
        )
        count["observations"] += 1
        if block["block_id"] not in count["source_blocks"]:
            count["source_blocks"].append(block["block_id"])

    return {
        "schema_version": "anchorworks_occular_cloud_counts@1",
        "config": config,
        "block_count": len(block_metadata),
        "record_count": len(records),
        "unique_center_count": len(counts),
        "records": records,
        "counts": counts,
        "blocked_symbols": list(manifest["blocked_symbols"]),
        "truth_boundary": {
            "source": "stored_visual_symbol_state",
            "normal_aw_text_counts": False,
            "phrase_authority": False,
            "symbolic_only": True,
        },
        "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
    }


def _symbol_id(symbol: str, symbol_to_id: dict[str, int], id_to_symbol: list[str]) -> int:
    if symbol in symbol_to_id:
        return symbol_to_id[symbol]
    symbol_to_id[symbol] = len(id_to_symbol)
    id_to_symbol.append(symbol)
    return symbol_to_id[symbol]


def _symbol_from_id(symbol_table: list[str], symbol_id: int) -> str:
    if symbol_id <= PAD_ID or symbol_id >= len(symbol_table):
        raise ValueError(f"invalid occular tensor symbol id: {symbol_id}")
    return str(symbol_table[symbol_id])


def _chunk_ids(symbol_ids: list[int], cloud_count: int, cloud_size: int) -> list[list[int]]:
    return [symbol_ids[index * cloud_size : (index + 1) * cloud_size] for index in range(cloud_count)]


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
