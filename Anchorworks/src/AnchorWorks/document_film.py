from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import Any

from .visual_manifest import manifest_from_image_bytes
from .visual_recognition_layer import create_empty_recognition_layer
from .visual_region_map import create_empty_region_map


DOCUMENT_FILM_CONTRACT_VERSION = "anchorworks_document_film@1"
NO_WRITE_POLICY = {"maps": False, "counts": False, "lifetime": False, "lexicon": False}


def build_document_film_from_images(
    *,
    source_document_id: str,
    source_path: str,
    source_hash: str,
    frames: list[dict[str, Any]],
    frame_rate: float = 1.0,
    duplicate_policy: str = "all_pages_report_duplicates",
) -> dict[str, Any]:
    """Build a preview-only document-film packet from ordered page/frame images."""

    if not frames:
        raise ValueError("document film requires at least one image frame")

    frame_rows: list[dict[str, Any]] = []
    hash_counts: dict[str, int] = {}
    safe_source_id = str(source_document_id or _document_id(source_path, source_hash))
    for ordinal, frame in enumerate(frames):
        raw = frame.get("image_bytes")
        if not isinstance(raw, (bytes, bytearray)) or not raw:
            raise ValueError("document film frame requires image_bytes")
        image_bytes = bytes(raw)
        page_number = int(frame.get("page_number") or ordinal + 1)
        page_index = int(frame.get("page_index") if frame.get("page_index") is not None else page_number - 1)
        frame_index = int(frame.get("frame_index") if frame.get("frame_index") is not None else ordinal)
        timestamp = frame.get("frame_timestamp_ms")
        if timestamp is None:
            timestamp = int(round((frame_index * 1000.0) / frame_rate)) if frame_rate else frame_index
        frame_timestamp_ms = int(timestamp)
        source_name = str(frame.get("source_name") or f"{Path(source_path).stem}_page_{page_number:04d}.image")

        manifest = manifest_from_image_bytes(
            image_bytes,
            source_name,
            frame_index=frame_index,
            frame_timestamp_ms=frame_timestamp_ms,
            page_index=page_index,
            page_number=page_number,
            source_document_id=safe_source_id,
        )
        region_map = create_empty_region_map(manifest)
        recognition_layer = create_empty_recognition_layer(manifest, region_map)
        source = manifest.source
        hash_counts[source.sha256] = hash_counts.get(source.sha256, 0) + 1
        frame_rows.append(
            {
                "frame_id": _frame_id(safe_source_id, frame_index, page_number, source.sha256),
                "frame_ordinal": ordinal,
                "frame_index": frame_index,
                "frame_timestamp_ms": frame_timestamp_ms,
                "page_index": page_index,
                "page_number": page_number,
                "source_path_ref": str(frame.get("source_path_ref") or f"{source_path}#page={page_number}#frame={frame_index}"),
                "visual_record_id": source.visual_record_id,
                "visual_content_hash": source.sha256,
                "kind": "pdf_page_frame",
                "width": source.width,
                "height": source.height,
                "aspect_ratio": source.aspect_ratio,
                "color_mode": source.color_mode,
                "file_format": source.file_format,
                "geometry_status": "known" if source.width and source.height else "unknown",
                "region_status": "empty",
                "recognition_status": "not_run",
                "visual_manifest": manifest.to_dict(),
                "visual_region_map": region_map.to_dict(),
                "visual_recognition_layer": recognition_layer.to_dict(),
                "writes_allowed": dict(NO_WRITE_POLICY),
            }
        )

    duplicate_hashes = {digest: count for digest, count in sorted(hash_counts.items()) if count > 1}
    return {
        "schema_version": DOCUMENT_FILM_CONTRACT_VERSION,
        "document_film_id": _film_id(safe_source_id, source_hash, len(frame_rows)),
        "source_document_id": safe_source_id,
        "source_pdf": source_path,
        "source_hash": source_hash,
        "frame_count": len(frame_rows),
        "frame_rate": frame_rate,
        "duplicate_policy": duplicate_policy,
        "duplicate_frame_hashes": duplicate_hashes,
        "duplicate_status": "reported" if duplicate_hashes else "none",
        "frames": frame_rows,
        "writes_allowed": dict(NO_WRITE_POLICY),
        "notes": [
            "PDF pages are preserved as visual evidence frames.",
            "Region maps and recognition layers may be empty.",
            "Document film preview does not write maps, counts, lifetime, or lexicon.",
        ],
    }


def extract_pdf_document_film(
    pdf_path: str | Path,
    *,
    frame_rate: float = 1.0,
    duplicate_policy: str = "all_pages_report_duplicates",
) -> dict[str, Any]:
    path = Path(pdf_path).expanduser().resolve()
    raw = path.read_bytes()
    return extract_pdf_document_film_from_bytes(
        raw,
        source_name=path.name,
        source_path=str(path),
        frame_rate=frame_rate,
        duplicate_policy=duplicate_policy,
    )


def extract_pdf_document_film_from_bytes(
    raw: bytes,
    *,
    source_name: str,
    source_path: str = "",
    frame_rate: float = 1.0,
    duplicate_policy: str = "all_pages_report_duplicates",
) -> dict[str, Any]:
    try:
        from pypdf import PdfReader
    except Exception as exc:  # pragma: no cover - depends on optional runtime packages
        raise ValueError("PDF document film extraction needs pypdf installed") from exc

    source_ref = source_path or source_name
    source_hash = hashlib.sha256(raw).hexdigest()
    source_document_id = _document_id(source_ref, source_hash)
    try:
        reader = PdfReader(io.BytesIO(raw))
    except Exception as exc:
        raise ValueError("PDF document film could not read PDF") from exc

    frames: list[dict[str, Any]] = []
    for page_index, page in enumerate(reader.pages):
        try:
            images = list(page.images)
        except Exception:
            images = []
        for image_index, image in enumerate(images[:1]):
            image_bytes = bytes(image.data)
            image_name = Path(str(getattr(image, "name", "") or f"page_{page_index + 1:04d}.image")).name
            suffix = Path(image_name).suffix
            if not suffix:
                suffix = ".image"
            frames.append(
                {
                    "page_index": page_index,
                    "page_number": page_index + 1,
                    "frame_index": len(frames),
                    "frame_timestamp_ms": int(round((len(frames) * 1000.0) / frame_rate)) if frame_rate else len(frames),
                    "source_name": f"{Path(source_name).stem}_page_{page_index + 1:04d}{suffix}",
                    "source_path_ref": f"{source_ref}#page={page_index + 1}#image={image_index + 1}",
                    "image_bytes": image_bytes,
                }
            )
    if not frames:
        raise ValueError("PDF document film found no extractable page images")
    packet = build_document_film_from_images(
        source_document_id=source_document_id,
        source_path=source_ref,
        source_hash=source_hash,
        frames=frames,
        frame_rate=frame_rate,
        duplicate_policy=duplicate_policy,
    )
    packet["source_page_count"] = len(reader.pages)
    packet["extracted_page_frame_count"] = len(frames)
    return packet


def _document_id(source_path: str, source_hash: str) -> str:
    seed = f"anchorworks_document_film@1::{source_path}::{source_hash}"
    return "docfilm_source_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def _film_id(source_document_id: str, source_hash: str, frame_count: int) -> str:
    seed = f"anchorworks_document_film@1::{source_document_id}::{source_hash}::{frame_count}"
    return "document_film_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def _frame_id(source_document_id: str, frame_index: int, page_number: int, content_hash: str) -> str:
    seed = f"anchorworks_document_frame@1::{source_document_id}::{frame_index}::{page_number}::{content_hash}"
    return "film_frame_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
