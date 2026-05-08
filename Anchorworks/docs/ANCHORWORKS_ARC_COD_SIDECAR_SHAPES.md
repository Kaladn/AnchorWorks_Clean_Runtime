# AnchorWorks ARC And COD Sidecar Shape Contract

Status: planning contract / sidecar extraction blueprint

Date: 2026-05-06

Source systems:

```text
G:\arc_production_solver
G:\arc_production_solver\cod_616
```

Scope:

```text
Extract reusable shapes, algorithms, rails, and sidecar contracts.
Do not import old repo structure.
Do not ingest old observed data.
Do not make either backend a truth owner.
```

## Purpose

AnchorWorks has two valuable older reasoning systems that should become sidecar references later:

```text
ARC backend = symbolic task solving, worker composition, few-shot shape learning
COD backend = multimodal signal fusion, baseline deviation, recognition-field verdicts
```

Both systems are messy as repositories.
Both systems contain valuable machinery.
The correct move is not to copy them into AnchorWorks.
The correct move is to preserve their algorithms as sidecar shapes and rebuild only the useful interfaces under AnchorWorks contracts.

Tiny law:

```text
Old engines may advise.
AnchorWorks decides.
Promotion stays gated.
Truth stays outside sidecars.
```

## Non-Goals

This document is not permission to import:

```text
ARC datasets
COD telemetry captures
Kaggle paths
YOLO model weights
old virtual environments
old debug scripts
old CLI wrappers
old generated result folders
old repo layout
old data files
```

This document is not permission to let sidecars:

```text
write maps
write counts
write lifetime memory
write chat memory
promote lexicon entries
change routing by themselves
claim source truth
train on private docs
become agent brains
```

## Shared Sidecar Law

Both ARC and COD sidecars must obey the same AnchorWorks boundary:

```text
Sidecar reads an input packet.
Sidecar returns a structured report.
Sidecar may include confidence and evidence about its own computation.
Sidecar does not mutate AnchorWorks state.
Sidecar does not promote truth.
Sidecar does not write memory.
```

Minimum sidecar response shape:

```json
{
  "sidecar_id": "arc_shape|cod_recognition",
  "sidecar_version": "local-dev",
  "operation_id": "op_...",
  "input_hash": "sha256:...",
  "output_hash": "sha256:...",
  "route": "shape_analysis|recognition_analysis|worker_prior|composition_probe",
  "write_intent": "none",
  "evidence_lane": "sidecar_computation",
  "result": {},
  "trace": [],
  "limits": {
    "max_runtime_ms": 0,
    "max_workers": 0,
    "max_chain_length": 0,
    "allow_state_write": false
  },
  "provenance": {
    "created_at": "...",
    "source_system": "arc|cod",
    "source_contract": "ANCHORWORKS_ARC_COD_SIDECAR_SHAPES@1",
    "anchorworks_branch": "..."
  }
}
```

## Two Backend Model

AnchorWorks should treat ARC and COD as two distinct backend families.

### Backend 1: ARC Shape Backend

Purpose:

```text
Few-shot symbolic pattern learning.
Worker selection.
Worker composition.
Rule hypothesis validation.
Shape extraction from examples.
```

ARC is the backend for:

```text
What shape is this task?
Which worker is likely useful?
Which worker chain is worth trying?
Which candidate rule survived validation?
Which near-miss contains reusable structure?
```

ARC should not answer user questions directly.
ARC should not read user documents unless a future operator explicitly converts a bounded AnchorWorks task into a safe symbolic sidecar packet.

### Backend 2: COD Recognition Backend

Purpose:

```text
Signal fusion.
Baseline building.
Deviation scoring.
Channel scoring.
Verdict generation.
```

COD is the backend for:

```text
What changed from normal behavior?
Which channel is drifting?
What dimensions caused the score?
How confident is the deviation report?
```

COD should not become an anti-cheat module inside AnchorWorks.
The reusable shape is baseline-vs-observed recognition, not COD game telemetry.

## Why These Backends Matter To AnchorWorks

AnchorWorks already has symbolic machinery:

```text
anchors
symbols
counts
maps
frames
gates
traces
chat memory
side branches
flat documents
```

The missing future layer is not more generic LLM reasoning.
The missing future layer is controlled pattern learning and recognition over AnchorWorks traces.

ARC contributes:

```text
observe examples -> extract metadata -> fuse invariant pattern -> propose rule -> validate -> accept/reject
```

COD contributes:

```text
collect runtime signals -> build fingerprint -> compare baseline -> score channels -> report health
```

