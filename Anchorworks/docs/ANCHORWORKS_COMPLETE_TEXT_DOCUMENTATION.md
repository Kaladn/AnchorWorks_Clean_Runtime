# AnchorWorks Complete Text Documentation

Status: source document for AnchorWorks self-knowledge.

Purpose: this file is written as a full text source that AnchorWorks can ingest, map, count, search, cite, and use as a procedural reference. It describes what AnchorWorks is, how it works, how to operate it, what must never happen, and how the major lanes connect.

Core law:

```text
Lexicon recognizes.
Symbols compute.
Maps preserve local structure.
Counts remember observed pressure.
Sources prove facts.
Frames aim the answer.
Renderer speaks the permitted path.
```

## 1. System Identity

AnchorWorks is a deterministic symbolic evidence and language system.

It is not built as a normal chatbot. It does not rely on hidden neural weights as its truth layer. It turns source material into anchors, resolves anchors to fixed-width symbols, stores observed symbolic relationships, and uses counts, source evidence, local overlays, and frame guidance to assemble answers.

The system goal is:

```text
source intake
-> anchor recognition
-> symbol authority
-> source-local evidence
-> local overlays
-> global count memory
-> active context clouds
-> top-K answer walk
-> source-labeled rendering
```

AnchorWorks should become useful because it can show how an answer was shaped:

```text
what was recognized
which symbols were used
which counts supported candidate movement
which source passages supplied facts
which evidence lane was used
which candidates were rejected
why the final answer was allowed
```

AnchorWorks should not hide the boundary between observed evidence and generated speech.

## 2. Primary Terms

### Anchor

An anchor is a recognized language unit, usually a word or approved single unit of meaning.

Examples:

```text
force
mass
acceleration
law
motion
source
answer
```

Anchors are human-readable at the display edge. Internally they should resolve to symbols as early as possible.

### Symbol

A symbol is the fixed-width machine identity for an anchor or approved phrase.

Current direction:

```text
symbol = fixed identity
text = intake and display
```

Hard law:

```text
Everyone speaks symbols internally.
Human rendered text appears onscreen.
```

### Lexicon

The lexicon is the first recognition base. Every inquiry must pass through lexicon recognition before document search, count search, or rendering.

The live minimal word row shape is:

```json
{
  "word": "force",
  "symbol": "0x1000000000"
}
```

The lexicon is authority for known anchor identity. It is not the memory of how often an anchor appears. Counts are memory.

### Phrase Authority

Phrase authority is separate from word authority. Phrases are not counted as the main memory substrate yet. Approved phrases shape fields and joins.

Phrase authority should be lexicon-shaped and reviewable. It may help lock a field such as:

```text
newton laws of motion
```

Phrase authority must not mutate Canonical word authority.

### NULL

NULL is an exact exclusion coordinate. NULL is not relation memory, not speech, and not Canonical.

NULL belongs in coordinate indexes:

```text
source_id
block_id
line
anchor_position
surface
reason
```

NULL must never enter AWSC relation cells.

## 3. The Lexicon Path

All user input should begin with lexicon recognition.

Procedure:

```text
1. Receive input text.
2. Normalize only enough to identify visible surfaces.
3. Split into candidate anchors.
4. Look up each candidate in Canonical, Structural, companion lanes, phrase authority, and user lexicon if enabled.
5. Return represented anchors and missing anchors.
6. Convert represented anchors to symbols.
7. Pass symbols to counts, document search, frame induction, or rendering.
```

Important rule:

```text
The lexicon recognizes shape before the system searches for proof.
```

If a user asks:

```text
hello
```

and `hello` is in the lexicon, the system must recognize its lexicon shape even if documents and lifetime counts do not contain support for it.

The correct behavior is not:

```text
No evidence, therefore no recognition.
```

The correct behavior is:

```text
Recognized by lexicon.
No source/count support found for grounded answer.
```

## 4. Symbol Genome

The symbol genome is the current forward direction for symbol assignment.

The genome allocator must prevent duplicate symbols and must provide new symbols on demand.

Hard laws:

```text
No old spare slot dependency as authority.
No tone_signature as identity.
No font_symbol as identity.
status remains lifecycle only.
tone_signature is reserved for future TTS/style work, not symbol identity.
```

Correct minimal live word record:

