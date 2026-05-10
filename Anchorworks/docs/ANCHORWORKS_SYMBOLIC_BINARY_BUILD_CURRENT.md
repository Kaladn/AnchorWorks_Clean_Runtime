# AnchorWorks Symbolic Binary Build Current

Status: active build document.

Date: 2026-05-10

This file replaces the scattered working notes for the current binary-brain branch. Older notes are archived under:

```text
docs/build historical
```

## Core Direction

AnchorWorks is moving from file-shaped runtime data to verified symbolic binary substrates.

The source file is allowed to be a file. After intake, the system should increasingly work from symbols and binary structures:

```text
source file
-> prepared source text or media evidence
-> anchors
-> symbols
-> AWSM symbolic map
-> AWSS symbol stream
-> AWSC count cells
-> cloud/answer fields
-> renderer
```

Core law:

```text
Strings are I/O.
Symbols are computation.
Binary cells are memory.
Clouds limit the answer surface.
The renderer speaks the completed path.
```

## Hardware And Toolchain

Confirmed current machine:

```text
CPU: AMD Ryzen 9 9950X3D 16-Core Processor
Physical cores: 16
Logical processors: 32
RAM: about 64 GB
OS: Windows 11 Pro
```

Native toolchain:

```text
Visual Studio Community 2026
MSVC 14.50
Bundled CMake
Generator: Visual Studio 18 2026
Architecture: x64
```

## Current Binary Substrates

### AWSM

AWSM means:

```text
AnchorWorks Symbolic Map
```

AWSM is the binary source-local symbolic map layer.

Current shape:

```text
64-byte header
24-byte relation rows
5-byte root symbol
5-byte neighbor symbol
offset
lane
flags
count
metadata CRC
relation payload CRC
```

Current proof:

```text
35 mixed source docs
JSON observed maps: 3,715,106 bytes
AWSM maps:          201,830 bytes
Size reduction: about 18.4x
AWSM read scan: about 3.36x faster than JSON parse/scan
Shape/data mismatches: 0
```

### AWSS

AWSS means:

```text
AnchorWorks Symbol Stream
```

AWSS is the compact stream consumed by native count merge.

Record size:

```text
24 bytes
root_symbol[5]
neighbor_symbol[5]
offset_i8
lane_u8
flags_u8
root_lane_u8
reserved_u16
count_u64
```

### AWSC

AWSC means:

```text
AnchorWorks Symbol Count
```

AWSC stores merged relation cells.

Current shape:

```text
64-byte header
16-byte relation rows
5-byte neighbor symbol
offset
lane
flags
count
payload CRC
generation
reserved WAL frame
reserved overflow offset
```

Native command surface:

```text
anchorworks-symbol-counts merge-stream
anchorworks-symbol-counts verify
anchorworks-symbol-counts inspect
anchorworks-symbol-counts score
```

## Completed Work

These are completed on the active branch:

```text
~~AWSC v1.1 binary cell contract~~
~~Python AWSC reader/writer~~
~~CRC rejection tests for AWSC~~
~~Native MSVC/C++ AWSC merge spine~~
~~AWSS stream writer from source-local symbol artifacts~~
~~Native AWSC verify command~~
~~Native AWSC inspect command~~
~~Native AWSC score command~~
~~Python wrapper for native scoring~~
~~Legacy JSON count ingest/write path removed~~
~~Observed maps moved out of runtime State path~~
~~New maps route to external AnchorMaps root~~
~~Grouped symbolic batch intake primitive~~
~~Symbolic batch intake CLI~~
~~AWSM binary symbolic map format~~
~~AWSM CRC tests~~
~~AWSM mixed-format proof with text, MD, JSON, HTML~~
~~35-doc mixed source dual-write benchmark~~
~~Cloud Of Clouds answer contract~~
```

Current test confirmation:

```text
Full suite reached 121 passing tests after AWSM.
No active runtime behavior was added for Cloud Of Clouds yet.
```

## Current Benchmarks

### 35 Mixed Source Documents

Mix:

```text
.cnxml  10
.html    5
.css     4
.js      4
.svg     4
.xml     3
.json    2
.yml     2
.md      1
```

Result:

