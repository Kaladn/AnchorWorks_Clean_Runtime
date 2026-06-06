# AW Operator Surface

Date: 2026-06-05
Scope: AnchorWorks only. Code files under `src`, `tests`, and `tools`.

This is an operator-facing inventory, not design fiction. It lists the code systems that exist now and the variables that are worth putting in front of a human operator during ClearSpeak, counts, and intake work.

## Code Inventory By System

| System | Code files | Role |
| --- | ---: | --- |
| `src/AnchorWorks` | 52 | Main runtime: app routes, store, ClearSpeak, document answers, lexicon, counts, visual prep, CLI shell. |
| `src/AnchorWorks/store_modules` | 9 | Store ownership helpers for paths, memory, intake, evidence, authority, visual, admin. |
| `src/AnchorWorks/inference` | 8 | Legacy or parallel inference package inside AnchorWorks. |
| `src/aw_inference_kernel` | 11 | Current local formula/query kernel used before document/count fallback. |
| `src/AnchorWorks/truevision_language` | 8 | TrueVision language contracts, transforms, occular tensor/cloud support. |
| `src/AnchorWorks/truevision_language/intake` | 2 | Glyph-pattern intake support. |
| `src/AnchorWorks/truevision_language/state` | 2 | Document-state movie/runtime-state records. |
| `src/AnchorWorks/truevision_language/cloud` | 1 | Cloud package marker. |
| `src/AnchorWorks/truevision_language/glyphs` | 1 | Glyph package marker. |
| `src/AnchorWorks/truevision_language/rendering` | 1 | Rendering package marker. |
| `src/AnchorWorks/native/symbol_counts` | 4 | Native C++ count cell CLI/library. |
| `src/AnchorWorks/native/symbol_genome` | 2 | Native C++ symbolic identity allocator. |
| `tests` | 20 | Runtime contracts and regression tests. |
| `tools` | 8 | Data curation and build utilities. |

## Operator-Worthy Variables

### Runtime Paths

These are operator-worthy because wrong paths silently create wrong state:

| Variable | Source | Why it matters |
| --- | --- | --- |
| `data_root` | CLI shell, app startup | Top-level runtime root used to derive state and maps. |
| `state_dir` | `LexiconStore` | Owns runtime state, flat docs, staging, count artifacts. |
| `ANCHORWORKS_MAP_ROOT` | environment | Overrides observed-map root. Must be visible when set. |
| `observed_maps_dir` | store paths | Source-local maps that document answers depend on. |
| `symbolic_maps_dir` | store paths | Symbolic map artifacts. |
| `flat_documents/raw` | store paths | Raw document answer sources. |
| `flat_documents/symbolic` | store paths | Anchorized document answer sources. |
| `source_local_symbol_counts` | store paths | Source-local count JSON artifacts. |
| `symbol_counts_binary` | store paths | Binary count-cell artifacts. |
| `ingest_staging_dir` and `ingest_staging_manifest_path` | store paths | Temporary staged intake writes and ledger. |
| `missing_anchor_registry_path` | store paths | Operator review queue for unknown anchors. |

### ClearSpeak And Answer Route

These belong in operator view because they explain why an answer sounded the way it did:

| Variable | Source | Operator meaning |
| --- | --- | --- |
| `query` | CLI/API input | Human ask. Plain text in shell routes here. |
| `limit` | `local_answer`, API body | Evidence/result bound. |
| `evidence_mode` | `local_answer`, API body | `auto`, document/map-only, or count fallback behavior. |
| `engine` | answer result | Shows whether answer came from formula solver, document assembler, no-map response, or ClearSpeak counts. |
| `speech` / `response` | answer result | Human-readable output. |
| `evidence` | answer result | Supporting rows from maps/counts. |
| `citations` | answer result | Document source coordinates when available. |

Current route order:

1. Formula solver.
2. Document answer assembler.
3. ClearSpeak count fallback.

### Intake Readiness

These variables must be visible before mapping:

| Variable | Source | Operator meaning |
| --- | --- | --- |
| `source_name` | intake preview/map | Human label for the source. |
| `source_path` | intake preview | Exact file being checked. |
| `file_size` | intake preview | Basic sanity check for expected source. |
| `file_type` | intake preview | Converter/type clue. |
| `paragraph_count` | preview result | How much text was detected. |
| `known_anchor_count` | preview result | Anchors already recognized. |
| `missing_anchor_count` | preview result | Unique anchors needing review before clean mapping. |
| `missing_anchor_observations` | preview result | How many source observations are blocked by missing anchors. |
| `missing_anchors` | preview result | Review preview for operator action. |
| `visual_preview_only` | preview result | Blocks text map build. Visual evidence needs its own approval route. |

CLI status rules:

| Status | Meaning |
| --- | --- |
| `ready` | No missing anchors and not visual-only. Mapping can proceed. |
| `blocked_missing_anchors` | Missing anchors must be reviewed before mapping. |
| `visual_held` | Visual-only packet is evidence-only for now. Do not map as text. |

### Intake Build And Batch Controls

These are operator-worthy when ingesting large sources:

| Variable | Source | Operator meaning |
| --- | --- | --- |
| `max_workers` | CLI/store batch intake | CPU parallelism. |
| `run_id` | chunked intake CLI/store | Job identity and resume/stop handle. |
| `chunk_file_limit` | chunked intake | Files per chunk before flush. |
| `soft_warning_gb` | chunked intake | Memory warning threshold. |
| `emergency_flush_gb` | chunked intake | Flush threshold before failure. |
| `abort_gb` | chunked intake | Stop threshold after safe chunk flush. |
| `write_chunk_binaries` | chunked intake | Whether chunk binary artifacts are emitted. |
| `manifest_path` | chunked intake | Job report and resume state. |
| `STOP` file | chunked intake CLI | Operator stop request. |
| `files_ok` / `files_failed` | chunked intake manifest | Job quality summary. |
| `memory_status` | chunk manifest | Memory health at chunk boundary. |
| `peak_rss_bytes` | chunk manifest | Peak resident memory seen. |

### Subtitle Conversation Intake

Subtitle, transcript, and simulated-dialogue intake is a conversation-flow lane, not a truth lane.

| Store | Purpose |
| --- | --- |
| `conversation_flow_counts` | Turn-shape transitions such as greeting to greeting or question to answer. |
| `speaker_turn_maps` | Conversation id, turn id, speaker id, reply order, speaker change, timestamp. |
| `source_manifests` | Private local source metadata and normalized turn records. |
| `rejected_or_unknown_lines` | Lines whose conversational shape is unknown or rejected. |

Rules:

1. Subtitles may shape renderer rhythm and turn-taking.
2. Subtitles must not become factual authority by default.
3. Unknown line shape is valid and still keeps anchor counts for the conversation lane.
4. Core anchor counts, evidence counts, lexicon, and lifetime stores are not written by the conversation-flow artifact builder.

Hugging Face dataset `CHATS-Lab/Verbalized-Sampling-Dialogue-Simulation` is a useful test source for this lane because it already has `conversation_id`, JSON-encoded utterance lists, speaker ids, speaker roles, model, method, and turn count. It is simulated model dialogue, so it must stay style/flow/count-test material only. Do not treat it as human dialogue or factual evidence.

### Counts And Binary Substrate

These should stay operator-visible because lifetime counts are the architecture backbone:

| Variable | Source | Operator meaning |
| --- | --- | --- |
| `counts_status()` | store | Current count artifact summary. |
| `binary_substrate_status()` | store | Binary count-cell/readiness state. |
| `.awsc` file exists/size | binary count status | Whether native count cells are present. |
| `.awss` stream exists/size | binary count status | Whether native count stream is present. |
| observed map count | binary/count status | Source-local map coverage. |
| sidecar count | binary/count status | Companion metadata coverage. |
| runtime law fields | binary/count status | Tells operator what is allowed to be runtime authority. |

### Missing-Anchor Review

These are operator-worthy because they gate clean intake:

| Variable | Source | Operator meaning |
| --- | --- | --- |
| `limit` | review queue call | How many entries to inspect. |
| `min_observations` | review queue call | Noise threshold. |
| `entries` | review result | Missing anchors ready for classification. |
| `total_registry_anchors` | review result | Backlog size. |
| `review_status` | review row | Pending/approved/ignored state. |

### Runtime Settings

Current setting inventory says:

| Setting | Runtime active | Operator handling |
| --- | --- | --- |
| `symbol_genome_pool` | Yes | Show capacity, remaining, assigned count, next index, manifest path. |
| `tree_brain_controls` | No | Diagnostic-only. Do not present as active ClearSpeak runtime control. |
| `symbol_policy` | No | Diagnostic-only until wired into active renderer. |
| `policy_diagnostic_queries` | No | Diagnostics harness only. |

Tree-brain controls are still worth documenting for diagnostics, but they should not be shown as live answer knobs until wired:

`max_depth`, `branch_width`, `max_total_nodes`, `soft_total_nodes`, `min_count_threshold`, `dynamic_prune_enabled`, rescue settings, answer level limits, evidence thresholds, scoring weights, and diagnostics file paths.

## Not Worth Operator Eyes During Normal Runs

| Area | Reason |
| --- | --- |
| Internal answer scoring weights inside inference modules | Useful for debugging, not ordinary operation. |
| Built-in stop/glue/noise lists | Policy work only unless they become runtime settings. |
| Glyph package markers and empty package files | No operator decision surface. |
| Visual region internal headers | Visual pipeline diagnostics only. |
| Test fixture details | Developer surface, not operator surface. |
| Tool-only defaults for external data pack builders | Show only when running those tools. |

## Intake Is Ready When

1. `/operator` shows the expected `data_root`, storage paths, count status, and missing review status.
2. `/intake-audit <dir>` reports files seen, prepared count, converter coverage, warnings, and failures.
3. `/intake-ready <path>` returns `ready`.
4. `/intake-map <path>` is only run after readiness passes.
5. Missing anchors are handled in review before mapping, not silently counted as clean runtime evidence.
