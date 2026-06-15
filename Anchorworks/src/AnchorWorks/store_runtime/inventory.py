from __future__ import annotations

from ..store_support import *


class InventoryMixin:
    def observed_map_files(self) -> dict[str, Any]:
        files: list[dict[str, Any]] = []
        for path in sorted(self.observed_maps_dir.glob("*.observed.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            stat = path.stat()
            payload = self._read_json(path, {})
            files.append({
                "name": path.name,
                "path": str(path),
                "source_name": payload.get("source_name") or "",
                "source_path": payload.get("source_path") or "",
                "paragraph_count": int(payload.get("paragraph_count", 0) or 0),
                "unique_anchor_count": int(payload.get("unique_anchor_count", 0) or 0),
                "total_anchor_observations": int(payload.get("total_anchor_observations", 0) or 0),
                "modified": stat.st_mtime,
                "size_bytes": stat.st_size,
            })
        return {"root": str(self.observed_maps_dir), "files": files}

    def symbolic_map_files(self) -> dict[str, Any]:
        files: list[dict[str, Any]] = []
        symbolic_paths = sorted(self.symbolic_maps_dir.glob("*.awsm"), key=lambda item: item.stat().st_mtime, reverse=True)
        for path in symbolic_paths:
            stat = path.stat()
            locator_path = path.with_suffix(".locators.awsl")
            null_path = path.with_suffix(".nulls.awsn")
            visual_path = path.with_suffix(".visuals.awsv")
            files.append({
                "name": path.name,
                "path": str(path),
                "modified": stat.st_mtime,
                "size_bytes": stat.st_size,
                "locator_name": locator_path.name if locator_path.exists() else "",
                "locator_path": str(locator_path) if locator_path.exists() else "",
                "null_name": null_path.name if null_path.exists() else "",
                "null_path": str(null_path) if null_path.exists() else "",
                "visual_name": visual_path.name if visual_path.exists() else "",
                "visual_path": str(visual_path) if visual_path.exists() else "",
                "sidecars": {
                    "locators": locator_path.exists(),
                    "nulls": null_path.exists(),
                    "visuals": visual_path.exists(),
                },
            })
        return {
            "ok": True,
            "schema_version": "anchorworks_symbolic_map_inventory@1",
            "source_format": "awsm_bundle",
            "root": str(self.symbolic_maps_dir),
            "map_count": len(symbolic_paths),
            "locator_sidecar_count": len(list(self.symbolic_maps_dir.glob("*.locators.awsl"))),
            "null_sidecar_count": len(list(self.symbolic_maps_dir.glob("*.nulls.awsn"))),
            "visual_sidecar_count": len(list(self.symbolic_maps_dir.glob("*.visuals.awsv"))),
            "json_role": "witness_debug_only",
            "files": files,
            "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
        }

    def binary_substrate_status(self) -> dict[str, Any]:
        seed = self.ensure_user_symbol_counts_seeded()
        count_size = self.symbol_counts_binary_file.stat().st_size if self.symbol_counts_binary_file.exists() else 0
        record_count = int(count_size / 24) if count_size % 24 == 0 else 0
        symbolic_inventory = self.symbolic_map_files()
        return {
            "ok": True,
            "schema_version": "anchorworks_binary_substrate_status@1",
            "anchor_maps_root": str(self.anchor_maps_root),
            "observed_maps_root": str(self.observed_maps_dir),
            "symbolic_maps_root": str(self.symbolic_maps_dir),
            "json_observed_map_count": len(list(self.observed_maps_dir.glob("*.observed.json"))),
            "json_role": "witness_debug_only",
            "awsm_map_count": symbolic_inventory["map_count"],
            "awsl_locator_count": symbolic_inventory["locator_sidecar_count"],
            "awsn_null_count": symbolic_inventory["null_sidecar_count"],
            "awsv_visual_count": symbolic_inventory["visual_sidecar_count"],
            "binary_counts_path": str(self.symbol_counts_binary_file),
            "active_binary_counts_path": str(self.symbol_counts_binary_file),
            "count_file_created": seed["count_file_created"],
            "count_file_size": count_size,
            "record_count": record_count,
            "runtime_law": "Native C++ count ingest writes one binary count file; Python only orchestrates.",
        }

    def misspelled_review_files(self) -> dict[str, Any]:
        files: list[dict[str, Any]] = []
        for path in sorted(self.misspelled_reviews_dir.glob("*.misspellings.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            stat = path.stat()
            payload = self._read_json(path, {})
            files.append({
                "name": path.name,
                "path": str(path),
                "source_name": payload.get("source_name") or "",
                "source_path": payload.get("source_path") or "",
                "paragraph_count": int(payload.get("paragraph_count", 0) or 0),
                "unique_anchor_count": int(payload.get("unique_anchor_count", 0) or 0),
                "review_count": int(payload.get("review_count", 0) or 0),
                "modified": stat.st_mtime,
                "size_bytes": stat.st_size,
            })
        return {"root": str(self.misspelled_reviews_dir), "files": files}

    def load_observed_map(self, name: str) -> dict[str, Any]:
        path = self._resolve_observed_map_name(name)
        if not path.exists():
            raise FileNotFoundError(name)
        payload = self._read_json(path, {})
        if not isinstance(payload, dict):
            raise ValueError(f"invalid observed map: {path.name}")

        return {
            "ok": True,
            "source_path": payload.get("source_path") or "",
            "source_name": payload.get("source_name") or "",
            "saved_map_path": str(path),
            "saved_map_name": path.name,
            "paragraph_count": int(payload.get("paragraph_count", 0) or 0),
            "window_radius": int(payload.get("window_radius", 0) or 0),
            "total_anchor_observations": int(payload.get("total_anchor_observations", 0) or 0),
            "unique_anchor_count": int(payload.get("unique_anchor_count", 0) or 0),
            "known_anchor_count": int(payload.get("known_anchor_count", 0) or 0),
            "missing_anchor_count": int(payload.get("missing_anchor_count", 0) or 0),
            "known_anchor_observations": int(payload.get("known_anchor_observations", 0) or 0),
            "missing_anchor_observations": int(payload.get("missing_anchor_observations", 0) or 0),
            "registered_missing_anchors": len(payload.get("missing_anchors") or []),
            "known_anchors_preview": (payload.get("known_anchors") or [])[:25],
            "missing_anchors_preview": (payload.get("missing_anchors") or [])[:25],
            "observed_anchors_preview": (payload.get("observed_anchors") or [])[:25],
            "occurrence_preview": (payload.get("occurrences") or [])[:12],
            "co_occurrence_preview": (payload.get("co_occurrence_counts") or [])[:12],
            "anchor_index_preview": (payload.get("anchor_index") or [])[:25],
            "context_items_preview": list((payload.get("items") or {}).values())[:12],
            "temp_symbol_count": int(payload.get("temp_symbol_count", 0) or 0),
            "temp_lexicon_path": payload.get("temp_lexicon_path") or "",
        }

    def load_misspelled_review(self, name: str) -> dict[str, Any]:
        path = self._resolve_misspelled_review_name(name)
        if not path.exists():
            raise FileNotFoundError(name)
        payload = self._read_json(path, {})
        if not isinstance(payload, dict):
            raise ValueError(f"invalid misspelled review: {path.name}")

        return {
            "ok": True,
            "source_path": payload.get("source_path") or "",
            "source_name": payload.get("source_name") or "",
            "saved_review_path": str(path),
            "saved_review_name": path.name,
            "paragraph_count": int(payload.get("paragraph_count", 0) or 0),
            "total_anchor_observations": int(payload.get("total_anchor_observations", 0) or 0),
            "unique_anchor_count": int(payload.get("unique_anchor_count", 0) or 0),
            "review_count": int(payload.get("review_count", 0) or 0),
            "rows_preview": (payload.get("rows") or [])[:50],
        }

