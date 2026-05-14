# Architecture Chart Inputs

Date: 2026-05-14

This file distills `ARCHITECTURE_PATH_TRACE.md` into chartable boxes and arrows. Only active or explicitly staged traced paths should appear.

## Legend

```text
green  = active connected runtime
yellow = partial/staged
orange = active compatibility bridge or known mismatch
blue   = external/future contract shell
red    = legacy/excluded
gray   = planned/docs only
```

## Boxes

### Active Runtime Boxes

```text
Source Intake
Canonical Lexicon Recognition
Genome Allocator
AWSM Symbolic Maps
AWSL Locator Sidecars
AWSN NULL Sidecars
AWSV Visual Sidecars
Source-Local Symbol Count Artifacts
AWSS Relation Stream
C++ Native Symbol Counts
AWSC Binary Count Cells
ClearSpeak Symbol Walk
Q/R/A/F Active Cloud
Top-K Lookahead
Verification Harness
```

### Partial/Staged Boxes

```text
Document Evidence Mode
Local Meta-Count Overlays
AWSG Source Graph
Phrase Authority
User/Workspace Lexicon
```

### Compatibility/Warning Boxes

```text
Genome/Legacy Count Bridge
AWSC Tiny-Cell Fanout
```

### Planned/External Boxes

```text
V2 Boundary Brain
Invoked UI Recipes
GPU/Sparse Matrix Scoring
Packed AWSC Shards
```

### Legacy/Excluded Boxes

```text
Spare_Slots Legacy Pool
Legacy JSON Lifetime Monolith
Old Lexicon Identity Fields
```

## Primary Arrows

```text
Source Files
  -> document_prep/intake
  -> Canonical/Structural recognition
  -> observed map debug JSON
  -> AWSM/AWSL/AWSN/AWSV
  -> source-local symbol count artifacts
  -> AWSS stream
  -> C++ merge-stream
  -> AWSC cells
  -> ClearSpeak count index
  -> Q/R/A/F active cloud
  -> Top-K lookahead
  -> rendered text at edge
```

## Identity Arrows

```text
Canonical rows word -> genome symbol
Genome allocator -> State/symbol_genome_pool/manifest.json
Lexicon_Genome_Rebuild mappings -> ClearSpeak old-symbol bridge
Legacy AWSC symbols -> bridge -> anchor display
```

## Evidence Arrows

```text
AWSL locators -> citation/address support
AWSN NULL sidecars -> exclusion audit
AWSV visual sidecars -> page/frame visual evidence
AWSG proof graph -> topology/debug export only today
Local overlays -> compact source-local cloud support
```

## Renderer Arrows

```text
query text
  -> lexicon recognition
  -> represented/missing anchors
  -> phrase match, if any
  -> count index load
  -> active cloud C_t = wq Q + wr R + wa A_t + wf F_t
  -> candidate scoring
  -> lookahead health check
  -> answer path trace
```

## Warning Callouts

```text
GENOME <-> LEGACY AWSC COUNT IDENTITY BRIDGE NEEDED/ACTIVE
Phrase authority exists but has zero live rows.
AWSG production graph root is empty; proof graph exists under test data.
V2 is a contract destination, not active runtime.
Spare_Slots remains referenced in code but is not intended authority.
AWSC tiny-cell fanout is active and verified, but storage needs packed shard/index future.
```

## Chart Labels

```text
Source Intake: active
Lexicon Recognition: active
Genome Allocator: active
Canonical Authority: active
User Lexicon: staged
Phrase Authority: staged empty
AWSM/AWSL/AWSN/AWSV: active
AWSS: active with legacy identity warning
AWSC: active with fanout warning
Genome/Legacy Count Bridge: active compatibility
ClearSpeak: active
Q/R/A/F Cloud: active
Top-K Lookahead: active
Document Evidence: partial
AWSG: proof/staged
Native Commands: active V1 / staged V2
V2 Contracts: external staged
Invoked UI: planned
Legacy Spare Pool: legacy/excluded
Tests: active
```

