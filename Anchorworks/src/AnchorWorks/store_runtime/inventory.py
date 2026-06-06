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
        stream_path = self.symbol_streams_dir / "source_local_symbol_counts.awss"
        cells_root = self.symbol_counts_binary_dir / "cells"
        cell_count = sum(1 for _ in cells_root.glob("*/*.cell")) if cells_root.exists() else 0
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
            "awss_stream_path": str(stream_path),
            "awss_stream_exists": stream_path.exists(),
            "awss_stream_size_bytes": stream_path.stat().st_size if stream_path.exists() else 0,
            "awsc_cells_root": str(cells_root),
            "canonical_seed_counts_root": str(self.canonical_symbol_counts_binary_dir),
            "active_binary_counts_root": str(self.symbol_counts_binary_dir),
            "user_count_acknowledgement_path": seed["acknowledgement_path"],
            "awsc_cell_count": cell_count,
            "runtime_law": "AWSM serves; JSON witnesses; AWSC counts.",
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

    def search_observed_map_evidence(
        self,
        anchors: list[str],
        *,
        query_anchors: list[str] | None = None,
        map_limit: int = 12,
        max_map_bytes: int = 128 * 1024 * 1024,
    ) -> dict[str, Any]:
        query_set = {self.normalize_anchor(anchor) for anchor in anchors if self.normalize_anchor(anchor)}
        query_anchor_set = {self.normalize_anchor(anchor) for anchor in (query_anchors or []) if self.normalize_anchor(anchor)}
        if not query_set and query_anchor_set:
            query_set = set(query_anchor_set)
        source_passages: list[dict[str, Any]] = []
        map_hits: list[dict[str, Any]] = []
        maps_scanned = 0
        maps_skipped: list[dict[str, Any]] = []
        max_maps = max(1, min(int(map_limit or 12), 100))

        for path in sorted(self.observed_maps_dir.glob("*.observed.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            if maps_scanned >= max_maps:
                break
            stat = path.stat()
            if stat.st_size > max_map_bytes:
                maps_skipped.append({"saved_map_name": path.name, "reason": "map_file_too_large_for_interactive_scan", "size_bytes": int(stat.st_size)})
                continue
            payload = self._read_json(path, {})
            if not isinstance(payload, dict):
                continue
            maps_scanned += 1
            locators = payload.get("paragraph_line_locators")
            if not isinstance(locators, dict):
                locators = self._paragraph_line_locators(payload)
            passage_rows: list[dict[str, Any]] = []
            for paragraph in payload.get("paragraphs") or []:
                if not isinstance(paragraph, dict):
                    continue
                paragraph_anchors = {self.normalize_anchor(anchor) for anchor in paragraph.get("anchors") or []}
                paragraph_anchors.update(self.normalize_anchor(anchor) for anchor in paragraph.get("resolved_anchors") or [])
                text = str(paragraph.get("text") or "")
                text_anchors = {self.normalize_anchor(row["anchor"]) for row in extract_anchor_rows(text)}
                hits = sorted((query_set | query_anchor_set) & (paragraph_anchors | text_anchors))
                if not hits:
                    continue
                paragraph_id = int(paragraph.get("paragraph_id", len(passage_rows)) or 0)
                locator = locators.get(str(paragraph_id)) or locators.get(paragraph_id) or {}
                score = float(len(hits) * 100 + len(hits) / max(1, int(paragraph.get("anchor_count", 1) or 1)))
                passage_rows.append({
                    "source_name": payload.get("source_name") or "",
                    "source_path": payload.get("source_path") or "",
                    "saved_map_name": path.name,
                    "paragraph_id": paragraph_id,
                    "block_id": int(locator.get("block_id", paragraph_id) or 0),
                    "line_start": int(locator.get("line_start", 0) or 0),
                    "line_end": int(locator.get("line_end", 0) or 0),
                    "score": score,
                    "anchor_hits": hits,
                    "anchor_count": int(paragraph.get("anchor_count", 0) or 0),
                    "text": text.strip(),
                })
            if passage_rows:
                passage_rows.sort(key=lambda row: (-float(row.get("score", 0.0) or 0.0), int(row.get("paragraph_id", 0) or 0)))
                source_passages.extend(passage_rows[:8])
                map_hits.append({
                    "saved_map_name": path.name,
                    "source_name": payload.get("source_name") or "",
                    "source_path": payload.get("source_path") or "",
                    "passage_count": len(passage_rows),
                    "top_score": float(passage_rows[0].get("score", 0.0) or 0.0),
                })

        source_passages.sort(key=lambda row: (-float(row.get("score", 0.0) or 0.0), str(row.get("source_name") or ""), int(row.get("paragraph_id", 0) or 0)))
        return {
            "query_anchors": sorted(query_anchor_set or query_set),
            "maps_scanned": maps_scanned,
            "maps_with_query_symbols": len(map_hits),
            "map_hits": map_hits,
            "maps_skipped": maps_skipped,
            "source_passages": source_passages[:12],
        }
