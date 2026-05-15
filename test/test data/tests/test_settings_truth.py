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
        html = Path("D:/AnchorWorks_Clean_Runtime/Anchorworks/UI/index.html").read_text(encoding="utf-8")
        js = Path("D:/AnchorWorks_Clean_Runtime/Anchorworks/UI/assets/app.js").read_text(encoding="utf-8")

        self.assertIn("System", html)
        self.assertIn("No auth gate. No dead cockpit.", html)
        self.assertNotIn("Cockpit switches are now active", js)
        self.assertNotIn("Windows Hello", html)

    def test_ui_invoked_surfaces_submit_from_chat_and_delegate_card_actions(self) -> None:
        html = Path("D:/AnchorWorks_Clean_Runtime/Anchorworks/UI/index.html").read_text(encoding="utf-8")
        js = Path("D:/AnchorWorks_Clean_Runtime/Anchorworks/UI/assets/app.js").read_text(encoding="utf-8")

        self.assertIn('id="chat-feed"', html)
        self.assertIn('id="chat-search-form"', html)
        self.assertIn('id="evidence-view"', html)
        self.assertIn("renderWorkbenchActions(result)", js)
        self.assertIn("data-action", js)
        self.assertIn("/api/chat/search", js)
        self.assertIn("continue_working", js)
        self.assertIn("/api/chat/action", js)
        self.assertIn("runWorkbenchAction(\"continue_working\")", js)
        self.assertNotIn("sendChat(\"Continue working.\")", js)
        self.assertIn("target.dataset.action", js)
        self.assertNotIn("CARD_RECIPES", js)

    def test_ui_chat_send_appends_response_without_history_reload_loop(self) -> None:
        html = Path("D:/AnchorWorks_Clean_Runtime/Anchorworks/UI/index.html").read_text(encoding="utf-8")
        js = Path("D:/AnchorWorks_Clean_Runtime/Anchorworks/UI/assets/app.js").read_text(encoding="utf-8")
        css = Path("D:/AnchorWorks_Clean_Runtime/Anchorworks/UI/assets/app.css").read_text(encoding="utf-8")

        self.assertIn('id="chat-form"', html)
        self.assertIn('id="chat-input"', html)
        self.assertIn('/assets/app.css', html)
        self.assertIn('/assets/app.js', html)
        self.assertIn("if (state.sending) return", js)
        self.assertIn("state.sending = true", js)
        self.assertIn("state.sending = false", js)
        self.assertIn("appendAssistantResult(result)", js)
        self.assertIn("/api/chat/send", js)
        self.assertNotIn("await loadChat();", js)
        self.assertIn('grid-template-columns: minmax(0, 1fr) 110px', css)
        self.assertIn('grid-template-columns: 1fr', css)

    def test_ui_chat_surface_uses_backend_workbench_contract(self) -> None:
        js = Path("D:/AnchorWorks_Clean_Runtime/Anchorworks/UI/assets/app.js").read_text(encoding="utf-8")

        self.assertIn("/api/chat/status", js)
        self.assertIn("if (state.sending) return", js)
        self.assertIn("renderWorkbenchActions(result)", js)
        self.assertIn("result?.actions", js)
        self.assertIn("state.lastWorkflow = result.workflow", js)
        self.assertIn("evidence_visible: $(\"#evidence-toggle\").checked", js)
        self.assertIn("data-action", js)
        self.assertIn("hide_evidence", js)

    def test_settings_inventory_route_exposes_truth_labels(self) -> None:
        app = create_app(Path("D:/AnchorWorks_Clean_Runtime"))
        route = next(route for route in app.routes if getattr(route, "path", "") == "/api/settings/inventory")

        payload = route.endpoint()
        self.assertEqual(payload["schema_version"], "anchorworks_settings_inventory@1")
        self.assertTrue(any(row["id"] == "symbol_genome_pool" and row["runtime_active"] for row in payload["settings"]))
        self.assertTrue(any(row["id"] == "tree_brain_controls" and not row["runtime_active"] for row in payload["settings"]))


if __name__ == "__main__":
    unittest.main()
