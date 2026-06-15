# AnchorWorks Activity Log

## 2026-06-15

### ClearSpeak Count Search Admission Fix

- Investigated incomplete answers where rendering was suspected but counts already contained the missing answer terms.
- Reproduced the failure with a focused ClearSpeak count-search test: a question-form query could recognize content anchors while the answer path stayed empty.
- Root cause: question-field drift rejection was too strict. Valid answer terms outside the literal query tokens were rejected before rendering when they had count support from the represented content field.
- Fix: candidates with support from the represented content anchors are no longer rejected as question-field drift.
- Verification: focused ClearSpeak test passed and full test suite passed.

### User Lexicon State Finding

- Inspected `State/user/user_lexicon/anchors.json` after noticing a large unstaged runtime-state change.
- Current file grew from the tracked empty seed to about 185 MB of canonical/structural seeded entries dated 2026-06-07.
- The file is not clean JSON/UTF-8 at the current working state; byte inspection found invalid UTF-8 near the tail.
- This appears to be runtime lexicon materialization/corruption, not a code change. It was not staged for commit.
- Relevant code shape: `ensure_user_lexicon_seeded()` copies Canonical and Structural entries into the user lexicon as `canonical_seed`; new accepted user entries are allocated through the user symbol genome pool in the `0xE...` range.
