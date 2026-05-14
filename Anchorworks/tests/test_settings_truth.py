import unittest
from pathlib import Path

from AnchorWorks.settings_inventory import build_settings_inventory
from AnchorWorks.app import create_app


class SettingsTruthTests(unittest.TestCase):
    def test_settings_inventory_marks_runtime_vs_diagnostic_surfaces(self) -> None:
        inventory = build_settings_inventory(Path("D:/AnchorWorks_Clean_Runtime/Anchorworks"))
        by_id = {row["id"]: row for row in inventory["settings"]}

        self.assertEqual(by_id["tree_brain_controls"]["classification"], "diagnostic_only")
        self.assertFalse(by_id["tree_brain_controls"]["runtime_active"])
        self.assertIn("not wired", by_id["tree_brain_controls"]["reason"])

        self.assertEqual(by_id["symbol_policy"]["classification"], "diagnostic_policy")
        self.assertFalse(by_id["symbol_policy"]["runtime_active"])

        self.assertEqual(by_id["symbol_genome_pool"]["classification"], "runtime")
        self.assertTrue(by_id["symbol_genome_pool"]["runtime_active"])

    def test_ui_labels_unwired_controls_as_diagnostic_only(self) -> None:
        html = Path("D:/AnchorWorks_Clean_Runtime/Anchorworks/src/AnchorWorks/ui/index.html").read_text(encoding="utf-8")
        js = Path("D:/AnchorWorks_Clean_Runtime/Anchorworks/src/AnchorWorks/ui/app.js").read_text(encoding="utf-8")

        self.assertIn("Settings + Diagnostics", html)
        self.assertIn("Diagnostic-only", html)
        self.assertNotIn("Cockpit switches are now active", js)
        self.assertIn("diagnostic-only", js)

    def test_settings_inventory_route_exposes_truth_labels(self) -> None:
        app = create_app(Path("D:/AnchorWorks_Clean_Runtime"))
        route = next(route for route in app.routes if getattr(route, "path", "") == "/api/settings/inventory")

        payload = route.endpoint()
        self.assertEqual(payload["schema_version"], "anchorworks_settings_inventory@1")
        self.assertTrue(any(row["id"] == "symbol_genome_pool" and row["runtime_active"] for row in payload["settings"]))
        self.assertTrue(any(row["id"] == "tree_brain_controls" and not row["runtime_active"] for row in payload["settings"]))


if __name__ == "__main__":
    unittest.main()
