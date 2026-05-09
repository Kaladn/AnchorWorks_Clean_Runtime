from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any


DEFAULT_TREE_BRAIN_CONTROLS: dict[str, Any] = {
    "version": "0.2",
    "sections": {
        "tree_limits": {
            "label": "Tree Limits",
            "fields": {
                "max_depth": {"label": "Max depth", "value": 3, "default": 3, "type": "number", "min": 1, "max": 3},
                "branch_width": {"label": "Branch width", "value": 6, "default": 6, "type": "number", "min": 1, "max": 64},
                "max_total_nodes": {
                    "label": "Max total nodes",
                    "value": 22000,
                    "default": 22000,
                    "type": "number",
                    "min": 100,
                    "max": 22000,
                },
                "soft_total_nodes": {
                    "label": "Soft total nodes",
                    "value": 20000,
                    "default": 20000,
                    "type": "number",
                    "min": 50,
                    "max": 22000,
                },
                "min_count_threshold": {
                    "label": "Minimum branch count",
                    "value": 1,
                    "default": 1,
                    "type": "number",
                    "min": 1,
                    "max": 1000,
                },
                "dynamic_prune_enabled": {
                    "label": "Dynamic prune enabled",
                    "value": True,
                    "default": True,
                    "type": "boolean",
                },
            },
        },
        "rescue_layer": {
            "label": "Rescue Layer",
            "fields": {
                "rescue_enabled": {"label": "Rescue enabled", "value": True, "default": True, "type": "boolean"},
                "rescue_radius": {"label": "Rescue radius", "value": 18, "default": 18, "type": "number", "min": 1, "max": 18},
                "rescue_weight": {
                    "label": "Rescue weight",
                    "value": 0.35,
                    "default": 0.35,
                    "type": "number",
                    "min": 0,
                    "max": 1,
                    "step": 0.01,
                },
                "rescue_branch_width": {
                    "label": "Rescue branch width",
                    "value": 18,
                    "default": 18,
                    "type": "number",
                    "min": 1,
                    "max": 64,
                },
                "min_eligible_leaves_trigger": {
                    "label": "Min eligible leaves trigger",
                    "value": 8,
                    "default": 8,
                    "type": "number",
                    "min": 1,
                    "max": 64,
                },
                "confidence_trigger": {
                    "label": "Confidence trigger",
                    "value": 0.35,
                    "default": 0.35,
                    "type": "number",
                    "min": 0,
                    "max": 1,
                    "step": 0.01,
                },
                "rejection_ratio_trigger": {
                    "label": "Rejection ratio trigger",
                    "value": 3.0,
                    "default": 3.0,
                    "type": "number",
                    "min": 0,
                    "max": 100,
                    "step": 0.1,
                },
                "max_rescue_nodes": {
                    "label": "Max rescue nodes",
                    "value": 22000,
                    "default": 22000,
                    "type": "number",
                    "min": 0,
                    "max": 22000,
                },
                "require_multi_root_support": {
                    "label": "Require multi-root support",
                    "value": True,
                    "default": True,
                    "type": "boolean",
                },
            },
        },
        "answer_regulation": {
            "label": "Answer Regulation",
            "fields": {
                "level_1_limit": {"label": "Level 1 limit", "value": 8, "default": 8, "type": "number", "min": 1, "max": 64},
                "level_2_limit": {"label": "Level 2 limit", "value": 16, "default": 16, "type": "number", "min": 1, "max": 64},
                "level_3_limit": {"label": "Level 3 limit", "value": 32, "default": 32, "type": "number", "min": 1, "max": 64},
                "level_4_limit": {"label": "Level 4 limit", "value": 64, "default": 64, "type": "number", "min": 1, "max": 64},
                "level_2_evidence_threshold": {
                    "label": "Level 2 evidence threshold",
                    "value": 100,
                    "default": 100,
                    "type": "number",
                    "min": 0,
                    "max": 1000000,
                },
                "level_3_evidence_threshold": {
                    "label": "Level 3 evidence threshold",
                    "value": 500,
                    "default": 500,
                    "type": "number",
                    "min": 0,
                    "max": 1000000,
                },
                "level_4_evidence_threshold": {
                    "label": "Level 4 evidence threshold",
                    "value": 1500,
                    "default": 1500,
                    "type": "number",
                    "min": 0,
                    "max": 1000000,
                },
                "confidence_top_share_weight": {
                    "label": "Confidence top-share weight",
                    "value": 1.0,
                    "default": 1.0,
                    "type": "number",
                    "min": 0,
                    "max": 10,
                    "step": 0.1,
                },
            },
        },
        "scoring": {
            "label": "Scoring",
            "fields": {
                "direct_support_weight": {
                    "label": "Direct support weight",
                    "value": 1.0,
                    "default": 1.0,
                    "type": "number",
                    "min": 0,
                    "max": 10,
                    "step": 0.1,
                },
                "second_order_support_weight": {
                    "label": "Second-order support weight",
                    "value": 1.5,
                    "default": 1.5,
                    "type": "number",
                    "min": 0,
                    "max": 10,
                    "step": 0.1,
                },
                "cross_consensus_weight": {
                    "label": "Cross-root consensus weight",
                    "value": 3.0,
                    "default": 3.0,
                    "type": "number",
                    "min": 0,
                    "max": 20,
                    "step": 0.1,
                },
                "position_strength_weight": {
                    "label": "Position strength weight",
                    "value": 1.25,
                    "default": 1.25,
                    "type": "number",
                    "min": 0,
                    "max": 10,
                    "step": 0.05,
                },
                "path_strength_weight": {
                    "label": "Path strength weight",
                    "value": 1.5,
                    "default": 1.5,
                    "type": "number",
                    "min": 0,
                    "max": 10,
                    "step": 0.1,
                },
                "rescue_support_weight": {
                    "label": "Rescue support weight",
                    "value": 1.0,
                    "default": 1.0,
                    "type": "number",
                    "min": 0,
                    "max": 10,
                    "step": 0.1,
                },
                "low_context_penalty": {
                    "label": "Low-context penalty",
                    "value": 5.0,
                    "default": 5.0,
                    "type": "number",
                    "min": 0,
                    "max": 100,
                    "step": 0.5,
                },
            },
        },
        "diagnostics_harness": {
            "label": "Diagnostics Harness",
            "fields": {
                "fixed_query_file": {
                    "label": "Fixed query file",
                    "value": "config/policy_diagnostic_queries.json",
                    "default": "config/policy_diagnostic_queries.json",
                    "type": "text",
                },
                "latest_report_file": {
                    "label": "Latest report file",
                    "value": "reports/policy_diagnostics/latest.json",
                    "default": "reports/policy_diagnostics/latest.json",
                    "type": "text",
                },
            },
        },
    },
}


