# TrueVision State Media POC TODO

## Purpose

This TODO preserves the next work after the first one-hour proof of concept.

Core truth:

```text
We did not solve video generation.
We proved that a replayable visual-state substrate is viable enough to continue.
The current language is incomplete.
Geometry is the next major unlock.
```

Current best boundary:

```text
Forward TrueVision witnesses.
Reverse TrueVision replays or demonstrates state.
Generated state media is synthetic, not evidence.
```

## Current State

Done:

```text
real 30s screen/video capture
90x160x16 cell-state recording
compressed NPZ cell chunks
JSONL temporal records
manifest/summary/replay reports
deterministic replay from stored cell state
synthetic scene formula using same state shape
first full-power single frame consuming non-RGB channels
SecureCore and AnchorWorks handoff bundles
```

Known weakness:

```text
The state exists, but the language is crude.
The replay renderer still does not know enough geometry.
The generated frames are conceptually valid but visually weak.
```

## Phase 0: Freeze And Verify

- [ ] Keep the current POC bundle unchanged as `v0`.
- [ ] Confirm both bundle copies remain identical:

```powershell
Get-ChildItem D:\SecureCore_Workspace\SecureCore\TRUEVISION_STATE_MEDIA_POC -Recurse -File |
  Measure-Object Length -Sum

Get-ChildItem D:\AnchorWorks_Clean_Runtime\TRUEVISION_STATE_MEDIA_POC -Recurse -File |
  Measure-Object Length -Sum
```

- [ ] Re-run focused COD tests from the source repo:

```powershell
cd D:\arc_solver_clean\cod_616
python -m unittest test_truevision_full_power_frame test_truevision_state_scene_generator test_truevision_state_replay test_truevision_resonance_recorder -v
```

- [ ] Do not make claims beyond the POC:

```text
Do not claim photoreal generation.
Do not claim original video reconstruction.
Do not claim raw-pixel forensic accuracy.
Do not claim synthetic media is evidence.
```

## Phase 1: Language Cleanup

- [ ] Rename the work around `state media`, not generic generation.
- [ ] Keep the forward/reverse distinction explicit:

```text
Forward TrueVision: observed visual state capture.
Reverse TrueVision: replay or demonstration from state.
Synthetic State Media: declared state formula rendered through the same substrate.
```

- [ ] Define the minimum vocabulary:

```text
cell
frame state
temporal state
state tensor
state chunk
replay fidelity
synthetic state media
observed state media
state sidecar
geometry sidecar
```

- [ ] Rewrite reports so the wording does not overstate the result.
- [ ] Keep the French-language analogy as an internal note:

```text
We found there is a visual language, but we are speaking it badly.
```

## Phase 2: Real Capture Study

- [ ] Profile multiple real captures, not just one music video.
- [ ] Capture at least these scenarios:

```text
person walking video
talking face video
camera pan
static desktop with window movement
high-motion music video
dark scene with flashes
```

- [ ] For each capture, record:

```text
frame_count
duration_seconds
fps
grid shape
feature distribution
motion distribution
edge distribution
texture distribution
compression ratio
disk usage
```

- [ ] Build a comparison report:

```text
real_capture_profile_vs_synthetic_profile.md
```

- [ ] Identify which channels matter most for replay quality.

## Phase 3: Replay Renderer v2

- [ ] Create `truevision_state_replay_v2.py`.
- [ ] Keep `truevision_state_replay.py` unchanged as the v1 baseline.
- [ ] Renderer v2 must consume:

```text
rgb_mean
rgb_std
luma_std
texture_energy
edge_density
motion_energy
delta_luma_abs
saturation_mean
```

- [ ] Add optional sidecar support:

```text
object_id_layer
foreground_coverage_layer
depth_hint_layer
motion_dx_layer
motion_dy_layer
edge_orientation_layer
material_class_layer
texture_seed_layer
skeleton_joint_state
camera_state
lighting_state
```

- [ ] Renderer v2 must report:

```text
channels used
channels ignored
sidecars used
input hashes
output hashes
synthetic/evidence boundary
hardware used
wall-clock time
```

- [ ] Acceptance criteria:

```text
same input state produces same output hash
no raw frames required
no audio unless explicitly requested
state frame visibly uses texture/edge/motion channels
report identifies replay as state replay, not original video
```

## Phase 4: Geometry Engine Integration

This is the big unlock.

- [ ] Define a geometry sidecar schema.
- [ ] Start with simple 2D/2.5D scene geometry:

```text
camera transform
horizon line
ground plane
object bounds
actor skeleton
limb segments
depth order
occlusion masks
contact shadows
```

