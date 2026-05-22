import tempfile
import unittest
from pathlib import Path

from AnchorWorks.truevision_language.occular_cloud import OccularCloudConfig, build_occular_cloud_counts
from AnchorWorks.truevision_language.occular_tensor_store import (
    build_occular_counts_from_tensor_shard,
    load_occular_tensor_shard,
    write_occular_tensor_shard,
)


class OccularTensorStoreTests(unittest.TestCase):
    def test_tensor_shard_round_trips_to_cpu_counts(self):
        blocks = [
            {
                "block_id": "visual-page-1",
                "symbols": [f"VG{i:03d}" for i in range(72)],
                "source_ref": "doc://visual/page/1",
                "visual_ref": {"state": "state://visual/1"},
            },
            {
                "block_id": "visual-page-2",
                "symbols": [f"VG{i:03d}" for i in range(16)]
                + ["__NULL__", "visual_unknown_glyph", "STRING_LITERAL"]
                + [f"VG{i:03d}" for i in range(16, 82)],
                "count_eligible": [True] * 16 + [True, True, False] + [True] * 66,
                "source_ref": "doc://visual/page/2",
                "visual_ref": {"state": "state://visual/2"},
            },
        ]
        config = OccularCloudConfig(context_clouds_each_side=6, context_cloud_size=4, center_size=4)

        with tempfile.TemporaryDirectory() as tmpdir:
            written = write_occular_tensor_shard(
                root=Path(tmpdir),
                shard_id="unit-shard",
                blocks=blocks,
                config=config,
                backend="cpu",
            )
            loaded = load_occular_tensor_shard(Path(written["manifest_path"]))
            rebuilt = build_occular_counts_from_tensor_shard(loaded)
            cpu = build_occular_cloud_counts(blocks=blocks, config=config)

        self.assertEqual(written["schema_version"], "anchorworks_occular_tensor_shard_write@1")
        self.assertEqual(loaded["manifest"]["schema_version"], "anchorworks_occular_tensor_shard_manifest@1")
        self.assertEqual(loaded["arrays"]["center_windows"].shape[1], 4)
        self.assertEqual(loaded["arrays"]["left_context"].shape[1:], (6, 4))
        self.assertEqual(loaded["arrays"]["right_context"].shape[1:], (6, 4))
        self.assertEqual(rebuilt, cpu)

    def test_tensor_shard_manifest_blocks_writes_to_authority_lanes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            written = write_occular_tensor_shard(
                root=Path(tmpdir),
                shard_id="write-boundary",
                blocks=[{"block_id": "visual-page-1", "symbols": [f"VG{i:03d}" for i in range(60)]}],
                config=OccularCloudConfig(),
                backend="cpu",
            )
            loaded = load_occular_tensor_shard(Path(written["manifest_path"]))

        self.assertEqual(
            loaded["manifest"]["writes_allowed"],
            {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
        )
        self.assertTrue(loaded["manifest"]["truth_boundary"]["gpu_execution_not_authority"])


if __name__ == "__main__":
    unittest.main()
