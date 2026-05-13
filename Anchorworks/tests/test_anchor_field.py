from __future__ import annotations

import unittest

from AnchorWorks.anchor_field import (
    AnchorField,
    build_anchor_field_from_observed_map,
    build_query_frame,
    skim_three_level_cloud,
)


class AnchorFieldTests(unittest.TestCase):
    def test_builds_in_memory_field_from_observed_map_paragraph_stream(self) -> None:
        observed_map = {
            "source_name": "toy",
            "window_radius": 2,
            "paragraphs": [
                {
                    "paragraph_id": 0,
                    "anchors": ["how", "sear", "meat", "hot", "pan", "sear", "surface"],
                }
            ],
        }
        field = build_anchor_field_from_observed_map(observed_map)
        self.assertEqual(field.source_name, "toy")
        self.assertEqual(field.anchor_count, 7)
        self.assertEqual(field.positions_for("sear"), [1, 5])

    def test_three_level_cloud_expands_from_seed_without_whole_map_runtime(self) -> None:
        field = AnchorField(
            source_name="toy",
            window_radius=2,
            stream=["how", "sear", "meat", "hot", "pan", "sear", "surface"],
            positions=[
                {"paragraph_id": 0, "position": index, "anchor": anchor}
                for index, anchor in enumerate(["how", "sear", "meat", "hot", "pan", "sear", "surface"])
            ],
        )
        cloud = skim_three_level_cloud(field, ["sear"], max_level_width=4)
        self.assertEqual(cloud["schema_version"], "anchorworks_anchor_field_cloud@1")
        self.assertEqual(cloud["seed_anchors"], ["sear"])
        self.assertIn("meat", cloud["levels"]["1"])
        self.assertIn("pan", cloud["levels"]["1"])
        self.assertIn("surface", cloud["levels"]["1"])
        self.assertLessEqual(len(cloud["levels"]["3"]), 4)
        self.assertGreater(cloud["shape"]["non_null_ratio"], 0.0)

    def test_null_heavy_surface_does_not_expand_deeply(self) -> None:
        field = AnchorField(
            source_name="toy",
            window_radius=2,
            stream=["seed", "__NULL__", "__NULL__", "__NULL__", "meat"],
            positions=[
                {"paragraph_id": 0, "position": index, "anchor": anchor}
                for index, anchor in enumerate(["seed", "__NULL__", "__NULL__", "__NULL__", "meat"])
            ],
        )
        cloud = skim_three_level_cloud(field, ["seed"], max_level_width=4, null_stop_ratio=0.5)
        self.assertEqual(cloud["stop_reason"], "null_heavy_surface")
        self.assertEqual(cloud["levels"]["2"], [])

    def test_query_frame_keeps_directors_out_of_content_seed(self) -> None:
        frame = build_query_frame(["how", "do", "i", "sear", "meat"])
        self.assertEqual(frame["frame"], "method_question")
        self.assertEqual(frame["content_seeds"], ["sear", "meat"])
        self.assertEqual(
            [(row["anchor"], row["role"]) for row in frame["director_anchors"]],
            [
                ("how", "question_method"),
                ("do", "auxiliary"),
                ("i", "speaker_subject"),
            ],
        )

    def test_role_aware_cloud_blocks_glue_as_content_but_traces_it(self) -> None:
        field = AnchorField(
            source_name="toy",
            window_radius=2,
            stream=["how", "do", "i", "sear", "meat", "with", "pan", "the", "surface"],
            positions=[
                {"paragraph_id": 0, "position": index, "anchor": anchor}
                for index, anchor in enumerate(["how", "do", "i", "sear", "meat", "with", "pan", "the", "surface"])
            ],
        )
        frame = build_query_frame(["how", "do", "i", "sear", "meat"])
        cloud = skim_three_level_cloud(field, frame["content_seeds"], query_frame=frame, max_level_width=6)
        self.assertIn("pan", cloud["levels"]["1"])
        self.assertNotIn("with", cloud["levels"]["1"])
        self.assertNotIn("the", cloud["levels"]["2"])
        self.assertIn("with", cloud["blocked_as_content"])
        self.assertEqual(cloud["query_frame"]["frame"], "method_question")


if __name__ == "__main__":
    unittest.main()
