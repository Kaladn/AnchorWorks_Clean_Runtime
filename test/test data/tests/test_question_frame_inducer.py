import unittest

from AnchorWorks.clearspeak_attention import infer_attention_frame
from AnchorWorks.clearspeak_attention import build_active_cloud_frame
from AnchorWorks.question_frame_inducer import default_reasoning_frame_corpus, induce_question_frame


class QuestionFrameInducerTests(unittest.TestCase):
    def test_why_question_produces_causal_frame_without_fact_authority(self):
        frame = induce_question_frame("Why do laws of physics matter?")

        self.assertEqual(frame["frame_type"], "causal_explanation")
        self.assertFalse(frame["fact_answer_authority"])
        self.assertEqual(frame["slots"]["subject"], "do laws of physics matter")
        self.assertIn("Explain why", frame["reasoning_frame"])
        self.assertEqual(frame["support"][0]["pattern"], "why_causal")
        self.assertEqual(default_reasoning_frame_corpus().name, "frame_cloud_rules.json")
        self.assertFalse(frame["support"][0].get("scan_source_corpus_live", False))

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

    def test_active_cloud_uses_learned_frame_candidate_guidance(self):
        count_index = {
            "by_anchor": {
                "physics": {
                    "+1": {
                        "force": 10,
                        "banana": 10,
                    }
                }
            }
        }
        cloud = build_active_cloud_frame(
            count_index,
            question_anchors=["why", "physics", "?"],
            rear_context=[],
            answer_so_far=[],
            forward_context=[],
            top_k=2,
        )

        by_anchor = {row["anchor"]: row for row in cloud["candidates"]}
        self.assertGreater(by_anchor["force"]["learned_frame_guidance"]["boost"], 0)
        self.assertGreater(
            by_anchor["force"]["learned_frame_guidance"]["boost"],
            by_anchor["banana"]["learned_frame_guidance"]["boost"],
        )
        self.assertGreater(by_anchor["force"]["score"], by_anchor["banana"]["score"])


if __name__ == "__main__":
    unittest.main()
