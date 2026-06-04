from __future__ import annotations

from pathlib import Path
from typing import Any


SETTINGS_INVENTORY_SCHEMA_VERSION = "anchorworks_settings_inventory@1"


def build_settings_inventory(app_root: str | Path) -> dict[str, Any]:
    root = Path(app_root).expanduser().resolve()
    config_root = root / "config"
    data_root = root.parent
    rows = [
        {
            "id": "tree_brain_controls",
            "label": "Tree-Brain Controls",
            "path": str(config_root / "tree_brain_controls.json"),
            "classification": "diagnostic_only",
            "runtime_active": False,
            "reason": "Saved and validated, but not wired into the active ClearSpeak renderer/count walk runtime.",
        },
        {
            "id": "symbol_policy",
            "label": "Symbol Policy Lists",
            "path": str(config_root / "symbol_policy.json"),
            "classification": "diagnostic_policy",
            "runtime_active": False,
            "reason": "Saved and validated for diagnostics; active renderer still uses built-in glue/noise policy paths.",
        },
        {
            "id": "policy_diagnostic_queries",
            "label": "Policy Diagnostic Queries",
            "path": str(config_root / "policy_diagnostic_queries.json"),
            "classification": "diagnostic",
            "runtime_active": False,
            "reason": "Used by the settings diagnostics harness only.",
        },
        {
            "id": "symbol_genome_pool",
            "label": "Symbol Genome Pool",
            "path": str(data_root / "State" / "symbol_genome_pool" / "manifest.json"),
            "classification": "runtime",
            "runtime_active": True,
            "reason": "Backend allocation/checkpoint routes consume this manifest as the live symbol cursor.",
        },
    ]
    for row in rows:
        path = Path(str(row["path"]))
        row["exists"] = path.exists()
    return {
        "schema_version": SETTINGS_INVENTORY_SCHEMA_VERSION,
        "settings": rows,
        "law": "If a switch does not move runtime, it must say diagnostic-only or leave main Settings.",
    }
