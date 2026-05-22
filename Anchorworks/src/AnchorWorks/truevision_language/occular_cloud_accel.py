from __future__ import annotations

import hashlib
import json
import platform
from dataclasses import asdict, dataclass
from typing import Any, Literal

from .occular_tensor_store import write_occular_tensor_shard
from .occular_cloud import (
    DEFAULT_BLOCKED_SYMBOLS,
    OccularCloudConfig,
    _center_hash,
    _chunk,
    build_occular_cloud_counts,
)


OccularCloudBackend = Literal["cpu", "cuda", "openvino", "oneapi", "auto"]


@dataclass(frozen=True)
class OccularCloudExecutionReceipt:
    schema_version: str
    backend_requested: str
    backend: str
    device: str
    batch_size: int
    window_shape: str
    fallback_used: bool
    fallback_reason: str | None
    input_hash: str
    output_hash: str
    determinism: dict[str, str]
    tensor_store: dict[str, Any]
    writes_allowed: dict[str, bool]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def probe_occular_cloud_backends() -> dict[str, Any]:
    """Report accelerator visibility without claiming authority over output."""

    torch_info = _probe_torch()
    openvino_info = _probe_openvino()
    return {
        "schema_version": "anchorworks_occular_cloud_backend_probe@1",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "backends": {
            "cpu": {"available": True, "device": "cpu"},
            "torch": torch_info,
            "cuda": {
                "available": bool(torch_info.get("cuda_available")),
                "device_count": int(torch_info.get("cuda_device_count") or 0),
                "devices": list(torch_info.get("cuda_devices") or []),
            },
            "openvino": openvino_info,
            "oneapi": {
                "available": bool(openvino_info.get("gpu_available")),
                "via": "openvino" if openvino_info.get("gpu_available") else None,
            },
        },
    }


def build_occular_cloud_counts_accelerated(
    *,
    blocks: list[dict[str, Any]],
    config: OccularCloudConfig | None = None,
    blocked_symbols: set[str] | None = None,
    backend: OccularCloudBackend = "auto",
    batch_size: int = 4096,
    tensor_store_root: Any | None = None,
    tensor_shard_id: str | None = None,
) -> dict[str, Any]:
    """Build Occular Cloud counts through a selectable execution lane.

    The returned counts payload is intentionally identical to the CPU authority
    payload. The execution receipt sits beside it so speed/device facts never
    become symbolic truth.
    """

    cfg = config or OccularCloudConfig()
    selected_backend, device, fallback_used, fallback_reason = _select_backend(backend)
    input_hash = _hash_payload(
        {
            "blocks": blocks,
            "config": cfg.to_dict(),
            "blocked_symbols": sorted(str(symbol) for symbol in (blocked_symbols or set())),
        }
    )

    if selected_backend == "cpu":
        counts_payload = build_occular_cloud_counts(blocks=blocks, config=cfg, blocked_symbols=blocked_symbols)
    else:
        try:
            counts_payload = _build_with_tensor_lane(
                blocks=blocks,
                config=cfg,
                blocked_symbols=blocked_symbols,
                backend=selected_backend,
                device=device,
                batch_size=batch_size,
            )
        except Exception as exc:
            selected_backend = "cpu"
            device = "cpu"
            fallback_used = True
            fallback_reason = f"accelerated backend failed and fell back to cpu: {exc}"
            counts_payload = build_occular_cloud_counts(blocks=blocks, config=cfg, blocked_symbols=blocked_symbols)

    output_hash = _hash_payload(counts_payload)
    tensor_store = _maybe_write_tensor_store(
        root=tensor_store_root,
        shard_id=tensor_shard_id,
        blocks=blocks,
        config=cfg,
        blocked_symbols=blocked_symbols,
        backend=selected_backend,
    )
    receipt = OccularCloudExecutionReceipt(
        schema_version="anchorworks_occular_cloud_execution_receipt@1",
        backend_requested=backend,
        backend=selected_backend,
        device=device,
        batch_size=int(batch_size),
        window_shape=cfg.window_shape,
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
        input_hash=input_hash,
        output_hash=output_hash,
        determinism={"input_hash": input_hash, "output_hash": output_hash},
        tensor_store=tensor_store,
        writes_allowed={"maps": False, "counts": False, "lifetime": False, "lexicon": False},
    )
    return {
        "schema_version": "anchorworks_occular_cloud_accel_run@1",
        "counts_payload": counts_payload,
        "execution": receipt.to_dict(),
    }


def _maybe_write_tensor_store(
    *,
    root: Any | None,
    shard_id: str | None,
    blocks: list[dict[str, Any]],
    config: OccularCloudConfig,
    blocked_symbols: set[str] | None,
    backend: str,
) -> dict[str, Any]:
    if root is None and not shard_id:
        return {"written": False, "reason": "tensor store not requested"}
    if not shard_id:
        shard_id = "occular-auto-" + hashlib.sha256(_hash_payload(blocks).encode("ascii")).hexdigest()[:16]
    written = write_occular_tensor_shard(
        root=root,
        shard_id=shard_id,
        blocks=blocks,
        config=config,
        blocked_symbols=blocked_symbols,
        backend=backend,
    )
    return {"written": True, **written}


