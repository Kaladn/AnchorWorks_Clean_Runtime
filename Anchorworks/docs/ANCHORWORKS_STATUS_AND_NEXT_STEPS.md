# AnchorWorks Lexicon Status And Next Steps

Date: 2026-05-02

## What We Built

We rebuilt AnchorWorks as a standalone lexicon-first system.

The current foundation is:

```text
Lexicon
Document Intake
Anchor Mapping
6-1-6 Co-occurrence Counts
ClearSpeak Query
Chat + Memory Module
External API Chat Mode
```

The important rule is now locked:

```text
Every observed written unit becomes an anchor identity.
Anchor identity is always lowercase.
The original surface text is still preserved for inspection.
```

## What Changed Today

We copied 100 random supported files from `D:\` into:

```text
C:\Users\mydyi\OneDrive\Documents\Desktop\data\d_drive_random_100_20260502_134953
```

We launched the UI against the real data root:

```text
http://127.0.0.1:8081
```

We confirmed the real data root is:

```text
C:\Users\mydyi\OneDrive\Documents\Desktop\Lexical Data
```

We fixed several ingest rules:

```text
Uppercase is normalized to lowercase.
Leading apostrophe debris is stripped from anchor identity.
Real internal forms like don't stay intact.
Possessive endings like girls' stay intact.
Unicode visual leaders are stripped during document prep.
Large UI previews are capped so the browser does not try to render huge files.
```

Examples now behave like this:

```text
NASA      -> nasa
RT54TX    -> rt 5 4 tx
'apm      -> apm
’apm      -> apm
don't     -> don't
girls'    -> girls'
├──       -> stripped during prep
────      -> stripped during prep
```

## What Was Successfully Ingested

The base lifetime count lattice is accumulating.

Last confirmed base count state:

```text
Base ingest events: 10
Unique relations: 11,503,933
Total relation observations: 49,320,850
Anchor observation rows: 60,671
```

The base lifetime counts file is:

```text
C:\Users\mydyi\OneDrive\Documents\Desktop\Lexical Data\State\lifetime_co_occurrence_counts.json
```

This file grew very large, around 1.6 GB.

## Where Everything Is Saved

Main saved data:

```text
C:\Users\mydyi\OneDrive\Documents\Desktop\Lexical Data
```

Base lexicon:

```text
C:\Users\mydyi\OneDrive\Documents\Desktop\Lexical Data\Canonical
```

Deprecated domain-pack note:

```text
Deprecated domain-pack path removed from active AnchorWorks runtime.
```

Structural anchors:

```text
C:\Users\mydyi\OneDrive\Documents\Desktop\Lexical Data\Structural\structural.json
```

Spare slots:

```text
C:\Users\mydyi\OneDrive\Documents\Desktop\Lexical Data\Spare_Slots\spare_slots.json
```

Base lifetime counts:

```text
C:\Users\mydyi\OneDrive\Documents\Desktop\Lexical Data\State\lifetime_co_occurrence_counts.json
```

Observed debug maps:

```text
C:\Users\mydyi\OneDrive\Documents\Desktop\Lexical Data\State\observed_maps
```

Prepared intake files:

```text
C:\Users\mydyi\OneDrive\Documents\Desktop\Lexical Data\State\intake_uploads
```

Missing anchor review files:

```text
C:\Users\mydyi\OneDrive\Documents\Desktop\Lexical Data\State\misspelled_reviews
```

Chat memory:

```text
C:\Users\mydyi\OneDrive\Documents\Desktop\Lexical Data\State\chat_memory
```

User-side counts:

```text
C:\Users\mydyi\OneDrive\Documents\Desktop\Lexical Data\State\user\user_counts
```

Chat-side counts:

```text
C:\Users\mydyi\OneDrive\Documents\Desktop\Lexical Data\State\user\chat_counts
```

## What Caused The Laptop Crash Risk

The system worked, but the laptop was asked to carry too much at once.

The biggest pressure points were:

```text
Huge lifetime count JSON file
Very large observed map JSON files
UI/API status routes trying to summarize massive count data
Large debug maps being written for big documents
Browser rendering large prepared text and long review lists
```

One observed map became several GB by itself:

```text
C:\Users\mydyi\OneDrive\Documents\Desktop\Lexical Data\State\observed_maps
```

The durable learned structure is the lifetime counts file.

Observed maps are useful for debugging and replay, but they are not the core durable brain.

## Current Problem To Fix

The system needs a safer large-corpus mode.

Right now it can ingest and count, but for thousands of documents it should not:

```text
Write giant full observed maps by default.
Load the full lifetime count lattice into UI status calls.
Render huge prepared files in the browser.
Summarize millions of relations on every status request.
Run giant documents manually one by one.
```

## What We Should Do Next

Next build target:

```text
Safe Batch Ingest Mode
```

Required behavior:

```text
1. Read a manifest or folder queue.
2. Process one document at a time.
3. Preview coverage.
4. Stop if missing anchors exist.
5. Approve anchors in batches.
6. Map and update base lifetime counts only after coverage is complete.
7. Save compact ingest logs.
8. Make observed maps optional.
9. Never load the full count lattice just to show status.
10. Resume after crash from the last completed file.
```

The immediate safety changes should be:

```text
Make observed map saving optional or compact.
Add a lightweight counts metadata file.
Make ClearSpeak status read metadata only.
Add batch queue checkpointing.
Add a max document size warning in the UI.
Add a "headless ingest" path for long runs.
```

## Recovery Rule

Before more ingest:

```text
Back up Lexical Data.
Do not delete lifetime counts.
Do not delete Canonical.
Domain packs are not active AnchorWorks authority; quarantine instead of relying on them.
Do not delete Spare_Slots.
Observed maps can be archived or moved later if needed.
```

Critical backup folder:

```text
C:\Users\mydyi\OneDrive\Documents\Desktop\Lexical Data
```

## Plain English Summary

We proved the system works.

The lexicon is filling.

The lifetime count lattice is accumulating.

The anchor rules are now cleaner:

```text
lowercase identity
no leading apostrophe junk
visual leaders stripped
paragraph windows preserved
6-1-6 counts accumulating
```

The crash was not a concept failure.

It was a scale/load problem.

Next step is to make the same working system safer for large document batches.

