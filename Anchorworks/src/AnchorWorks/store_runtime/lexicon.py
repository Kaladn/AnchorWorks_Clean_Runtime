from __future__ import annotations

from ..store_support import *


class LexiconMixin:
    def _user_lexicon_symbol_from_allocation(self, allocation: dict[str, Any]) -> str:
        allocation_index = int(allocation.get("allocation_index", 0) or 0)
        if allocation_index < 0 or allocation_index >= USER_LEXICON_SYMBOL_CAPACITY:
            raise ValueError("user lexicon symbol range exhausted")
        symbol = str(allocation.get("hex") or allocation.get("symbol") or "").strip()
        if symbol.upper().startswith("0XE"):
            return "0x" + symbol[2:].upper()
        return f"0x{USER_LEXICON_SYMBOL_BASE + allocation_index:010X}"

    def _build_user_lexicon_entry(
        self,
        anchor: str,
        allocation: dict[str, Any],
        *,
        frequency: int = 0,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        symbol = self._user_lexicon_symbol_from_allocation(allocation)
        return {
            "word": anchor,
            "display": anchor,
            "symbol": symbol,
            "hex": symbol,
            "status": "ASSIGNED",
            "pack": "user",
            "authority": "user_lexicon",
            "frequency": int(frequency or 0),
            "mapped_at": timestamp or _utc_now(),
            "allocation_index": int(allocation.get("allocation_index", 0) or 0),
        }

    def ensure_user_lexicon_seeded(self) -> dict[str, Any]:
        with self._lock:
            existing_entries = self._read_entries(self.user_lexicon_path)
            existing_keys = {
                (
                    self.normalize_anchor(entry.get("word", "")),
                    str(entry.get("symbol") or entry.get("hex") or "").strip().upper(),
                )
                for entry in existing_entries
            }
            seeded: list[dict[str, Any]] = []

            source_paths: list[Path] = []
            source_paths.extend(sorted(self.canonical_dir.glob("canonical_*.json")))
            canonical_structural = self.canonical_dir / "structural.json"
            if canonical_structural.exists():
                source_paths.append(canonical_structural)
            if self.structural_file.exists():
                source_paths.append(self.structural_file)

            for path in source_paths:
                for entry in self._read_entries(path):
                    anchor = self.normalize_anchor(entry.get("word", ""))
                    symbol = str(entry.get("symbol") or entry.get("hex") or "").strip()
                    if not anchor or not symbol:
                        continue
                    key = (anchor, symbol.upper())
                    if key in existing_keys:
                        continue
                    seeded.append({
                        "word": anchor,
                        "display": entry.get("display") or entry.get("word") or anchor,
                        "symbol": symbol,
                        "hex": entry.get("hex") or symbol,
                        "status": entry.get("status") or "SEEDED",
                        "pack": "user",
                        "authority": "canonical_seed",
                        "frequency": int(entry.get("frequency", 0) or 0),
                        "mapped_at": entry.get("mapped_at") or _utc_now(),
                    })
                    existing_keys.add(key)

            if seeded:
                combined = existing_entries + seeded
                combined.sort(key=lambda item: (self.normalize_anchor(item.get("word", "")), str(item.get("symbol") or item.get("hex") or "")))
                self._write_entries(self.user_lexicon_path, combined)
            elif not self.user_lexicon_path.exists():
                self._write_entries(self.user_lexicon_path, [])

            return {
                "ok": True,
                "canonical_entries_seeded": len(seeded),
                "seed_mode": "explicit_copy_canonical_and_structural_to_user_lexicon",
                "user_lexicon_path": str(self.user_lexicon_path),
            }

    def _load_pending(self) -> list[dict[str, Any]]:
        data = self._read_json(self.pending_path, [])
        out: list[dict[str, Any]] = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    word = self.normalize_anchor(item.get("word", ""))
                    if word:
                        out.append({
                            "word": word,
                            "frequency": int(item.get("frequency", 0) or 0),
                            "added_at": item.get("added_at") or _utc_now(),
                        })
                elif isinstance(item, str):
                    word = self.normalize_anchor(item)
                    if word:
                        out.append({"word": word, "frequency": 0, "added_at": _utc_now()})
        return out

    def _write_pending(self, entries: list[dict[str, Any]]) -> None:
        self._write_json(self.pending_path, entries)

    def _load_unmatched(self) -> list[dict[str, Any]]:
        data = self._read_json(self.unmatched_path, [])
        out: list[dict[str, Any]] = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    word = self.normalize_anchor(item.get("word", ""))
                    if word:
                        out.append({
                            "word": word,
                            "frequency": int(item.get("frequency", 0) or 0),
                            "first_seen": item.get("first_seen") or _utc_now(),
                        })
                elif isinstance(item, str):
                    word = self.normalize_anchor(item)
                    if word:
                        out.append({"word": word, "frequency": 0, "first_seen": _utc_now()})
        return out

    def _write_unmatched(self, entries: list[dict[str, Any]]) -> None:
        self._write_json(self.unmatched_path, entries)

    def _load_missing_anchor_registry(self) -> list[dict[str, Any]]:
        data = self._read_json(self.missing_anchor_registry_path, [])
        rows: list[dict[str, Any]] = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    anchor = item.get("anchor")
                    if isinstance(anchor, str) and anchor:
                        rows.append({
                            "anchor": anchor,
                            "observations": int(item.get("observations", 0) or 0),
                            "first_seen": item.get("first_seen") or _utc_now(),
                            "last_seen": item.get("last_seen") or _utc_now(),
                        })
        return rows

    def _write_missing_anchor_registry(self, entries: list[dict[str, Any]]) -> None:
        self._write_json(self.missing_anchor_registry_path, entries)

    def _register_missing_anchors(self, missing_counts: Counter[str]) -> None:
        if not missing_counts:
            return

        with self._lock:
            existing_rows = self._load_missing_anchor_registry()
            existing = {row["anchor"]: row for row in existing_rows}
            timestamp = _utc_now()

            for anchor, count in missing_counts.items():
                row = existing.get(anchor)
                if row is None:
                    existing[anchor] = {
                        "anchor": anchor,
                        "observations": int(count),
                        "first_seen": timestamp,
                        "last_seen": timestamp,
                    }
                    continue

                row["observations"] = int(row.get("observations", 0) or 0) + int(count)
                row["last_seen"] = timestamp

            rows = sorted(existing.values(), key=lambda item: (-int(item["observations"]), item["anchor"]))
            self._write_missing_anchor_registry(rows)

    def _load_ignored(self) -> list[str]:
        data = self._read_json(self.ignored_path, [])
        if not isinstance(data, list):
            return []
        return sorted({self.normalize_anchor(item) for item in data if self.normalize_anchor(item)})

    def _write_ignored(self, words: list[str]) -> None:
        self._write_json(self.ignored_path, sorted({self.normalize_anchor(word) for word in words if self.normalize_anchor(word)}))

    def _pack_paths(self, pack: str) -> list[tuple[str, Path]]:
        selected = (pack or "all").lower()
        paths: list[tuple[str, Path]] = []
        if selected in {"all", "canonical"}:
            canonical_paths = sorted(self.canonical_dir.glob("canonical_*.json"))
            if canonical_paths:
                paths.extend(("canonical", path) for path in canonical_paths)
            else:
                paths.extend(("canonical", self.canonical_dir / f"canonical_{letter}.json") for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        if selected in {"all", "structural"} and self.structural_file.exists():
            paths.append(("structural", self.structural_file))
        if selected in {"all", "user", "user_lexicon"} and self.user_lexicon_path.exists():
            paths.append(("user", self.user_lexicon_path))
        if selected in {"all", "spare"}:
            paths.extend(("spare", path) for path in self._active_spare_paths())
        return paths

    def _preview_entry(self, raw: dict[str, Any], pack: str) -> dict[str, Any]:
        hex_value = raw.get("hex") or raw.get("symbol") or ""
        return {
            "word": raw.get("word", "") or "",
            "display": raw.get("display") or raw.get("word", "") or "",
            "status": raw.get("status", ""),
            "frequency": int(raw.get("frequency", 0) or 0),
            "hex": hex_value,
            "binary": raw.get("binary", ""),
            "font_symbol": raw.get("font_symbol", ""),
            "tone_signature": raw.get("tone_signature", ""),
            "mapped_at": raw.get("mapped_at"),
            "pack": raw.get("pack") or pack,
            "symbol": raw.get("symbol") or hex_value,
            "payload": {
                "hex": hex_value,
                "binary": raw.get("binary", ""),
                "font_symbol": raw.get("font_symbol", ""),
                "tone_signature": raw.get("tone_signature", ""),
            },
        }

    def _phrase_previews(self) -> list[dict[str, Any]]:
        previews: list[dict[str, Any]] = []
        for entry in self.phrases.phrases():
            hex_value = entry.get("hex") or entry.get("symbol") or ""
            phrase = str(entry.get("phrase") or entry.get("display") or "").strip()
            previews.append({
                "word": phrase,
                "display": entry.get("display") or phrase,
                "status": entry.get("status", ""),
                "frequency": int((entry.get("source_support") or {}).get("occurrences", 0) or 0),
                "hex": hex_value,
                "binary": entry.get("binary", ""),
                "font_symbol": entry.get("font_symbol", ""),
                "tone_label": entry.get("tone_label", ""),
                "tone_profile": entry.get("tone_profile"),
                "mapped_at": entry.get("mapped_at"),
                "pack": "phrase",
                "symbol": entry.get("symbol") or hex_value,
                "phrase_type": entry.get("phrase_type", ""),
                "anchor_sequence": entry.get("anchor_sequence") or [],
                "payload": {
                    "hex": hex_value,
                    "binary": entry.get("binary", ""),
                    "font_symbol": entry.get("font_symbol", ""),
                    "tone_label": entry.get("tone_label", ""),
                    "visual_rune": entry.get("visual_rune", ""),
                },
            })
        return previews

    def _find_entry(self, word: str) -> tuple[dict[str, Any], str, Path] | None:
        target = self.normalize_anchor(word)
        if not target:
            return None
        structural = self._read_entries(self.structural_file)
        for entry in structural:
            if self.normalize_anchor(entry.get("word", "")) == target:
                return entry, "structural", self.structural_file
        for entry in self._read_entries(self.user_lexicon_path):
            if self.normalize_anchor(entry.get("word", "")) == target:
                return entry, "user", self.user_lexicon_path
        letter = self._letter_for_word(target)
        path = self.canonical_dir / f"canonical_{letter}.json"
        for entry in self._read_entries(path):
            if self.normalize_anchor(entry.get("word", "")) == target:
                return entry, "canonical", path
        return None

    def _all_known_anchors(self) -> set[str]:
        if self._known_anchor_index is not None:
            return self._known_anchor_index

        known: set[str] = set()
        for pack_name, path in self._pack_paths("all"):
            if pack_name == "spare":
                continue
            for entry in self._read_entries(path):
                word = entry.get("word")
                if isinstance(word, str) and word:
                    normalized = self.normalize_anchor(word)
                    if normalized:
                        known.add(normalized)

        self._known_anchor_index = known
        return known

    def recognize_query_anchors(self, text: str) -> dict[str, Any]:
        observed = _ordered_unique(row["anchor"] for row in extract_anchor_rows(str(text or "")) if row.get("anchor"))
        query_frame = build_query_frame(observed)
        punctuation = [
            row["anchor"]
            for row in query_frame.get("director_anchors", [])
            if isinstance(row, dict) and row.get("role") == "punctuation"
        ]
        punctuation_set = set(punctuation)
        query_anchors = [anchor for anchor in observed if anchor not in punctuation_set]
        direction_anchors = [
            str(row.get("anchor") or "").strip().casefold()
            for row in query_frame.get("director_anchors", [])
            if isinstance(row, dict) and str(row.get("anchor") or "").strip()
        ]
        content = [
            str(anchor or "").strip().casefold()
            for anchor in query_frame.get("content_seeds", [])
            if str(anchor or "").strip()
        ]
        known = self._all_known_anchors()
        represented = [anchor for anchor in query_anchors if anchor in known]
        missing = [anchor for anchor in query_anchors if anchor not in known]
        represented_content = [anchor for anchor in content if anchor in known]
        missing_content = [anchor for anchor in content if anchor not in known]
        return {
            "schema_version": "anchorworks_lexicon_recognition@1",
            "query": str(text or ""),
            "observed_anchors": observed,
            "query_anchors": query_anchors,
            "content_anchors": content,
            "direction_anchors": direction_anchors,
            "punctuation_anchors": punctuation,
            "input_kind": _query_input_kind(observed, query_frame),
            "query_frame": query_frame,
            "represented_anchors": represented,
            "missing_anchors": missing,
            "represented_content_anchors": represented_content,
            "missing_content_anchors": missing_content,
            "recognition_layer": "lexicon",
            "lexicon_first": True,
            "direction_only_anchors": sorted(set(direction_anchors + punctuation)),
            "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
        }

    def _canonical_anchors(self) -> set[str]:
        if self._canonical_anchor_index is not None:
            return self._canonical_anchor_index

        canonical: set[str] = set()
        for _, path in self._pack_paths("canonical"):
            for entry in self._read_entries(path):
                word = entry.get("word")
                if isinstance(word, str) and word:
                    normalized = self.normalize_anchor(word)
                    if normalized:
                        canonical.add(normalized)

        self._canonical_anchor_index = canonical
        return canonical

    def _canonical_symbol_by_anchor(self) -> dict[str, str]:
        if self._canonical_symbol_index is not None:
            return dict(self._canonical_symbol_index)
        out: dict[str, str] = {}
        for _, path in self._pack_paths("canonical"):
            for entry in self._read_entries(path):
                anchor = self.normalize_anchor(entry.get("word", ""))
                symbol = str(entry.get("hex") or entry.get("symbol") or "").strip()
                if anchor and symbol:
                    out[anchor] = symbol
        for _, path in self._pack_paths("user"):
            for entry in self._read_entries(path):
                anchor = self.normalize_anchor(entry.get("word", ""))
                symbol = str(entry.get("hex") or entry.get("symbol") or "").strip()
                if anchor and symbol and anchor not in out:
                    out[anchor] = symbol
        self._canonical_symbol_index = dict(out)
        return out

    def _user_anchor_set(self) -> set[str]:
        anchors: set[str] = set()
        for _, path in self._pack_paths("user"):
            for entry in self._read_entries(path):
                anchor = self.normalize_anchor(entry.get("word", ""))
                if anchor:
                    anchors.add(anchor)
        return anchors

    def _symbol_authority_by_anchor(self) -> dict[str, tuple[str, str]]:
        out: dict[str, tuple[str, str]] = {}
        for _, path in self._pack_paths("canonical"):
            for entry in self._read_entries(path):
                anchor = self.normalize_anchor(entry.get("word", ""))
                symbol = str(entry.get("hex") or entry.get("symbol") or "").strip()
                if anchor and symbol:
                    out[anchor] = (symbol, "canonical")
        for _, path in self._pack_paths("user"):
            for entry in self._read_entries(path):
                anchor = self.normalize_anchor(entry.get("word", ""))
                symbol = str(entry.get("hex") or entry.get("symbol") or "").strip()
                if anchor and symbol and anchor not in out:
                    out[anchor] = (symbol, "user_lexicon")
        return out

    def _apply_user_symbol_authority(self, symbol_authority: list[dict[str, Any]]) -> list[dict[str, Any]]:
        user_anchors = self._user_anchor_set()
        if not user_anchors:
            return symbol_authority
        for row in symbol_authority:
            anchor = self.normalize_anchor(row.get("anchor", ""))
            if anchor in user_anchors:
                row["authority"] = "user_lexicon"
        return symbol_authority

    def _symbol_relation_lane(self, authority: str) -> int:
        if authority == "source_local":
            return 4
        if authority == "user_lexicon":
            return 5
        return 0

    def distribution(self) -> dict[str, Any]:
        canonical = 0
        structural = 0
        letters = {letter: 0 for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"}

        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            canonical_entries = self._read_entries(self.canonical_dir / f"canonical_{letter}.json")
            canonical += len(canonical_entries)
            letters[letter] += len(canonical_entries)

        structural_entries = self._read_entries(self.structural_file)
        structural = len(structural_entries)
        spare = sum(1 for entry in self._read_spare_entries() if str(entry.get("status", "")).upper() == "AVAILABLE")

        return {
            "total": canonical + structural,
            "canonical": canonical,
            "domain_packs": {},
            "structural": structural,
            "spare_slots": spare,
            "symbol_genome_pool": self.symbol_genome_status(),
            "letters": letters,
        }

    def symbol_genome_status(self) -> dict[str, Any]:
        return SymbolGenomePool(self.symbol_genome_pool_dir).status()

    def allocate_symbol_genome_identity(
        self,
        label: str,
        *,
        authority: str,
        category: str = "specialized",
        priority: int = 2,
    ) -> dict[str, Any]:
        return SymbolGenomePool(self.symbol_genome_pool_dir).allocate(
            label,
            authority=authority,
            category=category,
            priority=priority,
        )

    def checkpoint_symbol_genome(self, reason: str = "") -> dict[str, Any]:
        return SymbolGenomePool(self.symbol_genome_pool_dir).checkpoint(reason)

    def search(self, query: str, pack: str = "all", limit: int = 50) -> list[dict[str, Any]]:
        needle = self.normalize_word(query)
        if len(needle) < 2:
            return []
        results: list[dict[str, Any]] = []
        if pack in {"all", "phrase"}:
            for entry in self._phrase_previews():
                haystacks = [
                    self.normalize_word(entry.get("word", "")),
                    self.normalize_word(entry.get("display", "")),
                    self.normalize_word(entry.get("hex", "")),
                    self.normalize_word(entry.get("binary", "")),
                    self.normalize_word(entry.get("tone_label", "")),
                    self.normalize_word(entry.get("status", "")),
                    self.normalize_word(entry.get("phrase_type", "")),
                ]
                if any(needle in hay for hay in haystacks if hay):
                    results.append(entry)
                    if len(results) >= limit:
                        return results
        for pack_name, path in self._pack_paths(pack):
            if pack_name == "spare" and pack != "spare":
                continue
            for entry in self._read_entries(path):
                haystacks = [
                    self.normalize_word(entry.get("word", "")),
                    self.normalize_word(entry.get("display", "")),
                    self.normalize_word(entry.get("hex", "")),
                    self.normalize_word(entry.get("binary", "")),
                    self.normalize_word(entry.get("tone_signature", "")),
                    self.normalize_word(entry.get("status", "")),
                ]
                if any(needle in hay for hay in haystacks if hay):
                    results.append(self._preview_entry(entry, pack_name))
                    if len(results) >= limit:
                        return results
        return results

    def browse(self, letter: str, limit: int = 50, pack: str = "all") -> dict[str, Any]:
        letter = (letter or "A").strip().upper()[:1]
        entries: list[dict[str, Any]] = []
        total = 0
        if pack in {"all", "phrase"}:
            phrase_entries = [
                entry for entry in self._phrase_previews()
                if self._letter_for_word(str(entry.get("word") or "")) == letter
            ]
            total += len(phrase_entries)
            entries.extend(phrase_entries[: max(0, limit - len(entries))])
        if pack in {"all", "canonical"}:
            path = self.canonical_dir / f"canonical_{letter}.json"
            batch = self._read_entries(path)
            total += len(batch)
            entries.extend(self._preview_entry(entry, "canonical") for entry in batch[:limit])
        if pack == "spare" and len(entries) < limit:
            batch = self._read_spare_entries()
            total += len(batch)
            remaining = max(0, limit - len(entries))
            entries.extend(self._preview_entry(entry, "spare") for entry in batch[:remaining])
        return {"letter": letter, "total": total, "entries": entries[:limit]}

    def sample(self, count: int = 24, pack: str = "all") -> dict[str, Any]:
        chosen: list[dict[str, Any]] = []
        seen = 0
        if pack in {"all", "phrase"}:
            for preview in self._phrase_previews():
                seen += 1
                if len(chosen) < count:
                    chosen.append(preview)
                else:
                    index = random.randint(0, seen - 1)
                    if index < count:
                        chosen[index] = preview
        for pack_name, path in self._pack_paths(pack):
            if pack_name == "spare" and pack != "spare":
                continue
            for entry in self._read_entries(path):
                seen += 1
                preview = self._preview_entry(entry, pack_name)
                if len(chosen) < count:
                    chosen.append(preview)
                else:
                    index = random.randint(0, seen - 1)
                    if index < count:
                        chosen[index] = preview
        return {"total": seen, "entries": chosen}

    def top(self, count: int = 30, pack: str = "all") -> dict[str, Any]:
        ranked: list[dict[str, Any]] = []
        if pack in {"all", "phrase"}:
            ranked.extend(self._phrase_previews())
        for pack_name, path in self._pack_paths(pack):
            if pack_name == "spare" and pack != "spare":
                continue
            for entry in self._read_entries(path):
                ranked.append(self._preview_entry(entry, pack_name))
        ranked.sort(key=lambda item: (-int(item.get("frequency", 0) or 0), item.get("word", "") or item.get("hex", "")))
        return {"total": min(count, len(ranked)), "entries": ranked[:count]}

    def recent(self, count: int = 30) -> dict[str, Any]:
        entries: list[dict[str, Any]] = []
        for pack_name, path in self._pack_paths("all"):
            if pack_name == "spare":
                continue
            for entry in self._read_entries(path):
                if entry.get("mapped_at"):
                    entries.append(self._preview_entry(entry, pack_name))
        entries.sort(key=lambda item: item.get("mapped_at") or "", reverse=True)
        return {"total": len(entries), "entries": entries[:count]}

    def files(self) -> dict[str, Any]:
        files: list[dict[str, Any]] = []
        for folder, pattern, pack in [
            (self.canonical_dir, "canonical_{}.json", "canonical"),
        ]:
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                path = folder / pattern.format(letter)
                if path.exists():
                    stat = path.stat()
                    files.append({
                        "filename": path.name,
                        "letter": f"{letter} - {pack}",
                        "size_bytes": stat.st_size,
                        "modified": stat.st_mtime,
                    })
        for path in self._active_spare_paths():
            if path.exists():
                stat = path.stat()
                label = "* - spare" if path == self.spare_slots_path else f"{path.stem.rsplit('_', 1)[-1].upper()} - spare"
                files.append({
                    "filename": path.name,
                    "letter": label,
                    "size_bytes": stat.st_size,
                    "modified": stat.st_mtime,
                })
        if self.structural_file.exists():
            stat = self.structural_file.stat()
            files.append({
                "filename": self.structural_file.name,
                "letter": "# - structural",
                "size_bytes": stat.st_size,
                "modified": stat.st_mtime,
            })
        return {"lexicon_root": str(self.root), "files": files}

    def preview_file(self, filename: str, offset: int = 0, limit: int = 50) -> dict[str, Any]:
        target: Path | None = None
        for _, path in self._pack_paths("all"):
            if path.name == filename:
                target = path
                break
        if target is None:
            raise FileNotFoundError(filename)
        entries = self._read_entries(target)
        pack = "structural"
        if filename.startswith("canonical_"):
            pack = "canonical"
        elif filename == self.spare_slots_path.name or filename.startswith("pool_"):
            pack = "spare"
        preview = [self._preview_entry(entry, pack) for entry in entries[offset: offset + limit]]
        return {"filename": filename, "offset": offset, "limit": limit, "total": len(entries), "entries": preview}

    def entry(self, word: str) -> dict[str, Any] | None:
        found = self._find_entry(word)
        if found is None:
            return None
        raw, pack, _ = found
        preview = self._preview_entry(raw, pack)
        preview.update({
            "display": raw.get("display") or raw.get("word") or "",
            "wordnet": raw.get("wordnet"),
            "aliases": raw.get("aliases") or [],
            "categories": raw.get("categories") or ([raw.get("category")] if raw.get("category") else []),
            "notes": raw.get("notes"),
        })
        return preview

    def context_map(self, word: str) -> dict[str, Any]:
        surface = self.normalize_anchor(word)
        retrieved = self.retrieve_from_counts(surface, limit=100)
        before: dict[str, list[dict[str, Any]]] = {}
        after: dict[str, list[dict[str, Any]]] = {}
        for offset, rows in (retrieved.get("offsets") or {}).items():
            try:
                offset_int = int(offset)
            except (TypeError, ValueError):
                continue
            target = before if offset_int < 0 else after
            target[str(abs(offset_int))] = rows
        if before or after:
            return {
                "word": surface,
                "before": before,
                "after": after,
                "total_windows": int(retrieved.get("total_neighbor_observations", 0) or 0),
                "center_observations": int(retrieved.get("total_neighbor_observations", 0) or 0),
                "window_radius": DEFAULT_WINDOW_RADIUS,
            }
        return {
            "word": surface,
            "before": {},
            "after": {},
            "total_windows": 0,
            "center_observations": 0,
            "window_radius": DEFAULT_WINDOW_RADIUS,
        }

    def unmatched(self, letter: str | None = None, limit: int = 100) -> dict[str, Any]:
        entries = self._load_unmatched()
        if letter:
            needle = self.normalize_word(letter)[:1]
            entries = [item for item in entries if self.normalize_word(item["word"]).startswith(needle)]
        entries.sort(key=lambda item: (-int(item.get("frequency", 0) or 0), item["word"]))
        return {"unmatched_total": len(entries), "entries": entries[:limit]}

    def approve_unmatched(self, word: str) -> dict[str, Any]:
        surface = self.normalize_anchor(word)
        if not surface:
            raise ValueError("word required")
        if self._find_entry(surface):
            raise ValueError("word already exists in lexicon")
        with self._lock:
            unmatched = self._load_unmatched()
            pending = self._load_pending()
            picked = next((item for item in unmatched if item["word"] == surface), None)
            unmatched = [item for item in unmatched if item["word"] != surface]
            if not any(item["word"] == surface for item in pending):
                pending.append({
                    "word": surface,
                    "frequency": int((picked or {}).get("frequency", 0) or 0),
                    "added_at": _utc_now(),
                })
            self._write_unmatched(unmatched)
            self._write_pending(pending)
        return {"ok": True, "word": surface}

    def ignore_word(self, word: str) -> dict[str, Any]:
        surface = self.normalize_anchor(word)
        if not surface:
            raise ValueError("word required")
        with self._lock:
            ignored = self._load_ignored()
            if surface not in ignored:
                ignored.append(surface)
            self._write_ignored(ignored)
            self._write_unmatched([item for item in self._load_unmatched() if item["word"] != surface])
            self._write_pending([item for item in self._load_pending() if item["word"] != surface])
        return {"ok": True, "word": surface}

    def unignore_word(self, word: str) -> dict[str, Any]:
        surface = self.normalize_anchor(word)
        with self._lock:
            ignored = [item for item in self._load_ignored() if item != surface]
            self._write_ignored(ignored)
        return {"ok": True, "word": surface}

    def ignored(self, letter: str | None = None) -> dict[str, Any]:
        words = self._load_ignored()
        if letter:
            needle = self.normalize_word(letter)[:1]
            words = [word for word in words if self.normalize_word(word).startswith(needle)]
        return {"total": len(words), "words": words}

    def missing_anchor_review_queue(
        self,
        *,
        limit: int = 100,
        min_observations: int = 1,
        letter: str | None = None,
    ) -> dict[str, Any]:
        known = set(self._all_known_anchors())
        ignored = set(self._load_ignored())
        pending = {row["word"] for row in self._load_pending()}
        unmatched = {row["word"] for row in self._load_unmatched()}
        letter_prefix = self.normalize_word(letter or "")[:1]
        minimum = max(1, int(min_observations or 1))
        rows: list[dict[str, Any]] = []
        skipped_known = 0
        skipped_ignored = 0

        for row in self._load_missing_anchor_registry():
            anchor = self.normalize_anchor(row.get("anchor") or "")
            observations = int(row.get("observations", 0) or 0)
            if not anchor or observations < minimum:
                continue
            if letter_prefix and not self.normalize_word(anchor).startswith(letter_prefix):
                continue
            if anchor in known:
                skipped_known += 1
                continue
            if anchor in ignored:
                skipped_ignored += 1
                continue
            if anchor in pending:
                status = "pending"
            elif anchor in unmatched:
                status = "unmatched"
            else:
                status = "unreviewed"
            rows.append({
                "anchor": anchor,
                "observations": observations,
                "first_seen": row.get("first_seen") or "",
                "last_seen": row.get("last_seen") or "",
                "review_status": status,
                "known": False,
                "ignored": False,
            })

        rows.sort(key=lambda item: (-int(item["observations"]), item["anchor"]))
        capped_limit = max(1, int(limit or 100))
        return {
            "ok": True,
            "total_registry_anchors": len(self._load_missing_anchor_registry()),
            "reviewable_total": len(rows),
            "returned": min(len(rows), capped_limit),
            "skipped_known": skipped_known,
            "skipped_ignored": skipped_ignored,
            "min_observations": minimum,
            "entries": rows[:capped_limit],
            "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
        }

    def sync_missing_anchor_review_queue(
        self,
        *,
        limit: int = 1000,
        min_observations: int = 1,
        letter: str | None = None,
    ) -> dict[str, Any]:
        review = self.missing_anchor_review_queue(
            limit=limit,
            min_observations=min_observations,
            letter=letter,
        )
        candidates = [
            row for row in review.get("entries") or []
            if row.get("review_status") == "unreviewed"
        ]
        moved: list[dict[str, Any]] = []
        with self._lock:
            unmatched = self._load_unmatched()
            existing = {row["word"] for row in unmatched}
            timestamp = _utc_now()
            for row in candidates:
                anchor = self.normalize_anchor(row.get("anchor") or "")
                if not anchor or anchor in existing:
                    continue
                entry = {
                    "word": anchor,
                    "frequency": int(row.get("observations", 0) or 0),
                    "first_seen": row.get("first_seen") or timestamp,
                    "added_at": timestamp,
                    "source": "missing_anchor_registry",
                }
                unmatched.append(entry)
                existing.add(anchor)
                moved.append(entry)
            unmatched.sort(key=lambda item: (-int(item.get("frequency", 0) or 0), item["word"]))
            self._write_unmatched(unmatched)
        return {
            "ok": True,
            "moved_to_unmatched": len(moved),
            "reviewable_total": review.get("reviewable_total", 0),
            "entries": moved,
            "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
        }

    def classify_missing_anchor_registry(self) -> dict[str, Any]:
        output_dir = self.state_dir / "ingest_staging" / "anchor_inventory" / "classified_unknown_lanes"
        result = write_classified_unknown_report(self._load_missing_anchor_registry(), output_dir)
        result["math_lexicon"] = write_math_lexicon(output_dir / "math_lexicon.json")
        return result

    def pending(self) -> dict[str, Any]:
        entries = self._load_pending()
        entries.sort(key=lambda item: item.get("added_at") or "", reverse=True)
        return {"total": len(entries), "entries": entries}

    def remove_pending(self, word: str) -> dict[str, Any]:
        surface = self.normalize_anchor(word)
        with self._lock:
            pending = [item for item in self._load_pending() if item["word"] != surface]
            self._write_pending(pending)
        return {"ok": True, "word": surface}

    def _count_available_slots(self) -> int:
        return sum(1 for item in self._read_spare_entries() if str(item.get("status", "")).upper() == "AVAILABLE")

    def _assign_surface_anchor(self, anchor: str, frequency: int = 0) -> dict[str, Any]:
        surface_anchor = self.normalize_anchor(anchor)
        if not surface_anchor:
            raise ValueError("anchor required")
        if surface_anchor in self._all_known_anchors():
            raise ValueError("anchor already exists in lexicon")

        genome_pool = SymbolGenomePool(self.symbol_genome_pool_dir)
        allocation = genome_pool.allocate(
            surface_anchor,
            authority="user_lexicon",
            category="specialized",
            priority=2,
        )
        user_entries = self._read_entries(self.user_lexicon_path)
        new_entry = self._build_user_lexicon_entry(surface_anchor, allocation, frequency=frequency)
        user_entries.append(new_entry)
        user_entries.sort(key=lambda item: (str(item.get("word", "")).casefold(), str(item.get("word", ""))))
        self._write_entries(self.user_lexicon_path, user_entries)
        self._invalidate_known_anchor_index()
        return {
            "ok": True,
            "anchor": surface_anchor,
            "hex": new_entry["hex"],
            "symbol": new_entry["symbol"],
            "slots_available": genome_pool.status()["remaining"],
            "action": "added_to_user_lexicon",
            "pack": "user",
            "authority": "user_lexicon",
        }

    def _assign_word(self, word: str, frequency: int = 0) -> dict[str, Any]:
        surface = self.normalize_anchor(word)
        if self._find_entry(surface):
            raise ValueError("word already exists in lexicon")
        genome_pool = SymbolGenomePool(self.symbol_genome_pool_dir)
        allocation = genome_pool.allocate(
            surface,
            authority="user_lexicon",
            category="specialized",
            priority=2,
        )
        user_entries = self._read_entries(self.user_lexicon_path)
        new_entry = self._build_user_lexicon_entry(surface, allocation, frequency=frequency)
        user_entries.append(new_entry)
        user_entries.sort(key=lambda item: (str(item.get("word", "")).casefold(), str(item.get("word", ""))))
        self._write_entries(self.user_lexicon_path, user_entries)
        self._invalidate_known_anchor_index()
        return {
            "ok": True,
            "word": surface,
            "hex": new_entry["hex"],
            "symbol": new_entry["symbol"],
            "slots_available": genome_pool.status()["remaining"],
            "pack": "user",
            "authority": "user_lexicon",
        }

    def assign_pending(self, word: str) -> dict[str, Any]:
        surface = self.normalize_anchor(word)
        with self._lock:
            pending = self._load_pending()
            item = next((entry for entry in pending if entry["word"] == surface), None)
            if item is None:
                raise ValueError("pending word not found")
            result = self._assign_word(surface, frequency=int(item.get("frequency", 0) or 0))
            pending = [entry for entry in pending if entry["word"] != surface]
            self._write_pending(pending)
            return result

    def assign_all_pending(self) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        assigned = 0
        failed = 0
        for item in list(self._load_pending()):
            try:
                result = self.assign_pending(item["word"])
                results.append(result)
                assigned += 1
            except Exception as exc:
                results.append({"ok": False, "word": item["word"], "detail": str(exc)})
                failed += 1
        return {"assigned": assigned, "failed": failed, "results": results}

    def approve_all_unmatched(self) -> dict[str, Any]:
        moved = 0
        for item in list(self._load_unmatched()):
            self.approve_unmatched(item["word"])
            moved += 1
        return {"moved": moved}

    def deny_all_unmatched(self) -> dict[str, Any]:
        denied = 0
        for item in list(self._load_unmatched()):
            self.ignore_word(item["word"])
            denied += 1
        return {"denied": denied}

    def clear_canonical(self) -> dict[str, Any]:
        return {
            "ok": False,
            "locked": True,
            "reason": "canonical_lexicon_is_read_only",
            "purged": 0,
            "slots_reclaimed": 0,
            "slots_available": self._count_available_slots(),
            "pool_available": self._count_available_slots(),
            "moved": 0,
        }

    def return_to_pool(self) -> dict[str, Any]:
        return self.clear_canonical()

    def import_words_dir(self, words_dir: Path) -> dict[str, Any]:
        words_dir = Path(words_dir).expanduser().resolve()
        requested_by_letter: dict[str, list[str]] = {letter: [] for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"}
        frequencies: dict[str, int] = {}
        seen_global: set[str] = set()

        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            path = words_dir / f"verified_{letter}.json"
            if path.exists():
                data = self._read_json(path, [])
                entries: list[tuple[str, int]] = []
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, str):
                            entries.append((item, 0))
                        elif isinstance(item, dict):
                            value = item.get("word") or item.get("display")
                            if value:
                                entries.append((str(value), int(item.get("frequency", item.get("observations", 0)) or 0)))
                seen_letter: set[str] = set()
                for raw_word, frequency in entries:
                    word = self.normalize_anchor(raw_word)
                    if not word or word in seen_letter or word in seen_global:
                        continue
                    seen_letter.add(word)
                    seen_global.add(word)
                    requested_by_letter[letter].append(word)
                    frequencies[word] = int(frequency or 0)

        requested = [word for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" for word in requested_by_letter[letter]]
        result = self.approve_intake_anchors(requested, frequencies=frequencies)
        approved_words = {row.get("word") for row in result.get("approved", [])}
        skipped_words = {row.get("anchor") for row in result.get("skipped", [])}
        failed_words = {row.get("anchor") for row in result.get("failed", [])}
        letters: list[dict[str, Any]] = []
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            words = requested_by_letter[letter]
            letters.append({
                "letter": letter,
                "bound": sum(1 for word in words if word in approved_words),
                "skipped": sum(1 for word in words if word in skipped_words),
                "no_slots": sum(1 for word in words if word in failed_words),
            })

        return {
            "imported": int(result.get("approved_count", 0) or 0),
            "skipped": int(result.get("skipped_count", 0) or 0),
            "no_slots": int(result.get("failed_count", 0) or 0),
            "slots_available": self._count_available_slots(),
            "spare_pool_writes": int(result.get("spare_pool_writes", 0) or 0),
            "lexicon_files_written": int(result.get("lexicon_files_written", 0) or 0),
            "index_reloads": int(result.get("index_reloads", 0) or 0),
            "letters": letters,
        }
