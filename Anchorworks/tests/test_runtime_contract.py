import unittest

from AnchorWorks.app import create_app


class AnchorWorksRuntimeContractTests(unittest.TestCase):
    def test_conversation_runtime_is_installed_without_silent_memory_mutation(self):
        app = create_app()
        routes = {route.path for route in app.routes}

        self.assertIn("/api/chat/send", routes)
        self.assertTrue(hasattr(app.state, "conversation_engine"))

        status = getattr(app.state, "core_runtime_status", {})
        self.assertEqual(status.get("ui_runtime"), "terminal_operator_console")
        self.assertEqual(status.get("chat_runtime"), "conversation_engine")
        self.assertEqual(status.get("memory_runtime"), "awaiting_whiteboard_memory_scaffold")
        self.assertFalse(status.get("silent_memory_writes"))


if __name__ == "__main__":
    unittest.main()
