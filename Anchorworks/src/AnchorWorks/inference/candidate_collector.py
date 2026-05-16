from __future__ import annotations

from typing import Any


def collect_candidates(answer_assembly: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for index, row in enumerate(answer_assembly.get("terms") or [], start=1):
        if not isinstance(row, dict):
            continue
        anchor = str(row.get("anchor") or "").strip().casefold()
        if not anchor:
            continue
        candidates.append({
            "symbol": anchor,
            "anchor": anchor,
            "lane": str(row.get("lane") or "counts"),
            "role": _candidate_role(row),
            "evidence": row,
            "support_score": float(row.get("score") or row.get("selection_score") or 0.0),
            "status": "pending",
            "candidate_rank": int(row.get("candidate_rank") or index),
        })
    return candidates


def _candidate_role(row: dict[str, Any]) -> str:
    role_fit = row.get("role_fit")
    if isinstance(role_fit, dict):
        matched = role_fit.get("matched_roles")
        if isinstance(matched, list) and matched:
            return str(matched[0])
    return "candidate_answer_anchor"
