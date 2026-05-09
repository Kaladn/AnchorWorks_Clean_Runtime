from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from .bilateral_text_region import BilateralTextRegion, build_bilateral_text_region, validate_bilateral_text_region
from .visual_manifest import VisualWritePolicy
from .visual_recognition_layer import validate_recognition_layer
from .visual_region_map import validate_region_map


DUAL_PATH_VERIFICATION_CONTRACT_VERSION = "anchorworks_visual_dual_path_verification@1"
DUAL_PATH_BACKEND_ID = "anchorworks_dual_path_verifier"


_SPACE_RE = re.compile(r"\s+")
_NON_WORD_RE = re.compile(r"[^\w\s]+", re.UNICODE)


def _normalize_text(value: str) -> str:
    value = _NON_WORD_RE.sub(" ", value.casefold())
    return _SPACE_RE.sub(" ", value).strip()


def _report_id(source_id: str, region_map_id: str, recognition_layer_id: str) -> str:
    seed = f"{DUAL_PATH_VERIFICATION_CONTRACT_VERSION}::{source_id}::{region_map_id}::{recognition_layer_id}"
    return "vverify_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class SourceTextSpan:
    span_id: str
    text: str
    reading_order: int = 0
    region_id: str | None = None
    source_ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VerificationIssue:
    issue_type: str
    severity: str
    message: str
    source_span_id: str | None = None
    candidate_id: str | None = None
    region_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DualPathVerificationReport:
    contract_version: str
    verification_report_id: str
    source_id: str
    visual_record_id: str
    region_map_id: str
    recognition_layer_id: str
    source_span_count: int
    visual_text_candidate_count: int
    exact_match_count: int
    agreement_ratio: float
    reading_order_match: bool
    bilateral_text_regions: list[BilateralTextRegion] = field(default_factory=list)
    issues: list[VerificationIssue] = field(default_factory=list)
    approval_status: str = "preview_only"
    backend_id: str = DUAL_PATH_BACKEND_ID
    writes_allowed: VisualWritePolicy = field(default_factory=VisualWritePolicy)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "verification_report_id": self.verification_report_id,
            "source_id": self.source_id,
            "visual_record_id": self.visual_record_id,
            "region_map_id": self.region_map_id,
            "recognition_layer_id": self.recognition_layer_id,
            "source_span_count": self.source_span_count,
            "visual_text_candidate_count": self.visual_text_candidate_count,
            "exact_match_count": self.exact_match_count,
            "agreement_ratio": self.agreement_ratio,
            "reading_order_match": self.reading_order_match,
            "bilateral_text_regions": [region.to_dict() for region in self.bilateral_text_regions],
            "issues": [issue.to_dict() for issue in self.issues],
            "approval_status": self.approval_status,
            "backend_id": self.backend_id,
            "writes_allowed": self.writes_allowed.to_dict(),
            "notes": list(self.notes),
        }


def build_dual_path_verification_report(
    *,
    source_id: str,
    source_spans: list[SourceTextSpan],
    region_map: dict[str, Any],
    recognition_layer: dict[str, Any],
    min_confidence: float = 0.75,
) -> DualPathVerificationReport:
    """Compare source-doc text spans against visual recognition candidates.

    This is a preview-only comparator. It does not run OCR/CV, create regions,
    write maps/counts/lifetime, or promote text into Canonical.
    """
    validate_region_map(region_map)
    validate_recognition_layer(recognition_layer)
    if region_map["region_map_id"] != recognition_layer["region_map_id"]:
        raise ValueError("region map and recognition layer do not share a region_map_id")
    if region_map["visual_record_id"] != recognition_layer["visual_record_id"]:
        raise ValueError("region map and recognition layer do not share a visual_record_id")

    source_items = sorted(source_spans, key=lambda span: span.reading_order)
    visual_items = _visual_text_candidates(recognition_layer)
    source_norm = [_normalize_text(span.text) for span in source_items]
    visual_norm = [_normalize_text(item["text"]) for item in visual_items]
    bilateral_regions = _build_bilateral_regions(
        source_id=source_id,
        visual_record_id=region_map["visual_record_id"],
        source_items=source_items,
        visual_items=visual_items,
    )

    source_counts = _counts(source_norm)
    visual_counts = _counts(visual_norm)
    exact_match_count = sum(min(source_counts.get(text, 0), visual_counts.get(text, 0)) for text in source_counts)

    issues: list[VerificationIssue] = []
    for span, normalized in zip(source_items, source_norm):
        if normalized and visual_counts.get(normalized, 0) <= 0:
            issues.append(
                VerificationIssue(
                    issue_type="missing_visual_text",
                    severity="medium",
                    message="source text span was not found in visual recognition candidates",
                    source_span_id=span.span_id,
                    region_id=span.region_id,
                )
            )
        elif normalized:
            visual_counts[normalized] -= 1

    source_counts_for_extra = _counts(source_norm)
    for item, normalized in zip(visual_items, visual_norm):
        if normalized and source_counts_for_extra.get(normalized, 0) <= 0:
            issues.append(
                VerificationIssue(
                    issue_type="extra_visual_text",
                    severity="low",
                    message="visual recognition candidate was not found in source text spans",
                    candidate_id=item["candidate_id"],
                    region_id=item.get("region_id"),
                )
            )
        elif normalized:
            source_counts_for_extra[normalized] -= 1
        confidence = item.get("confidence")
        if confidence is not None and confidence < min_confidence:
            issues.append(
                VerificationIssue(
                    issue_type="low_confidence_visual_text",
                    severity="low",
                    message="visual recognition candidate is below confidence threshold",
                    candidate_id=item["candidate_id"],
                    region_id=item.get("region_id"),
                )
            )

    comparable = max(len(source_items), 1)
    agreement_ratio = round(exact_match_count / comparable, 4)
    reading_order_match = _reading_order_matches(source_norm, visual_norm)

    return DualPathVerificationReport(
        contract_version=DUAL_PATH_VERIFICATION_CONTRACT_VERSION,
        verification_report_id=_report_id(source_id, region_map["region_map_id"], recognition_layer["recognition_layer_id"]),
        source_id=source_id,
        visual_record_id=region_map["visual_record_id"],
        region_map_id=region_map["region_map_id"],
        recognition_layer_id=recognition_layer["recognition_layer_id"],
        source_span_count=len(source_items),
        visual_text_candidate_count=len(visual_items),
        exact_match_count=exact_match_count,
        agreement_ratio=agreement_ratio,
        reading_order_match=reading_order_match,
        bilateral_text_regions=bilateral_regions,
        issues=issues,
        notes=[
            "Source path reads first; vision path verifies and rescues.",
            "Verification report is preview-only and cannot promote truth.",
        ],
    )


