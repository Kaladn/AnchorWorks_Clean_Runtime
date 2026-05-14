from __future__ import annotations

import unittest

from AnchorWorks.visual_dual_path_verification import SourceTextSpan
from AnchorWorks.visual_pps_trial import (
    VisualPageTrialInput,
    run_visual_pps_trial,
    validate_visual_pps_trial_report,
)


class VisualPpsTrialTests(unittest.TestCase):
    def test_pps_trial_reports_throughput_and_quality_without_promotion(self) -> None:
        pages = [
            VisualPageTrialInput.from_text_lines(
                source_id=f"page_{index}",
                source_spans=[
                    SourceTextSpan(span_id=f"p{index}_s1", text="velocity", reading_order=0, region_id="r1"),
                    SourceTextSpan(span_id=f"p{index}_s2", text="time", reading_order=1, region_id="r2"),
                ],
                visual_texts=["velocity", "time"],
            )
            for index in range(5)
        ]

        report = run_visual_pps_trial(pages, elapsed_seconds=0.05).to_dict()
        validate_visual_pps_trial_report(report)

        self.assertEqual(report["page_count"], 5)
        self.assertEqual(report["pages_per_second"], 100.0)
        self.assertEqual(report["mean_agreement_ratio"], 1.0)
        self.assertEqual(report["total_issues"], 0)
        self.assertEqual(report["trial_mode"], "synthetic_dual_path")
        self.assertEqual(
            report["writes_allowed"],
            {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
        )

    def test_pps_trial_aggregates_noisy_visual_candidates(self) -> None:
        pages = [
            VisualPageTrialInput.from_text_lines(
                source_id="page_clean",
                source_spans=[SourceTextSpan(span_id="s1", text="alpha", reading_order=0, region_id="r1")],
                visual_texts=["alpha"],
            ),
            VisualPageTrialInput.from_text_lines(
                source_id="page_noisy",
                source_spans=[
                    SourceTextSpan(span_id="s2", text="beta", reading_order=0, region_id="r1"),
                    SourceTextSpan(span_id="s3", text="gamma", reading_order=1, region_id="r2"),
                ],
                visual_texts=["beta", "gar8age"],
                confidences=[0.96, 0.33],
            ),
        ]

        report = run_visual_pps_trial(pages, elapsed_seconds=0.02).to_dict()
        validate_visual_pps_trial_report(report)

        self.assertEqual(report["page_count"], 2)
        self.assertEqual(report["pages_per_second"], 100.0)
        self.assertEqual(report["exact_match_total"], 2)
        self.assertEqual(report["source_span_total"], 3)
        self.assertEqual(report["total_issues"], 3)
        self.assertLess(report["mean_agreement_ratio"], 1.0)


if __name__ == "__main__":
    unittest.main()
