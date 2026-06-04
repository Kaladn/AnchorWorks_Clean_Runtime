import unittest

from AnchorWorks.app import create_app


class AnchorWorksCleanCoreResetTests(unittest.TestCase):
    def test_chat_runtime_is_not_installed(self):
        app = create_app()
        routes = {route.path for route in app.routes}

        self.assertFalse(any(route.startswith("/api/chat") for route in routes))
        self.assertFalse(hasattr(app.state, "chat_memory"))

        status = getattr(app.state, "core_runtime_status", {})
        self.assertEqual(status.get("ui_runtime"), "not_installed")
        self.assertEqual(status.get("chat_runtime"), "not_installed")
        self.assertEqual(status.get("memory_runtime"), "not_installed")
        self.assertTrue(status.get("future_port"))


if __name__ == "__main__":
    unittest.main()
