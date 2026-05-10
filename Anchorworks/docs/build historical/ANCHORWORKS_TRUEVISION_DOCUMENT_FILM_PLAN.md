# AnchorWorks TrueVision Document Film Plan

Last updated: 2026-05-08

## Purpose

This document corrects the TrueVision rail for AnchorWorks.

TrueVision is not a logger. TrueVision is the visual perception/intake shape that lets AnchorWorks preserve, sequence, inspect, and later reason over visual source material without losing source geometry or writing unsafe truth.

The immediate idea is a document film:

```text
document source
-> ordered visual frames
-> native geometry records
-> source-local visual layers
-> garbage-capture filter
-> future approval gate
```

The goal is not to train a vision model first. The goal is to make AnchorWorks see the shape of a document as a reproducible visual sequence.

## Source Evidence

Reference repo inspected:

```text
https://github.com/Kaladn/CompuCog
commit 1cce6b3 Add ClearboxPluginRunner to CompuCog repo
```

Useful source shapes:

```text
CompuCog/core/frame_to_grid.py
```

- Lines 23-32 define the visual sensor purpose: convert raw frames into ARC-style grids for symbolic reasoning.
- Lines 65-117 define `FrameCapture`, including primary-monitor capture and source/region metadata.
- Lines 120-187 define `FrameToGrid`, including frame-to-grid conversion and quantization.

```text
CompuCog/gaming/gaming_sensor.py
```

- Lines 4-5 define the core loop: PERCEIVE -> REPRESENT -> SELECT -> APPLY -> EVALUATE -> UPDATE.
- Lines 97-152 define `_build_fingerprint`, converting a frame sequence into feature scores and detections.
- Lines 188-220 show the runtime path: capture frame, convert to representation, buffer frames, build fingerprint.

```text
CompuCog/operators/base_operator.py
```

- Lines 23-98 describe the video operator layer: small focused temporal/structural detectors over frame sequences.
- Lines 105-120 define `FrameSequence` and `VideoOpResult` as clean reusable shapes.

```text
CompuCog/gaming/truevision_schema.py
```

- Lines 73-134 define the operator/window record shape used by active TrueVision telemetry.
- This is useful as a schema precedent, not as the center of AnchorWorks TrueVision.

What not to carry forward:

- The 32x32 grid as the authoritative visual representation.
- Pillow as required intake plumbing.
- YOLO as the default center of gravity.
- Logging-gateway language as the TrueVision purpose.
- ClearboxPluginRunner implementation baggage.

## Correct Translation

CompuCog gaming shape:

```text
screen capture
-> frame grid
-> frame sequence
-> operators
-> fingerprint
-> recognition/baseline
```

AnchorWorks document shape:

```text
document page / figure / image
-> native frame packet
-> document film sequence
-> visual layers
-> document visual fingerprint
-> garbage-capture filter
```

The old CompuCog 32x32 grid was a symbolic sketch. AnchorWorks must not distort the source to fit that old sketch.

New law:

```text
Native geometry is authority.
Any grid is derived.
Any model resize is derived.
Any OCR/object label is derived.
Any count/map write requires approval.
```

## Document Film

A document film is an ordered source-local sequence of visual frames from a document or corpus source.

Frame sources:

- full page render
- figure image
- diagram image
- table image
- equation image
- screenshot
- chart
- cover/section visual
- future video frame

Each frame is still source-local evidence. It is not a map. It is not a count. It is not lifetime memory.

Minimum frame packet:

```json
{
  "schema_version": "anchorworks_document_film_frame@1",
  "film_id": "film_...",
  "frame_id": "frame_...",
  "frame_index": 0,
  "frame_role": "figure",
  "source_id": "...",
  "source_path": "...",
  "source_hash": "...",
  "visual_record_id": "visual_...",
  "native_width": 1200,
  "native_height": 800,
  "aspect_ratio": "3:2",
  "media_type": "image",
  "file_format": "PNG",
  "caption_text": "",
  "nearby_text": "",
  "page_label": "",
  "section_label": "",
  "coordinate_space": "native_pixels",
  "layers": [],
  "status": "preview_only",
  "writes_allowed": {
    "maps": false,
    "counts": false,
    "lifetime": false,
    "lexicon": false
  }
}
```

Minimum film packet:

```json
{
  "schema_version": "anchorworks_document_film@1",
  "film_id": "film_...",
  "source_id": "...",
  "source_name": "...",
  "frame_count": 0,
  "frames": [],
  "authority": "source_local_visual_evidence",
  "approval_status": "preview_only",
  "garbage_filter_status": "not_run"
}
```

## Why Film Helps Garbage Captures

Garbage captures happen when source visuals are missing, distorted, duplicated, out of order, low-information, or detached from nearby text.

A document film gives AnchorWorks an expected visual sequence before deeper intake.

The filter can catch:

- missing image file
- unreadable image geometry
- duplicate source hash
- unexpected aspect ratio
- zero-byte or tiny junk image
- repeated decorative asset
- SVG or unsupported format that needs special handling
- figure without nearby caption
- caption without visual source
- visual referenced by text but absent on disk
- visual source present but out of document order
- rasterized text image that needs OCR later

This is why the film matters: it gives the system a stable visual timeline of the document before it tries to know the document.

## AnchorWorks Visual Levels

```text
L0 Visual source identity
L1 Native geometry
L2 Document film sequence
L3 Region/box layers
L4 Text/object/scene layers
L5 Visual fingerprint/resonance
L6 Approved visual evidence promotion
```

Current implementation is at L0/L1 with preview-only UI and map/count blocking.

The next correct step is L2: document film sequence.

## Adapted CompuCog Loop

CompuCog loop:

```text
PERCEIVE -> REPRESENT -> SELECT -> APPLY -> EVALUATE -> UPDATE
```

AnchorWorks visual intake loop:

```text
PERCEIVE
  read source-local document/figure inventory

REPRESENT
  create immutable native visual records

SELECT
  group records into ordered document film frames

APPLY
  run deterministic garbage filters and later optional visual backends

EVALUATE
  score readiness, missing geometry, duplicate visuals, caption fit, layer quality

UPDATE
  write preview manifests only
  do not write maps/counts/lifetime/lexicon
```

## Backend Role

Specialized TrueVision backends are allowed, but only as derived-layer producers.

Allowed backend outputs:

- OCR candidate layer
- region layer
- object/shape candidate layer
- caption-nearby-text layer
- visual fingerprint layer
- garbage-filter diagnostic layer

Forbidden backend outputs:

- direct map write
- direct count write
- direct lexicon promotion
- direct lifetime write
- hidden model-driven truth
- source geometry replacement

Tiny backend law:

```text
Backends observe.
AnchorWorks records provenance.
Promotion decides truth.
```

## Immediate Build Rail

1. Keep current AnchorForge image header probe.
2. Keep current preview-only visual manifest gate.
3. Add a pure `DocumentFilm` schema module.
4. Add a builder that groups existing visual manifests into ordered film frames.
5. Add a garbage-filter report over film frames.
6. Add UI display for film readiness, not model execution.
7. Do not run OCR/YOLO/scene inference yet.
8. Do not write maps/counts/lifetime/lexicon.

## Tiny Law

```text
TrueVision sees.
DocumentFilm sequences.
AnchorForge measures.
Backends derive.
Garbage filters hold.
Promotion changes the machine.
```
