# AnchorWorks Chat Workbench Contract

Last updated: 2026-05-09

## Purpose

The AnchorWorks chat surface is not just a message box. It is the guided
workbench for document evidence, ClearSpeak counts, source-local intake review,
lexicon work, NULL review, visual sidecars, and future phrase authority.

The chat workbench must make the system easier to drive without letting the
assistant invent behavior or silently mutate source authority.

Core law:

```text
Chat explains.
Buttons execute.
Backend permits.
Evidence labels the lane.
Promotion changes state.
```

## Current Speaking Lanes

AnchorWorks has separate answer lanes. They must stay clearly labeled.

### Document Lane

```text
query
-> anchors
-> flat symbolic document search
-> block and line evidence
-> optional visual sidecar citation
-> renderer
```

Document answers may cite source locations:

```text
block 67, lines 12-45
```

Visual references may be shown as related evidence, but they do not become
document truth by appearing in a citation.

### ClearSpeak Count Lane

Codex 2 restored the compact ClearSpeak count walk in commit:

```text
345a8c9 Walk ClearSpeak count top-k answers
```

The intended shape is:

```text
content anchors
-> count neighbors
-> top-k candidate pool
-> block punctuation, numbers, glue, and query echoes
-> choose a term
-> feed chosen term back into context
-> walk again
-> render survivors
```

Rules:

- Counts mode must not claim document or map evidence.
- Query responses must not write lexicon, maps, flat docs, or counts.
- Raw count evidence remains available for audit.
- The fast hot path should eventually use `State/lifetime_by_symbol`.

### Resonance and Context Clouds

Context clouds and positional resonance guide retrieval and review. They cannot
cite as proof by themselves.

```text
Clouds find neighborhoods.
Occurrences prove addresses.
Renderer must label the lane.
```

## Evidence Toggle Contract

The chat UI must expose an evidence toggle.

### Evidence On

When evidence is on, the response should show:

- evidence mode
- answer engine
- citation type
- source block/line citations when present
- visual sidecar references when present
- ClearSpeak count evidence when in counts mode
- fallback status
- write status

### Evidence Off

When evidence is off:

- the response may be shorter and cleaner
- the backend must still compute and return lane metadata
- the backend must not change evidence eligibility
- hidden evidence must remain recoverable from the response record or audit

Evidence display is a rendering preference. It is not an authority switch.

Minimum response fields:

```json
{
  "evidence_visible": true,
  "evidence_mode": "document_map",
  "engine": "flat_symbolic_documents",
  "citation_type": "source_locator",
  "fallback_used": false,
  "writes_performed": false
}
```

## Stop Response Contract

The chat UI must expose a Stop Response control while a response, workflow step,
or long intake action is active.

Rules:

- Stop marks the active response or workflow step as interrupted.
- Stop does not finalize partial review decisions.
- Stop does not write lexicon entries, maps, flat runtime files, or counts.
- Deterministic local routes may stop at request cancellation boundaries.
- Streaming or long-running routes should use a response id or workflow id.

Minimum interrupted record:

```json
{
  "response_id": "response_...",
  "workflow_id": "workflow_...",
  "status": "interrupted",
  "writes_performed": false
}
```

## Guided Chat Controls

The assistant may return suggested next actions. The backend owns the action
registry. The UI only renders actions that the backend has validated.

Not allowed:

```text
assistant invents random buttons
assistant sends arbitrary route names
UI executes unregistered actions
dangerous writes happen without confirmation
```

Allowed shape:

```text
assistant text
-> backend action registry
-> validated action list
-> temporary UI buttons under that chat message
-> action route validates again
-> workflow advances
```

Every non-terminal workflow message should include:

```text
Continue Working
```

Tiny law:

```text
AI suggests.
Registry defines.
Backend validates.
UI renders.
```

## Workflow Response Schema

```json
{
  "workflow_id": "chat_intake_123",
  "step_id": "coverage_review",
  "assistant_text": "20 documents are staged. I found review candidates.",
  "evidence_visible": true,
  "actions": [
    {
      "id": "review_real_words",
      "label": "Review Real Words",
      "kind": "open_bucket",
      "payload": {
        "bucket": "unknown_real_word_candidates"
      },
      "requires_confirmation": false
    },
    {
      "id": "continue_working",
      "label": "Continue Working",
      "kind": "continue_workflow",
      "payload": {},
      "requires_confirmation": false
    }
  ]
}
```

Action records are temporary controls. They are not source evidence.

## Action Registry V1

Safe review and navigation actions:

```text
continue_working
show_evidence
hide_evidence
stop_response
review_real_words
review_math_structural
review_null_index
review_source_specific
review_phrase_candidates
show_context_cloud
show_occurrence_addresses
build_preview
```

Write or build actions must require confirmation:

```text
approve_selected_lexicon_entries
assign_spare_slots
apply_source_cleanup_batch
build_observed_maps
build_flat_runtime
finalize_counts
```

Forbidden action behavior:

