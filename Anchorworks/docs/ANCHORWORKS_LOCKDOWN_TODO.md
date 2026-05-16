# AnchorWorks Lockdown TODO

Purpose: keep V1 aligned with the system we are actually building. No museum pieces. No scaffold paths. No runtime scaffold layers.

Core law:

```text
Genome symbols are the only live identity.
Genome-native AWSC is required.
Python may orchestrate only.
C++ performs bulk symbol/count work.
Final systems do not carry scaffolding.
```

## Completed

### ClearSpeak identity path

Current runtime rule:

```text
word -> genome symbol -> genome-native AWSC cell -> renderer
```

ClearSpeak does not translate count identity through removed build scaffolds. If genome-native cells are absent, ClearSpeak reports missing count support instead of crossing identity lanes.

Receipts:

```powershell
rg "alias|fallback|translation" Anchorworks/src/AnchorWorks/clearspeak.py
```

Expected:

```text
no matches
```

## Finish-Line Items

### 1. Rebuild counts natively from source-local symbolic material

Status: required.

Correct path:

```text
source-local symbolic material
-> genome symbol resolution
-> native C++ 6-1-6 relation build/merge
-> genome-native AWSC output
-> native verify
-> ClearSpeak reads genome-native cells directly
```

Hard rules:

```text
Do not bulk-process count cells in Python.
Do not transfer count cells.
Do not create runtime identity aliases.
Do not add identity fallback.
```

Acceptance:

```text
native command writes genome-native AWSC
native verify ok
ClearSpeak count query returns support from genome-native cells
```

### 2. Remove live Spare_Slots authority path

Status: required.

Rule:

```text
Genome allocator is symbol authority.
Spare_Slots is not runtime authority.
```

Required work:

```text
disable runtime assignment from Spare_Slots
remove Spare_Slots from active status as available authority
preserve curated files outside active authority if needed
update tests from spare-assignment expectations to genome-allocation expectations
```

### 3. Collapse duplicate inference facade files

Status: required.

Rule:

```text
aw_inference_kernel owns inference implementation.
AnchorWorks.inference is import facade only.
```

Acceptance:

```text
from AnchorWorks.inference import run_inference
from aw_inference_kernel import run_inference
```

Both return the same kernel contract.

### 4. Settings truth cleanup

Status: required before serious UI work.

Rule:

```text
Every visible setting either changes runtime or clearly says diagnostic-only.
```

No fake cockpit.

### 5. System-doc lane separation

Status: required for answer quality.

Rule:

```text
system-self docs answer system-self questions only
education/general questions use education/general count lanes only
```

### 6. Counts-mode renderer hardening

Status: current active algorithmic focus.

Required path:

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

Required behavior:

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

