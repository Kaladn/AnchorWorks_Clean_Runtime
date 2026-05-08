from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any

from .intake import extract_anchors


@dataclass
class ClearSpeakResult:
    query: str
    query_anchors: list[str]
    represented_anchors: list[str]
    missing_anchors: list[str]
    response: str
    evidence: list[dict[str, Any]]
    citations: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ClearSpeakService:
    def __init__(self, store: Any) -> None:
        self.store = store

    def status(self) -> dict[str, Any]:
        status = self.store.counts_status()
        return {
            "ok": True,
            "name": "ClearSpeak",
            **status,
        }

    def query(self, text: str, limit: int = 6) -> ClearSpeakResult:
        query_text = str(text or "").strip()
        observed = extract_anchors(query_text)
        unique = _ordered_unique(observed)
        known = set(self.store._all_known_anchors())
        represented = [anchor for anchor in unique if anchor in known]
        missing = [anchor for anchor in unique if anchor not in known]

        evidence: list[dict[str, Any]] = []
        citation_rows: list[dict[str, Any]] = []
        for anchor in represented:
            retrieved = self.store.retrieve_from_counts(anchor, limit=limit)
            if int(retrieved.get("total_neighbor_observations", 0) or 0) <= 0:
                continue
            row = {
                "anchor": anchor,
                "neighbor_count": int(retrieved.get("neighbor_count", 0) or 0),
                "total_neighbor_observations": int(retrieved.get("total_neighbor_observations", 0) or 0),
                "neighbors": retrieved.get("neighbors") or [],
                "offsets": retrieved.get("offsets") or {},
            }
            evidence.append(row)
            citation_rows.append({
                "source": "clearspeak_lifetime_counts",
                "anchor": anchor,
                "coord": f"clearspeak:lifetime:{anchor}",
                "observations": row["total_neighbor_observations"],
            })

        response = self._compose_response(query_text, represented, missing, evidence)
        return ClearSpeakResult(
            query=query_text,
            query_anchors=unique,
            represented_anchors=represented,
            missing_anchors=missing,
            response=response,
            evidence=evidence,
            citations=citation_rows,
        )

    def _compose_response(
        self,
        query: str,
        represented: list[str],
        missing: list[str],
        evidence: list[dict[str, Any]],
    ) -> str:
        if not query:
            return "ClearSpeak is ready. Enter anchors to inspect the lifetime count lattice."

        lines: list[str] = ["ClearSpeak read the query as observed anchors."]
        if represented:
            lines.append("Represented anchors: " + ", ".join(represented))
        if missing:
            lines.append("Missing anchors: " + ", ".join(missing))
        if not evidence:
            lines.append("No lifetime co-occurrence evidence is available for the represented anchors yet.")
            return "\n".join(lines)

        lines.append("")
        lines.append("Strongest observed context:")
        for row in evidence:
            neighbors = row.get("neighbors") or []
            if not neighbors:
                lines.append(f"{row['anchor']}: no neighbors recorded")
                continue
            compact = ", ".join(
                f"{item.get('anchor')} ({int(item.get('observations', 0) or 0)})"
                for item in neighbors[:6]
            )
            lines.append(f"{row['anchor']}: {compact}")
        return "\n".join(lines)


def summarize_clearspeak_evidence(result: ClearSpeakResult | dict[str, Any]) -> str:
    payload = result.to_dict() if isinstance(result, ClearSpeakResult) else result
    evidence = payload.get("evidence") or []
    if not evidence:
        return "ClearSpeak evidence: none."
    totals = Counter()
    for row in evidence:
        anchor = row.get("anchor")
        observations = int(row.get("total_neighbor_observations", 0) or 0)
        if anchor:
            totals[str(anchor)] += observations
    if not totals:
        return "ClearSpeak evidence: none."
    pairs = ", ".join(f"{anchor}:{count}" for anchor, count in totals.most_common(8))
    return f"ClearSpeak evidence: {pairs}"


def _ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out
