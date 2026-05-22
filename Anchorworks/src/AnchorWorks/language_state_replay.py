from __future__ import annotations

from typing import Any


def build_language_state_replay(query_anchors: list[str], answer_assembly: dict[str, Any]) -> dict[str, Any]:
    """Describe whether ClearSpeak has enough walked state to render speech.

    This mirrors the TrueVision reverse-state boundary: reconstructed output may
    use only stored/walked state. Missing state is reported instead of filled.
    """

    query = _clean_list(query_anchors)
    chosen = _chosen_terms(answer_assembly)
    trace = answer_assembly.get("trace") if isinstance(answer_assembly.get("trace"), list) else []
    status = "replayable" if chosen else "missing_state"
    reason = "walked_answer_state_available" if chosen else "no_walked_answer_state"
    return {
        "schema_version": "anchorworks_language_state_replay@1",
        "method": "reverse_language_state_from_walked_count_path",
        "query_anchors": query,
        "seed_anchors": _clean_list(answer_assembly.get("seed_anchors") or []),
        "reconstructed_terms": chosen,
        "trace_steps": len(trace),
        "status": status,
        "reason": reason,
        "render_allowed": status == "replayable",
        "truth_boundary": {
            "counts_are_state": True,
            "walked_path_is_replay_source": True,
            "no_missing_state_fill": True,
            "not_fact_authority": True,
            "not_document_claim": True,
        },
    }


def _chosen_terms(answer_assembly: dict[str, Any]) -> list[str]:
    path = answer_assembly.get("answer_path")
    if isinstance(path, dict):
        chosen = _clean_list(path.get("chosen_anchors") or [])
        if chosen:
            return chosen
        steps = path.get("steps")
        if isinstance(steps, list):
            stepped = _clean_list([
                row.get("chosen_anchor") or row.get("selected_anchor") or ""
                for row in steps
                if isinstance(row, dict)
            ])
            if stepped:
                return stepped

    terms = answer_assembly.get("terms")
    if isinstance(terms, list):
        return _clean_list([
            row.get("anchor") or row.get("symbol") or ""
            for row in terms
            if isinstance(row, dict)
        ])
    return []


def _clean_list(values: Any) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values or []:
        clean = str(value or "").strip().casefold()
        if clean and clean not in seen:
            seen.add(clean)
            out.append(clean)
    return out
