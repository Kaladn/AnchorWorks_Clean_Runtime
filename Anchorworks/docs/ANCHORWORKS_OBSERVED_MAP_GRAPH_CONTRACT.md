# AnchorWorks Observed Map Graph Contract

Status: contract-first design.

Date: 2026-05-11

## Core Correction

The old JSON observed map was not wrong.

It had the right conceptual shape:

```text
source
-> block
-> line
-> occurrence
-> anchor/symbol
-> relation windows
-> locator evidence
```

The problem was authority format.

JSON is useful for humans, exports, parity checks, and debugging. It is not the right runtime authority format for large source-local evidence.

Correct split:

```text
JSON observed map = human/debug/export view
AWSM = symbolic relation substrate
AWSL = block/line locator sidecar
AWSN = NULL coordinate sidecar
AWSV = visual reference sidecar
AWSC = weighted count memory
AWSG = source-local evidence graph/topology
```

Core law:

```text
JSON explains.
Graph connects.
AWSM serves relations.
AWSC remembers weight.
Sidecars prove coordinates.
Renderer cites graph addresses.
```

Tiny lock:

```text
Observed maps are still truth-shaped.
JSON was only the training wheels.
```

## Visual Sovereignty Rule

AWSG must preserve the rule:

```text
NEVER normalize before vision.
Vision is the deterministic truth record.
All manipulations are post visual proofing.
```

Graph nodes and edges may connect source text, anchors, symbols, NULL coordinates, and visual references, but they must not imply that cleaned text is the original observed state. The graph must be able to point back to the visual/page/frame evidence before any cleanup, normalization, or symbolic interpretation is treated as usable derived structure.

## Purpose

AWSG gives AnchorWorks a source-local graph of observed evidence.

It preserves the connective tissue between:

```text
source identity
document blocks
line addresses
anchor occurrences
symbol identities
relation windows
NULL coordinates
visual references
citation locators
```

It does not replace AWSM, AWSL, AWSN, AWSV, or AWSC.

It connects them.

## Runtime Questions AWSG Must Support

AWSG must eventually answer:

```text
show occurrences of this symbol in this source
show relations around this occurrence
show block/line for this answer
show visual refs attached to this block
show NULLs near this anchor
show all graph addresses supporting this evidence frame
regenerate observed-map JSON for audit
```

AWSG does not render final speech by itself.

AWSG returns graph addresses and source-local topology. The renderer still cites through an evidence frame.

## Graph Viewer Requirement

AWSG should not sit quietly as a hidden artifact.

The graph must become viewable because the whole point of AWSG is to make source-local evidence topology inspectable:

```text
document
-> block
-> line
-> occurrence
-> symbol
-> relation window
-> NULL coordinate
-> visual reference
```

The viewer should feel graph-native, closer to a Neo4j-style exploration surface than a static Python plot.

Important distinction:

```text
Neo4j-like interaction model: yes.
Neo4j as required runtime authority: no, not yet.
```

Python graphing is acceptable for proof exports and tiny debug images. It is not the right primary viewer for AnchorWorks evidence graphs.

Core viewer law:

```text
Graph connects.
Viewer inspects.
Backend permits.
Nothing mutates from view.
```

## Viewer Modes

The AWSG viewer should support these read-only modes:

```text
source overview
block/line path
occurrence neighborhood
symbol neighborhood
relation-window inspection
NULL coordinate overlay
visual reference overlay
evidence-frame citation path
```

Minimum useful viewer flow:

```text
open graph
-> select document node
-> expand block
-> expand line
-> inspect occurrence
-> follow symbol
-> inspect relation windows
-> show locator/citation address
```

The first production viewer should not try to load the whole source graph into the browser.

It should load capped graph slices:

```text
selected node
radius
node-type filters
edge-type filters
result cap
```

This keeps the surface usable when a source graph becomes large.

## Viewer Controls

Minimum controls:

```text
graph selector
node type filters
edge type filters
radius control
expand selected node
collapse selected node
show source locator
show resolved anchor/symbol
show relation details
show NULL coordinates
show visual refs
export debug JSON view
copy citation address
```

The viewer should include an inspector panel for the selected node or edge.

Inspector fields should be source-local and explicit:

```text
node_id
node_type
source_id
block_id
line_start
line_end
anchor_position
surface
resolved_anchor
symbol
lane
reason
visual_record_id
edge_type
offset
count
source sidecar
```

## Viewer API Contract

The app should eventually expose read-only graph routes.

Suggested route shape:

```text
GET /api/awsg/graphs
GET /api/awsg/graph/{graph_name}
GET /api/awsg/graph/{graph_name}/node/{node_id}
GET /api/awsg/graph/{graph_name}/slice?node_id=...&radius=1&limit=500
GET /api/awsg/graph/{graph_name}/export/observed-map-debug
```

