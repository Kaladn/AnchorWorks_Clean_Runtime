# AW Inference Kernel Sample Set Round 1 Plan

Status: plan only. Do not build samples, write runtime code, or wire evaluation until this plan is approved.

## Goal

Create a first 50-row evaluation/training sample set for the AW Inference Kernel. The sample set teaches and tests lawful admission, rejection, planning, and speech. It must not become Q&A memory or fact authority.

Core flow:

```text
question
-> context/symbol chain
-> frame
-> candidate evidence
-> admitted/rejected candidates
-> answer plan
-> rendered answer
```

Kernel law:

```text
Search finds.
Counts weigh.
Inference admits.
Renderer speaks.
```

Dataset law:

```text
The sample set does not teach facts.
It teaches lawful admission, rejection, planning, and speech.
```

## Source Clues

### NLP Math Comparison PDF

Use:

- deterministic role verification
- context/position/relationship checks
- contrast between probability-only classification and structured verification

Do not use:

- claims of universal certainty
- claims that are not proven by current AnchorWorks contracts
- language implying the current kernel owns truth

### `contextual_reasoning_engine.py`

Use the structure:

```text
input text
-> contextual symbol chain
-> semantic fields
-> spatial/context signature
-> recommended strategy
-> reasoning result
-> confidence
-> trace/history
```

Translate to AnchorWorks:

```text
question anchors
-> query cloud
-> frame type
-> strategy
-> accepted candidates
-> rejected candidates
-> answer plan
```

Do not import:

- AGI claims
- zero-hallucination claims
- “true intelligence” marketing language
- hard certainty claims not backed by source/count/trace

## Round 1 Size

Total rows: 50

```text
10 formula
10 definition
10 why/causal
5 process
5 comparison
5 entity/who
5 unsupported/distractor
```

## Row Contract

Each row must be a JSON object with these fields:

```json
{
  "id": "formula_001",
  "category": "formula",
  "question": "",
  "mode": "auto",
  "expected_activity": "",
  "expected_frame": "",
  "query_anchors": [],
  "recognized_anchors": [],
  "missing_anchors": [],
  "context_chain": {
    "semantic_fields": [],
    "context_signature": "",
    "recommended_strategy": "",
    "notes": ""
  },
  "required_slots": [],
  "candidate_evidence": [],
  "expected_answer_plan": {},
  "target_answer": "",
  "forbidden_answer_terms": [],
  "scoring": {},
  "fact_authority": false,
  "notes": ""
}
```

## Candidate Evidence Contract

Each candidate row must identify what should happen and why:

```json
{
  "candidate": "F = ma",
  "lane": "formula_rule",
  "expected_status": "accepted",
  "reason": "mass_acceleration_force_frame",
  "support": {
    "source_ref": "",
    "count_ref": "",
    "formula_ref": "newton_second_law"
  }
}
```

Rejected candidates are mandatory for most rows. They teach the kernel what must not speak.

Examples of rejection reasons:

```text
off_frame_domain
shared_units_wrong_relation
adjacent_but_wrong_formula_slot
query_field_mismatch
anomalous_future_shape
missing_required_slot
unsupported_by_source
count_high_but_wrong_frame
verbatim_source_copy
```

## Category Designs

### 1. Formula

Purpose: prove formula questions enter formula lane before documents/counts.

Sample shape:

```text
numeric values + units + solve-for phrase
-> formula_solve
-> accepted formula/given/result
-> reject shared-unit wrong-domain evidence
```

Required examples:

- Newton second law: `F = ma`
- speed/distance/time
- density/mass/volume
- simple Ohm law if source support exists
- unit conversion with explicit values

Hard rule:

```text
Units alone cannot choose documents.
A formula question enters formula lane before evidence lane.
```

### 2. Definition

Purpose: define a concept without raw top-K word salad.

Sample shape:

```text
what is X
-> definition frame
-> category + defining property slots
-> source/count supported answer
```

Required examples:

- inertia
- acceleration
- force
- energy
- symbol
- anchor
- context cloud

Hard rule:

