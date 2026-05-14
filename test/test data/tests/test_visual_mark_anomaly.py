from __future__ import annotations

import unittest

from AnchorWorks.visual_mark_anomaly import MarkComponent, detect_visual_mark_anomalies


class VisualMarkAnomalyTests(unittest.TestCase):
    def test_unknown_glyph_is_blocking_anomaly(self) -> None:
        anomalies = detect_visual_mark_anomalies(
            [
                MarkComponent(
                    component_id="c1",
                    bounds=(0, 0, 5, 7),
                    pattern=("1",),
                    display="visual_unknown_glyph",
                    confidence=0.0,
                )
            ]
        )
        self.assertEqual(anomalies[0]["kind"], "visual_unknown_glyph")
        self.assertTrue(anomalies[0]["blocking"])

    def test_overlapping_components_are_anomalies(self) -> None:
        anomalies = detect_visual_mark_anomalies(
            [
                MarkComponent("c1", (0, 0, 5, 7), ("1",), "A", 1.0),
                MarkComponent("c2", (4, 0, 9, 7), ("1",), "B", 1.0),
            ]
        )
        self.assertEqual(anomalies[0]["kind"], "component_overlap")
        self.assertTrue(anomalies[0]["blocking"])

    def test_spacing_outlier_is_anomaly_but_not_identity(self) -> None:
        anomalies = detect_visual_mark_anomalies(
            [
                MarkComponent("c1", (0, 0, 5, 7), ("1",), "A", 1.0),
                MarkComponent("c2", (80, 0, 85, 7), ("1",), "B", 1.0),
            ],
            expected_word_gap_pixels=8,
            max_word_gap_multiplier=4,
        )
        self.assertEqual(anomalies[0]["kind"], "spacing_anomaly")
        self.assertFalse(anomalies[0]["blocking"])

    def test_clean_components_have_no_anomalies(self) -> None:
        anomalies = detect_visual_mark_anomalies(
            [
                MarkComponent("c1", (0, 0, 5, 7), ("1",), "A", 1.0),
                MarkComponent("c2", (8, 0, 13, 7), ("1",), "B", 1.0),
            ]
        )
        self.assertEqual(anomalies, [])


if __name__ == "__main__":
    unittest.main()

