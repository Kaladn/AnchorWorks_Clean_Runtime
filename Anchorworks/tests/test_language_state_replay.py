import unittest
from pathlib import Path

from AnchorWorks.app import create_app
from AnchorWorks.language_state_replay import build_language_state_replay


class LanguageStateReplayTests(unittest.TestCase):
    def test_missing_count_path_is_not_replayable(self):
        replay = build_language_state_replay(
            ["moon", "rocks"],
            {
                "seed_anchors": ["moon", "rocks"],
                "terms": [],
                "answer_path": {"chosen_anchors": [], "steps": []},
                "trace": [],
            },
        )

        self.assertEqual(replay["status"], "missing_state")
        self.assertFalse(replay["render_allowed"])
        self.assertEqual(replay["reconstructed_terms"], [])
        self.assertEqual(replay["reason"], "no_walked_answer_state")

    def test_walked_count_path_is_replayable(self):
        replay = build_language_state_replay(
            ["laws", "physics"],
            {
                "seed_anchors": ["laws", "physics"],
                "terms": [
                    {"anchor": "physics", "supporting_context": ["laws"]},
                    {"anchor": "motion", "supporting_context": ["physics"]},
                    {"anchor": "force", "supporting_context": ["motion"]},
                ],
                "answer_path": {
                    "chosen_anchors": ["physics", "motion", "force"],
                    "steps": [{"chosen_anchor": "physics"}, {"chosen_anchor": "motion"}, {"chosen_anchor": "force"}],
                },
                "trace": [{"step": 1}, {"step": 2}, {"step": 3}],
            },
        )

        self.assertEqual(replay["status"], "replayable")
        self.assertTrue(replay["render_allowed"])
        self.assertEqual(replay["reconstructed_terms"], ["physics", "motion", "force"])
        self.assertEqual(replay["method"], "reverse_language_state_from_walked_count_path")

    def test_clearspeak_exposes_missing_replay_state_for_moon_rocks(self):
        app = create_app(Path(r"D:\AnchorWorks_Clean_Runtime"))
        result = app.state.clearspeak.query("what are moon rocks?", limit=6).to_dict()

        replay = result["answer_assembly"]["state_replay"]
        self.assertEqual(replay["status"], "missing_state")
        self.assertFalse(replay["render_allowed"])
        self.assertIn("replayable count state", result["speech"])


if __name__ == "__main__":
    unittest.main()
