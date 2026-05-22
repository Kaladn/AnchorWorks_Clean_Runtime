import unittest

from AnchorWorks.truevision_language import (
    build_glyph_state_record,
    build_language_state_packet,
    build_textual_cloud_record,
)


class TrueVisionLanguageContractsTests(unittest.TestCase):
    def test_glyph_state_packet_and_cloud_preserve_state_boundary(self):
        glyph = build_glyph_state_record(
            source_id="source-1",
            frame_id="frame-1",
            glyph_id="glyph-1",
            glyph_symbol="a",
            bbox={"x": 1, "y": 2, "w": 3, "h": 4},
            confidence=0.99,
            state_hash="hash-glyph-1",
        )
        packet = build_language_state_packet(
            source_id="source-1",
            frame_id="frame-1",
            glyph_records=[glyph],
            ordered_symbols=["a"],
            packet_hash="hash-packet-1",
        )
        cloud = build_textual_cloud_record(
            packet=packet,
            cloud_terms=["anchor"],
            cloud_edges=[{"from": "a", "to": "anchor", "kind": "glyph_to_anchor"}],
        )

        self.assertTrue(glyph["state_recorded_not_copied"])
        self.assertTrue(packet["state_recorded_not_copied"])
        self.assertTrue(cloud["state_recorded_not_copied"])
        self.assertEqual(packet["glyph_record_refs"], ["glyph-1"])
        self.assertEqual(packet["ordered_symbols"], ["a"])
        self.assertTrue(packet["render_allowed"])
        self.assertEqual(cloud["language_state_packet_ref"], "hash-packet-1")
        self.assertTrue(cloud["truth_boundary"]["cloud_is_not_fact_authority"])


if __name__ == "__main__":
    unittest.main()
