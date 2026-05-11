from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from AnchorWorks.symbolic_map_binary import (
    HEADER_SIZE,
    MAGIC,
    RELATION_ROW_SIZE,
    SymbolicMapRelation,
    read_symbolic_map_bundle,
    read_symbolic_map_locator_sidecar,
    read_symbolic_map_null_sidecar,
    read_symbolic_map_visual_sidecar,
    read_symbolic_map_binary,
    write_symbolic_map_locator_sidecar,
    write_symbolic_map_null_sidecar,
    write_symbolic_map_visual_sidecar,
    write_symbolic_map_binary,
)


class SymbolicMapBinaryTests(unittest.TestCase):
    def test_round_trip_symbolic_map_binary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.awsm"
            write_symbolic_map_binary(
                path,
                metadata={
                    "source_name": "sample.md",
                    "source_hash": "abc",
                    "paragraph_count": 2,
                    "anchor_observations": 5,
                },
                relations=[
                    SymbolicMapRelation(1, 2, 1, 0, 0, 7),
                    SymbolicMapRelation(1, 3, -2, 4, 16, 5),
                ],
            )

            raw = path.read_bytes()
            loaded = read_symbolic_map_binary(path)

            self.assertEqual(raw[:4], MAGIC)
            self.assertEqual(HEADER_SIZE, 64)
            self.assertEqual(RELATION_ROW_SIZE, 24)
            self.assertEqual(loaded.metadata["source_name"], "sample.md")
            self.assertEqual(loaded.relation_count, 2)
            self.assertEqual(loaded.relations[1].neighbor_symbol_id, 3)
            self.assertEqual(loaded.relations[1].offset, -2)
            self.assertEqual(loaded.relations[1].lane, 4)
            self.assertEqual(loaded.relations[1].flags, 16)
            self.assertEqual(loaded.relations[1].count, 5)

    def test_crc_rejects_corrupted_relation_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.awsm"
            write_symbolic_map_binary(
                path,
                metadata={"source_name": "sample.md"},
                relations=[SymbolicMapRelation(1, 2, 1, 0, 0, 7)],
            )
            raw = bytearray(path.read_bytes())
            raw[-1] ^= 0x01
            path.write_bytes(raw)

            with self.assertRaises(ValueError):
                read_symbolic_map_binary(path)

    def test_round_trip_block_line_locator_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.locators.awsl"
            rows = [
                {
                    "paragraph_id": 0,
                    "block_id": 0,
                    "line_start": 1,
                    "line_end": 2,
                    "anchor_count": 3,
                    "countable_anchor_count": 2,
                },
                {
                    "paragraph_id": 1,
                    "block_id": 1,
                    "line_start": 4,
                    "line_end": 4,
                    "anchor_count": 1,
                    "countable_anchor_count": 1,
                },
            ]

            write_symbolic_map_locator_sidecar(path, rows)
            loaded = read_symbolic_map_locator_sidecar(path)

            self.assertEqual(loaded, rows)

    def test_locator_sidecar_crc_rejects_corruption(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.locators.awsl"
            write_symbolic_map_locator_sidecar(path, [{"paragraph_id": 0, "block_id": 0, "line_start": 1, "line_end": 1}])
            raw = bytearray(path.read_bytes())
            raw[-1] ^= 0x01
            path.write_bytes(raw)

            with self.assertRaises(ValueError):
                read_symbolic_map_locator_sidecar(path)

    def test_round_trip_null_coordinate_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.nulls.awsn"
            rows = [
                {
                    "block_id": 72,
                    "line_start": 4,
                    "line_end": 4,
                    "anchor_position": 7,
                    "anchor_label": "Block 72 Ln 4 Anchor 7",
                    "observed_anchor": "badjunk",
                    "surface": "badjunk",
                    "resolved_anchor": "__NULL__",
                    "count_eligible": False,
                    "memory_truth": False,
                }
            ]

            write_symbolic_map_null_sidecar(path, rows)
            loaded = read_symbolic_map_null_sidecar(path)

            self.assertEqual(loaded, rows)

    def test_null_sidecar_crc_rejects_corruption(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.nulls.awsn"
            write_symbolic_map_null_sidecar(path, [{"block_id": 1, "line_start": 1, "anchor_position": 2}])
            raw = bytearray(path.read_bytes())
            raw[-1] ^= 0x01
            path.write_bytes(raw)

            with self.assertRaises(ValueError):
                read_symbolic_map_null_sidecar(path)

    def test_round_trip_visual_ref_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.visuals.awsv"
            rows = [
                {
                    "block_id": "block_1",
                    "block_ordinal": 1,
                    "line_start": 3,
                    "line_end": 3,
                    "visual_record_id": "vis_emp_graph",
                    "kind": "graph",
                    "source_path_ref": "figures/emp_graph.png",
                    "caption_block_id": "block_2",
                    "manifest_id": "manifest_emp_graph",
                    "geometry_status": "known",
                    "recognition_status": "not_run",
                    "alt_text": "",
                    "title": "",
                    "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
                }
            ]

            write_symbolic_map_visual_sidecar(path, rows)
            loaded = read_symbolic_map_visual_sidecar(path)

            self.assertEqual(loaded, rows)

    def test_visual_ref_sidecar_crc_rejects_corruption(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.visuals.awsv"
            write_symbolic_map_visual_sidecar(path, [{"block_id": "block_1", "visual_record_id": "vis_emp_graph"}])
            raw = bytearray(path.read_bytes())
            raw[-1] ^= 0x01
            path.write_bytes(raw)

            with self.assertRaises(ValueError):
                read_symbolic_map_visual_sidecar(path)

    def test_read_symbolic_map_bundle_loads_map_and_sidecars(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.awsm"
            write_symbolic_map_binary(
                path,
                metadata={"source_name": "sample.md"},
                relations=[SymbolicMapRelation(1, 2, 1, 0, 0, 7)],
            )
            write_symbolic_map_locator_sidecar(
                Path(temp_dir) / "sample.locators.awsl",
                [{"paragraph_id": 0, "block_id": 0, "line_start": 1, "line_end": 1}],
            )
            write_symbolic_map_null_sidecar(
                Path(temp_dir) / "sample.nulls.awsn",
                [{"block_id": 0, "line_start": 1, "anchor_position": 1, "observed_anchor": "junk"}],
            )
            write_symbolic_map_visual_sidecar(
                Path(temp_dir) / "sample.visuals.awsv",
                [{"block_id": "block_0", "visual_record_id": "vis_1"}],
            )

            bundle = read_symbolic_map_bundle(path)

            self.assertEqual(bundle.map.metadata["source_name"], "sample.md")
            self.assertEqual(bundle.map.relation_count, 1)
            self.assertEqual(bundle.locators[0]["block_id"], 0)
            self.assertEqual(bundle.nulls[0]["observed_anchor"], "junk")
            self.assertEqual(bundle.visuals[0]["visual_record_id"], "vis_1")
            self.assertEqual(bundle.paths["map"], str(path))
            self.assertEqual(bundle.paths["locators"], str(Path(temp_dir) / "sample.locators.awsl"))

    def test_read_symbolic_map_bundle_uses_empty_lists_for_missing_optional_sidecars(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.awsm"
            write_symbolic_map_binary(
                path,
                metadata={"source_name": "sample.md"},
                relations=[SymbolicMapRelation(1, 2, 1, 0, 0, 7)],
            )

            bundle = read_symbolic_map_bundle(path)

            self.assertEqual(bundle.map.relation_count, 1)
            self.assertEqual(bundle.locators, [])
            self.assertEqual(bundle.nulls, [])
            self.assertEqual(bundle.visuals, [])
            self.assertNotIn("locators", bundle.paths)


if __name__ == "__main__":
    unittest.main()
