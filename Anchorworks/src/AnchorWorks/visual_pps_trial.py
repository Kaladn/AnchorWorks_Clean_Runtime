from __future__ import annotations

import hashlib
import struct
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from .visual_dual_path_verification import (
    DualPathVerificationReport,
    SourceTextSpan,
    build_dual_path_verification_report,
    validate_dual_path_verification_report,
)
from .visual_manifest import VisualWritePolicy, manifest_from_image_bytes
from .visual_recognition_layer import create_empty_recognition_layer
from .visual_region_map import create_empty_region_map


PPS_TRIAL_CONTRACT_VERSION = "anchorworks_visual_pps_trial@1"
PPS_TRIAL_BACKEND_ID = "anchorworks_pps_trial"


@dataclass(frozen=True)
class VisualPageTrialInput:
    source_id: str
    source_spans: list[SourceTextSpan]
    region_map: dict[str, Any]
    recognition_layer: dict[str, Any]

    @classmethod
    def from_text_lines(
        cls,
        *,
        source_id: str,
        source_spans: list[SourceTextSpan],
        visual_texts: list[str],
        confidences: list[float] | None = None,
    ) -> VisualPageTrialInput:
        raw = _synthetic_png_header(width=1024, height=max(1, len(source_spans)) * 64)
        manifest = manifest_from_image_bytes(raw, f"{source_id}.png")
        region_map_obj = create_empty_region_map(manifest)
        recognition = create_empty_recognition_layer(manifest, region_map_obj).to_dict()
        confidence_values = confidences or []
        recognition["candidates"] = [
            {
                "candidate_id": f"{source_id}_vcand_{index}",
                "candidate_type": "ocr_text",
                "region_id": f"r{index + 1}",
                "value": {"text": text},
                "confidence": confidence_values[index] if index < len(confidence_values) else 0.99,
                "backend_id": "synthetic_visual_text",
                "evidence_refs": [f"r{index + 1}"],
                "approval_status": "candidate",
            }
            for index, text in enumerate(visual_texts)
        ]
        return cls(
            source_id=source_id,
            source_spans=source_spans,
            region_map=region_map_obj.to_dict(),
            recognition_layer=recognition,
        )


@dataclass(frozen=True)
class VisualPpsTrialReport:
    contract_version: str
    trial_id: str
    trial_mode: str
    page_count: int
    elapsed_seconds: float
    pages_per_second: float
    source_span_total: int
    visual_text_candidate_total: int
    exact_match_total: int
    mean_agreement_ratio: float
    reading_order_match_count: int
    total_issues: int
    page_reports: list[DualPathVerificationReport] = field(default_factory=list)
    approval_status: str = "preview_only"
    backend_id: str = PPS_TRIAL_BACKEND_ID
    writes_allowed: VisualWritePolicy = field(default_factory=VisualWritePolicy)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "trial_id": self.trial_id,
            "trial_mode": self.trial_mode,
            "page_count": self.page_count,
            "elapsed_seconds": self.elapsed_seconds,
            "pages_per_second": self.pages_per_second,
            "source_span_total": self.source_span_total,
            "visual_text_candidate_total": self.visual_text_candidate_total,
            "exact_match_total": self.exact_match_total,
            "mean_agreement_ratio": self.mean_agreement_ratio,
            "reading_order_match_count": self.reading_order_match_count,
            "total_issues": self.total_issues,
            "page_reports": [report.to_dict() for report in self.page_reports],
            "approval_status": self.approval_status,
            "backend_id": self.backend_id,
            "writes_allowed": self.writes_allowed.to_dict(),
            "notes": list(self.notes),
        }


def run_visual_pps_trial(
    pages: list[VisualPageTrialInput],
    *,
    elapsed_seconds: float | None = None,
) -> VisualPpsTrialReport:
    started = time.perf_counter()
    page_reports = [
        build_dual_path_verification_report(
            source_id=page.source_id,
            source_spans=page.source_spans,
            region_map=page.region_map,
            recognition_layer=page.recognition_layer,
        )
        for page in pages
    ]
    measured_elapsed = time.perf_counter() - started
    elapsed = elapsed_seconds if elapsed_seconds is not None else measured_elapsed
    elapsed = max(elapsed, 0.000001)
    page_count = len(page_reports)
    source_span_total = sum(report.source_span_count for report in page_reports)
    candidate_total = sum(report.visual_text_candidate_count for report in page_reports)
    exact_match_total = sum(report.exact_match_count for report in page_reports)
    issue_total = sum(len(report.issues) for report in page_reports)
    mean_agreement = (
        sum(report.agreement_ratio for report in page_reports) / page_count
        if page_count
        else 0.0
    )
    return VisualPpsTrialReport(
        contract_version=PPS_TRIAL_CONTRACT_VERSION,
        trial_id=_trial_id(page_reports),
        trial_mode="synthetic_dual_path",
        page_count=page_count,
        elapsed_seconds=round(elapsed, 6),
        pages_per_second=round(page_count / elapsed, 3),
        source_span_total=source_span_total,
        visual_text_candidate_total=candidate_total,
        exact_match_total=exact_match_total,
        mean_agreement_ratio=round(mean_agreement, 4),
        reading_order_match_count=sum(1 for report in page_reports if report.reading_order_match),
        total_issues=issue_total,
        page_reports=page_reports,
        notes=[
            "PPS trial measures pages through the verification harness, not OCR/CV recognition speed.",
            "Source truth scores visual candidates; no promotion writes are allowed.",
        ],
    )


def validate_visual_pps_trial_report(record: dict[str, Any]) -> None:
    required = {
        "contract_version",
        "trial_id",
        "trial_mode",
        "page_count",
        "elapsed_seconds",
        "pages_per_second",
        "source_span_total",
        "visual_text_candidate_total",
        "exact_match_total",
        "mean_agreement_ratio",
        "reading_order_match_count",
        "total_issues",
        "page_reports",
        "approval_status",
        "writes_allowed",
    }
    missing = sorted(required.difference(record))
    if missing:
        raise ValueError(f"PPS trial report missing required fields: {', '.join(missing)}")
    if record["contract_version"] != PPS_TRIAL_CONTRACT_VERSION:
        raise ValueError("PPS trial contract version mismatch")
    if record["approval_status"] != "preview_only":
        raise ValueError("PPS trial must remain preview_only")
    if record["writes_allowed"] != VisualWritePolicy().to_dict():
        raise ValueError("PPS trial cannot allow map/count/lifetime/lexicon writes")
    if not isinstance(record["page_reports"], list):
        raise ValueError("PPS trial page_reports must be a list")
    for report in record["page_reports"]:
        validate_dual_path_verification_report(report)


def _trial_id(page_reports: list[DualPathVerificationReport]) -> str:
    seed = "::".join(report.verification_report_id for report in page_reports)
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
    return "pps_trial_" + digest


def _synthetic_png_header(width: int, height: int) -> bytes:
    ihdr = (
        b"\x00\x00\x00\x0d"
        b"IHDR"
        + struct.pack(">II", width, height)
        + bytes([8, 2, 0, 0, 0])
        + b"\x00\x00\x00\x00"
    )
    return b"\x89PNG\r\n\x1a\n" + ihdr + b"\x00\x00\x00\x00IEND\x00\x00\x00\x00"
