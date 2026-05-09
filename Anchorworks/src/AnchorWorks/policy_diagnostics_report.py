from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


TREE_VERSION = "v0.2-settings-restored"
POLICY_VERSION = "0.2"


def load_queries(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    queries = payload.get("queries")
    if not isinstance(queries, list) or not all(isinstance(query, str) for query in queries):
        raise ValueError(f"diagnostic query file must contain a string list at 'queries': {path}")
    return [query.strip() for query in queries if query.strip()]


def build_settings_report(
    queries: list[str],
    controls: dict[str, Any],
    symbol_policy: dict[str, Any],
    generated_at: str | None = None,
) -> dict[str, Any]:
    sections = controls.get("sections") or {}
    policy_counts = Counter(
        key for key, value in symbol_policy.items() if isinstance(value, list) for _ in value
    )
    control_fields = Counter()
    for section_name, section in sections.items():
        fields = section.get("fields") or {}
        control_fields[str(section_name)] = len(fields)

    return {
        "tree_version": TREE_VERSION,
        "policy_version": str(controls.get("version") or POLICY_VERSION),
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "tests_baseline": "settings harness; reasoner not wired",
        "query_count": len(queries),
        "queries": [
            {
                "query": query,
                "ranked_answer_symbols": [],
                "evidence_rows": [],
                "answer_level": None,
                "confidence": 0.0,
                "used_rescue_layer": False,
                "policy_diagnostics": {
                    "status": "settings_loaded_only",
                    "note": "Tree-Brain settings UI is restored; document reasoner diagnostics are not wired in this runtime.",
                },
            }
            for query in queries
        ],
        "aggregate": {
            "accepted_by_class": dict(sorted(control_fields.items())),
            "rejected_by_reason": {},
            "top_accepted_symbols": [
                {"symbol": key, "anchor": key, "reason": "symbol_policy_list_size", "count": count, "score": 0.0}
                for key, count in sorted(policy_counts.items())
            ][:10],
            "top_rejected_symbols": [],
        },
    }
