import unittest

from aw_inference_kernel import run_inference


class AWInferenceCandidateWalkTests(unittest.TestCase):
    def test_counts_candidates_are_walked_not_dumped(self):
        plan = run_inference(
            "why worry about laws of physics?",
            ["why", "worry", "laws", "physics"],
            {
                "terms": [
                    {
                        "anchor": "mother",
                        "score": 1.0,
                        "candidate_rank": 1,
                        "supporting_context": ["children", "mothers"],
                    },
                    {
                        "anchor": "gravity",
                        "score": 0.99,
                        "candidate_rank": 2,
                        "supporting_context": ["earth"],
                    },
                    {
                        "anchor": "physics",
                        "score": 0.95,
                        "candidate_rank": 3,
                        "supporting_context": ["laws", "physics"],
                    },
                    {
                        "anchor": "motion",
                        "score": 0.80,
                        "candidate_rank": 4,
                        "supporting_context": ["physics", "laws"],
                    },
                    {
                        "anchor": "force",
                        "score": 0.70,
                        "candidate_rank": 5,
                        "supporting_context": ["motion"],
                    },
                    {
                        "anchor": "because",
                        "score": 0.99,
                        "candidate_rank": 6,
                        "supporting_context": ["physics"],
                        "rejected_reason": "glue_as_content",
                    },
                ],
            },
            mode="counts",
        )

        accepted = [row["anchor"] for row in plan["accepted_candidates"]]
        rejected = {row["anchor"]: row["reason"] for row in plan["rejected_candidates"]}
        walk_steps = [
            step for step in plan["inference_steps"]
            if step["rule_id"] == "R_ACTIVE_CLOUD_WALK_SELECT"
            and step["decision"] == "accept"
        ]

        self.assertEqual(accepted, ["physics", "motion", "force"])
        self.assertEqual(rejected["mother"], "off_frame_domain")
        self.assertEqual(rejected["gravity"], "no_active_cloud_fit")
        self.assertEqual(rejected["because"], "glue_as_content")
        self.assertEqual([step["inputs_used"][0] for step in walk_steps], accepted)
        self.assertNotIn("mother", plan["direct_answer"])
        self.assertNotIn("gravity", plan["direct_answer"])
        self.assertNotIn("because", plan["direct_answer"])
        self.assertTrue(plan["contract"]["topk_walked"])


if __name__ == "__main__":
    unittest.main()
