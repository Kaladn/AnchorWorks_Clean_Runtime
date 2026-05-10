# AnchorWorks Attention White Paper

Status: current architecture plus next-step design
Last updated: 2026-05-10

## Abstract

AnchorWorks attention is the runtime selection layer that decides which
observed anchor relationships matter for the current question, statement, or
review task.

It is not a hidden generative model and it is not a replacement for source
evidence. It is a deterministic scoring layer over anchors, source-local
occurrences, positional relationships, context clouds, and ClearSpeak answer
assembly.

Core law:

```text
Counts store weight.
Context clouds store neighborhood.
Attention chooses relevance.
Renderer speaks the chosen structure.
Occurrences prove addresses.
```

## Problem

Raw co-occurrence counts can become a frequency table. A frequency table can
show strong neighbors, but it does not know which neighbors matter right now.

For example:

```text
How do I sear meat?
```

and:

```text
This is how I sear meat.
```

share many of the same anchors, but they do not have the same use. The first is
a method question. The second is a method declaration. The same weighted
relationships must be interpreted through different frames.

AnchorWorks attention exists to make that distinction explicit.

## Terminology

### Surface

The raw observed text fragment before AnchorWorks resolves it.

### Anchor

The whole observed language unit after AnchorWorks preparation. Anchors are the
counted and related units in the system.

### Symbol

The stable identity assigned to an anchor by Canonical, companion lanes,
source-local temporary entries, or NULL handling.

### Occurrence

A source-local observation of an anchor at a specific address. Occurrences carry
coordinates such as source, block, line, and anchor position.

### Context Cloud

A source-local or lifetime neighborhood around an anchor. It records which
anchors repeatedly appear near a center anchor and how strongly they are
related.

### Attention

The runtime relevance scorer. It receives the active context, reads the weighted
neighborhood, applies frame and role fit, and ranks candidate anchors.

## Separation Of Powers

AnchorWorks attention only chooses relevance. It does not create truth.

```text
Canonical knows base language authority.
Companion lanes assist without mutating Canonical.
NULL records parseable exclusions.
Observed maps prove and rebuild.
Flat documents serve runtime source evidence.
Occurrences prove source addresses.
Context clouds find neighborhoods.
Counts store observed weight.
Attention chooses relevant candidates.
ClearSpeak renders.
Approval gates decide promotion.
```

This split prevents the answer path from confusing strong association with
source proof.

## Current Code Placement

Current attention code lives in:

```text
src/AnchorWorks/clearspeak_attention.py
```

ClearSpeak uses it from:

```text
src/AnchorWorks/clearspeak.py
```

Source-local resonance support lives in:

```text
src/AnchorWorks/positional_resonance.py
```

External read-only count mirrors are loaded by:

```text
src/AnchorWorks/lifetime_symbol_mirror.py
```

The current attention contract is:

```text
anchorworks_clearspeak_attention@1
```

The current frame contract is:

```text
anchorworks_attention_frame@1
```

## Current Attention Law In Code

The active implementation carries this law:

```text
Counts store weight; context clouds store neighborhood; attention chooses relevance.
```

That is not only documentation. The law is embedded in the attention math
contract returned with answer assembly traces.

## Data Flow

```text
query text
-> anchor extraction
-> known anchor filtering
-> attention frame inference
-> content anchor selection
-> count index lookup
-> candidate scoring
-> selected candidate re-enters context
-> repeated walk
-> ClearSpeak answer assembly
-> renderer
```

The important part is the loop:

```text
active context
-> rank candidates
-> select candidate
-> add selected anchor back into context
-> rank again
```

This is the beginning of an AnchorWorks-native attention walk.

## Current Math

For each candidate neighbor:

```text
position_strength = 1 / absolute_offset_distance
```

The base candidate score is:

```text
sum(observations * position_strength)
+ supporting_context_count * 8
```

The current role-aware score adds:

```text
role_fit_score
```

So the full current shape is:

```text
selection_score =
  sum(observations * position_strength)
  + supporting_context_count * 8
  + role_fit_score
```

Current constants:

```text
MULTI_CONTEXT_SUPPORT_BONUS = 8.0
ROLE_SUPPORT_BONUS = 6.0
```

These values are simple deliberate starting weights. They make a candidate
supported by several active anchors beat a louder but isolated candidate when
the surrounding frame supports that decision.

## Context Cloud Math

Context clouds are built from relation rows:

```text
anchor
offset
neighbor
observations
```

For a center anchor `A` and neighbor `N`:

```text
member_count(A,N) = sum observed relationships across offsets
max_count(A) = strongest neighbor count for A
cloud_strength(A,N) = member_count(A,N) / max_count(A)
```

Current default inclusion rule:

```text
cloud_strength >= 0.3
top_k = 12
```

The context cloud is storage. It answers:

```text
What tends to appear near this anchor?
```

Attention is runtime selection. It answers:

```text
Which of those neighbors matters for this active frame?
```

## Positional Resonance

Positional resonance preserves offset shape.

For a center anchor `A`, offset `O`, and neighbor `N`:

```text
score(A,O,N) = observations(A,O,N) / max_observations(A,O)
```

This means the system can distinguish:

```text
neighbor usually appears before the anchor
neighbor usually appears after the anchor
neighbor appears near but without stable direction
```

Positional resonance guides retrieval and answer shaping. It cannot cite proof
by itself.

## Directional Resonance

Directional resonance collapses offset support into a directional relationship:

```text
directional_score(A,N) = pair_count(A,N) / total_observations_from_anchor(A)
```

This helps expand or suppress candidate neighborhoods. It is not source proof.

## Occurrence Grounding

Occurrences are the proof layer.

An occurrence can carry:

```text
source
source_path
paragraph_id
block_id
line_start
line_end
anchor_position
surface
anchor
symbol
```

Attention can rank a candidate. It cannot prove that a document supports a
claim. Proof comes from occurrence addresses and source-local evidence frames.

Rule:

```text
Clouds find neighborhoods.
Occurrences prove addresses.
Speech must cite addresses when making source claims.
```

## Frame Inference

The current attention layer infers a small runtime frame from observed anchors.

Current frame types:

```text
method_question
method_declaration
question
open_context
```

Examples:

```text
How do I sear meat? -> method_question
This is how I sear meat. -> method_declaration
```

This matters because the same anchors can support different answer behavior
depending on the frame.

## Role Inference

The current role layer is intentionally small.

Frame markers:

```text
how -> question_marker or method_marker
i -> speaker_marker
this -> declaration_marker
do / does / did / is / are / was / were -> glue_direction
? -> question_punctuation
. -> statement_punctuation
```

For method frames, the first content anchor becomes:

```text
action_candidate
```

The second content anchor becomes:

```text
object_candidate
```

Example:

```text
How do I sear meat?
```

Current frame:

```json
{
  "frame_type": "method_question",
  "role_by_anchor": {
    "how": "question_marker",
    "do": "glue_direction",
    "i": "speaker_marker",
    "sear": "action_candidate",
    "meat": "object_candidate",
    "?": "question_punctuation"
  }
}
```

## Role Fit

Candidate rows carry:

```text
role_fit.score
role_fit.matched_roles
role_fit.supporting_anchors
```

A candidate supported by both the action anchor and the object anchor receives
stronger role fit than a candidate supported by only one side.

For:

```text
How do I sear meat?
```

a candidate supported by both:

```text
sear
meat
```

is treated as better fitted to the active method frame than a candidate
supported only by a distant single relation.

## Answer Health

Current candidate rows include:

```text
answer_health.status
answer_health.reason
```

The current implemented status is:

```text
supported
```

with reason:

```text
candidate_has_observed_count_support
```

Future answer health should expand to include:

```text
unsupported_jump
query_echo
glue_only_candidate
source_required
low_context_support
conflict_with_document_evidence
```

## Lane Fit

Candidate rows currently carry:

```json
{
  "lane": "counts",
  "score": 1.0
}
```

This is a placeholder for future routing. It makes the distinction explicit:

```text
document lane
count lane
chat lane
intake review lane
visual evidence lane
```

The same anchor relationship should not behave identically in every lane.

## Query Echo And Glue Penalty

Current candidate rows include:

```text
query_echo_penalty
glue_penalty
```

They are currently initialized as zero. The blocking rules already prevent many
question words, punctuation marks, numbers, and generic glue anchors from
becoming spoken answer terms.

Future attention work should turn these placeholders into scored penalties
instead of only hard exclusion.

## ClearSpeak Walk

ClearSpeak does not simply display strongest neighbors.

It now:

```text
extracts anchors
filters known anchors
selects content anchors
infers attention frame
ranks candidate neighbors
selects a candidate
feeds the selected candidate back into context
walks again
returns answer assembly trace
```

This matters because the answer path becomes dynamic:

```text
sear + meat
-> pan
sear + meat + pan
-> heat
sear + meat + pan + heat
-> ...
```

The selected candidate changes the next candidate field.

## External Count Mirror

The current repo can use an external read-only lifetime-by-symbol mirror:

```text
ANCHORWORKS_LIFETIME_BY_SYMBOL_DIR
```

This allows ClearSpeak attention experiments to run against historical count
fields while the live runtime count build continues.

The external mirror is read-only. It does not mutate:

```text
Canonical
user lexicon
active lifetime counts
maps
source files
```

## What Attention Is Not

AnchorWorks attention is not:

```text
a source of truth
a document citation
a Canonical editor
a lifetime writer
a visual recognition engine
a hidden model guess
a replacement for source evidence
```

Attention only ranks observed candidates for the active context.

## Comparison To Neural Attention

Neural attention usually learns dense hidden weights. AnchorWorks attention uses
explicit observed weights.

Side by side:

```text
Neural system:
learned unit weights
hidden vectors
dense similarity
implicit salience
generated continuation

AnchorWorks:
anchors
symbols
observed counts
explicit offsets
source-local occurrences
auditable candidate scores
controlled rendering
```

The goal is not to imitate neural systems. The goal is to recover the useful
selection behavior of attention while keeping the evidence trail visible.

## Why This Matters

Without attention:

```text
counts become a table
strongest neighbor can dominate
glue can distort direction
questions and declarations blur together
answers sound like raw evidence dumps
```

With attention:

```text
counts become a weighted field
the active frame matters
roles influence candidate fit
nearby support matters
multi-anchor support matters
the walk can become fluent
the trace remains inspectable
```

## Current Tests

Current tests prove:

```text
nearby multi-context support beats louder distant isolated support
method question and method declaration frames are distinct
sear is marked as action_candidate
meat is marked as object_candidate
role fit appears in ranked candidates
ClearSpeak answer assembly exposes attention_frame
external lifetime-by-symbol mirror can feed ClearSpeak read-only
```

## Safety Rules

Attention must obey these rails:

```text
Do not write Canonical.
Do not write lifetime counts.
Do not write maps.
Do not promote visual evidence.
Do not cite context clouds as proof.
Do not let NULL speak.
Do not treat strong count as source truth.
Do not hide the lane used for an answer.
```

## Public Explanation

Plain description:

```text
AnchorWorks attention is a deterministic relevance layer that reads observed
anchor relationships, scores them against the current question or statement,
and produces an auditable candidate walk for the renderer.
```

Short version:

```text
Counts remember what was observed.
Attention decides what matters now.
Evidence proves where it came from.
```

## Roadmap

### Phase 1: Current Lock

Done:

```text
named ClearSpeak attention module
runtime relevance scoring contract
role-aware frame records
method question/declaration split
action/object role fit
external count mirror support
tests for attention behavior
```

### Phase 2: Better Role Policy

Add a real role policy table:

```text
action
object
quality
source
relation
quantity
time
location
evidence marker
method marker
contrast marker
cause marker
```

The current method-frame rules are a seed, not the final role system.

### Phase 3: Frame Library

Add more frames:

```text
definition_question
cause_question
comparison_question
evidence_request
agreement_request
method_declaration
source_summary_request
cleanup_review_request
visual_evidence_request
```

Each frame should specify:

```text
required roles
preferred lanes
blocked answer shapes
citation requirements
health checks
```

### Phase 4: Scored Penalties

Turn placeholders into real scoring:

```text
query_echo_penalty
glue_penalty
unsupported_jump_penalty
low_context_penalty
lane_mismatch_penalty
```

### Phase 5: Source Evidence Fusion

When documents are on:

```text
attention ranks candidates
flat runtime documents retrieve blocks
occurrences prove addresses
renderer cites block/line/anchor
```

Attention should guide retrieval, not replace citation.

### Phase 6: Visual Evidence Fit

For visual sidecars:

```text
visual records witness
source text tells
bilateral records compare
attention ranks evidence relevance
approval gates decide promotion
```

Visual attention must remain source-local until approved.

## Implementation Contract

Every attention result should preserve:

```text
schema_version
frame_type
selection_score
raw_observations
supporting_context
support_offsets
role_fit
lane_fit
query_echo_penalty
glue_penalty
source_support
answer_health
why_chosen
attention_math
```

Every answer assembly should preserve:

```text
schema_version
seed_anchors
attention_frame
terms
trace
stop_reason
attention_math
contract
```

## Final Law Set

```text
Anchors carry observed identity.
Counts store repeated relationship.
Context clouds store neighborhood.
Positional resonance stores where.
Directional resonance stores pressure.
Attention chooses relevance.
Role fit shapes selection.
Occurrences prove addresses.
Renderer speaks only the selected structure.
Approval decides what persists.
```