Together they imply:

```text
AnchorWorks can learn shape candidates like ARC.
AnchorWorks can monitor drift and health like COD.
AnchorWorks can let agents call those sidecars without giving them write authority.
```

## ARC Backend: Raw Algorithm Shapes

### ARC Core Rail

The ARC rail is:

```text
task examples
-> feature extraction
-> worker/operator hypotheses
-> validation against all examples
-> apply to test input
-> trace winning worker or failure
```

The strict law is:

```text
100 percent training validation or rejection.
```

Raw operator contract:

```python
class ArcOperator:
    name: str

    def analyze(self, input_grid, output_grid):
        """Return params if this pattern fits, else None."""

    def apply(self, input_grid, params):
        """Apply deterministic transform to one input."""
```

Raw validation algorithm:

```python
def validate_operator(operator, train_pairs):
    for input_grid, expected_output in train_pairs:
        params = operator.analyze(input_grid, expected_output)
        if params is None:
            return False

        result = operator.apply(input_grid, params)
        if result is None:
            return False

        if result != expected_output:
            return False

    return True
```

AnchorWorks translation:

```text
worker analyzes current symbolic task
worker proposes params/shape
worker must pass all fixture/training traces
worker may return a candidate route or shape
worker may not write production truth
```

### ARC Layered Architecture

Observed ARC layers:

```text
Layer 0: baseline single operators
Layer 1: composition solver / meta-comp engine
Layer 2: ARC-CORE specialist engines
Layer 3: Euclidean/ObjectSpace experiments
```

Functional execution order:

```text
1. Try proven baseline worker.
2. If baseline fails, try specialist engines.
3. If single engine fails, try bounded composition.
4. If bounded composition fails, preserve trace as near miss.
```

AnchorWorks translation:

```text
1. Use boring route/classifier gates.
2. Use single known worker if eligible.
3. Use known short worker chains if eligible.
4. Use shape learner only as candidate generator.
5. Stop before unbounded search.
```

### ARC Specialist Engine Shape

ARC-CORE had specialist engines grouped by role:

```text
GEO: rotate, flip, scale, translate
COLOR: mapping, recolor, structural color change
COMP: crop, extract, component transforms
PATTERN: tile, symmetry, periodic structure
SHAPE: outline, fill, skeleton
COUNT: frequency, repetition
REL: align, distribute, mirror, relationships
META: composition orchestration
```

AnchorWorks equivalent engine classes:

```text
ROUTE: classify mode/lane/tool/help/evidence request
FRAME: classify pre-answer symbolic frame
ROLE: classify anchor roles within a frame
EVIDENCE: classify evidence lane and support eligibility
COUNT: rank count-neighbor candidates
DOC: rank source-local passages
TRACE: classify answer health and drift
META: compose bounded worker chains
```

### ARC Object Metadata Algorithm

ARC ObjectSpace treats each shape as a structured entity rather than raw pixels.

Raw object schema:

```text
object_id
color
mask
bbox
centroid
radius
pixel_count
perimeter
shape_signature
sector
```

Raw object detection algorithm:

```text
for each pixel in grid:
  if pixel is background or visited:
    continue

  run 8-connected BFS over same-color neighbors
  collect component pixels
  build exact boolean mask
  compute bbox from min/max y/x
  compute centroid as mean pixel coordinate
  compute radius as max distance from centroid
  compute perimeter from exposed 4-neighbor edges
  compute shape_signature from cropped mask bytes
  assign object_id
```

AnchorWorks translation:

```text
for each anchor/symbol unit in input:
  preserve surface position
  preserve symbol id
  preserve lane/source
  classify role candidate
  classify relation candidates
  compute local context window
  compute source/evidence eligibility
  compute shape signature for repeated phrase/frame pattern
```

The object lesson:

```text
Do not treat tokens as flat words.
Treat them as entities with position, role, relation, and reusable shape.
```

### ARC Six-Channel Sensory Organ

ARC converts a grid into six structured channels.

Raw ARC channels:

```text
C0: color_normalized
C1: component_ids
C2: symmetry_score_map
C3: repetition_score_map / tiling groups
C4: shape_signature_map / border-interior role
C5: delta_map
```

Raw channel algorithm:

```text
normalize colors to bounded values
compute connected components
compute symmetry participation
compute repetition/tiling participation
compute shape/border role
compute input-output delta when output is available
```

AnchorWorks symbolic channel proposal:

```text
C0: symbol identity / anchor id
C1: lexical role / structural role
C2: source position / block-line / chat position
C3: local repetition / count-neighbor support
C4: frame role / relation role
C5: delta from expected route or prior context
```

For code symbolic representation:

```text
C0: token/glyph identity
C1: language-local syntax role
C2: AST/block/function/class position
C3: repetition/import/reference participation
C4: scope/boundary role
C5: diff/delta from prior version or expected pattern
```

### ARC Resonance State Algorithm

ARC compresses six channels into a 20-dimensional symbolic/resonance state.

Raw ARC v2 resonance dimensions:

```text
D0: foreground_mass_ratio
D1: object_count_normalized
D2: component_size_variance
D3: fill_compactness
D4: largest_component_dominance
D5: color_entropy_normalized
D6: border_fraction
D7: background_dominance
D8: vertical_symmetry_strength
D9: horizontal_symmetry_strength
D10: rotational_symmetry_strength
D11: tiling_strength
D12: row_col_alignment_score
D13: stripe_pattern_strength
D14: object_spacing_regularity
D15: aspect_ratio_trend
D16: change_localization
D17: color_change_concentration
D18: scale_change_indicator
D19: object_count_delta
```

Raw algorithm:

```text
extract metadata for input grid
extract metadata for output grid if available
compute global mass and object count
compute object size variance and compactness
compute dominance and entropy
compute symmetry and tiling metrics
compute layout alignment and spacing regularity
compute transformation priors from input-output delta
return bounded feature vector
```

AnchorWorks pre-answer frame resonance dimensions should be similar in spirit:

```text
D0: content_anchor_ratio
D1: structural_anchor_ratio
D2: punctuation_anchor_ratio
D3: unresolved_anchor_ratio
D4: dominant_role_strength
D5: role_entropy
D6: relation_count
D7: glue_dominance
D8: question_director_strength
D9: statement_strength
D10: command_strength
D11: repetition_strength
D12: source_lane_alignment
D13: evidence_request_strength
D14: listener_target_strength
D15: subject_quality_relation_strength
D16: context_delta_strength
D17: lane_conflict_score
D18: memory_write_risk
D19: answer_required_strength
```

These dimensions should be versioned:

```text
anchorworks_symbolic_resonance@1
anchorworks_code_resonance@1
anchorworks_chat_resonance@1
```

### ARC Multi-Example Fusion Algorithm

ARC does not treat examples independently. It fuses them to find invariants.

Raw algorithm:

```python
def fuse_examples(examples):
    resonances = []
    size_ratios = []

    for pair in examples:
        channels = compute_arc_channels_v2(pair.input_grid, pair.output_grid)
        resonance = ARCResonanceState.from_channels(channels, pair.input_grid, pair.output_grid)
        resonances.append(resonance)
        size_ratios.append(output_size / input_size)

    means = mean(each_dimension across resonances)
    variances = var(each_dimension across resonances)

    spatial_consistency = pairwise_correlation(spatial_feature_subset)
    color_consistency = pairwise_correlation(color_feature_subset)
    size_change_ratio = mean(size_ratios)

    return FusedResonanceState(means, variances, consistencies, size_change_ratio)
```

AnchorWorks translation:

```text
Collect accepted examples of a conversational/route/frame shape.
Convert each to symbolic resonance.
Compute mean role pattern.
Compute variance of role pattern.
Compute stable relations.
Compute unstable/noisy roles.
Only promote candidate shape if variance is low and gates pass.
```

Example:

```text
Surface examples:
- What a wonderful day, would you not agree?
- What a mess, do you not think?
- Fine weather today, wouldn't you say?

Potential fused shape:
- speaker asserts evaluated subject
- positive/negative valuation attaches to subject
- listener is asked for agreement
- docs/maps not requested
- light conversational response eligible
```

### ARC Recognition Field Algorithm

The recognition field maps fused resonance into rule classes.

Raw algorithm:

```python
def recognize(fused):
    candidates = [
        detect_identity(fused),
        detect_flip_h(fused),
        detect_flip_v(fused),
        detect_rotate_90(fused),
        detect_rotate_180(fused),
        detect_color_recolor(fused),
        detect_extract_largest(fused),
        detect_crop_to_bbox(fused),
        detect_grid_expand(fused),
    ]
    candidates.sort(key=lambda c: c.confidence, reverse=True)
    return candidates[0]
```

Each detector is threshold-based and returns:

```text
transform_class
confidence
rule_vector
reasoning
```

AnchorWorks translation:

```python
def recognize_symbolic_frame(fused):
    candidates = [
        detect_direct_question(fused),
        detect_rhetorical_agreement_request(fused),
        detect_declarative_note(fused),
        detect_document_fragment(fused),
        detect_command_request(fused),
        detect_help_lookup(fused),
        detect_citation_action(fused),
        detect_unknown_hold(fused),
    ]
    candidates = apply_lane_and_policy_gates(candidates)
    return highest_confidence_candidate(candidates)
```

Hard rule:

```text
Recognition classifies.
It does not answer.
It does not write memory.
It does not promote truth.
```

### ARC Rule Hypothesis Algorithm

ARC detectors create testable hypotheses.

Raw hypothesis shape:

```json
{
  "family": "TILING_EXPAND",
  "confidence": 0.91,
  "params": {
    "tile_factor_h": 3,
    "tile_factor_w": 3
  },
  "reasoning": "Perfect tiling detected across examples"
}
```

Raw detector pattern:

```text
read fused/task signature
check family-specific signals
extract candidate params
verify against all training examples
return RuleHypothesis or None
```

AnchorWorks frame hypothesis shape:

```json
{
  "family": "conversation_agreement_request",
  "confidence": 0.91,
  "params": {
    "subject_role": "evaluated_subject",
    "valuation_role": "positive_or_negative_quality",
    "target_role": "listener",
    "response_required": true,
    "evidence_allowed": false
  },
  "reasoning": "subject quality relation plus listener agreement action"
}
```

### ARC Worker Prior Algorithm

The ARC prior selector ranks workers from historical solved tasks.

Raw feature database build:

```text
for each training task:
  extract features
  test all single operators
  record which operator solves it, if any
  save task_id, features, operator, train_count, grid_shapes
```

Raw prior rank algorithm:

```python
def rank_operators(task_features, operators, k=10):
    similarities = []

    for task_id, data in feature_db.items():
        if data.operator is None:
            continue
        sim = feature_similarity(task_features, data.features)
        similarities.append((task_id, sim, data.operator))

    top_k = sort_desc(similarities)[:k]
    op_counts = count(operator for each top_k)
    ranked = operators sorted by frequency in similar solved tasks
    return ranked + remaining_operators
```

Reference feature similarity:

```text
boolean exact match -> +1
numeric closeness ratio -> +min(a,b)/max(a,b)
missing feature -> +0
```

AnchorWorks prior selector:

```text
new input/frame/task
-> symbolic fingerprint
-> compare to accepted successful traces
-> rank eligible workers/routes
-> run only bounded candidate set
```

AnchorWorks worker prior score should use the existing reason-learning contract:

```text
worker_prior_score(worker, task) =
  success_similarity * 1.00
  + valid_prefix_similarity * 0.75
  + lane_fit * 0.75
  + required_slot_fit * 1.00
  - near_miss_penalty * 0.50
  - failure_repetition_penalty * 1.00
  - forbidden_context_penalty * 9999
```

### ARC Composition Algorithm

ARC composition tries short chains only.

Raw two-step shape:

```text
for op1 in ranked_ops:
  for op2 in ranked_ops:
    infer cfg1 from first example
    apply op1 to input
    infer cfg2 from intermediate to expected output
    apply op2
    validate final output for all training examples
    if valid, apply chain to test input
```

Raw three-step shape:

```text
limit ranked ops to top 10
for op1 in top_ops:
  for op2 in top_ops:
    for op3 in top_ops:
      skip repeated ops if not allowed
      infer cfg1, cfg2, cfg3
      reject if step1 or step2 already solves when searching true 3-step
      validate final output across all examples
      return first valid chain
```

AnchorWorks bounded chain proposal:

```text
max_chain_length_default = 3
max_candidate_workers_default = 12
max_candidate_chains_default = 64
max_attempts_per_task_default = 96
```

Possible AnchorWorks chains:

```text
route_classifier -> frame_classifier
frame_classifier -> evidence_lane_selector
frame_classifier -> count_candidate_ranker -> renderer
citation_action_classifier -> bridge_attachment_writer
help_intent_classifier -> help_lookup -> renderer
```

Hard rule:

```text
Composition may suggest a route or answer frame.
Composition may not bypass lane gates.
```

## COD Backend: Raw Algorithm Shapes

### COD Core Rail

COD rail:

```text
live frame signals
-> per-modality feature extraction
-> 6-1-6 fusion
-> match fingerprint accumulation
-> baseline comparison
-> channel scoring
-> verdict and explanation
```

It is not an answer engine.
It is a recognition engine.

AnchorWorks translation:

```text
runtime traces
-> route/evidence/context features
-> interaction fingerprint
-> baseline comparison
-> drift/health channel scores
-> answer health and trace explanation
```

### COD Screen Resonance Algorithm

COD visual processing moved away from YOLO and toward pure signal math.

Raw inputs:

```text
grid_t: current 10x10 normalized intensity grid
prev_grid: previous grid
ema_fast: fast exponential moving average
ema_slow: slow exponential moving average
```

Raw update algorithm:

```text
if first frame:
  initialize prev_grid, ema_fast, ema_slow
  return zero features

ema_fast = alpha_fast * grid_t + (1 - alpha_fast) * ema_fast
ema_slow = alpha_slow * grid_t + (1 - alpha_slow) * ema_slow

delta = abs(grid_t - prev_grid)
high_freq = abs(grid_t - ema_slow)
low_freq = abs(ema_fast - ema_slow)

compute 20 features
prev_grid = grid_t
```

Raw 20 visual features:

```text
Core energy:
1. vis_energy_total
2. vis_energy_mean
3. vis_energy_std
4. vis_motion_concentration_50
5. vis_static_ratio

Spatial structure:
6. vis_center_energy_ratio
7. vis_edge_energy_ratio
8. vis_horizontal_vs_vertical_ratio
9. vis_recoil_vertical_bias
10. vis_scope_tunnel_index

Temporal/frequency:
11. vis_highfreq_energy
12. vis_lowfreq_energy
13. vis_high_to_low_ratio
14. vis_smoothness_index
15. vis_stutter_score

Event focused:
16. vis_flash_intensity
17. vis_firefight_focus_ratio
18. vis_jitter_band_energy
19. vis_contrast_shift_score
20. vis_aim_lock_score
```

AnchorWorks analogue:

```text
For chat/input traces, compute per-turn resonance:
- anchor_count
- unresolved_count
- director_strength
- content_strength
- glue_ratio
- punctuation_ratio
- evidence_request_strength
- citation_action_strength
- mode_stability
- route_delta_from_prior
- context_reuse_strength
- answer_health_delta
- no_anchor_risk
- fallback_risk
- hallucination_risk
- memory_write_risk
- source_support_strength
- count_support_strength
- remix_drift
- user_intent_confidence
```

### COD 6-1-6 Fusion Algorithm

Raw modalities:

```text
screen_features: 100 dims
visual_resonance: 20 dims
gamepad_features: 54 dims
network_features: 8 dims
```

Raw fusion:

```python
fused_vector = concat(screen_features, visual_resonance, gamepad_features, network_features)

for each anchor frequency [6.0, 1.0, 6.0]:
    phase += 2 * pi * frequency * dt
    phase %= 2 * pi
    amplitude = 0.9 * previous_amplitude + 0.1 * modality_energy

resonance_vector = [
    sin(phase0), cos(phase0),
    sin(phase1), cos(phase1),
    sin(phase2), cos(phase2),
    amplitude0, amplitude1, amplitude2,
    cos(phase0 - phase1),
    cos(phase1 - phase2),
    cos(phase0 - phase2),
]

full_signature = concat(fused_vector, resonance_vector)
```

Raw manipulation score:

```text
if history length < 10:
  score = 0
else:
  z_scores = abs((current - mean(history)) / std(history))
  max_z = max(z_scores)
  coherence_loss = 1 - mean(abs(phase_coherence))
  network_anomaly = network_spike_feature

  score = tanh(
    0.3 * (max_z / 3.0)
    + 0.4 * coherence_loss
    + 0.3 * network_anomaly
  )
```

AnchorWorks equivalent:

```text
route_vector = route/mode/context features
symbol_vector = anchor/role/relation features
evidence_vector = docs/maps/counts/citation features
memory_vector = write-intent/branch/attachment features

fused_interaction_vector = concat(route_vector, symbol_vector, evidence_vector, memory_vector)

compute coherence between:
- user intent and selected route
- selected route and evidence lane
- evidence lane and citation payload
- assistant answer and allowed evidence box
- chat context and memory write intent
```

### COD Match Fingerprint Algorithm

COD compresses many frames into one match fingerprint.

Raw layout v2 audio:

```text
0-127: visual summary
128-223: gamepad summary
224-255: network summary
256-335: cross-modal correlations
336-364: meta/anomaly flags
365-444: audio summary
445-524: audio cross-modal correlations
```

Raw stats per feature:

```text
mean
std
max
p90
```

Raw update algorithm:

```text
for each fused frame:
  flatten nested modality features
  update sum, sum_sq, min, max, values[] per feature
  update correlation accumulators for configured feature pairs
  update event counters
  update anomaly counters
  increment frame_count
```

Raw build algorithm:

```text
for each feature:
  mean = sum / n
  variance = max(0, sum_sq / n - mean^2)
  std = sqrt(variance)
  max = stored max
  p90 = percentile(values, 90)

for each correlation pair:
  r = pearson(x_values, y_values)
  x_when_y_high = mean(x where y >= p75(y))
  y_when_x_high = mean(y where x >= p75(x))
  frac_both_high = count(x high and y high) / n

assemble vector
attach metadata
```

AnchorWorks fingerprint builder proposal:

```text
InteractionFingerprintBuilder

Blocks:
0-63: input/symbol summary
64-127: route/mode summary
128-191: evidence summary
192-255: answer health summary
256-319: memory/bridge summary
320-383: cross-block correlations
384-415: meta/gate flags
```

Possible cross-block correlations:

```text
mode confidence vs evidence lane confidence
citation count vs document answer confidence
count-only route vs document read attempts
memory write intent vs approval state
remix drift vs answer health
no-anchor rate vs fallback attempts
```

### COD Recognition Field Algorithm

COD compares fingerprints against a baseline.

Raw baseline index:

```json
{
  "layout_version": "v1",
  "count": 42,
  "mean": [365 floats],
  "std": [365 floats]
}
```

Raw z-score algorithm:

```python
z[i] = (vector[i] - baseline.mean[i]) / (baseline.std[i] + eps)
```

Raw block scores:

```python
block_z = sqrt(mean(z[start:end] ** 2))
```

Raw COD blocks:

```text
visual_block_z: 0-127
gamepad_block_z: 128-223
network_block_z: 224-255
crossmodal_block_z: 256-335
meta_block_z: 336-364
```

Raw global anomaly:

```text
global_z = sqrt(
  0.25 * visual_z^2
  + 0.20 * gamepad_z^2
  + 0.20 * network_z^2
  + 0.25 * crossmodal_z^2
  + 0.10 * meta_z^2
)
```

Raw channel score:

```python
channel_z = abs(z_scores[key_dims])
rms_z = sqrt(mean(channel_z ** 2))
score = 1 / (1 + exp(-1.5 * (rms_z - 1.5)))
contributing_dims = top_3_abs_z_dims
```

Raw severity levels:

```text
none: score < 0.2
low: 0.2 <= score < 0.4
medium: 0.4 <= score < 0.6
high: 0.6 <= score < 0.8
critical: score >= 0.8
```

Raw verdict logic:

```text
normal:
  global_z < 1.5 and no high channels
  confidence 0.90

suspicious:
  global_z < 2.5 and at most one high channel
  confidence 0.60

manipulated_certain:
  any critical channel or global_z >= 3.5
  confidence 0.95

manipulated_likely:
  otherwise significant deviation
  confidence 0.75
```

AnchorWorks recognition field proposal:

```text
AnswerHealthRecognitionField

Inputs:
- interaction fingerprint
- baseline index for normal route behavior
- current policy/gate context

Outputs:
- answer health
- route drift score
- evidence integrity score
- citation integrity score
- memory write risk score
- fallback suspicion score
- explanation
```

Possible AnchorWorks verdicts:

```text
normal
weak_support
route_drift
citation_risk
memory_write_risk
unsupported_answer
hold_for_operator
```

Possible AnchorWorks channel scores:

```text
route_integrity
symbol_frame_fit
evidence_lane_fit
citation_integrity
count_coordinate_integrity
memory_write_integrity
context_drift
renderer_risk
```

### COD Recognition Report Shape

Raw report includes:

```text
match_id
profile
duration_seconds
frame_count
global_anomaly_score
block z-scores
channel scores
verdict
confidence
explanation
analysis_timestamp
baseline_count
```

AnchorWorks report shape:

```json
{
  "report_type": "anchorworks_answer_health@1",
  "message_id": "msg_...",
  "branch": "main",
  "route": "chat.main",
  "mode": "query|statement|command|document_fragment|answer_paste|unknown",
  "evidence_lane": "documents|counts|mixed|none|help|tool",
  "global_health_score": 0.0,
  "channels": {
    "route_integrity": {"score": 0.0, "level": "normal", "dimensions": []},
    "evidence_integrity": {"score": 0.0, "level": "normal", "dimensions": []},
    "citation_integrity": {"score": 0.0, "level": "normal", "dimensions": []},
    "memory_write_integrity": {"score": 0.0, "level": "normal", "dimensions": []},
    "context_drift": {"score": 0.0, "level": "normal", "dimensions": []}
  },
  "verdict": "normal|weak_support|route_drift|citation_risk|unsupported_answer|hold_for_operator",
  "confidence": 0.0,
  "explanation": [],
  "baseline_count": 0
}
```