```json
{
  "word": "motion",
  "symbol": "0x1000000001"
}
```

Migration rule:

```text
Original curated lexicons are preserved.
Genome rebuilds are created beside the old world.
No Canonical rewrite happens without old-to-new map and rollback file.
```

## 5. Intake Overview

AnchorWorks intake turns source material into symbolic structures.

General source flow:

```text
source file
-> preservation layer
-> prepared text or media evidence
-> anchorization
-> lexicon recognition
-> symbol stream
-> source-local map
-> local overlay
-> count stream
-> binary count cells
```

For text-first material, the prepared text path can run directly after source preservation.

For visualizable material, the visual sovereignty rule applies.

## 6. Visual Sovereignty

Hard rule:

```text
Never normalize before vision.
Vision is the deterministic truth record.
All cleanup, normalization, repair, compression, symbol conversion, or text shaping happens after visual proofing.
```

Meaning:

```text
PDF or image source
-> preserve page/frame visual state
-> record native geometry/hash/order/timing
-> attach visual references
-> then derive text or symbols
```

A visual frame proves pixels. It does not prove words until recognition exists.

Correct separation:

```text
TrueVision preserves visual state.
Glyph/region recognition derives text later.
Text extraction is a source claim.
Dual-path verification compares visual and text paths.
```

If source text and visual proof disagree, both sides stay recorded and the disagreement becomes review evidence.

## 7. Observed Maps

Observed maps preserve source-local topology.

The conceptual map shape is:

```text
source
-> block
-> line
-> occurrence
-> anchor/symbol
-> relation windows
-> locator evidence
```

Observed JSON maps are now debug/audit artifacts, not the preferred hot runtime format.

Current law:

```text
JSON explains.
Graph connects.
AWSM serves relations.
AWSC remembers weight.
Renderer cites.
```

Observed map JSON should not be loaded in chat runtime when a compact overlay or binary sidecar can serve the needed data.

## 8. AWSM Symbolic Maps

AWSM means AnchorWorks Symbolic Map.

AWSM is the binary source-local symbolic map layer. It carries compact source-local relation structure.

AWSM should be the hot path for source-local symbolic relations.

AWSM exists because:

```text
JSON observed maps are human-readable but too large for runtime.
AWSM preserves relation shape in a compact binary form.
AWSL/AWSN/AWSV sidecars preserve locators, NULL coordinates, and visual references.
```

AWSM should be trusted only after parity and verify checks.

## 9. AWSL Locator Sidecars

AWSL preserves locator tissue.

Purpose:

```text
symbol relation evidence
-> block/line/page locator
-> human audit address
```

AWSL lets the system point back to source coordinates without loading massive observed map JSON.

Renderer citations should cite locator addresses, not vague evidence labels.

## 10. AWSN NULL Sidecars

AWSN preserves exact NULL coordinates.

NULL entries do not become relation memory.

Use AWSN for:

```text
unknown surface
excluded symbol
structural gap
parse anomaly
source-local unresolved item
```

Never use NULL as a speech candidate.

## 11. AWSV Visual Sidecars

AWSV preserves visual references.

Use AWSV for:

```text
PDF page frame reference
image frame reference
visual hash
geometry
page number
frame index
recognition status
region status
```

AWSV can say:

```text
this page/frame exists
this geometry was preserved
recognition has not run
```

AWSV cannot say:

```text
this text is true
this figure means X
this chart proves Y
```

Recognition and interpretation come later.

## 12. AWSS Symbol Streams

AWSS is the source-local symbol relation stream.

It exists to feed binary counting without using huge JSON relation rows.

Correct flow:

```text
symbolized source
-> 6-1-6 relation observations
-> AWSS stream
-> native merge
-> AWSC cells
```

Do not use JSON relation rows as production hot path.

## 13. AWSC Binary Count Cells

AWSC means AnchorWorks Symbol Count Cell.

AWSC stores observed symbol relationships in binary cells.

AWSC v1.1 contract:

```text
64-byte little-endian header
16-byte fixed relation rows
u64 counts
payload CRC
total_size
generation
reserved WAL frame
reserved overflow offset
deterministic row order
no strings in relation payload
```

Relation row:

```text
neighbor_symbol[5]
offset_i8
lane_u8
flags_u8
count_u64
```

Approved lanes:

```text
0 canonical
1 math_companion
2 structural_companion
3 source_specific
4 source_local_temp
5 user_lexicon
255 reserved_error
```

Approved flags:

```text
bit 0 speak_blocked
bit 1 source_local_only
bit 2 companion
bit 3 user_scope
bit 4 audit_only
bit 5 overflow_related
bit 6 reserved
bit 7 reserved
```

Sort order:

```text
offset ascending
count descending
neighbor_symbol ascending
lane ascending
```

Hard law:

```text
NULL never enters AWSC relation memory.
```

## 14. Counts

Counts are observed memory pressure.

Counts record:

```text
which symbols appeared
which symbols appeared around them
at what offsets
how often
inside which source-local or global field
```

Counts do not prove truth by themselves.

Counts are useful for:

```text
candidate selection
context cloud building
top-K answer walk
role pressure
phrase field support
source-local resonance
global language pressure
```

Counts are not useful for:

```text
claiming a source fact without occurrence proof
inventing missing answer content
replacing document evidence
mutating Canonical
```

## 15. Local Meta-Count Overlays

Local meta-count overlays replace giant map loads in runtime.

Overlay extension:

```text
*.local_overlay.awlo.json
```

Fields:

```text
schema_version
source_id
symbolized_flat_doc_ref
locator_ref
visual_ref_locator_ref
local_relation_counts
local_symbol_counts
top_local_neighbors
block_relation_index
created_from_observed_map
created_at
checksum
```

Purpose:

```text
flat document preserves source text
locator preserves source address
local overlay preserves source-local pressure
global AWSC supplies broader memory pressure
renderer uses both
```

Law:

```text
Maps explain.
Overlays serve.
Flat docs preserve.
AWSC supplies memory pressure.
```

## 16. Flat Documents

Flat documents preserve text for source search and citation.

Use flat docs for grounded document search:

```text
question symbols
-> find relevant flat doc blocks
-> gather factual passages
-> return source coordinates
```

Flat docs should not be replaced by count-only answer generation when a factual claim is required.

Correct document answer path:

```text
lexicon anchor verification
-> flat document fact gathering
-> source-local 6-1-6 overlay
-> count top-K answer walk
-> human rendered text at edge
```

## 17. Document Search

Document search should use flat documents and local overlays, not giant observed map JSON.

Procedure:

```text
1. User asks a document-style question.
2. Input is passed through lexicon recognition.
3. Represented anchors become symbols.
4. Search flat docs for fact-bearing blocks.
5. Use local overlays to build source-local cloud pressure.
6. Use global counts for language assembly pressure.
7. Render a concise answer.
8. Attach citations to source blocks/lines.
```

If document search fails:

```text
state that no source-local support was found
show represented and missing anchors
do not silently substitute counts as source proof
```

## 18. ClearSpeak

ClearSpeak is the count-walk speaking layer.

ClearSpeak should:

```text
recognize input through lexicon
resolve anchors to symbols
load count support
build active context clouds
rank top-K candidates
use lookahead to avoid anomalous paths
assemble answer path
render human text at the edge
show trace
```

ClearSpeak must not:

```text
dump random high-count words
use unrelated candidates like mother for physics
claim source proof from counts alone
ignore glue/director words in answer shape
render raw candidates as final speech
```

## 19. Active Cloud Answer Formula

Core objects:

```text
Q = question cloud
R = rear context cloud
A_t = answer-so-far cloud at step t
F_t = forward candidate cloud at step t
C_t = combined active cloud at step t
K = top-K candidate count
```

At each answer step:

```text
C_t = wq Q + wr R + wa A_t + wf F_t
```

Default weights:

```text
wq = 0.35 question intent
wr = 0.25 rear context / grammar fit
wa = 0.30 answer-so-far coherence
wf = 0.10 forward local continuation
```

Candidate set:

```text
Candidates_t = topK6(next_symbols | C_t)
```

Score:

```text
Score(x) =
  0.30 * question_fit(x, Q)
+ 0.25 * rear_fit(x, R)
+ 0.25 * answer_fit(x, A_t)
+ 0.15 * forward_fit(x, F_t)
+ 0.05 * source_support(x)
+ count_pressure(x)
+ frame_fit_boost(x)
- penalties(x)
```

Penalties:

```text
glue_as_content_penalty
unsupported_jump_penalty
repetition_penalty
contradiction_penalty
source_mismatch_penalty
query_echo_penalty
domain_drift_penalty
```

Answer update:

```text
A_{t+1} = decay(A_t) + chosen_candidate_cloud(x)
```

Suggested decay:

```text
A_{t+1} = 0.85 A_t + 1.00 V_x
```

Lookahead:

```text
chosen candidate
-> open future top-K
-> check if future field remains coherent
-> reject if future is anomalous
```

Law:

```text
Question anchors pull direction.
Rear context enforces shape.
Answer-so-far preserves coherence.
Forward top-K provides choices.
Gates decide permission.
Scores decide movement.
Trace explains speech.
```

## 20. Glue Words

Glue words are part of the observed math.

Examples:

```text
of
to
for
with
is
not
what
how
does
why
```

Glue should not dominate subject selection, but it should shape direction.

Correct rule:

```text
Glue stays in placement/top-K math.
Glue is downgraded as answer content.
Glue directs the anchors that do become content.
```

Do not remove glue so aggressively that the answer loses grammar and frame direction.

## 21. Question Frame Induction

Question frame induction is the activity chooser / thought-shaping layer.

It does not answer questions.

It converts live questions into reusable answer-shape frames:

```text
live question
-> activity
-> frame_type
-> reasoning_frame
-> slots
-> confidence
-> trace
```

Examples:

```text
Why does X happen?
-> causal_explanation

How does X work?
-> process_explanation

What is X?
-> definition

Compare X and Y
-> comparison

Does X imply Y?
-> implication_check
```

Hard law:

```text
Frames are learned as reusable transformations, not stored answers.
```

The reasoning-frame corpus is not global answer memory.

Distilled frame-cloud rules are used at runtime:

```text
frame_cloud_rules.json
FRAME_CLOUD_RULES.md
```

The runtime must not scan a 10,000-row frame corpus for every chat answer.

Correct flow:

```text
offline frame corpus
-> compact frame cloud rules
-> runtime frame induction
-> answer assembly guidance
```

Frame clouds teach aiming. They do not teach factual answers.

## 22. Phrase Authority

Phrases are recognized authority, not count memory.

Phrase authority can help lock fields:

```text
laws of motion
newton laws of motion
separation of powers
checks and balances
```

Phrase rows should be separate from word anchors and browsable by a Words/Phrases toggle later.

Phrase records should include:

```text
phrase
symbol
anchor_sequence
status
source/proof fields when available
```

Phrases must not be hard-coded into the renderer.

Correct rule:

```text
Phrase authority locks the field.
Counts assemble the answer through anchor-symbol pressure.
```

## 23. Evidence Lanes

Every answer should know its evidence lane.

Possible lanes:

```text
document evidence
count evidence
phrase authority
visual witness
external model
no source support
```

Evidence toggle in UI may hide evidence display, but backend must preserve evidence metadata.

Hard law:

```text
Counts may shape speech.
Occurrences prove source.
Renderer must label the lane.
```

## 24. Chat Modes

Current chat modes include:

```text
counts
clearspeak
documents
auto
api/external/model
document_payload_guard
```

Counts mode:

```text
uses ClearSpeak count walk
does not call documents as substitute proof
```

Document mode:

```text
uses source-local docs/overlays
should not fall back to counts as if counts were source proof
```

External API mode:

```text
uses configured external model endpoint
must remain clearly labeled
does not mutate AnchorWorks truth
```

Payload guard:

```text
detects pasted documents or large payloads
does not treat them as user questions
```

## 25. Chat Memory

Chat memory records user and assistant exchanges.

Chat memory should support:

```text
chat rows
citations
notes
continue working
stop response
side chats
finalize/preview
archive import
```

Chat memory is not the same as global source truth. When a chat day is finalized, it should become an intake source only through an explicit prepare/finalize path.

Do not silently write chat content into counts while answering.

## 26. UI Principles

UI is disposable. Backend truth is not.

Main UI law:

```text
A UI control is a promise.
If runtime cannot honor it, do not render it.
```

Core UI surfaces:

```text
Chat
Evidence
Lexicon
System
```

Future surfaces:

```text
Intake
Counts
Visual
Phrase Browser
Frame Trace
```

Invoked UI rule:

```text
Dynamic UI, static recipes.
```

