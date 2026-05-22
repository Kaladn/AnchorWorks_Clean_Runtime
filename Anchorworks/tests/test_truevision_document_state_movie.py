import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from AnchorWorks.truevision_language.intake import ingest_glyph_pattern_frame
from AnchorWorks.truevision_language.state import (
    extract_black_glyph_patterns_from_state_movie,
    record_document_state_movie,
)
from AnchorWorks.visual_glyph_lexicon import VisualGlyphLexicon


def glyph_record(char: str, pattern: list[str]) -> dict[str, object]:
    return {
        "glyph_id": f"glyph-{ord(char)}",
        "display": char,
        "trim_pattern": pattern,
        "promotion_status": "approved",
    }


class TrueVisionDocumentStateMovieTests(unittest.TestCase):
    def test_document_page_records_three_state_frames_and_extracts_glyphs_from_state_only(self):
        h = ["10", "11", "10"]
        i = ["1", "1", "1"]
        q = ["111", "001", "010"]
        page = _page_from_patterns([h, i, q], height=7, width=16)

        with tempfile.TemporaryDirectory() as tmpdir:
            result = record_document_state_movie(
                source_id="doc-1",
                page_frames=[page],
                output_root=Path(tmpdir),
                run_id="doc-state-test",
                frames_per_page=3,
                fps=3.0,
                grid_shape=(7, 16),
            )
            manifest = json.loads(Path(result["manifest_json"]).read_text(encoding="utf-8"))
            records = Path(result["records_jsonl"]).read_text(encoding="utf-8").splitlines()

            self.assertEqual(manifest["config"]["source_kind"], "document_pages_as_state_movie")
            self.assertEqual(manifest["config"]["frames_per_page"], 3)
            self.assertEqual(manifest["records"]["frame_count"], 3)
            self.assertEqual(len(records), 3)
            self.assertEqual(manifest["cell_state"]["chunks"][0]["shape"], [3, 7, 16, 16])
            self.assertTrue(manifest["boundary"]["raw_frame_saved"] is False)
            self.assertEqual(manifest["frame_pages"], [{"frame_start": 0, "frame_end": 2, "page_index": 0, "page_number": 1}])

            patterns = extract_black_glyph_patterns_from_state_movie(
                manifest_path=Path(result["manifest_json"]),
                frame_index=0,
                luma_threshold=128.0,
            )
            self.assertEqual([row["pattern"] for row in patterns], [h, i, q])

            lexicon = VisualGlyphLexicon.from_records([
                glyph_record("h", h),
                glyph_record("i", i),
                glyph_record("?", q),
            ])
            ingested = ingest_glyph_pattern_frame(
                source_id="doc-1",
                frame_id="doc-state-test:frame:0",
                glyph_inputs=[
                    {"pattern": row["pattern"], "bbox": row["bbox"], "order": row["order"]}
                    for row in patterns
                ],
                glyph_lexicon=lexicon,
            )

            self.assertEqual(ingested["packet"]["ordered_symbols"], ["hi", "?"])
            self.assertEqual(ingested["transform"]["content_symbols"], ["hi"])
            self.assertEqual(ingested["transform"]["punctuation_symbols"], ["?"])
            self.assertTrue(ingested["truth_boundary"]["state_recorded_not_copied"])


def _page_from_patterns(patterns: list[list[str]], *, height: int, width: int) -> np.ndarray:
    page = np.full((height, width, 3), 255, dtype=np.uint8)
    cursor = 1
    for pattern in patterns:
        for y, row in enumerate(pattern):
            for x, value in enumerate(row):
                if value == "1":
                    page[y + 2, cursor + x] = [0, 0, 0]
        cursor += max(len(row) for row in pattern) + 2
    return page


if __name__ == "__main__":
    unittest.main()
