# Toy Evidence Renderer V2 Plan

Status: approved next experiment plan.

Date: 2026-05-11

Checkpoint `d3c3a6b` proved the first toy path:

```text
toy QA rows
-> toy source docs
-> anchors
-> 5-byte symbols
-> AWSM/AWSS/AWSC
-> evidence frames
-> paired JSONL datasets
-> dependency-free eval
```

V1 also proved isolation:

```text
No writes to D:\AnchorWorks_Clean_Runtime\State
No writes to D:\AnchorMaps
No writes to Canonical
No writes to Spare_Slots
No writes to Structural
```

V2 exists because V1 was intentionally too easy. It reached `1.0` exact-match with a deterministic renderer because the answer text was directly available through the simple evidence frame. V2 must make the toy hard enough to test evidence selection rather than fixture echo.

Core law:

```text
The model does not learn facts.
The model learns how to render permitted evidence.
```

## Commands

Keep the same runner and sandbox.

V1 remains the default:

```powershell
python experiments\toy_evidence_renderer\run.py build
python experiments\toy_evidence_renderer\run.py eval
python experiments\toy_evidence_renderer\run.py train
```

Add V2 difficulty:

```powershell
python experiments\toy_evidence_renderer\run.py build --difficulty v2
python experiments\toy_evidence_renderer\run.py eval --difficulty v2
python experiments\toy_evidence_renderer\run.py train --difficulty v2
python experiments\toy_evidence_renderer\run.py all --difficulty v2
```

Correct path:

```text
experiments\toy_evidence_renderer\run.py
```

Do not use the typo path:

```text
experiments\totoy_evidence_renderer\run.py
```

## Sandbox

All V2 runtime output stays under:

```text
experiments/toy_evidence_renderer/runtime/
  corpus/
  maps/
  awss/
  awsm/
  awsc/
  frames/
  datasets/
  reports/
```

Runtime remains ignored by git.

## V2 Fixture Size

Create a deterministic V2 fixture of `30` rows:

```text
18 supported rows
6 unsupported rows
6 distractor-heavy supported rows
```

Each supported row uses a small multi-sentence toy source document:

```text
one relevant evidence sentence
one same-topic distractor sentence
one unrelated distractor sentence
```

Unsupported rows must contain no permitted answer path:

```text
answer_symbols: []
evidence_used: []
render_allowed: false
```

Unsupported target text:

```text
I do not have evidence for that in this toy dataset.
```

## Frame Separation

V2 separates model input from gold target.

Hard rule:

```text
Input frame must not contain target_text.
Input frame must not expose answer text as an easy echo path.
Gold text lives only in dataset target fields and eval fixtures.
```

Dataset row shape:

```json
{
  "schema_version": "toy_symbol_frame_to_text@2",
  "input_frame": {},
  "target_text": "The selected permitted answer."
}
```

Structured row shape:

```json
{
  "schema_version": "toy_symbol_frame_to_structured@2",
  "input_frame": {},
  "target": {
    "answer_symbols": [],
    "evidence_used": [],
    "render_allowed": true,
    "text": "The selected permitted answer."
  }
}
```

## Candidate Evidence

Add explicit candidate evidence rows to each frame.

Shape:

```json
{
  "candidate_id": "qa_001_c1",
  "symbols": ["0x0000000001"],
  "locator": {
    "block_id": "block_1",
    "line_start": 1,
    "line_end": 1
  },
  "count_score": 3,
  "selected": true
}
```

Supported rows:

```text
At least one candidate has selected = true in deterministic eval frame.
At least one wrong candidate exists for distractor rows.
```

Unsupported rows:

```text
No selected evidence.
No answer symbols.
No evidence_used.
render_allowed = false.
```

## Strict Input Variant

V2 writes two frame views:

```text
deterministic_eval_frame
strict_model_input_frame
```

The deterministic eval frame may include:

```text
candidate_evidence[].selected
```

The strict model input frame must remove:

```text
target_text
answer text
evidence_used text
candidate_evidence[].selected
```

It may keep:

```text
query_symbols
candidate evidence symbols
candidate locators
count_score
frame_health
```

This lets eval prove frame correctness now while reserving a harder future learned-renderer test.

## Frame Health

Every row includes:

```json
{
  "frame_health": {
    "has_query_symbols": true,
    "has_evidence_symbols": true,
    "has_count_context": true,
    "citation_required": false,
    "render_allowed": true
  }
}
```

Unsupported rows set:

```json
{
  "has_evidence_symbols": false,
  "render_allowed": false
}
```

## Reports

Continue writing:

```text
experiment_manifest.json
build_report.json
eval_report.json
```

Add V2 fields:

```text
difficulty
candidate_evidence_rows
distractor_rows
target_leak_errors
selected_evidence_errors
unsupported_answer_leaks
strict_input_rows
deterministic_eval_rows
```

Evaluation must report:

```text
schema_errors
awsc_verify_errors
unsupported_answer_leaks
target_leak_errors
selected_evidence_errors
evidence_preservation_errors
exact_match_score
refusal_accuracy
```

## Dependency Rules

`build` must pass without:

```text
Hugging Face
PyTorch
ML dependencies
external model files
```

`eval` must pass without:

```text
Hugging Face
PyTorch
ML dependencies
external model files
```

`train` may skip cleanly until a local tiny renderer model is explicitly configured.

Training must not use production data.

## Hardware Direction

The current V2 build/eval path is CPU-only.

Future renderer experiments should target a discrete GPU after the CPU path proves the data contract.

Recommended future GPU target:

```text
Intel Arc Pro B70
```

Why it fits the direction:

```text
32 GB GDDR6
256-bit memory interface
608 GB/s memory bandwidth
367 peak INT8 TOPS
256 XMX AI engines
OpenVINO support
oneAPI support
Intel Extension for PyTorch support
ECC support
```

AnchorWorks GPU law:

```text
GPU accelerates verified symbolic fields.
GPU does not invent authority.
GPU does not replace evidence gates.
```

## NPU Position

Activating the possible NPU is optional.

Use it only as a later side experiment for:

```text
small ONNX renderer inference
Windows ML proof
OpenVINO proof
low-power local inference
```

Do not make NPU the primary path for V2.

Reason:

```text
V2 is proving frame shape, evidence selection, and refusal discipline.
The NPU does not help until there is an ONNX-shaped renderer to run.
The discrete GPU is the better future target for high-throughput symbolic scoring and renderer experiments.
```

NPU law:

```text
Enable NPU support only after the CPU contract is stable.
Treat NPU as an inference backend, not the authoritative substrate.
```

## Acceptance

First V2 checkpoint:

```powershell
python experiments\toy_evidence_renderer\run.py build --difficulty v2
python experiments\toy_evidence_renderer\run.py eval --difficulty v2
python -m unittest discover -s tests
```

Expected:

```text
0 schema errors
0 AWSC verify errors
0 unsupported-answer leaks
0 target_leak_errors
0 selected_evidence_errors
paired JSONL files written
build_report.json written
eval_report.json written
```

## Do Not Do

```text
Do not train on OpenStax.
Do not train on ARC/COD sidecar telemetry.
Do not write production State.
Do not write D:\AnchorMaps.
Do not touch Canonical.
Do not touch Spare_Slots.
Do not touch Structural.
Do not let strict input carry target text.
Do not treat deterministic exact-match as model intelligence.
```

## Next Implementation Step

Implement `--difficulty v2` in:

```text
experiments\toy_evidence_renderer\run.py
```

Then extend:

```text
tests\test_toy_evidence_renderer.py
```

with V2 assertions:

```text
runtime isolation still holds
input frames do not contain target_text
unsupported rows cannot contain answer symbols
distractor rows contain at least one wrong candidate
paired JSONL files are written
reports include V2 metrics
```
