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
        html = Path("D:/AnchorWorks_Clean_Runtime/Anchorworks/UI2/index.html").read_text(encoding="utf-8")
        js = Path("D:/AnchorWorks_Clean_Runtime/Anchorworks/UI2/assets/app.js").read_text(encoding="utf-8")

        self.assertIn("System", html)
        self.assertIn("diagnostic-only", html)
        self.assertNotIn("Cockpit switches are now active", js)
        self.assertIn("diagnostic-only", js)

    def test_ui2_invoked_surfaces_submit_from_chat_and_delegate_card_actions(self) -> None:
        html = Path("D:/AnchorWorks_Clean_Runtime/Anchorworks/UI2/index.html").read_text(encoding="utf-8")
        js = Path("D:/AnchorWorks_Clean_Runtime/Anchorworks/UI2/assets/app.js").read_text(encoding="utf-8")

        self.assertIn('id="invoked-card-panel"', html)
        self.assertIn('id="dismiss-invoked-card"', html)
        self.assertIn("CARD_RECIPES", js)
        self.assertIn("matchInvokedSurface(message)", js)
        self.assertIn("open system status", js)
        self.assertIn("text === 'evidence'", js)
        self.assertIn("requestSubmit()", js)
        self.assertIn("event.key === 'Enter' && !event.shiftKey", js)
        self.assertIn("event.target.closest('[data-action]')", js)
        self.assertIn("runUiAction(button.dataset.action)", js)

    def test_ui2_chat_send_appends_response_without_history_reload_loop(self) -> None:
        html = Path("D:/AnchorWorks_Clean_Runtime/Anchorworks/UI2/index.html").read_text(encoding="utf-8")
        js = Path("D:/AnchorWorks_Clean_Runtime/Anchorworks/UI2/assets/app.js").read_text(encoding="utf-8")
        css = Path("D:/AnchorWorks_Clean_Runtime/Anchorworks/UI2/assets/app.css").read_text(encoding="utf-8")

        self.assertIn('id="send-chat"', html)
        self.assertIn('data-action="send"', html)
        self.assertIn('/assets/app.css?v=ui2-backend-wire1', html)
        self.assertIn('/assets/app.js?v=ui2-backend-wire6', html)
        self.assertIn("if (state.sending) return", js)
        self.assertIn("setSending(true)", js)
        self.assertIn("setSending(false)", js)
        self.assertIn("$('send-chat').addEventListener('pointerdown', submitChatFromButton)", js)
        self.assertIn("$('send-chat').addEventListener('click', submitChatFromButton)", js)
        self.assertIn("if (action === 'send') submitChatFromButton", js)
        self.assertIn("appendLocalChatRow('user'", js)
        self.assertIn("appendLocalChatRow('assistant'", js)
        self.assertIn("assistantTextFromPayload(payload)", js)
        self.assertNotIn("await loadChat();", js)
        self.assertIn('grid-template-columns: minmax(150px, 1fr) auto auto', css)
        self.assertIn('grid-column: 1 / -1', css)

    def test_ui2_chat_surface_uses_backend_workbench_contract(self) -> None:
        js = Path("D:/AnchorWorks_Clean_Runtime/Anchorworks/UI2/assets/app.js").read_text(encoding="utf-8")

        self.assertIn("/api/chat/status", js)
        self.assertIn("if (state.sending || state.lastWorkflow) return", js)
        self.assertIn("renderWorkbench(payload)", js)
        self.assertIn("payload.actions", js)
        self.assertIn("payload.workflow", js)
        self.assertIn("evidence_visible: $('show-evidence').checked", js)
        self.assertIn("data-workbench-action", js)
        self.assertIn("toggle_evidence", js)

    def test_settings_inventory_route_exposes_truth_labels(self) -> None:
        app = create_app(Path("D:/AnchorWorks_Clean_Runtime"))
        route = next(route for route in app.routes if getattr(route, "path", "") == "/api/settings/inventory")

        payload = route.endpoint()
        self.assertEqual(payload["schema_version"], "anchorworks_settings_inventory@1")
        self.assertTrue(any(row["id"] == "symbol_genome_pool" and row["runtime_active"] for row in payload["settings"]))
        self.assertTrue(any(row["id"] == "tree_brain_controls" and not row["runtime_active"] for row in payload["settings"]))


if __name__ == "__main__":
    unittest.main()
