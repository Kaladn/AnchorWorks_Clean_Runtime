from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


CELL_FEATURE_NAMES = [
    "rgb_mean_r",
    "rgb_mean_g",
    "rgb_mean_b",
    "rgb_std_r",
    "rgb_std_g",
    "rgb_std_b",
    "hsv_mean_h",
    "hsv_mean_s",
    "hsv_mean_v",
    "luma_mean",
    "luma_std",
    "saturation_mean",
    "delta_luma_abs",
    "edge_density",
    "texture_energy",
    "motion_energy",
]


def record_document_state_movie(
    *,
    source_id: str,
    page_frames: list[np.ndarray],
    output_root: Path,
    run_id: str,
    frames_per_page: int = 3,
    fps: float = 3.0,
    grid_shape: tuple[int, int] = (90, 160),
) -> dict[str, Any]:
    """Record document pages as a TrueVision-shaped state movie."""

    if frames_per_page < 1:
        raise ValueError("frames_per_page must be at least 1")
    if fps <= 0:
        raise ValueError("fps must be positive")
    if not page_frames:
        raise ValueError("page_frames must not be empty")

    output_root = Path(output_root)
    run_dir = output_root / run_id
    cell_dir = run_dir / "cell_state_npz"
    cell_dir.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []
    cell_frames: list[np.ndarray] = []
    frame_numbers: list[int] = []
    frame_pages: list[dict[str, int]] = []
    previous_luma: np.ndarray | None = None
    frame_index = 0

    for page_index, page in enumerate(page_frames):
        start = frame_index
        for repeat_index in range(frames_per_page):
            cells, previous_luma = build_page_cell_state(
                page,
                grid_shape=grid_shape,
                previous_luma=previous_luma if repeat_index else None,
            )
            cell_frames.append(cells)
            frame_numbers.append(frame_index)
            elapsed_seconds = frame_index / fps
            records.append(
                {
                    "schema_version": 1,
                    "record_kind": "anchorworks_truevision_document_state_frame",
                    "source_id": str(source_id),
                    "run_id": str(run_id),
                    "observed_at_utc": _utc_now(),
                    "frame_index": frame_index,
                    "frame_number": frame_index,
                    "page_index": page_index,
                    "page_number": page_index + 1,
                    "page_repeat_index": repeat_index,
                    "elapsed_seconds": round(elapsed_seconds, 6),
                    "fps": fps,
                    "screen_energy": float(cells[:, :, CELL_FEATURE_NAMES.index("delta_luma_abs")].sum()),
                    "raw_frame_saved": False,
                    "raw_grid_saved": False,
                    "cell_state_ref": {
                        "format": "npz_compressed_float32",
                        "chunk_id": 0,
                        "chunk_frame_index": frame_index,
                        "grid_shape": list(grid_shape),
                        "feature_names": list(CELL_FEATURE_NAMES),
                        "feature_count": len(CELL_FEATURE_NAMES),
                    },
                }
            )
            frame_index += 1
        frame_pages.append(
            {
                "frame_start": start,
                "frame_end": frame_index - 1,
                "page_index": page_index,
                "page_number": page_index + 1,
            }
        )

    chunk_path = cell_dir / f"{run_id}_cells_0000.npz"
    np.savez_compressed(
        chunk_path,
        cell_state=np.stack(cell_frames).astype(np.float32),
        frame_numbers=np.asarray(frame_numbers, dtype=np.int32),
        feature_names=np.asarray(CELL_FEATURE_NAMES),
    )
    records_path = run_dir / f"{run_id}_records.jsonl"
    records_path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in records) + "\n", encoding="utf-8")

    summary = {
        "schema_version": 1,
        "record_kind": "anchorworks_truevision_document_state_summary",
        "source_id": str(source_id),
        "run_id": str(run_id),
        "frame_count": len(records),
        "page_count": len(page_frames),
        "duration_seconds": round((len(records) - 1) / fps if records else 0.0, 6),
        "geometry": {
            "frame_shape": [int(page_frames[0].shape[0]), int(page_frames[0].shape[1])],
            "grid_shape": list(grid_shape),
        },
        "raw_frame_saved": False,
        "raw_grid_saved": False,
    }
    summary_path = run_dir / f"{run_id}_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")

    manifest = {
        "schema_version": 1,
        "record_kind": "anchorworks_truevision_document_state_movie",
        "source_id": str(source_id),
        "run_id": str(run_id),
        "created_at_utc": _utc_now(),
        "records": {"jsonl_path": str(records_path), "frame_count": len(records)},
        "summary_json": str(summary_path),
        "config": {
            "source_kind": "document_pages_as_state_movie",
            "frames_per_page": frames_per_page,
            "fps": fps,
            "grid_shape_rows_cols": list(grid_shape),
            "page_count": len(page_frames),
            "cell_feature_names": list(CELL_FEATURE_NAMES),
        },
        "frame_pages": frame_pages,
        "cell_state": {
            "enabled": True,
            "format": "npz_compressed_float32",
            "feature_names": list(CELL_FEATURE_NAMES),
            "chunks": [
                {
                    "chunk_id": 0,
                    "path": str(chunk_path),
                    "format": "npz_compressed_float32",
                    "shape": [len(records), grid_shape[0], grid_shape[1], len(CELL_FEATURE_NAMES)],
                    "frames": len(records),
                    "grid_shape": list(grid_shape),
                    "feature_count": len(CELL_FEATURE_NAMES),
                    "sha256": _sha256_file(chunk_path),
                }
            ],
        },
        "boundary": {
            "raw_frame_saved": False,
            "generated_media_is_evidence": False,
            "recognition_must_read_state": True,
            "notes": "Document pages are recorded as repeated TrueVision cell-state frames. Recognition reads state chunks, not source pixels.",
        },
    }
    manifest_path = run_dir / f"{run_id}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False), encoding="utf-8")
    return {
        "run_id": str(run_id),
        "run_dir": str(run_dir),
        "records_jsonl": str(records_path),
        "summary_json": str(summary_path),
        "manifest_json": str(manifest_path),
        "cell_state_npz": str(chunk_path),
        "frame_count": len(records),
        "page_count": len(page_frames),
    }


