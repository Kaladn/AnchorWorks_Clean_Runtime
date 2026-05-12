# AnchorWorks Symbolic Binary Build Current

Status: active build document.

Date: 2026-05-11

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

## Visual Sovereignty Rule

Hard rule for every intake path:

```text
NEVER normalize before vision.
Vision is the deterministic truth record.
All cleanup, normalization, repair, compression, symbol conversion, or text shaping happens after visual proofing.
```

This means the first preservation layer must keep the original seen state:

```text
source file
-> visual/page/frame evidence if visualizable
-> native geometry/hash/order/timing
-> source-local visual proof
-> only then derived text cleanup or symbolic conversion
```

Text extraction may run in parallel as a source claim, but it may not overwrite or pre-clean the visual record. If source text and visual proof disagree, both sides stay recorded and the disagreement becomes evidence for review.

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
~~AWSM hot path for source-local symbol count artifacts~~
~~JSON observed-map fallback retained for parity/debug only~~
~~100-doc AWSM parity benchmark~~
~~AWSM block/line locator sidecar~~
~~AWSM NULL coordinate sidecar~~
~~AWSM visual-ref pointer sidecar~~
~~Binary read API for AWSM maps and sidecars~~
~~UI/API path aligned to AWSM/AWSL/AWSN/AWSV/AWSC as the runtime surface~~
~~Default app root corrected to D:\AnchorWorks_Clean_Runtime for this repo~~
~~Full OpenStax CNXML symbolic ingest completed from clean runtime root~~
~~Cloud Of Clouds answer contract~~
```

Current test confirmation:

```text
Full suite reached 138 passing tests after UI/root alignment.
No active runtime behavior was added for Cloud Of Clouds yet.
```

Current runtime confirmation:

```text
data_root: D:\AnchorWorks_Clean_Runtime
anchor_maps_root: D:\AnchorMaps
observed JSON witness maps: 2,656
AWSM maps: 2,656
AWSL locator sidecars: 2,656
AWSN NULL sidecars: 2,656
AWSV visual sidecars: 2,656
AWSS stream: D:\AnchorWorks_Clean_Runtime\State\symbol_streams\source_local_symbol_counts.awss
AWSS stream size: 1,802,161,488 bytes
AWSC cells: 147,678
```

Current UI confirmation:

```text
http://127.0.0.1:8081/
GET / returns 200
GET /app.js returns 200
GET /api/health reports D:\AnchorWorks_Clean_Runtime
GET /api/binary-substrate/status reports the live AWSM/AWSS/AWSC counts above
```

## Current Benchmarks

Benchmarks are last measured proof, not live startup state.

Current verification runner:

```text
python -m unittest discover -s tests
```

Native build path:

```text
Visual Studio bundled CMake is the supported native build path.
```

### Full OpenStax CNXML Runtime Ingest

This is a real current runtime state, not a parity benchmark.

Source:

```text
D:\curated data\raw_sources\openstax\extracted
```

Result:

```text
CNXML source files: 2,656
JSON observed maps written as witness/debug artifacts: 2,656
AWSM maps written to D:\AnchorMaps\symbolic_maps: 2,656
AWSL locator sidecars: 2,656
AWSN NULL sidecars: 2,656
AWSV visual sidecars: 2,656
Source-local symbol artifacts: 2,656
AWSS stream size: 1,802,161,488 bytes
AWSC cells verified by native verify: 147,678
Native verify errors: 0
```

Important nuance:

```text
This full ingest proves the symbolic binary path can carry the dataset.
It is not the same as a full JSON-vs-AWSM parity benchmark.
JSON artifacts still exist as witness/debug outputs in this run.
```

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

### 100 Mixed Source AWSM Parity

Mix:

```text
.cnxml  16
.html   12
.md     12
.css    10
.js     10
.json   10
.svg    10
.xml    10
.yml    10
```

Result:

```text
Dual-write total: 0.831s
AWSM artifact build: 0.441s
JSON fallback build: 0.536s
AWSM vs JSON artifact speedup: about 1.21x
AWSS/AWSC build from AWSM artifacts: 0.377s
Parity mismatches: 0
AWSS records: 7,256
AWSS observations: 8,688
AWSC cells verified: 348
AWSC verify errors: 0
```

Finding:

```text
AWSM serves source-local symbol artifacts with symbol authority, relation rows, and relation fates matching JSON fallback.
JSON remains fallback/parity/debug only.
```

## AWSM Hot Path Checkpoint

`build_source_local_symbol_counts()` now treats AWSM as the serving path.

Current flow:

```text
AWSM binary map
-> source-local symbol count artifact
-> AWSS stream
-> AWSC count cells
```

Fallback flow:

```text
JSON observed map
-> source-local symbol count artifact
```

The fallback exists for parity/debug only. It is no longer the preferred path.

Verification:

```text
AWSM works even when the JSON observed map is absent.
AWSM-derived artifacts match JSON-debug artifacts for symbol authority, relation rows, and relation fates.
Full unittest suite at that checkpoint: 123 tests OK.
Current full suite after later binary/UI/root work: 138 tests OK.
```

Current law:

```text
AWSM serves.
JSON witnesses.
AWSC counts.
Canonical governs.
```

## AWSM Locator Sidecar Checkpoint

AWSM now has a block/line locator sidecar.

Shape:

```text
AWSM relation file:      *.awsm
AWSM locator sidecar:    *.locators.awsl
```

The sidecar stores source-local block address rows:

```text
paragraph_id
block_id
line_start
line_end
anchor_count
countable_anchor_count
```

Verification:

```text
AWSL sidecar round-trips under CRC.
AWSL sidecar rejects corrupted payloads.
Ingest writes AWSL beside AWSM.
AWSL survives after JSON observed map deletion.
Full unittest suite at that checkpoint: 126 tests OK.
Current full suite after later binary/UI/root work: 138 tests OK.
```

Locator law:

```text
AWSM serves relations.
AWSL proves block and line address.
JSON remains witness/debug only.
```

## AWSM NULL Coordinate Sidecar Checkpoint

AWSM now has a NULL coordinate sidecar.

Shape:

```text
AWSM relation file:      *.awsm
AWSM locator sidecar:    *.locators.awsl
AWSM NULL sidecar:       *.nulls.awsn
```

The NULL sidecar stores parseable exclusions:

```text
block_id
line_start
line_end
anchor_position
anchor_label
observed_anchor
surface
resolved_anchor = __NULL__
count_eligible = false
memory_truth = false
```

Verification:

```text
AWSN sidecar round-trips under CRC.
AWSN sidecar rejects corrupted payloads.
Ingest writes AWSN beside AWSM/AWSL.
AWSN survives after JSON observed map deletion.
Full unittest suite at that checkpoint: 129 tests OK.
Current full suite after later binary/UI/root work: 138 tests OK.
```

NULL law:

```text
NULL is parseable.
NULL is locatable.
NULL is auditable.
NULL is not memory truth.
```

## AWSM Visual Reference Sidecar Checkpoint

AWSM now has a visual reference pointer sidecar.

Shape:

```text
AWSM relation file:      *.awsm
AWSM locator sidecar:    *.locators.awsl
AWSM NULL sidecar:       *.nulls.awsn
AWSM visual sidecar:     *.visuals.awsv
```

The visual sidecar stores source-local visual pointers:

```text
block_id
block_ordinal
line_start
line_end
visual_record_id
kind
source_path_ref
alt_text
title
caption_block_id
manifest_id
geometry_status
recognition_status
writes_allowed
```

Verification:

```text
AWSV sidecar round-trips under CRC.
AWSV sidecar rejects corrupted payloads.
Ingest writes AWSV beside AWSM/AWSL/AWSN.
AWSV survives after JSON observed map deletion.
Full unittest suite at that checkpoint: 132 tests OK.
Current full suite after later binary/UI/root work: 138 tests OK.
```

Visual law:

```text
Visual refs witness source structure.
Visual refs do not write Canonical, counts, lifetime, or lexicon.
Recognition remains not-run until a visual backend earns evidence.
```

## AWSM Binary Bundle Read API Checkpoint

AWSM now has a single read API for the binary map family.

Low-level API:

```text
read_symbolic_map_bundle(path)
```

Store API:

```text
LexiconStore.load_symbolic_map_bundle(name)
```

The bundle loads:

```text
AWSM relations
AWSL block/line locators
AWSN NULL coordinates
AWSV visual references
```

Missing sidecars return empty lists, not fake rows.

Verification:

```text
Bundle reader loads AWSM + AWSL + AWSN + AWSV together.
Bundle reader tolerates absent optional sidecars.
Store API resolves old observed-map names to AWSM bundles.
Store API works after JSON observed map deletion.
Full unittest suite at that checkpoint: 135 tests OK.
Current full suite after later binary/UI/root work: 138 tests OK.
```

Read API law:

```text
AWSM is the serving map.
Sidecars restore audit shape.
JSON is not required to read the binary evidence bundle.
```

## UI And App Root Checkpoint

The UI path is now aligned to the symbolic binary runtime.

Primary UI/API surfaces:

```text
GET /api/lexicon/symbolic-maps
GET /api/lexicon/symbolic-map/{name}
GET /api/binary-substrate/status
```

The app surface now presents:

```text
Symbolic Maps
AWSM bundle loading
AWSL locator samples
AWSN NULL coordinate samples
AWSV visual reference samples
AWSC cell status
JSON maps as witness/debug only
```

The older observed-map route still exists:

```text
GET /api/lexicon/observed-maps
GET /api/lexicon/observed-map/{name}
```

But those routes are compatibility/debug surfaces, not the primary UI path.

Root selection:

```text
ANCHORWORKS_DATA_ROOT wins if set.
When running from this repo, default root is D:\AnchorWorks_Clean_Runtime.
The old OneDrive Lexical Data path is only fallback behavior.
```

UI verification:

```text
GET / returns 200
GET /app.js returns 200
GET /api/health reports D:\AnchorWorks_Clean_Runtime
GET /api/binary-substrate/status reports 2,656 AWSM maps and 147,678 AWSC cells
Full unittest suite: 138 tests OK
```

UI law:

```text
AWSM serves the UI.
AWSL/AWSN/AWSV restore audit shape.
AWSC reports count substrate status.
JSON witnesses only.
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

