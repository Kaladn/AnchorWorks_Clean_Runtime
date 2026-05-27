import unittest
from pathlib import Path

from AnchorWorks.app import create_app
from AnchorWorks.grounded_mode import build_grounded_evidence_packet, render_grounded_result


class GroundedModeTests(unittest.TestCase):
    def test_evidence_packet_keeps_counts_and_documents_as_refs_not_authority_writes(self):
        packet = build_grounded_evidence_packet(
            query="what is truevision?",
            clearspeak_payload={
                "represented_anchors": ["truevision"],
                "missing_anchors": [],
                "speech": "TrueVision is a visual state path.",
                "evidence": [{"anchor": "truevision", "total_neighbor_observations": 4}],
                "citations": [{"coord": "clearspeak:lifetime:truevision"}],
                "answer_assembly": {"terms": [{"anchor": "visual"}, {"anchor": "state"}]},
            },
            document_payload={
                "ok": True,
                "speech": "TrueVision records state before rendering.",
                "citations": [{"coord": "flat-doc:truevision:1"}],
                "evidence": {"source_passages": [{"source_name": "doc", "text": "records state"}]},
            },
        )

        self.assertEqual(packet["schema_version"], "anchorworks_grounded_evidence_packet@1")
        self.assertEqual(packet["represented_anchors"], ["truevision"])
        self.assertEqual(packet["count_evidence_count"], 1)
        self.assertEqual(packet["document_evidence_count"], 1)
        self.assertFalse(packet["writes_performed"])
        self.assertEqual(packet["writes_allowed"], {"maps": False, "counts": False, "lifetime": False, "lexicon": False})

    def test_grounded_result_labels_no_evidence_instead_of_claiming_answer(self):
        packet = build_grounded_evidence_packet(
            query="what is unproven?",
            clearspeak_payload={"represented_anchors": [], "missing_anchors": ["unproven"], "speech": ""},
            document_payload={"ok": False, "citations": [], "evidence": {}},
        )
        result = render_grounded_result(packet)

        self.assertFalse(result["ok"])
        self.assertEqual(result["verdict"], "unsupported")
        self.assertIn("No grounded evidence", result["response"])
        self.assertFalse(result["writes_performed"])

    def test_chat_send_grounded_mode_returns_grounded_contract(self):
        app = create_app(Path(r"D:\AnchorWorks_Clean_Runtime"))
        result = app.state.chat_memory.send("what is truevision?", mode="grounded").to_dict()

        self.assertEqual(result["mode"], "grounded")
        self.assertFalse(result["writes_performed"])
        self.assertEqual(result["clearspeak"]["evidence_mode"], "grounded")
        self.assertEqual(result["clearspeak"]["engine"], "anchorworks_grounded_mode")
        self.assertIn("grounded", result["clearspeak"])
        self.assertFalse(result["clearspeak"]["grounded"]["writes_performed"])


if __name__ == "__main__":
    unittest.main()
