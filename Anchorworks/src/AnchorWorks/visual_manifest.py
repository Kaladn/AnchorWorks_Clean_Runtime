from __future__ import annotations

import hashlib
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .anchor_forge_visual import probe_image_bytes


VISUAL_CONTRACT_VERSION = "anchorworks_visual_intake@1"
COMPONENT_TRUEVISION = "truevision"
AUTHORITY_SOURCE_LOCAL_VISUAL = "source_local_visual_evidence"


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _safe_source_name(source_name: str) -> str:
    return Path(source_name or "visual_source").name


def _aspect_ratio(width: int | None, height: int | None) -> str:
    if not width or not height:
        return "unknown"
    divisor = math.gcd(width, height)
    return f"{width // divisor}:{height // divisor}"


def _record_id(source_name: str, digest: str) -> str:
    seed = f"{VISUAL_CONTRACT_VERSION}::{_safe_source_name(source_name)}::{digest}"
    return "visual_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class VisualWritePolicy:
    """Preview-only write gate for visual intake outputs."""

    maps: bool = False
    counts: bool = False
    lifetime: bool = False
    lexicon: bool = False

    def to_dict(self) -> dict[str, bool]:
        return asdict(self)


@dataclass(frozen=True)
class BackendCapability:
    """Static declaration of what a visual backend is allowed to do."""

    backend_id: str
    backend_type: str
    provider: str
    version: str
    inputs_supported: list[str]
    outputs_supported: list[str]
    coordinate_space: str = "native_pixels"
    distorts_source: bool = False
    may_resize_for_model: bool = False
    resize_is_derived: bool = True
    writes_allowed: VisualWritePolicy = field(default_factory=VisualWritePolicy)

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["writes_allowed"] = self.writes_allowed.to_dict()
        return row


@dataclass(frozen=True)
class VisualSourceRecord:
    """Immutable source identity and native geometry for an image/video frame."""

    visual_record_id: str
    source_name: str
    media_type: str
    sha256: str
    byte_size: int
    width: int | None = None
    height: int | None = None
    aspect_ratio: str = "unknown"
    color_mode: str = "unknown"
    file_format: str = "unknown"
    frame_index: int = 0
    frame_timestamp_ms: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VisualLayer:
    """Derived visual layer with provenance back to native pixel coordinates."""

    layer_type: str
    backend_id: str
    coordinate_space: str = "native_pixels"
    items: list[dict[str, Any]] = field(default_factory=list)
    status: str = "preview_only"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VisualIntakeManifest:
    """AnchorWorks visual intake packet; safe to attach to document prep metadata."""

    contract_version: str
    source: VisualSourceRecord
    authority: str = AUTHORITY_SOURCE_LOCAL_VISUAL
    approval_status: str = "preview_only"
    backend_capabilities: list[BackendCapability] = field(default_factory=list)
    layers: list[VisualLayer] = field(default_factory=list)
    writes_allowed: VisualWritePolicy = field(default_factory=VisualWritePolicy)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "source": self.source.to_dict(),
            "authority": self.authority,
            "approval_status": self.approval_status,
            "backend_capabilities": [backend.to_dict() for backend in self.backend_capabilities],
            "layers": [layer.to_dict() for layer in self.layers],
            "writes_allowed": self.writes_allowed.to_dict(),
            "notes": list(self.notes),
        }


def compucog_yolo_a_capability() -> BackendCapability:
    """Declare the current CompuCogVision YOLO-A backend as an adapter target."""

    return BackendCapability(
        backend_id="compucog_vision_yolo_a",
        backend_type="object_detection",
        provider="local_compucog",
        version="phase_a",
        inputs_supported=["screen_capture", "image_frame"],
        outputs_supported=["detections", "scene_analysis", "auto_labels"],
        coordinate_space="native_pixels",
        distorts_source=False,
        may_resize_for_model=True,
        resize_is_derived=True,
    )


def source_record_from_image_bytes(raw: bytes, source_name: str) -> VisualSourceRecord:
    """Create an immutable visual source record without running OCR/detection."""

    safe_name = _safe_source_name(source_name)
    digest = _sha256(raw)
    probe = probe_image_bytes(raw, safe_name)
    fallback_format = Path(safe_name).suffix.lower().lstrip(".") or "unknown"
    width = probe.width
    height = probe.height
    color_mode = probe.color_mode
    file_format = probe.file_format if probe.file_format != "unknown" else fallback_format

    return VisualSourceRecord(
        visual_record_id=_record_id(safe_name, digest),
        source_name=safe_name,
        media_type="image",
        sha256=digest,
        byte_size=len(raw),
        width=width,
        height=height,
        aspect_ratio=_aspect_ratio(width, height),
        color_mode=color_mode,
        file_format=file_format,
    )


def manifest_from_image_bytes(
    raw: bytes,
    source_name: str,
    *,
    backend_capabilities: list[BackendCapability] | None = None,
) -> VisualIntakeManifest:
    """Build a preview-only visual intake manifest for image document prep."""

    source = source_record_from_image_bytes(raw, source_name)
    return VisualIntakeManifest(
        contract_version=VISUAL_CONTRACT_VERSION,
        source=source,
        backend_capabilities=list(backend_capabilities or [compucog_yolo_a_capability()]),
        layers=[
            VisualLayer(
                layer_type="source_geometry",
                backend_id=COMPONENT_TRUEVISION,
                items=[
                    {
                        "width": source.width,
                        "height": source.height,
                        "aspect_ratio": source.aspect_ratio,
                        "color_mode": source.color_mode,
                        "file_format": source.file_format,
                    }
                ],
            )
        ],
        notes=[
            "Native pixels are preserved as source evidence.",
            "OCR/object/scene layers are derived later by approved backends.",
            "Visual preview does not write maps, counts, lifetime, or lexicon.",
        ],
    )