The user may ask chat to surface a temporary control panel. The backend should return assistant text plus allowed actions. The UI renders known registered controls only. The AI must not invent arbitrary button behavior.

Control law:

```text
Chat explains.
Buttons execute.
Backend permits.
```

## 27. Data Curation

AnchorWorks needs clean data to build useful count fields.

Data curation should prioritize:

```text
clean education Q/A
source-grounded Q/A
college-level science/math/CS
OpenStax
NIST/NASA technical material
Lee's proven system docs
ARC solver proven Q/A
reasoning frame cloud rules
```

Do not bulk ingest dirty web-scale corpora before smaller clean fields prove useful.

Hard laws:

```text
No account-gated scraping.
No unknown-license ingestion.
No unanswered worksheets as answer authority.
No multiple-choice distractor pollution.
No medical/high-stakes corpus without explicit safety lane.
```

Unanswered frame corpora:

```text
may teach aiming
may not teach speaking
may not teach truth
```

Answered triples:

```text
Question
Answer_Frame
Expected_Answer
```

can become eligible for map/count experiments only after validation.

## 28. Background Jobs

Long ingest must be detached and observable.

Hard law:

```text
Jobs run detached.
Codex reports and exits.
The filesystem manifest is the process manager.
```

Detached jobs should support:

```text
start
status
resume
stop
```

Each job must write:

```text
run_id
chunk_id
source paths
source hashes
files ok
files failed
anchors observed
relation observations
output paths
verify status
elapsed time
peak RAM
resume cursor
```

Do not camp on a long process in an assistant session.

## 29. Memory Governor

Large ingest should obey a memory budget.

Recommended budget:

```text
hard max process target: 40 GB
soft warning: 32 GB
emergency flush: 36 GB
abort current chunk safely: 39 GB
```

Chunking strategy:

```text
250 files per chunk
or 250 MB prepared text
or 25 million relation observations
or 32 GB RAM observed
whichever comes first
```

Procedure:

```text
source files batch
-> prepare text
-> extract anchors
-> symbol stream
-> native 6-1-6 relation build/count
-> write binary output
-> verify chunk
-> write checkpoint
-> free memory
-> next chunk
```

## 30. Testing Rules

Every serious change needs tests.

Current verification pattern:

```powershell
$env:PYTHONPATH='D:\AnchorWorks_Clean_Runtime\Anchorworks\src'
python -m unittest discover -s 'D:\AnchorWorks_Clean_Runtime\test\test data\tests' -q
```

Binary verification:

```powershell
anchorworks-symbol-counts.exe verify --root D:\AnchorWorks_Clean_Runtime\State\symbol_counts_binary
```

Do not claim success without verification output.

## 31. Git And Runtime Data

Runtime data should not be committed.

Do not commit:

```text
State/lifetime_co_occurrence_counts.json
State/source_local_symbol_counts
State/symbol_counts_binary
State/chat_memory
runtime map/count outputs
temporary ingestion outputs
```

Do commit:

```text
source code
contracts
docs
tools
tests
small fixtures
plans
schema definitions
```

If runtime state changes during tests, inspect before committing.

## 32. How To Ask AnchorWorks Questions

Good source-grounded questions:

```text
What is Newton's second law?
How does acceleration relate to force and mass?
Why do laws of physics matter?
What does the source say about motion?
Compare mass and weight.
```

Good system questions:

```text
What is ClearSpeak?
What is AWSC?
What does AWSM preserve?
How does AnchorWorks use counts?
What is the visual sovereignty rule?
```

Good operational questions:

```text
Show represented anchors for this query.
Use counts only.
Use documents only.
Show evidence.
Hide evidence.
Continue working.
Stop.
```

Bad expectations:

```text
Expecting counts to prove source facts.
Expecting visual frames to reconstruct text without recognition.
Expecting frame patterns to answer facts.
Expecting lexicon recognition to imply count support.
```

## 33. How To Ingest A Single Text Source

Procedure:

```powershell
$env:PYTHONPATH='D:\AnchorWorks_Clean_Runtime\Anchorworks\src'
python -m AnchorWorks.cli symbolic-batch-intake `
  --data-root D:\AnchorWorks_Clean_Runtime `
  --source-dir D:\AnchorWorks_Clean_Runtime\State\intake_uploads\some_folder `
  --pattern some_file.md `
  --map-root D:\AnchorMaps `
  --max-workers 1 `
  --generation 20260515
```

