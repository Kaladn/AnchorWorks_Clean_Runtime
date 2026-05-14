# AnchorWorks Architecture Path Trace

Date: 2026-05-14

Purpose: trace the current AnchorWorks V1 paths before drawing a new architecture chart. This is a connection report, not an implementation plan. A box is marked active only when a traced code path or runtime artifact proves it is connected.

Core law:

```text
Trace first.
Chart second.
Fix third.
```

## Summary

Current truth:

```text
Live lexicon authority: word -> genome symbol
Current AWSC count cells: legacy/older symbols from the count build
ClearSpeak runtime: decodes live genome lexicon, then uses old-symbol bridge mappings to read legacy AWSC cells
Phrase authority: storage and renderer hook exist, but live phrase authority is empty
Maps: external D:\AnchorMaps carries observed JSON, AWSM, AWSL, AWSN, AWSV
Runtime docs: local overlays and source-local symbol-count artifacts exist under State
V2: separate contract/control-plane destination, not active V1 runtime
```

Big chart gap:

```text
GENOME <-> LEGACY AWSC COUNT IDENTITY BRIDGE
```

This is active as a compatibility bridge, not final architecture. Final tightening is a genome-native count rebuild or an explicit permanent alias/index layer.

## Runtime Artifact Snapshot

Observed on disk:

```text
D:\AnchorMaps\observed_maps                 2,657 *.observed.json
D:\AnchorMaps\symbolic_maps                 2,657 *.awsm
D:\AnchorMaps\symbolic_maps                 2,657 *.locators.awsl
D:\AnchorMaps\symbolic_maps                 2,657 *.nulls.awsn
D:\AnchorMaps\symbolic_maps                 2,657 *.visuals.awsv
D:\AnchorWorks_Clean_Runtime\State\source_local_symbol_counts  2,657 *.symbol_counts.json
D:\AnchorWorks_Clean_Runtime\State\flat_documents\local_overlays 2,657 *.local_overlay.awlo.json
D:\AnchorWorks_Clean_Runtime\State\symbol_streams\source_local_symbol_counts.awss 872,818,608 bytes
D:\AnchorWorks_Clean_Runtime\State\symbol_counts_binary\cells 1,728,048 *.cell
D:\AnchorWorks_Clean_Runtime\Phrase_Lexicon 0 phrase rows
```

## Connection Questions

### Does runtime ClearSpeak read the live canonical lexicon directly?

Yes. `ClearSpeakService._load_awsc_count_index()` calls `store._canonical_symbol_by_anchor()` to build `symbol_by_anchor` and `anchor_by_symbol`.

Files:

```text
src/AnchorWorks/clearspeak.py
src/AnchorWorks/store.py
```

### Where does word -> symbol resolution happen?

Primary V1 lookup is in `LexiconStore` over `Canonical/canonical_*.json` and `Structural/structural.json`. The live canonical row shape is now minimal:

```json
{"word": "example", "symbol": "0x1000000000"}
```

Genome allocation/checkpoint uses `SymbolGenomePool` under:

```text
State/symbol_genome_pool
```

### Where does symbol -> AWSC cell lookup happen?

ClearSpeak normalizes a symbol to 5-byte hex and computes:

```text
State/symbol_counts_binary/cells/<first-byte>/<10-hex>.cell
```

Reader:

```text
src/AnchorWorks/symbol_count_cells.py
```

Runtime caller:

```text
src/AnchorWorks/clearspeak.py
```

### Does any path still reference Spare_Slots?

Yes. `store.py` still initializes `self.spare_dir = root / "Spare_Slots"` and has legacy assignment helpers that read spare pool files. This is a legacy surface and should not be charted as live symbol authority.

Known mismatch: the directory name still exists in the runtime root even though genome is the intended allocator authority.

### Does any active runtime path expect `tone_signature`, `font_symbol`, or `frequency`?

Legacy assignment/import helpers in `store.py` still mention these fields. The live genome lexicon verifier expects only `word` and `symbol`. These legacy fields should be charted as legacy compatibility residue, not live authority.

### Does AWSS stream carry old symbols, genome symbols, or mixed?

The current AWSS stream was produced from source-local symbol-count artifacts generated before the live lexicon swap. Runtime evidence indicates the AWSC cells require the old-symbol bridge. Treat current AWSS/AWSC as legacy-symbol count memory until rebuilt or explicitly remapped.

