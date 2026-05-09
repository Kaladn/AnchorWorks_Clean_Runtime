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
    answer_assembly: dict[str, Any]

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
        count_index = self._load_count_index()

        evidence: list[dict[str, Any]] = []
        citation_rows: list[dict[str, Any]] = []
        for anchor in represented:
            retrieved = _retrieve_from_count_index(count_index, anchor, limit=limit)
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

        answer_assembly = self._assemble_answer_terms(represented, count_index=count_index, limit=limit)
        response = self._compose_response(query_text, represented, missing, evidence, answer_assembly)
        return ClearSpeakResult(
            query=query_text,
            query_anchors=unique,
            represented_anchors=represented,
            missing_anchors=missing,
            response=response,
            evidence=evidence,
            citations=citation_rows,
            answer_assembly=answer_assembly,
        )

    def _compose_response(
        self,
        query: str,
        represented: list[str],
        missing: list[str],
        evidence: list[dict[str, Any]],
        answer_assembly: dict[str, Any],
    ) -> str:
        if not query:
            return "ClearSpeak is ready. Enter anchors to inspect the lifetime count lattice."

        lines: list[str] = []
        terms = [
            str(row.get("anchor") or "")
            for row in answer_assembly.get("terms", [])
            if isinstance(row, dict) and str(row.get("anchor") or "").strip()
        ]
        if terms:
            lines.append("ClearSpeak walked lifetime counts from content anchors.")
            lines.append("Count-assembled answer terms: " + ", ".join(terms))
            lines.append("")
        lines.append("ClearSpeak read the query as observed anchors.")
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

    def _load_count_index(self) -> dict[str, Any]:
        if hasattr(self.store, "_load_combined_relation_counts"):
            counter, _observed = self.store._load_combined_relation_counts()
            by_anchor: dict[str, dict[str, Counter[str]]] = {}
            for (anchor, offset, neighbor), observations in counter.items():
                if observations <= 0:
                    continue
                by_anchor.setdefault(anchor, {}).setdefault(offset, Counter())[neighbor] += int(observations)
            return {"by_anchor": by_anchor}
        return {"by_anchor": {}}

    def _assemble_answer_terms(self, represented: list[str], *, count_index: dict[str, Any], limit: int = 6) -> dict[str, Any]:
        seeds = _content_anchors(represented)
        if not seeds:
            return _empty_answer_assembly("no_content_seed")
        context = list(seeds)
        selected: list[dict[str, Any]] = []
        selected_anchors: set[str] = set()
        trace: list[dict[str, Any]] = []
        blocked = set(seeds)

        for step in range(max(1, int(limit or 6))):
            pool = self._rank_count_candidates(count_index, context, blocked=blocked | selected_anchors)
            if not pool:
                return {
                    "schema_version": "clearspeak_dynamic_count_answer@1",
                    "seed_anchors": seeds,
                    "terms": selected,
                    "trace": trace,
                    "stop_reason": "no_supported_candidate" if selected else "no_candidate_pool",
                    "contract": _answer_assembly_contract(),
                }
            winner = pool[0]
            selected.append({**winner, "selection_step": step + 1})
            selected_anchors.add(winner["anchor"])
            before = context[-50:]
            context.append(winner["anchor"])
            context = context[-50:]
            trace.append({
                "step": step + 1,
                "context_before": before,
                "selected_anchor": winner["anchor"],
                "selection_score": winner["selection_score"],
                "supporting_context": winner["supporting_context"],
                "context_after": context,
                "candidate_preview": pool[:6],
            })

        return {
            "schema_version": "clearspeak_dynamic_count_answer@1",
            "seed_anchors": seeds,
            "terms": selected,
            "trace": trace,
            "stop_reason": "answer_limit_reached",
            "contract": _answer_assembly_contract(),
        }

    def _rank_count_candidates(self, count_index: dict[str, Any], context: list[str], *, blocked: set[str]) -> list[dict[str, Any]]:
        candidates: dict[str, dict[str, Any]] = {}
        for context_anchor in context[-50:]:
            retrieved = _retrieve_from_count_index(count_index, context_anchor, limit=32)
            offsets = retrieved.get("offsets") if isinstance(retrieved.get("offsets"), dict) else {}
            for offset, rows in offsets.items():
                distance = _offset_distance(str(offset))
                position_strength = 1.0 / max(distance, 1)
                for row in rows or []:
                    anchor = str(row.get("anchor") or "").strip()
                    if not anchor or anchor in blocked or _blocked_answer_anchor(anchor):
                        continue
                    observations = int(row.get("observations", 0) or 0)
                    if observations <= 0:
                        continue
                    current = candidates.setdefault(anchor, {
                        "anchor": anchor,
                        "selection_score": 0.0,
                        "raw_observations": 0,
                        "supporting_context": [],
                        "support_offsets": [],
                        "why_chosen": [],
                    })
                    current["selection_score"] += observations * position_strength
                    current["raw_observations"] += observations
                    if context_anchor not in current["supporting_context"]:
                        current["supporting_context"].append(context_anchor)
                    if str(offset) not in current["support_offsets"]:
                        current["support_offsets"].append(str(offset))

        ranked = list(candidates.values())
        for row in ranked:
            support_count = len(row["supporting_context"])
            row["selection_score"] = round(float(row["selection_score"]) + (support_count * 8.0), 4)
            row["why_chosen"] = [
                f"raw_observations={row['raw_observations']}",
                f"context_support={support_count}",
                "position_weighted_topk_walk",
            ]
        ranked.sort(key=lambda row: (-float(row["selection_score"]), -int(row["raw_observations"]), str(row["anchor"])))
        return ranked


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


