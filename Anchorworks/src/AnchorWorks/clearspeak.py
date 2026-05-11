from __future__ import annotations

import os
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any

from .clearspeak_attention import (
    attention_math_contract,
    content_anchors,
    infer_attention_frame,
    rank_attention_candidates,
    retrieve_from_count_index,
)
from .intake import extract_anchors
from .lifetime_symbol_mirror import load_lifetime_by_symbol_dir


@dataclass
class ClearSpeakResult:
    query: str
    query_anchors: list[str]
    represented_anchors: list[str]
    missing_anchors: list[str]
    lexicon_recognition: dict[str, Any]
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
        recognition = self._recognize(query_text)
        unique = recognition["query_anchors"]
        represented = recognition["represented_anchors"]
        missing = recognition["missing_anchors"]
        count_index = self._load_count_index()

        evidence: list[dict[str, Any]] = []
        citation_rows: list[dict[str, Any]] = []
        for anchor in represented:
            retrieved = retrieve_from_count_index(count_index, anchor, limit=limit)
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
            lexicon_recognition=recognition,
            response=response,
            evidence=evidence,
            citations=citation_rows,
            answer_assembly=answer_assembly,
        )

    def _recognize(self, query: str) -> dict[str, Any]:
        if hasattr(self.store, "recognize_query_anchors"):
            return self.store.recognize_query_anchors(query)
        observed = extract_anchors(query)
        unique = _ordered_unique(observed)
        known = set(self.store._all_known_anchors())
        return {
            "schema_version": "anchorworks_lexicon_recognition@1",
            "query": str(query or ""),
            "query_anchors": unique,
            "represented_anchors": [anchor for anchor in unique if anchor in known],
            "missing_anchors": [anchor for anchor in unique if anchor not in known],
            "recognition_layer": "lexicon",
            "lexicon_first": True,
            "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
        }

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
        external_by_symbol_dir = os.environ.get("ANCHORWORKS_LIFETIME_BY_SYMBOL_DIR")
        if external_by_symbol_dir:
            return load_lifetime_by_symbol_dir(external_by_symbol_dir)
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
        seeds = content_anchors(represented)
        if not seeds:
            return _empty_answer_assembly("no_content_seed")
        attention_frame = infer_attention_frame(represented)
        context = list(seeds)
        selected: list[dict[str, Any]] = []
        selected_anchors: set[str] = set()
        trace: list[dict[str, Any]] = []
        blocked = set(seeds)

        for step in range(max(1, int(limit or 6))):
            pool = self._rank_count_candidates(
                count_index,
                context,
                blocked=blocked | selected_anchors,
                attention_frame=attention_frame,
            )
            if not pool:
                return {
                    "schema_version": "clearspeak_dynamic_count_answer@1",
                    "seed_anchors": seeds,
                    "terms": selected,
                    "trace": trace,
                    "stop_reason": "no_supported_candidate" if selected else "no_candidate_pool",
                    "attention_frame": attention_frame,
                    "attention_math": attention_math_contract(),
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
            "attention_frame": attention_frame,
            "attention_math": attention_math_contract(),
            "contract": _answer_assembly_contract(),
        }

    def _rank_count_candidates(
        self,
        count_index: dict[str, Any],
        context: list[str],
        *,
        blocked: set[str],
        attention_frame: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        return rank_attention_candidates(count_index, context, blocked=blocked, attention_frame=attention_frame)


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
        "attention_frame": infer_attention_frame([]),
        "attention_math": attention_math_contract(),
        "contract": _answer_assembly_contract(),
    }


def _ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out