```text
Dual-write total: 3.212s
Average per file: 0.0918s
Median per file: 0.0249s
AWSM shape/data mismatches: 0
Symbol artifact build: 0.244s
AWSC build: 1.024s
AWSS records: 7,646
AWSS observations: 17,282
AWSC cells verified: 364
AWSC verify errors: 0
AWSM read scan: about 958,686 relations/sec
JSON read scan: about 285,435 relations/sec
Native AWSC score call: 0.0095s
```

### Repo Folder Stress

Result after excluding build/binary/cache/image files and capping oversized source files:

```text
Sources mapped: 156
Groups: 15
Workers: 16
Elapsed: 87.81s
Maps: 156
Symbol artifacts: 156
Anchor observations: 660,715
AWSS records: 2,363,056
AWSS observations: 7,563,180
AWSC cells verified: 16,024
Verify errors: 0
```

Finding:

```text
Large structured data files can still explode the compatibility JSON observed-map path.
AWSM/AWSS/AWSC are the path out.
```

## Vision And Media Boundary

The visual intake law remains active:

```text
Visuals are source-local evidence sidecars.
They do not write Canonical.
They do not write lifetime.
They do not become truth without approval.
```

Images correctly refuse text map/count promotion.

For clean rebuilds:

```text
text and source-layout data enter the symbolic binary lane
visuals enter visual evidence packets
visual refs are linked back to document blocks later
```

## Cloud Of Clouds Contract

The answer system must not load the whole symbolic brain for every answer.

Object model:

```text
ContextCloud
CloudOfClouds
AnswerField
AnswerPath
Renderer
```

Runtime flow:

```text
query symbols
-> open seed ContextClouds
-> score neighboring clouds
-> open only needed clouds
-> build compact AnswerField
-> top-k candidate walk
-> track AnswerPath
-> path-health score
-> render
```

Law:

```text
Do not search the brain. Wake the right clouds.
```

Top-k law:

```text
Top-k proposes anchors.
The path decides sequence.
The renderer speaks the path.
```

Evidence law:

```text
Evidence constrains claims.
Evidence labels are not speech.
```

## GPU Direction

GPU does not mean neural net training here.

GPU means:

```text
verified symbolic binaries resident in high-throughput memory
sparse relation fields
cloud activation fields
candidate score fields
batched path exploration
```

Corrected direction:

```text
CPU builds and verifies.
GPU may become the active symbolic substrate.
AnchorWorks gates authority.
```

The GPU must not invent. It may later hold verified AnchorWorks binary structures and perform fast symbolic field scoring.

## Final Todo

Start here when returning to binaries:

```text
1. Build source-local symbol count artifacts directly from AWSM instead of JSON observed maps.
2. Add AWSM block/line locator section or sidecar.
3. Add AWSM NULL coordinate section or sidecar.
4. Add AWSM visual-ref pointer section or sidecar.
5. Add binary read API for AWSM maps.
6. Add 100-doc AWSM parity benchmark.
7. Add 1000-doc AWSM parity benchmark.
8. Make JSON observed-map output optional debug mode.
9. Route source-local symbol artifact builder through AWSM by default.
10. Route AWSS creation through AWSM-derived artifacts.
11. Add CloudOfClouds builder from AWSC cells.
12. Add AnswerField builder with cloud caps.
13. Add AnswerPath walker with path-health scoring.
14. Move native scoring into ClearSpeak behind a binary-read feature gate.
15. Add batch-aware native scoring for many active contexts.
16. Only after CPU-native proof: design GPU sparse symbolic field loader.
```

## Ready Confirmations

Current branch state is ready to continue from the binary work:

```text
AWSC exists.
AWSS exists.
AWSM exists.
Native C++ merge exists.
Native C++ verify exists.
Native C++ score exists.
JSON count ingest writes are removed.
New maps write outside runtime State.
Batch intake exists.
Cloud Of Clouds contract exists.
Next build target is AWSM -> source-local symbol artifacts.
```

## Do Not Do Yet

```text
Do not implement binary lexicon/meta yet.
Do not make GPU the first implementation target.
Do not delete JSON debug maps until AWSM carries block/line/NULL/visual refs.
Do not route renderer speech through evidence labels.
Do not let one top-k choice decide alone.
```