### Can a new unknown anchor receive a genome symbol now?

Yes through the symbol genome pool API:

```text
GET  /api/symbol-genome/status
POST /api/symbol-genome/allocate
POST /api/symbol-genome/checkpoint
```

This allocates identity but does not by itself prove full Canonical promotion policy.

### Where is the genome cursor/checkpoint read and written?

`SymbolGenomePool` uses:

```text
State/symbol_genome_pool/manifest.json
```

The live lexicon genome promotion reserves the pool after existing live rows.

### Where are phrase entries loaded from?

`PhraseLexiconStore` loads:

```text
Phrase_Lexicon/*.json
```

Current live phrase row count: `0`.

### Is phrase authority empty by design or disconnected accidentally?

Empty by current state, but not disconnected. The storage class and renderer hook exist. `ClearSpeakService` asks `store.phrases.match_phrase(represented)` and passes `phrase_field` into `infer_attention_frame()`.

### Which V2 contracts correspond to current V1 runtime lanes?

V2 is an external contract destination at:

```text
D:\AnchorWorks_V2
```

It declares contracts, route docs, lexicon placement, native command specs, phrase authority, invoked UI planning, and runtime module migration decisions. It is not active V1 runtime.

### Which native command specs are declared but not executable yet?

V1 native symbol counts are executable through the Python wrapper:

```text
merge-stream
verify
inspect
score
```

V2 native command specs are contract declarations, not V1 execution paths.

## Lane Trace

### 1. Source Intake Path

Status: active

Entry point:

```text
src/AnchorWorks/app.py
src/AnchorWorks/cli.py
LexiconStore.build_observed_map()
```

Files/modules:

```text
src/AnchorWorks/document_prep.py
src/AnchorWorks/intake.py
src/AnchorWorks/store.py
src/AnchorWorks/symbolic_map_binary.py
```

Contracts/docs:

```text
ANCHORWORKS_SYMBOLIC_BINARY_BUILD_CURRENT.md
```

Data inputs:

```text
source files
Canonical/*
Structural/structural.json
```

Data outputs:

```text
D:\AnchorMaps\observed_maps\*.observed.json
D:\AnchorMaps\symbolic_maps\*.awsm
D:\AnchorMaps\symbolic_maps\*.locators.awsl
D:\AnchorMaps\symbolic_maps\*.nulls.awsn
D:\AnchorMaps\symbolic_maps\*.visuals.awsv
```

Symbol identity used: mixed

Connected to:

```text
AWSM sidecars
source-local symbol counts
local overlays
AWSS/AWSC build
```

Not connected to:

```text
V2 runtime execution
production AWSG source_graphs
```

Known mismatch:

```text
Observed JSON still exists as debug/audit.
AWSM is the hot path for source-local symbol-count build when present.
```

Verifier/test coverage:

```text
test_mapping.py
test_symbolic_map_binary.py
test_cli.py
test_document_film.py
```

Command used to verify:

```text
python -m unittest discover -s "..\test\test data\tests" -q
```

Chart label: Source Intake -> AWSM/AWSL/AWSN/AWSV

Chart status color: active green

Notes: External map root is `D:\AnchorMaps`.

### 2. Lexicon Lookup Path

Status: active

Entry point:

```text
LexiconStore.search()
LexiconStore.lookup()
LexiconStore._canonical_symbol_by_anchor()
ClearSpeakService._recognize()
```

Files/modules:

```text
src/AnchorWorks/store.py
src/AnchorWorks/clearspeak.py
```

Contracts/docs:

```text
SYMBOL_GENOME_PROTOCOL_CONTRACT.md
SYMBOL_SYSTEM_NEXT_HANDOFF.md
```

Data inputs:

```text
Canonical/canonical_*.json
Structural/structural.json
```

Data outputs:

```text
recognized anchors
word -> genome symbol table
```

Symbol identity used: genome

Connected to:

```text
ClearSpeak recognition
intake mapping
phrase anchor symbol lookup
UI lexicon endpoints
```

Not connected to:

```text
direct genome-native AWSC cells
```

Known mismatch:

```text
Live lexicon is genome-style; existing AWSC count cells are older symbols.
```

