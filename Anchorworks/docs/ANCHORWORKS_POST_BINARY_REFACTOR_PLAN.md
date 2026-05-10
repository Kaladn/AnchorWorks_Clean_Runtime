# AnchorWorks Post-Binary Refactor Plan

Status: shelved until AWSC v1.1 and the native binary count spine are constructed.

## Purpose

`store.py` and `chat_memory_system.py` are allowed to remain compatibility facades while the binary count spine is being built. They must not keep absorbing new behavior after the binary spine is stable.

The refactor is intentionally postponed because the binary storage path needs stable integration points first.

```text
AWSC first.
C++ spine second.
God-file split after binary proof.
```

## Rails

```text
No route behavior changes during the split.
No data root changes.
No lifetime count writes during refactor tests.
No runtime data commits.
No public method renames in the first pass.
No incidental cleanup.
```

## Store Split

`src/AnchorWorks/store.py` remains as the public facade during the first pass.

Target ownership:

```text
store_core.py
  paths
  atomic JSON helpers
  shared state root
  common file utilities

lexicon_store.py
  Canonical reads/writes
  spare slot management
  user lexicon reads/writes

document_runtime_store.py
  observed map access
  flat symbolic documents
  block indexes
  occurrence indexes

count_store.py
  source-local preview counts
  lifetime count access
  source-local symbol count paths
  binary symbol count paths

visual_store.py
  visual manifests
  visual links
  visual sidecars

resonance_store.py
  positional resonance
  context clouds
  occurrence-derived resonance files

cleanup_store.py
  cleanup ledger
  rebuild readiness
  audit reports
```

Extraction order:

```text
1. store_core.py
2. lexicon_store.py
3. visual_store.py
4. document_runtime_store.py
5. resonance_store.py
6. count_store.py
7. cleanup_store.py
```

Counts move late because they are the loaded path.

## Chat Split

`src/AnchorWorks/chat_memory_system.py` remains as the public facade during the first pass.

Target ownership:

```text
chat_paths.py
  chat storage roots
  branch paths
  archive staging paths

chat_ledger.py
  chat messages
  branches
  citations
  notes

chat_attachment_bridge.py
  file attachments
  chat-side intake staging

chat_archive_adapter.py
  imported chat archive parsing
  external chat archive conversion

chat_finalize_bridge.py
  preview/finalize chat into approved intake/count path

chat_response_bridge.py
  document mode
  count mode
  model/API fallback routing
```

Extraction order:

```text
1. chat_paths.py
2. chat_ledger.py
3. chat_attachment_bridge.py
4. chat_archive_adapter.py
5. chat_finalize_bridge.py
6. chat_response_bridge.py
```

Finalize and response routing move late because they touch intake, counts, and user-visible behavior.

## Characterization Tests First

Before moving logic:

```text
freeze public method inventory
add tests for current return shapes
add tests for no count writes in read-only paths
add route smoke tests for existing imports
```

After each extraction:

```text
run full unit suite
confirm route imports still work
confirm runtime data remains untracked
```

## Definition Of Done

First-pass completion requires:

```text
store.py still exists
chat_memory_system.py still exists
routes still import the same public classes
tests pass
UI still opens
runtime data remains ignored
facades are smaller
lanes have named owners
```

## Law

```text
Split ownership before changing behavior.
Bridges stay dumb.
Counts move last.
```
