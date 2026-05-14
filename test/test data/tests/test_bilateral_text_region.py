from __future__ import annotations

import unittest

from AnchorWorks.bilateral_text_region import (
    BILATERAL_TEXT_REGION_CONTRACT_VERSION,
    build_bilateral_text_region,
    validate_bilateral_text_region,
)


class BilateralTextRegionTests(unittest.TestCase):
    def test_exact_agreement_keeps_source_authority_and_visual_witness(self) -> None:
        record = build_bilateral_text_region(
            page_id="page_1",
            visual_record_id="visual_1",
            region_id="r1",
            source_text="Photosynthesis converts light energy.",
            source_span_id="s1",
            source_reading_order=3,
            visual_text="photosynthesis converts light energy",
            visual_candidate_id="vc1",
            visual_confidence=0.98,
        ).to_dict()

        validate_bilateral_text_region(record)
        self.assertEqual(record["schema_version"], BILATERAL_TEXT_REGION_CONTRACT_VERSION)
        self.assertEqual(record["agreement"]["status"], "exact")
        self.assertEqual(record["agreement"]["score"], 1.0)
        self.assertTrue(record["source_text"]["permissions"]["may_feed_text_intake"])
        self.assertTrue(record["source_text"]["permissions"]["may_feed_maps"])
        self.assertTrue(record["source_text"]["permissions"]["may_speak"])
        self.assertFalse(record["visual_text"]["permissions"]["may_feed_text_intake"])
        self.assertTrue(record["visual_text"]["permissions"]["may_rescue"])
        self.assertTrue(record["visual_text"]["permissions"]["may_audit"])
        self.assertEqual(
            record["writes_allowed"],
            {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
        )

    def test_missing_source_creates_visual_rescue_candidate(self) -> None:
        record = build_bilateral_text_region(
            page_id="page_1",
            visual_record_id="visual_1",
            region_id="r2",
            source_text=None,
            visual_text="orphan visual text",
            visual_candidate_id="vc2",
            visual_confidence=0.91,
        ).to_dict()

        validate_bilateral_text_region(record)
        self.assertEqual(record["agreement"]["status"], "visual_rescue_candidate")
        self.assertEqual(record["source_text"]["text"], "")
        self.assertEqual(record["visual_text"]["permissions"]["may_feed_maps"], "source_local_candidate")
        self.assertFalse(record["visual_text"]["permissions"]["may_speak"])
        self.assertFalse(record["visual_text"]["permissions"]["may_feed_lifetime"])

    def test_conflict_blocks_promotion_and_preserves_both_sides(self) -> None:
        record = build_bilateral_text_region(
            page_id="page_1",
            visual_record_id="visual_1",
            region_id="r3",
            source_text="mass",
            source_span_id="s3",
            visual_text="velocity",
            visual_candidate_id="vc3",
            visual_confidence=0.87,
        ).to_dict()

        validate_bilateral_text_region(record)
        self.assertEqual(record["agreement"]["status"], "conflict")
        self.assertEqual(record["source_text"]["text"], "mass")
        self.assertEqual(record["visual_text"]["text"], "velocity")
        self.assertEqual(record["approval_status"], "candidate")
        self.assertIn("Disagreement creates evidence, not truth.", record["notes"])


if __name__ == "__main__":
    unittest.main()
