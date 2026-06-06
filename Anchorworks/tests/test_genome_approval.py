import json
import tempfile
import unittest
from pathlib import Path

from AnchorWorks.store import LexiconStore
from AnchorWorks.symbol_genome_pool import SymbolGenomePool, symbol_genome_identity_from_index


class GenomeApprovalTests(unittest.TestCase):
    def test_approve_intake_anchors_allocates_from_genome_pool_without_spare_slots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Canonical").mkdir()
            (root / "Structural").mkdir()
            (root / "Structural" / "structural.json").write_text("[]", encoding="utf-8")
            (root / "Spare_Slots").mkdir()
            (root / "Spare_Slots" / "spare_slots.json").write_text("[]", encoding="utf-8")

            store = LexiconStore(root)
            result = store.approve_intake_anchors(["securecore", "occular"], frequencies={"securecore": 13})

            self.assertTrue(result["ok"])
            self.assertEqual(result["approved_count"], 2)
            self.assertEqual(result["failed_count"], 0)
            self.assertEqual(result["slots_allocated"], 2)
            self.assertEqual(result["symbol_genome_pool"]["assigned_count"], 2)
            self.assertEqual(result["spare_pool_writes"], 0)
            self.assertIn("securecore", store._all_known_anchors())
            symbols = store._canonical_symbol_by_anchor()
            self.assertRegex(symbols["securecore"], r"^0x[0-9A-F]{10}$")
            self.assertRegex(symbols["occular"], r"^0x[0-9A-F]{10}$")
            canonical_s = json.loads((root / "Canonical" / "canonical_S.json").read_text(encoding="utf-8"))
            self.assertEqual(set(canonical_s[0]), {"word", "symbol"})

    def test_observed_unknown_surfaces_get_source_local_symbols_without_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Canonical").mkdir()
            (root / "Structural").mkdir()
            (root / "Structural" / "structural.json").write_text("[]", encoding="utf-8")
            source = root / "odd_source.txt"
            source.write_text("Blorxium columnalign href aques text.", encoding="utf-8")

            result = LexiconStore(root).build_observed_map(source)

            temp_by_word = {row["word"]: row for row in result["temp_symbols"]}
            for anchor in ["blorxium", "columnalign", "href", "aques"]:
                self.assertIn(anchor, temp_by_word)
                self.assertRegex(temp_by_word[anchor]["symbol"], r"^U[0-9A-F]{11}$")
            self.assertEqual(result["character_decomposed_anchor_count"], 0)
            self.assertEqual(result["null_anchor_count"], 0)
            observed = {row["anchor"]: row for row in result["observed_anchors"]}
            self.assertNotEqual(observed["blorxium"]["resolved_to"], "b")
            self.assertNotEqual(observed["href"]["resolved_to"], "__NULL__")

    def test_operator_null_is_still_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Canonical").mkdir()
            (root / "Structural").mkdir()
            (root / "Structural" / "structural.json").write_text("[]", encoding="utf-8")
            source = root / "odd_source.txt"
            source.write_text("Blorxium href.", encoding="utf-8")

            result = LexiconStore(root).build_observed_map(source, null_anchors={"href"})

            observed = {row["anchor"]: row for row in result["observed_anchors"]}
            self.assertEqual(observed["href"]["resolved_to"], "__NULL__")
            self.assertEqual(result["null_anchor_count"], 1)
            self.assertNotIn("href", {row["word"] for row in result["temp_symbols"]})

    def test_symbol_genome_pool_supports_trillion_scale_cursor(self):
        with tempfile.TemporaryDirectory() as tmp:
            pool = SymbolGenomePool(Path(tmp))
            status = pool.status()

            self.assertGreaterEqual(status["capacity"], 1_000_000_000_000)

            identity = symbol_genome_identity_from_index(
                "late-anchor",
                authority="source_local_coordinate",
                allocation_index=1_000_000_000_000 - 1,
            )

            self.assertEqual(identity["symbol_length_bytes"], 5)
            self.assertRegex(identity["hex"], r"^0x[0-9A-F]{10}$")
            self.assertEqual(identity["allocation_index"], 1_000_000_000_000 - 1)


if __name__ == "__main__":
    unittest.main()