```text
Definition requires category and defining property, not only neighbors.
```

### 3. Why/Causal

Purpose: answer reason questions with purpose/mechanism/consequence.

Sample shape:

```text
why X
-> causal_explanation
-> purpose + mechanism + consequence
-> reject unrelated high-count terms
```

Required examples:

- why worry about laws of physics
- why does inertia matter
- why use source citations
- why count anchors
- why reject unsupported candidates

Hard rule:

```text
Causal answers require at least one mechanism or consequence slot.
```

### 4. Process

Purpose: answer how questions with ordered steps or mechanism.

Sample shape:

```text
how X works
-> process_explanation
-> steps/mechanism
-> no unordered candidate pile
```

Required examples:

- how does acceleration relate to force
- how does AnchorWorks ingest a document
- how does a count walk choose candidates
- how does lexicon recognition happen
- how does source evidence constrain speech

Hard rule:

```text
Process answers must preserve order.
```

### 5. Comparison

Purpose: compare two things with a named basis.

Sample shape:

```text
compare X and Y
-> comparison
-> left + right + basis
-> answer must not collapse one side
```

Required examples:

- force vs energy
- counts vs documents
- lexicon vs phrase authority
- source evidence vs count evidence
- document maps vs overlays

Hard rule:

```text
Comparison answers need both sides and a basis.
```

### 6. Entity/Who

Purpose: avoid partial-entity and misspelled-name drift.

Sample shape:

```text
who is X
-> who_entity
-> verify entity parts
-> reject partial missing entity
```

Required examples:

- who is Isaac Newton
- who is Issac Newton
- who is Lee Mercey
- who is AnchorWorks
- who is ClearBoxAI

Hard rule:

```text
Partial missing entity names block count walking.
```

### 7. Unsupported/Distractor

Purpose: test refusal and rejection discipline.

Sample shape:

```text
question resembles known domain
-> candidates exist
-> no lawful answer path
-> clean insufficiency response
```

Required examples:

- physics prompt with NMR/caption distractor
- system prompt with unrelated chat history match
- document question with no source support
- count question with only glue/query terms
- formula question missing one numeric value

Hard rule:

```text
No candidate speaks until it belongs.
```

## Scoring Contract

Score trace, not just final text.

Fields:

```json
{
  "activity_correct": true,
  "frame_correct": true,
  "required_slots_filled": true,
  "accepted_required_candidates": true,
  "rejected_bad_candidates": true,
  "forbidden_terms_absent": true,
  "answer_value_correct": true,
  "render_allowed_correct": true,
  "no_verbatim_copy": true
}
```

Pass rule:

```text
activity_correct must pass
frame_correct must pass
rejected_bad_candidates must pass
render_allowed_correct must pass
answer_value_correct must pass when a numeric/formula row exists
forbidden_terms_absent must pass
```

## Storage Plan

Proposed location:

```text
D:\AnchorWorks_Clean_Runtime\test\test data\inference_kernel_samples\round1\
  inference_kernel_round1.jsonl
  reports\
    round1_eval_report.json
```

Reason:

```text
All testing files, code, and data stay outside the repo source tree under test/test data.
```

No production writes.
No count writes.
No lexicon writes.
No V2 work.

## Build Procedure

1. Create the folder above.
2. Write 50 rows by category.
3. Include real bad outputs as distractor candidates where available.
4. Add expected admission/rejection reasons.
5. Add target answers that are clean but not source-verbatim.
6. Add forbidden terms for known leakage.
7. Create evaluator that reads the JSONL and calls the kernel.
8. Produce an eval report with pass/fail by scoring field.

## Round 1 Acceptance

```text
50 rows exist
all rows validate schema
formula rows route before documents/counts
definition rows do not render raw top-K
why rows reject off-domain terms
comparison rows preserve both sides
entity rows block partial missing names
unsupported rows refuse cleanly
eval report written
no production data changed
full unit tests still pass
```

## Hold Point

Stop here until approved.

Next action after approval:

```text
Build the Round 1 sample JSONL and evaluator under test/test data only.
```
