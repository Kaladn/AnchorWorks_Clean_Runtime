from __future__ import annotations

import difflib
import hashlib
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from .visual_manifest import VisualWritePolicy


BILATERAL_TEXT_REGION_CONTRACT_VERSION = "anchorworks_bilateral_text_region@1"
SOURCE_LAYOUT_AUTHORITY = "source_layout_evidence"
VISUAL_RECOGNITION_AUTHORITY = "derived_visual_recognition"

AGREEMENT_STATUSES = {
    "exact",
    "near",
    "missing_visual",
    "missing_source",
    "conflict",
    "unreadable_visual",
    "source_layout_only",
    "visual_rescue_candidate",
}

_SPACE_RE = re.compile(r"\s+")
_NON_WORD_RE = re.compile(r"[^\w\s]+", re.UNICODE)


def _normalize_text(value: str | None) -> str:
    value = _NON_WORD_RE.sub(" ", (value or "").casefold())
    return _SPACE_RE.sub(" ", value).strip()


def _record_id(page_id: str, visual_record_id: str, region_id: str, source_text: str, visual_text: str) -> str:
    seed = f"{BILATERAL_TEXT_REGION_CONTRACT_VERSION}::{page_id}::{visual_record_id}::{region_id}::{source_text}::{visual_text}"
    return "btext_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class SourceTextSide:
    text: str
    authority: str = SOURCE_LAYOUT_AUTHORITY
    span_id: str | None = None
    reading_order: int | None = None
    permissions: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["permissions"] = dict(self.permissions or source_text_permissions())
        return row


@dataclass(frozen=True)
class VisualTextSide:
    text: str
    authority: str = VISUAL_RECOGNITION_AUTHORITY
    candidate_id: str | None = None
    confidence: float | None = None
    permissions: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["permissions"] = dict(self.permissions or visual_text_permissions())
        return row


@dataclass(frozen=True)
class BilateralAgreement:
    status: str
    score: float
    normalized_source: str
    normalized_visual: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BilateralTextRegion:
    schema_version: str
    bilateral_text_region_id: str
    page_id: str
    visual_record_id: str
    region_id: str
    source_text: SourceTextSide
    visual_text: VisualTextSide
    agreement: BilateralAgreement
    approval_status: str = "candidate"
    writes_allowed: VisualWritePolicy = field(default_factory=VisualWritePolicy)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "bilateral_text_region_id": self.bilateral_text_region_id,
            "page_id": self.page_id,
            "visual_record_id": self.visual_record_id,
            "region_id": self.region_id,
            "source_text": self.source_text.to_dict(),
            "visual_text": self.visual_text.to_dict(),
            "agreement": self.agreement.to_dict(),
            "approval_status": self.approval_status,
            "writes_allowed": self.writes_allowed.to_dict(),
            "notes": list(self.notes),
        }


def source_text_permissions() -> dict[str, Any]:
    return {
        "may_feed_text_intake": True,
        "may_feed_maps": True,
        "may_feed_counts": "if_source_authority_approved",
        "may_feed_lifetime": "promotion_required",
        "may_speak": True,
    }


def visual_text_permissions() -> dict[str, Any]:
    return {
        "may_feed_text_intake": False,
        "may_feed_maps": "source_local_candidate",
        "may_feed_counts": "source_local_preview",
        "may_feed_lifetime": False,
        "may_speak": False,
        "may_rescue": True,
        "may_audit": True,
        "promotion_required": True,
    }


def build_bilateral_text_region(
    *,
    page_id: str,
    visual_record_id: str,
    region_id: str,
    source_text: str | None = None,
    source_span_id: str | None = None,
    source_reading_order: int | None = None,
    visual_text: str | None = None,
    visual_candidate_id: str | None = None,
    visual_confidence: float | None = None,
) -> BilateralTextRegion:
    source_value = source_text or ""
    visual_value = visual_text or ""
    agreement = _agreement(source_value, visual_value)
    return BilateralTextRegion(
        schema_version=BILATERAL_TEXT_REGION_CONTRACT_VERSION,
        bilateral_text_region_id=_record_id(page_id, visual_record_id, region_id, source_value, visual_value),
        page_id=page_id,
        visual_record_id=visual_record_id,
        region_id=region_id,
        source_text=SourceTextSide(
            text=source_value,
            span_id=source_span_id,
            reading_order=source_reading_order,
            permissions=source_text_permissions(),
        ),
        visual_text=VisualTextSide(
            text=visual_value,
            candidate_id=visual_candidate_id,
            confidence=visual_confidence,
            permissions=visual_text_permissions(),
        ),
        agreement=agreement,
        notes=[
            "Source tells.",
            "Vision witnesses.",
            "The bilateral record remembers both.",
            "Promotion decides what joins memory.",
            "Agreement strengthens trust.",
            "Disagreement creates evidence, not truth.",
        ],
    )


def validate_bilateral_text_region(record: dict[str, Any]) -> None:
    required = {
        "schema_version",
        "bilateral_text_region_id",
        "page_id",
        "visual_record_id",
        "region_id",
        "source_text",
        "visual_text",
        "agreement",
        "approval_status",
        "writes_allowed",
    }
    missing = sorted(required.difference(record))
    if missing:
        raise ValueError(f"bilateral text region missing required fields: {', '.join(missing)}")
    if record["schema_version"] != BILATERAL_TEXT_REGION_CONTRACT_VERSION:
        raise ValueError("bilateral text region schema version mismatch")
    if record["approval_status"] != "candidate":
        raise ValueError("bilateral text region must remain candidate until promotion")
    if record["writes_allowed"] != VisualWritePolicy().to_dict():
        raise ValueError("bilateral text region cannot directly write maps/counts/lifetime/lexicon")
    _validate_side(record["source_text"], source=True)
    _validate_side(record["visual_text"], source=False)
    agreement = record["agreement"]
    if not isinstance(agreement, dict):
        raise ValueError("bilateral agreement must be an object")
    if agreement.get("status") not in AGREEMENT_STATUSES:
        raise ValueError("bilateral agreement status is not allowed")


def _validate_side(side: dict[str, Any], *, source: bool) -> None:
    required = {"text", "authority", "permissions"}
    missing = sorted(required.difference(side))
    if missing:
        raise ValueError(f"bilateral text side missing required fields: {', '.join(missing)}")
    expected = SOURCE_LAYOUT_AUTHORITY if source else VISUAL_RECOGNITION_AUTHORITY
    if side["authority"] != expected:
        raise ValueError("bilateral text side authority mismatch")
    if not isinstance(side["permissions"], dict):
        raise ValueError("bilateral text side permissions must be an object")


def _agreement(source_text: str, visual_text: str) -> BilateralAgreement:
    source_norm = _normalize_text(source_text)
    visual_norm = _normalize_text(visual_text)
    if source_norm and visual_norm and source_norm == visual_norm:
        return BilateralAgreement("exact", 1.0, source_norm, visual_norm)
    if source_norm and not visual_norm:
        return BilateralAgreement("source_layout_only", 0.0, source_norm, visual_norm)
    if visual_norm and not source_norm:
        return BilateralAgreement("visual_rescue_candidate", 0.0, source_norm, visual_norm)
    if not source_norm and not visual_norm:
        return BilateralAgreement("unreadable_visual", 0.0, source_norm, visual_norm)
    score = round(difflib.SequenceMatcher(a=source_norm, b=visual_norm).ratio(), 4)
    status = "near" if score >= 0.82 else "conflict"
    return BilateralAgreement(status, score, source_norm, visual_norm)
