import unittest

from AnchorWorks.clearspeak_attention import infer_attention_frame
from AnchorWorks.question_frame_inducer import induce_question_frame


class QuestionFrameInducerTests(unittest.TestCase):
    def test_why_question_produces_causal_frame_without_fact_authority(self):
        frame = induce_question_frame("Why do laws of physics matter?")

        self.assertEqual(frame["frame_type"], "causal_explanation")
        self.assertFalse(frame["fact_answer_authority"])
        self.assertEqual(frame["slots"]["subject"], "do laws of physics matter")
        self.assertIn("Explain why", frame["reasoning_frame"])
        self.assertEqual(frame["support"][0]["pattern"], "why_causal")

    def test_compare_question_extracts_two_slots(self):
        frame = induce_question_frame("Compare mass and weight")

        self.assertEqual(frame["frame_type"], "comparison")
        self.assertEqual(frame["slots"]["left"], "mass")
        self.assertEqual(frame["slots"]["right"], "weight")
        self.assertFalse(frame["fact_answer_authority"])

    def test_attention_frame_carries_learned_frame_guidance(self):
        frame = infer_attention_frame(["why", "laws", "physics", "?"])

        learned = frame["learned_question_frame"]
        self.assertEqual(learned["schema_version"], "anchorworks_question_frame_inducer@1")
        self.assertEqual(learned["frame_type"], "causal_explanation")
        self.assertFalse(learned["fact_answer_authority"])
        self.assertFalse(learned["writes_allowed"]["counts"])


if __name__ == "__main__":
    unittest.main()
