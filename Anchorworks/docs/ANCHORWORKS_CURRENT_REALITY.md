# AnchorWorks Current Reality

Status: authoritative current documentation for this repository.

This document is the only active AnchorWorks system document. Older design notes, bridge notes, Genesis notes, and historical build plans were removed from the active docs because they no longer matched the code.

## Runtime Shape

AnchorWorks is a deterministic anchor, symbol, source, and count runtime.

The active public runtime is the Python package under `src/AnchorWorks`. The public store import remains:

```text
from AnchorWorks.store import LexiconStore
```

`store.py` is now a compatibility facade. Store behavior is split into Python mixin modules under `src/AnchorWorks/store_runtime`, with shared support helpers in `src/AnchorWorks/store_support.py`.

No C++ store rewrite is active yet. Existing C++ is used through native command-line cores for symbol counts and symbol genome support.

## Authority And Symbols

Canonical is the trusted shared base. Canonical lexicon writes are locked in the active API and store routes.

User lexicon is the local observed acceptance layer:

```text
State/user/user_lexicon/anchors.json
```

New approved observed anchors go to the user lexicon. Raw observed spelling is preserved there, including misspellings, OCR junk, names, slang, and domain-specific forms.

Symbol authority ranges:

```text
canonical = low 40-bit symbols, lane 0
user_lexicon = 0xE... symbols, lane 5
source_local = 0xF... symbols, lane 4
```

Counts receive symbols, not raw anchor text. Spelling and provenance live in authority sidecars and lexicon records.

## Counts

Canonical binary counts are a seed snapshot:

```text
State/symbol_counts_binary/
```

The active writable count root is user-side:

```text
State/user/user_counts/symbol_counts_binary/
```

The store copies missing canonical seed files into the user-side count root and records:

```text
State/user/user_counts/symbol_counts_binary/user_count_acknowledgement.json
```

After seeding, runtime count additions merge into the user-side root only. Canonical count data remains readable as the seed and must not be treated as the active writable target.

## Intake

Text intake prepares source text, extracts anchors, resolves known anchors through Canonical plus user lexicon, assigns source-local symbols for document oddities, writes observed/symbolic maps, and builds symbol count artifacts.

Unknown observed forms are not silently cleaned into Canonical. They are either accepted into user lexicon by approval or represented as source-local symbols for the source.

Conversation corpus intake is separate from truth evidence. It can build conversation-flow counts and symbolic source exports, but those artifacts do not become factual evidence unless later routed through normal reviewed intake.

## ClearSpeak And Conversation

ClearSpeak reads recognized anchors, source evidence, and active user-side binary counts. It must not use generic bridge language unless the selected evidence path supports it.

Conversation runtime is installed as `conversation_engine`. It classifies greetings, corrections, notes, questions, and unsupported prompts without silently writing count memory.

## Terminal And API Surface

The current interface surface is:

```text
anchorworks shell
anchorworks operator
anchorworks serve
```

The FastAPI app exposes ClearSpeak, chat, lexicon, intake, symbolic map, visual intake, flat document, resonance, and binary count status/build routes.

Destructive Canonical routes are intentionally blocked. They return locked responses and do not mutate Canonical.

## TrueVision Boundary

TrueVision language code in this repo is state capture and visual/language boundary support, not prompt generation.

Required current wording:

```text
glyph-state capture
SegmentField becomes LanguageSegmentField
not prompt generation
No generated video/media artifacts live in AnchorWorks
```

Copied TrueVision method files under `external_methods/truevision_generation_lab` are read-only reference material. They are not imported into the runtime.

## Four-Anchor Unit Counts

Four-anchor unit counts are a sibling experimental count layer.

Required current rules:

```text
Do not replace solo counts.
Unit4 stream = fixed ordered groups of 4 anchors.
6-1-6 over unit4
```

This layer does not mutate solo symbol counts, Canonical, user lexicon, or lifetime count state.

## Documentation Rule

This file is the active truth document. If code changes the system reality, update this file in the same change.