_ANSWER_BLOCKLIST = {
    "",
    ".",
    ",",
    "?",
    "!",
    ":",
    ";",
    "(",
    ")",
    "[",
    "]",
    "{",
    "}",
    "a",
    "an",
    "and",
    "are",
    "as",
    "be",
    "but",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "for",
    "from",
    "had",
    "has",
    "have",
    "how",
    "i",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "our",
    "should",
    "source",
    "that",
    "the",
    "their",
    "this",
    "to",
    "was",
    "we",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
    "would",
    "you",
}


def _content_anchors(anchors: list[str]) -> list[str]:
    content = [anchor for anchor in anchors if not _blocked_answer_anchor(anchor)]
    return content or anchors


def _blocked_answer_anchor(anchor: str) -> bool:
    clean = str(anchor or "").strip().casefold()
    if clean in _ANSWER_BLOCKLIST:
        return True
    if len(clean) == 1 and not clean.isalnum():
        return True
    return bool(clean) and all(char.isdigit() for char in clean)


def _offset_distance(offset: str) -> int:
    try:
        return abs(int(str(offset).replace("+", "")))
    except ValueError:
        return 6


def _answer_assembly_contract() -> dict[str, bool]:
    return {
        "topk_is_walked_not_displayed": True,
        "selected_terms_reenter_context": True,
        "punctuation_cannot_speak": True,
        "numbers_cannot_speak": True,
        "query_echoes_cannot_speak": True,
        "counts_only_no_document_claims": True,
        "memory_writes": False,
    }


def _empty_answer_assembly(reason: str) -> dict[str, Any]:
    return {
        "schema_version": "clearspeak_dynamic_count_answer@1",
        "seed_anchors": [],
        "terms": [],
        "trace": [],
        "stop_reason": reason,
        "contract": _answer_assembly_contract(),
    }


def _retrieve_from_count_index(count_index: dict[str, Any], anchor: str, limit: int = 25) -> dict[str, Any]:
    surface = str(anchor or "").strip().lower()
    offsets = (count_index.get("by_anchor") or {}).get(surface) or {}
    total_by_neighbor: Counter[str] = Counter()
    by_offset: dict[str, Counter[str]] = {}
    for offset, counter in offsets.items():
        if not isinstance(counter, Counter):
            counter = Counter(counter or {})
        for neighbor, observations in counter.items():
            count = int(observations or 0)
            if count <= 0:
                continue
            total_by_neighbor[str(neighbor)] += count
            by_offset.setdefault(str(offset), Counter())[str(neighbor)] += count
    neighbor_rows = [
        {"anchor": neighbor, "observations": count}
        for neighbor, count in sorted(total_by_neighbor.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]
    offset_rows = {
        offset: [
            {"anchor": neighbor, "observations": count}
            for neighbor, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit]
        ]
        for offset, counter in sorted(by_offset.items(), key=lambda item: (_offset_sort_key(item[0]), item[0]))
    }
    return {
        "anchor": surface,
        "neighbor_count": len(total_by_neighbor),
        "total_neighbor_observations": int(sum(total_by_neighbor.values())),
        "neighbors": neighbor_rows,
        "offsets": offset_rows,
    }


def _offset_sort_key(offset: str) -> int:
    try:
        return int(str(offset).replace("+", ""))
    except ValueError:
        return 0


def _ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out
