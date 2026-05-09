from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from AnchorWorks.anchor_classification import (
    classify_unknown_anchor,
    classify_unknown_anchor_rows,
    write_math_lexicon,
    write_classified_unknown_report,
)


class AnchorClassificationTests(unittest.TestCase):
    def test_classifies_structural_math_markup_before_word_surface(self) -> None:
        self.assertEqual(classify_unknown_anchor("stretchy")["lane"], "math_markup")
        self.assertEqual(classify_unknown_anchor("mfrac")["lane"], "math_markup")
        self.assertEqual(classify_unknown_anchor("columnalign")["lane"], "source_cleanup_candidates")
        self.assertEqual(classify_unknown_anchor("enumerated")["lane"], "unknown_real_word_candidates")

    def test_classifies_known_abbreviations_as_cleanup_candidates(self) -> None:
        self.assertEqual(classify_unknown_anchor("rques")["expansion"], "review questions")
        self.assertEqual(classify_unknown_anchor("sques")["expansion"], "self check questions")
        self.assertEqual(classify_unknown_anchor("ctques")["expansion"], "critical thinking questions")
        self.assertEqual(classify_unknown_anchor("rques")["lane"], "source_cleanup_candidates")

    def test_classifies_domain_notation_as_companion_authority(self) -> None:
        self.assertEqual(classify_unknown_anchor("sqrt")["expansion"], "square root")
        self.assertEqual(classify_unknown_anchor("gcf")["expansion"], "greatest common factor")
        self.assertEqual(classify_unknown_anchor("csc")["expansion"], "cosecant")
        self.assertEqual(classify_unknown_anchor("hcl")["lane"], "domain_notation_anchors")
        self.assertEqual(classify_unknown_anchor("ln")["lane"], "domain_notation_anchors")
        self.assertEqual(classify_unknown_anchor("csc")["lane"], "domain_notation_anchors")

    def test_classifies_symbols_structural_source_and_media_separately(self) -> None:
        self.assertEqual(classify_unknown_anchor("π")["lane"], "math_terms_or_symbols")
        self.assertEqual(classify_unknown_anchor("−")["lane"], "math_terms_or_symbols")
        self.assertEqual(classify_unknown_anchor("⋅")["lane"], "math_terms_or_symbols")
        self.assertEqual(classify_unknown_anchor("ⓐ")["lane"], "structural_source_anchors")
        self.assertEqual(classify_unknown_anchor("cnxml")["lane"], "structural_source_anchors")
        self.assertEqual(classify_unknown_anchor("jpeg")["lane"], "structural_source_anchors")
        self.assertEqual(classify_unknown_anchor("tbl")["lane"], "structural_source_anchors")
        self.assertEqual(classify_unknown_anchor("ch02mod03_review_questions_problem_01")["lane"], "source_id_artifacts")

    def test_classifies_possessives_and_accented_words_as_real_word_candidates(self) -> None:
        self.assertEqual(classify_unknown_anchor("mendel's")["lane"], "unknown_real_word_candidates")
        self.assertEqual(classify_unknown_anchor("josé")["lane"], "unknown_real_word_candidates")
        self.assertEqual(classify_unknown_anchor("naïve")["lane"], "unknown_real_word_candidates")

    def test_writes_lane_report_without_promoting_lexicon_or_counts(self) -> None:
        rows = [
            {"anchor": "stretchy", "observations": 40},
            {"anchor": "enumerated", "observations": 9},
            {"anchor": "π", "observations": 7},
            {"anchor": "cnxml", "observations": 5},
            {"anchor": "ch02mod03_review_questions_problem_01", "observations": 3},
            {"anchor": "width=\"0.2em\"/><m:mo>×</m:mo>", "observations": 2},
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            result = write_classified_unknown_report(rows, Path(temp_dir))

            self.assertEqual(result["total_unique"], 6)
            self.assertEqual(result["lane_counts"]["math_markup"], 1)
            self.assertEqual(result["lane_counts"]["unknown_real_word_candidates"], 1)
            self.assertEqual(result["lane_counts"]["math_terms_or_symbols"], 1)
            self.assertEqual(result["lane_counts"]["structural_source_anchors"], 1)
            self.assertEqual(result["lane_counts"]["source_id_artifacts"], 1)
            self.assertEqual(result["lane_counts"]["null_symbol_anchors"], 1)
            self.assertEqual(result["writes_allowed"], {"maps": False, "counts": False, "lifetime": False, "lexicon": False})

            summary_path = Path(result["summary_path"])
            self.assertTrue(summary_path.exists())
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary["lane_counts"], result["lane_counts"])

    def test_classify_rows_preserves_observation_totals(self) -> None:
        classified = classify_unknown_anchor_rows([
            {"anchor": "mrow", "observations": 11},
            {"anchor": "wikimedia", "observations": 4},
            {"anchor": "θ", "observations": 3},
        ])

        self.assertEqual(classified["lane_counts"]["math_markup"], 1)
        self.assertEqual(classified["lane_counts"]["unknown_real_word_candidates"], 1)
        self.assertEqual(classified["lane_counts"]["math_terms_or_symbols"], 1)
        self.assertEqual(classified["lane_observations"]["math_markup"], 11)
        self.assertEqual(classified["lane_observations"]["unknown_real_word_candidates"], 4)
        self.assertEqual(classified["lane_observations"]["math_terms_or_symbols"], 3)

    def test_writes_math_lexicon_as_non_canonical_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = write_math_lexicon(Path(temp_dir) / "math_lexicon.json")
            payload = json.loads(Path(result["path"]).read_text(encoding="utf-8"))

            self.assertEqual(payload["schema_version"], "anchorworks_math_lexicon@1")
            self.assertIn("fraction", payload["terms"])
            self.assertIn("π", payload["symbols"])
            self.assertIn("mfrac", payload["markup"])
            self.assertEqual(payload["writes_allowed"], {"maps": False, "counts": False, "lifetime": False, "lexicon": False})


if __name__ == "__main__":
    unittest.main()
