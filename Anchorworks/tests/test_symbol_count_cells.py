from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from AnchorWorks.symbol_count_cells import (
    CANONICAL_LANE,
    SymbolRelation,
    corrupt_cell_for_test,
    merge_symbol_cell,
    read_symbol_cell,
    symbol_to_bytes,
    write_symbol_cell,
)


class SymbolCountCellTests(unittest.TestCase):
    def test_write_and_read_symbol_cell(self) -> None:
        with TemporaryDirectory() as root:
            path = Path(root) / "cell.bin"
            write_symbol_cell(
                path,
                symbol="0x0000000001",
                anchor_observations=7,
                relations=[
                    SymbolRelation(offset=1, neighbor_symbol="0x0000000002", count=3, lane=CANONICAL_LANE),
                    SymbolRelation(offset=-1, neighbor_symbol="0x0000000003", count=2, lane=CANONICAL_LANE),
                ],
            )

            cell = read_symbol_cell(path)

            self.assertEqual(cell.symbol, symbol_to_bytes("0x0000000001"))
            self.assertEqual(cell.anchor_observations, 7)
            self.assertEqual(len(cell.relations), 2)
            self.assertEqual(cell.relations[0].count, 3)

    def test_merge_symbol_cell_combines_existing_rows(self) -> None:
        with TemporaryDirectory() as root:
            path = Path(root) / "cell.bin"
            write_symbol_cell(
                path,
                symbol="0x0000000001",
                anchor_observations=7,
                relations=[
                    SymbolRelation(offset=1, neighbor_symbol="0x0000000002", count=3, lane=CANONICAL_LANE),
                ],
            )

            merge_symbol_cell(
                path,
                symbol="0x0000000001",
                anchor_observations_delta=5,
                relations=[
                    SymbolRelation(offset=1, neighbor_symbol="0x0000000002", count=4, lane=CANONICAL_LANE),
                    SymbolRelation(offset=2, neighbor_symbol="0x0000000003", count=1, lane=CANONICAL_LANE),
                ],
            )
            cell = read_symbol_cell(path)

            self.assertEqual(cell.anchor_observations, 12)
            rows = {(row.offset, row.neighbor_symbol, row.lane): row.count for row in cell.relations}
            self.assertEqual(rows[(1, symbol_to_bytes("0x0000000002"), CANONICAL_LANE)], 7)
            self.assertEqual(rows[(2, symbol_to_bytes("0x0000000003"), CANONICAL_LANE)], 1)

    def test_crc_corruption_is_rejected(self) -> None:
        with TemporaryDirectory() as root:
            path = Path(root) / "cell.bin"
            write_symbol_cell(
                path,
                symbol="0x0000000001",
                anchor_observations=1,
                relations=[SymbolRelation(offset=1, neighbor_symbol="0x0000000002", count=1, lane=CANONICAL_LANE)],
            )
            corrupt_cell_for_test(path)

            with self.assertRaises(ValueError):
                read_symbol_cell(path)


if __name__ == "__main__":
    unittest.main()
