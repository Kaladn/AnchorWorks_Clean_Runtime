from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any

from .visual_manifest import VisualIntakeManifest, VisualWritePolicy
from .visual_region_map import VisualRegionMap


RECOGNITION_LAYER_CONTRACT_VERSION = "anchorworks_visual_recognition_layer@1"
RECOGNITION_BACKEND_ID = "anchorworks_recognition_schema"
ALLOWED_CANDIDATE_TYPES = {
    "ocr_text",
    "object",
    "diagram_element",
    "chart_element",
    "table_structure",
    "ui_element",
    "frame_state_change",
    "symbolic_note",
}


def _recognition_layer_id(visual_record_id: str, region_map_id: str) -> str:
    seed = f"{RECOGNITION_LAYER_CONTRACT_VERSION}::{visual_record_id}::{region_map_id}"
    return "recognition_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class RecognitionCandidate:
    candidate_id: str
    candidate_type: str
    region_id: str | None = None
    value: dict[str, Any] = field(default_factory=dict)
    confidence: float | None = None
    backend_id: str = RECOGNITION_BACKEND_ID
    evidence_refs: list[str] = field(default_factory=list)
    approval_status: str = "candidate"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VisualRecognitionLayer:
    contract_version: str
    visual_record_id: str
    region_map_id: str
    recognition_layer_id: str
    source_hash: str
    backend_id: str = RECOGNITION_BACKEND_ID
    candidates: list[RecognitionCandidate] = field(default_factory=list)
    approval_status: str = "candidate"
    writes_allowed: VisualWritePolicy = field(default_factory=VisualWritePolicy)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "visual_record_id": self.visual_record_id,
            "region_map_id": self.region_map_id,
            "recognition_layer_id": self.recognition_layer_id,
            "source_hash": self.source_hash,
            "backend_id": self.backend_id,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "approval_status": self.approval_status,
            "writes_allowed": self.writes_allowed.to_dict(),
            "notes": list(self.notes),
        }


def create_empty_recognition_layer(
    manifest: VisualIntakeManifest,
    region_map: VisualRegionMap,
) -> VisualRecognitionLayer:
    source = manifest.source
    return VisualRecognitionLayer(
        contract_version=RECOGNITION_LAYER_CONTRACT_VERSION,
        visual_record_id=source.visual_record_id,
        region_map_id=region_map.region_map_id,
        recognition_layer_id=_recognition_layer_id(source.visual_record_id, region_map.region_map_id),
        source_hash=source.sha256,
        notes=[
            "Recognition layer is initialized empty; no OCR/object/scene candidates have been generated.",
            "Recognition candidates remain evidence until approval promotes them.",
        ],
    )


def validate_recognition_layer(record: dict[str, Any]) -> None:
    required = {
        "contract_version",
        "visual_record_id",
        "region_map_id",
        "recognition_layer_id",
        "source_hash",
        "candidates",
        "approval_status",
        "writes_allowed",
    }
    missing = sorted(required.difference(record))
    if missing:
        raise ValueError(f"recognition layer missing required fields: {', '.join(missing)}")
    if record["contract_version"] != RECOGNITION_LAYER_CONTRACT_VERSION:
        raise ValueError("recognition layer contract version mismatch")
    if record["writes_allowed"] != VisualWritePolicy().to_dict():
        raise ValueError("recognition layer cannot allow map/count/lifetime/lexicon writes")
    if not isinstance(record["candidates"], list):
        raise ValueError("recognition candidates must be a list")
    for candidate in record["candidates"]:
        _validate_candidate(candidate)


def _validate_candidate(candidate: dict[str, Any]) -> None:
    required = {"candidate_id", "candidate_type", "backend_id", "evidence_refs", "approval_status"}
    missing = sorted(required.difference(candidate))
    if missing:
        raise ValueError(f"recognition candidate missing required fields: {', '.join(missing)}")
    if candidate["candidate_type"] not in ALLOWED_CANDIDATE_TYPES:
        raise ValueError("recognition candidate type is not allowed")
    if not isinstance(candidate["evidence_refs"], list):
        raise ValueError("recognition candidate evidence_refs must be a list")
