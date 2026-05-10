# AnchorWorks Flat Runtime RAG Contract

Last updated: 2026-05-09

## Purpose

Flat runtime RAG is the compact answer path built after source mapping.

Core law:

```text
Maps are build/audit artifacts.
Flat symbolic documents are RAG runtime.
Occurrences prove addresses.
Visuals are source-local sidecar evidence.
Counts remember only approved truth.
```

## Current Runtime Files

After an observed map exists, AnchorWorks can build flat runtime files:

```text
State/flat_documents/symbolic/*.symbolic.json
State/flat_documents/block_index/*.blocks.jsonl
State/flat_documents/occurrence_index/*.occurrences.jsonl
State/flat_documents/visual_links/*.visual_links.jsonl
```

Observed maps stay where they are. AnchorWorks does not move maps; the user may manually archive or move them later.

## Build Route

```text
POST /api/flat-documents/runtime/build
```

Body:

```json
{
  "observed_map_name": "some-map.observed.json"
}
```

The route reads an existing observed map and writes compact runtime files. It does not write lifetime counts, Canonical lexicon, or visual truth.

## Block Records

Each paragraph becomes a block. Even one word is a block.

Block records include:

```json
{
  "schema_version": "flat_symbolic_block@1",
  "source_id": "...",
  "source_name": "book.txt",
  "source_hash": "...",
  "block_id": "block_67",
  "block_ordinal": 67,
  "line_start": 12,
  "line_end": 45,
  "raw_text": "...",
  "anchor_stream": [],
  "symbol_stream": [],
  "visual_refs": [],
  "writes_allowed": {
    "maps": false,
    "counts": false,
    "lifetime": false,
    "lexicon": false
  }
}
```

## Visual Refs

Visual references are evidence links only.

Example:

```json
{
  "visual_record_id": "vis_abc123",
  "kind": "figure",
  "source_path": "...",
  "caption_block_id": "block_68",
  "manifest_id": "...",
  "geometry_status": "known",
  "recognition_status": "not_run"
}
```

Answer rendering may cite a visual ref:

```text
OpenStax Physics, block 67, lines 12-45, figure vis_abc123
```

That citation does not promote the visual record into lifetime memory.

## Runtime Answer Path

Current document answer order:

```text
query
-> anchors
-> flat block index search
-> source passages with block/line/visual refs
-> renderer
-> observed-map fallback only when flat runtime has no support
```

## Forbidden Writes

Flat runtime RAG must not:

- move observed maps
- write lifetime counts
- write Canonical lexicon
- promote visual refs
- treat context clouds as proof
- treat LLM explanations as truth

## Tiny Law

```text
Flat docs serve.
Occurrences prove.
Visuals witness.
Renderer speaks.
Promotion changes memory.
```
