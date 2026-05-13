from __future__ import annotations

import unittest

from AnchorWorks.visual_black_pixel_reconstruction import reconstruct_from_known_components
from AnchorWorks.visual_glyph_lexicon import VisualGlyphLexicon


def _one_pixel_record(display: str) -> dict[str, object]:
    return {
        "schema_version": "anchorworks_visual_glyph_lexicon@1",
        "glyph_id": f"vglyph_{display}_0001",
        "display": display,
        "class": "controlled",
        "width": 1,
        "height": 1,
        "trim_pattern": ["1"],
        "match_policy": {"max_hamming_distance": 0},
        "promotion_status": "approved",
    }


class VisualBlackPixelReconstructionTests(unittest.TestCase):
    def test_reconstructs_ordered_text_from_known_components(self) -> None:
        lexicon = VisualGlyphLexicon.from_records([_one_pixel_record("A")])
        result = reconstruct_from_known_components(
            lexicon,
            [
                {"component_id": "c1", "bounds": (0, 0, 1, 1), "pattern": ["1"]},
                {"component_id": "c2", "bounds": (3, 0, 4, 1), "pattern": ["1"]},
            ],
            word_gap_pixels=2,
        )
        self.assertEqual(result["text_candidate"], "A A")
        self.assertEqual(result["unknown_glyphs"], 0)
        self.assertEqual(result["blocking_anomalies"], 0)

    def test_unknown_glyph_blocks_text_candidate(self) -> None:
        result = reconstruct_from_known_components(
            VisualGlyphLexicon.from_records([]),
            [{"component_id": "c1", "bounds": (0, 0, 1, 1), "pattern": ["1"]}],
            word_gap_pixels=2,
        )
        self.assertEqual(result["text_candidate"], "")
        self.assertEqual(result["unknown_glyphs"], 1)
        self.assertEqual(result["blocking_anomalies"], 1)
        self.assertEqual(result["resolved_anchor"], "__NULL__")
        self.assertFalse(result["count_eligible"])


if __name__ == "__main__":
    unittest.main()
