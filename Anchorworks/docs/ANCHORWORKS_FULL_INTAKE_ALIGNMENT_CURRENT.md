# AnchorWorks Full Intake Alignment - Current Truth

Updated: 2026-05-16

This document aligns the intake path around the code that is actually on the current AnchorWorks V1 path. It separates what should remain Python orchestration from what belongs in the C++ spine, and it records the symbolizing, ambiguity, map, count, and TrueVision rules needed before the next clean ingest.

## Map Archive Receipt

Current map roots:

```text
D:\AnchorMaps\observed_maps
D:\AnchorMaps\symbolic_maps
```

Current measured footprint before archive:

```text
observed_maps:  2,672 files, 40,224,741,771 bytes
symbolic_maps: 10,688 files,  5,678,477,907 bytes
```

Archive job started:

```text
Destination: D:\AnchorMaps_archive_20260516_AnchorMaps.zip
Mode: detached Compress-Archive, Fastest compression
Contents: observed_maps + symbolic_maps
```

Do not delete `D:\AnchorMaps` until the archive exists, has nonzero size, and can list both roots.

## Current Critical Findings

The existing AWSM maps are real and useful, but they are mixed identity:

```text
AWSM files read OK: 2,672 / 2,672
canonical authority rows: 12,283
canonical genome-style rows: 10,938
canonical non-genome rows: 1,345
source-local rows: 57,498
```

Therefore the next count build must not blindly merge AWSM into AWSC. It must remap canonical symbols to the live genome lexicon during the merge.

Current native count CLI supports:

```text
AWSS -> AWSC
AWSY -> AWSC
verify
inspect
score
```

Current native count CLI does not yet support:

```text
AWSM directory -> genome-corrected AWSC
```

That is the next required C++ count function. No Python bulk relation conversion should be used for the final count build.

## Core Intake Law

```text
Source bytes enter.
TrueVision preserves visual state first where visual evidence exists.
Prepared text is derived after visual proofing.
Anchors are recognized.
Anchors resolve to symbols.
Maps preserve local topology and locators.
C++ builds binary count memory.
Renderer reads symbols and only renders human text at the edge.
```

Short form:

```text
Pixels prove sight.
Lexicon recognizes anchors.
Symbols compute.
C++ counts.
AWSC remembers.
Human text is display only.
```

## Stage 1 - Source Discovery

Function:

```text
Find source files and classify by extension.
```

Current code:

```text
AnchorWorks.document_prep.prepare_file()
AnchorWorks.document_prep.prepare_bytes()
```

Python should stay responsible for:

```text
file enumeration
extension/type routing
small metadata objects
job manifests
error reports
detached process control
```

Why it matters:

```text
Python is good at orchestration and file-type routing.
The expensive count work must not live here.
```

## Stage 2 - TrueVision First

Function:

```text
Preserve visual evidence before text normalization or semantic interpretation.
```

Current code:

```text
visual_manifest.manifest_from_image_bytes()
visual_manifest.source_record_from_image_bytes()
document_film.extract_pdf_document_film_from_bytes()
document_film.build_document_film_from_images()
visual_region_map.create_empty_region_map()
visual_recognition_layer.create_empty_recognition_layer()
```

Current visual authority:

```text
authority: source_local_visual_evidence
approval_status: preview_only
writes_allowed: maps=false counts=false lifetime=false lexicon=false
recognition_status: not_run
```

TrueVision should stay Python for now for:

```text
image byte probing
page-frame metadata
visual manifest creation
document film packets
AWSV sidecar rows
empty region/recognition layers
```

TrueVision should later use native/GPU for:

```text
high-speed frame extraction
black-pixel/glyph segmentation
region generation
visual anomaly scanning
recognition candidate generation
```

Current gap:

```text
document_prep._prepare_pdf() extracts PDF text before attempting document_film extraction.
The policy is now stricter: NEVER NORMALIZE PRIOR TO VISION.
The corrected path must run visual preservation first, then derive text.
```

Required final PDF path:

```text
PDF bytes
-> TrueVision document film/page visual refs
-> page geometry + frame identity + AWSV refs
-> derived text extraction for text lane
-> anchorization
```

Why it matters:

```text
Visual state is source evidence.
OCR/recognition/text extraction are derived layers, not visual truth.
```

## Stage 3 - Text Preparation

Function:

```text
Convert source file content into prepared text only after source evidence is preserved.
```

Current code:

```text
document_prep.prepare_bytes()
_prepare_text / _prepare_xml / _prepare_html / _prepare_pdf / _prepare_docx
_prepare_spreadsheet / _prepare_image / _prepare_epub / etc.
```

Python should stay responsible for:

```text
format adapters
safe text extraction
metadata extraction
source hash and source name
warnings
preview-only visual text stubs
```

C++ should not handle this yet because:

```text
format parsing is messy and library-dependent
it is not the bottleneck compared to count building
```

