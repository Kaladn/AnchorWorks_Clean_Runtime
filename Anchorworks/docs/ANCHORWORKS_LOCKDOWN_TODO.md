# AnchorWorks Lockdown TODO

Purpose: align V1 with what is needed now. No nice-to-have work. No broad rewrites. No V2. No UI expansion. No Python bulk-processing of count/symbol memory.

Core law:

```text
Python may orchestrate.
C++ does bulk symbol/count work.
Runtime speaks genome authority only.
Legacy artifacts may be archived or used as read-only reference, never runtime authority.
```

## Completed In This Lockdown Pass

### Runtime legacy count bridge removed

ClearSpeak no longer reads `Lexicon_Genome_Rebuild/mappings/old_symbol_to_genome_symbol.jsonl` to translate genome anchors into old AWSC cells at runtime.

Expected behavior:

```text
word -> genome symbol -> genome-native AWSC cell
```

Forbidden behavior:

```text
word -> genome symbol -> old-symbol bridge -> legacy AWSC cell
```

Receipt target:

```text
rg "_load_genome_legacy_count_bridge|old_symbol_to_genome_symbol|awsc_binary_symbol_cells_genome_legacy_bridge" Anchorworks/src/AnchorWorks/clearspeak.py
```

Expected:

```text
no matches
```

## Finish-Line Items

### 1. Restore counts through native rebuild, not transfer

Status: required.

Current truth:

```text
Live lexicon is genome.
Existing AWSC cells may still be old-symbol artifacts.
ClearSpeak now refuses the old runtime bridge.
```

Do not migrate millions of tiny cells in Python.
Do not transfer counts cell-by-cell in Python.

Correct path:

```text
source-local symbolic material
-> genome symbol resolution
-> native C++ 6-1-6 relation build/merge
-> genome-native AWSC output
-> native verify
-> ClearSpeak reads genome-native cells directly
```

Acceptance:

```text
native command writes genome-native AWSC
native verify ok
ClearSpeak count query returns support without legacy bridge
rg confirms no old-symbol bridge in runtime
```

### 2. Remove live Spare_Slots authority path

Status: required.

Problem:

`store.py` still contains live spare-slot read/write helpers.

Lock:

```text
Spare_Slots is historical/reference only.
Genome allocator is symbol authority.
```

Required work:

```text
disable runtime assignment from Spare_Slots
remove Spare_Slots from active status as available authority
preserve old files untouched outside active authority
update tests from spare-assignment expectations to genome-allocation expectations
```

Acceptance:

```text
rg "Spare_Slots|spare_slots|_read_spare_entries|_write_spare_entries" Anchorworks/src/AnchorWorks/store.py
```

Allowed only if explicitly labeled legacy/archive/read-only.

### 3. Collapse duplicate inference facade files

Status: required.

Problem:

`AnchorWorks/inference/` contains a facade plus stale duplicate implementation files. Runtime should use `aw_inference_kernel`.

Required work:

```text
keep AnchorWorks.inference as compatibility import facade only
remove stale duplicate implementation files
tests import through facade and external package
```

Acceptance:

```text
from AnchorWorks.inference import run_inference
from aw_inference_kernel import run_inference
```

Both return the same kernel contract.

### 4. Settings truth cleanup

Status: required before any serious UI work.

Problem:

Tree-Brain/settings endpoints expose controls that diagnostics admit are not wired into active ClearSpeak/count-walk runtime.

Required work:

```text
main settings shows runtime-active only
diagnostic-only controls are labeled diagnostic-only or removed from main surface
no fake cockpit switches
```

Acceptance:

```text
Every visible setting either changes runtime or clearly says diagnostic-only.
```

### 5. System-doc lane separation

Status: required for answer quality.

Problem:

System/self docs can pollute education answers with terms like:

```text
text, frame, question, answer, induction
```

Required work:

```text
system docs count into system-self lane only
education/general questions do not use system-self counts unless requested
```

Acceptance:

```text
"who is Isaac Newton" cannot answer from system-frame docs.
"what is AnchorWorks rendering" may use system-self lane.
```

### 6. Counts-mode renderer hardening

Status: current active algorithmic focus.

Required work:

```text
counts propose top-K
active cloud scores candidates
lookahead rejects anomalous paths
inference admits/rejects candidates
renderer speaks only accepted answer plan
```

Acceptance questions:

```text
what is inertia?
who is Isaac Newton?
why worry about laws of physics?
A 2 kg object is accelerating at 3 m/s^2. What net force is acting on it?
```

Required:

```text
no raw top-K word salad
no off-frame junk
trace shows accepted and rejected candidates
formula lane handles formula-shaped questions before counts/docs
```

## Parked

Do not work these until finish-line items above are closed:

```text
V2
invoked UI
phrase UI
TrueVision glyph recognition
GPU sparse scoring
Auto mode
large new data ingest
store.py full refactor
```

Tiny law:

```text
Finish the runtime spine before adding more body parts.
```
