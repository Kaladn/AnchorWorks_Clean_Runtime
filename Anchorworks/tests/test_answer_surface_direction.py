import unittest

from AnchorWorks.answer_surface import render_anchor_answer_surface


class AnswerSurfaceDirectionalWordTests(unittest.TestCase):
    def test_default_count_renderer_does_not_use_involves_as_directional_fallback(self):
        speech = render_anchor_answer_surface(
            ["what", "is", "truevision"],
            {
                "terms": [
                    {"anchor": "state"},
                    {"anchor": "glyph"},
                    {"anchor": "visual"},
                    {"anchor": "preserves"},
                ],
                "answer_path": {"chosen_anchors": ["state", "glyph", "visual", "preserves"]},
            },
            fallback_subjects=["truevision"],
            source_label="count path",
        )

        self.assertNotIn("involves", speech.casefold())
        self.assertIn("truevision", speech.casefold())
        self.assertIn("state", speech.casefold())


if __name__ == "__main__":
    unittest.main()
