from __future__ import annotations

from ..store_support import *


class IntakeMixin:
    def _known_anchor_spell_buckets(self) -> dict[tuple[str, tuple[bool, int], int], list[str]]:
        if self._known_anchor_spell_index is not None:
            return self._known_anchor_spell_index

        buckets: dict[tuple[str, tuple[bool, int], int], list[str]] = {}
        for anchor in self._all_known_anchors():
            if not anchor or not any(char.isalpha() for char in anchor):
                continue
            key = (
                self._letter_for_word(anchor).lower(),
                self._anchor_case_signature(anchor),
                len(anchor),
            )
            buckets.setdefault(key, []).append(anchor)

        self._known_anchor_spell_index = buckets
        return buckets

    def _extract_document_anchor_inventory(self, text: str) -> dict[str, Any]:
        paragraphs = split_paragraphs(text)
        ordered_anchors: list[str] = []
        paragraph_rows: list[dict[str, Any]] = []
        observed_counts: Counter[str] = Counter()

        for paragraph_id, paragraph in enumerate(paragraphs):
            anchor_rows = extract_anchor_rows(paragraph)
            anchors = [row["anchor"] for row in anchor_rows]
            composed_streams = [compose_anchor_stream(anchor) for anchor in anchors]
            ordered_anchors.extend(anchors)
            observed_counts.update(anchors)
            paragraph_rows.append({
                "paragraph_id": paragraph_id,
                "anchor_count": len(anchors),
                "anchors": anchors,
                "composed_anchor_streams": composed_streams,
                "composed_anchor_stream": [part for stream in composed_streams for part in stream],
                "text": paragraph,
            })

        return {
            "paragraph_count": len(paragraph_rows),
            "paragraphs": paragraph_rows,
            "ordered_anchors": ordered_anchors,
            "observed_counts": observed_counts,
        }

    def preview_document_intake(
        self,
        *,
        source_name: str,
        content: str,
        file_size: int = 0,
        file_type: str = "",
        source_path: str = "",
    ) -> dict[str, Any]:
        if _is_visual_preview_content(content):
            return {
                "ok": True,
                "source_name": source_name or "document",
                "source_path": source_path or "",
                "file_type": file_type or "",
                "file_size": int(file_size or len(content.encode("utf-8"))),
                "real_lexicon_path": str(self.root),
                "paragraph_count": 0,
                "total_anchor_observations": 0,
                "unique_anchor_count": 0,
                "known_anchor_count": 0,
                "missing_anchor_count": 0,
                "known_anchor_observations": 0,
                "missing_anchor_observations": 0,
                "unique_anchors": [],
                "missing_anchors": [],
                "visual_preview_only": True,
                "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
                "reason": "visual_intake_preview_only",
            }

        inventory = self._extract_document_anchor_inventory(content)
        observed_counts: Counter[str] = inventory["observed_counts"]
        known_anchors = set(self._all_known_anchors())
        missing_counts = Counter({
            anchor: count for anchor, count in observed_counts.items() if anchor not in known_anchors
        })
        known_counts = Counter({
            anchor: count for anchor, count in observed_counts.items() if anchor in known_anchors
        })
        unique_rows = [
            {
                "anchor": anchor,
                "observations": int(count),
                "known": anchor in known_anchors,
            }
            for anchor, count in sorted(observed_counts.items(), key=lambda item: (-item[1], item[0]))
        ]

        return {
            "ok": True,
            "source_name": source_name or "document",
            "source_path": source_path or "",
            "file_type": file_type or "",
            "file_size": int(file_size or len(content.encode("utf-8"))),
            "real_lexicon_path": str(self.root),
            "paragraph_count": int(inventory["paragraph_count"]),
            "total_anchor_observations": int(sum(observed_counts.values())),
            "unique_anchor_count": len(observed_counts),
            "known_anchor_count": len(known_counts),
            "missing_anchor_count": len(missing_counts),
            "known_anchor_observations": int(sum(known_counts.values())),
            "missing_anchor_observations": int(sum(missing_counts.values())),
            "unique_anchors": unique_rows,
            "missing_anchors": self._anchor_rows(missing_counts),
        }

    def edit_intake_content(
        self,
        *,
        source_name: str,
        content: str,
        edits: list[dict[str, Any]],
        file_type: str = "edited-intake-text",
        source_path: str = "",
    ) -> dict[str, Any]:
        updated = str(content or "")
        applied: list[dict[str, Any]] = []
        for edit in edits or []:
            original = self.normalize_anchor(str(edit.get("original_anchor") or ""))
            replacement = str(edit.get("replacement_anchor") or "")
            action = str(edit.get("action") or "replace").strip().lower()
            if not original or action not in {"replace", "delete"}:
                continue
            rows = [
                row for row in extract_anchor_rows(updated)
                if self.normalize_anchor(str(row.get("anchor") or "")) == original
            ]
            if not rows:
                continue
            next_text = updated
            for row in sorted(rows, key=lambda item: int(item.get("start", 0) or 0), reverse=True):
                start = int(row.get("start", 0) or 0)
                end = int(row.get("end", start) or start)
                next_text = next_text[:start] + ("" if action == "delete" else replacement) + next_text[end:]
            updated = next_text
            applied.append({
                "original_anchor": original,
                "replacement_anchor": replacement,
                "action": action,
                "occurrences": len(rows),
            })
        preview = self.preview_document_intake(
            source_name=source_name,
            content=updated,
            file_size=len(updated.encode("utf-8")),
            file_type=file_type,
            source_path=source_path,
        )
        return {
            "ok": True,
            "source_name": source_name,
            "content": updated,
            "edits": applied,
            "edit_count": len(applied),
            "preview": preview,
        }

    def approve_intake_anchors(
        self,
        anchors: list[str],
        frequencies: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        frequency_map = {
            self.normalize_anchor(anchor): int(count or 0)
            for anchor, count in (frequencies or {}).items()
            if self.normalize_anchor(anchor)
        }
        approved: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []
        seen: set[str] = set()
        slots_available = 0
        lexicon_files_written = 0
        spare_pool_writes = 0
        index_reloads = 0

        with self._lock:
            known_anchors = set(self._all_known_anchors())
            requested: list[str] = []

            for raw_anchor in anchors:
                anchor = self.normalize_anchor(raw_anchor)
                if not anchor or anchor in seen:
                    continue
                seen.add(anchor)

                if anchor in known_anchors:
                    skipped.append({"anchor": anchor, "reason": "already_in_lexicon"})
                    continue

                requested.append(anchor)

            user_entries = self._read_entries(self.user_lexicon_path)
            changed_user_lexicon = False
            timestamp = _utc_now()
            genome_pool = SymbolGenomePool(self.symbol_genome_pool_dir)

            for anchor in requested:
                try:
                    allocation = genome_pool.allocate(
                        anchor,
                        authority="user_lexicon",
                        category="specialized",
                        priority=2,
                    )
                except ValueError as exc:
                    failed.append({"anchor": anchor, "reason": str(exc)})
                    continue

                new_entry = self._build_user_lexicon_entry(
                    anchor,
                    allocation,
                    frequency=int(frequency_map.get(anchor, 0) or 0),
                    timestamp=timestamp,
                )
                user_entries.append(new_entry)
                changed_user_lexicon = True
                known_anchors.add(anchor)
                approved.append({
                    "ok": True,
                    "word": anchor,
                    "hex": new_entry["hex"],
                    "symbol": new_entry["symbol"],
                    "mapped_at": timestamp,
                    "frequency": int(frequency_map.get(anchor, 0) or 0),
                    "pack": "user",
                    "authority": "user_lexicon",
                })

            if approved:
                if changed_user_lexicon:
                    user_entries.sort(key=lambda item: (str(item.get("word", "")).casefold(), str(item.get("word", ""))))
                    self._write_entries(self.user_lexicon_path, user_entries)
                    lexicon_files_written += 1
                self._invalidate_known_anchor_index()
                self._canonical_symbol_index = None
                self._canonical_anchor_index = None
                self._all_known_anchors()
                index_reloads = 1
            slots_available = genome_pool.status()["remaining"]

        return {
            "ok": not failed,
            "approved_count": len(approved),
            "skipped_count": len(skipped),
            "failed_count": len(failed),
            "slots_allocated": len(approved),
            "slots_available": slots_available,
            "lexicon_files_written": lexicon_files_written,
            "user_lexicon_files_written": lexicon_files_written,
            "spare_pool_writes": spare_pool_writes,
            "index_reloads": index_reloads,
            "approved": approved,
            "skipped": skipped,
            "failed": failed,
            "symbol_genome_pool": self.symbol_genome_status(),
            "real_lexicon_path": str(self.root),
        }

    def build_intake_mapping(
        self,
        *,
        source_name: str,
        content: str,
        count_target: str = "binary_source_local",
        intake_edits: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        del count_target
        return self.map_intake_content_to_user_counts_native(
            source_name=source_name,
            content=content,
            intake_edits=intake_edits,
        )

    def _anchor_case_signature(self, anchor: str) -> tuple[bool, int]:
        return (anchor[:1].isupper(), sum(1 for char in anchor if char.isupper()))

    def _bounded_edit_distance(self, left: str, right: str, max_distance: int = 1) -> int:
        if abs(len(left) - len(right)) > max_distance:
            return max_distance + 1

        previous = list(range(len(right) + 1))
        for index, left_char in enumerate(left, start=1):
            current = [index]
            row_min = current[0]
            for right_index, right_char in enumerate(right, start=1):
                substitution = previous[right_index - 1] + (0 if left_char == right_char else 1)
                insertion = current[right_index - 1] + 1
                deletion = previous[right_index] + 1
                cost = min(substitution, insertion, deletion)
                current.append(cost)
                row_min = min(row_min, cost)
            if row_min > max_distance:
                return max_distance + 1
            previous = current
        return previous[-1]

    def _suggest_existing_anchor(self, anchor: str, known_anchors: set[str]) -> str | None:
        if not anchor:
            return None
        if not any(char.isalpha() for char in anchor):
            return None

        case_signature = self._anchor_case_signature(anchor)
        first_alpha = self._letter_for_word(anchor).lower()
        spell_buckets = self._known_anchor_spell_buckets()
        candidates: list[tuple[int, int, str]] = []

        for length in range(max(1, len(anchor) - 1), len(anchor) + 2):
            for known_anchor in spell_buckets.get((first_alpha, case_signature, length), []):
                if known_anchor == anchor:
                    continue
                distance = self._bounded_edit_distance(anchor, known_anchor, max_distance=1)
                if distance <= 1:
                    candidates.append((distance, abs(len(anchor) - len(known_anchor)), known_anchor))

        if not candidates:
            return None

        candidates.sort(key=lambda item: (item[0], item[1], item[2]))
        best = candidates[0]
        if len(candidates) > 1 and candidates[1][:2] == best[:2]:
            return None
        return best[2]

    def _should_attempt_spell_suggestion(self, anchor: str, missing_unique_count: int) -> bool:
        if missing_unique_count > _SPELL_SUGGESTION_MISSING_LIMIT:
            return False
        if not _SPELL_SUGGESTION_WORD_RE.fullmatch(anchor or ""):
            return False
        if len(anchor) > 1 and anchor.isupper():
            return False
        return True

    def _should_decompose_unknown_string(self, anchor: str) -> bool:
        value = self.normalize_anchor(anchor)
        if len(value) < 2:
            return False
        return any(char.isalnum() for char in value)

    def _precompute_spell_suggestions(
        self,
        missing_counts: Counter[str],
        known_anchors: set[str],
    ) -> dict[str, str]:
        suggestions: dict[str, str] = {}
        missing_unique_count = len(missing_counts)
        for anchor in missing_counts:
            if not self._should_attempt_spell_suggestion(anchor, missing_unique_count):
                continue
            suggestion = self._suggest_existing_anchor(anchor, known_anchors)
            if suggestion is not None:
                suggestions[anchor] = suggestion
        return suggestions

    def _resolve_missing_anchors(
        self,
        missing_counts: Counter[str],
        known_anchors: set[str],
        suggestions: dict[str, str] | None = None,
    ) -> tuple[dict[str, str], list[dict[str, Any]], list[dict[str, Any]], Counter[str]]:
        resolved: dict[str, str] = {}
        corrections: list[dict[str, Any]] = []
        additions: list[dict[str, Any]] = []
        unresolved: Counter[str] = Counter()
        suggestion_map = suggestions or {}

        for anchor, observations in missing_counts.items():
            suggestion = suggestion_map.get(anchor)
            if suggestion is not None:
                resolved[anchor] = suggestion
                corrections.append({
                    "anchor": anchor,
                    "resolved_to": suggestion,
                    "observations": int(observations),
                    "action": "spell_corrected_to_existing",
                })
                continue

            try:
                additions.append(self._assign_surface_anchor(anchor, frequency=int(observations)))
                resolved[anchor] = anchor
                known_anchors.add(anchor)
            except Exception:
                unresolved[anchor] = int(observations)

        return resolved, corrections, additions, unresolved

    def _build_misspelled_review_rows(
        self,
        missing_counts: Counter[str],
        known_anchors: set[str],
        suggestions: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        suggestion_map = suggestions or {}
        for anchor, observations in sorted(missing_counts.items(), key=lambda item: (-item[1], item[0])):
            suggestion = suggestion_map.get(anchor)
            rows.append({
                "anchor": anchor,
                "observations": int(observations),
                "suggested_existing": suggestion,
                "review_kind": "possible_misspelling" if suggestion else "missing_anchor",
                "ingest_action": "pending_review",
                "resolved_to": None,
            })
        return rows

    def _write_misspelled_review(
        self,
        source_path: Path,
        inventory: dict[str, Any],
        review_rows: list[dict[str, Any]],
    ) -> Path:
        payload = {
            "saved_at": _utc_now(),
            "source_path": str(source_path),
            "source_name": source_path.name,
            "paragraph_count": int(inventory.get("paragraph_count", 0) or 0),
            "total_anchor_observations": int(sum((inventory.get("observed_counts") or Counter()).values())),
            "unique_anchor_count": len(inventory.get("observed_counts") or {}),
            "review_count": len(review_rows),
            "rows": review_rows,
        }
        review_path = self._misspelled_review_path(source_path)
        self._write_json(review_path, payload)
        return review_path

    def _read_source_text(self, source_path: Path) -> str:
        return prepare_file(source_path).prepared_text

    def prepare_intake_document(
        self,
        raw: bytes,
        *,
        source_name: str,
        file_type: str = "",
        source_path: str = "",
    ) -> dict[str, Any]:
        prepared = prepare_bytes(
            raw,
            source_name=source_name,
            source_path=source_path,
            file_type=file_type,
        )
        payload = prepared.to_dict()
        visual_intake = self._persist_visual_intake_packet(payload)
        if visual_intake:
            payload.setdefault("metadata", {})["visual_intake"] = visual_intake
        return payload

    def _observed_map_path(self, source_path: Path) -> Path:
        digest = hashlib.sha1(str(source_path).encode("utf-8")).hexdigest()[:12]
        safe_name = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in source_path.stem).strip("_")
        if not safe_name:
            safe_name = "observed"
        return self.observed_maps_dir / f"{safe_name}-{digest}.observed.json"

    def _symbolic_map_path(self, source_path: Path) -> Path:
        digest = hashlib.sha1(str(source_path).encode("utf-8")).hexdigest()[:12]
        safe_name = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in source_path.stem).strip("_")
        if not safe_name:
            safe_name = "symbolic"
        return self.symbolic_maps_dir / f"{safe_name}-{digest}.awsm"

    def _symbolic_locator_path(self, source_path: Path) -> Path:
        digest = hashlib.sha1(str(source_path).encode("utf-8")).hexdigest()[:12]
        safe_name = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in source_path.stem).strip("_")
        if not safe_name:
            safe_name = "symbolic"
        return self.symbolic_maps_dir / f"{safe_name}-{digest}.locators.awsl"

    def _symbolic_null_path(self, source_path: Path) -> Path:
        digest = hashlib.sha1(str(source_path).encode("utf-8")).hexdigest()[:12]
        safe_name = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in source_path.stem).strip("_")
        if not safe_name:
            safe_name = "symbolic"
        return self.symbolic_maps_dir / f"{safe_name}-{digest}.nulls.awsn"

    def _symbolic_visual_path(self, source_path: Path) -> Path:
        digest = hashlib.sha1(str(source_path).encode("utf-8")).hexdigest()[:12]
        safe_name = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in source_path.stem).strip("_")
        if not safe_name:
            safe_name = "symbolic"
        return self.symbolic_maps_dir / f"{safe_name}-{digest}.visuals.awsv"

    def _misspelled_review_path(self, source_path: Path) -> Path:
        digest = hashlib.sha1(str(source_path).encode("utf-8")).hexdigest()[:12]
        safe_name = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in source_path.stem).strip("_")
        if not safe_name:
            safe_name = "review"
        return self.misspelled_reviews_dir / f"{safe_name}-{digest}.misspellings.json"

    def _intake_upload_path(self, *, source_name: str, content: str) -> Path:
        original = Path(source_name or "document.txt").name
        suffix = ".prepared.txt"
        safe_stem = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in Path(original).stem).strip("_")
        if not safe_stem:
            safe_stem = "document"
        digest = hashlib.sha1((original + "\n" + content).encode("utf-8")).hexdigest()[:12]
        return self.intake_uploads_dir / f"{safe_stem}-{digest}{suffix}"

    def _resolve_observed_map_name(self, name: str) -> Path:
        filename = Path(name).name
        target = (self.observed_maps_dir / filename).resolve()
        if target.parent != self.observed_maps_dir.resolve():
            raise FileNotFoundError(name)
        return target

    def _resolve_symbolic_map_name(self, name: str) -> Path:
        filename = Path(name).name
        if filename.endswith(".observed.json"):
            filename = filename[: -len(".observed.json")] + ".awsm"
        target = (self.symbolic_maps_dir / filename).resolve()
        if target.parent != self.symbolic_maps_dir.resolve():
            raise FileNotFoundError(name)
        return target

    def _flat_runtime_stem(self, source_name: str, source_id: str) -> str:
        safe_name = "".join(
            char if char.isalnum() or char in {"-", "_"} else "_"
            for char in Path(source_name or "document").stem
        ).strip("_")
        if not safe_name:
            safe_name = "document"
        return f"{safe_name}-{source_id[:12]}"

    def _resolve_misspelled_review_name(self, name: str) -> Path:
        filename = Path(name).name
        target = (self.misspelled_reviews_dir / filename).resolve()
        if target.parent != self.misspelled_reviews_dir.resolve():
            raise FileNotFoundError(name)
        return target

    def _anchor_rows(self, counts: Counter[str]) -> list[dict[str, Any]]:
        return [
            {"anchor": anchor, "observations": count}
            for anchor, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        ]

    def _temp_symbol_for_anchor(self, source_id: str, anchor: str, salt: int = 0) -> str:
        seed = f"{TEMP_SYMBOL_VERSION}::{source_id}::{anchor}::{salt}"
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest().upper()
        return f"{TEMP_SYMBOL_PREFIX}{digest[:TEMP_SYMBOL_HEX_LENGTH]}"

    def _temp_lexicon_path(self, source_path: Path) -> Path:
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", source_path.stem).strip("._") or "source"
        digest = hashlib.sha256(str(source_path).encode("utf-8")).hexdigest()[:12]
        return self.temp_lexicons_dir / f"{safe_name}-{digest}.temp_lexicon.json"

    def _build_temp_symbol_entries(self, source_path: Path, missing_counts: Counter[str]) -> tuple[dict[str, str], list[dict[str, Any]]]:
        source_id = hashlib.sha256(str(source_path).encode("utf-8")).hexdigest()
        used: set[str] = set()
        symbol_map: dict[str, str] = {}
        entries: list[dict[str, Any]] = []
        for anchor, observations in sorted(missing_counts.items(), key=lambda item: item[0]):
            salt = 0
            symbol = self._temp_symbol_for_anchor(source_id, anchor, salt)
            while symbol in used:
                salt += 1
                symbol = self._temp_symbol_for_anchor(source_id, anchor, salt)
            used.add(symbol)
            symbol_map[anchor] = symbol
            entries.append({
                "word": anchor,
                "display": anchor,
                "symbol": symbol,
                "hex": symbol,
                "status": "TEMP_UNKNOWN",
                "pack": "temp",
                "authority": "source_local_coordinate",
                "scope": "source_local",
                "source_id": source_id,
                "source_name": source_path.name,
                "observations": int(observations),
                "temp_symbol_version": TEMP_SYMBOL_VERSION,
                "lifetime_eligible": False,
                "speak_eligible": False,
                "promotion_required": True,
                "created_at": _utc_now(),
            })
        return symbol_map, entries

    def _null_occurrence_index(self, occurrences: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for occurrence in occurrences:
            if occurrence.get("anchor") != NULL_ANCHOR:
                continue
            block_id = int(occurrence.get("block_id", occurrence.get("paragraph_id", 0)) or 0)
            line_start = int(occurrence.get("line_start", 0) or 0)
            position = int(occurrence.get("position", 0) or 0)
            rows.append({
                "schema_version": "anchorworks_null_index@1",
                "block_id": block_id,
                "line_start": line_start,
                "line_end": int(occurrence.get("line_end", line_start) or line_start),
                "anchor_position": position,
                "anchor_label": f"Block {block_id} Ln {line_start} Anchor {position}",
                "observed_anchor": occurrence.get("observed_anchor", ""),
                "surface": occurrence.get("surface", ""),
                "resolved_anchor": NULL_ANCHOR,
                "count_eligible": False,
                "memory_truth": False,
            })
        rows.sort(key=lambda row: (int(row["block_id"]), int(row["line_start"]), int(row["anchor_position"]), str(row["observed_anchor"])))
        return rows

    def _paragraph_line_locators(self, payload: dict[str, Any]) -> dict[int, dict[str, int]]:
        source_path = Path(str(payload.get("source_path") or ""))
        if not source_path.exists() or not source_path.is_file():
            return {}
        try:
            source_text = source_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return {}
        paragraphs = [row for row in payload.get("paragraphs") or [] if isinstance(row, dict)]
        if not paragraphs:
            return {}
        normalized_source, source_index = _normalize_with_source_index(source_text)
        if not normalized_source or not source_index:
            return {}
        locators: dict[int, dict[str, int]] = {}
        cursor = 0
        for paragraph in paragraphs:
            paragraph_id = int(paragraph.get("paragraph_id", len(locators)) or 0)
            normalized_paragraph, _ = _normalize_with_source_index(str(paragraph.get("text") or ""))
            if not normalized_paragraph:
                continue
            found = normalized_source.find(normalized_paragraph, cursor)
            if found < 0:
                found = normalized_source.find(normalized_paragraph)
            if found < 0:
                continue
            raw_start = source_index[min(found, len(source_index) - 1)]
            raw_end_index = min(found + len(normalized_paragraph) - 1, len(source_index) - 1)
            raw_end = source_index[raw_end_index]
            locators[paragraph_id] = {
                "block_id": paragraph_id,
                "line_start": source_text.count("\n", 0, raw_start) + 1,
                "line_end": source_text.count("\n", 0, raw_end) + 1,
            }
            cursor = found + len(normalized_paragraph)
        return locators

    def build_observed_map(
        self,
        source_path: Path,
        *,
        count_target: str = "binary_source_local",
        null_anchors: set[str] | None = None,
    ) -> dict[str, Any]:
        source_path = Path(source_path).expanduser().resolve()
        if not source_path.exists():
            raise FileNotFoundError(source_path)
        if source_path.is_dir():
            raise IsADirectoryError(source_path)

        map_path = self._observed_map_path(source_path)
        symbolic_map_path = self._symbolic_map_path(source_path)
        symbolic_locator_path = self._symbolic_locator_path(source_path)
        symbolic_null_path = self._symbolic_null_path(source_path)
        symbolic_visual_path = self._symbolic_visual_path(source_path)
        observed_map_name = map_path.name
        prepared = prepare_file(source_path)
        source_id = hashlib.sha1((str(source_path) + "\n" + prepared.sha256 + "\n" + observed_map_name).encode("utf-8")).hexdigest()
        if isinstance(prepared.metadata, dict) and prepared.metadata.get("visual_manifest"):
            raise ValueError("visual intake preview is source-local evidence only; use a future visual approval route before mapping/counting")
        text = prepared.prepared_text
        inventory = self._extract_document_anchor_inventory(text)
        observed_counts: Counter[str] = inventory["observed_counts"]
        known_anchors = set(self._all_known_anchors())
        null_anchor_set = {self.normalize_anchor(anchor) for anchor in (null_anchors or set()) if self.normalize_anchor(anchor)}
        unique_anchors = sorted(observed_counts)

        resolution_map: dict[str, str] = {anchor: anchor for anchor in unique_anchors if anchor in known_anchors}
        for anchor in null_anchor_set:
            if anchor in observed_counts:
                resolution_map[anchor] = NULL_ANCHOR
        raw_missing_counts: Counter[str] = Counter({
            anchor: count for anchor, count in observed_counts.items() if anchor not in known_anchors and anchor not in null_anchor_set
        })
        classified_missing = classify_unknown_anchor_rows(self._anchor_rows(raw_missing_counts))
        companion_counts: Counter[str] = Counter()
        classified_null_counts: Counter[str] = Counter()
        missing_counts: Counter[str] = Counter(raw_missing_counts)

        suggestions: dict[str, str] = {}
        review_rows = self._build_misspelled_review_rows(missing_counts, known_anchors, suggestions=suggestions)
        review_index = {row["anchor"]: row for row in review_rows}

        corrections: list[dict[str, Any]] = []
        additions: list[dict[str, Any]] = []
        decomposed_string_counts: Counter[str] = Counter()
        unresolved_counts: Counter[str] = Counter(missing_counts)

        unresolved_anchor_count = len(unresolved_counts)
        temp_symbol_map, temp_entries = self._build_temp_symbol_entries(source_path, unresolved_counts)
        resolution_map.update(temp_symbol_map)
        for anchor, temp_symbol in temp_symbol_map.items():
            row = review_index.get(anchor)
            if row is not None:
                row["ingest_action"] = "temp_symbolized"
                row["resolved_to"] = temp_symbol
                row["temp_symbol_version"] = TEMP_SYMBOL_VERSION

        review_path = self._write_misspelled_review(source_path, inventory, review_rows)
        if unresolved_anchor_count > 0:
            self._register_missing_anchors(unresolved_counts)
            logger.info("LEXICON INCOMPLETE: using source-local temp symbols for unresolved anchors")
        else:
            logger.info("LEXICON COMPLETE: proceeding to mapping")

        mapping = build_anchor_map(
            text,
            window_radius=DEFAULT_WINDOW_RADIUS,
            resolved_anchors=resolution_map,
            null_anchors=null_anchor_set,
            decompose_anchors=set(decomposed_string_counts),
        )
        line_locators = self._paragraph_line_locators({
            "source_path": str(source_path),
            "paragraphs": mapping["paragraphs"],
        })
        for paragraph in mapping["paragraphs"]:
            locator = line_locators.get(int(paragraph.get("paragraph_id", 0) or 0))
            if locator:
                paragraph.update(locator)
        for occurrence in mapping["occurrences"]:
            locator = line_locators.get(int(occurrence.get("paragraph_id", 0) or 0))
            if locator:
                occurrence["block_id"] = locator["block_id"]
                occurrence["line_start"] = locator["line_start"]
                occurrence["line_end"] = locator["line_end"]
        null_index = self._null_occurrence_index(mapping["occurrences"])
        resolved_counts: Counter[str] = mapping["observed_counts"]
        known_counts: Counter[str] = Counter({
            anchor: count for anchor, count in observed_counts.items() if anchor in known_anchors
        })
        temp_symbols_present = bool(temp_entries)
        source_local_only_present = temp_symbols_present or bool(companion_counts) or bool(null_anchor_set)
        symbolic_anchors: list[str] = []
        for paragraph in mapping["paragraphs"]:
            symbolic_anchors.extend(str(anchor) for anchor in paragraph.get("resolved_anchors", []) if str(anchor))
        symbol_by_anchor, symbol_authority = build_source_local_symbol_table(
            symbolic_anchors,
            canonical_symbol_by_anchor=self._canonical_symbol_by_anchor(),
            symbol_authority_by_anchor=self._symbol_authority_by_anchor(),
            source_id=source_id,
        )
        symbol_authority = self._apply_user_symbol_authority(symbol_authority)
        authority_by_symbol = {
            str(row.get("symbol") or ""): str(row.get("authority") or "")
            for row in symbol_authority
            if isinstance(row, dict)
        }
        symbolic_relation_rows = build_symbol_relation_rows(
            mapping["paragraphs"],
            symbol_by_anchor=symbol_by_anchor,
            window_radius=DEFAULT_WINDOW_RADIUS,
        )
        if count_target not in {"binary_source_local", "user_chat_preview"}:
            raise ValueError("JSON count targets are removed on the binary spine branch")
        count_write = {
            "count_target": count_target,
            "count_paths": [],
            "lifetime_write_skipped": True,
            "json_counts_removed": True,
            "binary_counts_required": True,
            "reason": "observed_map_only_binary_symbol_counts_post_step_required",
        }

        observed_rows = [
            {
                "anchor": anchor,
                "observations": count,
                "known": anchor in known_anchors,
                "resolved_to": resolution_map.get(anchor, anchor),
                "null_mapped": anchor in null_anchor_set,
            }
            for anchor, count in sorted(observed_counts.items(), key=lambda item: (-item[1], item[0]))
        ]

        temp_lexicon_path: Path | None = None
        if source_local_only_present:
            temp_lexicon_path = self._temp_lexicon_path(source_path)
            self._write_json(temp_lexicon_path, {
                "saved_at": _utc_now(),
                "source_path": str(source_path),
                "source_name": source_path.name,
                "temp_symbol_version": TEMP_SYMBOL_VERSION,
                "authority": "source_local_coordinate",
                "entries": temp_entries,
                "companion_authority_anchors": self._anchor_rows(companion_counts),
                "null_anchors": self._anchor_rows(Counter({
                    anchor: observed_counts[anchor]
                    for anchor in null_anchor_set
                    if anchor in observed_counts
                })),
            })

        payload = {
            "saved_at": _utc_now(),
            "source_path": str(source_path),
            "source_name": source_path.name,
            "paragraph_count": mapping["paragraph_count"],
            "window_radius": mapping["window_radius"],
            "total_anchor_observations": int(sum(observed_counts.values())),
            "unique_anchor_count": len(observed_counts),
            "known_anchor_count": len(known_counts),
            "companion_anchor_count": len(companion_counts),
            "missing_anchor_count": len(missing_counts),
            "null_anchor_count": len([anchor for anchor in null_anchor_set if anchor in observed_counts]),
            "null_occurrence_count": len(null_index),
            "known_anchor_observations": int(sum(known_counts.values())),
            "companion_anchor_observations": int(sum(companion_counts.values())),
            "missing_anchor_observations": int(sum(missing_counts.values())),
            "character_decomposed_anchor_count": len(decomposed_string_counts),
            "character_decomposed_anchor_observations": int(sum(decomposed_string_counts.values())),
            "null_anchor_observations": int(sum(observed_counts.get(anchor, 0) for anchor in null_anchor_set)),
            "raw_missing_anchor_count": len(raw_missing_counts),
            "raw_missing_anchor_observations": int(sum(raw_missing_counts.values())),
            "paragraphs": mapping["paragraphs"],
            "paragraph_line_locators": {str(key): value for key, value in line_locators.items()},
            "occurrences": mapping["occurrences"],
            "null_index": null_index,
            "co_occurrence_counts": mapping["co_occurrence_counts"],
            "items": mapping["items"],
            "anchor_index": mapping["anchor_index"],
            "stats": mapping["stats"],
            "known_anchors": self._anchor_rows(known_counts),
            "companion_authority_anchors": self._anchor_rows(companion_counts),
            "missing_anchors": self._anchor_rows(missing_counts),
            "character_decomposed_anchors": self._anchor_rows(decomposed_string_counts),
            "null_anchors": self._anchor_rows(Counter({
                anchor: observed_counts[anchor]
                for anchor in null_anchor_set
                if anchor in observed_counts
            })),
            "observed_anchors": observed_rows,
            "spell_corrections": corrections,
            "lexicon_additions": additions,
            "classified_missing_lanes": {
                "lane_counts": classified_missing.get("lane_counts", {}),
                "lane_observations": classified_missing.get("lane_observations", {}),
            },
            "temp_symbol_count": len(temp_entries),
            "temp_symbols": temp_entries,
            "temp_lexicon_path": str(temp_lexicon_path) if temp_lexicon_path else "",
            "document_prep": {
                key: value
                for key, value in prepared.to_dict().items()
                if key != "prepared_text"
            },
            "count_target": count_write["count_target"],
            "count_paths": count_write["count_paths"],
            "count_write": count_write,
        }

        locator_rows = [
            {
                "paragraph_id": int(paragraph.get("paragraph_id", 0) or 0),
                "block_id": int(paragraph.get("block_id", paragraph.get("paragraph_id", 0)) or 0),
                "line_start": int(paragraph.get("line_start", 0) or 0),
                "line_end": int(paragraph.get("line_end", paragraph.get("line_start", 0)) or paragraph.get("line_start", 0) or 0),
                "anchor_count": int(paragraph.get("anchor_count", len(paragraph.get("resolved_anchors") or paragraph.get("anchors") or [])) or 0),
                "countable_anchor_count": int(paragraph.get("countable_anchor_count", 0) or 0),
            }
            for paragraph in mapping["paragraphs"]
            if isinstance(paragraph, dict)
        ]
        visual_rows: list[dict[str, Any]] = []
        document_film = (prepared.metadata or {}).get("document_film") if isinstance(prepared.metadata, dict) else None
        if isinstance(document_film, dict):
            for frame in document_film.get("frames") or []:
                if not isinstance(frame, dict):
                    continue
                manifest = frame.get("visual_manifest") if isinstance(frame.get("visual_manifest"), dict) else {}
                source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
                page_number = int(frame.get("page_number") or source.get("page_number") or 0)
                frame_index = int(frame.get("frame_index") if frame.get("frame_index") is not None else source.get("frame_index", 0) or 0)
                visual_rows.append({
                    "block_id": f"page_{page_number}" if page_number else "",
                    "block_ordinal": page_number,
                    "line_start": page_number,
                    "line_end": page_number,
                    "visual_record_id": str(frame.get("visual_record_id") or source.get("visual_record_id") or ""),
                    "kind": "pdf_page_frame",
                    "source_path_ref": str(frame.get("source_path_ref") or ""),
                    "page_index": int(frame.get("page_index") if frame.get("page_index") is not None else source.get("page_index", -1) or -1),
                    "page_number": page_number,
                    "frame_index": frame_index,
                    "frame_timestamp_ms": int(frame.get("frame_timestamp_ms") if frame.get("frame_timestamp_ms") is not None else source.get("frame_timestamp_ms", 0) or 0),
                    "width": source.get("width", frame.get("width")),
                    "height": source.get("height", frame.get("height")),
                    "aspect_ratio": str(source.get("aspect_ratio") or frame.get("aspect_ratio") or "unknown"),
                    "file_format": str(source.get("file_format") or frame.get("file_format") or "unknown"),
                    "color_mode": str(source.get("color_mode") or frame.get("color_mode") or "unknown"),
                    "manifest_id": str(frame.get("visual_record_id") or source.get("visual_record_id") or ""),
                    "geometry_status": str(frame.get("geometry_status") or "known"),
                    "recognition_status": "not_run",
                    "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
                })
        for ref in (prepared.metadata or {}).get("visual_refs") or []:
            if isinstance(ref, dict) and str(ref.get("source_path") or ref.get("source_path_ref") or ref.get("visual_record_id") or "").strip():
                visual_rows.append({
                    "block_id": "",
                    "block_ordinal": 0,
                    "line_start": 0,
                    "line_end": 0,
                    **ref,
                })
        for paragraph in mapping["paragraphs"]:
            if not isinstance(paragraph, dict):
                continue
            paragraph_id = int(paragraph.get("paragraph_id", 0) or 0)
            for ref in paragraph.get("visual_refs") or []:
                if isinstance(ref, dict) and str(ref.get("visual_record_id") or ref.get("source_path") or ref.get("source_path_ref") or "").strip():
                    visual_rows.append({
                        "block_id": f"block_{paragraph_id}",
                        "block_ordinal": paragraph_id,
                        "line_start": int(paragraph.get("line_start", 0) or 0),
                        "line_end": int(paragraph.get("line_end", paragraph.get("line_start", 0)) or paragraph.get("line_start", 0) or 0),
                        **ref,
                    })

        write_symbolic_map_binary(
            symbolic_map_path,
            metadata={
                "schema_version": "anchorworks_symbolic_map_binary_metadata@1",
                "source_path": str(source_path),
                "source_name": source_path.name,
                "source_hash": prepared.sha256,
                "source_id": source_id,
                "observed_map_name": observed_map_name,
                "paragraph_count": mapping["paragraph_count"],
                "window_radius": mapping["window_radius"],
                "anchor_observations": int(sum(observed_counts.values())),
                "symbol_authority_count": len(symbol_authority),
                "symbol_authority": symbol_authority,
            },
            relations=[
                SymbolicMapRelation(
                    root_symbol_id=int(row["symbol_id"]),
                    neighbor_symbol_id=int(row["neighbor_symbol_id"]),
                    offset=int(str(row["offset"]).replace("+", "")),
                    lane=self._symbol_relation_lane(authority_by_symbol.get(str(row["neighbor_symbol_anchor"]))),
                    flags=0,
                    count=int(row["observations"]),
                )
                for row in symbolic_relation_rows
            ],
        )
        write_symbolic_map_locator_sidecar(symbolic_locator_path, locator_rows)
        write_symbolic_map_null_sidecar(symbolic_null_path, null_index)
        write_symbolic_map_visual_sidecar(symbolic_visual_path, visual_rows)
        payload["symbolic_map_path"] = str(symbolic_map_path)
        payload["symbolic_map_relation_count"] = len(symbolic_relation_rows)
        payload["symbolic_locator_path"] = str(symbolic_locator_path)
        payload["symbolic_locator_count"] = len(locator_rows)
        payload["symbolic_null_path"] = str(symbolic_null_path)
        payload["symbolic_null_count"] = len(null_index)
        payload["symbolic_visual_path"] = str(symbolic_visual_path)
        payload["symbolic_visual_count"] = len(visual_rows)
        self._write_json(map_path, payload)

        return {
            "ok": True,
            "source_path": str(source_path),
            "source_name": source_path.name,
            "saved_map_path": str(map_path),
            "saved_map_name": map_path.name,
            "symbolic_map_path": str(symbolic_map_path),
            "symbolic_map_name": symbolic_map_path.name,
            "symbolic_map_relation_count": len(symbolic_relation_rows),
            "symbolic_locator_path": str(symbolic_locator_path),
            "symbolic_locator_name": symbolic_locator_path.name,
            "symbolic_locator_count": len(locator_rows),
            "symbolic_null_path": str(symbolic_null_path),
            "symbolic_null_name": symbolic_null_path.name,
            "symbolic_null_count": len(null_index),
            "symbolic_visual_path": str(symbolic_visual_path),
            "symbolic_visual_name": symbolic_visual_path.name,
            "symbolic_visual_count": len(visual_rows),
            "paragraph_count": payload["paragraph_count"],
            "window_radius": payload["window_radius"],
            "total_anchor_observations": payload["total_anchor_observations"],
            "unique_anchor_count": payload["unique_anchor_count"],
            "known_anchor_count": payload["known_anchor_count"],
            "companion_anchor_count": payload["companion_anchor_count"],
            "missing_anchor_count": payload["missing_anchor_count"],
            "null_anchor_count": payload["null_anchor_count"],
            "null_occurrence_count": payload["null_occurrence_count"],
            "known_anchor_observations": payload["known_anchor_observations"],
            "companion_anchor_observations": payload["companion_anchor_observations"],
            "missing_anchor_observations": payload["missing_anchor_observations"],
            "character_decomposed_anchor_count": payload["character_decomposed_anchor_count"],
            "character_decomposed_anchor_observations": payload["character_decomposed_anchor_observations"],
            "null_anchor_observations": payload["null_anchor_observations"],
            "raw_missing_anchor_count": payload["raw_missing_anchor_count"],
            "raw_missing_anchor_observations": payload["raw_missing_anchor_observations"],
            "registered_missing_anchors": len(unresolved_counts),
            "known_anchors_preview": payload["known_anchors"][:25],
            "companion_authority_anchors_preview": payload["companion_authority_anchors"][:25],
            "missing_anchors_preview": payload["missing_anchors"][:25],
            "character_decomposed_anchors": payload["character_decomposed_anchors"],
            "character_decomposed_anchors_preview": payload["character_decomposed_anchors"][:25],
            "null_anchors": payload["null_anchors"],
            "null_anchors_preview": payload["null_anchors"][:25],
            "null_index_preview": payload["null_index"][:25],
            "classified_missing_lanes": payload["classified_missing_lanes"],
            "observed_anchors_preview": payload["observed_anchors"][:25],
            "occurrence_preview": payload["occurrences"][:12],
            "co_occurrence_preview": payload["co_occurrence_counts"][:12],
            "anchor_index_preview": payload["anchor_index"][:25],
            "context_items_preview": list(payload["items"].values())[:12],
            "document_prep": payload["document_prep"],
            "count_target": count_write["count_target"],
            "count_paths": count_write["count_paths"],
            "count_write": count_write,
            "temp_symbol_count": len(temp_entries),
            "temp_lexicon_path": str(temp_lexicon_path) if temp_lexicon_path else "",
            "temp_symbols": temp_entries,
            "observed_anchors": payload["observed_anchors"],
            "misspelled_review_path": str(review_path),
            "misspelled_review_name": review_path.name,
            "misspelled_review_preview": review_rows[:25],
        }
