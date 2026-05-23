import tempfile
import unittest
from pathlib import Path

from AnchorWorks.truevision_language.occular_cloud import OccularCloudConfig
from AnchorWorks.truevision_language.occular_tensor_index import (
    build_occular_shard_index,
    query_occular_tensor_cloud,
)
from AnchorWorks.truevision_language.occular_tensor_store import write_occular_tensor_shard


class OccularTensorIndexTests(unittest.TestCase):
    def test_builds_index_from_tensor_shard_manifests(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            written = write_occular_tensor_shard(
                root=root,
                shard_id="index-unit",
                blocks=[
                    {
                        "block_id": "visual-page-1",
                        "symbols": [f"VG{i:04d}" for i in range(80)],
                        "source_ref": "doc://visual/page/1",
                        "visual_ref": {"state": "state://visual/1"},
                    }
                ],
                config=OccularCloudConfig(),
                backend="openvino",
            )

            index = build_occular_shard_index(
                root=root,
                manifest_paths=[Path(written["manifest_path"])],
                recognition_grade="synthetic_page",
            )

        self.assertEqual(index["schema_version"], "anchorworks_occular_tensor_shard_index@1")
        self.assertEqual(index["record_count"], 1)
        record = index["records"][0]
        self.assertEqual(record["shard_id"], "index-unit")
        self.assertEqual(record["backend"], "openvino")
        self.assertEqual(record["source_ids"], ["doc://visual/page/1"])
        self.assertEqual(record["symbol_count"], 81)
        self.assertEqual(record["window_count"], 29)
        self.assertEqual(record["unique_center_count"], 29)
        self.assertEqual(record["recognition_grade"], "synthetic_page")

    def test_query_matches_center_and_context_without_loading_unrelated_shards(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wanted = write_occular_tensor_shard(
                root=root,
                shard_id="wanted",
                blocks=[{"block_id": "wanted-block", "symbols": [f"VG{i:04d}" for i in range(96)]}],
                config=OccularCloudConfig(),
                backend="openvino",
            )
            other = write_occular_tensor_shard(
                root=root,
                shard_id="other",
                blocks=[{"block_id": "other-block", "symbols": [f"OTHER{i:04d}" for i in range(96)]}],
                config=OccularCloudConfig(),
                backend="cpu",
            )
            build_occular_shard_index(
                root=root,
                manifest_paths=[Path(wanted["manifest_path"]), Path(other["manifest_path"])],
            )

            query = query_occular_tensor_cloud(
                root=root,
                query_symbols=["VG0024", "VG0025", "VG0026", "VG0027"],
                top_k=5,
                write_receipt=True,
            )
            receipt_exists = Path(query["receipt_path"]).exists()

        self.assertEqual(query["schema_version"], "anchorworks_occular_tensor_query@1")
        self.assertEqual(query["loaded_shard_ids"], ["wanted"])
        self.assertEqual(query["skipped_shard_ids"], ["other"])
        self.assertEqual(query["top_k"][0]["center_symbols"], ["VG0024", "VG0025", "VG0026", "VG0027"])
        self.assertEqual(query["top_k"][0]["score"], 1.0)
        self.assertTrue(receipt_exists)
        self.assertEqual(query["writes_allowed"], {"maps": False, "counts": False, "lifetime": False, "lexicon": False})


if __name__ == "__main__":
    unittest.main()
