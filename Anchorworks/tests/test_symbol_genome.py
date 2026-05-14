import unittest

from AnchorWorks.symbol_genome import (
    SYMBOL_GENOME_SCHEMA_VERSION,
    generate_symbol_genome_identity,
)


class SymbolGenomeTests(unittest.TestCase):
    def test_symbol_genome_encodes_category_priority_and_hash_payload(self) -> None:
        identity = generate_symbol_genome_identity(
            "newton laws of motion",
            category="specialized",
            priority=2,
        )

        self.assertEqual(identity["schema_version"], SYMBOL_GENOME_SCHEMA_VERSION)
        self.assertEqual(identity["symbol_length_bytes"], 5)
        self.assertEqual(len(identity["symbol_bytes"]), 5)
        self.assertEqual(identity["symbol_bytes"][0], 0x28)
        self.assertTrue(identity["hex"].startswith("0x28"))
        self.assertEqual(len(identity["binary"]), 40)
        self.assertEqual(len(identity["visual_grid"]), 8)
        self.assertTrue(all(len(row) == 8 for row in identity["visual_grid"]))
        self.assertIn("#", identity["visual_rune"])
        self.assertIn(".", identity["visual_rune"])
        self.assertEqual(len(identity["integrity_hash"]), 64)


if __name__ == "__main__":
    unittest.main()
