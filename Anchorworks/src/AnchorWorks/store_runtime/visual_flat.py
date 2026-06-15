from __future__ import annotations

from ..store_support import *


class VisualFlatMixin:
    def _ensure_flat_document_dirs(self) -> None:
        self.flat_documents_raw_dir.mkdir(parents=True, exist_ok=True)
        self.flat_documents_symbolic_dir.mkdir(parents=True, exist_ok=True)
        self.flat_documents_block_index_dir.mkdir(parents=True, exist_ok=True)
        self.flat_documents_visual_links_dir.mkdir(parents=True, exist_ok=True)
        self.flat_documents_occurrence_index_dir.mkdir(parents=True, exist_ok=True)
        self.flat_documents_local_overlays_dir.mkdir(parents=True, exist_ok=True)

    def _visual_safe_stem(self, source_name: str, visual_record_id: str) -> str:
        original = Path(source_name or "visual").stem
        safe_stem = "".join(
            char if char.isalnum() or char in {"-", "_"} else "_"
            for char in original
        ).strip("_")
        if not safe_stem:
            safe_stem = "visual"
        return f"{safe_stem}-{visual_record_id}"

    def _persist_visual_intake_packet(self, prepared: dict[str, Any]) -> dict[str, Any] | None:
        metadata = prepared.get("metadata")
        if not isinstance(metadata, dict):
            return None
        visual_manifest = metadata.get("visual_manifest")
        visual_region_map = metadata.get("visual_region_map")
        visual_recognition_layer = metadata.get("visual_recognition_layer")
        if not all(isinstance(item, dict) for item in (visual_manifest, visual_region_map, visual_recognition_layer)):
            return None

        source = visual_manifest.get("source") if isinstance(visual_manifest, dict) else {}
        visual_record_id = str((source or {}).get("visual_record_id") or "").strip()
        if not visual_record_id:
            return None
        region_map_id = str(visual_region_map.get("region_map_id") or visual_record_id).strip()
        recognition_layer_id = str(visual_recognition_layer.get("recognition_layer_id") or visual_record_id).strip()
        safe_stem = self._visual_safe_stem(str(prepared.get("source_name") or "visual"), visual_record_id)

        manifest_path = self.visual_intake_manifests_dir / f"{safe_stem}.manifest.json"
        region_map_path = self.visual_intake_region_maps_dir / f"{safe_stem}-{region_map_id}.region_map.json"
        recognition_layer_path = self.visual_intake_recognition_layers_dir / f"{safe_stem}-{recognition_layer_id}.recognition_layer.json"
        packet_path = self.visual_intake_packets_dir / f"{safe_stem}.visual_packet.json"

        writes_allowed = {"maps": False, "counts": False, "lifetime": False, "lexicon": False}
        packet = {
            "schema_version": "anchorworks_visual_intake_packet@1",
            "saved_at": _utc_now(),
            "source_name": str(prepared.get("source_name") or ""),
            "source_path": str(prepared.get("source_path") or ""),
            "file_type": str(prepared.get("file_type") or ""),
            "original_size": int(prepared.get("original_size") or 0),
            "sha256": str(prepared.get("sha256") or ""),
            "converter": str(prepared.get("converter") or ""),
            "visual_record_id": visual_record_id,
            "region_map_id": region_map_id,
            "recognition_layer_id": recognition_layer_id,
            "authority": "source_local_visual_evidence",
            "approval_status": "preview_only",
            "writes_allowed": writes_allowed,
            "visual_manifest": visual_manifest,
            "visual_region_map": visual_region_map,
            "visual_recognition_layer": visual_recognition_layer,
            "trace": {
                "source": "lexicon_intake_prepare",
                "write_intent": "source_local_visual_intake_packet",
                "promotion_required": True,
            },
        }

        self._write_json(manifest_path, visual_manifest)
        self._write_json(region_map_path, visual_region_map)
        self._write_json(recognition_layer_path, visual_recognition_layer)
        self._write_json(packet_path, packet)

        return {
            "schema_version": "anchorworks_visual_intake_packet@1",
            "visual_record_id": visual_record_id,
            "region_map_id": region_map_id,
            "recognition_layer_id": recognition_layer_id,
            "packet_path": str(packet_path),
            "manifest_path": str(manifest_path),
            "region_map_path": str(region_map_path),
            "recognition_layer_path": str(recognition_layer_path),
            "authority": "source_local_visual_evidence",
            "approval_status": "preview_only",
            "writes_allowed": writes_allowed,
        }

    def visual_intake_files(self) -> dict[str, Any]:
        packets: list[dict[str, Any]] = []
        for path in sorted(self.visual_intake_packets_dir.glob("*.visual_packet.json"), key=lambda item: item.name.lower()):
            data = self._read_json(path, {})
            source = data.get("visual_manifest", {}).get("source", {}) if isinstance(data, dict) else {}
            packets.append({
                "name": path.name,
                "path": str(path),
                "size_bytes": path.stat().st_size,
                "visual_record_id": str(data.get("visual_record_id") or ""),
                "source_name": str(data.get("source_name") or ""),
                "file_type": str(data.get("file_type") or ""),
                "width": source.get("width"),
                "height": source.get("height"),
                "aspect_ratio": source.get("aspect_ratio"),
                "approval_status": str(data.get("approval_status") or "preview_only"),
            })
        return {
            "ok": True,
            "root": str(self.visual_intake_dir),
            "packet_count": len(packets),
            "packets": packets,
        }

    def load_visual_intake_packet(self, name: str) -> dict[str, Any]:
        packet_path = (self.visual_intake_packets_dir / Path(name).name).resolve()
        if packet_path.parent != self.visual_intake_packets_dir.resolve():
            raise ValueError("invalid visual packet name")
        if not packet_path.exists() or not packet_path.is_file():
            raise FileNotFoundError(packet_path)
        data = self._read_json(packet_path, {})
        if not isinstance(data, dict):
            raise ValueError("invalid visual packet")
        data["packet_path"] = str(packet_path)
        return data

    def flat_document_files(self) -> dict[str, Any]:
        raw_files = []
        for path in sorted(self.flat_documents_raw_dir.glob("*"), key=lambda item: item.name.lower()):
            if path.is_file():
                raw_files.append({"name": path.name, "path": str(path), "size_bytes": path.stat().st_size})
        symbolic_files = []
        for path in sorted(self.flat_documents_symbolic_dir.glob("*.symbolic.json"), key=lambda item: item.name.lower()):
            payload = self._read_json(path, {})
            symbolic_files.append({
                "name": path.name,
                "path": str(path),
                "source_name": payload.get("source_name") or "",
                "total_anchor_observations": int(payload.get("total_anchor_observations", 0) or 0),
                "unique_anchor_count": int(payload.get("unique_anchor_count", 0) or 0),
            })
        return {
            "ok": True,
            "raw_root": str(self.flat_documents_raw_dir),
            "symbolic_root": str(self.flat_documents_symbolic_dir),
            "block_index_root": str(self.flat_documents_block_index_dir),
            "visual_links_root": str(self.flat_documents_visual_links_dir),
            "occurrence_index_root": str(self.flat_documents_occurrence_index_dir),
            "local_overlay_root": str(self.flat_documents_local_overlays_dir),
            "raw_files": raw_files,
            "symbolic_files": symbolic_files,
        }

    def load_flat_document(self, name: str) -> dict[str, Any]:
        filename = Path(name).name
        raw_path = (self.flat_documents_raw_dir / filename).resolve()
        symbolic_path = (self.flat_documents_symbolic_dir / filename).resolve()
        if raw_path.parent == self.flat_documents_raw_dir.resolve() and raw_path.exists() and raw_path.is_file():
            return {"ok": True, "name": raw_path.name, "path": str(raw_path), "content": raw_path.read_text(encoding="utf-8", errors="replace")}
        if symbolic_path.parent == self.flat_documents_symbolic_dir.resolve() and symbolic_path.exists() and symbolic_path.is_file():
            return {"ok": True, **self._read_json(symbolic_path, {})}
        raise FileNotFoundError(name)

    def load_local_overlay_for_symbolic_document(self, saved_document_name: str) -> dict[str, Any] | None:
        clean = str(saved_document_name or "").strip()
        suffix = ".symbolic.json"
        if not clean.endswith(suffix):
            return None
        overlay_name = clean[: -len(suffix)] + ".local_overlay.awlo.json"
        overlay_path = (self.flat_documents_local_overlays_dir / overlay_name).resolve()
        if overlay_path.parent != self.flat_documents_local_overlays_dir.resolve():
            return None
        if not overlay_path.exists() or not overlay_path.is_file():
            return None
        return load_local_meta_count_overlay(overlay_path)

    def match_phrase_authority(self, anchors: list[str]) -> dict[str, Any] | None:
        return self.phrases.match_phrase(anchors)

    def build_phrase_candidate_review(
        self,
        *,
        min_length: int = 2,
        max_length: int = 5,
        min_count: int = 2,
        max_candidates: int = 5000,
        limit: int | None = None,
    ) -> dict[str, Any]:
        review = build_phrase_candidates_from_symbolic_dir(
            self.flat_documents_symbolic_dir,
            min_length=min_length,
            max_length=max_length,
            min_count=min_count,
            max_candidates=max_candidates,
            limit=limit,
        )
        written = write_phrase_candidate_review(self.phrase_candidates_dir, review)
        return {
            **written,
            "candidate_count": int(review.get("candidate_count", 0) or 0),
            "symbolic_doc_count": int(review.get("symbolic_doc_count", 0) or 0),
            "writes_allowed": review["writes_allowed"],
        }

    def build_phrase_candidate_review_from_observed_maps(
        self,
        *,
        min_length: int = 2,
        max_length: int = 5,
        min_count: int = 2,
        max_candidates: int = 5000,
        limit: int | None = None,
    ) -> dict[str, Any]:
        return write_phrase_candidate_review_from_observed_maps(
            self.observed_maps_dir,
            self.phrase_candidates_dir,
            symbolic_map_dir=self.symbolic_maps_dir,
            min_length=min_length,
            max_length=max_length,
            min_count=min_count,
            max_candidates=max_candidates,
            limit=limit,
        )

    def anchorize_flat_document(self, source_path: Path | None = None, *, name: str = "") -> dict[str, Any]:
        raw_root = self.flat_documents_raw_dir.resolve()
        source = Path(source_path).expanduser().resolve() if source_path else (raw_root / Path(name).name).resolve()
        if source.parent != raw_root:
            raise ValueError("flat document source must live under the raw flat document root")
        if not source.exists() or not source.is_file():
            raise FileNotFoundError(source.name)
        self._ensure_flat_document_dirs()
        prepared = prepare_file(source)
        inventory = self._extract_document_anchor_inventory(prepared.prepared_text)
        observed_counts: Counter[str] = inventory["observed_counts"]
        known_anchors = set(self._all_known_anchors())
        missing = sorted(anchor for anchor in observed_counts if anchor not in known_anchors)
        if missing:
            raise ValueError("flat document has unresolved anchors: " + ", ".join(missing[:12]))
        mapping = build_anchor_map(prepared.prepared_text, window_radius=DEFAULT_WINDOW_RADIUS)
        target = self.flat_documents_symbolic_dir / f"{source.stem}.symbolic.json"
        payload = {
            "schema_version": "flat_symbolic_document@1",
            "saved_at": _utc_now(),
            "source_path": str(source),
            "source_name": source.name,
            "saved_document_name": target.name,
            "paragraph_count": mapping["paragraph_count"],
            "window_radius": mapping["window_radius"],
            "total_anchor_observations": int(sum(mapping["observed_counts"].values())),
            "unique_anchor_count": len(mapping["observed_counts"]),
            "paragraphs": mapping["paragraphs"],
            "occurrences": mapping["occurrences"],
            "anchor_index": mapping["anchor_index"],
            "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
        }
        self._write_json(target, payload)
        return {"ok": True, "saved_document_name": target.name, "saved_document_path": str(target), **payload}

    def build_flat_runtime_from_observed_map(self, observed_map_name: str) -> dict[str, Any]:
        path = self._resolve_observed_map_name(observed_map_name)
        if not path.exists():
            raise FileNotFoundError(observed_map_name)
        payload = self._read_json(path, {})
        if not isinstance(payload, dict):
            raise ValueError(f"invalid observed map: {path.name}")

        source_name = str(payload.get("source_name") or Path(str(payload.get("source_path") or "document")).name or "document")
        source_path = str(payload.get("source_path") or "")
        source_hash = str((payload.get("document_prep") or {}).get("sha256") or hashlib.sha256(source_path.encode("utf-8")).hexdigest())
        source_id = hashlib.sha1((source_path + "\n" + source_hash + "\n" + path.name).encode("utf-8")).hexdigest()
        stem = self._flat_runtime_stem(source_name, source_id)
        self._ensure_flat_document_dirs()

        symbolic_path = self.flat_documents_symbolic_dir / f"{stem}.symbolic.json"
        block_index_path = self.flat_documents_block_index_dir / f"{stem}.blocks.jsonl"
        occurrence_index_path = self.flat_documents_occurrence_index_dir / f"{stem}.occurrences.jsonl"
        visual_links_path = self.flat_documents_visual_links_dir / f"{stem}.visual_links.jsonl"
        local_overlay_path = self.flat_documents_local_overlays_dir / f"{stem}.local_overlay.awlo.json"

        paragraphs = [row for row in payload.get("paragraphs") or [] if isinstance(row, dict)]
        occurrences = [row for row in payload.get("occurrences") or [] if isinstance(row, dict)]
        occurrence_rows: list[dict[str, Any]] = []
        for occurrence in occurrences:
            paragraph_id = int(occurrence.get("paragraph_id", 0) or 0)
            occurrence_rows.append({
                "schema_version": "flat_symbolic_occurrence@1",
                "source_id": source_id,
                "source_name": source_name,
                "source_path": source_path,
                "source_hash": source_hash,
                "block_id": f"block_{paragraph_id}",
                "block_ordinal": paragraph_id,
                "line_start": int(occurrence.get("line_start", 0) or 0),
                "line_end": int(occurrence.get("line_end", 0) or 0),
                "anchor": str(occurrence.get("anchor") or ""),
                "observed_anchor": str(occurrence.get("observed_anchor") or occurrence.get("anchor") or ""),
                "surface": str(occurrence.get("surface") or ""),
                "position": int(occurrence.get("position", 0) or 0),
                "start": int(occurrence.get("start", 0) or 0),
                "end": int(occurrence.get("end", 0) or 0),
                "count_eligible": bool(occurrence.get("count_eligible", True)),
            })

        occurrences_by_paragraph: dict[int, list[dict[str, Any]]] = {}
        for occurrence in occurrence_rows:
            occurrences_by_paragraph.setdefault(int(occurrence["block_ordinal"]), []).append(occurrence)

        block_rows: list[dict[str, Any]] = []
        visual_link_rows: list[dict[str, Any]] = []
        for paragraph in paragraphs:
            paragraph_id = int(paragraph.get("paragraph_id", len(block_rows)) or 0)
            visual_refs = [
                ref for ref in paragraph.get("visual_refs") or []
                if isinstance(ref, dict) and str(ref.get("visual_record_id") or "").strip()
            ]
            block_row = {
                "schema_version": "flat_symbolic_block@1",
                "source_id": source_id,
                "source_name": source_name,
                "source_path": source_path,
                "source_hash": source_hash,
                "observed_map_name": path.name,
                "block_id": f"block_{paragraph_id}",
                "block_ordinal": paragraph_id,
                "paragraph_id": paragraph_id,
                "line_count": max(0, int(paragraph.get("line_end", 0) or 0) - int(paragraph.get("line_start", 0) or 0) + 1)
                if int(paragraph.get("line_start", 0) or 0) > 0 else 0,
                "line_start": int(paragraph.get("line_start", 0) or 0),
                "line_end": int(paragraph.get("line_end", 0) or 0),
                "raw_text": str(paragraph.get("text") or ""),
                "anchor_stream": list(paragraph.get("resolved_anchors") or paragraph.get("anchors") or []),
                "symbol_stream": list(paragraph.get("composed_anchor_stream") or []),
                "visual_refs": visual_refs,
                "occurrence_count": len(occurrences_by_paragraph.get(paragraph_id, [])),
                "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
            }
            block_rows.append(block_row)
            for ref in visual_refs:
                visual_link_rows.append({
                    "schema_version": "flat_symbolic_visual_link@1",
                    "source_id": source_id,
                    "source_name": source_name,
                    "source_path": source_path,
                    "source_hash": source_hash,
                    "block_id": block_row["block_id"],
                    "block_ordinal": paragraph_id,
                    "line_start": block_row["line_start"],
                    "line_end": block_row["line_end"],
                    "visual_record_id": str(ref.get("visual_record_id") or ""),
                    "kind": str(ref.get("kind") or ""),
                    "source_path_ref": str(ref.get("source_path") or ""),
                    "caption_block_id": str(ref.get("caption_block_id") or ""),
                    "manifest_id": str(ref.get("manifest_id") or ""),
                    "geometry_status": str(ref.get("geometry_status") or "held"),
                    "recognition_status": str(ref.get("recognition_status") or "not_run"),
                    "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
                })

        symbolic = {
            "schema_version": "flat_symbolic_document@2",
            "saved_at": _utc_now(),
            "source_id": source_id,
            "source_path": source_path,
            "source_name": source_name,
            "source_hash": source_hash,
            "saved_document_name": symbolic_path.name,
            "observed_map_name": path.name,
            "observed_map_path": str(path),
            "block_count": len(block_rows),
            "occurrence_count": len(occurrence_rows),
            "visual_link_count": len(visual_link_rows),
            "paragraph_count": int(payload.get("paragraph_count", len(block_rows)) or len(block_rows)),
            "window_radius": int(payload.get("window_radius", DEFAULT_WINDOW_RADIUS) or DEFAULT_WINDOW_RADIUS),
            "total_anchor_observations": int(payload.get("total_anchor_observations", len(occurrence_rows)) or 0),
            "unique_anchor_count": int(payload.get("unique_anchor_count", 0) or 0),
            "blocks": block_rows,
            "occurrences": occurrence_rows,
            "visual_links": visual_link_rows,
            "block_index_path": str(block_index_path),
            "occurrence_index_path": str(occurrence_index_path),
            "visual_links_path": str(visual_links_path),
            "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
        }

        self._write_json(symbolic_path, symbolic)
        write_jsonl(block_index_path, block_rows)
        write_jsonl(occurrence_index_path, occurrence_rows)
        write_jsonl(visual_links_path, visual_link_rows)
        local_overlay = build_local_meta_count_overlay(
            source_id,
            symbolic,
            block_index_path,
            observed_map_debug=path.name,
        )
        self._write_json(local_overlay_path, local_overlay)

        return {
            "ok": True,
            "source_id": source_id,
            "source_name": source_name,
            "source_path": source_path,
            "source_hash": source_hash,
            "observed_map_name": path.name,
            "observed_map_path": str(path),
            "symbolic_document_name": symbolic_path.name,
            "symbolic_document_path": str(symbolic_path),
            "block_index_path": str(block_index_path),
            "occurrence_index_path": str(occurrence_index_path),
            "visual_links_path": str(visual_links_path),
            "local_overlay_path": str(local_overlay_path),
            "block_count": len(block_rows),
            "occurrence_count": len(occurrence_rows),
            "visual_link_count": len(visual_link_rows),
            "local_overlay_relation_count": len(local_overlay["local_relation_counts"]),
            "writes_allowed": symbolic["writes_allowed"],
        }

    def search_flat_document_evidence(
        self,
        anchors: list[str],
        *,
        query_anchors: list[str] | None = None,
        max_files: int = 32,
        max_index_bytes: int = 64 * 1024 * 1024,
    ) -> dict[str, Any]:
        query_set = {self.normalize_anchor(anchor) for anchor in anchors or [] if self.normalize_anchor(anchor)}
        query_anchor_set = {self.normalize_anchor(anchor) for anchor in query_anchors or [] if self.normalize_anchor(anchor)}
        if not query_set and not query_anchor_set:
            return {
                "runtime_source": "flat_symbolic_documents",
                "query_anchors": [],
                "files_scanned": 0,
                "files_with_query_symbols": 0,
                "files_skipped": [],
                "source_passages": [],
            }

        files_scanned = 0
        files_skipped: list[dict[str, Any]] = []
        file_hits: list[dict[str, Any]] = []
        source_passages: list[dict[str, Any]] = []
        for path in sorted(self.flat_documents_block_index_dir.glob("*.blocks.jsonl"), key=lambda item: item.stat().st_mtime, reverse=True):
            if files_scanned >= max_files:
                break
            stat = path.stat()
            if stat.st_size > max_index_bytes:
                files_skipped.append({"block_index_name": path.name, "reason": "block_index_too_large_for_interactive_scan", "size_bytes": int(stat.st_size)})
                continue
            files_scanned += 1
            block_hits: list[dict[str, Any]] = []
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    block = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(block, dict):
                    continue
                block_anchors = {self.normalize_anchor(anchor) for anchor in block.get("anchor_stream") or []}
                text = str(block.get("raw_text") or "")
                anchor_rows = extract_anchor_rows(text)
                ordered_text_anchors = [
                    self.normalize_anchor(row["anchor"])
                    for row in anchor_rows
                    if self.normalize_anchor(row["anchor"])
                ]
                text_anchors = set(ordered_text_anchors)
                hits = sorted((query_set | query_anchor_set) & (block_anchors | text_anchors))
                if not hits:
                    continue
                anchor_count = max(1, len(block_anchors | text_anchors))
                score = float(len(hits) * 100 + len(hits) / anchor_count)
                proximity_span = _query_proximity_span(ordered_text_anchors, list(query_anchor_set or query_set))
                if proximity_span is not None:
                    score += max(0.0, 90.0 - float(proximity_span * 12))
                block_id_text = str(block.get("block_id") or "block_0")
                try:
                    block_number = int(block_id_text.rsplit("_", 1)[-1])
                except ValueError:
                    block_number = int(block.get("block_ordinal", 0) or 0)
                block_hits.append({
                    "source": "flat_symbolic_document",
                    "source_name": block.get("source_name") or "",
                    "source_path": block.get("source_path") or "",
                    "source_id": block.get("source_id") or "",
                    "source_hash": block.get("source_hash") or "",
                    "saved_document_name": path.name.replace(".blocks.jsonl", ".symbolic.json"),
                    "block_id": block_number,
                    "block_label": block_id_text,
                    "paragraph_id": int(block.get("paragraph_id", block_number) or 0),
                    "line_start": int(block.get("line_start", 0) or 0),
                    "line_end": int(block.get("line_end", 0) or 0),
                    "score": score,
                    "anchor_hits": hits,
                    "anchor_count": len(block_anchors),
                    "text": _query_centered_snippet(text, anchor_rows, list(query_anchor_set or query_set)) or text.strip(),
                    "raw_block_text": text.strip(),
                    "visual_refs": block.get("visual_refs") or [],
                })
            if block_hits:
                block_hits.sort(key=lambda row: (-float(row.get("score", 0.0) or 0.0), int(row.get("block_id", 0) or 0)))
                source_passages.extend(block_hits[:8])
                file_hits.append({
                    "block_index_name": path.name,
                    "passage_count": len(block_hits),
                    "top_score": float(block_hits[0].get("score", 0.0) or 0.0),
                })

        source_passages.sort(key=lambda row: (-float(row.get("score", 0.0) or 0.0), str(row.get("source_name") or ""), int(row.get("block_id", 0) or 0)))
        return {
            "runtime_source": "flat_symbolic_documents",
            "query_anchors": sorted(query_anchor_set or query_set),
            "files_scanned": files_scanned,
            "files_with_query_symbols": len(file_hits),
            "file_hits": file_hits,
            "files_skipped": files_skipped,
            "source_passages": source_passages[:12],
        }
