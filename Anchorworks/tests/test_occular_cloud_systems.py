import unittest

from AnchorWorks.truevision_language.occular_cloud import (
    OccularCloudConfig,
    build_occular_cloud_counts,
    build_video_modality_switch,
    evaluate_trailing_count_status,
)


class OccularCloudSystemsTests(unittest.TestCase):
    def test_builds_6x4_4_6x4_symbol_windows_without_crossing_blocks(self):
        symbols = [f"S{i:02d}" for i in range(60)]

        result = build_occular_cloud_counts(
            blocks=[{"block_id": "page-1", "symbols": symbols}],
            config=OccularCloudConfig(context_clouds_each_side=6, context_cloud_size=4, center_size=4),
        )

        center_key = "S24 S25 S26 S27"
        record = next(row for row in result["records"] if row["center_symbols"] == ["S24", "S25", "S26", "S27"])

        self.assertEqual(result["schema_version"], "anchorworks_occular_cloud_counts@1")
        self.assertEqual(result["config"]["window_shape"], "6x4-4-6x4")
        self.assertEqual(record["center_key"], center_key)
        self.assertEqual(record["left_context_clouds"][0], ["S00", "S01", "S02", "S03"])
        self.assertEqual(record["left_context_clouds"][-1], ["S20", "S21", "S22", "S23"])
        self.assertEqual(record["right_context_clouds"][0], ["S28", "S29", "S30", "S31"])
        self.assertEqual(record["right_context_clouds"][-1], ["S48", "S49", "S50", "S51"])
        self.assertEqual(result["counts"][center_key]["observations"], 1)
        self.assertEqual(result["counts"][center_key]["source_blocks"], ["page-1"])

    def test_rejects_null_unknown_and_string_literal_symbols_from_counts(self):
        result = build_occular_cloud_counts(
            blocks=[
                {
                    "block_id": "page-1",
                    "symbols": [
                        "S00",
                        "S01",
                        "S02",
                        "S03",
                        "__NULL__",
                        "visual_unknown_glyph",
                        "STRING_LITERAL",
                        "S04",
                        "S05",
                    ],
                    "count_eligible": [True, True, True, True, True, True, False, True, True],
                }
            ]
        )

        self.assertEqual(result["records"], [])
        self.assertIn("__NULL__", result["blocked_symbols"])
        self.assertIn("visual_unknown_glyph", result["blocked_symbols"])
        self.assertIn("STRING_LITERAL", result["blocked_symbols"])

    def test_trailing_count_policy_retries_then_stops_with_pickup_cursor(self):
        status = evaluate_trailing_count_status(
            capture_cursor={"source_id": "doc-1", "page_index": 2, "frame_index": 90},
            count_cursor={"source_id": "doc-1", "page_index": 2, "frame_index": 40},
            lag_seconds=61.0,
            max_lag_seconds=15.0,
            retry_index=3,
            max_retries=3,
        )

        self.assertEqual(status["action"], "graceful_stop")
        self.assertEqual(status["reason"], "count_worker_lag_exceeded_retries")
        self.assertEqual(status["pickup_cursor"]["frame_index"], 40)
        self.assertTrue(status["deterministic_resume_required"])

    def test_embedded_video_switches_intake_authority_and_preserves_parent_pickup(self):
        switch = build_video_modality_switch(
            parent_document_id="doc-physics",
            page_index=4,
            region_id="figure-video-2",
            video_ref={"path": "media/demo.mp4", "sha256": "abc123"},
            document_cursor={"page_index": 4, "region_index": 7, "next_region_index": 8},
        )

        self.assertEqual(switch["record_kind"], "anchorworks_occular_video_modality_switch")
        self.assertEqual(switch["intake_authority"], "video")
        self.assertEqual(switch["parent"]["document_id"], "doc-physics")
        self.assertEqual(switch["parent_pickup_cursor"]["next_region_index"], 8)
        self.assertEqual(switch["video_cursor"]["frame_index"], 0)
        self.assertEqual(switch["counts_policy"]["trailing_delay_seconds"], 15)
        self.assertTrue(switch["resume_parent_after_video"])


if __name__ == "__main__":
    unittest.main()