- unknown action id
- stale workflow id
- action not valid for the current step
- action payload that fails schema validation
- dangerous action without confirmation

## Chat Document Intake Contract

The chat surface should support staging up to 20 user documents per batch.

The chat upload path must use the normal intake pipeline:

```text
chat file staging
-> document preparation
-> source cleanup checks
-> anchor coverage classification
-> companion lane classification
-> NULL index output
-> review workflow
-> optional observed map build
-> optional flat runtime build
```

Rules:

- 20 documents is the default batch limit.
- 21 or more documents must produce a guided split-batch response.
- Chat intake must not bypass document prep.
- Chat intake must not write Canonical directly.
- Chat intake must not write durable counts directly.
- Chat intake must not promote visual or media sidecars.
- Every observed surface gets a fate: Canonical, companion lane, source-local,
  NULL, or review.

## Lexicon Workbench Assistant Contract

The AI helper may assist lexicon review, but it does not own lexicon authority.

Allowed AI assistance:

- explain why a surface appears to be a real word
- explain why a surface appears to be a spelling issue
- explain why a surface appears structural, math-related, source-specific, or junk
- use occurrence addresses and context clouds to support review
- propose batch choices for the user

Forbidden AI behavior:

- directly writing Canonical
- directly deleting spare slots
- directly assigning spare slots without confirmation
- treating context clouds as proof
- approving source cleanup without user confirmation

The write path remains:

```text
candidate
-> user review
-> spare slot assignment
-> Canonical update when approved
-> used spare slot removal
-> verification report
```

## NULL Index Contract

NULL is parseable exclusion with exact coordinates.

```text
NULL does not remember meaning.
NULL remembers that something was there.
```

Required NULL locator:

```json
{
  "source_id": "source_...",
  "block_id": "block_72",
  "line": 4,
  "anchor_position": 7,
  "surface": "...",
  "reason": "junk_artifact",
  "speakable": false,
  "countable": false
}
```

The chat workbench must be able to show NULL records by source, block, line,
surface, reason, and surrounding context.

## Phrase Lexicon Contract

AnchorWorks may add a separate phrase authority beside Canonical. Canonical
remains the only global base language authority.

Phrase entries are approved multi-anchor surfaces. They do not split anchors.

Initial phrase lane:

```text
2 to 6 whole anchors
-> phrase candidate
-> occurrence support
-> context cloud review
-> user approval
-> 6-byte phrase symbol
```

Minimum phrase record:

```json
{
  "schema_version": "anchorworks_phrase_lexicon@1",
  "phrase_id": "phrase_...",
  "phrase_symbol_6byte_hex": "000000000000",
  "anchor_sequence": ["source", "local", "evidence"],
  "support_occurrences": [],
  "status": "candidate",
  "authority": "phrase_companion",
  "writes_allowed": {
    "canonical": false,
    "counts": false,
    "lifetime": false
  }
}
```

Phrase candidates may improve search and review. They do not become speakable
authority until approved.

## Visual and Media Sidecar Rule

Visual, OCR, video, and audio layers are source-local evidence until explicitly
approved by their own gates.

They may help answer:

```text
what figure is near this block?
what visual witness exists for this page?
what transcript range supports this segment?
what frame region changed?
```

They may not silently write Canonical, counts, maps, or durable speech authority.

## API Targets

Future implementation should add or extend these routes:

```text
POST /api/chat/send
POST /api/chat/stop
POST /api/chat-workflow/action
POST /api/chat-intake/stage
GET  /api/chat-workflow/{workflow_id}
```

The existing chat send route should return enough metadata for the UI to render:

- evidence toggle state
- stop eligibility
- workflow id
- action list
- evidence lane metadata
- citation metadata
- write status

## UI Targets

The chat surface should add:

- Evidence On/Off toggle
- Stop Response button
- guided action buttons under assistant messages
- document staging control capped at 20 files
- evidence drawer/card that can collapse
- lexicon review buckets surfaced inside chat
- NULL review view surfaced inside chat
- phrase candidate review view surfaced inside chat

Temporary controls belong to the assistant message that produced them. When the
workflow advances, old controls should be disabled or marked stale.

## Acceptance Tests

Required tests before implementation is called complete:

- evidence off hides evidence details but preserves lane metadata
- evidence on shows document block/line citations
- counts-only mode never claims document evidence
- document mode does not fall back silently when strict document mode is set
- Stop Response marks an active workflow interrupted and performs no writes
- 20 document chat staging succeeds
- 21 document chat staging asks for split-batch handling
- unknown action id is rejected
- stale workflow action is rejected
- dangerous action without confirmation is rejected
- Continue Working appears on non-terminal workflow steps
- lexicon helper suggestions do not write Canonical directly
- NULL records include block, line, anchor position, surface, and reason
- phrase candidates preserve whole anchor sequences
- context clouds cannot cite as proof alone

## Tiny Lock

```text
Source passages cite.
Counts walk.
Clouds guide.
NULL locates exclusions.
Phrases preserve whole anchors.
Chat guides the work.
Backend guards the state.
```
