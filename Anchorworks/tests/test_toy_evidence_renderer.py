from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "experiments" / "toy_evidence_renderer" / "run.py"
RUNTIME = REPO_ROOT / "experiments" / "toy_evidence_renderer" / "runtime"


class ToyEvidenceRendererExperimentTests(unittest.TestCase):
    def setUp(self) -> None:
        if RUNTIME.exists():
            shutil.rmtree(RUNTIME)

    def test_build_creates_isolated_binary_evidence_frame_dataset(self) -> None:
        result = subprocess.run(
            [sys.executable, str(RUNNER), "build"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("build_report.json", result.stdout)

        build_report = _read_json(RUNTIME / "reports" / "build_report.json")
        manifest = _read_json(RUNTIME / "reports" / "experiment_manifest.json")
        text_rows = _read_jsonl(RUNTIME / "datasets" / "symbol_frame_to_text.jsonl")
        structured_rows = _read_jsonl(RUNTIME / "datasets" / "symbol_frame_to_structured.jsonl")

        self.assertEqual(build_report["schema_errors"], 0)
        self.assertEqual(build_report["awsc_verify_errors"], 0)
        self.assertGreaterEqual(build_report["supported_rows"], 4)
        self.assertGreaterEqual(build_report["unsupported_rows"], 2)
        self.assertEqual(len(text_rows), build_report["rows_built"])
        self.assertEqual(len(structured_rows), build_report["rows_built"])
        self.assertTrue(any((RUNTIME / "awsm").glob("*.awsm")))
        self.assertTrue((RUNTIME / "awss" / "toy_relations.awss").is_file())
        self.assertTrue(any((RUNTIME / "awsc" / "cells").glob("*/*.cell")))

        blocked_roots = {Path(path).resolve() for path in manifest["isolation"]["blocked_roots"]}
        for output_path in manifest["outputs"]:
            resolved = Path(output_path).resolve()
            self.assertTrue(str(resolved).startswith(str(RUNTIME.resolve())))
            self.assertFalse(any(resolved == root or root in resolved.parents for root in blocked_roots))

    def test_eval_validates_refusals_and_evidence_preservation_without_ml_dependencies(self) -> None:
        subprocess.run([sys.executable, str(RUNNER), "build"], cwd=REPO_ROOT, check=True, capture_output=True, text=True)
        result = subprocess.run(
            [sys.executable, str(RUNNER), "eval"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("eval_report.json", result.stdout)

        eval_report = _read_json(RUNTIME / "reports" / "eval_report.json")
        self.assertEqual(eval_report["schema_errors"], 0)
        self.assertEqual(eval_report["unsupported_answer_leaks"], 0)
        self.assertEqual(eval_report["evidence_preservation_errors"], 0)
        self.assertEqual(eval_report["refusal_accuracy"], 1.0)

    def test_train_skips_cleanly_without_required_model_assets(self) -> None:
        result = subprocess.run(
            [sys.executable, str(RUNNER), "train"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("skipped", result.stdout.lower())


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