## Sidecar Integration With Agentic Systems

Future agentic systems may call ARC/COD sidecars, but they must not get write authority.

Agent-safe call chain:

```text
agent proposes sidecar call
AnchorWorks validates sidecar route
AnchorWorks builds bounded input packet
sidecar computes report
AnchorWorks stores report as trace/attachment if allowed
AnchorWorks decides next action
```

Forbidden agent behavior:

```text
agent calls sidecar directly with filesystem paths
agent passes private documents without lane approval
agent lets sidecar write maps/counts/memory
agent uses sidecar verdict as truth without gate
agent imports old code into production route
```

Required agent sidecar request:

```json
{
  "requested_by": "agent_id",
  "request_type": "arc_shape_probe|cod_health_probe",
  "target_id": "trace_or_message_id",
  "input_scope": "bounded_trace|fixture|approved_system_doc",
  "write_intent": "none",
  "reason": "rank candidate route shapes",
  "max_runtime_ms": 2000,
  "max_output_bytes": 65536
}
```

## ARC Sidecar API Draft

### Operation: `arc.shape_probe`

Purpose:

```text
Given examples of symbolic frames or worker traces, return candidate shape families.
```

Input:

```json
{
  "schema_version": "arc_shape_probe@1",
  "examples": [
    {
      "input_symbols": [],
      "expected_frame": {},
      "trace": {}
    }
  ],
  "allowed_shape_families": [],
  "limits": {
    "max_candidates": 8,
    "max_chain_length": 3,
    "require_all_examples": true
  }
}
```

Output:

```json
{
  "shape_candidates": [
    {
      "family": "conversation_agreement_request",
      "confidence": 0.91,
      "params": {},
      "validated_examples": 3,
      "failed_examples": 0,
      "reasoning": "...",
      "eligible_for_promotion_candidate": false
    }
  ],
  "near_misses": [],
  "trace": []
}
```

### Operation: `arc.worker_prior`

Purpose:

```text
Rank eligible workers/routes from a task fingerprint.
```

Output:

```json
{
  "ranked_workers": [
    {
      "worker_id": "frame_classifier.conversation_agreement_request",
      "score": 1.92,
      "eligible": true,
      "reason": "matched prior successful frame traces"
    }
  ],
  "blocked_workers": [
    {
      "worker_id": "documents_search",
      "eligible": false,
      "reason": "frame does not request evidence"
    }
  ]
}
```

### Operation: `arc.chain_probe`

Purpose:

```text
Try bounded worker chains against fixtures/traces.
```

Output:

```json
{
  "valid_chains": [],
  "invalid_chains": [],
  "near_misses": [],
  "limits_hit": false
}
```

## COD Sidecar API Draft

### Operation: `cod.baseline_build`

Purpose:

```text
Build baseline over approved AnchorWorks trace fingerprints.
```

Input:

```json
{
  "schema_version": "cod_baseline_build@1",
  "fingerprints": [],
  "layout_version": "anchorworks_interaction_fingerprint@1",
  "baseline_label": "normal_chat_route_main"
}
```

Output:

```json
{
  "baseline_id": "baseline_...",
  "layout_version": "anchorworks_interaction_fingerprint@1",
  "count": 0,
  "mean": [],
  "std": [],
  "std_floor": 0.000001
}
```

### Operation: `cod.health_analyze`

Purpose:

```text
Compare one interaction fingerprint against a baseline and return channel verdicts.
```

Input:

```json
{
  "schema_version": "cod_health_analyze@1",
  "fingerprint": [],
  "baseline_id": "baseline_...",
  "channel_config": {}
}
```

Output:

```json
{
  "global_score": 0.0,
  "block_scores": {},
  "channels": {},
  "verdict": "normal|weak_support|route_drift|citation_risk|unsupported_answer|hold_for_operator",
  "confidence": 0.0,
  "explanation": [],
  "top_contributing_dimensions": []
}
```

## How ARC And COD Work Together

ARC answers:

```text
What shape is this?
Which worker/chain is worth trying?
Did the hypothesis validate?
```

COD answers:

```text
Is this behavior normal?
Which channel is drifting?
What dimensions caused the drift?
```