Verifier/test coverage:

```text
test_lexicon_genome_rebuild.py
test_symbol_genome_pool.py
test_settings_truth.py
```

Chart label: Canonical Lexicon Recognition

Chart status color: active green with bridge warning

### 3. Genome Symbol Allocation Path

Status: active

Entry point:

```text
/api/symbol-genome/status
/api/symbol-genome/allocate
/api/symbol-genome/checkpoint
LexiconStore.allocate_symbol_genome_identity()
```

Files/modules:

```text
src/AnchorWorks/symbol_genome_pool.py
src/AnchorWorks/symbol_genome.py
src/AnchorWorks/symbol_genome_native.py
src/AnchorWorks/lexicon_genome_rebuild.py
```

Contracts/docs:

```text
SYMBOL_GENOME_PROTOCOL_CONTRACT.md
```

Data inputs:

```text
label
authority
State/symbol_genome_pool/manifest.json
```

Data outputs:

```text
5-byte genome symbol
checkpointed allocator cursor
```

Symbol identity used: genome

Connected to:

```text
live lexicon rebuild
API status/allocate/checkpoint
phrase symbol generation path
```

Not connected to:

```text
automatic unknown-anchor Canonical promotion
genome-native AWSC rebuild
```

Known mismatch:

```text
Legacy spare helper methods still exist in store.py and should be isolated as legacy.
```

Verifier/test coverage:

```text
test_symbol_genome.py
test_symbol_genome_pool.py
test_lexicon_genome_rebuild.py
```

Chart label: Genome Allocator

Chart status color: active green

### 4. Canonical Authority Path

Status: active

Entry point:

```text
Canonical/canonical_*.json
Structural/structural.json
LexiconStore._canonical_symbol_by_anchor()
```

Files/modules:

```text
src/AnchorWorks/store.py
src/AnchorWorks/lexicon_genome_rebuild.py
```

Data inputs:

```text
live Canonical rows
live Structural rows
```

Data outputs:

```text
word -> symbol authority
anchor recognition
symbol table for AWSM and ClearSpeak
```

Symbol identity used: genome

Connected to:

```text
intake
ClearSpeak recognition
phrase anchor validation
UI lexicon browser/search
```

Not connected to:

```text
old AWSC cell identity except through mapping bridge
```

Known mismatch:

```text
Canonical is genome; historical count cells are legacy.
```

Verifier/test coverage:

```text
test_lexicon_genome_rebuild.py
test_symbol_genome_pool.py
```

Chart label: Canonical Authority

Chart status color: active green

### 5. User/Workspace Lexicon Path

Status: staged

Entry point:

```text
State/user/*
State/user/user_counts
State/user/chat_counts
```

Files/modules:

```text
src/AnchorWorks/store.py
src/AnchorWorks/chat_memory_system.py
```

Data inputs:

```text
chat/user state
```

Data outputs:

```text
user/chat count sidecars
```

Symbol identity used: mixed/unclear

Connected to:

```text
chat memory surfaces
```

Not connected to:

```text
clear genome authority policy
V2 user identity contracts
```

Known mismatch:

```text
User/workspace lexicon authority is not yet as clean as Canonical.
```

Verifier/test coverage:

```text
partial chat/store tests only
```

Chart label: User Workspace Lexicon

Chart status color: staged yellow

### 6. Phrase Authority Path

Status: staged/empty

Entry point:

```text
PhraseLexiconStore
Phrase_Lexicon/*.json
ClearSpeakService._assemble_answer_terms()
```

Files/modules:

```text
src/AnchorWorks/phrase_lexicon.py
src/AnchorWorks/phrase_candidates.py
src/AnchorWorks/clearspeak.py
src/AnchorWorks/clearspeak_attention.py
```

Contracts/docs:

```text
PHRASES_AND_RENDERING_TODO.md
```

Data inputs:

```text
approved phrase rows
symbolized flat docs or observed map/AWSM review source
```

Data outputs:

```text
phrase field
phrase candidate review files
```

Symbol identity used: genome for phrase symbols, anchor symbols for phrase members

Connected to:

```text
ClearSpeak phrase field hook
phrase candidate extraction
```

Not connected to:

```text
live phrase UI browser toggle
non-empty phrase authority
AWSC phrase counting
```

