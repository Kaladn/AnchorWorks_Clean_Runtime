from __future__ import annotations

import struct
import unittest
import zlib
from pathlib import Path
from tempfile import TemporaryDirectory

from AnchorWorks.symbol_count_cells import (
    CANONICAL_LANE,
    HEADER_SIZE,
    MATH_COMPANION_LANE,
    ROW_SIZE,
    SOURCE_LOCAL_TEMP_LANE,
    SPEAK_BLOCKED_FLAG,
    SymbolRelation,
    corrupt_cell_for_test,
    merge_symbol_cell,
    read_symbol_cell,
    symbol_to_bytes,
    write_symbol_cell,
)


class SymbolCountCellTests(unittest.TestCase):
    def test_awsc_v11_uses_exact_header_and_row_sizes(self) -> None:
        self.assertEqual(HEADER_SIZE, 64)
        self.assertEqual(ROW_SIZE, 16)

    def test_write_and_read_awsc_v11_cell(self) -> None:
        with TemporaryDirectory() as root:
            path = Path(root) / "cell.bin"
            write_symbol_cell(
                path,
                symbol="0x0000000001",
                root_lane=CANONICAL_LANE,
                generation=7,
                relations=[
                    SymbolRelation(offset=1, neighbor_symbol="0x0000000002", count=3, lane=CANONICAL_LANE),
                    SymbolRelation(offset=-1, neighbor_symbol="0x0000000003", count=2, lane=MATH_COMPANION_LANE),
                ],
            )

            raw = path.read_bytes()
            cell = read_symbol_cell(path)

            self.assertEqual(len(raw), HEADER_SIZE + (2 * ROW_SIZE))
            self.assertEqual(cell.total_size, len(raw))
            self.assertEqual(cell.symbol, symbol_to_bytes("0x0000000001"))
            self.assertEqual(cell.root_lane, CANONICAL_LANE)
            self.assertEqual(cell.generation, 7)
            self.assertEqual(len(cell.relations), 2)

    def test_relation_rows_are_sorted_deterministically(self) -> None:
        with TemporaryDirectory() as root:
            path = Path(root) / "cell.bin"
            write_symbol_cell(
                path,
                symbol="0x0000000001",
                relations=[
                    SymbolRelation(offset=2, neighbor_symbol="0x0000000005", count=1, lane=CANONICAL_LANE),
                    SymbolRelation(offset=-1, neighbor_symbol="0x0000000004", count=3, lane=CANONICAL_LANE),
                    SymbolRelation(offset=-1, neighbor_symbol="0x0000000002", count=3, lane=MATH_COMPANION_LANE),
                    SymbolRelation(offset=-1, neighbor_symbol="0x0000000003", count=9, lane=CANONICAL_LANE),
                ],
            )

            rows = read_symbol_cell(path).relations

            self.assertEqual(
                [(row.offset, row.count, row.neighbor_symbol, row.lane) for row in rows],
                [
                    (-1, 9, symbol_to_bytes("0x0000000003"), CANONICAL_LANE),
                    (-1, 3, symbol_to_bytes("0x0000000002"), MATH_COMPANION_LANE),
                    (-1, 3, symbol_to_bytes("0x0000000004"), CANONICAL_LANE),
                    (2, 1, symbol_to_bytes("0x0000000005"), CANONICAL_LANE),
                ],
            )

    def test_merge_symbol_cell_combines_existing_rows(self) -> None:
        with TemporaryDirectory() as root:
            path = Path(root) / "cell.bin"
            write_symbol_cell(
                path,
                symbol="0x0000000001",
                generation=2,
                relations=[
                    SymbolRelation(offset=1, neighbor_symbol="0x0000000002", count=3, lane=CANONICAL_LANE),
                ],
            )

            merge_symbol_cell(
                path,
                symbol="0x0000000001",
                generation=3,
                relations=[
                    SymbolRelation(offset=1, neighbor_symbol="0x0000000002", count=4, lane=CANONICAL_LANE),
                    SymbolRelation(offset=2, neighbor_symbol="0x0000000003", count=1, lane=SOURCE_LOCAL_TEMP_LANE),
                ],
            )
            cell = read_symbol_cell(path)

            self.assertEqual(cell.generation, 3)
            rows = {(row.offset, row.neighbor_symbol, row.lane): row.count for row in cell.relations}
            self.assertEqual(rows[(1, symbol_to_bytes("0x0000000002"), CANONICAL_LANE)], 7)
            self.assertEqual(rows[(2, symbol_to_bytes("0x0000000003"), SOURCE_LOCAL_TEMP_LANE)], 1)

    def test_crc_corruption_is_rejected(self) -> None:
        with TemporaryDirectory() as root:
            path = Path(root) / "cell.bin"
            write_symbol_cell(
                path,
                symbol="0x0000000001",
                relations=[SymbolRelation(offset=1, neighbor_symbol="0x0000000002", count=1, lane=CANONICAL_LANE)],
            )
            corrupt_cell_for_test(path)

            with self.assertRaises(ValueError):
                read_symbol_cell(path)

    def test_total_size_must_match_file_size(self) -> None:
        with TemporaryDirectory() as root:
            path = Path(root) / "cell.bin"
            write_symbol_cell(
                path,
                symbol="0x0000000001",
                relations=[SymbolRelation(offset=1, neighbor_symbol="0x0000000002", count=1, lane=CANONICAL_LANE)],
            )
            raw = bytearray(path.read_bytes())
            raw[8:16] = struct.pack("<Q", 999)
            path.write_bytes(raw)

            with self.assertRaises(ValueError):
                read_symbol_cell(path)

    def test_null_lane_cannot_be_written_as_relation_memory(self) -> None:
        with self.assertRaises(ValueError):
            SymbolRelation(offset=1, neighbor_symbol="0x0000000002", count=1, lane=6)

    def test_fixture_byte_layout_is_stable(self) -> None:
        with TemporaryDirectory() as root:
            path = Path(root) / "cell.bin"
            relation = SymbolRelation(
                offset=1,
                neighbor_symbol="0x0000000002",
                count=3,
                lane=CANONICAL_LANE,
                flags=SPEAK_BLOCKED_FLAG,
            )
            write_symbol_cell(
                path,
                symbol="0x0000000001",
                root_lane=CANONICAL_LANE,
                generation=7,
                wal_frame=0,
                flags=0,
                relations=[relation],
            )

            payload = bytes.fromhex("00000000020100010300000000000000")
            expected = (
                b"AWSC"
                + struct.pack("<HHQQQ", 0x0101, 64, 80, 7, 0)
                + symbol_to_bytes("0x0000000001")
                + struct.pack("<BHIHHIIQ", CANONICAL_LANE, 0, 1, 16, 0, 16, zlib.crc32(payload) & 0xFFFFFFFF, 0)
                + payload
            )

            self.assertEqual(path.read_bytes(), expected)


if __name__ == "__main__":
    unittest.main()
