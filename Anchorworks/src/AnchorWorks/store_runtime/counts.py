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

    def _load_relation_counts_file(self, path: Path) -> tuple[Counter[tuple[str, str, str]], Counter[str], dict[str, Any]]:
        payload = self._read_json(path, {})
        counter: Counter[tuple[str, str, str]] = Counter()
        observed_counts: Counter[str] = Counter()
        metadata = {
            "first_saved_at": None,
            "updated_at": None,
            "ingest_events": 0,
            "window_radius": DEFAULT_WINDOW_RADIUS,
        }

        if isinstance(payload, dict):
            metadata["first_saved_at"] = payload.get("first_saved_at")
            metadata["updated_at"] = payload.get("updated_at")
            metadata["ingest_events"] = int(payload.get("ingest_events", 0) or 0)
            metadata["window_radius"] = int(payload.get("window_radius", DEFAULT_WINDOW_RADIUS) or DEFAULT_WINDOW_RADIUS)

            rows = payload.get("co_occurrence_counts") or []
            if isinstance(rows, list):
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    anchor = row.get("anchor")
                    offset = row.get("offset")
                    neighbor = row.get("neighbor")
                    observations = int(row.get("observations", 0) or 0)
                    if not isinstance(anchor, str) or not isinstance(offset, str) or not isinstance(neighbor, str):
                        continue
                    if observations <= 0:
                        continue
                    counter[(anchor, offset, neighbor)] += observations

            observed_rows = payload.get("anchor_observation_counts") or []
            if isinstance(observed_rows, list):
                for row in observed_rows:
                    if not isinstance(row, dict):
                        continue
                    anchor = row.get("anchor")
                    observations = int(row.get("observations", 0) or 0)
                    if not isinstance(anchor, str) or observations <= 0:
                        continue
                    observed_counts[anchor] += observations

        return counter, observed_counts, metadata

    def _load_combined_relation_counts(self) -> tuple[Counter[tuple[str, str, str]], Counter[str]]:
        base_counter, base_observed, _ = self._load_relation_counts_file(self.lifetime_counts_path)
        user_counter, user_observed, _ = self._load_relation_counts_file(self.user_counts_path)
        combined_counter = Counter(base_counter)
        combined_counter.update(user_counter)
        combined_observed = Counter(base_observed)
        combined_observed.update(user_observed)
        return combined_counter, combined_observed

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
            self.symbol_counts_binary_dir.mkdir(parents=True, exist_ok=True)
            seeded = False
            source_root = self.canonical_symbol_counts_binary_dir
            if source_root.exists():
                for source_path in source_root.rglob("*"):
                    if not source_path.is_file():
                        continue
                    relative = source_path.relative_to(source_root)
                    target_path = self.symbol_counts_binary_dir / relative
                    if target_path == self.user_counts_acknowledgement_path:
                        continue
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    if not target_path.exists():
                        shutil.copy2(source_path, target_path)
                        seeded = True
            if not self.user_counts_acknowledgement_path.exists():
                acknowledgement = {
                    "schema_version": "anchorworks_user_binary_counts_acknowledgement@1",
                    "acknowledged_at": _utc_now(),
                    "seed_source": str(self.canonical_symbol_counts_binary_dir),
                    "active_binary_counts_root": str(self.symbol_counts_binary_dir),
                    "canonical_seed_locked": True,
                    "future_writes": "user_side_binary_counts_only",
                    "seed_copy_mode": "copy_missing_files_only",
                }
                self._write_json(self.user_counts_acknowledgement_path, acknowledgement)
                seeded = True
            acknowledgement = self._read_json(self.user_counts_acknowledgement_path, {})
        return {
            "ok": True,
            "seeded": seeded,
            "canonical_seed_counts_root": str(self.canonical_symbol_counts_binary_dir),
            "active_binary_counts_root": str(self.symbol_counts_binary_dir),
            "acknowledgement_path": str(self.user_counts_acknowledgement_path),
            "acknowledgement": acknowledgement,
        }

    def counts_status(self) -> dict[str, Any]:
        seed = self.ensure_user_symbol_counts_seeded()
        cells_root = self.symbol_counts_binary_dir / "cells"
        cell_paths = list(cells_root.glob("*/*.cell")) if cells_root.exists() else []
        stream_path = self.symbol_streams_dir / "source_local_symbol_counts.awss"
        return {
            "runtime": "awsc_v1_1_binary_cells",
            "binary_counts_root": str(self.symbol_counts_binary_dir),
            "canonical_seed_counts_root": str(self.canonical_symbol_counts_binary_dir),
            "user_count_acknowledgement_path": seed["acknowledgement_path"],
            "symbol_stream_path": str(stream_path),
            "symbol_stream_exists": stream_path.exists(),
            "cell_count": len(cell_paths),
            "json_counts_removed": True,
            "ingest_events": 0,
            "unique_relations": 0,
            "total_relation_observations": 0,
            "anchor_count": len(cell_paths),
            "relation_rows": 0,
        }

    def retrieve_from_counts(self, anchor: str, limit: int = 25) -> dict[str, Any]:
        surface = self.normalize_anchor(anchor)
        counter, _ = self._load_combined_relation_counts()
        total_by_neighbor: Counter[str] = Counter()
        by_offset: dict[str, Counter[str]] = {}
        for (anchor, offset, neighbor), observations in counter.items():
            if anchor != surface or observations <= 0:
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

    def build_source_local_symbol_counts(self, observed_map_name: str) -> dict[str, Any]:
        symbolic_path = self._resolve_symbolic_map_name(observed_map_name)
        if symbolic_path.exists():
            return self._build_source_local_symbol_counts_from_awsm(symbolic_path)

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
        target = self.source_local_symbol_counts_dir / f"{stem}.symbol_counts.json"

        paragraphs = [row for row in payload.get("paragraphs") or [] if isinstance(row, dict)]
        anchors: list[str] = []
        for paragraph in paragraphs:
            anchors.extend(str(anchor) for anchor in (paragraph.get("resolved_anchors") or paragraph.get("anchors") or []) if str(anchor))

        symbol_by_anchor, symbol_authority = build_source_local_symbol_table(
            anchors,
            canonical_symbol_by_anchor=self._canonical_symbol_by_anchor(),
            symbol_authority_by_anchor=self._symbol_authority_by_anchor(),
            source_id=source_id,
        )
        symbol_authority = self._apply_user_symbol_authority(symbol_authority)
        relation_rows = build_symbol_relation_rows(
            paragraphs,
            symbol_by_anchor=symbol_by_anchor,
            window_radius=int(payload.get("window_radius", DEFAULT_WINDOW_RADIUS) or DEFAULT_WINDOW_RADIUS),
        )
        authority_by_symbol = {
            str(row.get("symbol") or ""): str(row.get("authority") or "")
            for row in symbol_authority
        }
        for row in relation_rows:
            row["lane"] = self._symbol_relation_lane(authority_by_symbol.get(str(row.get("neighbor_symbol_anchor") or "")))
            row["flags"] = 0
        source_local_symbols = sum(1 for row in symbol_authority if row.get("authority") == "source_local")
        canonical_symbols = sum(1 for row in symbol_authority if row.get("authority") == "canonical")
        user_symbols = sum(1 for row in symbol_authority if row.get("authority") == "user_lexicon")
        relation_fates = self._symbol_relation_fates_from_symbol_rows(relation_rows, authority_by_symbol)
        out = {
            "schema_version": "anchorworks_source_local_symbol_counts@1",
            "saved_at": _utc_now(),
            "source_id": source_id,
            "source_name": source_name,
            "source_path": source_path,
            "source_hash": source_hash,
            "source_format": "observed_json",
            "observed_map_name": path.name,
            "observed_map_path": str(path),
            "window_radius": int(payload.get("window_radius", DEFAULT_WINDOW_RADIUS) or DEFAULT_WINDOW_RADIUS),
            "symbol_authority": symbol_authority,
            "canonical_symbol_count": canonical_symbols,
            "user_lexicon_symbol_count": user_symbols,
            "source_local_symbol_count": source_local_symbols,
            "relation_fates": relation_fates,
            "symbol_relation_counts": relation_rows,
            "unique_symbol_relations": len(relation_rows),
            "total_symbol_relation_observations": int(sum(row["observations"] for row in relation_rows)),
            "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
        }
        self._write_json(target, out)
        return {
            "ok": True,
            "source_id": source_id,
            "source_name": source_name,
            "source_path": source_path,
            "source_format": "observed_json",
            "observed_map_name": path.name,
            "symbol_counts_name": target.name,
            "symbol_counts_path": str(target),
            "canonical_symbol_count": canonical_symbols,
            "user_lexicon_symbol_count": user_symbols,
            "source_local_symbol_count": source_local_symbols,
            "relation_fates": relation_fates,
            "unique_symbol_relations": len(relation_rows),
            "total_symbol_relation_observations": out["total_symbol_relation_observations"],
            "writes_allowed": out["writes_allowed"],
        }

    def _build_source_local_symbol_counts_from_awsm(self, symbolic_path: Path) -> dict[str, Any]:
        symbolic = read_symbolic_map_binary(symbolic_path)
        metadata = symbolic.metadata
        symbol_authority = [row for row in metadata.get("symbol_authority") or [] if isinstance(row, dict)]
        if not symbol_authority:
            raise ValueError(f"symbolic map lacks symbol authority table: {symbolic_path.name}")
        symbol_authority = self._apply_user_symbol_authority(symbol_authority)

        source_name = str(metadata.get("source_name") or "document")
        source_path = str(metadata.get("source_path") or "")
        source_hash = str(metadata.get("source_hash") or hashlib.sha256(source_path.encode("utf-8")).hexdigest())
        observed_map_name = str(metadata.get("observed_map_name") or (symbolic_path.stem + ".observed.json"))
        source_id = str(
            metadata.get("source_id")
            or hashlib.sha1((source_path + "\n" + source_hash + "\n" + observed_map_name).encode("utf-8")).hexdigest()
        )
        stem = self._flat_runtime_stem(source_name, source_id)
        target = self.source_local_symbol_counts_dir / f"{stem}.symbol_counts.json"

        authority_by_symbol = {
            str(row.get("symbol") or ""): str(row.get("authority") or "")
            for row in symbol_authority
        }
        relation_rows: list[dict[str, Any]] = []
        for row in symbolic.relations:
            root_display = f"0x{row.root_symbol_id:010X}"
            neighbor_display = f"0x{row.neighbor_symbol_id:010X}"
            observations = int(row.count)
            if observations <= 0:
                continue
            relation_rows.append({
                "symbol_id": int(row.root_symbol_id),
                "symbol_anchor": root_display,
                "offset": f"+{row.offset}" if row.offset > 0 else str(row.offset),
                "neighbor_symbol_id": int(row.neighbor_symbol_id),
                "neighbor_symbol_anchor": neighbor_display,
                "observations": observations,
                "lane": int(row.lane),
                "flags": int(row.flags),
            })

        canonical_symbols = sum(1 for row in symbol_authority if row.get("authority") == "canonical")
        user_symbols = sum(1 for row in symbol_authority if row.get("authority") == "user_lexicon")
        source_local_symbols = sum(1 for row in symbol_authority if row.get("authority") == "source_local")
        relation_fates = self._symbol_relation_fates_from_symbol_rows(relation_rows, authority_by_symbol)
        out = {
            "schema_version": "anchorworks_source_local_symbol_counts@1",
            "saved_at": _utc_now(),
            "source_id": source_id,
            "source_name": source_name,
            "source_path": source_path,
            "source_hash": source_hash,
            "source_format": "awsm",
            "observed_map_name": observed_map_name,
            "symbolic_map_name": symbolic_path.name,
            "symbolic_map_path": str(symbolic_path),
            "window_radius": int(metadata.get("window_radius", DEFAULT_WINDOW_RADIUS) or DEFAULT_WINDOW_RADIUS),
            "symbol_authority": symbol_authority,
            "canonical_symbol_count": canonical_symbols,
            "user_lexicon_symbol_count": user_symbols,
            "source_local_symbol_count": source_local_symbols,
            "relation_fates": relation_fates,
            "symbol_relation_counts": relation_rows,
            "unique_symbol_relations": len(relation_rows),
            "total_symbol_relation_observations": int(sum(row["observations"] for row in relation_rows)),
            "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
        }
        self._write_json(target, out)
        return {
            "ok": True,
            "source_id": source_id,
            "source_name": source_name,
            "source_path": source_path,
            "source_format": "awsm",
            "observed_map_name": observed_map_name,
            "symbolic_map_name": symbolic_path.name,
            "symbol_counts_name": target.name,
            "symbol_counts_path": str(target),
            "canonical_symbol_count": canonical_symbols,
            "user_lexicon_symbol_count": user_symbols,
            "source_local_symbol_count": source_local_symbols,
            "relation_fates": out["relation_fates"],
            "unique_symbol_relations": len(relation_rows),
            "total_symbol_relation_observations": out["total_symbol_relation_observations"],
            "writes_allowed": out["writes_allowed"],
        }

    def load_symbolic_map_bundle(self, name: str) -> dict[str, Any]:
        symbolic_path = self._resolve_symbolic_map_name(name)
        if not symbolic_path.exists():
            raise FileNotFoundError(name)
        bundle = read_symbolic_map_bundle(symbolic_path)
        return {
            "ok": True,
            "schema_version": "anchorworks_symbolic_map_bundle@1",
            "source_format": "awsm_bundle",
            "symbolic_map_name": symbolic_path.name,
            "symbolic_map_path": str(symbolic_path),
            "metadata": bundle.map.metadata,
            "relation_count": bundle.map.relation_count,
            "relations": [
                {
                    "root_symbol_id": row.root_symbol_id,
                    "neighbor_symbol_id": row.neighbor_symbol_id,
                    "offset": row.offset,
                    "lane": row.lane,
                    "flags": row.flags,
                    "count": row.count,
                }
                for row in bundle.map.relations
            ],
            "locator_count": len(bundle.locators),
            "locators": bundle.locators,
            "null_count": len(bundle.nulls),
            "nulls": bundle.nulls,
            "visual_count": len(bundle.visuals),
            "visuals": bundle.visuals,
            "paths": bundle.paths,
            "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
        }

    def build_binary_symbol_counts_from_source_local(
        self,
        *,
        limit: int | None = None,
        generation: int = 0,
        artifact_names: list[str] | None = None,
    ) -> dict[str, Any]:
        if artifact_names is None:
            artifact_paths = sorted(self.source_local_symbol_counts_dir.glob("*.symbol_counts.json"))
        else:
            artifact_paths = []
            root = self.source_local_symbol_counts_dir.resolve()
            for name in artifact_names:
                target = (self.source_local_symbol_counts_dir / Path(name).name).resolve()
                if target.parent != root:
                    raise FileNotFoundError(name)
                artifact_paths.append(target)
            artifact_paths = sorted(artifact_paths, key=lambda item: item.name.lower())
        if limit is not None:
            artifact_paths = artifact_paths[: max(0, int(limit))]
        if not artifact_paths:
            raise FileNotFoundError("no source-local symbol count artifacts found")
        missing = [str(path) for path in artifact_paths if not path.exists()]
        if missing:
            raise FileNotFoundError(f"missing source-local symbol count artifacts: {missing[:3]}")
        seed = self.ensure_user_symbol_counts_seeded()
        stream_path = self.symbol_streams_dir / "source_local_symbol_counts.awss"
        stream = write_awss_from_symbol_count_artifacts(artifact_paths, stream_path)
        merge = merge_symbol_stream(
            stream_path,
            self.symbol_counts_binary_dir,
            generation=int(generation),
        )
        verify = verify_binary_counts(self.symbol_counts_binary_dir)
        return {
            "ok": bool(merge.get("ok")) and bool(verify.get("ok")),
            "schema_version": "anchorworks_binary_symbol_counts_build@1",
            "artifact_count": len(artifact_paths),
            "stream_path": str(stream_path),
            "stream_record_count": int(stream.get("record_count", 0) or 0),
            "stream_observation_count": int(stream.get("observation_count", 0) or 0),
            "stream_size_bytes": stream_path.stat().st_size if stream_path.exists() else 0,
            "binary_counts_root": str(self.symbol_counts_binary_dir),
            "canonical_seed_counts_root": str(self.canonical_symbol_counts_binary_dir),
            "user_count_acknowledgement_path": seed["acknowledgement_path"],
            "verify": verify,
            "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
        }

    def build_symbolic_intake_batch(
        self,
        source_paths: list[str | Path],
        *,
        max_workers: int | None = None,
        generation: int = 0,
        null_anchors: set[str] | None = None,
    ) -> dict[str, Any]:
        normalized_paths = [Path(path).expanduser().resolve() for path in source_paths]
        if not normalized_paths:
            raise ValueError("at least one source path is required")
        for path in normalized_paths:
            if not path.exists():
                raise FileNotFoundError(path)
            if not path.is_file():
                raise IsADirectoryError(path)

        groups: dict[str, list[Path]] = {}
        for path in normalized_paths:
            groups.setdefault(str(path.parent), []).append(path)

        worker_count = max(1, min(int(max_workers or (os.cpu_count() or 1)), len(normalized_paths)))
        worker_args = [
            (str(self.root), str(path), "binary_source_local", sorted(null_anchors or set()))
            for group_name in sorted(groups)
            for path in sorted(groups[group_name], key=lambda item: item.name.lower())
        ]

        map_results: list[dict[str, Any]] = []
        if worker_count == 1:
            map_results = [_build_observed_map_worker(args) for args in worker_args]
        else:
            with ProcessPoolExecutor(max_workers=worker_count) as executor:
                future_by_path = {executor.submit(_build_observed_map_worker, args): args[1] for args in worker_args}
                for future in as_completed(future_by_path):
                    map_results.append(future.result())
            map_results.sort(key=lambda row: str(row.get("source_path") or "").lower())

        symbol_artifacts = [
            self.build_source_local_symbol_counts(str(row["saved_map_name"]))
            for row in map_results
        ]
        binary = self.build_binary_symbol_counts_from_source_local(
            generation=generation,
            artifact_names=[str(row["symbol_counts_name"]) for row in symbol_artifacts],
        )
        return {
            "ok": bool(binary.get("ok")),
            "schema_version": "anchorworks_symbolic_intake_batch@1",
            "source_count": len(normalized_paths),
            "group_count": len(groups),
            "groups": [
                {"group": group, "source_count": len(paths)}
                for group, paths in sorted(groups.items())
            ],
            "max_workers_used": worker_count,
            "map_root": str(self.observed_maps_dir),
            "map_count": len(map_results),
            "maps": map_results,
            "symbol_artifact_count": len(symbol_artifacts),
            "symbol_artifacts": symbol_artifacts,
            "binary": binary,
            "writes_allowed": {"maps": True, "counts": False, "lifetime": False, "lexicon": False},
        }

    def build_symbolic_intake_batch_chunked(
        self,
        source_paths: list[str | Path],
        *,
        max_workers: int | None = None,
        generation: int = 0,
        null_anchors: set[str] | None = None,
        run_id: str | None = None,
        chunk_file_limit: int = 250,
        soft_warning_gb: float = 32.0,
        emergency_flush_gb: float = 36.0,
        abort_gb: float = 39.0,
        write_chunk_binaries: bool = True,
    ) -> dict[str, Any]:
        normalized_paths = [Path(path).expanduser().resolve() for path in source_paths]
        if not normalized_paths:
            raise ValueError("at least one source path is required")
        for path in normalized_paths:
            if not path.exists():
                raise FileNotFoundError(path)
            if not path.is_file():
                raise IsADirectoryError(path)

        safe_run_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(run_id or f"chunked_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}")).strip("._") or "chunked"
        run_root = self.ingest_staging_dir / "chunked_symbolic_intake" / safe_run_id
        chunks_root = run_root / "chunks"
        chunk_binary_root = self.state_dir / "symbol_counts_binary_chunks" / safe_run_id
        run_root.mkdir(parents=True, exist_ok=True)
        chunks_root.mkdir(parents=True, exist_ok=True)
        if write_chunk_binaries:
            chunk_binary_root.mkdir(parents=True, exist_ok=True)

        file_limit = max(1, int(chunk_file_limit))
        worker_count = max(1, int(max_workers or (os.cpu_count() or 1)))
        chunks = [
            normalized_paths[index : index + file_limit]
            for index in range(0, len(normalized_paths), file_limit)
        ]
        manifest_path = run_root / "manifest.json"
        stop_path = run_root / "STOP"
        started = time.perf_counter()
        chunk_rows: list[dict[str, Any]] = []
        failed_files: list[dict[str, Any]] = []
        stopped_reason = ""
        completed_chunk_ids: set[str] = set()
        if manifest_path.exists():
            try:
                existing = json.loads(manifest_path.read_text(encoding="utf-8"))
                for row in existing.get("chunks") or []:
                    if not isinstance(row, dict):
                        continue
                    chunk_id = str(row.get("chunk_id") or "")
                    if chunk_id and int(row.get("files_failed", 0) or 0) == 0:
                        completed_chunk_ids.add(chunk_id)
                        chunk_rows.append(row)
                for error in existing.get("failed_files") or []:
                    if isinstance(error, dict):
                        failed_files.append(error)
            except Exception:
                completed_chunk_ids = set()
                chunk_rows = []
                failed_files = []

        for chunk_index, chunk_paths in enumerate(chunks, start=1):
            chunk_id = f"chunk_{chunk_index:04d}"
            if stop_path.exists():
                stopped_reason = "stop_requested_before_chunk"
                break
            if chunk_id in completed_chunk_ids:
                continue
            chunk_started = time.perf_counter()
            rss_start = _current_process_rss_bytes()
            chunk_manifest_path = chunks_root / f"{chunk_id}.json"
            chunk_workers = max(1, min(worker_count, len(chunk_paths)))
            worker_args = [
                (str(self.root), str(path), "binary_source_local", sorted(null_anchors or set()))
                for path in chunk_paths
            ]

            map_results: list[dict[str, Any]] = []
            map_errors: list[dict[str, Any]] = []
            if chunk_workers == 1:
                for args in worker_args:
                    try:
                        map_results.append(_build_observed_map_worker(args))
                    except Exception as exc:
                        error = {"source_path": args[1], "stage": "map", "error": str(exc)}
                        map_errors.append(error)
                        failed_files.append(error)
            else:
                with ProcessPoolExecutor(max_workers=chunk_workers) as executor:
                    future_by_path = {executor.submit(_build_observed_map_worker, args): args[1] for args in worker_args}
                    for future in as_completed(future_by_path):
                        source_path = future_by_path[future]
                        try:
                            map_results.append(future.result())
                        except Exception as exc:
                            error = {"source_path": source_path, "stage": "map", "error": str(exc)}
                            map_errors.append(error)
                            failed_files.append(error)
                map_results.sort(key=lambda row: str(row.get("source_path") or "").lower())

            symbol_artifacts: list[dict[str, Any]] = []
            symbol_errors: list[dict[str, Any]] = []
            for row in map_results:
                try:
                    symbol_artifacts.append(self.build_source_local_symbol_counts(str(row["saved_map_name"])))
                except Exception as exc:
                    error = {
                        "source_path": str(row.get("source_path") or ""),
                        "observed_map_name": str(row.get("saved_map_name") or ""),
                        "stage": "source_local_symbol_counts",
                        "error": str(exc),
                    }
                    symbol_errors.append(error)
                    failed_files.append(error)

            binary: dict[str, Any] | None = None
            binary_error = ""
            if write_chunk_binaries and symbol_artifacts:
                try:
                    artifact_paths = [self.source_local_symbol_counts_dir / str(row["symbol_counts_name"]) for row in symbol_artifacts]
                    stream_path = run_root / "symbol_streams" / f"{chunk_id}.awss"
                    stream = write_awss_from_symbol_count_artifacts(artifact_paths, stream_path)
                    output_root = chunk_binary_root / chunk_id
                    merge = merge_symbol_stream(stream_path, output_root, generation=int(generation))
                    verify = verify_binary_counts(output_root)
                    binary = {
                        "ok": bool(merge.get("ok")) and bool(verify.get("ok")),
                        "stream_path": str(stream_path),
                        "stream_record_count": int(stream.get("record_count", 0) or 0),
                        "stream_observation_count": int(stream.get("observation_count", 0) or 0),
                        "stream_size_bytes": stream_path.stat().st_size if stream_path.exists() else 0,
                        "binary_counts_root": str(output_root),
                        "verify": verify,
                    }
                except Exception as exc:
                    binary_error = str(exc)

            del worker_args
            gc.collect()
            rss_end = _current_process_rss_bytes()
            peak_rss = max(rss_start, rss_end)
            elapsed = time.perf_counter() - chunk_started
            chunk_row = {
                "chunk_id": chunk_id,
                "source_count": len(chunk_paths),
                "files_ok": len(symbol_artifacts),
                "files_failed": len(map_errors) + len(symbol_errors),
                "source_paths": [str(path) for path in chunk_paths],
                "map_count": len(map_results),
                "maps": [
                    {
                        "source_path": str(row.get("source_path") or ""),
                        "saved_map_name": str(row.get("saved_map_name") or ""),
                        "symbolic_map_name": str(row.get("symbolic_map_name") or ""),
                    }
                    for row in map_results
                ],
                "symbol_artifact_count": len(symbol_artifacts),
                "symbol_artifacts": [
                    {
                        "source_path": str(row.get("source_path") or ""),
                        "symbol_counts_name": str(row.get("symbol_counts_name") or ""),
                        "unique_symbol_relations": int(row.get("unique_symbol_relations", 0) or 0),
                        "total_symbol_relation_observations": int(row.get("total_symbol_relation_observations", 0) or 0),
                    }
                    for row in symbol_artifacts
                ],
                "binary": binary,
                "binary_error": binary_error,
                "errors": map_errors + symbol_errors,
                "elapsed_seconds": round(elapsed, 6),
                "rss_start_bytes": rss_start,
                "rss_end_bytes": rss_end,
                "peak_rss_bytes": peak_rss,
                "memory_status": _memory_status(peak_rss, soft_warning_gb, emergency_flush_gb, abort_gb),
            }
            chunk_manifest_path.write_text(json.dumps(chunk_row, indent=2, ensure_ascii=False), encoding="utf-8")
            chunk_rows.append(chunk_row)

            manifest = {
                "schema_version": "anchorworks_chunked_symbolic_intake_run@1",
                "run_id": safe_run_id,
                "status": "running",
                "source_count": len(normalized_paths),
                "chunk_count": len(chunks),
                "completed_chunks": len(chunk_rows),
                "chunk_file_limit": file_limit,
                "memory_budget": {
                    "soft_warning_gb": soft_warning_gb,
                    "emergency_flush_gb": emergency_flush_gb,
                    "abort_gb": abort_gb,
                },
                "chunk_binary_root": str(chunk_binary_root) if write_chunk_binaries else "",
                "chunks": chunk_rows,
                "failed_files": failed_files,
                "writes_allowed": {"maps": True, "counts": False, "lifetime": False, "lexicon": False},
            }
            manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
            if peak_rss >= int(float(abort_gb) * 1024 * 1024 * 1024):
                stopped_reason = "abort_gb_reached_after_safe_chunk_flush"
                break
            if stop_path.exists():
                stopped_reason = "stop_requested_after_safe_chunk_flush"
                break

        total_elapsed = time.perf_counter() - started
        ok = not stopped_reason and not failed_files and all((row.get("binary") or {}).get("ok", True) for row in chunk_rows)
        final = {
            "schema_version": "anchorworks_chunked_symbolic_intake_run@1",
            "run_id": safe_run_id,
            "status": "stopped" if stopped_reason else "completed",
            "ok": bool(ok),
            "stopped_reason": stopped_reason,
            "source_count": len(normalized_paths),
            "chunk_count": len(chunks),
            "completed_chunks": len(chunk_rows),
            "files_ok": sum(int(row.get("files_ok", 0) or 0) for row in chunk_rows),
            "files_failed": len(failed_files),
            "manifest_path": str(manifest_path),
            "run_root": str(run_root),
            "map_root": str(self.observed_maps_dir),
            "source_local_symbol_counts_root": str(self.source_local_symbol_counts_dir),
            "chunk_binary_root": str(chunk_binary_root) if write_chunk_binaries else "",
            "elapsed_seconds": round(total_elapsed, 6),
            "chunks": chunk_rows,
            "failed_files": failed_files,
            "writes_allowed": {"maps": True, "counts": False, "lifetime": False, "lexicon": False},
        }
        manifest_path.write_text(json.dumps(final, indent=2, ensure_ascii=False), encoding="utf-8")
        return final

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
