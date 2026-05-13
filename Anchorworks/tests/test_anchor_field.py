from __future__ import annotations

import unittest

from AnchorWorks.anchor_field import AnchorField, build_anchor_field_from_observed_map, skim_three_level_cloud


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
        self.assertIn("surface", cloud["levels"]["2"])
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


if __name__ == "__main__":
    unittest.main()
