from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from AnchorWorks.code_lexicon_mirror import (
    build_code_lexicon_mirror,
    identifier_anchor_stream,
    write_code_lexicon_mirror,
)


class CodeLexiconMirrorTests(unittest.TestCase):
    def test_identifier_anchor_stream_uses_regular_anchor_rules(self):
        self.assertEqual(identifier_anchor_stream("HTTPServerID2"), ["h", "t", "t", "p", "server", "i", "d", "2"])
        self.assertEqual(identifier_anchor_stream("edge_state_intake"), ["edge", "state", "intake"])
        self.assertEqual(identifier_anchor_stream("GPU2DWorker"), ["g", "p", "u", "2", "d", "worker"])

    def test_builds_python_and_rust_identifier_mirror_without_live_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            aw = root / "AnchorWorks"
            sc = root / "SecureCore"
            tv = root / "TrueVision"
            aw.mkdir()
            sc.mkdir()
            tv.mkdir()
            (aw / "alpha.py").write_text(
                "class EdgeStateReceiver:\n"
                "    def ingest_HTTP_packet(self, userID2):\n"
                "        local_count = userID2\n"
                "        self.lastReceipt = local_count\n",
                encoding="utf-8",
            )
            (sc / "main.rs").write_text(
                "struct ForgeWriter { sequence_id: u64 }\n"
                "fn build_GPU_state(mut windowCount: usize) { let edgeState = windowCount; }\n",
                encoding="utf-8",
            )
            (tv / "ignored.txt").write_text("not code", encoding="utf-8")

            mirror = build_code_lexicon_mirror({"anchorworks": aw, "securecore": sc, "truevision": tv})

            self.assertEqual(mirror["schema_version"], "anchorworks_code_lexicon_mirror@1")
            self.assertEqual(mirror["kind"], "code_lexicon_mirror")
            self.assertEqual(mirror["writes_allowed"], {
                "canonical": False,
                "structural": False,
                "lexicon": False,
                "counts": False,
                "lifetime": False,
            })
            self.assertEqual(mirror["source_repo_count"], 3)
            self.assertIn("python", mirror["languages"] )
            self.assertIn("rust", mirror["languages"] )
            identifiers = {entry["identifier"] for entry in mirror["entries"]}
            self.assertIn("EdgeStateReceiver", identifiers)
            self.assertIn("ingest_HTTP_packet", identifiers)
            self.assertIn("ForgeWriter", identifiers)
            self.assertIn("build_GPU_state", identifiers)
            self.assertNotIn("ignored", identifiers)

            entry = next(row for row in mirror["entries"] if row["identifier"] == "ingest_HTTP_packet")
            self.assertEqual(entry["anchor_stream"], ["ingest", "h", "t", "t", "p", "packet"])
            self.assertTrue(entry["mirror_only"])
            self.assertFalse(entry["live_lexicon_entry"])

    def test_write_mirror_writes_only_mirror_and_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()
            (repo / "tool.py").write_text("def run_tool(toolID):\n    return toolID\n", encoding="utf-8")
            out_root = root / "state"

            result = write_code_lexicon_mirror({"one": repo}, output_root=out_root)

            mirror_path = Path(result["mirror_path"])
            receipt_path = Path(result["receipt_path"])
            self.assertTrue(mirror_path.exists())
            self.assertTrue(receipt_path.exists())
            mirror = json.loads(mirror_path.read_text(encoding="utf-8"))
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(receipt["mirror_sha256"], mirror["mirror_sha256"] )
            self.assertEqual(receipt["writes_performed"], ["mirror", "receipt"] )
            self.assertEqual(receipt["forbidden_writes"], ["canonical", "structural", "lexicon", "counts", "lifetime"] )


if __name__ == "__main__":
    unittest.main()