Route responsibilities:

```text
/graphs
  list available graph manifests

/graph/{graph_name}
  return manifest and summary counts

/node/{node_id}
  return one node plus direct metadata

/slice
  return a bounded node/edge subgraph for interactive viewing

/export/observed-map-debug
  regenerate or return the human/debug export
```

All viewer routes are read-only.

Forbidden viewer writes:

```text
Canonical
lexicon
lifetime counts
AWSC
AWSM
AWSL
AWSN
AWSV
source files
```

## Rendering Guidance

Use a browser-native graph renderer for the real viewer.

The viewer should be able to handle many nodes by using canvas or WebGL-style rendering, slice loading, and filters.

Do not make Python plotting the main interface.

Allowed uses for Python graph output:

```text
toy proof images
test snapshots
debug exports
static report diagrams
```

Main interface target:

```text
AnchorWorks UI
-> Source Graphs panel
-> interactive graph canvas
-> selected-node inspector
-> citation/address panel
```

## Neo4j Position

Neo4j is useful as a mental model and optional export target.

It should not be required for the first AnchorWorks AWSG viewer.

Use Neo4j-like concepts:

```text
nodes
edges
labels
properties
neighborhood expansion
graph queries
inspector panel
```

Avoid requiring Neo4j until AnchorWorks has proven:

```text
AWSG slice API
source graph manifests
debug export regeneration
renderer citation path
production graph placement
```

Optional future bridge:

```text
AWSG -> Cypher export
AWSG -> Neo4j import
Neo4j -> exploratory analysis only
```

Neo4j must not become the source of authority unless explicitly promoted by a later storage contract.

## Viewer Proof Target

Next proof target after the graph contract:

```text
read toy AWSG runtime graph
serve bounded graph slice
render source graph in browser UI
inspect selected node/edge
show locator path
regenerate debug JSON view
prove no production writes
```

First acceptable viewer proof:

```text
one toy graph
document/block/line/occurrence/symbol nodes visible
relation_window edges visible
NULL and visual nodes visible when present
selected-node inspector works
slice cap enforced
no write routes
tests prove isolation
```

Production viewer gate:

```text
one real document graph can be viewed
large graphs are sliced, not fully loaded
viewer can copy citation addresses
viewer can show sidecar provenance
viewer never writes authority data
```

## File Family

Proposed local graph family:

```text
*.awsg
*.graph_manifest.json
```

Where:

```text
AWSG = AnchorWorks Source Graph
```

Initial placement for experiments:

```text
experiments/observed_map_graph/runtime/
```

Candidate production placement after proof:

```text
D:\AnchorMaps\source_graphs
```

Do not place AWSG in production beside AWSM until toy and one-map proofs pass.

## Graph Identity

Every graph belongs to one source-local map bundle.

Minimum manifest:

```json
{
  "schema_version": "anchorworks_awsg_manifest@1",
  "graph_name": "source-name-digest.awsg",
  "source_id": "source_digest_or_stable_id",
  "source_path": "D:\\source\\file.cnxml",
  "source_hash": "sha256...",
  "awsm_path": "D:\\AnchorMaps\\symbolic_maps\\source.awsm",
  "awsl_path": "D:\\AnchorMaps\\symbolic_maps\\source.locators.awsl",
  "awsn_path": "D:\\AnchorMaps\\symbolic_maps\\source.nulls.awsn",
  "awsv_path": "D:\\AnchorMaps\\symbolic_maps\\source.visuals.awsv",
  "node_count": 0,
  "edge_count": 0,
  "writes_allowed": {
    "canonical": false,
    "counts": false,
    "lifetime": false,
    "lexicon": false
  }
}
```

## Node Types

### document

Represents the source document.

```json
{
  "node_type": "document",
  "node_id": "doc:source_id",
  "source_id": "source_id",
  "source_path": "...",
  "source_hash": "sha256..."
}
```

### block

Represents a source-local block.

```json
{
  "node_type": "block",
  "node_id": "block:source_id:67",
  "source_id": "source_id",
  "block_id": 67,
  "block_ordinal": 67
}
```

### line

Represents a line range inside a block.

```json
{
  "node_type": "line",
  "node_id": "line:source_id:67:12",
  "source_id": "source_id",
  "block_id": 67,
  "line_start": 12,
  "line_end": 12
}
```

### occurrence

Represents one observed anchor position.

```json
{
  "node_type": "occurrence",
  "node_id": "occ:source_id:67:12:7",
  "source_id": "source_id",
  "block_id": 67,
  "line_start": 12,
  "anchor_position": 7,
  "surface": "photosynthesis",
  "resolved_anchor": "photosynthesis",
  "symbol": "0x0000000001",
  "lane": 0
}
```

