# AnchorWorks Positional Resonance Index Plan

Status: plan only
Source sample: `G:\basement_analysis  RESONANCE SAMPLE FOR LEARNING`
AnchorWorks target root: `D:\AnchorWorks_Clean_Runtime\Anchorworks`

## Purpose

The Basement sample proves a useful middle layer between exact document evidence and broad count memory:

```text
anchor/symbol occurrence
-> positional 6-1-6 neighbors
-> directional resonance
-> context clouds
-> retrieval expansion
-> exact occurrence grounding
-> answer shaping
```

This is not lifetime count ingestion by itself. It is a source-local positional resonance index used to improve search, RAG expansion, answer shaping, and trace inspection.

Tiny law:

```text
Resonance finds the neighborhood.
Occurrences prove the address.
Speech must cite the address.
```

## Evidence From The Basement Sample

Files inspected:

- `G:\basement_analysis  RESONANCE SAMPLE FOR LEARNING\summary_report.md`
- `G:\basement_analysis  RESONANCE SAMPLE FOR LEARNING\process_story.py`
- `G:\basement_analysis  RESONANCE SAMPLE FOR LEARNING\analysis_results.json`
- `G:\basement_analysis  RESONANCE SAMPLE FOR LEARNING\context_map.json`
- `G:\basement_analysis  RESONANCE SAMPLE FOR LEARNING\context_clouds.json`

Observed sample behavior:

- `summary_report.md` reports 2,544 words, 30,528 context relationships, 2,544 context clouds, and average cloud size 19.80.
- `process_story.py:42` constructs `ContextWindowParser(window_size=6, top_k=5)`.
- `process_story.py:67` constructs `DirectionalSemanticResonance`.
- `process_story.py:70` constructs `ContextCloudManager`.
- `process_story.py:73` builds context clouds with `threshold=0.3`.
- `process_story.py:117` computes directional resonance between focus words.
- `process_story.py:197` exports `context_map.json`.

Useful result shape:

```text
focus word
-> offset -6..-1 and +1..+6
-> top neighbors per offset
-> directional resonance scores
-> context cloud members + strengths
```

Example from `summary_report.md` for `basement`:

```text
-3: creatures, rift, back, hole, of
-2: in, into, of, from, the
-1: the, cursed, your, her, murky
+1: door, and, she, in, it
+2: she, but, fact, there, was
+3: was, ashley, knew, the, it
```

Strong directional resonance examples:

```text
basement -> creatures: 1.0000
creatures -> basement: 1.0000
evil -> basement: 1.0000
flashlight -> basement: 1.0000
basement -> evil: 0.8000
```

Production risk in the sample:

```text
The sample aggregates positional relationships but does not preserve citation-grade occurrence addresses.
```

AnchorWorks must keep the resonance cloud separate from proof.

## Current AnchorWorks Fit

Current code already has the raw skeleton:

- `src/AnchorWorks/intake.py` builds relation counts from anchor windows and occurrence rows.
- `src/AnchorWorks/intake.py:257` defines `build_context_views(...)`.
- `src/AnchorWorks/intake.py:299` builds context `items`.
- `src/AnchorWorks/intake.py:319` builds `anchor_index`.
- `src/AnchorWorks/intake.py:341` limits bucket rows to top-k neighbors.
- `src/AnchorWorks/store.py:907` serializes relation rows with `anchor`, `offset`, `neighbor`, and `observations`.
- `src/AnchorWorks/store.py:1123` retrieves combined count neighbors for ClearSpeak.
- `src/AnchorWorks/clearspeak.py:45` gathers count evidence per represented anchor.
- `src/AnchorWorks/clearspeak.py:58` currently emits count coordinates as `clearspeak:lifetime:{anchor}`.

Current observed-map payload already contains:

```text
paragraphs
occurrences
co_occurrence_counts
items
anchor_index
stats
```

Current limitation:

```text
The counts path can say which neighbors are strong, but the answer path still needs exact occurrence addresses to prove where useful evidence happened.
```

## Architecture Placement

The resonance index belongs after source intake/mapping, not before approval.

```text
source document
-> prepare/clean
-> anchorize/resolve/temp-symbolize
-> observed source map
-> occurrence address index
-> source-local positional resonance index
-> retrieval expansion
-> occurrence-backed evidence selection
-> renderer
```

It must not bypass current laws:

