from __future__ import annotations

from ..store_support import *


class CountsMixin:
    def _relation_count_rows(self, counts: Counter[tuple[str, str, str]]) -> list[dict[str, Any]]:
        return [
            {
                "anchor": anchor,
                "offset": offset,
                "neighbor": neighbor,
                "observations": observations,
            }
            for (anchor, offset, neighbor), observations in sorted(
                counts.items(),
                key=lambda item: (-item[1], item[0][0], item[0][1], item[0][2]),
            )
        ]

    def _canonical_lifetime_relation_rows(
        self,
        relation_rows: list[dict[str, Any]],
        canonical_counts: Counter[str],
    ) -> list[dict[str, Any]]:
        canonical_anchors = set(canonical_counts)
        out: list[dict[str, Any]] = []
        for row in relation_rows:
            if not isinstance(row, dict):
                continue
            anchor = row.get("anchor")
            neighbor = row.get("neighbor")
            observations = int(row.get("observations", 0) or 0)
            if not isinstance(anchor, str) or not isinstance(neighbor, str) or observations <= 0:
                continue
            if anchor not in canonical_anchors or neighbor not in canonical_anchors:
                continue
            out.append(dict(row))
        return out

    def _symbol_relation_fates(
        self,
        relation_rows: list[dict[str, Any]],
        authority_by_anchor: dict[str, str],
    ) -> dict[str, int]:
        fates = Counter()
        for row in relation_rows:
            if not isinstance(row, dict):
                continue
            anchor = str(row.get("anchor") or "")
            neighbor = str(row.get("neighbor") or "")
            observations = int(row.get("observations", 0) or 0)
            if observations <= 0:
                continue
            anchor_authority = authority_by_anchor.get(anchor, "unresolved")
            neighbor_authority = authority_by_anchor.get(neighbor, "unresolved")
            if anchor_authority == "canonical" and neighbor_authority == "canonical":
                fates["canonical_to_canonical"] += observations
            elif "unresolved" in {anchor_authority, neighbor_authority}:
                fates["unresolved_relation"] += observations
            elif "source_local" in {anchor_authority, neighbor_authority}:
                fates["source_local_relation"] += observations
            else:
                fates["other_relation"] += observations
        return dict(sorted(fates.items()))

    def _symbol_relation_fates_from_symbol_rows(
        self,
        relation_rows: list[dict[str, Any]],
        authority_by_symbol: dict[str, str],
    ) -> dict[str, int]:
        fates = Counter()
        for row in relation_rows:
            if not isinstance(row, dict):
                continue
            root = str(row.get("symbol_anchor") or "")
            neighbor = str(row.get("neighbor_symbol_anchor") or "")
            observations = int(row.get("observations", 0) or 0)
            if observations <= 0:
                continue
            root_authority = authority_by_symbol.get(root, "unresolved")
            neighbor_authority = authority_by_symbol.get(neighbor, "unresolved")
            if root_authority == "canonical" and neighbor_authority == "canonical":
                fates["canonical_to_canonical"] += observations
            elif "unresolved" in {root_authority, neighbor_authority}:
                fates["unresolved_relation"] += observations
            elif "source_local" in {root_authority, neighbor_authority}:
                fates["source_local_relation"] += observations
            else:
                fates["other_relation"] += observations
        return dict(sorted(fates.items()))

    def ensure_user_symbol_counts_seeded(self) -> dict[str, Any]:
        with self._lock:
            self.user_counts_dir.mkdir(parents=True, exist_ok=True)
            count_file_created = False
            if not self.symbol_counts_binary_file.exists():
                self.symbol_counts_binary_file.write_bytes(b"")
                count_file_created = True
        return {
            "ok": True,
            "seeded": count_file_created,
            "count_file_created": count_file_created,
            "active_binary_counts_path": str(self.symbol_counts_binary_file),
            "count_spine": "single_awss_binary_stream",
            "json_counts_allowed": False,
        }

    def _canonical_seed_symbol_values(self) -> list[str]:
        symbols: list[str] = []
        seen: set[str] = set()
        seed_paths = [path for _, path in self._pack_paths("canonical")]
        canonical_structural = self.canonical_dir / "structural.json"
        if canonical_structural.exists():
            seed_paths.append(canonical_structural)
        if self.structural_file.exists():
            seed_paths.append(self.structural_file)
        for path in seed_paths:
            for entry in self._read_entries(path):
                symbol = str(entry.get("hex") or entry.get("symbol") or "").strip()
                if not symbol:
                    continue
                text = symbol[2:] if symbol.lower().startswith("0x") else symbol
                text = text.upper().zfill(10)
                if len(text) != 10 or text in seen:
                    continue
                seen.add(text)
                symbols.append("0x" + text)
        return symbols

    def _symbol_text(self, symbol: str | bytes) -> str:
        if isinstance(symbol, bytes):
            return "0x" + symbol.hex().upper()
        text = str(symbol or "").strip()
        if not text:
            return ""
        if text.lower().startswith("0x"):
            text = text[2:]
        return "0x" + text.upper().zfill(10)

    def _binary_relation_rows_for_anchor(self, anchor: str) -> list[dict[str, Any]]:
        surface = self.normalize_anchor(anchor)
        if not surface or not hasattr(self, "_canonical_symbol_by_anchor"):
            return []
        symbol_by_anchor = self._canonical_symbol_by_anchor()
        root_symbol = symbol_by_anchor.get(surface)
        if not root_symbol:
            return []
        anchor_by_symbol = {
            self._symbol_text(symbol): self.normalize_anchor(anchor_value)
            for anchor_value, symbol in symbol_by_anchor.items()
            if str(anchor_value or "").strip() and str(symbol or "").strip()
        }
        rows: list[dict[str, Any]] = []
        if self.symbol_counts_binary_file.exists():
            try:
                scored = score_binary_count_stream(
                    self.symbol_counts_binary_file,
                    context_symbols=[self._symbol_text(root_symbol)],
                    top_k=512,
                )
            except Exception:
                scored = {}
            for candidate in scored.get("candidates") or []:
                neighbor = anchor_by_symbol.get(self._symbol_text(candidate.get("symbol")))
                if not neighbor:
                    continue
                for offset_row in candidate.get("offsets") or []:
                    observations = int(offset_row.get("observations", 0) or 0)
                    if observations <= 0:
                        continue
                    rows.append({
                        "anchor": surface,
                        "offset": str(int(offset_row.get("offset", 0) or 0)),
                        "neighbor": neighbor,
                        "observations": observations,
                    })
        return rows

    def counts_status(self) -> dict[str, Any]:
        seed = self.ensure_user_symbol_counts_seeded()
        stream_size = self.symbol_counts_binary_file.stat().st_size if self.symbol_counts_binary_file.exists() else 0
        record_count = int(stream_size / 24) if stream_size % 24 == 0 else 0
        return {
            "runtime": "awss_v1_single_binary_stream",
            "binary_counts_path": str(self.symbol_counts_binary_file),
            "count_file_created": seed["count_file_created"],
            "count_file_size": stream_size,
            "record_count": record_count,
            "json_counts_removed": True,
            "ingest_events": 0,
            "unique_relations": 0,
            "total_relation_observations": 0,
            "anchor_count": 0,
            "relation_rows": record_count,
        }

    def retrieve_from_counts(self, anchor: str, limit: int = 25) -> dict[str, Any]:
        surface = self.normalize_anchor(anchor)
        total_by_neighbor: Counter[str] = Counter()
        by_offset: dict[str, Counter[str]] = {}
        for row in self._binary_relation_rows_for_anchor(surface):
            observations = int(row.get("observations", 0) or 0)
            if observations <= 0:
                continue
            offset = str(row.get("offset") or "")
            neighbor = str(row.get("neighbor") or "")
            if not offset or not neighbor:
                continue
            total_by_neighbor[neighbor] += observations
            by_offset.setdefault(offset, Counter())[neighbor] += observations

        neighbor_rows = [
            {"anchor": neighbor, "observations": count}
            for neighbor, count in sorted(total_by_neighbor.items(), key=lambda item: (-item[1], item[0]))[:limit]
        ]
        offset_rows = {
            offset: [
                {"anchor": neighbor, "observations": count}
                for neighbor, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit]
            ]
            for offset, counter in sorted(by_offset.items(), key=lambda item: (int(item[0]), item[0]))
        }
        return {
            "anchor": surface,
            "maps_scanned": len(list(self.observed_maps_dir.glob("*.observed.json"))),
            "maps_with_anchor": 1 if total_by_neighbor else 0,
            "neighbor_count": len(total_by_neighbor),
            "total_neighbor_observations": int(sum(total_by_neighbor.values())),
            "neighbors": neighbor_rows,
            "offsets": offset_rows,
        }

    def map_document_to_user_counts_native(
        self,
        source_path: str | Path,
        *,
        window_radius: int = DEFAULT_WINDOW_RADIUS,
        generation: int = 0,
    ) -> dict[str, Any]:
        source = Path(source_path).expanduser().resolve()
        if not source.exists():
            raise FileNotFoundError(source)
        if source.is_dir():
            raise IsADirectoryError(source)
        seed = self.ensure_user_symbol_counts_seeded()
        digest = hashlib.sha1(str(source).encode("utf-8")).hexdigest()[:12]
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", source.name).strip("._") or "source"
        run_root = self.ingest_staging_dir / "native_mapping" / f"{safe_name}-{digest}"
        authority_path = run_root / "authority_snapshot.json"
        manifest_path = run_root / "manifest.json"
        missing_path = run_root / "missing.json"
        stream_path = run_root / "symbol_counts_delta.bin"
        snapshot = write_authority_snapshot(self._symbol_authority_by_anchor(), authority_path)
        receipt = native_text_intake_to_counts(
            input_path=source,
            authority_path=authority_path,
            output_path=stream_path,
            manifest_path=manifest_path,
            missing_path=missing_path,
            source_id=digest,
            window_radius=window_radius,
            source_local_missing=True,
        )
        if stream_path.exists() and stream_path.stat().st_size:
            with self.symbol_counts_binary_file.open("ab") as handle:
                handle.write(stream_path.read_bytes())
        manifest = self._read_json(manifest_path, {})
        missing = self._read_json(missing_path, {})
        verify = {
            "ok": self.symbol_counts_binary_file.exists()
            and self.symbol_counts_binary_file.stat().st_size % 24 == 0,
            "record_count": int(self.symbol_counts_binary_file.stat().st_size / 24)
            if self.symbol_counts_binary_file.exists() and self.symbol_counts_binary_file.stat().st_size % 24 == 0
            else 0,
            "count_spine": "single_awss_binary_stream",
        }
        return {
            "ok": bool(receipt.get("ok")) and bool(verify.get("ok")),
            "runtime": "native_cpp_intake_text",
            "source_path": str(source),
            "run_root": str(run_root),
            "authority_snapshot": snapshot,
            "authority_path": str(authority_path),
            "manifest_path": str(manifest_path),
            "missing_path": str(missing_path),
            "active_binary_counts_path": str(self.symbol_counts_binary_file),
            "receipt": receipt,
            "manifest": manifest,
            "missing": missing,
            "verify": verify,
            "raw_text_in_count_spine": bool(manifest.get("raw_text_in_count_spine")),
        }

    def map_directory_to_user_counts_native(
        self,
        source_dir: str | Path,
        *,
        window_radius: int = DEFAULT_WINDOW_RADIUS,
        generation: int = 0,
    ) -> dict[str, Any]:
        source = Path(source_dir).expanduser().resolve()
        if not source.exists():
            raise FileNotFoundError(source)
        if not source.is_dir():
            raise NotADirectoryError(source)

        self.ensure_user_symbol_counts_seeded()
        digest = hashlib.sha1(str(source).encode("utf-8")).hexdigest()[:12]
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", source.name).strip("._") or "source_dir"
        run_root = self.ingest_staging_dir / "native_directory_mapping" / f"{safe_name}-{digest}"
        authority_path = run_root / "authority_snapshot.json"
        manifest_path = run_root / "manifest.json"
        missing_path = run_root / "missing.json"
        stream_path = run_root / "symbol_counts_delta.bin"
        snapshot = write_authority_snapshot(self._symbol_authority_by_anchor(), authority_path)
        receipt = native_directory_intake_to_counts(
            input_dir=source,
            authority_path=authority_path,
            output_path=stream_path,
            manifest_path=manifest_path,
            missing_path=missing_path,
            source_id=digest,
            window_radius=window_radius,
            source_local_missing=True,
        )
        if stream_path.exists() and stream_path.stat().st_size:
            with self.symbol_counts_binary_file.open("ab") as handle:
                handle.write(stream_path.read_bytes())
        manifest = self._read_json(manifest_path, {})
        missing = self._read_json(missing_path, {})
        verify = {
            "ok": self.symbol_counts_binary_file.exists()
            and self.symbol_counts_binary_file.stat().st_size % 24 == 0,
            "record_count": int(self.symbol_counts_binary_file.stat().st_size / 24)
            if self.symbol_counts_binary_file.exists() and self.symbol_counts_binary_file.stat().st_size % 24 == 0
            else 0,
            "count_spine": "single_awss_binary_stream",
        }
        return {
            "ok": bool(receipt.get("ok")) and bool(verify.get("ok")),
            "runtime": "native_cpp_directory_mapping",
            "source_dir": str(source),
            "run_root": str(run_root),
            "authority_snapshot": snapshot,
            "authority_path": str(authority_path),
            "manifest_path": str(manifest_path),
            "missing_path": str(missing_path),
            "file_count": int(manifest.get("file_count", 0) or 0),
            "files_mapped": int(manifest.get("file_count", 0) or 0),
            "skipped_file_count": int(manifest.get("skipped_file_count", 0) or 0),
            "skipped_files": manifest.get("skipped_files") or [],
            "failure_count": 0,
            "failures": [],
            "active_binary_counts_path": str(self.symbol_counts_binary_file),
            "receipt": receipt,
            "manifest": manifest,
            "missing": missing,
            "verify": verify,
            "files": [],
            "raw_text_in_count_spine": bool(manifest.get("raw_text_in_count_spine")),
        }

    def map_path_to_user_counts_native(
        self,
        source_path: str | Path,
        *,
        window_radius: int = DEFAULT_WINDOW_RADIUS,
        generation: int = 0,
    ) -> dict[str, Any]:
        source = Path(source_path).expanduser().resolve()
        if source.is_dir():
            return self.map_directory_to_user_counts_native(
                source,
                window_radius=window_radius,
                generation=generation,
            )
        return self.map_document_to_user_counts_native(
            source,
            window_radius=window_radius,
            generation=generation,
        )

    def map_intake_content_to_user_counts_native(
        self,
        *,
        source_name: str,
        content: str,
        intake_edits: list[dict[str, Any]] | None = None,
        window_radius: int = DEFAULT_WINDOW_RADIUS,
        generation: int = 0,
    ) -> dict[str, Any]:
        if _is_visual_preview_content(content):
            raise ValueError("visual intake preview is source-local evidence only; use a future visual approval route before mapping/counting")
        if intake_edits:
            raise ValueError("native intake mapping does not accept inline edit/null fallback; run edit/approval first, then map")
        staged_path = self._intake_upload_path(source_name=source_name, content=content)
        staged_path.write_text(content, encoding="utf-8")
        result = self.map_document_to_user_counts_native(
            staged_path,
            window_radius=window_radius,
            generation=generation,
        )
        result["source_name"] = source_name or staged_path.name
        result["staged_path"] = str(staged_path)
        result["intake_edits_applied"] = False
        return result

    def build_source_local_resonance(self, observed_map_name: str) -> dict[str, Any]:
        path = self._resolve_observed_map_name(observed_map_name)
        if not path.exists():
            raise FileNotFoundError(observed_map_name)
        payload = self._read_json(path, {})
        if not isinstance(payload, dict):
            raise ValueError(f"invalid observed map: {path.name}")

        index = build_source_local_resonance_index(payload)
        source_id = index["source_id"]
        safe_stem = index["safe_source_stem"]
        short_source = source_id[:12]
        occurrence_path = self.source_local_occurrences_dir / f"{safe_stem}-{short_source}.occurrences.jsonl"
        profile_path = self.source_local_resonance_dir / f"{safe_stem}-{short_source}.positional_profiles.jsonl"
        directional_path = self.source_local_resonance_dir / f"{safe_stem}-{short_source}.directional_resonance.jsonl"
        cloud_path = self.source_local_resonance_dir / f"{safe_stem}-{short_source}.context_clouds.jsonl"
        summary_path = self.source_local_resonance_dir / f"{safe_stem}-{short_source}.summary.json"

        write_jsonl(occurrence_path, index["occurrences"])
        write_jsonl(profile_path, index["positional_profiles"])
        write_jsonl(directional_path, index["directional_resonance"])
        write_jsonl(cloud_path, index["context_clouds"])

        summary = {
            **index["summary"],
            "saved_at": _utc_now(),
            "observed_map_name": path.name,
            "observed_map_path": str(path),
            "occurrence_path": str(occurrence_path),
            "positional_profiles_path": str(profile_path),
            "directional_resonance_path": str(directional_path),
            "context_clouds_path": str(cloud_path),
            "summary_path": str(summary_path),
        }
        self._write_json(summary_path, summary)

        return {
            "ok": True,
            "source_id": source_id,
            "source_name": summary.get("source_name") or "",
            "source_path": summary.get("source_path") or "",
            "observed_map_name": path.name,
            "occurrence_path": str(occurrence_path),
            "positional_profiles_path": str(profile_path),
            "directional_resonance_path": str(directional_path),
            "context_clouds_path": str(cloud_path),
            "summary_path": str(summary_path),
            "occurrence_records": int(summary["occurrence_records"]),
            "positional_profile_rows": int(summary["positional_profile_rows"]),
            "directional_resonance_rows": int(summary["directional_resonance_rows"]),
            "context_cloud_rows": int(summary["context_cloud_rows"]),
            "writes_allowed": summary["writes_allowed"],
            "authority": summary["authority"],
        }