Rule:

```text
Prepared text is an intake/display derivative, not authority over visual truth.
```

## Stage 4 - Anchor Extraction

Function:

```text
Turn prepared text into anchor rows with surfaces, positions, and count eligibility.
```

Current code:

```text
intake.extract_anchor_rows()
intake.extract_anchors()
intake.compose_anchor_stream()
intake.build_anchor_map()
```

Current symbolizing/anchor rules:

```text
Whitespace separates runs.
Digits become single-character anchors.
Punctuation becomes single-character anchors, except joined apostrophe handling.
Emoji sequences become __EMOJI__.
Acronym alpha runs are split into one letter per anchor.
Long no-space alpha+digit strings become string_literal rows.
string_literal rows are not count eligible.
Curly apostrophes normalize to straight apostrophe.
Anchor identity is lowercase except __EMOJI__.
```

Acronym rule:

```text
Each letter/digit is represented solely, then the stream is smooshed together by position.
Example: NASA -> n a s a
```

Unknown string rule:

```text
Unknown long mixed strings should decompose into character anchors or become source-local string_literal,
not global word authority.
```

Python should stay responsible for:

```text
anchor-row extraction
surface offsets
paragraph splitting
initial ambiguity detection
review queue creation
small source-local metadata
```

C++ should later own:

```text
high-volume symbol stream construction
window counting
direct AWSM/AWSY/AWSC relation aggregation
```

Why it matters:

```text
Anchor rows preserve human/source positions.
Symbols are the computational form.
```

## Stage 5 - Lexicon Recognition and Ambiguity

Function:

```text
Recognize anchors against live authority before counting.
```

Current code:

```text
LexiconStore._canonical_symbol_by_anchor()
LexiconStore._all_known_anchors()
LexiconStore._assign_surface_anchor()
SymbolGenomePool.allocate()
```

Current live authority target:

```text
word -> genome symbol
```

Required live row shape:

```json
{
  "word": "inertia",
  "symbol": "0x1000..."
}
```

Ambiguity rules:

```text
Canonical match: use canonical genome symbol.
Structural match: use structural lane/symbol.
Approved companion: use companion/source-specific lane.
Unknown normal anchor: register missing anchor; source-local temp symbol until approved.
Unknown long mixed string: decompose or string_literal; do not poison global lexicon.
NULL/exclusion: exact coordinate index only; never relation memory.
Visual-only evidence: source-local visual evidence only; no count/lexicon writes.
Phrase authority: separate from word lexicon; phrases recognize fields, counts remain anchor-symbol memory.
```

Important:

```text
status is lifecycle only.
tone_signature must not carry symbol identity.
hex/symbol/binary identity must agree wherever those fields exist.
```

Python should stay responsible for:

```text
lexicon lookup
review queues
manual approval paths
genome allocator orchestration
small JSON lexicon authority
```

C++ should not mutate lexicon:

```text
The C++ spine counts symbols. It does not decide language authority.
```

## Stage 6 - Local Map Build

Function:

```text
Build source-local topology: paragraphs, occurrences, 6-1-6 windows, locators, and sidecars.
```

Current code:

```text
intake.build_anchor_map()
LexiconStore.build_observed_map()
symbolic_map_binary.write_symbolic_map_binary()
write_symbolic_map_locator_sidecar()
write_symbolic_map_null_sidecar()
write_symbolic_map_visual_sidecar()
```

Current outputs:

```text
Observed JSON map: debug/audit/export view
AWSM: symbolic relation map
AWSL: locator sidecar
AWSN: NULL sidecar
AWSV: visual reference sidecar
```

Current 6-1-6 rule:

```text
For each count-eligible anchor position:
look left 6 and right 6 within the same paragraph block.
Record signed offset.
Do not cross paragraph blocks.
Do not count NULL/string_literal/count-blocked anchors.
Glue words are retained in placement/count surfaces.
Glue classification must affect rendering, not erase placement counts.
```

Python can stay responsible for map writing for now:

```text
maps are audit/local-topology artifacts
sidecars preserve locators and evidence
```

But for the next clean count build:

```text
Do not regenerate observed JSON maps.
Use existing AWSM/AWSL/AWSN/AWSV as source artifacts.
```

Why it matters:

```text
Maps preserve local structure.
Counts preserve accumulated pressure.
Flat docs preserve source truth.
Renderer should not load giant observed JSON maps.
```

## Stage 7 - Count Build

Function:

```text
Merge source-local symbolic relations into AWSC binary count cells.
```

Current native code:

```text
native/symbol_counts
anchorworks-symbol-counts merge-stream
anchorworks-symbol-counts merge-symbol-stream
anchorworks-symbol-counts verify
anchorworks-symbol-counts inspect
anchorworks-symbol-counts score
```

C++ must own:

```text
bulk relation ingestion
symbol correction/remap during merge
relation aggregation
AWSC cell writing
CRC verification
score/top-k hot loops
future packed shard/index storage
```

Python may orchestrate only:

```text
start detached job
record job id
write status manifest
call C++ executable
read verify result
```

Required next C++ command:

```text
anchorworks-symbol-counts merge-awsm-dir
  --input D:\AnchorMaps\symbolic_maps
  --canonical D:\AnchorWorks_Clean_Runtime\Canonical
  --structural D:\AnchorWorks_Clean_Runtime\Structural
  --output D:\AnchorWorks_Clean_Runtime\State\symbol_counts_binary
  --generation YYYYMMDD
```

Required behavior:

```text
Read AWSM files directly.
Read live word->genome authority.
Correct canonical map symbols to genome symbols in memory.
Preserve source-local symbols as source-local lane unless promoted.
Skip NULL from relation memory.
Merge directly into AWSC cells.
Write no AWSS, no source-local JSON, no observed JSON, no lifetime JSON.
Verify output root.
```

Why it matters:

```text
The current Python/AWSS bridge is useful for proof, not final bulk count fill.
The full count build must be binary-in/binary-out.
```

## Stage 8 - Flat Documents and Overlays

Function:

```text
Support grounded answer gathering without loading giant observed maps.
```

Current direction:

```text
flat document text
symbolized flat doc
local meta-count overlay
locator refs
global AWSC counts
```

Rule:

```text
Runtime chat must not load giant observed map JSON.
Maps explain.
Overlays serve.
Flat docs preserve.
AWSC supplies memory pressure.
```

Python should own:

```text
small overlay JSON for development
flat doc indexing
locator lookup
debug/audit exports
```

C++ should later own:

```text
binary overlay lookup
packed local count indexes
fast top-k cloud expansion
```

## Stage 9 - Rendering Intake Dependency

Rendering depends on intake correctness:

```text
user input -> lexicon recognition -> count cloud -> flat/evidence gather when needed -> count top-k assembly -> inference admission -> renderer
```

Counts are not speech:

```text
Search finds.
Counts weigh.
Inference admits.
Renderer speaks.
```

Glue words:

```text
Glue must remain in placement counts.
Glue may be down-ranked as content during rendering.
Glue still guides relation, direction, polarity, and frame shape.
```

## Final Clean Intake Procedure

Use this sequence for the next clean run:

```text
1. Archive existing maps.
2. Verify archive can list observed_maps and symbolic_maps.
3. Clear bad State\State staging output.
4. Keep or clear D:\AnchorMaps only after archive verification.
5. Start fresh source intake with TrueVision-first policy.
6. Build AWSM/AWSL/AWSN/AWSV.
7. Do not write giant runtime JSON counts.
8. Run native C++ AWSM-dir merge with live genome correction.
9. Verify AWSC root.
10. Point ClearSpeak/counts mode only at verified genome-native AWSC.
11. Run count questions against known source terms.
```

## Files On Current Path

```text
Anchorworks/src/AnchorWorks/document_prep.py
Anchorworks/src/AnchorWorks/document_film.py
Anchorworks/src/AnchorWorks/visual_manifest.py
Anchorworks/src/AnchorWorks/visual_region_map.py
Anchorworks/src/AnchorWorks/visual_recognition_layer.py
Anchorworks/src/AnchorWorks/intake.py
Anchorworks/src/AnchorWorks/store.py
Anchorworks/src/AnchorWorks/symbolic_map_binary.py
Anchorworks/src/AnchorWorks/symbol_count_native.py
Anchorworks/src/AnchorWorks/native/symbol_counts/
Anchorworks/src/AnchorWorks/clearspeak.py
Anchorworks/src/AnchorWorks/clearspeak_attention.py
Anchorworks/src/AnchorWorks/inference/
```

## Current Gaps To Close Before Fresh Full Ingest

```text
1. Native C++ AWSM directory merge does not exist yet.
2. Existing AWSM maps contain mixed canonical symbol identity and require genome correction during merge.
3. PDF path must be corrected to preserve TrueVision/document-film before derived text normalization.
4. Bad State\State run output should be deleted after archive/report review.
5. Active AWSC root is not full OpenStax; it is currently a small verified root.
6. Packed shard/index storage is still future work; current AWSC writes many cell files.
```

## Non-Negotiable Laws

```text
Never normalize prior to vision.
Vision is deterministic source evidence.
Recognition is derived.
Strings are intake/display.
Symbols are computation.
Genome symbols are live identity.
Maps are local topology/audit.
AWSC is count memory.
C++ performs bulk counting.
Python orchestrates and records receipts.
No legacy count bridge.
No JSON lifetime monolith in the hot path.
No giant observed map JSON in chat runtime.
No source-local temp symbol becomes global truth without lexicon approval.
No candidate speaks until admitted.
```
