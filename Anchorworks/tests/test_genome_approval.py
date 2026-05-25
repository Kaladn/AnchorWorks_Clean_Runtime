import json
import tempfile
import unittest
from pathlib import Path

from AnchorWorks.store import LexiconStore


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


if __name__ == "__main__":
    unittest.main()
