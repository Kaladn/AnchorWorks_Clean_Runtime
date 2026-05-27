import tempfile
import unittest
from pathlib import Path

from AnchorWorks.four_anchor_unit_counts import (
    build_four_anchor_unit_counts,
    build_four_anchor_units,
    read_four_anchor_unit_counts_binary,
    write_four_anchor_unit_counts_binary,
)
from AnchorWorks.symbol_relation_counts import build_symbol_relation_map


class FourAnchorUnitCountsTests(unittest.TestCase):
    def test_groups_anchor_stream_into_fixed_ordered_units_from_document_start(self):
        result = build_four_anchor_units(list("abcdefghijklmnop"))

        self.assertEqual(result["schema_version"], "anchorworks_four_anchor_units@1")
        self.assertEqual([unit["unit_key"] for unit in result["units"]], ["a b c d", "e f g h", "i j k l", "m n o p"])
        self.assertEqual(result["units"][0]["anchors"], ["a", "b", "c", "d"])
        self.assertEqual(result["units"][3]["anchors"], ["m", "n", "o", "p"])
        self.assertEqual(result["partial_policy"], "drop")
        self.assertEqual(result["partial_tail"], [])

    def test_drops_partial_tail_by_default_and_marks_policy(self):
        result = build_four_anchor_units(["a", "b", "c", "d", "e", "f"])

        self.assertEqual(len(result["units"]), 1)
        self.assertEqual(result["partial_tail"], ["e", "f"])
        self.assertEqual(result["truth_boundary"]["partial_tail_not_counted"], True)

    def test_builds_6_1_6_over_four_anchor_units_without_touching_solo_counts(self):
        anchors = [f"a{i:02d}" for i in range(52)]
        solo_before = build_symbol_relation_map(
            " ".join(anchors),
            symbol_by_anchor={anchor: f"0x{index + 1:010X}" for index, anchor in enumerate(anchors)},
            window_radius=6,
        )

        result = build_four_anchor_unit_counts(anchors, window_radius=6)

        solo_after = build_symbol_relation_map(
            " ".join(anchors),
            symbol_by_anchor={anchor: f"0x{index + 1:010X}" for index, anchor in enumerate(anchors)},
            window_radius=6,
        )
        self.assertEqual(solo_after, solo_before)
        self.assertEqual(result["schema_version"], "anchorworks_four_anchor_unit_counts@1")
        self.assertEqual(result["count_layer"], "four_anchor_unit_sibling")
        self.assertEqual(result["unit_size"], 4)
        self.assertEqual(result["window_shape"], "6-1-6 over unit4")
        self.assertEqual(result["unit_count"], 13)
        self.assertEqual(result["full_window_count"], 1)
        window = result["windows"][0]
        self.assertEqual([unit["unit_index"] for unit in window["left_units"]], [0, 1, 2, 3, 4, 5])
        self.assertEqual(window["center_unit"]["unit_index"], 6)
        self.assertEqual([unit["unit_index"] for unit in window["right_units"]], [7, 8, 9, 10, 11, 12])
        self.assertEqual(window["center_unit"]["anchors"], ["a24", "a25", "a26", "a27"])
        self.assertEqual(result["writes_allowed"], {"solo_counts": False, "unit4_counts": True, "lexicon": False, "lifetime": False})

    def test_binary_round_trip_preserves_unit_relations_as_separate_layer(self):
        anchors = [f"a{i:02d}" for i in range(52)]
        counts = build_four_anchor_unit_counts(anchors, window_radius=6)

        with tempfile.TemporaryDirectory() as tmpdir:
            written = write_four_anchor_unit_counts_binary(root=Path(tmpdir), count_payload=counts, shard_id="unit4")
            loaded = read_four_anchor_unit_counts_binary(written["manifest_path"])

        self.assertEqual(written["schema_version"], "anchorworks_four_anchor_unit_counts_binary_write@1")
        self.assertEqual(loaded["schema_version"], "anchorworks_four_anchor_unit_counts_binary_loaded@1")
        self.assertEqual(loaded["manifest"]["schema_version"], "anchorworks_four_anchor_unit_counts_binary_manifest@1")
        self.assertEqual(loaded["relation_count"], len(counts["relation_counts"]))
        self.assertEqual(loaded["manifest"]["count_layer"], "four_anchor_unit_sibling")
        self.assertEqual(loaded["writes_allowed"], {"solo_counts": False, "unit4_counts": True, "lexicon": False, "lifetime": False})

    def test_contract_doc_locks_sibling_layer_rules(self):
        doc = (Path(__file__).resolve().parents[1] / "docs" / "FOUR_ANCHOR_UNIT_COUNTS_CONTRACT.md").read_text(encoding="utf-8")

        self.assertIn("Do not replace solo counts.", doc)
        self.assertIn("Unit4 stream = fixed ordered groups of 4 anchors.", doc)
        self.assertIn("6-1-6 over unit4", doc)


if __name__ == "__main__":
    unittest.main()
