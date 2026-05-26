import unittest
from pathlib import Path

from AnchorWorks.app import create_app


ROOT = Path(__file__).resolve().parents[1]


class AnchorWorksRulebookDocsTests(unittest.TestCase):
    def test_full_rulebook_contains_core_intake_and_render_laws(self):
        rulebook = ROOT / "docs" / "ANCHORWORKS_INTAKE_RENDER_RULEBOOK.md"
        text = rulebook.read_text(encoding="utf-8")

        required = [
            "Lexicon recognizes.",
            "Counts propose.",
            "Frames aim.",
            "Inference admits.",
            "Renderer speaks.",
            "Top-K is walked, not dumped.",
            "Engagement first.",
            "Vision records state first.",
            "Occular Clouds are visual-symbolic counts, not lifetime word counts.",
            "GPU is execution, not authority.",
            "No generic bridge unless the active relation permits it.",
        ]

        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_first_prompt_is_short_and_contains_nonnegotiable_laws(self):
        primer = ROOT / "docs" / "ANCHORWORKS_AGENT_FIRST_PROMPT.md"
        text = primer.read_text(encoding="utf-8")

        self.assertLessEqual(len(text.splitlines()), 90)
        required = [
            "Read this first before intake or answer generation.",
            "Engagement first.",
            "Top-K is walked, not dumped.",
            "No raw candidates as speech.",
            "No unsupported candidate enters speech.",
            "Normal conversation is not always a question.",
        ]

        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_external_model_lane_sees_agent_first_prompt_first(self):
        app = create_app(Path(r"D:\AnchorWorks_Clean_Runtime"))
        messages = app.state.chat_memory._model_api_messages(branch="main", memory_context={})

        self.assertGreaterEqual(len(messages), 1)
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("Read this first before intake or answer generation.", messages[0]["content"])
        self.assertIn("Top-K is walked, not dumped.", messages[0]["content"])
        self.assertIn("No raw candidates as speech.", messages[0]["content"])


if __name__ == "__main__":
    unittest.main()
