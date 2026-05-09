from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


POLICY_LIST_KEYS = [
    "blocked_leaf",
    "glue",
    "conversational_generic",
    "relation_eligible",
    "domain_eligible",
    "generic_noise",
]


@dataclass(frozen=True)
class SymbolDecision:
    eligible: bool
    eligibility_class: str
    winner_reason: str | None
    rejection_reason: str | None


class SymbolPolicy:
    def __init__(self, categories: dict[str, Any] | None = None) -> None:
        self.categories = self._normalize_categories(categories or {})

    @classmethod
    def load(cls, policy_path: str | Path) -> "SymbolPolicy":
        path = Path(policy_path)
        if not path.is_file():
            raise FileNotFoundError(f"symbol policy file not found: {path}")
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict):
            raise ValueError(f"symbol policy must be a JSON object: {path}")
        return cls(payload)

    @staticmethod
    def normalize(symbol: str | None) -> str:
        return str(symbol or "").casefold().strip()

    @classmethod
    def _normalize_categories(cls, categories: dict[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {
            "numeric_policy": str(categories.get("numeric_policy", "reject_leaf")),
            "punctuation_policy": str(categories.get("punctuation_policy", "reject_leaf")),
        }
        for key in POLICY_LIST_KEYS:
            values = categories.get(key, [])
            if not isinstance(values, list):
                raise ValueError(f"symbol policy '{key}' must be a list")
            normalized[key] = {cls.normalize(item) for item in values}
        return normalized
