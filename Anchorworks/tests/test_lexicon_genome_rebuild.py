from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from AnchorWorks.lexicon_genome_rebuild import build_lexicon_genome_rebuild
from AnchorWorks.symbol_genome_native import build_native_symbol_genome


REPO_ROOT = Path(__file__).resolve().parents[1]
VS_CMAKE = Path(
    r"C:\Program Files\Microsoft Visual Studio\18\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"
)


class LexiconGenomeRebuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not VS_CMAKE.exists() and not shutil.which("cmake"):
            raise unittest.SkipTest("CMake not available")

    def test_rebuild_writes_clean_genome_lexicon_without_mutating_source(self) -> None:
        with TemporaryDirectory() as root:
            temp_root = Path(root)
            data_root = temp_root / "source"
            out_root = temp_root / "Lexicon_Genome_Rebuild"
            (data_root / "Canonical").mkdir(parents=True)
            (data_root / "Structural").mkdir(parents=True)
            source_rows = [
                {
                    "word": "hello",
                    "display": "hello",
                    "hex": "0xAAAAAAAAAA",
                    "symbol": "0xAAAAAAAAAA",
                    "binary": "1010101010101010101010101010101010101010",
                    "tone_signature": "TONE_123",
                    "font_symbol": "CHAR_OLD",
                    "frequency": 99,
                    "status": "ASSIGNED",
                },
                {
                    "word": "world",
                    "display": "world",
                    "hex": "0xAAAAAAAAAA",
                    "symbol": "0xAAAAAAAAAA",
                    "binary": "1010101010101010101010101010101010101010",
                    "tone_signature": "TONE_456",
                    "font_symbol": "CHAR_OLD",
                    "frequency": 88,
                    "status": "ASSIGNED",
                },
                {
                    "word": "hello",
                    "display": "hello",
                    "hex": "0xBBBBBBBBBB",
                    "symbol": "0xBBBBBBBBBB",
                    "binary": "1011101110111011101110111011101110111011",
                    "tone_signature": "TONE_789",
                    "font_symbol": "CHAR_DUP",
                    "status": "ASSIGNED",
                },
                {
                    "word": "!!!",
                    "display": "!!!",
                    "hex": "0xDDDDDDDDDD",
                    "symbol": "0xDDDDDDDDDD",
                    "binary": "1101110111011101110111011101110111011101",
                    "tone_signature": "TONE_BANG",
                    "font_symbol": "CHAR_BANG",
                    "status": "ASSIGNED",
                },
                {
                    "word": "???",
                    "display": "???",
                    "hex": "0xEEEEEEEEEE",
                    "symbol": "0xEEEEEEEEEE",
                    "binary": "1110111011101110111011101110111011101110",
                    "tone_signature": "TONE_Q",
                    "font_symbol": "CHAR_Q",
                    "status": "ASSIGNED",
                },
            ]
            structural_rows = [
                {
                    "word": "0",
                    "display": "DIGIT_0",
                    "hex": "0xCCCCCCCCCC",
                    "symbol": "0xCCCCCCCCCC",
                    "binary": "1100110011001100110011001100110011001100",
                    "tone_signature": "TONE_000",
                    "font_symbol": "CHAR_STRUCT",
                    "status": "STRUCTURAL",
                }
            ]
            canonical_path = data_root / "Canonical" / "canonical_A.json"
            structural_path = data_root / "Structural" / "structural.json"
            canonical_path.write_text(json.dumps(source_rows, indent=2), encoding="utf-8")
            structural_path.write_text(json.dumps(structural_rows, indent=2), encoding="utf-8")
            original_canonical = canonical_path.read_text(encoding="utf-8")
            original_structural = structural_path.read_text(encoding="utf-8")

            exe = build_native_symbol_genome(temp_root / "native_symbol_genome_build")
            report = build_lexicon_genome_rebuild(
                data_root,
                output_root=out_root,
                native_allocator=exe,
            )

            self.assertTrue(report["ok"])
            self.assertEqual(report["unique_rows"], 5)
            self.assertEqual(report["rebuilt_rows"], report["unique_rows"])
            self.assertEqual(canonical_path.read_text(encoding="utf-8"), original_canonical)
            self.assertEqual(structural_path.read_text(encoding="utf-8"), original_structural)

            rebuilt_rows = []
            for path in sorted((out_root / "Canonical").glob("*.json")) + sorted((out_root / "Structural").glob("*.json")):
                rebuilt_rows.extend(json.loads(path.read_text(encoding="utf-8")))

            self.assertEqual(len(rebuilt_rows), 5)
            allowed = {
                "anchor",
                "display",
                "genome_symbol",
                "genome_hex",
                "genome_binary",
                "status",
                "pack",
                "created_at",
                "category",
                "source_old_hex",
                "source_old_symbol",
            }
            genome_symbols = set()
            genome_hexes = set()
            for row in rebuilt_rows:
                self.assertLessEqual(set(row), allowed)
                self.assertNotIn("tone_signature", row)
                self.assertNotIn("font_symbol", row)
                self.assertEqual(row["genome_symbol"], row["genome_hex"])
                self.assertEqual(len(row["genome_binary"]), 40)
                self.assertEqual(int(row["genome_hex"][2:], 16), int(row["genome_binary"], 2))
                self.assertEqual(row["status"], "ASSIGNED")
                genome_symbols.add(row["genome_symbol"])
                genome_hexes.add(row["genome_hex"])

            self.assertEqual(len(genome_symbols), 5)
            self.assertEqual(len(genome_hexes), 5)

            duplicate_report = json.loads((out_root / "reports" / "duplicate_old_symbols.json").read_text(encoding="utf-8"))
            self.assertEqual(duplicate_report["duplicate_old_symbol_count"], 1)
            self.assertEqual(duplicate_report["duplicates"][0]["old_symbol"], "0xAAAAAAAAAA")

            manifest = json.loads((out_root / "reports" / "rebuild_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["generator"], "native_cpp_symbol_genome_allocator")
            self.assertEqual(manifest["tone_signature_absent"], True)
            self.assertEqual(manifest["font_symbol_absent"], True)


if __name__ == "__main__":
    unittest.main()
