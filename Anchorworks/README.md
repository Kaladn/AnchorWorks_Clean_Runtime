# Anchorworks

Contained AnchorWorks lexicon service and UI.

This folder lives inside the active `Lexical Data` root so the app and durable lexicon state stay together.

It operates against the parent data root:

`C:\Users\mydyi\OneDrive\Documents\Desktop\Lexical Data`

## Install

```bash
pip install -e .
```

## Run

```bash
..\launch_anchorworks.ps1
```

Then open:

`http://127.0.0.1:8081`

## Test Harness

Test code and test-only harnesses live outside the app package:

```bash
python -m unittest discover -s "..\test\test data\tests"
```

## What it serves

- Lexicon explorer UI
- Canonical / structural / spare-slot browsing
- Spare-slot assignment
- Pending / ignored / unmatched state
- Import / clear / return-to-pool operations
- Document intake, resident chat memory, ClearSpeak, and lifetime co-occurrence counts

## System Map

The living data-flow contract is kept in:

- `docs/DATA_FLOW_MAP.md`

## Data root layout

The service expects:

- `Canonical/canonical_A.json` ... `canonical_Z.json`
- Deprecated domain-pack files are not part of the active AnchorWorks runtime.
- `Spare_Slots/spare_slots.json`
- `Structural/structural.json`

State files are created under:

- `State/unmatched_words.json`
- `State/pending_words.json`
- `State/ignored_words.json`
- `State/user/custom_entries.json`