```text
Preview is free.
Memory writes require approval.
Counts can suggest.
Evidence proves.
Temp symbols are source-local only.
```

## Required Layer Split

### 1. Occurrence Address Index

Question answered:

```text
Where exactly did this symbol happen?
```

Authority:

```text
evidence address / citation source
```

It is allowed to support document answers because it points to source/block/line/token coordinates.

### 2. Positional Resonance Index

Question answered:

```text
What tends to appear around this symbol, by exact offset?
```

Authority:

```text
retrieval expansion / answer shaping / trace support
```

It is not citation proof by itself.

### 3. Directional Resonance Index

Question answered:

```text
How strongly does one symbol point toward another in this source or lane?
```

Authority:

```text
ranking / candidate expansion / relationship suspicion
```

It must not speak as fact without occurrence support.

### 4. Context Cloud Index

Question answered:

```text
What is the source-local neighborhood around this symbol?
```

Authority:

```text
query expansion / related-term discovery / trace-visible search help
```

It must not become durable truth unless promoted.

## Proposed Runtime Files

All files below are runtime/state files, not static repo source files.

### Source-Local Occurrences

```text
State/source_local_occurrences/{source_id}.occurrences.jsonl
```

One row per resolved anchor/symbol occurrence.

### Source-Local Positional Profiles

```text
State/source_local_resonance/{source_id}.positional_profiles.jsonl
```

One row per center symbol, offset, neighbor symbol, and source-local support count.

### Source-Local Directional Resonance

```text
State/source_local_resonance/{source_id}.directional_resonance.jsonl
```

One row per directed pair.

### Source-Local Context Clouds

```text
State/source_local_resonance/{source_id}.context_clouds.jsonl
```

One row per center symbol cloud.

### Source-Local Resonance Summary

```text
State/source_local_resonance/{source_id}.summary.json
```

Small UI/debug summary.

## Proposed Record Shapes

### Occurrence Record

```json
{
  "contract": "anchorworks_symbol_occurrence@1",
  "occurrence_id": "occ_<source_id>_<paragraph_id>_<position>",
  "source_id": "...",
  "source_name": "The_Basement.prepared.txt",
  "source_path": "...",
  "paragraph_id": 16,
  "block_id": 16,
  "line_start": 45,
  "line_end": 45,
  "token_index": 123,
  "anchor_position": 42,
  "surface": "basement",
  "anchor": "basement",
  "symbol": "0x...",
  "authority": "source_local_occurrence",
  "scope": "source_local",
  "count_eligible": true,
  "evidence_eligible": true,
  "speak_eligible": false,
  "left_window_symbols": ["..."],
  "right_window_symbols": ["..."],
  "window_radius": 6,
  "locator": {
    "source": "The_Basement.prepared.txt",
    "block": 16,
    "line": 45
  }
}
```

### Positional Profile Row

```json
{
  "contract": "anchorworks_positional_resonance@1",
  "source_id": "...",
  "scope": "source_local",
  "center_anchor": "basement",
  "center_symbol": "0x...",
  "offset": "-3",
  "neighbor_anchor": "creatures",
  "neighbor_symbol": "0x...",
  "observations": 7,
  "support_occurrence_count": 7,
  "score": 0.875,
  "rank_at_offset": 1,
  "window_radius": 6,
  "evidence_eligible": false,
  "retrieval_eligible": true,
  "speak_eligible": false
}
```

### Directional Resonance Row

```json
{
  "contract": "anchorworks_directional_resonance@1",
  "source_id": "...",
  "scope": "source_local",
  "from_anchor": "basement",
  "from_symbol": "0x...",
  "to_anchor": "creatures",
  "to_symbol": "0x...",
  "directional_score": 1.0,
  "method": "shared_positional_context@1",
  "support_offsets": ["-3", "+1"],
  "support_occurrence_count": 4,
  "retrieval_eligible": true,
  "evidence_eligible": false,
  "speak_eligible": false
}
```

### Context Cloud Row

```json
{
  "contract": "anchorworks_context_cloud@1",
  "source_id": "...",
  "scope": "source_local",
  "center_anchor": "basement",
  "center_symbol": "0x...",
  "threshold": 0.3,
  "members": [
    {
      "anchor": "creatures",
      "symbol": "0x...",
      "strength": 1.0,
      "best_offsets": ["-3"],
      "support_occurrence_count": 7
    }
  ],
  "retrieval_eligible": true,
  "evidence_eligible": false,
  "speak_eligible": false
}
```

