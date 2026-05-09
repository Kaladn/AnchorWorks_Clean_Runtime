from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any

from .visual_manifest import VisualIntakeManifest, VisualWritePolicy


REGION_MAP_CONTRACT_VERSION = "anchorworks_visual_region_map@1"
REGION_MAP_BACKEND_ID = "anchorworks_region_map_schema"
ALLOWED_COORDINATE_SPACES = {"native_pixels", "grid_cells"}
ALLOWED_REGION_SHAPES = {"box", "polygon", "point", "line", "mask_ref"}


def _region_map_id(visual_record_id: str, source_hash: str) -> str:
    seed = f"{REGION_MAP_CONTRACT_VERSION}::{visual_record_id}::{source_hash}"
    return "region_map_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class VisualRegion:
    region_id: str
    shape: str
    bounds: dict[str, Any]
    kind_candidate: str = "unknown"
    confidence: float | None = None
    backend_id: str = REGION_MAP_BACKEND_ID
    approval_status: str = "candidate"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VisualRegionRelation:
    relation_id: str
    relation_type: str
    source_region_id: str
    target_region_id: str
    confidence: float | None = None
    backend_id: str = REGION_MAP_BACKEND_ID
    approval_status: str = "candidate"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VisualRegionMap:
    contract_version: str
    visual_record_id: str
    region_map_id: str
    source_hash: str
    coordinate_space: str = "native_pixels"
    backend_id: str = REGION_MAP_BACKEND_ID
    regions: list[VisualRegion] = field(default_factory=list)
    relations: list[VisualRegionRelation] = field(default_factory=list)
    approval_status: str = "candidate"
    writes_allowed: VisualWritePolicy = field(default_factory=VisualWritePolicy)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "visual_record_id": self.visual_record_id,
            "region_map_id": self.region_map_id,
            "source_hash": self.source_hash,
            "coordinate_space": self.coordinate_space,
            "backend_id": self.backend_id,
            "regions": [region.to_dict() for region in self.regions],
            "relations": [relation.to_dict() for relation in self.relations],
            "approval_status": self.approval_status,
            "writes_allowed": self.writes_allowed.to_dict(),
            "notes": list(self.notes),
        }


def create_empty_region_map(manifest: VisualIntakeManifest) -> VisualRegionMap:
    source = manifest.source
    return VisualRegionMap(
        contract_version=REGION_MAP_CONTRACT_VERSION,
        visual_record_id=source.visual_record_id,
        region_map_id=_region_map_id(source.visual_record_id, source.sha256),
        source_hash=source.sha256,
        notes=[
            "Region map is initialized empty; no visual regions have been generated.",
            "Regions must use native source coordinates unless explicitly marked as derived grid cells.",
        ],
    )


def validate_region_map(record: dict[str, Any]) -> None:
    required = {
        "contract_version",
        "visual_record_id",
        "region_map_id",
        "source_hash",
        "coordinate_space",
        "regions",
        "relations",
        "approval_status",
        "writes_allowed",
    }
    missing = sorted(required.difference(record))
    if missing:
        raise ValueError(f"region map missing required fields: {', '.join(missing)}")
    if record["contract_version"] != REGION_MAP_CONTRACT_VERSION:
        raise ValueError("region map contract version mismatch")
    if record["coordinate_space"] not in ALLOWED_COORDINATE_SPACES:
        raise ValueError("region map coordinate space must be native_pixels or grid_cells")
    if record["writes_allowed"] != VisualWritePolicy().to_dict():
        raise ValueError("region map cannot allow map/count/lifetime/lexicon writes")
    if not isinstance(record["regions"], list):
        raise ValueError("region map regions must be a list")
    if not isinstance(record["relations"], list):
        raise ValueError("region map relations must be a list")
    for region in record["regions"]:
        _validate_region(region)


def _validate_region(region: dict[str, Any]) -> None:
    required = {"region_id", "shape", "bounds", "kind_candidate", "backend_id", "approval_status"}
    missing = sorted(required.difference(region))
    if missing:
        raise ValueError(f"visual region missing required fields: {', '.join(missing)}")
    if region["shape"] not in ALLOWED_REGION_SHAPES:
        raise ValueError("visual region shape is not allowed")
    if not isinstance(region["bounds"], dict):
        raise ValueError("visual region bounds must be an object")
