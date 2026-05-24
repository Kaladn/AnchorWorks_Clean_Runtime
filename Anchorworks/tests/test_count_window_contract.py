import unittest

from AnchorWorks.count_window import CountWindowConfig, count_window_preset
from AnchorWorks.truevision_language.occular_cloud import OccularCloudConfig, build_occular_cloud_counts


class CountWindowContractTests(unittest.TestCase):
    def test_presets_name_scalar_and_occular_base_windows(self):
        scalar = count_window_preset("text_6_1_6")
        occular = count_window_preset("occular_6x4_4_6x4")

        self.assertEqual(scalar.window_shape, "6-1-6")
        self.assertEqual(occular.window_shape, "6x4-4-6x4")
        self.assertEqual(occular.context_span_each_side, 24)
        self.assertEqual(occular.total_window_symbols, 52)
        self.assertTrue(occular.configurable)

    def test_rejects_invalid_window_dimensions(self):
        with self.assertRaises(ValueError):
            CountWindowConfig(left_context_units=0, center_units=1, right_context_units=1, unit_size=1)
        with self.assertRaises(ValueError):
            CountWindowConfig(left_context_units=6, center_units=0, right_context_units=6, unit_size=1)
        with self.assertRaises(ValueError):
            CountWindowConfig(left_context_units=6, center_units=1, right_context_units=6, unit_size=0)

    def test_occular_config_can_be_built_from_window_contract(self):
        contract = CountWindowConfig(left_context_units=2, center_units=3, right_context_units=2, unit_size=5)
        occular = OccularCloudConfig.from_window_contract(contract)

        self.assertEqual(occular.window_shape, "2x5-3-2x5")
        self.assertEqual(occular.context_span_each_side, 10)

    def test_different_window_contract_changes_count_shape_without_mutating_authority(self):
        symbols = [f"S{i:02d}" for i in range(40)]
        base = build_occular_cloud_counts(
            blocks=[{"block_id": "visual-1", "symbols": symbols}],
            config=OccularCloudConfig.from_window_contract(count_window_preset("occular_6x4_4_6x4")),
        )
        compact = build_occular_cloud_counts(
            blocks=[{"block_id": "visual-1", "symbols": symbols}],
            config=OccularCloudConfig.from_window_contract(
                CountWindowConfig(left_context_units=2, center_units=2, right_context_units=2, unit_size=3)
            ),
        )

        self.assertEqual(base["config"]["window_shape"], "6x4-4-6x4")
        self.assertEqual(compact["config"]["window_shape"], "2x3-2-2x3")
        self.assertGreater(compact["record_count"], base["record_count"])
        self.assertEqual(compact["writes_allowed"], {"maps": False, "counts": False, "lifetime": False, "lexicon": False})
        self.assertEqual(compact["window_contract"]["total_window_symbols"], 14)


if __name__ == "__main__":
    unittest.main()
