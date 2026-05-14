from __future__ import annotations

import json
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
from AnchorWorks.symbol_count_native import (
    inspect_cell,
    merge_compact_symbol_stream,
    merge_symbol_stream,
    score_binary_counts,
    verify_binary_counts,
    write_compact_symbol_stream,
    write_awss_from_symbol_count_artifacts,
)


def _anchorworks_repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent if (parent / "src" / "AnchorWorks").exists() else parent / "Anchorworks"
        if (candidate / "src" / "AnchorWorks").exists():
            return candidate
    raise RuntimeError("Anchorworks repo root not found")


REPO_ROOT = _anchorworks_repo_root()
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

    def test_awss_can_be_written_from_source_local_symbol_artifact(self) -> None:
        with TemporaryDirectory() as root:
            temp_root = Path(root)
            artifact = temp_root / "sample.symbol_counts.json"
            stream_path = temp_root / "sample.awss"
            output_root = temp_root / "binary_counts"
            artifact.write_text(
                json.dumps({
                    "symbol_authority": [
                        {"anchor": "a", "symbol": "0x0000000001", "authority": "canonical"},
                        {"anchor": "b", "symbol": "0x0000000002", "authority": "canonical"},
                        {"anchor": "c", "symbol": "0xF000000003", "authority": "source_local"},
                    ],
                    "symbol_relation_counts": [
                        {
                            "symbol_anchor": "0x0000000001",
                            "offset": "+1",
                            "neighbor_symbol_anchor": "0x0000000002",
                            "observations": 5,
                        },
                        {
                            "symbol_anchor": "0x0000000001",
                            "offset": "-1",
                            "neighbor_symbol_anchor": "0xF000000003",
                            "observations": 2,
                        },
                    ],
                }),
                encoding="utf-8",
            )

            stream = write_awss_from_symbol_count_artifacts([artifact], stream_path)
            self.assertEqual(stream["record_count"], 2)
            self.assertEqual(stream_path.stat().st_size, 48)

            merge_symbol_stream(stream_path, output_root, generation=12, executable=self.exe)
            cell = read_symbol_cell(output_root / "cells" / "00" / "0000000001.cell")
            rows = {(row.offset, row.neighbor_symbol, row.lane): row.count for row in cell.relations}
            self.assertEqual(rows[(1, symbol_to_bytes("0x0000000002"), CANONICAL_LANE)], 5)
            self.assertEqual(rows[(-1, symbol_to_bytes("0xF000000003"), SOURCE_LOCAL_TEMP_LANE)], 2)

    def test_native_score_returns_weighted_top_k_from_awsc_cells(self) -> None:
        with TemporaryDirectory() as root:
            temp_root = Path(root)
            stream_path = temp_root / "sample.awss"
            output_root = temp_root / "binary_counts"
            stream_path.write_bytes(
                b"".join([
                    self._stream_record("0x0000000001", "0x00000000AA", 1, CANONICAL_LANE, 0, CANONICAL_LANE, 10),
                    self._stream_record("0x0000000002", "0x00000000AA", 1, CANONICAL_LANE, 0, CANONICAL_LANE, 5),
                    self._stream_record("0x0000000001", "0x00000000BB", 2, CANONICAL_LANE, 0, CANONICAL_LANE, 20),
                    self._stream_record("0x0000000002", "0x00000000CC", -1, CANONICAL_LANE, 0, CANONICAL_LANE, 7),
                    self._stream_record("0x0000000002", "0x00000000DD", 1, SOURCE_LOCAL_TEMP_LANE, 0, CANONICAL_LANE, 99),
                ])
            )
            merge_symbol_stream(stream_path, output_root, generation=13, executable=self.exe)

            completed = subprocess.run(
                [
                    str(self.exe),
                    "score",
                    "--root",
                    str(output_root),
                    "--context",
                    "0x0000000001,0x0000000002",
                    "--top-k",
                    "3",
                    "--allowed-lanes",
                    "0",
                ],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(completed.stdout)

            self.assertTrue(payload["ok"])
            self.assertEqual(payload["context_count"], 2)
            self.assertEqual([row["symbol"] for row in payload["candidates"]], ["00000000AA", "00000000BB", "00000000CC"])
            self.assertEqual(payload["candidates"][0]["score"], 15.0)
            self.assertEqual(payload["candidates"][0]["supporting_roots"], 2)
            self.assertEqual(payload["candidates"][1]["score"], 10.0)
            self.assertEqual(payload["candidates"][2]["score"], 7.0)

    def test_python_wrapper_scores_binary_counts(self) -> None:
        with TemporaryDirectory() as root:
            temp_root = Path(root)
            stream_path = temp_root / "sample.awss"
            output_root = temp_root / "binary_counts"
            stream_path.write_bytes(
                b"".join([
                    self._stream_record("0x0000000001", "0x00000000AA", 1, CANONICAL_LANE, 0, CANONICAL_LANE, 3),
                    self._stream_record("0x0000000002", "0x00000000AA", 1, CANONICAL_LANE, 0, CANONICAL_LANE, 4),
                    self._stream_record("0x0000000002", "0x00000000BB", 2, CANONICAL_LANE, 0, CANONICAL_LANE, 8),
                ])
            )
            merge_symbol_stream(stream_path, output_root, generation=14, executable=self.exe)

            payload = score_binary_counts(
                output_root,
                context_symbols=["0x0000000001", "0x0000000002"],
                top_k=2,
                allowed_lanes=[CANONICAL_LANE],
                executable=self.exe,
            )

            self.assertTrue(payload["ok"])
            self.assertEqual([row["symbol"] for row in payload["candidates"]], ["00000000AA", "00000000BB"])
            self.assertEqual(payload["candidates"][0]["supporting_roots"], 2)

    def test_native_merge_compact_symbol_stream_builds_relations(self) -> None:
        with TemporaryDirectory() as root:
            temp_root = Path(root)
            stream_path = temp_root / "sample.awsy"
            output_root = temp_root / "binary_counts"

            stream = write_compact_symbol_stream(
                [[
                    {"symbol": "0x0000000001", "lane": CANONICAL_LANE},
                    {"symbol": "0x0000000002", "lane": CANONICAL_LANE},
                    {"symbol": "0x0000000003", "lane": MATH_COMPANION_LANE},
                    {"symbol": "0x0000000002", "lane": CANONICAL_LANE},
                ]],
                stream_path,
            )
            self.assertEqual(stream["record_count"], 4)
            self.assertEqual(stream_path.stat().st_size, 32)

            merge = merge_compact_symbol_stream(
                stream_path,
                output_root,
                generation=15,
                window_radius=2,
                executable=self.exe,
            )
            self.assertTrue(merge["ok"])

            verify_payload = verify_binary_counts(output_root, executable=self.exe)
            self.assertTrue(verify_payload["ok"])
            self.assertEqual(verify_payload["checked"], 3)

            cell = read_symbol_cell(output_root / "cells" / "00" / "0000000002.cell")
            rows = {(row.offset, row.neighbor_symbol, row.lane): row.count for row in cell.relations}
            self.assertEqual(rows[(-1, symbol_to_bytes("0x0000000001"), CANONICAL_LANE)], 1)
            self.assertEqual(rows[(1, symbol_to_bytes("0x0000000003"), MATH_COMPANION_LANE)], 1)
            self.assertEqual(rows[(2, symbol_to_bytes("0x0000000002"), CANONICAL_LANE)], 1)

    def test_native_compact_symbol_stream_respects_sequence_boundaries(self) -> None:
        with TemporaryDirectory() as root:
            temp_root = Path(root)
            stream_path = temp_root / "sample.awsy"
            output_root = temp_root / "binary_counts"

            write_compact_symbol_stream(
                [
                    [
                        {"symbol": "0x0000000001", "lane": CANONICAL_LANE},
                        {"symbol": "0x0000000002", "lane": CANONICAL_LANE},
                    ],
                    [
                        {"symbol": "0x0000000003", "lane": CANONICAL_LANE},
                        {"symbol": "0x0000000004", "lane": CANONICAL_LANE},
                    ],
                ],
                stream_path,
            )
            merge_compact_symbol_stream(
                stream_path,
                output_root,
                generation=16,
                window_radius=2,
                executable=self.exe,
            )

            cell = read_symbol_cell(output_root / "cells" / "00" / "0000000002.cell")
            neighbors = {row.neighbor_symbol for row in cell.relations}
            self.assertIn(symbol_to_bytes("0x0000000001"), neighbors)
            self.assertNotIn(symbol_to_bytes("0x0000000003"), neighbors)

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
