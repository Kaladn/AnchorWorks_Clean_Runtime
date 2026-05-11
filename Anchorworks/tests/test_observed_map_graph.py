from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

from AnchorWorks.app import create_app


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "experiments" / "observed_map_graph" / "run.py"
RUNTIME = REPO_ROOT / "experiments" / "observed_map_graph" / "runtime"


class ObservedMapGraphExperimentTests(unittest.TestCase):
    def setUp(self) -> None:
        if RUNTIME.exists():
            shutil.rmtree(RUNTIME)

    def test_build_writes_isolated_awsg_proof(self) -> None:
        result = subprocess.run(
            [sys.executable, str(RUNNER), "build"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("build_report.json", result.stdout)

        build_report = _read_json(RUNTIME / "reports" / "build_report.json")
        manifest = _read_json(RUNTIME / "graph" / "graph_manifest.json")
        nodes = _read_jsonl(RUNTIME / "graph" / "nodes.jsonl")
        edges = _read_jsonl(RUNTIME / "graph" / "edges.jsonl")
        export = _read_json(RUNTIME / "exports" / "observed-map-debug-export.json")

        self.assertEqual(build_report["schema_errors"], 0)
        self.assertEqual(build_report["production_write_errors"], 0)
        self.assertTrue(build_report["debug_export_written"])
        self.assertEqual(manifest["writes_allowed"], {"canonical": False, "counts": False, "lifetime": False, "lexicon": False})

        required_node_types = {"document", "block", "line", "occurrence", "symbol", "null_coordinate", "visual_ref"}
        required_edge_types = {
            "contains_block",
            "contains_line",
            "contains_occurrence",
            "resolves_to_symbol",
            "relation_window",
            "has_null",
            "has_visual_ref",
        }
        self.assertTrue(required_node_types.issubset({node["node_type"] for node in nodes}))
        self.assertTrue(required_edge_types.issubset({edge["edge_type"] for edge in edges}))

        blocked_roots = {Path(path).resolve() for path in manifest["blocked_roots"]}
        for output_path in manifest["outputs"]:
            resolved = Path(output_path).resolve()
            self.assertTrue(str(resolved).startswith(str(RUNTIME.resolve())))
            self.assertFalse(any(resolved == root or root in resolved.parents for root in blocked_roots))

        self.assertIn("source", export)
        self.assertTrue(export["blocks"])
        self.assertTrue(export["lines"])
        self.assertTrue(export["occurrences"])
        self.assertTrue(export["symbols"])
        self.assertTrue(export["relation_windows"])
        self.assertTrue(export["null_coordinates"])
        self.assertTrue(export["visual_refs"])

    def test_eval_validates_graph_contract(self) -> None:
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
        self.assertEqual(eval_report["production_write_errors"], 0)
        self.assertEqual(eval_report["missing_node_types"], [])
        self.assertEqual(eval_report["missing_edge_types"], [])
        self.assertTrue(eval_report["debug_export_written"])

    def test_viewer_routes_list_graphs_and_return_capped_slice(self) -> None:
        subprocess.run([sys.executable, str(RUNNER), "build"], cwd=REPO_ROOT, check=True, capture_output=True, text=True)
        app = create_app(REPO_ROOT.parent)
        paths = {getattr(route, "path", ""): route.endpoint for route in app.routes if hasattr(route, "endpoint")}

        listing = paths["/api/awsg/graphs"]()
        self.assertTrue(listing["ok"])
        self.assertEqual(listing["graph_count"], 1)

        graph_name = listing["graphs"][0]["graph_name"]
        summary = paths["/api/awsg/graph/{graph_name}"](graph_name)
        self.assertTrue(summary["ok"])
        self.assertGreater(summary["node_count"], 0)
        self.assertGreater(summary["edge_count"], 0)
        self.assertEqual(summary["writes_allowed"], {"canonical": False, "counts": False, "lifetime": False, "lexicon": False})

        graph_slice = paths["/api/awsg/graph/{graph_name}/slice"](graph_name, node_id="", radius=1, limit=12)
        self.assertTrue(graph_slice["ok"])
        self.assertLessEqual(len(graph_slice["nodes"]), 12)
        self.assertTrue(graph_slice["nodes"])
        self.assertTrue(graph_slice["edges"])
        self.assertTrue(graph_slice["slice"]["read_only"])
        self.assertIn("document", {node["node_type"] for node in graph_slice["nodes"]})

    def test_viewer_ui_exposes_source_graph_workbench(self) -> None:
        ui_root = REPO_ROOT / "src" / "AnchorWorks" / "ui"
        index_html = (ui_root / "index.html").read_text(encoding="utf-8")
        app_js = (ui_root / "app.js").read_text(encoding="utf-8")

        self.assertIn("Source Graphs", index_html)
        self.assertIn('id="source-graphs-btn"', index_html)
        self.assertIn("/api/awsg/graphs", app_js)
        self.assertIn("/api/awsg/graph/", app_js)
        self.assertIn("renderSourceGraphSlice", app_js)


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


if __name__ == "__main__":
    unittest.main()