Known mismatch:

```text
Phrase authority exists but currently has 0 live phrase rows.
```

Verifier/test coverage:

```text
test_phrase_candidates.py
ClearSpeak phrase tests in current suite
```

Chart label: Phrase Authority

Chart status color: staged yellow

### 7. AWSS Symbol Stream Path

Status: active

Entry point:

```text
LexiconStore.build_binary_symbol_counts_from_source_local()
write_awss_from_symbol_count_artifacts()
```

Files/modules:

```text
src/AnchorWorks/symbol_count_native.py
src/AnchorWorks/symbol_relation_counts.py
```

Data inputs:

```text
State/source_local_symbol_counts/*.symbol_counts.json
```

Data outputs:

```text
State/symbol_streams/source_local_symbol_counts.awss
```

Symbol identity used: legacy/mixed for current artifact set

Connected to:

```text
C++ merge-stream
AWSC cell build
```

Not connected to:

```text
genome-native rebuilt counts
```

Known mismatch:

```text
Current AWSS reflects the pre-genome count identity and therefore needs bridge or rebuild.
```

Verifier/test coverage:

```text
test_native_symbol_counts.py
test_symbol_relation_counts.py
```

Chart label: AWSS Relation Stream

Chart status color: active green with identity warning

### 8. AWSC Binary Count-Cell Path

Status: active

Entry point:

```text
merge_symbol_stream()
verify_binary_counts()
read_symbol_cell()
ClearSpeakService._load_awsc_count_index()
```

Files/modules:

```text
src/AnchorWorks/symbol_count_native.py
src/AnchorWorks/symbol_count_cells.py
src/AnchorWorks/clearspeak.py
```

Contracts/docs:

```text
ANCHORWORKS_SYMBOLIC_BINARY_BUILD_CURRENT.md
```

Data inputs:

```text
AWSS stream
```

Data outputs:

```text
State/symbol_counts_binary/cells/**/*.cell
State/symbol_counts_binary/metadata.json
```

Symbol identity used: legacy/mixed current cells

Connected to:

```text
ClearSpeak counts
C++ verify/inspect/score commands
```

Not connected to:

```text
packed shard/index storage
genome-native count memory
```

Known mismatch:

```text
1,728,048 tiny cells exist; shard storage is a future tightening item.
```

Verifier/test coverage:

```text
test_symbol_count_cells.py
test_native_symbol_counts.py
```

Chart label: AWSC Count Cells

Chart status color: active green with storage-warning stripe

### 9. Old-Symbol -> Genome-Symbol Mismatch Path

Status: active bridge

Entry point:

```text
ClearSpeakService._load_genome_legacy_count_bridge()
```

Files/modules:

```text
src/AnchorWorks/clearspeak.py
Lexicon_Genome_Rebuild/mappings/old_symbol_to_genome_symbol.jsonl
```

Data inputs:

```text
old_symbol_to_genome_symbol.jsonl
Canonical/canonical_*.json
AWSC legacy count cells
```

Data outputs:

```text
anchor-decoded count index
```

Symbol identity used: mixed

Connected to:

```text
ClearSpeak runtime answer walk
```

Not connected to:

```text
intake-time count rebuild
permanent count identity migration
```

Known mismatch:

```text
This bridge is why genome lexicon can query old AWSC counts. It is useful but should be charted as compatibility, not final memory architecture.
```

Verifier/test coverage:

```text
current full suite
ClearSpeak runtime probes from prior checkpoint
```

Chart label: Genome/Legacy Count Bridge

Chart status color: active orange

### 10. ClearSpeak Renderer Path

Status: active

Entry point:

```text
/api/clearspeak/query
ClearSpeakService.query()
```

Files/modules:

```text
src/AnchorWorks/app.py
src/AnchorWorks/clearspeak.py
src/AnchorWorks/clearspeak_attention.py
```

Data inputs:

```text
user query
Canonical lexicon
AWSC count index
phrase field if matched
```

Data outputs:

```text
ClearSpeakResult
answer_assembly
trace/evidence metadata
```

Symbol identity used: genome recognition + legacy bridge to counts

Connected to:

```text
API chat/query UI
AWSC counts
phrase field hook
```

Not connected to:

```text
source-local overlays in final renderer path
document-map evidence when counts mode is selected
```

Known mismatch:

```text
ClearSpeak counts mode is not a document-citation mode.
```

Verifier/test coverage:

```text
ClearSpeak tests in current suite
```

Chart label: ClearSpeak Symbol Walk

Chart status color: active green

### 11. Active Cloud Q/R/A/F Path

Status: active

Entry point:

```text
build_active_cloud_frame()
ClearSpeakService._assemble_answer_terms()
```

Files/modules:

```text
src/AnchorWorks/clearspeak_attention.py
src/AnchorWorks/clearspeak.py
```

Data inputs:

```text
Q = question anchors
R = rear context
A = answer so far
F = forward context
count index
```

Data outputs:

```text
active cloud candidates
score parts
rejected candidates
answer trace
```

Symbol identity used: decoded anchor names at renderer edge

Connected to:

```text
ClearSpeak answer assembly
top-K lookahead
phrase field pressure
```

Not connected to:

```text
GPU matrix backend
V2 renderer contracts
```

Known mismatch:

```text
Runtime scoring happens in Python over decoded anchors, not native/GPU symbols.
```

Verifier/test coverage:

```text
test_anchor_field.py
ClearSpeak-related tests
```

Chart label: Q/R/A/F Active Cloud

Chart status color: active green

### 12. Top-K / Lookahead Path

Status: active

Entry point:

```text
choose_candidate_with_lookahead()
choose_topk_with_lookahead()
```

Files/modules:

```text
src/AnchorWorks/clearspeak_attention.py
src/AnchorWorks/anchor_field.py
```

Data inputs:

```text
candidate top-K
future count cloud
blocked/glue/null gates
```

Data outputs:

```text
chosen candidate
future cloud
pattern_health
lookahead_score
```

Symbol identity used: decoded anchor names at renderer edge

Connected to:

```text
ClearSpeak answer assembly
cloud anomaly avoidance
```

Not connected to:

```text
native/GPU scoring backend
```

Known mismatch:

```text
Algorithm is connected, but still Python-side and not yet symbol-native end to end.
```

Verifier/test coverage:

```text
test_anchor_field.py
ClearSpeak tests
```

Chart label: Top-K Lookahead

Chart status color: active green

### 13. Evidence/Map/Document Path

Status: partially active

Entry point:

```text
/api/clearspeak/query evidence_mode=documents/maps/auto
ChatMemorySystem.document_answer
DocumentAnswerService.answer()
```

Files/modules:

```text
src/AnchorWorks/document_answer.py
src/AnchorWorks/chat_memory_system.py
src/AnchorWorks/local_meta_overlay.py
src/AnchorWorks/observed_map_graph_viewer.py
```

Data inputs:

```text
flat documents
source-local occurrences
local overlays
observed maps/AWSM for audit
```

Data outputs:

```text
document answers
coordinates
locator/evidence metadata
```

Symbol identity used: mixed, depending on source

Connected to:

```text
document mode fallback/no-support responses
AWSG proof viewer
local overlays
```

Not connected to:

```text
full AWSG production graph routing
ClearSpeak counts-only answer assembly
```

Known mismatch:

```text
AWSG proof exists in test root and viewer can read proof graphs; production source_graphs is empty.
```

Verifier/test coverage:

```text
test_observed_map_graph.py
test_document_film.py
test_visual_manifest.py
test_positional_resonance.py
```

Chart label: Evidence/Locator Layer

Chart status color: partial yellow

### 14. Native Command/Spec Path

Status: active in V1, declared in V2

Entry point:

```text
symbol_count_native.py
symbol_genome_native.py
```

Files/modules:

```text
src/AnchorWorks/native/symbol_counts
src/AnchorWorks/native/symbol_genome
```

Data inputs:

```text
AWSS/AWSY streams
symbol genome allocation requests
```

Data outputs:

```text
AWSC cells
verify/inspect/score JSON
genome allocation batch output
```

Symbol identity used: fixed 5-byte hex

Connected to:

```text
V1 build wrappers
unit tests
```

Not connected to:

```text
V2 runtime execution
GPU scoring
packed shard storage
```

Known mismatch:

```text
V2 native command specs are plans/contracts. V1 native commands are executable wrappers.
```