def build_page_cell_state(
    frame: np.ndarray,
    *,
    grid_shape: tuple[int, int],
    previous_luma: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    frame_rgb = _fit_to_grid(np.asarray(frame, dtype=np.uint8), grid_shape)
    rgb = frame_rgb.astype(np.float32)
    luma = (0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]).astype(np.float32)
    rgb_std = np.zeros_like(rgb, dtype=np.float32)
    luma_std = np.zeros_like(luma, dtype=np.float32)
    saturation = (rgb.max(axis=2) - rgb.min(axis=2)).astype(np.float32)
    delta = np.zeros_like(luma) if previous_luma is None or previous_luma.shape != luma.shape else np.abs(luma - previous_luma)
    edge = _edge_density(luma)
    cells = np.dstack(
        [
            rgb[:, :, 0],
            rgb[:, :, 1],
            rgb[:, :, 2],
            rgb_std[:, :, 0],
            rgb_std[:, :, 1],
            rgb_std[:, :, 2],
            np.zeros_like(luma),
            saturation,
            rgb.max(axis=2),
            luma,
            luma_std,
            saturation,
            delta,
            edge,
            luma_std,
            delta,
        ]
    ).astype(np.float32)
    return cells, luma


def extract_black_glyph_patterns_from_state_movie(
    *,
    manifest_path: Path,
    frame_index: int = 0,
    luma_threshold: float = 128.0,
) -> list[dict[str, Any]]:
    """Extract connected black-cell glyph patterns from stored state only."""

    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    chunk = manifest["cell_state"]["chunks"][0]
    with np.load(chunk["path"], allow_pickle=False) as data:
        state = np.asarray(data["cell_state"], dtype=np.float32)
    cells = state[frame_index]
    luma = cells[:, :, CELL_FEATURE_NAMES.index("luma_mean")]
    mask = luma < float(luma_threshold)
    components = _connected_components(mask)
    rows: list[dict[str, Any]] = []
    for order, component in enumerate(components):
        ys = [cell[0] for cell in component]
        xs = [cell[1] for cell in component]
        top, bottom = min(ys), max(ys)
        left, right = min(xs), max(xs)
        pattern: list[str] = []
        points = set(component)
        for y in range(top, bottom + 1):
            pattern.append("".join("1" if (y, x) in points else "0" for x in range(left, right + 1)))
        rows.append(
            {
                "order": order,
                "pattern": pattern,
                "bbox": {"x": left, "y": top, "w": right - left + 1, "h": bottom - top + 1},
                "source": "stored_cell_state_luma",
            }
        )
    return rows


def _fit_to_grid(frame: np.ndarray, grid_shape: tuple[int, int]) -> np.ndarray:
    rows, cols = grid_shape
    if frame.shape[0] == rows and frame.shape[1] == cols:
        return frame[:, :, :3]
    y_idx = np.linspace(0, frame.shape[0] - 1, rows).round().astype(int)
    x_idx = np.linspace(0, frame.shape[1] - 1, cols).round().astype(int)
    return frame[y_idx][:, x_idx, :3]


def _edge_density(luma: np.ndarray) -> np.ndarray:
    vertical = np.zeros_like(luma)
    horizontal = np.zeros_like(luma)
    vertical[:, 1:] = np.abs(luma[:, 1:] - luma[:, :-1])
    horizontal[1:, :] = np.abs(luma[1:, :] - luma[:-1, :])
    return np.clip((vertical + horizontal) / 255.0, 0.0, 1.0).astype(np.float32)


def _connected_components(mask: np.ndarray) -> list[list[tuple[int, int]]]:
    visited = np.zeros(mask.shape, dtype=bool)
    components: list[list[tuple[int, int]]] = []
    rows, cols = mask.shape
    for y in range(rows):
        for x in range(cols):
            if not mask[y, x] or visited[y, x]:
                continue
            stack = [(y, x)]
            visited[y, x] = True
            component: list[tuple[int, int]] = []
            while stack:
                cy, cx = stack.pop()
                component.append((cy, cx))
                for ny in range(cy - 1, cy + 2):
                    for nx in range(cx - 1, cx + 2):
                        if ny == cy and nx == cx:
                            continue
                        if 0 <= ny < rows and 0 <= nx < cols and mask[ny, nx] and not visited[ny, nx]:
                            visited[ny, nx] = True
                            stack.append((ny, nx))
            components.append(component)
    components.sort(key=lambda cells: (min(y for y, _x in cells), min(x for _y, x in cells)))
    return components


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()
