from __future__ import annotations

from typing import Any


OCR_CANDIDATE_LAYER_VERSION = "anchorworks_ocr_candidate_layer@1"
OCR_ALLOWED_COORDINATE_SPACES = {"native_pixels", "grid_cells"}
NO_WRITE_POLICY = {"maps": False, "counts": False, "lifetime": False, "lexicon": False}


def create_ocr_backend_capability(backend_id: str, provider: str = "local") -> dict[str, Any]:
    return {
        "backend_id": str(backend_id or "ocr_backend"),
        "backend_type": "ocr_text",
        "provider": provider,
        "inputs_supported": ["image", "video_frame"],
        "outputs_supported": ["ocr_text", "bilateral_text_region"],
        "coordinate_space": "native_pixels",
        "distorts_source": False,
        "writes_allowed": dict(NO_WRITE_POLICY),
    }


def validate_ocr_candidate_layer(record: dict[str, Any]) -> None:
    required = {"schema_version", "backend", "visual_record_id", "candidates", "writes_allowed"}
    missing = sorted(required.difference(record))
    if missing:
        raise ValueError(f"OCR candidate layer missing required fields: {', '.join(missing)}")
    if record["schema_version"] != OCR_CANDIDATE_LAYER_VERSION:
        raise ValueError("OCR candidate layer contract version mismatch")
    if record["writes_allowed"] != NO_WRITE_POLICY:
        raise ValueError("OCR candidate layer cannot allow map/count/lifetime/lexicon writes")
    backend = record["backend"]
    if not isinstance(backend, dict) or backend.get("writes_allowed") != NO_WRITE_POLICY:
        raise ValueError("OCR backend capability must be write locked")
    if not isinstance(record["candidates"], list):
        raise ValueError("OCR candidates must be a list")
    for candidate in record["candidates"]:
        _validate_candidate(candidate)


def _validate_candidate(candidate: dict[str, Any]) -> None:
    required = {"candidate_id", "text", "confidence", "coordinate_space"}
    missing = sorted(required.difference(candidate))
    if missing:
        raise ValueError(f"OCR candidate missing required fields: {', '.join(missing)}")
    confidence = float(candidate["confidence"])
    if confidence < 0.0 or confidence > 1.0:
        raise ValueError("OCR confidence must be between 0 and 1")
    if candidate["coordinate_space"] not in OCR_ALLOWED_COORDINATE_SPACES:
        raise ValueError("OCR candidate coordinate space is not allowed")
