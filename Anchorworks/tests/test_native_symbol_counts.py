from __future__ import annotations

import shutil
import struct
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from AnchorWorks.symbol_count_cells import (
    CANONICAL_LANE,
    MATH_COMPANION_LANE,
    SOURCE_LOCAL_TEMP_LANE,
    read_symbol_cell,
    symbol_to_bytes,
)
from AnchorWorks.symbol_count_native import inspect_cell, merge_symbol_stream, verify_binary_counts


REPO_ROOT = Path(__file__).resolve().parents[1]
NATIVE_ROOT = REPO_ROOT / "src" / "AnchorWorks" / "native" / "symbol_counts"
BUILD_ROOT = REPO_ROOT / "build" / "native_symbol_counts_tests"
VS_CMAKE = Path(
    r"C:\Program Files\Microsoft Visual Studio\18\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"
)


class NativeSymbolCountsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cmake = cls._find_cmake()
        subprocess.run(
            [
                str(cls.cmake),
                "-S",
                str(NATIVE_ROOT),
                "-B",
                str(BUILD_ROOT),
                "-G",
                "Visual Studio 18 2026",
                "-A",
                "x64",
            ],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [str(cls.cmake), "--build", str(BUILD_ROOT), "--config", "Release"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        cls.exe = BUILD_ROOT / "Release" / "anchorworks-symbol-counts.exe"
        if not cls.exe.exists():
            raise AssertionError(f"native executable missing: {cls.exe}")

    @staticmethod
    def _find_cmake() -> Path:
        if VS_CMAKE.exists():
            return VS_CMAKE
        discovered = shutil.which("cmake")
        if discovered:
            return Path(discovered)
        raise unittest.SkipTest("CMake not available")

    def test_native_merge_stream_writes_awsc_cells_python_can_read(self) -> None:
        with TemporaryDirectory() as root:
            temp_root = Path(root)
            stream_path = temp_root / "sample.awss"
            output_root = temp_root / "binary_counts"
            stream_path.write_bytes(
                b"".join([
                    self._stream_record("0x0000000001", "0x0000000002", 1, CANONICAL_LANE, 0, CANONICAL_LANE, 3),
                    self._stream_record("0x0000000001", "0x0000000002", 1, CANONICAL_LANE, 0, CANONICAL_LANE, 4),
                    self._stream_record("0x0000000001", "0x0000000003", -1, MATH_COMPANION_LANE, 0, CANONICAL_LANE, 2),
                    self._stream_record("0x0000000004", "0x0000000005", 1, SOURCE_LOCAL_TEMP_LANE, 0, SOURCE_LOCAL_TEMP_LANE, 1),
                ])
            )

            merge = merge_symbol_stream(
                stream_path,
                output_root,
                generation=11,
                executable=self.exe,
            )
            self.assertTrue(merge["ok"])

            verify_payload = verify_binary_counts(output_root, executable=self.exe)
            self.assertTrue(verify_payload["ok"])
            self.assertEqual(verify_payload["checked"], 2)

            cell = read_symbol_cell(output_root / "cells" / "00" / "0000000001.cell")
            self.assertEqual(cell.generation, 11)
            rows = {(row.offset, row.neighbor_symbol, row.lane): row.count for row in cell.relations}
            self.assertEqual(rows[(1, symbol_to_bytes("0x0000000002"), CANONICAL_LANE)], 7)
            self.assertEqual(rows[(-1, symbol_to_bytes("0x0000000003"), MATH_COMPANION_LANE)], 2)

            inspect_payload = inspect_cell(output_root / "cells" / "00" / "0000000001.cell", executable=self.exe)
            self.assertEqual(inspect_payload["symbol"], "0000000001")
            self.assertEqual(inspect_payload["relation_count"], 2)

    @staticmethod
    def _stream_record(
        root_symbol: str,
        neighbor_symbol: str,
        offset: int,
        lane: int,
        flags: int,
        root_lane: int,
        count: int,
    ) -> bytes:
        return struct.pack(
            "<5s5sbBBBHQ",
            symbol_to_bytes(root_symbol),
            symbol_to_bytes(neighbor_symbol),
            offset,
            lane,
            flags,
            root_lane,
            0,
            count,
        )


if __name__ == "__main__":
    unittest.main()