## Integration Plan

### Phase 1: Contract And Shape Only

Add docs and schema tests only.

Planned files:

```text
docs/ANCHORWORKS_POSITIONAL_RESONANCE_INDEX_PLAN.md
src/AnchorWorks/positional_resonance_schema.py
tests/test_positional_resonance_schema.py
```

No builder yet.

### Phase 2: Occurrence Index Builder

Build occurrence rows from existing observed-map payloads.

Input:

```text
observed map payload: paragraphs + occurrences + co_occurrence_counts
```

Output:

```text
State/source_local_occurrences/{source_id}.occurrences.jsonl
```

Rules:

```text
No lifetime writes.
No canonical lexicon writes.
No count promotion.
Each row must carry locator/provenance.
```

### Phase 3: Source-Local Resonance Builder

Build positional profiles, directional resonance, and clouds from approved source-local maps.

Output:

```text
State/source_local_resonance/{source_id}.*
```

Rules:

```text
Resonance rows are retrieval eligible.
Resonance rows are not evidence by themselves.
Clouds cannot cite.
Clouds must lead back to occurrence ids.
```

### Phase 4: Retrieval Expansion Hook

When documents/maps are allowed:

```text
query anchors
-> source/lane resonance expansion candidates
-> exact occurrence retrieval
-> source/block/line evidence selection
```

When documents are off:

```text
Do not read source-local resonance.
Use strict counts-only path.
```

### Phase 5: UI Trace Surface

Add a trace-only panel later:

```text
Query anchor
Expansion cloud
Directional resonance candidates
Occurrence addresses found
Evidence chosen
Evidence rejected
```

Required warning:

```text
Cloud membership is not citation evidence.
```

## Fit With Temp Symbols

Unknowns may be represented by source-local U-symbols.

Rules:

```text
U-symbols may appear in source-local occurrence and resonance files.
U-symbols may not enter lifetime counts.
U-symbols may not speak as canonical meaning.
U-symbol resonance is useful for repair/review/search only.
```

This matches the current store behavior where temp entries carry `authority: source_local_coordinate`, `lifetime_eligible: false`, and `speak_eligible: false` in `src/AnchorWorks/store.py:894` through `src/AnchorWorks/store.py:900`.

## Fit With Visual/Bilateral Text

Visual text should not feed resonance directly unless a source/approval gate allows it.

Allowed path:

```text
source text span
-> bilateral text agreement exact/near
-> approved source-layout authority
-> anchor stream
-> occurrence/resonance
```

Visual rescue path:

```text
visual text candidate
-> candidate only
-> review/approval
-> source-local preview resonance only
```

Forbidden path:

```text
unapproved OCR/visual candidate -> lifetime resonance/counts
```

## Answer Path Law

Correct use:

```text
User asks a document question.
Route allows docs/maps.
Resonance expands the search neighborhood.
Occurrence index finds exact source addresses.
Answer cites source/block/line.
Renderer may use resonance for phrasing.
```

Wrong use:

```text
Cloud says basement relates to creatures.
Assistant claims the document proves something without an occurrence address.
```

## Tests Needed Before Runtime Use

- Build occurrence records from a tiny source and prove every row has source/block/line or explicit no-line reason.
- Build positional profile rows and prove offsets remain within -6..-1 and +1..+6.
- Prove context clouds cannot produce citations by themselves.
- Prove documents-off/counts-only chat path does not read `State/source_local_resonance`.
- Prove U-symbol rows are source-local and lifetime-ineligible.
- Prove resonance expansion must resolve back to occurrence ids before answer evidence is emitted.
- Prove deleting/quarantining a source-local resonance file cannot corrupt lifetime counts.

## Do Not Do Yet

- Do not merge Basement prototype code directly.
- Do not add plots or matplotlib.
- Do not make resonance a truth source.
- Do not let clouds speak.
- Do not change ClearSpeak answer behavior before trace-only validation.
- Do not write lifetime counts from source-local resonance.
- Do not use word strings where symbols are available.

## Final Shape

```text
Observed source map
-> occurrence address index
-> positional resonance profiles
-> directional resonance
-> context clouds
-> retrieval expansion
-> exact occurrence evidence
-> cited answer
```

Tiny law:

```text
Counts remember repeated shape.
Resonance finds nearby shape.
Occurrences prove source address.
Promotion decides brain memory.
```