class TreeBrainControls:
    def __init__(self, path: Path, payload: dict[str, Any] | None = None) -> None:
        self.path = Path(path)
        self.payload = self.validate(payload or deepcopy(DEFAULT_TREE_BRAIN_CONTROLS))

    @classmethod
    def load(cls, path: Path) -> "TreeBrainControls":
        if not path.exists():
            controls = cls(path)
            controls.save()
            return controls
        return cls(path, json.loads(path.read_text(encoding="utf-8-sig")))

    def to_dict(self) -> dict[str, Any]:
        return deepcopy(self.payload)

    def active_values(self) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for section in self.payload.get("sections", {}).values():
            for key, field in (section.get("fields") or {}).items():
                values[key] = field.get("value")
        return values

    def update(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.payload = self.validate(payload)
        self.save()
        return self.to_dict()

    def reset(self) -> dict[str, Any]:
        self.payload = self.validate(deepcopy(DEFAULT_TREE_BRAIN_CONTROLS))
        self.save()
        return self.to_dict()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def validate(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("tree brain controls must be a JSON object")
        merged = deepcopy(DEFAULT_TREE_BRAIN_CONTROLS)
        incoming_sections = payload.get("sections") or {}
        if not isinstance(incoming_sections, dict):
            raise ValueError("tree brain controls sections must be a JSON object")
        for section_name, section in merged["sections"].items():
            incoming_fields = (incoming_sections.get(section_name) or {}).get("fields") or {}
            for key, field in section["fields"].items():
                if key in incoming_fields:
                    field["value"] = self._coerce_field_value(field, incoming_fields[key].get("value"))
        return merged

    def _coerce_field_value(self, field: dict[str, Any], raw: Any) -> Any:
        field_type = field.get("type")
        if field_type == "boolean":
            return bool(raw)
        if field_type == "number":
            value = float(raw)
            if float(value).is_integer():
                value = int(value)
            minimum = field.get("min")
            maximum = field.get("max")
            if minimum is not None and value < minimum:
                raise ValueError(f"{field.get('label')} must be >= {minimum}")
            if maximum is not None and value > maximum:
                raise ValueError(f"{field.get('label')} must be <= {maximum}")
            return value
        return str(raw)
