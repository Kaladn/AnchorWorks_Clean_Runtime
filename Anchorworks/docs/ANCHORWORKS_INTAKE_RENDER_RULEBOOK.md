# AnchorWorks Intake And Render Rulebook v1

This document is the current AnchorWorks intake and render authority document.
It wins over older planning notes unless a newer committed rulebook replaces it.

Purpose:

```text
Make every intake, count, inference, and rendering step obey explicit rules.
Make future algorithms, agents, and workers inherit the same base laws.
```

## Short Law

```text
Lexicon recognizes.
Counts propose.
Frames aim.
Inference admits.
Renderer speaks.
Receipts prove.
```

## Authority Boundary

AnchorWorks is the language, count, anchor, frame, and rendering system.
It does not become SecureCore, TrueVision Generation, or a generic agent runtime.

Rules:

```text
Truth lives in source, counts, traces, receipts, and verified code paths.
No doc becomes truth by existing.
No model becomes fact authority.
No renderer may invent evidence.
No UI surface may imply a backend action unless that action is wired.
```

## Intake Rules

AnchorWorks intake starts with represented identity, not guessed language.

Rules:

```text
Lexicon first.
Known anchors are admitted by current live authority.
Missing anchors go to review.
Unknown strings are not silently counted as words.
String literals are represented as strings unless promoted.
No hidden substitute lexicon.
No fake lexicon.
No hidden splitting.
No stop-word truth.
No punctuation as content anchor.
No grammar rule becomes source truth.
```

Punctuation, glue, and director words may shape direction.
They may not seed content counts by themselves.

## Unknown And Canonical Anchor Rules

Unknowns must become a reviewable anchor list before any lifetime authority change.

Rules:

```text
New unknowns are surfaced.
Canonical additions require the genome symbol path.
Genome identity is the live identity path.
Dead spare slots are not approval authority.
Non-word strings stay string-symbolized until approved.
Acronyms split into represented letters/digits, then may be smooshed as a surface form.
```

Examples:

```text
SC -> S + C -> SC surface
GPU -> G + P + U -> GPU surface
TrueVision -> canonical concept only after explicit approval
```

## Engagement Rules

Not every user input is a question.
AnchorWorks must classify conversational role before count walking or answer generation.

Core law:

```text
Engagement first.
Relation second.
Speech third.
```

Current engagement types:

```text
question
conversation
info_transfer
correction
planning_note
statement
```

Rules:

```text
question may start answer generation.
conversation maintains flow.
info_transfer updates working context.
correction adjusts a prior path.
planning_note shapes future work.
statement does not automatically become a question.
```

Normal conversation is not always a question.

## Count Rules

Counts are pressure, not speech.
Top-K is candidate pressure, not truth.

Rules:

```text
Top-K is walked, not dumped.
No raw candidates as speech.
No count cloud speaks directly.
No unsupported candidate enters speech.
No off-frame candidate enters the answer plan.
No generic "points toward" answer when the frame needs a definition, cause, process, or formula.
```

Counts may provide:

```text
candidate anchors
local pressure
directional pressure
nearby phrases
accepted/rejected paths
support metrics
uncertainty notes
```

Counts may not provide:

```text
final fact authority
automatic answer text
raw top-k dump
domain override
unverified source claims
```

## Frame And Inference Rules

Frames aim the answer.
Inference decides what belongs.

Rules:

```text
Frame rules may fire from input shape.
Fact rules may fire only from evidence.
Candidates may not speak until admitted.
Every rejected candidate needs a reason.
Every admitted path needs support.
Every missing support stays missing.
No gap becomes a fake chain.
No randomness.
```

Minimum frame classes:

```text
definition
why_causal
how_process
implication_check
comparison
formula_solve
document_fact
count_explanation
insufficient_support
off_frame_rejection
```

## Answer Starter Rules

The answer starter is not a canned phrase list.
It is derived from the first legal relation between the held subject and the strongest admitted answer path.

Law:

```text
Starter = first legal relation between subject and admitted path.
```

Relation permissions:

```text
identity_or_class
function
process
cause
composition
location
contrast
limitation
evidence
correction
planning
```

Process:

```text
Hold the subject anchor.
Hold the engagement type.
Hold the input frame.
Walk admitted top-k path memory.
Score relation pressure.
Select the first legal relation.
Only then insert glue and directional speech.
```

## Bridge And Glue Rules