Verifier/test coverage:

```text
test_native_symbol_counts.py
test_symbol_genome_pool.py
```

Chart label: Native C++ Spine

Chart status color: active green for V1, staged yellow for V2

### 15. V2 Contract Destination Path

Status: staged external

Entry point:

```text
D:\AnchorWorks_V2
npm verify
```

Files/modules:

```text
D:\AnchorWorks_V2\contracts
D:\AnchorWorks_V2\src
D:\AnchorWorks_V2\docs
D:\AnchorWorks_V2\ALL TESTS
```

Data inputs:

```text
contract fixtures
copied lexicon authority
native command specs
```

Data outputs:

```text
contract verification reports
```

Symbol identity used: genome

Connected to:

```text
V2 contract verification
future migration docs
```

Not connected to:

```text
V1 runtime process
V1 UI
V1 ClearSpeak
```

Known mismatch:

```text
V2 should not appear as active runtime in the V1 chart.
```

Verifier/test coverage:

```text
D:\AnchorWorks_V2\package.json verify scripts
```

Chart label: V2 Boundary Brain

Chart status color: staged blue/yellow

### 16. Invoked UI Planning Path

Status: planned/staged

Entry point:

```text
D:\AnchorWorks_V2\docs\INVOKED_UI_RECIPE_PLAN.md
```

Files/modules:

```text
V2 docs only
V1 app UI endpoints for current static UI
```

Data inputs:

```text
future recipe manifests
assistant/workflow suggested UI recipes
```

Data outputs:

```text
future static recipe invocations
```

Symbol identity used: none yet

Connected to:

```text
planning docs
```

Not connected to:

```text
V1 frontend runtime
active chat buttons/cards
```

Known mismatch:

```text
Do not chart invoked UI as active. It is a planned V2 surface idea.
```

Verifier/test coverage:

```text
V2 invoked UI plan verifier
```

Chart label: Invoked UI Recipes

Chart status color: planned gray/blue

### 17. Legacy Exclusion Path

Status: legacy/blocked

Entry point:

```text
Spare_Slots references
legacy assignment helpers
legacy JSON lifetime counts
```

Files/modules:

```text
src/AnchorWorks/store.py
```

Data inputs:

```text
Spare_Slots/*
legacy count files if present
```

Data outputs:

```text
legacy rows only
```

Symbol identity used: legacy

Connected to:

```text
some old helper methods in store.py
```

Not connected to:

```text
genome authority as intended
final chart active identity path
```

Known mismatch:

```text
The code still references Spare_Slots; chart should mark it as legacy/excluded until removed or isolated.
```

Verifier/test coverage:

```text
lexicon genome tests guard the new row shape
```

Chart label: Legacy Spare/Old Lexicon

Chart status color: red/legacy

### 18. Test/Verification Path

Status: active

Entry point:

```text
test\test data\tests
```

Files/modules:

```text
test\test data\tests
test\test data\experiments
test\test data\harnesses
test\test data\reports
```

Data inputs:

```text
fixtures and contained proof artifacts
```

Data outputs:

```text
unittest results
proof reports
```

Symbol identity used: mixed by test target

Connected to:

```text
V1 modules
proof experiments
binary contracts
visual contracts
settings truth
```

Not connected to:

```text
production runtime writes except temp directories
```

Known mismatch:

```text
Historical superpowers plans still mention old test paths, but live test command uses the new contained root.
```

Verifier/test coverage:

```text
194 tests
```

Command used to verify:

```text
python -m unittest discover -s "..\test\test data\tests" -q
```

Chart label: Verification Harness

Chart status color: active green

## Chart Guardrails

Use these labels:

```text
active      traced path connected and tested
partial     connected in one lane but not all claimed lanes
staged      code/contract exists but no live data or no production runtime path
planned     docs/spec only
legacy      old code/data present but not intended authority
blocked     cannot be active until a named gap is resolved
```

Use these mandatory chart warnings:

```text
GENOME <-> LEGACY AWSC COUNT IDENTITY BRIDGE
AWSG proof exists, production source_graphs empty
Phrase authority path exists, live phrase rows = 0
Spare_Slots references remain legacy residue
AWSC fanout is active but storage shape needs packed shard/index future
V2 is not V1 runtime
```