Combined future flow:

```text
1. AnchorWorks receives input.
2. Route classifier emits initial route.
3. ARC sidecar may propose shape/worker candidates for difficult cases.
4. AnchorWorks runs allowed deterministic workers.
5. COD sidecar may score resulting trace health.
6. AnchorWorks chooses speak/hold/retry/escalate.
7. Any promotion requires operator approval.
```

This gives AnchorWorks both:

```text
shape learning
runtime health recognition
```

without making either sidecar the owner of truth.

## Relationship To Tiny/System-Language Model

The future translator/speaker model may use sidecar reports as input context.

Allowed:

```text
model receives sidecar report
model explains report in plain language
model phrases supported answer health explanation
model translates trace into user-readable output
```

Forbidden:

```text
model trains on ARC datasets
model trains on COD telemetry
model memorizes sidecar outputs as truth
model overrides sidecar gates
model converts sidecar confidence into factual evidence
```

Tiny law:

```text
Sidecars calculate.
AnchorWorks gates.
Translator speaks.
```

## Relationship To Chat Memory

Sidecar reports may be attached as provenance to chat messages or trace events.

Allowed attachment type:

```json
{
  "target_type": "chat_message|trace_event|help_item|source_block",
  "target_id": "...",
  "attachment_type": "sidecar_report",
  "payload": {},
  "source": "arc_shape|cod_recognition",
  "created_by": "system",
  "write_intent": "l2_point_only",
  "evidence_lane": "sidecar_computation",
  "provenance": {}
}
```

Not allowed:

```text
sidecar report becomes source truth
sidecar report becomes lifetime count update
sidecar report promotes lexicon anchors
sidecar report becomes document evidence
sidecar report silently writes chat memory without route/write intent
```

## Immediate Use In AnchorWorks

Not now:

```text
do not implement sidecars during base chat route cleanup
do not import ARC/COD code
do not start agentic sidecar calls
do not train models on these systems yet
```

Later, after base route is stable:

```text
1. Create fixture-sized symbolic frame examples.
2. Build InteractionFingerprintBuilder.
3. Build AnswerHealthRecognitionField using COD math.
4. Build ShapeHypothesisProbe using ARC math.
5. Add sidecar report attachments through bridge.
6. Add agent-safe sidecar call contract.
7. Promote only after tests and live UI proof.
```

## Files Worth Studying Later

ARC files:

```text
G:\arc_production_solver\CONSTITUTION.md
G:\arc_production_solver\ALGORITHM_DOCUMENTATION.md
G:\arc_production_solver\arc_core.py
G:\arc_production_solver\solvers\baseline_solver.py
G:\arc_production_solver\solvers\composition_solver.py
G:\arc_production_solver\solvers\production_solver.py
G:\arc_production_solver\arc_organ\arc_grid_parser.py
G:\arc_production_solver\arc_organ\arc_resonance_state_v2.py
G:\arc_production_solver\arc_organ\arc_example_fuser.py
G:\arc_production_solver\arc_organ\arc_recognition_field.py
G:\arc_production_solver\arc_organ\arc_rule_hypothesis.py
G:\arc_production_solver\arc_organ\arc_rule_applicator.py
G:\arc_production_solver\arc_organ\mixer.py
G:\arc_production_solver\arc_organ\prior_selector.py
G:\arc_production_solver\engines\object_geometry.py
G:\arc_production_solver\training_feature_database.json
```

COD files:

```text
G:\arc_production_solver\cod_616\README.md
G:\arc_production_solver\cod_616\COMPUCOG_VISION_SPEC.md
G:\arc_production_solver\cod_616\screen_resonance_state.py
G:\arc_production_solver\cod_616\modules\fusion_616_engine.py
G:\arc_production_solver\cod_616\match_fingerprint_builder.py
G:\arc_production_solver\cod_616\recognition\recognition_field.py
G:\arc_production_solver\cod_616\recognition\RECOGNITION_FIELD_MANIFEST.md
G:\arc_production_solver\cod_616\PHASE_7_COMPLETE.md
G:\arc_production_solver\cod_616\modules\audio_resonance_state.py
```

## Final Rails

```text
ARC shape says: learn candidate patterns from examples, validate before use.
COD shape says: build baselines, score drift, explain contributing dimensions.
AnchorWorks says: sidecars may advise, never rule.
```

Operational lock:

```text
No import before contract.
No sidecar before base route.
No agent calls before bounded packet schema.
No promotion without gauntlet.
No truth without evidence lane.
```
