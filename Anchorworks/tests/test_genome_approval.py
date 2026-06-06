import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from AnchorWorks.app import create_app
from AnchorWorks.store import LexiconStore
from AnchorWorks.symbol_genome_pool import SymbolGenomePool, symbol_genome_identity_from_index
from AnchorWorks.symbol_relation_counts import build_source_local_symbol_table
from AnchorWorks.symbol_count_native import _lane_for_authority


class GenomeApprovalTests(unittest.TestCase):
    def test_approve_intake_anchors_allocates_from_genome_pool_without_spare_slots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Canonical").mkdir()
            (root / "Structural").mkdir()
            (root / "Structural" / "structural.json").write_text("[]", encoding="utf-8")
            (root / "Spare_Slots").mkdir()
            (root / "Spare_Slots" / "spare_slots.json").write_text("[]", encoding="utf-8")

            store = LexiconStore(root)
            result = store.approve_intake_anchors(["securecore", "occular"], frequencies={"securecore": 13})

            self.assertTrue(result["ok"])
            self.assertEqual(result["approved_count"], 2)
            self.assertEqual(result["failed_count"], 0)
            self.assertEqual(result["slots_allocated"], 2)
            self.assertEqual(result["symbol_genome_pool"]["assigned_count"], 2)
            self.assertEqual(result["spare_pool_writes"], 0)
            self.assertIn("securecore", store._all_known_anchors())
            symbols = store._canonical_symbol_by_anchor()
            self.assertRegex(symbols["securecore"], r"^0xE[0-9A-F]{9}$")
            self.assertRegex(symbols["occular"], r"^0xE[0-9A-F]{9}$")
            self.assertFalse((root / "Canonical" / "canonical_S.json").exists())
            user_entries = json.loads((root / "State" / "user" / "user_lexicon" / "anchors.json").read_text(encoding="utf-8"))
            self.assertEqual({entry["word"] for entry in user_entries}, {"securecore", "occular"})
            self.assertTrue(all(entry["pack"] == "user" for entry in user_entries))
            self.assertTrue(all(entry["authority"] == "user_lexicon" for entry in user_entries))
            self.assertEqual(store._find_entry("securecore")[1], "user")

    def test_user_lexicon_symbols_are_available_to_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Canonical").mkdir()
            (root / "Structural").mkdir()
            (root / "Structural" / "structural.json").write_text("[]", encoding="utf-8")
            source = root / "user_anchor_source.txt"
            source.write_text("SecureCore protects SecureCore mapping.", encoding="utf-8")

            store = LexiconStore(root)
            approval = store.approve_intake_anchors(["securecore"])
            self.assertTrue(approval["ok"])

            observed = store.build_observed_map(source)
            counts = store.build_source_local_symbol_counts(observed["saved_map_name"])

            self.assertTrue(counts["ok"])
            self.assertGreater(counts["unique_symbol_relations"], 0)
            self.assertEqual(counts["user_lexicon_symbol_count"], 1)
            payload = json.loads(Path(counts["symbol_counts_path"]).read_text(encoding="utf-8"))
            authority_by_anchor = {row["anchor"]: row for row in payload["symbol_authority"]}
            self.assertEqual(authority_by_anchor["securecore"]["symbol"], store._canonical_symbol_by_anchor()["securecore"])
            self.assertEqual(authority_by_anchor["securecore"]["authority"], "user_lexicon")

    def test_dirty_observed_approvals_preserve_canonical_and_count_as_user_lane(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            canonical_dir = root / "Canonical"
            canonical_dir.mkdir()
            (root / "Structural").mkdir()
            (root / "Structural" / "structural.json").write_text("[]", encoding="utf-8")
            canonical_b = canonical_dir / "canonical_B.json"
            canonical_b.write_text('[{"word":"base","symbol":"0x000000000A"}]', encoding="utf-8")
            canonical_before = {path.name: path.read_bytes() for path in canonical_dir.glob("*.json")}
            source = root / "dirty_source.txt"
            source.write_text("blorxium teh blorxium teh", encoding="utf-8")

            store = LexiconStore(root)
            approval = store.approve_intake_anchors(["blorxium", "teh", "bad-ocr-word"])
            observed = store.build_observed_map(source)
            counts = store.build_source_local_symbol_counts(observed["saved_map_name"])

            self.assertTrue(approval["ok"])
            self.assertEqual(canonical_before, {path.name: path.read_bytes() for path in canonical_dir.glob("*.json")})
            user_entries = json.loads((root / "State" / "user" / "user_lexicon" / "anchors.json").read_text(encoding="utf-8"))
            user_by_word = {entry["word"]: entry for entry in user_entries}
            for anchor in ["blorxium", "teh", "bad-ocr-word"]:
                self.assertIn(anchor, user_by_word)
                self.assertEqual(user_by_word[anchor]["authority"], "user_lexicon")
                self.assertRegex(user_by_word[anchor]["symbol"], r"^0xE[0-9A-F]{9}$")
                self.assertEqual(store._find_entry(anchor)[1], "user")
                self.assertIn(anchor, store._all_known_anchors())

            symbol_lookup = store._canonical_symbol_by_anchor()
            self.assertEqual(symbol_lookup["base"], "0x000000000A")
            self.assertEqual(symbol_lookup["blorxium"], user_by_word["blorxium"]["symbol"])
            self.assertEqual(counts["user_lexicon_symbol_count"], 2)
            payload = json.loads(Path(counts["symbol_counts_path"]).read_text(encoding="utf-8"))
            authority_by_anchor = {row["anchor"]: row for row in payload["symbol_authority"]}
            self.assertEqual(authority_by_anchor["blorxium"]["authority"], "user_lexicon")
            self.assertEqual(authority_by_anchor["teh"]["authority"], "user_lexicon")
            self.assertTrue(payload["symbol_relation_counts"])
            self.assertTrue(all(row["lane"] == 5 for row in payload["symbol_relation_counts"]))

    def test_canonical_purge_routes_are_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            canonical_dir = root / "Canonical"
            canonical_dir.mkdir()
            (root / "Structural").mkdir()
            (root / "Structural" / "structural.json").write_text("[]", encoding="utf-8")
            canonical_b = canonical_dir / "canonical_B.json"
            canonical_b.write_text('[{"word":"base","symbol":"0x000000000A"}]', encoding="utf-8")
            before = canonical_b.read_bytes()

            client = TestClient(create_app(root))
            delete_response = client.delete("/api/lexicon/canonical")
            return_response = client.post("/api/lexicon/return-to-pool")

            self.assertEqual(delete_response.status_code, 200)
            self.assertEqual(return_response.status_code, 200)
            self.assertTrue(delete_response.json()["locked"])
            self.assertTrue(return_response.json()["locked"])
            self.assertEqual(canonical_b.read_bytes(), before)

    def test_binary_counts_seed_canonical_then_route_user_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Canonical").mkdir()
            (root / "Structural").mkdir()
            (root / "Structural" / "structural.json").write_text("[]", encoding="utf-8")
            canonical_cell = root / "State" / "symbol_counts_binary" / "cells" / "00" / "seed.cell"
            canonical_cell.parent.mkdir(parents=True)
            canonical_cell.write_bytes(b"canonical-seed")

            store = LexiconStore(root)
            canonical_before = canonical_cell.read_bytes()
            active_root = store.ensure_user_symbol_counts_seeded()["active_binary_counts_root"]
            user_cell = Path(active_root) / "cells" / "00" / "seed.cell"

            self.assertEqual(Path(active_root), root / "State" / "user" / "user_counts" / "symbol_counts_binary")
            self.assertEqual(user_cell.read_bytes(), canonical_before)
            self.assertEqual(canonical_cell.read_bytes(), canonical_before)
            ack = json.loads((Path(active_root) / "user_count_acknowledgement.json").read_text(encoding="utf-8"))
            self.assertEqual(ack["seed_source"], str(root / "State" / "symbol_counts_binary"))
            self.assertTrue(ack["canonical_seed_locked"])

            artifact = root / "State" / "source_local_symbol_counts" / "sample.symbol_counts.json"
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_text('{"symbol_relation_counts":[]}', encoding="utf-8")

            with (
                patch("AnchorWorks.store.write_awss_from_symbol_count_artifacts", return_value={"record_count": 1, "observation_count": 7}),
                patch("AnchorWorks.store.merge_symbol_stream", return_value={"ok": True}) as merge,
                patch("AnchorWorks.store.verify_binary_counts", return_value={"ok": True}) as verify,
            ):
                result = store.build_binary_symbol_counts_from_source_local(artifact_names=[artifact.name])

            self.assertEqual(Path(result["binary_counts_root"]), Path(active_root))
            self.assertEqual(Path(result["canonical_seed_counts_root"]), root / "State" / "symbol_counts_binary")
            self.assertEqual(Path(merge.call_args.args[1]), Path(active_root))
            self.assertEqual(Path(verify.call_args.args[0]), Path(active_root))
            self.assertEqual(canonical_cell.read_bytes(), canonical_before)

    def test_binary_counts_seed_copies_missing_files_even_after_acknowledgement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Canonical").mkdir()
            (root / "Structural").mkdir()
            (root / "Structural" / "structural.json").write_text("[]", encoding="utf-8")
            canonical_cell = root / "State" / "symbol_counts_binary" / "cells" / "00" / "seed.cell"
            canonical_cell.parent.mkdir(parents=True)
            canonical_cell.write_bytes(b"canonical-seed")
            user_root = root / "State" / "user" / "user_counts" / "symbol_counts_binary"
            user_root.mkdir(parents=True)
            (user_root / "user_count_acknowledgement.json").write_text(json.dumps({
                "schema_version": "anchorworks_user_binary_counts_acknowledgement@1",
                "canonical_seed_locked": True,
            }), encoding="utf-8")

            result = LexiconStore(root).ensure_user_symbol_counts_seeded()

            self.assertTrue(result["seeded"])
            self.assertEqual((user_root / "cells" / "00" / "seed.cell").read_bytes(), b"canonical-seed")

    def test_observed_unknown_surfaces_get_source_local_symbols_without_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Canonical").mkdir()
            (root / "Structural").mkdir()
            (root / "Structural" / "structural.json").write_text("[]", encoding="utf-8")
            source = root / "odd_source.txt"
            source.write_text("Blorxium columnalign href aques text.", encoding="utf-8")

            result = LexiconStore(root).build_observed_map(source)

            temp_by_word = {row["word"]: row for row in result["temp_symbols"]}
            for anchor in ["blorxium", "columnalign", "href", "aques"]:
                self.assertIn(anchor, temp_by_word)
                self.assertRegex(temp_by_word[anchor]["symbol"], r"^U[0-9A-F]{11}$")
            self.assertEqual(result["character_decomposed_anchor_count"], 0)
            self.assertEqual(result["null_anchor_count"], 0)
            observed = {row["anchor"]: row for row in result["observed_anchors"]}
            self.assertNotEqual(observed["blorxium"]["resolved_to"], "b")
            self.assertNotEqual(observed["href"]["resolved_to"], "__NULL__")

    def test_operator_null_is_still_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Canonical").mkdir()
            (root / "Structural").mkdir()
            (root / "Structural" / "structural.json").write_text("[]", encoding="utf-8")
            source = root / "odd_source.txt"
            source.write_text("Blorxium href.", encoding="utf-8")

            result = LexiconStore(root).build_observed_map(source, null_anchors={"href"})

            observed = {row["anchor"]: row for row in result["observed_anchors"]}
            self.assertEqual(observed["href"]["resolved_to"], "__NULL__")
            self.assertEqual(result["null_anchor_count"], 1)
            self.assertNotIn("href", {row["word"] for row in result["temp_symbols"]})

    def test_symbol_genome_pool_supports_trillion_scale_cursor(self):
        with tempfile.TemporaryDirectory() as tmp:
            pool = SymbolGenomePool(Path(tmp))
            status = pool.status()

            self.assertGreaterEqual(status["capacity"], 1_000_000_000_000)

            identity = symbol_genome_identity_from_index(
                "late-anchor",
                authority="source_local_coordinate",
                allocation_index=16,
            )

            self.assertEqual(identity["symbol_length_bytes"], 5)
            self.assertRegex(identity["hex"], r"^0xF[0-9A-F]{9}$")
            self.assertEqual(identity["allocation_index"], 16)

    def test_symbol_genome_pool_uses_authority_ranges(self):
        with tempfile.TemporaryDirectory() as tmp:
            pool = SymbolGenomePool(Path(tmp))

            canonical = pool.allocate("base", authority="canonical")
            user = pool.allocate("observed", authority="user_lexicon")
            source_local = pool.allocate("oddity", authority="source_local")

            self.assertEqual(canonical["hex"], "0x0000000000")
            self.assertEqual(user["hex"], "0xE000000001")
            self.assertEqual(source_local["hex"], "0xF000000002")

    def test_symbol_genome_pool_migrates_small_legacy_manifest_capacity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.mkdir(exist_ok=True)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "schema_version": "anchorworks_symbol_genome_pool@1",
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
                "capacity": 15_000_000,
                "next_index": 12,
                "assigned_count": 12,
                "generator": "cursor_backed_symbol_genome",
                "lexicon_pack": False,
                "records_materialized": False,
                "checkpoints": [],
            }), encoding="utf-8")

            status = SymbolGenomePool(root).status()

            self.assertGreaterEqual(status["capacity"], 1_000_000_000_000)
            self.assertEqual(status["next_index"], 12)
            self.assertEqual(status["generator"], "cursor_backed_40_bit_symbol_genome")

    def test_relation_counts_preserve_user_symbol_authority(self):
        symbol_by_anchor, authority_rows = build_source_local_symbol_table(
            ["securecore", "strayword"],
            canonical_symbol_by_anchor={},
            symbol_authority_by_anchor={"securecore": ("0xE000000123", "user_lexicon")},
            source_id="source-1",
        )

        authority_by_anchor = {row["anchor"]: row for row in authority_rows}
        self.assertEqual(symbol_by_anchor["securecore"], "0xE000000123")
        self.assertEqual(authority_by_anchor["securecore"]["authority"], "user_lexicon")
        self.assertRegex(symbol_by_anchor["strayword"], r"^0xF[0-9A-F]{9}$")
        self.assertEqual(authority_by_anchor["strayword"]["authority"], "source_local")

    def test_native_lane_mapping_knows_user_lexicon(self):
        self.assertEqual(_lane_for_authority("canonical"), 0)
        self.assertEqual(_lane_for_authority("user_lexicon"), 5)
        self.assertEqual(_lane_for_authority("source_local"), 4)


if __name__ == "__main__":
    unittest.main()
