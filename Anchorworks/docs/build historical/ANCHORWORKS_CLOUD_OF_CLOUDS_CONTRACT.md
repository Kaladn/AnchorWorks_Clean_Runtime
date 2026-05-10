# AnchorWorks Cloud Of Clouds Contract

Status: contract-first, no runtime behavior change.

## Purpose

AnchorWorks must not load or search the whole symbolic brain for one answer.

The answer system should open only the symbolic neighborhoods needed for the current query, build a compact temporary answer field, walk candidate anchors inside that field, and render only the completed path.

Core law:

```text
Do not search the brain. Wake the right clouds.
```

## Object Model

```text
ContextCloud
CloudOfClouds
AnswerField
AnswerPath
Renderer
```

### ContextCloud

A `ContextCloud` is the local relation field around one center symbol.

It answers:

```text
When this symbol is active, what neighboring symbols become relevant?
```

Minimum record shape:

```json
{
  "schema_version": "anchorworks_context_cloud@1",
  "cloud_id": "cloud_...",
  "center_symbol": "0x0000000001",
  "center_anchor": "sear",
  "generation": 42,
  "neighbors": [
    {
      "symbol": "0x0000000002",
      "anchor": "meat",
      "offset": 1,
      "lane": "canonical",
      "weight": 88.0,
      "observations": 88,
      "flags": []
    }
  ],
  "writes_allowed": {
    "canonical": false,
    "lifetime": false,
    "lexicon": false
  }
}
```

### CloudOfClouds

A `CloudOfClouds` is a compiled index of which context clouds commonly activate together.

It answers:

```text
If this cloud is active, which other clouds should be opened next?
```

Minimum record shape:

```json
{
  "schema_version": "anchorworks_cloud_of_clouds@1",
  "cloud_id": "cloud_sear",
  "center_symbol": "0x0000000001",
  "linked_clouds": [
    {
      "cloud_id": "cloud_meat",
      "center_symbol": "0x0000000002",
      "activation_weight": 164.0,
      "co_activation_count": 12,
      "relation_type": "shared_answer_field",
      "lane": "canonical",
      "last_seen_generation": 42
    }
  ]
}
```

### AnswerField

An `AnswerField` is the temporary runtime slice opened for one query or frame.

It contains only:

```text
seed clouds
activated neighbor clouds above threshold
eligible candidate symbols
suppression rules
evidence constraints
path limits
```

Minimum record shape:

```json
{
  "schema_version": "anchorworks_answer_field@1",
  "field_id": "field_...",
  "query_symbols": ["0x0000000001", "0x0000000002"],
  "opened_clouds": ["cloud_sear", "cloud_meat"],
  "candidate_symbols": ["0x0000000003"],
  "limits": {
    "max_clouds": 32,
    "max_candidates": 512,
    "max_path_branches": 16
  },
  "stop_reasons": []
}
```

### AnswerPath

An `AnswerPath` is the chosen sequence through an `AnswerField`.

It tracks:

```text
chosen anchors
candidate top-k at each step
why each anchor was chosen
which prior anchors unlocked it
which anchors were suppressed
path score
path coherence
source/count lane
stop reason
```

Minimum record shape:

```json
{
  "schema_version": "anchorworks_answer_path@1",
  "path_id": "path_...",
  "field_id": "field_...",
  "chosen": [
    {
      "step": 1,
      "symbol": "0x0000000003",
      "anchor": "heat",
      "score": 164.0,
      "supporting_clouds": ["cloud_sear", "cloud_meat"],
      "top_k_rank": 1,
      "choice_reason": "highest_supported_candidate"
    }
  ],
  "path_score": 0.91,
  "path_health": "coherent",
  "stop_reason": "answer_path_saturated"
}
```

## Runtime Flow

```text
query symbols
-> detect frame/intent
-> open seed ContextClouds
-> score neighboring clouds
-> open only needed clouds
-> build compact AnswerField
-> top-k candidate walk
-> track AnswerPath
-> path-health score
-> render
```

## Top-K Rule

Top-k does not decide alone.

```text
Top-k proposes anchors.
The path decides sequence.
The renderer speaks the path.
```

Every chosen anchor changes the future candidate field:

```text
chosen anchor
-> answer context changes
-> clouds may open or close
-> candidate top-k changes
-> path health is recomputed
```

## Evidence Rule

Evidence labels are not speech.

```text
Evidence constrains claims.
Evidence does not become the answer text by itself.
```

Clouds may guide retrieval and candidate choice, but clouds do not prove truth.

Proof still comes from:

```text
source-local occurrence addresses
block/line locators
approved symbolic records
approved count lanes
```

## Load Rules

```text
Open seed clouds first.
Open neighbor clouds only if activation crosses threshold.
Cap active clouds.
Cap candidate anchors.
Recompute after every chosen anchor.
Stop when path health saturates or degrades.
```

Default CPU-era caps:

```text
max_seed_clouds: 8
max_open_clouds: 32
max_candidate_symbols: 512
max_path_branches: 16
max_answer_steps: 64
```

These are runtime caps, not storage limits.

## CPU Now

CPU-native work should build:

```text
AWSM/AWSC read APIs
ContextCloud builder from AWSC cells
CloudOfClouds index builder
AnswerField builder
AnswerPath walker
path-health scoring
```

Each piece must be tested independently before it feeds rendering.

## GPU Later

When the CPU contracts are proven, GPU can hold active symbolic fields.

GPU does not mean neural net training.

GPU means:

```text
verified symbolic binaries resident in high-throughput memory
sparse relation fields
cloud activation matrices
candidate score fields
batched path exploration
```

Corrected law:

```text
CPU builds and verifies.
GPU holds active symbolic fields.
AnchorWorks gates authority.
```

GPU may become the runtime substrate for active symbolic thought only when it holds verified AnchorWorks binary structures.

## Forbidden Behavior

```text
Do not load the whole brain for one answer.
Do not let one top-k choice decide alone.
Do not render evidence labels as speech.
Do not let clouds prove truth.
Do not let GPU invent.
Do not mutate Canonical from cloud activation.
Do not write lifetime memory from answer rendering.
```

## Law Set

```text
Clouds propose territory.
AnswerField limits surface area.
Top-k proposes anchors.
AnswerPath decides sequence.
Evidence constrains claims.
Renderer speaks path.
```
