import json
import unittest
from pathlib import Path

from AnchorWorks.truevision_language.method_boundary import (
    load_truevision_method_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
METHOD_ROOT = ROOT / "external_methods" / "truevision_generation_lab"


class TrueVisionLanguageMethodBoundaryTests(unittest.TestCase):
    def test_method_manifest_keeps_exact_reference_code_out_of_runtime(self):
        manifest = load_truevision_method_manifest(METHOD_ROOT / "METHOD_MANIFEST.json")

        self.assertEqual(manifest["method_name"], "TrueVision Generation Lab")
        self.assertEqual(manifest["authority"], "reference_method_only")
        self.assertTrue(manifest["generated_media_excluded"])
        self.assertTrue(manifest["anchorworks_runtime_imports_disallowed"])
        self.assertIn("capture observed state", manifest["method_chain"][0])
        self.assertIn("SegmentField", manifest["method_chain"][2])

        copied_paths = {item["path"] for item in manifest["copied_sources"]}
        self.assertIn("native_rust_exact_copy/src/main.rs", copied_paths)
        self.assertIn(
            "native_rust_exact_copy/src/bin/trueframegen_stream_rs.rs",
            copied_paths,
        )
        self.assertIn("docs_exact_copy/TECHNICAL_OVERVIEW.md", copied_paths)

    def test_copied_method_files_are_present_and_marked_read_only_reference(self):
        manifest_path = METHOD_ROOT / "METHOD_MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        for item in manifest["copied_sources"]:
            copied = METHOD_ROOT / item["path"]
            self.assertTrue(copied.exists(), item["path"])
            self.assertGreater(copied.stat().st_size, 0, item["path"])
            self.assertEqual(item["use"], "read_only_reference")

    def test_language_branch_doc_names_state_capture_and_not_prompt_generation(self):
        doc = (ROOT / "docs" / "ANCHORWORKS_CURRENT_REALITY.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("glyph-state capture", doc)
        self.assertIn("SegmentField becomes LanguageSegmentField", doc)
        self.assertIn("not prompt generation", doc)
        self.assertIn("No generated video/media artifacts live in AnchorWorks", doc)


if __name__ == "__main__":
    unittest.main()
