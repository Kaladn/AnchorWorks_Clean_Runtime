from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from AnchorWorks.intake import build_anchor_map
from AnchorWorks.store import LexiconStore
from AnchorWorks.symbol_relation_counts import (
    build_source_local_symbol_table,
    build_symbol_relation_map,
    build_symbol_relation_rows,
    pack_symbol_id,
)


class SymbolRelationCountsTests(unittest.TestCase):
    def test_pack_symbol_id_reads_canonical_hex(self) -> None:
        self.assertEqual(pack_symbol_id("0x00000000FF"), 255)
        self.assertEqual(pack_symbol_id("C545598B96"), 0xC545598B96)

    def test_source_local_symbol_table_keeps_every_anchor_symbolic(self) -> None:
        symbol_by_anchor, rows = build_source_local_symbol_table(
            ["alpha", ",", "alpha"],
            canonical_symbol_by_anchor={"alpha": "0x0000000001"},
            source_id="source_a",
        )

        self.assertEqual(symbol_by_anchor["alpha"], "0x0000000001")
        self.assertTrue(symbol_by_anchor[","].startswith("0xF"))
        self.assertEqual({row["authority"] for row in rows}, {"canonical", "source_local"})

    def test_symbol_relation_rows_match_anchor_relation_rows(self) -> None:
        text = "how do i sear meat\n\nthis is how i sear meat"
        mapping = build_anchor_map(text)
        symbol_by_anchor = {
            anchor: f"0x{index + 1:010X}"
            for index, anchor in enumerate(sorted(mapping["observed_counts"]))
        }

        rows = build_symbol_relation_rows(
            mapping["paragraphs"],
            symbol_by_anchor=symbol_by_anchor,
            window_radius=6,
        )
        decoded = {
            (
                row["symbol_anchor"],
                row["offset"],
                row["neighbor_symbol_anchor"],
            ): row["observations"]
            for row in rows
        }
        expected = {
            (
                symbol_by_anchor[row["anchor"]],
                row["offset"],
                symbol_by_anchor[row["neighbor"]],
            ): row["observations"]
            for row in mapping["co_occurrence_counts"]
        }

        self.assertEqual(decoded, expected)

    def test_symbol_relation_map_matches_anchor_relation_rows_without_string_counting(self) -> None:
        text = "how do i sear meat\n\nthis is how i sear meat"
        mapping = build_anchor_map(text)
        symbol_by_anchor = {
            anchor: f"0x{index + 1:010X}"
            for index, anchor in enumerate(sorted(mapping["observed_counts"]))
        }

        symbol_mapping = build_symbol_relation_map(
            text,
            symbol_by_anchor=symbol_by_anchor,
            window_radius=6,
        )
        decoded = {
            (
                row["symbol_anchor"],
                row["offset"],
                row["neighbor_symbol_anchor"],
            ): row["observations"]
            for row in symbol_mapping["symbol_relation_counts"]
        }
        expected = {
            (
                symbol_by_anchor[row["anchor"]],
                row["offset"],
                symbol_by_anchor[row["neighbor"]],
            ): row["observations"]
            for row in mapping["co_occurrence_counts"]
        }

        self.assertEqual(decoded, expected)
        self.assertEqual(symbol_mapping["stats"]["total_anchor_observations"], mapping["stats"]["total_anchor_observations"])

    def test_symbol_relation_rows_exclude_null_symbol_as_relation_endpoint(self) -> None:
        text = "alpha junk beta"
        mapping = build_anchor_map(text, null_anchors={"junk"})
        symbol_by_anchor = {
            "alpha": "0x0000000001",
            "beta": "0x0000000002",
            "__NULL__": "0x0000000000",
        }

        rows = build_symbol_relation_rows(
            mapping["paragraphs"],
            symbol_by_anchor=symbol_by_anchor,
            window_radius=6,
        )

        self.assertTrue(rows)
        self.assertFalse(any(row["symbol_id"] == 0 or row["neighbor_symbol_id"] == 0 for row in rows))

    def test_store_writes_source_local_symbol_counts_without_lifetime_write(self) -> None:
        with TemporaryDirectory() as temp_root:
            store = LexiconStore(temp_root)
            store.canonical_dir.mkdir(parents=True, exist_ok=True)
            (store.canonical_dir / "canonical_A.json").write_text(
                '[{"word":"alpha","hex":"0x0000000001"},{"word":"beta","hex":"0x0000000002"}]',
                encoding="utf-8",
            )
            observed_path = store.observed_maps_dir / "sample.observed.json"
            observed_path.write_text(
                """{
  "source_name": "sample.txt",
  "source_path": "sample.txt",
  "window_radius": 6,
  "paragraphs": [
    {
      "paragraph_id": 0,
      "anchors": ["alpha", ",", "beta"],
      "resolved_anchors": ["alpha", ",", "beta"],
      "count_eligible": [true, true, true]
    }
  ],
  "co_occurrence_counts": [
    {"anchor":"alpha","offset":"+1","neighbor":",","observations":1},
    {"anchor":"alpha","offset":"+2","neighbor":"beta","observations":1},
    {"anchor":",","offset":"-1","neighbor":"alpha","observations":1},
    {"anchor":",","offset":"+1","neighbor":"beta","observations":1},
    {"anchor":"beta","offset":"-2","neighbor":"alpha","observations":1},
    {"anchor":"beta","offset":"-1","neighbor":",","observations":1}
  ],
  "document_prep": {"sha256": "abc"}
}""",
                encoding="utf-8",
            )

            result = store.build_source_local_symbol_counts("sample.observed.json")

            self.assertTrue(result["ok"])
            self.assertEqual(result["canonical_symbol_count"], 2)
            self.assertEqual(result["source_local_symbol_count"], 1)
            self.assertEqual(result["relation_fates"]["canonical_to_canonical"], 2)
            self.assertEqual(result["relation_fates"]["source_local_relation"], 4)
            self.assertEqual(result["writes_allowed"]["lifetime"], False)

    def test_store_reads_awsm_hot_path_when_json_observed_map_is_absent(self) -> None:
        with TemporaryDirectory() as temp_root:
            store = LexiconStore(temp_root)
            store.canonical_dir.mkdir(parents=True, exist_ok=True)
            (store.canonical_dir / "canonical_A.json").write_text(
                '[{"word":"alpha","hex":"0x0000000001"},{"word":"beta","hex":"0x0000000002"}]',
                encoding="utf-8",
            )
            source = Path(temp_root) / "sample.txt"
            source.write_text("alpha beta alpha", encoding="utf-8")
            map_result = store.build_observed_map(source)
            Path(map_result["saved_map_path"]).unlink()

            result = store.build_source_local_symbol_counts(map_result["saved_map_name"])

            self.assertTrue(result["ok"])
            self.assertEqual(result["source_format"], "awsm")
            self.assertEqual(result["canonical_symbol_count"], 2)
            self.assertEqual(result["source_local_symbol_count"], 0)
            self.assertGreater(result["unique_symbol_relations"], 0)
            self.assertEqual(result["writes_allowed"]["lifetime"], False)

    def test_store_awsm_symbol_counts_match_json_debug_fallback(self) -> None:
        with TemporaryDirectory() as temp_root:
            store = LexiconStore(temp_root)
            store.canonical_dir.mkdir(parents=True, exist_ok=True)
            (store.canonical_dir / "canonical_A.json").write_text(
                '[{"word":"alpha","hex":"0x0000000001"},{"word":"beta","hex":"0x0000000002"}]',
                encoding="utf-8",
            )
            source = Path(temp_root) / "sample.txt"
            source.write_text("alpha beta alpha", encoding="utf-8")
            map_result = store.build_observed_map(source)

            awsm_result = store.build_source_local_symbol_counts(map_result["saved_map_name"])
            awsm_artifact = store._read_json(Path(awsm_result["symbol_counts_path"]), {})
            Path(map_result["symbolic_map_path"]).unlink()
            json_result = store.build_source_local_symbol_counts(map_result["saved_map_name"])
            json_artifact = store._read_json(Path(json_result["symbol_counts_path"]), {})

            self.assertEqual(awsm_result["source_format"], "awsm")
            self.assertEqual(json_result["source_format"], "observed_json")
            self.assertEqual(awsm_artifact["symbol_authority"], json_artifact["symbol_authority"])
            self.assertEqual(awsm_artifact["symbol_relation_counts"], json_artifact["symbol_relation_counts"])
            self.assertEqual(awsm_artifact["relation_fates"], json_artifact["relation_fates"])

    def test_store_builds_binary_symbol_counts_from_source_local_artifacts(self) -> None:
        with TemporaryDirectory() as temp_root:
            store = LexiconStore(temp_root)
            artifact = store.source_local_symbol_counts_dir / "sample.symbol_counts.json"
            artifact.write_text(
                """{
  "symbol_authority": [
    {"anchor": "alpha", "symbol": "0x0000000001", "authority": "canonical"},
    {"anchor": "beta", "symbol": "0x0000000002", "authority": "canonical"}
  ],
  "symbol_relation_counts": [
    {"symbol_anchor": "0x0000000001", "offset": "+1", "neighbor_symbol_anchor": "0x0000000002", "observations": 3},
    {"symbol_anchor": "0x0000000001", "offset": "+1", "neighbor_symbol_anchor": "0x0000000002", "observations": 4}
  ]
}""",
                encoding="utf-8",
            )

            result = store.build_binary_symbol_counts_from_source_local(generation=4)

            self.assertTrue(result["ok"])
            self.assertEqual(result["artifact_count"], 1)
            self.assertEqual(result["stream_record_count"], 2)
            self.assertEqual(result["verify"]["checked"], 1)
            self.assertEqual(result["writes_allowed"]["lifetime"], False)


if __name__ == "__main__":
    unittest.main()