### symbol

Represents a 5-byte symbol identity seen in this source graph.

```json
{
  "node_type": "symbol",
  "node_id": "symbol:0x0000000001",
  "symbol": "0x0000000001",
  "lane": 0,
  "display_anchor": "photosynthesis"
}
```

### null_coordinate

Represents a parseable exclusion from AWSN.

```json
{
  "node_type": "null_coordinate",
  "node_id": "null:source_id:67:12:7",
  "source_id": "source_id",
  "block_id": 67,
  "line_start": 12,
  "anchor_position": 7,
  "surface": "dirty_surface",
  "resolved_anchor": "__NULL__",
  "reason": "junk_or_artifact"
}
```

### visual_ref

Represents a source-local visual pointer from AWSV.

```json
{
  "node_type": "visual_ref",
  "node_id": "visual:source_id:vis_abc123",
  "source_id": "source_id",
  "visual_record_id": "vis_abc123",
  "kind": "figure",
  "source_path_ref": "figures/example.png",
  "recognition_status": "not_run"
}
```

## Edge Types

### contains_block

```text
document -> block
```

### contains_line

```text
block -> line
```

### contains_occurrence

```text
line -> occurrence
```

### resolves_to_symbol

```text
occurrence -> symbol
```

### relation_window

Represents a source-local relation from one occurrence/symbol neighborhood.

```json
{
  "edge_type": "relation_window",
  "from": "occ:source_id:67:12:7",
  "to": "symbol:0x0000000002",
  "offset": 2,
  "count": 1,
  "source": "AWSM"
}
```

### has_null

```text
line/block -> null_coordinate
```

### has_visual_ref

```text
block/line -> visual_ref
```

### citation_locator

Connects evidence frames back to source-local graph addresses.

```json
{
  "edge_type": "citation_locator",
  "from": "evidence_frame:frame_id",
  "to": "block:source_id:67",
  "coord": "source:block67:L12-L45"
}
```

Citation edges may be generated later; they are not required for the first graph writer.

## Binary Versus JSON

AWSG should become binary or graph-native after the contract is proven.

For the first proof, the graph may use a simple JSONL node/edge export inside the experiment sandbox:

```text
nodes.jsonl
edges.jsonl
graph_manifest.json
```

This is allowed because the first proof tests graph shape, not runtime speed.

Production path must not make large JSON graph files the hot authority format.

Law:

```text
JSON graph proof is allowed.
JSON graph runtime is not the goal.
```

## Build Inputs

First graph writer input:

```text
one AWSM bundle:
  AWSM relations
  AWSL locators
  AWSN NULL coordinates
  AWSV visual refs
```

Optional debug input:

```text
JSON observed map
```

The writer may use JSON observed map for parity comparison only, not as the required source of truth.

## Export Requirement

AWSG must eventually regenerate a debug observed-map export.

Export target:

```text
observed-map-debug-export.json
```

The export does not need to be byte-for-byte identical to the legacy JSON map.

It must preserve:

```text
source identity
block ids
line locators
occurrence addresses
resolved anchors
symbols
relation windows
NULL coordinates
visual refs
```

## First Proof

Contract-first implementation target:

```text
experiments/observed_map_graph/
  run.py
  runtime/
    input/
    graph/
    exports/
    reports/
```

Commands:

```powershell
python experiments\observed_map_graph\run.py build
python experiments\observed_map_graph\run.py eval
```

Build should:

```text
create one toy source
write AWSM/AWSL/AWSN/AWSV
build graph nodes/edges from the bundle
write graph_manifest.json
write observed-map-debug-export.json
```

Eval should prove:

```text
0 schema errors
document node exists
block nodes exist
line nodes exist
occurrence nodes exist
symbol nodes exist
relation_window edges exist
NULL coordinate nodes exist when NULLs exist
visual_ref nodes exist when visual refs exist
debug export includes source/block/line/occurrence/symbol/relation shape
no production writes
```

## Production Gate

Do not place AWSG beside AWSM until the proof can show:

```text
graph survives without JSON observed map
debug JSON export can be regenerated from graph/binary shape
source-local evidence addresses are stable
renderer can cite graph addresses
```

## Hard Boundaries

```text
AWSG does not mutate Canonical.
AWSG does not write lifetime counts.
AWSG does not replace AWSM.
AWSG does not replace AWSC.
AWSG does not make visual evidence true.
AWSG does not render speech directly.
AWSG gives topology and addresses.
```

Final law:

```text
Observed-map meaning survives.
JSON becomes export.
Graph becomes topology.
Binary remains substrate.
Evidence frames decide speech.
```
