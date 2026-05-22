import unittest
from pathlib import Path

from AnchorWorks.app import create_app


class QueryRecognitionFrameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app(Path(r"D:\AnchorWorks_Clean_Runtime"))
        cls.store = cls.app.state.store
        cls.clearspeak = cls.app.state.clearspeak

    def test_punctuation_is_direction_not_query_anchor(self):
        recognition = self.store.recognize_query_anchors("what are moon rocks?")

        self.assertEqual(recognition["observed_anchors"], ["what", "are", "moon", "rocks", "?"])
        self.assertEqual(recognition["query_anchors"], ["what", "are", "moon", "rocks"])
        self.assertEqual(recognition["content_anchors"], ["moon", "rocks"])
        self.assertEqual(recognition["punctuation_anchors"], ["?"])
        self.assertIn("what", recognition["direction_anchors"])
        self.assertIn("are", recognition["direction_anchors"])
        self.assertEqual(recognition["input_kind"], "question")

    def test_clearspeak_does_not_use_direction_anchors_as_evidence(self):
        result = self.clearspeak.query("what are moon rocks?", limit=6).to_dict()

        self.assertEqual(result["query_anchors"], ["what", "are", "moon", "rocks"])
        self.assertNotIn("?", result["represented_anchors"])
        self.assertEqual([row["anchor"] for row in result["evidence"]], [])
        self.assertIn("moon", result["speech"])
        self.assertIn("rocks", result["speech"])
        self.assertNotIn("what, are", result["speech"])
        self.assertNotIn("what:", result["response"])
        self.assertNotIn("are:", result["response"])


if __name__ == "__main__":
    unittest.main()
