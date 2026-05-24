from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Any

from AnchorWorks.count_window import CountWindowConfig, count_window_preset


OCCULAR_CLOUD_SCHEMA_VERSION = "anchorworks_occular_cloud_counts@1"
DEFAULT_BLOCKED_SYMBOLS = {"__NULL__", "visual_unknown_glyph"}


@dataclass(frozen=True)
class OccularCloudConfig:
    context_clouds_each_side: int = 6
    context_cloud_size: int = 4
    center_size: int = 4
    max_lag_seconds: float = 15.0
    max_retries: int = 3

    @classmethod
    def from_window_contract(
        cls,
        contract: CountWindowConfig,
        *,
        max_lag_seconds: float = 15.0,
        max_retries: int = 3,
    ) -> "OccularCloudConfig":
        return cls(
            context_clouds_each_side=contract.left_context_units,
            context_cloud_size=contract.unit_size,
            center_size=contract.center_units,
            max_lag_seconds=max_lag_seconds,
            max_retries=max_retries,
        )

    @classmethod
    def default(cls) -> "OccularCloudConfig":
        return cls.from_window_contract(count_window_preset("occular_6x4_4_6x4"))

    @property
    def window_shape(self) -> str:
        return f"{self.context_clouds_each_side}x{self.context_cloud_size}-{self.center_size}-{self.context_clouds_each_side}x{self.context_cloud_size}"

    @property
    def context_span_each_side(self) -> int:
        return self.context_clouds_each_side * self.context_cloud_size

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["window_shape"] = self.window_shape
        row["context_span_each_side"] = self.context_span_each_side
        return row

    def count_window_contract(self) -> CountWindowConfig:
        return CountWindowConfig(
            left_context_units=self.context_clouds_each_side,
            center_units=self.center_size,
            right_context_units=self.context_clouds_each_side,
            unit_size=self.context_cloud_size,
            lane="occular",
            name=self.window_shape,
        )


def build_occular_cloud_counts(
    *,
    blocks: list[dict[str, Any]],
    config: OccularCloudConfig | None = None,
    blocked_symbols: set[str] | None = None,
) -> dict[str, Any]:
    """Build visual-local 6x4-4-6x4 symbolic count records."""

    cfg = config or OccularCloudConfig.default()
    blocked = set(DEFAULT_BLOCKED_SYMBOLS)
    blocked.update(str(symbol) for symbol in (blocked_symbols or set()) if str(symbol))

    records: list[dict[str, Any]] = []
    counts: dict[str, dict[str, Any]] = {}
    blocked_seen: set[str] = set()
    block_count = 0

    for block in blocks:
        block_count += 1
        block_id = str(block.get("block_id") or f"block-{block_count}")
        symbols = [str(symbol) for symbol in block.get("symbols") or []]
        eligibility = list(block.get("count_eligible") or [True] * len(symbols))
        eligible_symbols: list[str] = []
        for index, symbol in enumerate(symbols):
            is_eligible = bool(eligibility[index]) if index < len(eligibility) else True
            if not is_eligible or symbol in blocked:
                blocked_seen.add(symbol)
                continue
            eligible_symbols.append(symbol)

        for center_start in _valid_center_starts(len(eligible_symbols), cfg):
            center = eligible_symbols[center_start : center_start + cfg.center_size]
            left_span = eligible_symbols[center_start - cfg.context_span_each_side : center_start]
            right_start = center_start + cfg.center_size
            right_span = eligible_symbols[right_start : right_start + cfg.context_span_each_side]
            left_clouds = _chunk(left_span, cfg.context_cloud_size)
            right_clouds = _chunk(right_span, cfg.context_cloud_size)
            center_key = " ".join(center)
            record = {
                "schema_version": "anchorworks_occular_cloud_record@1",
                "window_shape": cfg.window_shape,
                "center_key": center_key,
                "center_hash": _center_hash(center),
                "center_symbols": center,
                "left_context_clouds": left_clouds,
                "right_context_clouds": right_clouds,
                "block_id": block_id,
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
            if block_id not in count["source_blocks"]:
                count["source_blocks"].append(block_id)

    return {
        "schema_version": OCCULAR_CLOUD_SCHEMA_VERSION,
        "config": cfg.to_dict(),
        "window_contract": cfg.count_window_contract().to_dict(),
        "block_count": block_count,
        "record_count": len(records),
        "unique_center_count": len(counts),
        "records": records,
        "counts": counts,
        "blocked_symbols": sorted(blocked_seen),
        "truth_boundary": {
            "source": "stored_visual_symbol_state",
            "normal_aw_text_counts": False,
            "phrase_authority": False,
            "symbolic_only": True,
        },
        "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
    }


def evaluate_trailing_count_status(
    *,
    capture_cursor: dict[str, Any],
    count_cursor: dict[str, Any],
    lag_seconds: float,
    max_lag_seconds: float = 15.0,
    retry_index: int = 0,
    max_retries: int = 3,
) -> dict[str, Any]:
    if lag_seconds <= max_lag_seconds:
        action = "continue"
        reason = "count_worker_within_lag_budget"
    elif retry_index < max_retries:
        action = "wait_retry"
        reason = "count_worker_lagging"
    else:
        action = "graceful_stop"
        reason = "count_worker_lag_exceeded_retries"
    return {
        "schema_version": "anchorworks_occular_cloud_trailing_count_status@1",
        "action": action,
        "reason": reason,
        "lag_seconds": float(lag_seconds),
        "max_lag_seconds": float(max_lag_seconds),
        "retry_index": int(retry_index),
        "max_retries": int(max_retries),
        "capture_cursor": dict(capture_cursor),
        "count_cursor": dict(count_cursor),
        "pickup_cursor": dict(count_cursor),
        "deterministic_resume_required": action == "graceful_stop",
    }


def build_video_modality_switch(
    *,
    parent_document_id: str,
    page_index: int,
    region_id: str,
    video_ref: dict[str, Any],
    document_cursor: dict[str, Any],
    config: OccularCloudConfig | None = None,
) -> dict[str, Any]:
    cfg = config or OccularCloudConfig()
    return {
        "schema_version": "anchorworks_occular_modality_switch@1",
        "record_kind": "anchorworks_occular_video_modality_switch",
        "intake_authority": "video",
        "parent": {
            "document_id": str(parent_document_id),
            "page_index": int(page_index),
            "region_id": str(region_id),
        },
        "video_ref": dict(video_ref),
        "video_cursor": {
            "frame_index": 0,
            "state_chunk_id": 0,
            "count_cursor": 0,
        },
        "parent_pickup_cursor": dict(document_cursor),
        "resume_parent_after_video": True,
        "counts_policy": {
            "trailing_delay_seconds": int(cfg.max_lag_seconds),
            "max_retries": cfg.max_retries,
            "window_shape": cfg.window_shape,
        },
        "truth_boundary": {
            "video_detached_from_document": False,
            "video_is_child_visual_stream": True,
            "recognition_must_read_state": True,
        },
        "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
    }


def _valid_center_starts(symbol_count: int, cfg: OccularCloudConfig) -> range:
    start = cfg.context_span_each_side
    end = symbol_count - cfg.context_span_each_side - cfg.center_size + 1
    if end <= start:
        return range(0)
    return range(start, end)


def _chunk(symbols: list[str], size: int) -> list[list[str]]:
    return [symbols[index : index + size] for index in range(0, len(symbols), size)]


def _center_hash(symbols: list[str]) -> str:
    payload = "\x1f".join(symbols).encode("utf-8")
    return "occular_center_" + hashlib.sha256(payload).hexdigest()[:24]
