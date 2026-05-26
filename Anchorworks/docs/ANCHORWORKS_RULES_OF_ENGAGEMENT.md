# AnchorWorks Rules Of Engagement v1

This document defines the current conversation and answer-start contract for AnchorWorks.
It is part of the larger intake/render contract in:

```text
docs/ANCHORWORKS_INTAKE_RENDER_RULEBOOK.md
```

The short primer that agents should see first is:

```text
docs/ANCHORWORKS_AGENT_FIRST_PROMPT.md
```

## Core Law

```text
Engagement first.
Relation second.
Speech third.
```

AnchorWorks must not force every user input into answer generation.
Some inputs are questions.
Some are context transfer.
Some are corrections.
Some are planning notes.
Some are ordinary conversation.

## Engagement Types

Current live engagement types:

```text
question
conversation
info_transfer
correction
planning_note
statement
```

### question

A question asks AnchorWorks to produce an answer path.
Question input may trigger lexicon recognition, count retrieval, inference admission, and rendering.

Examples:

```text
what is truevision?
how does truevision record state?
why worry about laws of physics?
```

### conversation

Conversation input maintains human flow.
It does not automatically trigger a count walk.

Examples:

```text
hello
thanks
good morning
```

### info_transfer

Information transfer updates working context.
It is not an answer request by default.

Examples:

```text
now keep in mind that we talk, not everything is a question
remember the UI is last
consider answer starter algorithm that does not require a pre-ordained list
```

### correction

Correction input adjusts the working context or rejects a prior path.
It is not a new answer request unless paired with one.

Examples:

```text
no, that is not correct
that is wrong
actually use the genome path
```

### planning_note

Planning notes shape future work.
They are held as project context rather than rendered as count answers.

Examples:

```text
next we build the harness
add this to the todo
we need this later
```

### statement

Statement is the fallback for non-question input that does not yet match a stronger engagement type.
A statement may be eligible for later classifiers, but it should not be treated as a question automatically.

## Gate Contract

```text
Gate 1: classify engagement type.
Gate 2: decide whether an answer path is allowed.
Gate 3: if allowed, find the first legal relation.
Gate 4: render speech from admitted path memory.
```

Rules:

```text
If engagement_type is info_transfer, correction, or planning_note:
  do not start a count walk by default.
  acknowledge the role.
  preserve context anchors for later use.

If engagement_type is question:
  run lexicon recognition.
  retrieve counts only from represented content anchors.
  walk top-k candidates.
  admit only lawful candidates.
  render from the admitted path.

If engagement_type is statement:
  do not pretend it is a question.
  use future algorithms to decide whether it is assertion, note, command, or context.
```

## Answer Starter Algorithm

The answer starter is not selected from a canned phrase bank.

```text
Starter = first legal relation between the held subject and the strongest admitted answer path.
```

Inputs:

```text
engagement_type
subject_anchor
input_frame
admitted_candidate_path
candidate_roles
relation_scores
forbidden_bridges
held_answer_memory
```

Process:

```text
1. Hold the subject anchor.
2. Hold the input frame if present.
3. Classify admitted top-k candidates by role.
4. Score relation pressure.
5. Pick the highest legal relation.
6. Render the starter from subject + relation + first admitted candidate.
7. Keep the rest of the answer path in memory.
8. Revise next top-k choices until sentence shape remains legal.
9. Insert interior speech glue only after relation selection.
```

Relation pressure classes:

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

These are semantic permissions, not fixed phrases.

## Forbidden Lazy Bridges

Generic bridge words are blocked unless directly supported by the selected relation and path.

Current forbidden fallback bridges:

```text
involves
connects through
relates to
is associated with
has to do with
links to
```

Law:

```text
No generic bridge unless the active relation permits it.
```

## Current Proofs

Current tests proving this contract:

```text
tests/test_conversation_input_type.py
tests/test_answer_surface_direction.py
tests/test_clearspeak_directional_render.py
tests/test_query_recognition_frame.py
tests/test_aw_inference_candidate_walk.py
```

Current verified examples:

```text
Input:
now keep in mind that we talk, not everything is a question

Classification:
info_transfer

Behavior:
No count walk. Context held.
```

```text
Input:
no, that is not correct

Classification:
correction

Behavior:
No count walk. Correction acknowledged.
```

```text
Input:
what is truevision?

Classification:
question

Rendered shape:
TrueVision is a visual state path that preserves glyph, text, and document as state.
```

## Agent And Worker Future Boundary

Future agents and workers must obey this contract.

```text
Agents may receive engagement packets.
Workers may execute approved tasks.
Renderers may speak only admitted paths.
No agent may reinterpret info_transfer as a command without policy and context proof.
No worker may act from conversation flow alone.
```

## Tiny Lock

```text
We talk first.
We classify second.
We answer only when the input asks for answer behavior.
```