Glue words are allowed inside speech after the relation is chosen.
They are not allowed to replace the relation.

Hard rule:

```text
No generic bridge unless the active relation permits it.
```

Blocked lazy bridges unless evidence-supported:

```text
involves
connects through
relates to
is associated with
has to do with
links to
```

Directional content words such as `preserves`, `records`, `derives`, `counts`, and `renders` may be used when the admitted path supports that function.

## Renderer Rules

Renderer speaks only from the approved plan.

Rules:

```text
Renderer speaks from admitted path memory.
Renderer keeps the question frame alive.
Renderer may transform for readable speech.
Renderer may use glue after relation selection.
Renderer may not invent facts.
Renderer may not substitute vague bridge words for structure.
Renderer may not dump debug traces as answers.
```

For definition-like questions, prefer the legal shape discovered from relation pressure:

```text
subject -> class/path/system/layer -> supported function/object/mode
```

Example:

```text
TrueVision is a visual state path that preserves glyph, text, and document as state.
```

## Occular Cloud Rules

Occular Clouds are visual-symbolic counts, not lifetime word counts.
They are their own lane.

Current experimental OC shape:

```text
4x6-4-4x6
```

Meaning:

```text
left_context = 4 mini-clouds
each left mini-cloud = 6 symbols
center = 4-symbol visual phrase
right_context = 4 mini-clouds
each right mini-cloud = 6 symbols
```

Rules:

```text
Do not mutate lifetime word counts from OC dry-runs.
Do not mix OC counts with text counts silently.
Do not count unknown or ineligible symbols.
Do not put __NULL__ into count memory.
Do not change OC shape without manifesting shape parameters.
```

## GPU Rules

GPU acceleration is an execution lane, not an authority lane.

Hard rule:

```text
GPU is execution, not authority.
```

Rules:

```text
CPU and GPU output schemas must match.
GPU runs must report backend, device, shape, hashes, and fallback reason.
GPU may carry tensors faster.
GPU may not decide truth.
CPU verification remains valid proof.
```

## TrueVision Visual-Symbolic Intake Rules

TrueVision-style intake for AnchorWorks is visual-symbolic state intake.
It is not prompt-video generation.

Rules:

```text
Vision records state first.
Text and symbols are derived after visual proof.
Native geometry is authority.
Any grid is derived.
Any model resize is derived.
Any OCR label is derived.
Any object label is derived.
Derived labels do not become truth without promotion.
Original source remains evidence.
```

Embedded video is a modality switch.

```text
Document intake walks.
Video intake sprints.
Counts trail.
```

If processing falls behind:

```text
wait 15 seconds
retry up to 3 times
write deterministic pickup point on failure
continue from pickup, not from zero
```

## Write And Promotion Rules

Dry-run means dry-run.

Rules:

```text
No lifetime write without explicit approval.
No lexicon mutation without canonical path.
No count promotion without eligibility.
No generated artifact becomes source truth.
No hidden fallback write.
Every promotion needs a receipt or manifest.
```

## UI And Help Rules

UI is dead last unless needed to expose a real backend action.
Help and UI must share the same action map.

Rules:

```text
No backend binding means no active control.
No policy gate means no mutation control.
No receipt target means no write control.
No registered action means no rendered action control.
Help describes the same mapped actions the UI exposes.
```

## Agent And Worker Rules

Future agents and workers inherit this rulebook.

Rules:

```text
Agents may interpret packets.
Workers may execute approved tasks.
Agents may not invent authority.
Workers may not act from conversation flow alone.
Renderers may speak only admitted paths.
System prompts must include the short first prompt before answer generation.
```

## Current Proof Anchors

Tests that currently cover important parts of this rulebook:

```text
tests/test_conversation_input_type.py
tests/test_answer_surface_direction.py
tests/test_clearspeak_directional_render.py
tests/test_query_recognition_frame.py
tests/test_aw_inference_candidate_walk.py
tests/test_count_window_contract.py
tests/test_occular_cloud_systems.py
tests/test_occular_cloud_accel.py
tests/test_occular_tensor_store.py
tests/test_occular_tensor_index.py
tests/test_truevision_language_intake.py
tests/test_truevision_language_pipeline.py
tests/test_truevision_document_state_movie.py
tests/test_genome_approval.py
```

## Final Lock

```text
Classify the input.
Represent the anchors.
Walk the counts.
Admit the path.
Choose the relation.
Speak only what survived.
```