- [ ] Later expand toward 3D:

```text
mesh proxy
surface normals
material ids
light direction
camera intrinsics
camera motion
parallax hints
volumetric hints
```

- [ ] Add a minimal walking-person geometry sidecar:

```json
{
  "actor_id": "person_001",
  "skeleton_2d": {
    "head": [0.54, 0.48],
    "neck": [0.54, 0.55],
    "hip": [0.54, 0.74],
    "left_foot": [0.50, 0.82],
    "right_foot": [0.58, 0.82]
  },
  "depth_order": ["field_far", "person", "field_near"],
  "contact_shadow": true
}
```

- [ ] Renderer v2 should use geometry to preserve object coherence.

## Phase 5: Scene Formula v2

- [ ] Create `truevision_scene_formula_v2.py`.
- [ ] Keep v1 scene generator as a compatibility proof.
- [ ] v2 should generate:

```text
cell_state_npz
records.jsonl
manifest.json
summary.json
geometry_sidecar.json
material_sidecar.json
motion_sidecar.json
formula_report.md
preview frame/video
lossless state replay
```

- [ ] The walking person scene should include:

```text
field wind phase
grass texture layers
sky gradient and cloud drift
actor skeleton
limb gait phase
contact shadow
foreground/background depth
material ids
motion vector field
```

- [ ] Acceptance criteria:

```text
not a flat drawing
object continuity is stable
person proportions are coherent
field has subcell texture
motion vectors agree with gait phase
state report explains which channels were used
```

## Phase 6: Capture Tier Policy

- [ ] Define recording tiers.

Tier 1: State Audit

```text
960x540
90x160 grid
16 features
9 fps
compressed NPZ
JSONL records
no raw frames
about 6.3 GiB/hour with replay artifacts
```

Tier 2: Rich State

```text
denser grid or more channels
sidecars enabled
expected tens of GiB/hour
```

Tier 3: Evidence Plus State

```text
state capture plus raw source preservation
case-controlled retention
explicit evidence policy
```

- [ ] Write retention defaults:

```text
normal windows: compact/delete chunks after short TTL
interesting windows: preserve chunks and replay reports
critical windows: preserve chunks, source if available, hash manifests, and case metadata
```

## Phase 7: SecureCore Integration

- [ ] Keep SecureCore as logger/guard/toolbox.
- [ ] Do not make TrueVision synthetic output evidence.
- [ ] Add Central Writer language:

```text
observed_state_media
synthetic_state_media
state_replay_artifact
state_formula_artifact
geometry_sidecar_artifact
```

- [ ] Add Policy Gate rules:

```text
raw screen/video capture requires explicit mode
evidence export requires approval
synthetic media must be labeled
generated media cannot fill evidence gaps
```

- [ ] Add Artifact Engine handling for:

```text
cell_state_npz
records_jsonl
state_replay_video
state_formula_report
geometry_sidecar
hash_manifest
```

## Phase 8: AnchorWorks Integration

- [ ] Keep AnchorWorks as the main shape/route/language system.
- [ ] Let AW consume TrueVision state as a structured stream, not raw media.
- [ ] AW should help map:

```text
counts
state transitions
shape continuity
scene grammar
route proposals
```

- [ ] SecureCore should clean, guard, log, and label the outputs.
- [ ] Neither system should silently own sole authority.

## Phase 9: Paper Trail

- [ ] Draft a short paper outline:

```text
Title
Abstract
Problem
Prior model: prompt video and raw video
Proposed model: temporal visual state substrate
Method
POC results
Disk/storage math
Limitations
Next work
Safety boundary
```

- [ ] Preserve the exact one-hour story:

```text
concept
bad procedural demo
real TrueVision record lookup
30s capture
state replay
synthetic state formula
failure analysis
full-power frame
handoff bundle
```

- [ ] Keep all claims sober.

## Immediate Next Session Order

```text
1. Re-read TRUEVISION_STATE_MEDIA_POC_HANDOFF.md.
2. Re-read DATA_USAGE_AND_RECORDING_MATH.md.
3. Re-read STATE_LANGUAGE_NEXT_STEPS.md.
4. Capture one real person-walking video sample.
5. Profile the real walking sample.
6. Compare it against synthetic walk v1.
7. Implement geometry sidecar schema.
8. Build replay renderer v2.
9. Only then generate a second 5s walking clip.
```

## Tiny Law

```text
Pixels show.
State remembers.
Geometry organizes.
Replay demonstrates.
Evidence remains observed.
Synthetic remains labeled.
```
