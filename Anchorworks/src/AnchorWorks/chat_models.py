from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class SubContextPointer:
    ref_type: str
    ref_id: str
    description: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class L2Context:
    citation_hooks: list[str] = field(default_factory=list)
    context_summary: str = ""
    subcontext_pointers: list[SubContextPointer] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "citation_hooks": [str(row) for row in self.citation_hooks],
            "context_summary": str(self.context_summary or ""),
            "subcontext_pointers": [row.to_dict() for row in self.subcontext_pointers],
        }


@dataclass(frozen=True)
class L3Lesson:
    lesson_text: str
    significance: str = ""
    change: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    lesson_id: str = ""
    created_at_utc: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "lesson_id": self.lesson_id,
            "lesson_text": str(self.lesson_text or ""),
            "significance": str(self.significance or ""),
            "change": str(self.change or ""),
            "evidence_refs": [str(row) for row in self.evidence_refs],
            "created_at_utc": self.created_at_utc or _utc_now(),
        }


@dataclass(frozen=True)
class L4ReasoningHooks:
    reasoning_step_ids: list[str] = field(default_factory=list)
    external_data_pointers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "reasoning_step_ids": [str(row) for row in self.reasoning_step_ids],
            "external_data_pointers": [str(row) for row in self.external_data_pointers],
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