AnchorMaps is created by runtime/store initialization.

## Cloud Of Clouds Contract

Cloud Of Clouds is contract-only until implemented.

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
~~Patch this current build document with verification nuances.~~
~~Build source-local symbol count artifacts directly from AWSM instead of JSON observed maps.~~
~~Route source-local symbol artifact builder through AWSM by default.~~
~~Add 100-doc AWSM parity benchmark.~~
~~Add AWSM block/line locator section or sidecar.~~
~~Add AWSM NULL coordinate section or sidecar.~~
~~Add AWSM visual-ref pointer section or sidecar.~~
~~Add binary read API for AWSM maps.~~
~~Align UI/API map browser to AWSM bundle routes.~~
~~Correct default app root to D:\AnchorWorks_Clean_Runtime.~~
~~Run full OpenStax CNXML symbolic ingest through current binary path.~~
1. Make JSON observed-map output optional debug mode.
2. Add no-JSON rebuild proof: AWSM/AWSL/AWSN/AWSV + AWSS + AWSC from source with JSON disabled.
3. Add a larger AWSM parity benchmark only if needed for regression confidence; the 100-doc parity proof already exists.
4. Add CloudOfClouds builder from AWSC cells.
5. Add AnswerField builder with cloud caps.
6. Add AnswerPath walker with path-health scoring.
7. Move native scoring into ClearSpeak behind a binary-read feature gate.
8. Add batch-aware native scoring for many active contexts.
9. Only after CPU-native proof: design GPU sparse symbolic field loader.
```

## Ready Confirmations

Current branch state is ready to continue from the binary work:

```text
AWSC exists.
AWSS exists.
AWSM exists.
AWSM serves source-local symbol count artifacts.
Full OpenStax CNXML runtime ingest exists in the current data root.
AWSM block/line locator sidecar exists.
AWSM NULL coordinate sidecar exists.
AWSM visual-ref pointer sidecar exists.
AWSM binary bundle read API exists.
UI/API binary map browser exists.
Default app root points at D:\AnchorWorks_Clean_Runtime from this repo.
Native C++ merge exists.
Native C++ verify exists.
Native C++ score exists.
JSON count ingest writes are removed.
JSON observed maps are parity/debug fallback for this path.
New maps write outside runtime State.
Batch intake exists.
Cloud Of Clouds contract exists.
Next build target is optional JSON observed-map output, then no-JSON rebuild proof.
```

## Do Not Do Yet

```text
Do not implement binary lexicon/meta yet.
Do not make GPU the first implementation target.
Do not delete JSON debug maps until optional debug mode and no-JSON rebuild proof both pass.
Do not route renderer speech through evidence labels.
Do not let one top-k choice decide alone.
```
