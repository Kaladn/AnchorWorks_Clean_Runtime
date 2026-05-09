from __future__ import annotations

import hashlib
from typing import Any

from .visual_region_map import REGION_MAP_CONTRACT_VERSION


NO_WRITE_POLICY = {"maps": False, "counts": False, "lifetime": False, "lexicon": False}


def generate_basic_visual_regions(
    visual_manifest: dict[str, Any],
    *,
    captions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    source = visual_manifest.get("source") or {}
    visual_record_id = str(source.get("visual_record_id") or "")
    source_hash = str(source.get("sha256") or "")
    width = int(source.get("width") or 0)
    height = int(source.get("height") or 0)
    region_map_id = "region_map_" + hashlib.sha256(f"{visual_record_id}::{source_hash}::basic".encode("utf-8")).hexdigest()[:16]
    regions: list[dict[str, Any]] = [
        {
            "region_id": "region_full_image_0",
            "shape": "rectangle",
            "bounds": {"x": 0, "y": 0, "width": width, "height": height},
            "kind_candidate": "full_image",
            "backend_id": "anchorworks_basic_region_generator",
            "confidence": 1.0 if width and height else 0.0,
            "approval_status": "candidate",
        }
    ]
    for index, caption in enumerate(captions or [], start=1):
        regions.append({
            "region_id": f"region_caption_{index}",
            "shape": "rectangle",
            "bounds": {"x": 0, "y": height, "width": width, "height": 0},
            "kind_candidate": "caption",
            "backend_id": "source_layout_caption_linker",
            "confidence": 1.0,
            "approval_status": "candidate",
            "source_text": caption.get("text") or "",
            "line_start": caption.get("line_start"),
            "line_end": caption.get("line_end"),
        })
    return {
        "schema_version": REGION_MAP_CONTRACT_VERSION,
        "visual_record_id": visual_record_id,
        "region_map_id": region_map_id,
        "coordinate_space": "native_pixels",
        "backend_id": "anchorworks_basic_region_generator",
        "regions": regions,
        "relations": [],
        "notes": [
            "Basic region generation creates source-local candidate regions only.",
            "No object, OCR, chart, or scene claims are produced.",
        ],
        "writes_allowed": dict(NO_WRITE_POLICY),
    }