def validate_dual_path_verification_report(record: dict[str, Any]) -> None:
    required = {
        "contract_version",
        "verification_report_id",
        "source_id",
        "visual_record_id",
        "region_map_id",
        "recognition_layer_id",
        "source_span_count",
        "visual_text_candidate_count",
        "exact_match_count",
        "agreement_ratio",
        "reading_order_match",
        "bilateral_text_regions",
        "issues",
        "approval_status",
        "writes_allowed",
    }
    missing = sorted(required.difference(record))
    if missing:
        raise ValueError(f"dual-path verification report missing required fields: {', '.join(missing)}")
    if record["contract_version"] != DUAL_PATH_VERIFICATION_CONTRACT_VERSION:
        raise ValueError("dual-path verification contract version mismatch")
    if record["writes_allowed"] != VisualWritePolicy().to_dict():
        raise ValueError("dual-path verification cannot allow map/count/lifetime/lexicon writes")
    if record["approval_status"] != "preview_only":
        raise ValueError("dual-path verification must remain preview_only")
    if not isinstance(record["issues"], list):
        raise ValueError("dual-path verification issues must be a list")
    if not isinstance(record["bilateral_text_regions"], list):
        raise ValueError("dual-path verification bilateral_text_regions must be a list")
    for region in record["bilateral_text_regions"]:
        validate_bilateral_text_region(region)


def _visual_text_candidates(recognition_layer: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for candidate in recognition_layer.get("candidates", []):
        if candidate.get("candidate_type") != "ocr_text":
            continue
        value = candidate.get("value") if isinstance(candidate.get("value"), dict) else {}
        text = (
            value.get("text")
            or value.get("surface")
            or value.get("normalized_surface")
            or candidate.get("surface")
            or candidate.get("normalized_surface")
            or ""
        )
        items.append(
            {
                "candidate_id": candidate.get("candidate_id", ""),
                "region_id": candidate.get("region_id"),
                "text": str(text),
                "confidence": candidate.get("confidence"),
            }
        )
    return items


def _build_bilateral_regions(
    *,
    source_id: str,
    visual_record_id: str,
    source_items: list[SourceTextSpan],
    visual_items: list[dict[str, Any]],
) -> list[BilateralTextRegion]:
    regions: list[BilateralTextRegion] = []
    used_visual_indexes: set[int] = set()
    for span in source_items:
        span_norm = _normalize_text(span.text)
        visual_index = _first_matching_visual_index(span_norm, visual_items, used_visual_indexes)
        visual_item = visual_items[visual_index] if visual_index is not None else None
        if visual_index is not None:
            used_visual_indexes.add(visual_index)
        regions.append(
            build_bilateral_text_region(
                page_id=source_id,
                visual_record_id=visual_record_id,
                region_id=span.region_id or (visual_item or {}).get("region_id") or span.span_id,
                source_text=span.text,
                source_span_id=span.span_id,
                source_reading_order=span.reading_order,
                visual_text=(visual_item or {}).get("text"),
                visual_candidate_id=(visual_item or {}).get("candidate_id"),
                visual_confidence=(visual_item or {}).get("confidence"),
            )
        )
    for index, visual_item in enumerate(visual_items):
        if index in used_visual_indexes:
            continue
        regions.append(
            build_bilateral_text_region(
                page_id=source_id,
                visual_record_id=visual_record_id,
                region_id=visual_item.get("region_id") or visual_item.get("candidate_id") or f"visual_extra_{index}",
                visual_text=visual_item.get("text"),
                visual_candidate_id=visual_item.get("candidate_id"),
                visual_confidence=visual_item.get("confidence"),
            )
        )
    return regions


def _first_matching_visual_index(
    span_norm: str,
    visual_items: list[dict[str, Any]],
    used_indexes: set[int],
) -> int | None:
    if not span_norm:
        return None
    for index, item in enumerate(visual_items):
        if index in used_indexes:
            continue
        if _normalize_text(item.get("text", "")) == span_norm:
            return index
    return None


def _counts(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        if not value:
            continue
        counts[value] = counts.get(value, 0) + 1
    return counts


def _reading_order_matches(source_norm: list[str], visual_norm: list[str]) -> bool:
    source = [value for value in source_norm if value]
    visual = [value for value in visual_norm if value]
    if not source and not visual:
        return True
    filtered_visual = [value for value in visual if value in set(source)]
    return source == filtered_visual[: len(source)]
