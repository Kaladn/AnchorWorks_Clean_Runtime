import unittest
from pathlib import Path

from AnchorWorks.app import create_app


class ConversationInputTypeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app(Path(r"D:\AnchorWorks_Clean_Runtime"))
        cls.store = cls.app.state.store
        cls.clearspeak = cls.app.state.clearspeak

    def test_non_question_info_transfer_is_not_forced_into_count_answer(self):
        recognition = self.store.recognize_query_anchors(
            "now keep in mind that we talk, not everything is a question"
        )

        self.assertEqual(recognition["input_kind"], "info_transfer")

    def test_clearspeak_acknowledges_info_transfer_without_count_walk(self):
        result = self.clearspeak.query(
            "now keep in mind that we talk, not everything is a question"
        ).to_dict()

        self.assertEqual(result["lexicon_recognition"]["input_kind"], "info_transfer")
        self.assertEqual(result["answer_assembly"]["stop_reason"], "info_transfer")
        self.assertEqual(result["answer_assembly"].get("terms"), [])
        self.assertIn("context", result["speech"].casefold())

    def test_user_correction_is_detected_as_correction_not_question(self):
        recognition = self.store.recognize_query_anchors("no, that is not correct")

        self.assertEqual(recognition["input_kind"], "correction")


if __name__ == "__main__":
    unittest.main()
