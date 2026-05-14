from __future__ import annotations

import unittest

from AnchorWorks.visual_glyph_lexicon import GlyphMatch, VisualGlyphLexicon, normalize_trim_pattern


class VisualGlyphLexiconTests(unittest.TestCase):
    def test_exact_pattern_match_names_mark(self) -> None:
        lexicon = VisualGlyphLexicon.from_records(
            [
                {
                    "schema_version": "anchorworks_visual_glyph_lexicon@1",
                    "glyph_id": "vglyph_A_0001",
                    "display": "A",
                    "class": "letter_upper",
                    "width": 5,
                    "height": 7,
                    "trim_pattern": [
                        "01110",
                        "10001",
                        "10001",
                        "11111",
                        "10001",
                        "10001",
                        "10001",
                    ],
                    "match_policy": {"max_hamming_distance": 0},
                    "promotion_status": "approved",
                }
            ]
        )
        match = lexicon.match(
            [
                "01110",
                "10001",
                "10001",
                "11111",
                "10001",
                "10001",
                "10001",
            ]
        )
        self.assertEqual(match, GlyphMatch("vglyph_A_0001", "A", 1.0, "exact"))

    def test_unknown_pattern_does_not_become_text(self) -> None:
        lexicon = VisualGlyphLexicon.from_records([])
        match = lexicon.match(["1"])
        self.assertEqual(match.display, "visual_unknown_glyph")
        self.assertEqual(match.confidence, 0.0)
        self.assertEqual(match.match_type, "unknown")

    def test_normalize_trim_pattern_removes_empty_border(self) -> None:
        self.assertEqual(normalize_trim_pattern(["0000", "0110", "0110", "0000"]), ("11", "11"))


if __name__ == "__main__":
    unittest.main()

