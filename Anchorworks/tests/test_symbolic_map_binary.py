from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from AnchorWorks.symbolic_map_binary import (
    HEADER_SIZE,
    MAGIC,
    RELATION_ROW_SIZE,
    SymbolicMapRelation,
    read_symbolic_map_binary,
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


if __name__ == "__main__":
    unittest.main()
