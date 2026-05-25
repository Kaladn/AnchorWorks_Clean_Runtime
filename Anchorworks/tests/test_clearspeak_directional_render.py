import unittest
from pathlib import Path
from AnchorWorks.store import LexiconStore
from AnchorWorks.clearspeak import ClearSpeakService

class ClearSpeakNoLazyDirectionTests(unittest.TestCase):
    def test_truevision_question_uses_shape_not_involves_or_connects_through(self):
        result = ClearSpeakService(LexiconStore(Path(r'D:\\AnchorWorks_Clean_Runtime'))).query(
            'what is truevision?', limit=6, min_anchors=2, target_anchors=5, max_anchors=8
        )
        speech = result.speech.casefold()
        forbidden_bridges = [
            'involves',
            'connects through',
            'relates to',
            'is associated with',
            'has to do with',
            'links to',
        ]
        for bridge in forbidden_bridges:
            self.assertNotIn(bridge, speech)
        self.assertIn('truevision', speech)
        self.assertIn(' is ', speech)
        self.assertIn('state', speech)
        self.assertRegex(speech, r'truevision is (a|an) .+ (that|which) ')

if __name__ == '__main__':
    unittest.main()
