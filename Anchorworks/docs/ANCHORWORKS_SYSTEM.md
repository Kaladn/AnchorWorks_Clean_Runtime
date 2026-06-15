# AnchorWorks System

AnchorWorks is the local language and count runtime. Its job is to admit text, attach it to the user lexicon, update the single count spine, and answer by walking the stored count evidence. It is not an LLM layer and it does not invent answer content when the evidence walk is incomplete.

## Current Law

AnchorWorks has one active user count authority:

```text
State/user/user_counts/symbol_counts.bin
```

The user lexicon is JSON:

```text
State/user/user_lexicon/anchors.json
```

That split is absolute:

```text
lexicon = JSON
counts = one binary file
compute = native executable
Python = orchestration, routing, rendering, receipts
```

JSON may be used for lexicon entries, manifests, receipts, settings, UI payloads, and review records. JSON may not be used as AnchorWorks count memory.

## Runtime Shape

`LexiconStore` is the main facade. It gathers the store powers for intake, lexicon work, memory records, evidence, visual support, administration, and native count mapping.

The active count path is:

```text
input text or approved document
-> native count intake
-> State/user/user_counts/symbol_counts.bin
-> native count scoring
-> ClearSpeak evidence walk
-> rendered answer
```

The active answer path is evidence-first. ClearSpeak receives a query, resolves observed anchors, asks the native count scorer for count relationships, admits enough connected evidence, and renders from what the walk actually found. A short or incomplete answer means the search/admission path needs work; it does not mean the renderer should fabricate missing content.

## Main Components

`src/AnchorWorks/store.py`
Defines the `LexiconStore` facade and canonical user paths.

`src/AnchorWorks/store_modules/paths.py`
Defines the same canonical state paths for composed store powers.

`src/AnchorWorks/store_runtime/counts.py`
Routes approved text or directories into the native count intake and routes query evidence through native scoring.

`src/AnchorWorks/symbol_count_native.py`
Builds and invokes the native count executable. Python does not compute, parse, or score the count file itself.

`src/AnchorWorks/native/symbol_counts/`
Owns count intake and scoring.

`src/AnchorWorks/store_runtime/lexicon.py`
Owns user lexicon read/write behavior.

`src/AnchorWorks/clearspeak.py`
Owns the answer rendering surface after the count walk has produced evidence.

`src/AnchorWorks/app.py`, `src/AnchorWorks/cli_shell.py`, and `src/AnchorWorks/terminal_operator.py`
Expose the runtime through API, shell, and terminal surfaces.

## Data Classes

Canonical and structural lexicons are source/reference material.

The user lexicon is the writable user language surface. It is human-readable JSON because it stores symbols, anchors, authority, and lexical metadata.

The user count spine is the writable count surface. It is exactly one native binary file.

Working chat and intake records may exist as text or JSONL before explicit consolidation. They are not count authority until the native count intake writes the binary count spine.

Receipts and manifests describe work already performed. They are not count memory.

## Hard Boundaries

No component may create a second AnchorWorks count store.

No component may create a JSON count companion.

No Python component may become a count compute fallback.

No UI, test, preview, or chat helper may silently create count authority outside the single binary file.

No answer renderer may compensate for missing evidence by inventing content.

## Verification

The current spine test is:

```text
tests/test_single_binary_count_spine.py
```

It proves that native intake writes the single binary count file, native scoring reads that file, and stale count side stores are not created.

The expected cleanup scan is:

```text
State must not contain alternate AnchorWorks count stores.
docs and tests must not teach stale count roots.
runtime answers must trace back to native count evidence.
```

## Current Risk Gate

Some modules may still use the word "count" for local statistics, visual profiles, or metadata. That wording is only acceptable when it is not AnchorWorks user count memory and cannot be confused with the binary count spine. Anything that writes durable user count evidence must use the native count path.
