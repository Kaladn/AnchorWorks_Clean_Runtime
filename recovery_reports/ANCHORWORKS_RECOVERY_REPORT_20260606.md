# AnchorWorks Recovery Report

Date: 2026-06-06

Scope: contamination cleanup report only. No runtime deletes were performed.

## Roots

Real git repo root:

```text
D:\AnchorWorks_Clean_Runtime
```

Code folder:

```text
D:\AnchorWorks_Clean_Runtime\Anchorworks
```

Intended real runtime/data root:

```text
D:\AnchorWorks_Clean_Runtime\State
```

Bad repo-local pollution root:

```text
D:\AnchorWorks_Clean_Runtime\Anchorworks\State
```

## Patch And Inventory Exports

Dirty patch:

```text
D:\AnchorWorks_Clean_Runtime\recovery_reports\anchorworks_dirty_patch_20260606_134721.patch
```

Dirty status:

```text
D:\AnchorWorks_Clean_Runtime\recovery_reports\anchorworks_dirty_status_20260606_134721.txt
```

Dirty diffstat:

```text
D:\AnchorWorks_Clean_Runtime\recovery_reports\anchorworks_dirty_diffstat_20260606_134722.txt
```

## Runtime State Sizes

Bad repo-local state:

```text
D:\AnchorWorks_Clean_Runtime\Anchorworks\State
files: 15
bytes: 97,081,174
size: 92.584 MiB
```

Real runtime state:

```text
D:\AnchorWorks_Clean_Runtime\State
files: 1,943,250
bytes: 74,758,949,062
size: 71,295.69 MiB
```

## Confirmed Bad Repo-Local Writes

These are under the code folder and should not be treated as intended runtime:

```text
D:\AnchorWorks_Clean_Runtime\Anchorworks\State\user\chat_logs\2026-06-06.jsonl
D:\AnchorWorks_Clean_Runtime\Anchorworks\State\user\user_counts\symbol_counts_binary\user_count_acknowledgement.json
D:\AnchorWorks_Clean_Runtime\Anchorworks\State\user\ingest_staging\manifest.json
D:\AnchorWorks_Clean_Runtime\Anchorworks\State\user\user_lexicon\anchors.json
D:\AnchorWorks_Clean_Runtime\Anchorworks\State\missing_anchor_registry.json
D:\AnchorWorks_Clean_Runtime\Anchorworks\State\pending_words.json
D:\AnchorWorks_Clean_Runtime\Anchorworks\State\unmatched_words.json
D:\AnchorWorks_Clean_Runtime\Anchorworks\State\ignored_words.json
D:\AnchorWorks_Clean_Runtime\Anchorworks\State\code_lexicon_mirror\code_lexicon_mirror.jsonl
```

Largest bad repo-local file:

```text
D:\AnchorWorks_Clean_Runtime\Anchorworks\State\code_lexicon_mirror\code_lexicon_mirror.jsonl
~96.9 MB
```

## Real Runtime Dirty Contamination

The first failed import happened before automatic user-lexicon seeding was removed. It modified:

```text
D:\AnchorWorks_Clean_Runtime\State\user\user_lexicon\anchors.json
size: 79,532,559 bytes
git diff: 3,103,377 added lines, 1 deleted line
```

This file is tracked by the repo and should be handled explicitly before commit.

## Current Git Dirty Summary

Known dirty areas:

```text
Anchorworks/src/AnchorWorks/...
Anchorworks/docs/...
Anchorworks/tests/... old tests deleted, new tests added
State/chat_memory/... tracked placeholders deleted
State/user/user_lexicon/anchors.json modified
```

Important deleted source files:

```text
Anchorworks/src/AnchorWorks/symbol_relation_counts.py
Anchorworks/src/AnchorWorks/lifetime_symbol_mirror.py
```

Important new tests:

```text
Anchorworks/tests/test_chat_jsonl_memory.py
Anchorworks/tests/test_native_count_cli_surface.py
Anchorworks/tests/test_native_count_executable.py
Anchorworks/tests/test_native_count_ingest_governance.py
Anchorworks/tests/test_native_count_routes.py
Anchorworks/tests/test_native_mapping_ui_surfaces.py
Anchorworks/tests/test_native_user_mapping_pipeline.py
```

## Tests Run Before Hard Stop

Command:

```powershell
$env:PYTHONPATH='D:\AnchorWorks_Clean_Runtime\Anchorworks\src'
python -m pytest -q tests
```

Result:

```text
25 passed in 2.05s
```

Additional check:

```text
NO_FORBIDDEN_PYTHON_COUNT_PATHS
```

## Tests That Write State

The active tests use `tmp_path` and therefore write temp state, not real runtime, when invoked correctly:

```text
test_chat_jsonl_memory.py
test_native_count_routes.py
test_native_mapping_ui_surfaces.py
test_native_user_mapping_pipeline.py
```

Risk area:

```text
Importing AnchorWorks.app creates a global app at module import time.
Before the auto-seed fix, that global app used the default data root and wrote real runtime state.
```

Relevant source:

```text
D:\AnchorWorks_Clean_Runtime\Anchorworks\src\AnchorWorks\app.py
```

## Good Work To Preserve

The green test run indicates the following recent work is coherent:

```text
JSONL chat memory tests
native AWSC count CLI tests
native count executable tests
native ingest governance tests
native route tests
native mapping UI surface tests
native user mapping pipeline tests
```

Implementation changes worth preserving after cleanup:

```text
No old Python count-producing ingest paths.
Native AWSC binary cells are the count spine.
User count seeding is explicit instead of import-time.
User lexicon seeding is explicit instead of import-time.
ClearSpeak no longer falls back to old JSON relation-count loaders.
```

## Required Cleanup Proposal

Do not execute without approval:

```text
1. Preserve the patch file listed above.
2. Restore or move tracked runtime file:
   D:\AnchorWorks_Clean_Runtime\State\user\user_lexicon\anchors.json
3. Remove bad repo-local state:
   D:\AnchorWorks_Clean_Runtime\Anchorworks\State
4. Add guard so code root cannot create:
   D:\AnchorWorks_Clean_Runtime\Anchorworks\State
5. Ensure tests never instantiate default data root during import.
6. Rerun tests with explicit temp roots only.
7. Rerun one manual integration check with explicit:
   D:\AnchorWorks_Clean_Runtime
```

## Hard Law

```text
Tests use temp roots.
Runtime uses D:\AnchorWorks_Clean_Runtime\State.
Code folder must not grow Anchorworks\State.
No import-time seed writes.
No repo-tracked user runtime data commits.
```