Expected outputs:

```text
observed map
AWSM
AWSL
AWSN
AWSV if visual refs exist
source-local symbol counts
flat document runtime
local overlay
AWSS/AWSC update if enabled by path
```

After ingest:

```text
run a document query
run a counts query
inspect citations
inspect represented/missing anchors
verify no unrelated runtime files were committed
```

## 34. How To Add A Q/A Dataset

Procedure:

```text
1. Inspect dataset license and shape.
2. Convert to plain question -> answer rows.
3. Resolve multiple-choice answer keys to answer text.
4. Keep distractors as blocked alternatives, not truth.
5. Mark approved_for_intake only after review.
6. Store under external curation root.
7. Stage into intake only after conversion report passes.
```

Do not ingest raw multiple-choice distractors as if they were facts.

## 35. How To Add A Frame Dataset

Frame datasets are not answer datasets.

Procedure:

```text
1. Stage frame rows externally.
2. Build compact frame cloud rules.
3. Runtime reads compact rules only.
4. Frame rules guide activity/frame selection.
5. Do not merge unanswered frames into global counts.
```

Law:

```text
Unanswered frames may teach aiming.
Answered triples may teach speaking.
Only verified sources may teach truth.
```

## 36. How To Use TrueVision For Documents

Procedure:

```text
1. Preserve original document visual state.
2. Extract page/frame visual records.
3. Assign frame_index, page_number, frame_timestamp_ms.
4. Record geometry/hash/order.
5. Attach AWSV visual references.
6. Run text extraction separately.
7. Normalize text after visual proofing.
8. Run dual-path verification later when recognition exists.
```

Do not call visual preservation OCR.

Do not claim prose reconstruction from pixels until glyph/region recognition exists.

## 37. How To Debug Bad Answers

When an answer is bad, inspect:

```text
represented anchors
missing anchors
question frame
learned frame guidance
source-local facts gathered
local overlay support
global count support
top-K candidates
lookahead health
rejected candidates
final answer path
evidence lane
citations
```

Common failure:

```text
wrong lane chosen
lexicon recognized but counts missing
counts support unrelated high-frequency candidates
document gathering found a heading but not a fact
glue words were blocked too early
frame guidance did not constrain candidate choice
source proof missing
```

Correct response:

```text
trace first
fix the smallest disconnected step
test with a tiny source
then test with the larger corpus
```

## 38. How To Debug UI

First verify active served root.

Do not assume there are many UIs.

Procedure:

```text
1. Identify active UI root from app.py.
2. Identify backend routes UI calls.
3. Verify /api/chat/send works directly.
4. Verify UI sends expected JSON.
5. Verify response shape matches renderer.
6. Remove fake auth and fake controls.
```

UI law:

```text
No fake cockpit.
Every visible switch must either run the machine or clearly say it does not.
```

## 39. Hard Forbidden Moves

Do not:

```text
normalize before vision
put NULL into AWSC relation memory
store strings in AWSC relation payloads
let tone_signature carry symbol identity
let phrase lexicon mutate Canonical
let companion lanes mutate Canonical
let visual evidence become truth directly
use JSON lifetime monolith in hot path
load giant observed maps in chat runtime
let renderer speak raw candidate piles
let counts cite without occurrence proof
ingest unanswered frames as answer knowledge
let UI show controls backend cannot honor
camp on long background jobs
```

## 40. One-Page Operating Summary

```text
AnchorWorks recognizes words with the lexicon.
The lexicon resolves words to symbols.
Symbols are the internal computation language.
Source intake creates maps, sidecars, streams, overlays, and count cells.
Flat documents preserve source text.
AWSM serves compact local relations.
AWSL/AWSN/AWSV preserve locator, NULL, and visual evidence.
AWSC stores binary count memory.
ClearSpeak walks counts through active context clouds.
Question frame induction tells the answer what shape is being requested.
Document search gathers facts from flat docs.
Counts assemble pressure and candidate path.
Renderer speaks only permitted human text.
Evidence lanes remain attached even when hidden in UI.
```

Final law:

```text
Lexicon is the key.
Symbols are the engine.
Counts are memory.
Sources are proof.
Frames aim.
Renderer speaks.
Trace keeps everyone honest.
```
