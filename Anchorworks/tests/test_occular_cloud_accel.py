import unittest
from pathlib import Path
import tempfile

from AnchorWorks.truevision_language.occular_cloud import OccularCloudConfig, build_occular_cloud_counts
from AnchorWorks.truevision_language.occular_cloud_accel import (
    build_occular_cloud_counts_accelerated,
    probe_occular_cloud_backends,
)


class OccularCloudAccelTests(unittest.TestCase):
    def test_accelerated_counts_match_cpu_payload_exactly(self):
        blocks = [
            {
                "block_id": "visual-page-1",
                "symbols": [f"VG{i:03d}" for i in range(72)],
                "source_ref": "doc://synthetic/page/1",
                "visual_ref": {"state_record": "state://synthetic/1"},
            },
            {
                "block_id": "visual-page-2",
                "symbols": [f"VG{i:03d}" for i in range(16)]
                + ["__NULL__", "visual_unknown_glyph", "STRING_LITERAL"]
                + [f"VG{i:03d}" for i in range(16, 82)],
                "count_eligible": [True] * 16 + [True, True, False] + [True] * 66,
                "source_ref": "doc://synthetic/page/2",
                "visual_ref": {"state_record": "state://synthetic/2"},
            },
        ]
        config = OccularCloudConfig(context_clouds_each_side=6, context_cloud_size=4, center_size=4)

        cpu = build_occular_cloud_counts(blocks=blocks, config=config)
        accelerated = build_occular_cloud_counts_accelerated(blocks=blocks, config=config, backend="auto")

        self.assertEqual(accelerated["counts_payload"], cpu)
        self.assertEqual(accelerated["execution"]["window_shape"], "6x4-4-6x4")
        self.assertIn(accelerated["execution"]["backend"], {"cpu", "cuda", "openvino", "oneapi"})
        self.assertEqual(accelerated["execution"]["input_hash"], accelerated["execution"]["determinism"]["input_hash"])
        self.assertEqual(accelerated["execution"]["output_hash"], accelerated["execution"]["determinism"]["output_hash"])

    def test_accelerated_run_can_write_tensor_shard_receipt(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            accelerated = build_occular_cloud_counts_accelerated(
                blocks=[{"block_id": "visual-page-1", "symbols": [f"VG{i:03d}" for i in range(72)]}],
                backend="auto",
                tensor_store_root=Path(tmpdir),
                tensor_shard_id="accel-unit",
            )

        tensor_store = accelerated["execution"]["tensor_store"]
        self.assertTrue(tensor_store["written"])
        self.assertEqual(tensor_store["shard_id"], "accel-unit")
        self.assertIn("manifest_path", tensor_store)
        self.assertIn("tensor_sha256", tensor_store)

    def test_forced_unavailable_gpu_backend_falls_back_to_cpu_with_reason(self):
        result = build_occular_cloud_counts_accelerated(
            blocks=[{"block_id": "visual-page-1", "symbols": [f"VG{i:03d}" for i in range(60)]}],
            backend="cuda",
        )

        if result["execution"]["backend"] == "cpu":
            self.assertTrue(result["execution"]["fallback_used"])
            self.assertIn("cuda", result["execution"]["fallback_reason"].lower())

    def test_backend_probe_reports_python_and_device_visibility(self):
        probe = probe_occular_cloud_backends()

        self.assertEqual(probe["schema_version"], "anchorworks_occular_cloud_backend_probe@1")
        self.assertIn("python", probe)
        self.assertIn("torch", probe["backends"])
        self.assertIn("openvino", probe["backends"])


if __name__ == "__main__":
    unittest.main()
