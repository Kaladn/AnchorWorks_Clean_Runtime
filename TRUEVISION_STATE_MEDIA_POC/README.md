# TrueVision State Media POC Bundle

This directory is a handoff bundle for the one-hour TrueVision state-media proof of concept.

The same bundle was duplicated into:

```text
D:\SecureCore_Workspace\SecureCore\TRUEVISION_STATE_MEDIA_POC
D:\AnchorWorks_Clean_Runtime\TRUEVISION_STATE_MEDIA_POC
```

Source work happened in:

```text
D:\arc_solver_clean\cod_616
```

## What This Proves

```text
Observed video can be converted into structured temporal cell state.
Stored cell state can be replayed deterministically.
Declared scene formulas can emit the same cell-state shape.
Replay quality depends on which state channels the renderer actually consumes.
```

## Core Boundary

```text
Forward TrueVision witnesses.
Reverse TrueVision replays or demonstrates state.
Generated state media is synthetic, not evidence.
Raw frames are not implied unless explicitly saved.
```

## Directory Layout

```text
ui/
  truevision_state_media_studio.html

instructions/
  LLM_TRUEVISION_STATE_MEDIA_INSTRUCTIONS.md
  ARC_SOLVER_LEARNING_SHAPE_FOR_TRUEVISION.md
  SECURECORE_AGENT_CHAIN_FOR_TRUEVISION.md

scripts/
  truevision_resonance_recorder.py
  truevision_state_replay.py
  truevision_state_scene_generator.py
  truevision_full_power_frame.py

modules/
  screen_grid_mapper.py

screen_resonance_state.py

tests/
  test_truevision_resonance_recorder.py
  test_truevision_state_replay.py
  test_truevision_state_scene_generator.py
  test_truevision_full_power_frame.py
  test_video_cell_state.py
  test_screen_grid_mapper_dimensions.py
  test_screen_resonance_rectangular.py

reports/
  person_field_walk_5s_state_media_formula_report.md
  person_field_clean_frame_full_power_report.md
  TRUEVISION_STATE_MEDIA_POC_HANDOFF.md
  DATA_USAGE_AND_RECORDING_MATH.md
  STATE_LANGUAGE_NEXT_STEPS.md
  FPS_OPTIMIZATION_SMOKE_REPORT.md

manifests/
  captured and generated run manifests, summaries, and replay reports

artifact_index/
  artifact_index.csv
  artifact_index.json
```

## Important Note

The large generated/captured artifacts were indexed by hash and path instead of blindly copying every binary into both repos. The source artifacts remain under:

```text
D:\arc_solver_clean\cod_616\data\truevision_full
D:\arc_solver_clean\cod_616\data\truevision_generated
```
