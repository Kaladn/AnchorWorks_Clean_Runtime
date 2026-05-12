from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from AnchorWorks.store import LexiconStore
from AnchorWorks.store_modules.admin import AdminStore
from AnchorWorks.store_modules.authority import AuthorityStore
from AnchorWorks.store_modules.evidence import EvidenceStore
from AnchorWorks.store_modules.intake import IntakeStore
from AnchorWorks.store_modules.memory import MemoryStore
from AnchorWorks.store_modules.paths import StorePaths, anchor_maps_root_for
from AnchorWorks.store_modules.visual import VisualStore


class StoreModulePathTests(unittest.TestCase):
    def test_store_paths_match_lexicon_store_public_paths(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            data_root = Path(root) / "Anchorworks"
            expected = StorePaths(data_root)
            store = LexiconStore(data_root)

            self.assertEqual(store.paths.root, expected.root)
            self.assertEqual(store.canonical_dir, expected.canonical_dir)
            self.assertEqual(store.observed_maps_dir, expected.observed_maps_dir)
            self.assertEqual(store.symbolic_maps_dir, expected.symbolic_maps_dir)
            self.assertEqual(store.symbol_counts_binary_dir, expected.symbol_counts_binary_dir)
            self.assertEqual(store.flat_documents_symbolic_dir, expected.flat_documents_symbolic_dir)
            self.assertTrue(store.symbolic_maps_dir.exists())
            self.assertTrue(store.flat_documents_occurrence_index_dir.exists())

    def test_anchor_maps_root_can_be_configured_externally(self) -> None:
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as maps:
            old_value = os.environ.get("ANCHORWORKS_MAP_ROOT")
            os.environ["ANCHORWORKS_MAP_ROOT"] = maps
            try:
                resolved = anchor_maps_root_for(Path(root) / "Anchorworks")
                self.assertEqual(resolved, Path(maps).resolve())
            finally:
                if old_value is None:
                    os.environ.pop("ANCHORWORKS_MAP_ROOT", None)
                else:
                    os.environ["ANCHORWORKS_MAP_ROOT"] = old_value

    def test_lexicon_store_exposes_imported_power_modules(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            store = LexiconStore(Path(root) / "Anchorworks")

            self.assertIsInstance(store.authority, AuthorityStore)
            self.assertIsInstance(store.evidence, EvidenceStore)
            self.assertIsInstance(store.memory, MemoryStore)
            self.assertIsInstance(store.intake_power, IntakeStore)
            self.assertIsInstance(store.visual, VisualStore)
            self.assertIsInstance(store.admin, AdminStore)

            self.assertIs(store.authority.facade, store)
            self.assertIs(store.evidence.facade, store)


if __name__ == "__main__":
    unittest.main()
