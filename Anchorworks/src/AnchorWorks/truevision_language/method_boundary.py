from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_MANIFEST_FLAGS = {
    "generated_media_excluded": True,
    "anchorworks_runtime_imports_disallowed": True,
}


def load_truevision_method_manifest(path: str | Path) -> dict[str, Any]:
    """Load and validate the copied TrueVision method boundary manifest."""

    manifest_path = Path(path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _validate_method_manifest(manifest)
    return manifest


def _validate_method_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("authority") != "reference_method_only":
        raise ValueError("TrueVision method copy must be reference_method_only")
    for key, expected in REQUIRED_MANIFEST_FLAGS.items():
        if manifest.get(key) is not expected:
            raise ValueError(f"TrueVision method manifest requires {key}={expected}")
    copied_sources = manifest.get("copied_sources")
    if not isinstance(copied_sources, list) or not copied_sources:
        raise ValueError("TrueVision method manifest requires copied_sources")
    for item in copied_sources:
        if item.get("use") != "read_only_reference":
            raise ValueError("copied TrueVision method sources must be read_only_reference")
