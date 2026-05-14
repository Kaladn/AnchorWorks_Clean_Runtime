from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from AnchorWorks.intake import build_anchor_map
from AnchorWorks.positional_resonance import build_source_local_resonance_index
from AnchorWorks.store import LexiconStore


class PositionalResonanceTests(unittest.TestCase):
    def test_resonance_index_splits_occurrence_proof_from_cloud_guidance(self) -> None:
        observed_map = build_anchor_map("basement creatures basement evil basement creatures")
        observed_map["source_name"] = "basement.txt"
        observed_map["source_path"] = "source/basement.txt"

        index = build_source_local_resonance_index(observed_map, cloud_threshold=0.3, top_k=8)

        self.assertEqual(len(index["occurrences"]), 6)
        self.assertTrue(all(row["evidence_eligible"] for row in index["occurrences"]))
        self.assertTrue(all(not row["speak_eligible"] for row in index["occurrences"]))
        self.assertTrue(all(row["locator"]["source"] == "basement.txt" for row in index["occurrences"]))
        self.assertTrue(any(row["locator"]["line_reason"] for row in index["occurrences"]))

        basement_profiles = [
            row
            for row in index["positional_profiles"]
            if row["center_anchor"] == "basement" and row["neighbor_anchor"] == "creatures"
        ]
        self.assertTrue(basement_profiles)
        self.assertTrue(all(row["retrieval_eligible"] for row in basement_profiles))
        self.assertTrue(all(not row["evidence_eligible"] for row in basement_profiles))

        basement_cloud = next(row for row in index["context_clouds"] if row["center_anchor"] == "basement")
        self.assertTrue(any(member["anchor"] == "creatures" for member in basement_cloud["members"]))
        self.assertFalse(basement_cloud["evidence_eligible"])
        self.assertFalse(basement_cloud["speak_eligible"])
        self.assertEqual(index["summary"]["writes_allowed"]["lifetime"], False)

    def test_directional_resonance_is_deterministic_and_non_citing(self) -> None:
        observed_map = build_anchor_map("alpha beta alpha beta alpha gamma")
        observed_map["source_name"] = "direction.txt"
        observed_map["source_path"] = "source/direction.txt"

        first = build_source_local_resonance_index(observed_map)
        second = build_source_local_resonance_index(observed_map)

        self.assertEqual(first["directional_resonance"], second["directional_resonance"])
        alpha_to_beta = next(
            row
            for row in first["directional_resonance"]
            if row["from_anchor"] == "alpha" and row["to_anchor"] == "beta"
        )
        self.assertGreater(alpha_to_beta["directional_score"], 0)
        self.assertTrue(alpha_to_beta["retrieval_eligible"])
        self.assertFalse(alpha_to_beta["evidence_eligible"])

    def test_store_writes_source_local_resonance_files_without_lifetime_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            source = Path(temp_dir) / "basement.txt"
            source.write_text("basement creatures basement evil basement creatures", encoding="utf-8")
            store = LexiconStore(root)

            mapped = store.build_observed_map(source)
            built = store.build_source_local_resonance(mapped["saved_map_name"])

            expected_paths = [
                Path(built["occurrence_path"]),
                Path(built["positional_profiles_path"]),
                Path(built["directional_resonance_path"]),
                Path(built["context_clouds_path"]),
                Path(built["summary_path"]),
            ]
            self.assertTrue(all(path.exists() for path in expected_paths))
            self.assertEqual(built["writes_allowed"]["lifetime"], False)
            self.assertEqual(built["authority"], "source_local_retrieval_shape")
            self.assertGreater(built["occurrence_records"], 0)
            self.assertGreater(built["positional_profile_rows"], 0)
            self.assertGreater(built["context_cloud_rows"], 0)

            summary = json.loads(Path(built["summary_path"]).read_text(encoding="utf-8"))
            self.assertEqual(summary["observed_map_name"], mapped["saved_map_name"])
            self.assertEqual(summary["writes_allowed"]["counts"], False)
            self.assertIn("Resonance finds neighborhoods", summary["law"])


if __name__ == "__main__":
    unittest.main()
