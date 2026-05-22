import unittest

from AnchorWorks.truevision_language.intake import ingest_glyph_pattern_frame
from AnchorWorks.visual_glyph_lexicon import VisualGlyphLexicon


def glyph_record(char: str, pattern: list[str]) -> dict[str, object]:
    return {
        "glyph_id": f"glyph-{ord(char)}",
        "display": char,
        "trim_pattern": pattern,
        "promotion_status": "approved",
    }


class TrueVisionLanguageIngestTests(unittest.TestCase):
    def test_visual_glyph_ingest_applies_render_transform_rules(self):
        patterns = {
            "w": ["101", "111", "101"],
            "h": ["10", "11", "10", "10"],
            "a": ["01", "11", "10"],
            "t": ["111", "010", "010"],
            " ": ["0"],
            "i": ["1", "1"],
            "s": ["11", "10", "01", "11"],
            "m": ["101", "111", "101", "101"],
            "o": ["11", "11"],
            "n": ["10", "11", "10"],
            "r": ["11", "10", "10"],
            "c": ["11", "10", "10", "11"],
            "k": ["01", "11", "10", "01"],
            "?": ["111", "001", "010"],
        }
        lexicon = VisualGlyphLexicon.from_records([
            glyph_record(char, pattern) for char, pattern in patterns.items()
        ])
        glyph_inputs = [
            {"pattern": patterns[char], "bbox": {"x": index * 4, "y": 0, "w": 3, "h": 4}}
            for index, char in enumerate("what is moon rocks?")
        ]

        result = ingest_glyph_pattern_frame(
            source_id="source-moon",
            frame_id="frame-1",
            glyph_inputs=glyph_inputs,
            glyph_lexicon=lexicon,
        )

        self.assertEqual(result["packet"]["ordered_symbols"], ["what", "is", "moon", "rocks", "?"])
        self.assertEqual(result["transform"]["content_symbols"], ["moon", "rocks"])
        self.assertEqual(result["transform"]["punctuation_symbols"], ["?"])
        self.assertEqual(
            [row["anchor"] for row in result["transform"]["director_symbols"]],
            ["what", "is", "?"],
        )
        self.assertEqual(result["cloud"]["cloud_terms"], ["moon", "rocks"])
        self.assertTrue(result["cloud"]["render_allowed"])
        self.assertTrue(result["truth_boundary"]["state_recorded_not_copied"])
        self.assertTrue(result["truth_boundary"]["transform_rules_from_renderer"])

    def test_unknown_glyph_blocks_render_until_state_is_named(self):
        lexicon = VisualGlyphLexicon.from_records([
            glyph_record("z", ["11", "01", "10", "11"]),
        ])

        result = ingest_glyph_pattern_frame(
            source_id="source-unknown",
            frame_id="frame-1",
            glyph_inputs=[
                {"pattern": ["11", "01", "10", "11"], "bbox": {"x": 0, "y": 0, "w": 3, "h": 4}},
                {"pattern": ["101", "010", "101"], "bbox": {"x": 4, "y": 0, "w": 3, "h": 4}},
            ],
            glyph_lexicon=lexicon,
        )

        self.assertIn("visual_unknown_glyph", result["unknown_glyphs"])
        self.assertFalse(result["packet"]["render_allowed"])
        self.assertFalse(result["cloud"]["render_allowed"])
        self.assertEqual(result["transform"]["content_symbols"], ["z"])


if __name__ == "__main__":
    unittest.main()