def _build_with_tensor_lane(
    *,
    blocks: list[dict[str, Any]],
    config: OccularCloudConfig,
    blocked_symbols: set[str] | None,
    backend: str,
    device: str,
    batch_size: int,
) -> dict[str, Any]:
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

        center_starts = _tensor_center_starts(
            symbol_count=len(eligible_symbols),
            config=config,
            backend=backend,
            device=device,
            batch_size=batch_size,
        )
        for center_start in center_starts:
            center = eligible_symbols[center_start : center_start + config.center_size]
            left_span = eligible_symbols[center_start - config.context_span_each_side : center_start]
            right_start = center_start + config.center_size
            right_span = eligible_symbols[right_start : right_start + config.context_span_each_side]
            left_clouds = _chunk(left_span, config.context_cloud_size)
            right_clouds = _chunk(right_span, config.context_cloud_size)
            center_key = " ".join(center)
            record = {
                "schema_version": "anchorworks_occular_cloud_record@1",
                "window_shape": config.window_shape,
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
        "schema_version": "anchorworks_occular_cloud_counts@1",
        "config": config.to_dict(),
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


def _tensor_center_starts(
    *,
    symbol_count: int,
    config: OccularCloudConfig,
    backend: str,
    device: str,
    batch_size: int,
) -> list[int]:
    start = config.context_span_each_side
    end = symbol_count - config.context_span_each_side - config.center_size + 1
    if end <= start:
        return []

    if backend == "cuda":
        import torch

        starts = torch.arange(start, end, dtype=torch.int64, device=device)
        return [int(value) for value in starts.cpu().tolist()]

    if backend in {"openvino", "oneapi"}:
        return _openvino_center_starts(start=start, end=end, device=device)

    return list(range(start, end))


def _openvino_center_starts(*, start: int, end: int, device: str) -> list[int]:
    import numpy as np
    import openvino as ov
    from openvino import opset8 as ops

    starts = np.arange(start, end, dtype=np.int32)
    if starts.size == 0:
        return []

    parameter = ops.parameter(starts.shape, dtype=np.int32, name="center_starts")
    model = ov.Model([ops.result(parameter)], [parameter], "occular_cloud_center_start_identity")
    compiled = ov.Core().compile_model(model, device)
    output = compiled([starts])[compiled.output(0)]
    return [int(value) for value in np.asarray(output, dtype=np.int32).tolist()]


def _select_backend(requested: str) -> tuple[str, str, bool, str | None]:
    normalized = requested.lower().strip()
    probe = probe_occular_cloud_backends()

    if normalized == "cpu":
        return "cpu", "cpu", False, None

    cuda = probe["backends"]["cuda"]
    openvino = probe["backends"]["openvino"]
    if normalized == "auto":
        if cuda["available"]:
            return "cuda", "cuda:0", False, None
        if openvino.get("gpu_available"):
            return "openvino", str(openvino.get("gpu_device") or "GPU"), False, None
        return "cpu", "cpu", True, "auto found no visible GPU execution backend"

    if normalized == "cuda":
        if cuda["available"]:
            return "cuda", "cuda:0", False, None
        return "cpu", "cpu", True, "cuda backend requested but torch cuda is unavailable"

    if normalized in {"openvino", "oneapi"}:
        if openvino.get("gpu_available"):
            return normalized, str(openvino.get("gpu_device") or "GPU"), False, None
        return "cpu", "cpu", True, f"{normalized} backend requested but OpenVINO GPU is unavailable"

    return "cpu", "cpu", True, f"unknown backend requested: {requested}"


def _probe_torch() -> dict[str, Any]:
    try:
        import torch

        device_count = int(torch.cuda.device_count()) if torch.cuda.is_available() else 0
        devices = [torch.cuda.get_device_name(index) for index in range(device_count)]
        return {
            "available": True,
            "version": str(torch.__version__),
            "cuda_available": bool(torch.cuda.is_available()),
            "cuda_device_count": device_count,
            "cuda_devices": devices,
        }
    except Exception as exc:  # pragma: no cover - depends on local install
        return {"available": False, "error": str(exc)}


def _probe_openvino() -> dict[str, Any]:
    try:
        import openvino as ov

        core = ov.Core()
        devices = list(core.available_devices)
        gpu_devices = [device for device in devices if str(device).upper().startswith("GPU")]
        return {
            "available": True,
            "devices": devices,
            "gpu_available": bool(gpu_devices),
            "gpu_device": gpu_devices[0] if gpu_devices else None,
        }
    except Exception as exc:  # pragma: no cover - depends on local install
        return {"available": False, "gpu_available": False, "error": str(exc)}


def _hash_payload(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
