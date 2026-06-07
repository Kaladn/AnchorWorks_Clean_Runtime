from __future__ import annotations

from ..store_support import *


class StateMixin:
    def _ensure_state_file(self, path: Path, default: Any) -> None:
        if not path.exists():
            path.write_text(json.dumps(default, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def _write_json(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def user_storage_status(self) -> dict[str, Any]:
        directories = {
            "user_lexicon": self.user_lexicon_dir,
            "user_counts": self.user_counts_dir,
            "chat_logs": self.chat_logs_dir,
            "ingest_staging": self.ingest_staging_dir,
            "rejected_or_literal_clusters": self.rejected_or_literal_clusters_dir,
        }
        files = {
            "user_lexicon": self.user_lexicon_path,
            "ingest_staging_manifest": self.ingest_staging_manifest_path,
            "rejected_or_literal_clusters": self.rejected_or_literal_clusters_path,
        }
        return {
            "ok": True,
            "root": str(self.user_state_dir),
            "directories": [
                {"name": name, "path": str(path), "exists": path.is_dir()}
                for name, path in directories.items()
            ],
            "files": [
                {
                    "name": name,
                    "path": str(path),
                    "exists": path.is_file(),
                    "size_bytes": path.stat().st_size if path.exists() else 0,
                }
                for name, path in files.items()
            ],
            "protected_paths": {
                "main_lexicon": str(self.canonical_dir),
                "canonical_binary_counts": str(self.canonical_symbol_counts_binary_dir),
                "active_user_binary_counts": str(self.symbol_counts_binary_dir),
            },
        }

    def _read_entries(self, path: Path) -> list[dict[str, Any]]:
        data = self._read_json(path, [])
        return data if isinstance(data, list) else []

    def _write_entries(self, path: Path, entries: list[dict[str, Any]]) -> None:
        self._write_json(path, entries)

    def _invalidate_known_anchor_index(self) -> None:
        self._known_anchor_index = None
        self._canonical_anchor_index = None
        self._canonical_symbol_index = None
        self._known_anchor_spell_index = None

    def _invalidate_spare_entries_cache(self) -> None:
        self._spare_entries_cache = None
        self._spare_entries_cache_key = None

    def normalize_word(self, word: str) -> str:
        return str(word or "").strip().lower()

    def normalize_anchor(self, word: str) -> str:
        anchor = str(word or "").strip()
        if anchor == EMOJI_ANCHOR:
            return EMOJI_ANCHOR
        return anchor.lower()

    def _letter_for_word(self, word: str) -> str:
        for char in self.normalize_anchor(word):
            if char.isalpha():
                return char.upper()
        return "A"

    def _archived_spare_paths(self) -> list[Path]:
        return [path for path in (self.spare_dir / f"pool_{letter}.json" for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ") if path.exists()]

    def _active_spare_paths(self) -> list[Path]:
        if self.spare_slots_path.exists():
            return [self.spare_slots_path]
        archived_paths = self._archived_spare_paths()
        if archived_paths:
            return archived_paths
        return [self.spare_slots_path]

    def _spare_entries_cache_signature(self, paths: list[Path]) -> tuple[tuple[str, int | None, int | None], ...]:
        signature: list[tuple[str, int | None, int | None]] = []
        for path in paths:
            if path.exists():
                stat = path.stat()
                signature.append((str(path), stat.st_mtime_ns, stat.st_size))
            else:
                signature.append((str(path), None, None))
        return tuple(signature)

    def _read_spare_entries(self) -> list[dict[str, Any]]:
        paths = self._active_spare_paths()
        signature = self._spare_entries_cache_signature(paths)
        if self._spare_entries_cache is not None and self._spare_entries_cache_key == signature:
            return list(self._spare_entries_cache)

        entries: list[dict[str, Any]] = []
        for path in paths:
            entries.extend(self._read_entries(path))
        self._spare_entries_cache = list(entries)
        self._spare_entries_cache_key = signature
        return entries

    def _write_spare_entries(self, entries: list[dict[str, Any]]) -> None:
        self._write_entries(self.spare_slots_path, entries)
        self._spare_entries_cache = list(entries)
        self._spare_entries_cache_key = self._spare_entries_cache_signature([self.spare_slots_path])
