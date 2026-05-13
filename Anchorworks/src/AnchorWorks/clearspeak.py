from __future__ import annotations

import os
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any

from .clearspeak_attention import (
    ACTIVE_CLOUD_WEIGHTS,
    attention_math_contract,
    build_active_cloud_frame,
    choose_candidate_with_lookahead,
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
    speech: str
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
        speech = self._compose_speech(represented, missing, answer_assembly)
        response = self._compose_response(query_text, represented, missing, evidence, answer_assembly)
        return ClearSpeakResult(
            query=query_text,
            query_anchors=unique,
            represented_anchors=represented,
            missing_anchors=missing,
            lexicon_recognition=recognition,
            speech=speech,
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

    def _compose_speech(
        self,
        represented: list[str],
        missing: list[str],
        answer_assembly: dict[str, Any],
    ) -> str:
        terms = [
            str(row.get("anchor") or "").strip()
            for row in answer_assembly.get("terms", [])
            if isinstance(row, dict) and str(row.get("anchor") or "").strip()
        ]
        if terms:
            return " ".join(terms)
        if represented:
            return "I recognize " + ", ".join(represented) + ", but I do not have count support yet."
        if missing:
            return "I do not recognize " + ", ".join(missing) + " in the lexicon yet."
        return "ClearSpeak is ready."

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
        rear_context = list(seeds[-6:])
        answer_so_far: list[str] = []
        forward_context: list[str] = []
        selected: list[dict[str, Any]] = []
        selected_anchors: set[str] = set()
        trace: list[dict[str, Any]] = []
        blocked = set(seeds)

        for step in range(max(1, int(limit or 6))):
            active_cloud = build_active_cloud_frame(
                count_index,
                question_anchors=represented,
                rear_context=rear_context,
                answer_so_far=answer_so_far,
                forward_context=forward_context,
                blocked=blocked | selected_anchors,
                attention_frame=attention_frame,
                top_k=6,
            )
            pool = active_cloud["candidates"]
            if not pool:
                return {
                    "schema_version": "clearspeak_active_cloud_answer@1",
                    "seed_anchors": seeds,
                    "terms": selected,
                    "trace": trace,
                    "stop_reason": "no_supported_candidate" if selected else "no_candidate_pool",
                    "attention_frame": attention_frame,
                    "active_cloud_weights": dict(ACTIVE_CLOUD_WEIGHTS),
                    "attention_math": attention_math_contract(),
                    "contract": _answer_assembly_contract(),
                }
            lookahead_decision = choose_candidate_with_lookahead(
                count_index,
                pool,
                seed_anchors=seeds,
                blocked=blocked | selected_anchors,
                lookahead_k=6,
            )
            winner = lookahead_decision.get("chosen") or pool[0]
            selected.append({**winner, "selection_step": step + 1})
            selected_anchors.add(winner["anchor"])
            before_rear = list(rear_context)
            before_answer = list(answer_so_far)
            answer_so_far = answer_so_far[-49:] + [winner["anchor"]]
            rear_context = (answer_so_far[-6:] + seeds)[-12:]
            forward_context = _forward_context_from_count_index(count_index, winner["anchor"])
            trace.append({
                "step": step + 1,
                "chosen_anchor": winner["anchor"],
                "selected_anchor": winner["anchor"],
                "candidate_rank": winner.get("candidate_rank", 1),
                "score": winner["score"],
                "selection_score": winner["selection_score"],
                "score_parts": winner.get("score_parts") or {},
                "penalties": winner.get("penalties") or {},
                "supporting_context": winner["supporting_context"],
                "rear_context_before": before_rear,
                "answer_so_far_before": before_answer,
                "rear_context_after": rear_context,
                "answer_so_far_after": answer_so_far,
                "forward_context_after": forward_context,
                "lookahead_decision": lookahead_decision,
                "active_cloud": {
                    "schema_version": active_cloud["schema_version"],
                    "clouds": active_cloud["clouds"],
                    "weights": active_cloud["weights"],
                    "combined_cloud_formula": active_cloud["combined_cloud_formula"],
                },
                "candidate_preview": pool[:6],
                "rejected_candidates": active_cloud.get("rejected_candidates") or [],
            })

        return {
            "schema_version": "clearspeak_active_cloud_answer@1",
            "seed_anchors": seeds,
            "terms": selected,
            "trace": trace,
            "stop_reason": "answer_limit_reached",
            "attention_frame": attention_frame,
            "active_cloud_weights": dict(ACTIVE_CLOUD_WEIGHTS),
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
        "active_cloud_answer_walk": True,
        "question_rear_answer_forward_clouds": True,
        "trace_explains_speech": True,
        "topk_is_walked_not_displayed": True,
        "selected_terms_reenter_context": True,
        "punctuation_cannot_speak": True,
        "numbers_cannot_speak": True,
        "query_echoes_cannot_speak": True,
        "counts_only_no_document_claims": True,
        "topk_lookahead_future_shape": True,
        "memory_writes": False,
    }


def _forward_context_from_count_index(count_index: dict[str, Any], anchor: str, limit: int = 6) -> list[str]:
    retrieved = retrieve_from_count_index(count_index, anchor, limit=limit)
    rows: list[dict[str, Any]] = []
    offsets = retrieved.get("offsets") if isinstance(retrieved.get("offsets"), dict) else {}
    for offset, items in offsets.items():
        try:
            numeric_offset = int(str(offset).replace("+", ""))
        except ValueError:
            continue
        if numeric_offset <= 0:
            continue
        for item in items or []:
            neighbor = str(item.get("anchor") or "").strip()
            if neighbor and not any(row.get("anchor") == neighbor for row in rows):
                rows.append({"anchor": neighbor, "observations": int(item.get("observations", 0) or 0)})
    rows.sort(key=lambda row: (-int(row.get("observations", 0) or 0), str(row.get("anchor") or "")))
    return [str(row["anchor"]) for row in rows[:limit]]


def _empty_answer_assembly(reason: str) -> dict[str, Any]:
    return {
        "schema_version": "clearspeak_active_cloud_answer@1",
        "seed_anchors": [],
        "terms": [],
        "trace": [],
        "stop_reason": reason,
        "attention_frame": infer_attention_frame([]),
        "active_cloud_weights": dict(ACTIVE_CLOUD_WEIGHTS),
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
