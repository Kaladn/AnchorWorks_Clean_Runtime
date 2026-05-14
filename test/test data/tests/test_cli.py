from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _anchorworks_repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent if (parent / "src" / "AnchorWorks").exists() else parent / "Anchorworks"
        if (candidate / "src" / "AnchorWorks").exists():
            return candidate
    raise RuntimeError("Anchorworks repo root not found")


class AnchorWorksCliTests(unittest.TestCase):
    def test_symbolic_batch_intake_cli_runs_with_process_workers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            data_root = temp_root / "LexicalData"
            source_dir = temp_root / "source_docs"
            map_root = temp_root / "AnchorMaps"
            source_dir.mkdir(parents=True)
            _write_json(data_root / "Canonical" / "canonical_A.json", [{"word": "alpha", "hex": "0x0000000001"}])
            _write_json(data_root / "Canonical" / "canonical_B.json", [{"word": "beta", "hex": "0x0000000002"}])
            _write_json(data_root / "Structural" / "structural.json", [{"word": ".", "status": "STRUCTURAL"}])
            _write_json(data_root / "Spare_Slots" / "spare_slots.json", [])
            (source_dir / "one.txt").write_text("alpha beta \u2192 alpha.", encoding="utf-8")
            (source_dir / "two.txt").write_text("beta alpha.", encoding="utf-8")

            env = os.environ.copy()
            env["PYTHONPATH"] = "src"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "AnchorWorks.cli",
                    "symbolic-batch-intake",
                    "--data-root",
                    str(data_root),
                    "--source-dir",
                    str(source_dir),
                    "--pattern",
                    "*.txt",
                    "--map-root",
                    str(map_root),
                    "--max-workers",
                    "2",
                    "--generation",
                    "17",
                ],
                cwd=_anchorworks_repo_root(),
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(completed.stdout)

            self.assertTrue(payload["ok"])
            self.assertEqual(payload["source_count"], 2)
            self.assertEqual(payload["max_workers_used"], 2)
            self.assertEqual(payload["map_root"], str((map_root / "observed_maps").resolve()))
            self.assertEqual(payload["map_count"], 2)
            self.assertTrue(payload["binary"]["ok"])


if __name__ == "__main__":
    unittest.main()
