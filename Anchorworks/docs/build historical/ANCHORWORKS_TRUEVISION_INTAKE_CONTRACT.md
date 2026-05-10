# AnchorWorks TrueVision Intake Contract

Last updated: 2026-05-08

## Purpose

AnchorWorks visual intake preserves images, figures, diagrams, screenshots, and future video frames as source-local visual evidence before any text, object, scene, map, count, or lifetime operation is allowed.

TrueVision is not one model and not a logging backbone. TrueVision is the visual intake bridge that hosts specialized visual backends and returns traceable derived layers.

The document-film direction is tracked separately in:

```text
docs/ANCHORWORKS_TRUEVISION_DOCUMENT_FILM_PLAN.md
```

Core law:

```text
Pixels are evidence.
Backends derive layers.
Layers stay source-local.
Promotion decides truth.
```

## Current Fit

The current AnchorWorks document preparation path already recognizes image files. As of this contract, image prep emits a preview-only visual manifest in metadata, a compact prepared-text notice, and a source-local visual intake packet on disk.

Active module:

```text
src/AnchorWorks/visual_manifest.py
```

Native visual probe:

```text
src/AnchorWorks/anchor_forge_visual.py
```

Active image prep hook:

```text
src/AnchorWorks/document_prep.py::_prepare_image
```

This hook records native image identity and geometry, then files empty region-map and recognition-layer containers beside the manifest. It does not run OCR, YOLO, scene reconstruction, map writes, count writes, lifetime writes, or lexicon writes.

Active source-local visual files:

```text
State/visual_intake/packets/*.visual_packet.json
State/visual_intake/manifests/*.manifest.json
State/visual_intake/region_maps/*.region_map.json
State/visual_intake/recognition_layers/*.recognition_layer.json
```

Inventory routes:

```text
GET /api/visual-intake/files
GET /api/visual-intake/packet/{name}
```

AnchorForge handles the current image metadata role directly. It reads image headers from bytes and does not depend on Pillow for intake geometry.

Visual image prep is enforced in two places:

- Document Intake UI detects `metadata.visual_manifest`, shows a Visual Evidence Preview card, and blocks normal anchor approval/map actions.
- Backend preview/map routes recognize visual preview content and refuse map/count execution until a future explicit visual approval path exists.

## Authority Split

```text
Canonical = meaning authority
Structural = form/position authority
Temp = unresolved source-local coordinate authority
Visual Intake = source-local visual evidence authority
Promotion = durable truth-changing gate
```

Visual intake may support later evidence review. It is not automatically a source of lifetime truth.

## Source Record

Every visual source must first become an immutable source record.

Minimum fields:

```json
{
  "visual_record_id": "visual_...",
  "source_name": "figure.png",
  "media_type": "image",
  "sha256": "...",
  "byte_size": 12345,
  "width": 1920,
  "height": 1080,
  "aspect_ratio": "16:9",
  "color_mode": "RGB",
  "file_format": "PNG",
  "frame_index": 0,
  "frame_timestamp_ms": null
}
```

Rules:

- Native geometry must be preserved.
- Aspect ratio must describe the original source, not a resized inference copy.
- Hash must identify the original source bytes.
- Still images use `frame_index = 0`.
- Video frames later use stable frame index and timestamp.
- Header probing is allowed for identity and geometry.
- Pixel decoding is not required for the preview-only source record.

## AnchorForge Visual Probe

AnchorForge is the local deterministic intake helper for source geometry.

Current role:

```text
image bytes
-> header probe
-> format / width / height / color mode
-> visual source record
```

Supported first-pass headers:

- PNG
- GIF
- JPEG
- BMP
- WEBP
- TIFF

Forbidden:

- no object detection
- no OCR
- no scene understanding
- no model loading
- no screen capture
- no map/count/lifetime/lexicon writes

AnchorForge law:

```text
AnchorForge measures the visual container.
TrueVision reads the scene later.
AnchorWorks gates the evidence.
```

## Backend Adapter Contract

Specialized visual backends must declare what they can read and what they can emit.

Minimum fields:

```json
{
  "backend_id": "compucog_vision_yolo_a",
  "backend_type": "object_detection",
  "provider": "local_compucog",
  "version": "phase_a",
  "inputs_supported": ["screen_capture", "image_frame"],
  "outputs_supported": ["detections", "scene_analysis", "auto_labels"],
  "coordinate_space": "native_pixels",
  "distorts_source": false,
  "may_resize_for_model": true,
  "resize_is_derived": true,
  "writes_allowed": {
    "maps": false,
    "counts": false,
    "lifetime": false,
    "lexicon": false
  }
}
```

Backend law:

```text
Backend output may describe.
Backend output may not promote.
Backend output may not write the brain.
Backend output must keep provenance to native pixels.
```

## CompuCogVision Backend Fit

The inspected CompuCogVision backend at:

```text
C:\Users\mydyi\OneDrive\Documents\Desktop\CompuCogVision
```

contains:

- `vision_logger.py`
- `curate_dataset.py`
- `config.json`
- `README.md`
- `requirements.txt`

Useful functions:

- `VisionLogger.capture_frame`
- `VisionLogger.detect_objects`
- `VisionLogger.analyze_scene`
- `VisionLogger.save_auto_labels`
- `VisionLogger.log_event`
- `DatasetCurator.review_dataset`
- `DatasetCurator.build_dataset`

Important correction:

CompuCogVision currently supports model-oriented resizing such as `640x480`. That is acceptable only as a derived backend layer. AnchorWorks visual intake must preserve native geometry first.

Clean fit:

```text
CompuCogVision detects.
AnchorWorks preserves.
TrueVision adapts.
Promotion decides.
```

## Visual Layers

Visual layers are derived records attached to a visual source.

Allowed layer types:

- `source_geometry`
- `ocr_text`
- `object_detection`
- `region`
- `caption`
- `nearby_text`
- `scene_summary`
- `state_change`
- `visual_resonance`
- `backend_diagnostic`

Layer item coordinates must use native pixel space unless the layer explicitly declares a derived coordinate space.

Example:

```json
{
  "layer_type": "object_detection",
  "backend_id": "compucog_vision_yolo_a",
  "coordinate_space": "native_pixels",
  "status": "preview_only",
  "items": [
    {
      "label": "person",
      "confidence": 0.87,
      "bbox": [320.5, 180.2, 450.8, 380.6]
    }
  ]
}
```

## Production Recognition Layer

AnchorWorks already intakes source-local media evidence:

- text
- photos
- static image records
- future video frame records

What is missing is the production recognition ladder that turns visual evidence into usable candidate knowledge without pretending it is already truth.

Recognition law:

```text
Recognition produces candidates.
Candidates need provenance.
Promotion decides truth.
```

### L0 Source Record

Purpose:

```text
identify the source without interpreting it
```

Contains:

- file name
- source path or source id
- media type
- byte size
- sha256 hash
- source-local authority

Allowed writes:

- preview manifest
- trace/provenance

Forbidden writes:

- maps
- counts
- lifetime
- lexicon

### L1 Native Geometry

Purpose:

```text
preserve the original visual canvas
```

Contains:

- native width
- native height
- aspect ratio
- file format
- color mode when available
- frame index for still/video
- timestamp for video frames when available

Rules:

- Native geometry is sovereign.
- Resize/crop/model input geometry is always derived.
- A derived view must point back to native pixel coordinates.

### L2 Visual Region Map

Purpose:

```text
divide the source canvas into addressable regions without semantic truth
```

The concrete Visual Region Map record contract lives in:

```text
docs/ANCHORWORKS_VISUAL_REGION_MAP_CONTRACT.md
```

Region map outputs may include:

- region id
- bounding box
- polygon
- mask reference
- source coordinate space
- region role candidate
- parent visual record id
- backend/probe provenance

Example:

```json
{
  "layer_type": "visual_region_map",
  "coordinate_space": "native_pixels",
  "items": [
    {
      "region_id": "region_0001",
      "bbox": [120, 80, 640, 420],
      "polygon": [],
      "role_candidate": "figure_body",
      "confidence": 0.0,
      "provenance": {
        "backend_id": "anchorforge_region_probe",
        "operation_id": "..."
      }
    }
  ]
}
```

Rules:

- A region is a coordinate handle, not truth.
- Region ids may be cited by later OCR/object/table/diagram layers.
- Region maps are source-local until approved.

### L3 Recognition Layers

Purpose:

```text
attach candidate readings to visual regions
```

The concrete Visual Recognition Layer record contract lives in:

```text
docs/ANCHORWORKS_VISUAL_RECOGNITION_LAYER_CONTRACT.md
```

Dual-path source-vs-vision verification is tracked in:

```text
docs/ANCHORWORKS_DUAL_PATH_VISUAL_VERIFICATION_CONTRACT.md
```

Recognition layers may include:

- OCR text candidates
- object candidates
- diagram candidates
- chart candidates
- table candidates
- equation-image candidates
- UI/screenshot candidates
- frame/state-change candidates for video

Every recognition item must include:

- source visual record id
- optional region id
- coordinate space
- backend id
- confidence or deterministic score
- candidate payload
- failure/warning fields when uncertain

Rules:

- OCR text is not Canonical lexicon truth.
- Object labels are not document truth.
- Diagram/chart/table labels are candidate structure only.
- Recognition outputs must never silently enter maps/counts/lifetime.

### L4 Visual Relation Graph

Purpose:

```text
describe relationships among regions and recognition candidates
```

Allowed relation candidates:

- label points to object
- arrow connects regions
- caption describes figure
- table cell relates to row/column
- axis label belongs to chart axis
- legend item describes color/shape
- object moved between video frames
- text block overlays image region
- callout line targets diagram part

Example:

```json
{
  "layer_type": "visual_relation_graph",
  "items": [
    {
      "relation_id": "vrel_0001",
      "subject_region_id": "region_label_01",
      "predicate": "labels",
      "object_region_id": "region_part_03",
      "confidence": 0.72,
      "evidence": ["arrow_line_02"],
      "status": "candidate"
    }
  ]
}
```

Rules:

- This is a visual relation graph, not Neo4j storage.
- Graph here means candidate visual relation structure.
- Future graph DB import must use an explicit export/approval path.

### L5 Scene / Symbolic Interpretation

Purpose:

```text
turn visual candidates into derived notes that a human/operator can inspect
```

Allowed outputs:

- scene summary candidates
- diagram interpretation candidates
- table structure candidates
- chart reading candidates
- screenshot/UI layout candidates
- video state-change summaries
- uncertainty notes

Forbidden:

- claiming visual interpretation as source truth without approval
- correcting source text silently
- inventing missing labels
- using model output as promotion authority

### L6 Approval Promotion

Purpose:

```text
allow selected visual evidence to become usable knowledge only through a gate
```

Promotion may later allow:

- selected OCR text into text intake
- selected visual facts into source-local maps
- selected approved structure into counts
- selected terms into lexicon review
- selected durable facts into lifetime lanes

Promotion requires:

- operator approval
- source visual record id
- region/citation payload when applicable
- lane decision
- write intent
- trace/provenance

Hard rule:

```text
Recognition can prepare.
Only approval can promote.
```

## Document Film Recognition Route

The document-film path is the production-ready route for visual document intake.

Shape:

```text
docs / images / video
-> canonical visual frames
-> optional replay or film sequence
-> TrueVision recognition backend
-> region map
-> recognition layers
-> visual relation graph
-> approval gate
```

Replay/film law:

```text
Replay helps recognition.
Replay is not source truth.
Native source geometry remains sovereign.
Recognition is candidate evidence until approved.
```

The film sequence may help clear garbage captures by comparing expected source-local visual order against derived capture/recognition output.

Potential garbage signals:

- missing expected frame
- duplicate frame hash
- unreadable geometry
- unsupported visual format
- caption/figure mismatch
- page order mismatch
- low-information decorative asset
- OCR candidate without region
- region without source visual record
- model-derived layer without native coordinate provenance

First backend stubs should be pure schema/validation only:

```text
src/AnchorWorks/visual_region_map.py
src/AnchorWorks/visual_recognition_layer.py
src/AnchorWorks/visual_replay_manifest.py
```

No YOLO, OpenCV, OCR, external LLM, or model execution is required for this contract layer.

## Video Future Path

Video is a future-compatible packet type, not the first implementation target.

Shape:

```text
recording
-> native frames
-> frame manifests
-> region tracks
-> state-change events
-> reproducible scene packet
```

State-change examples:

- object entered frame
- object left frame
- text appeared
- text disappeared
- object moved region
- scene changed
- caption/diagram step changed

Video outputs remain source-local until approval.

## OpenStax Handling

OpenStax raw data is currently held because many sources contain figures, images, diagrams, charts, and image-backed equations.

OpenStax visual intake must produce figure records before text ingestion proceeds.

Minimum OpenStax figure manifest fields:

```json
{
  "visual_record_id": "visual_...",
  "source_book": "osbooks-physics",
  "source_file": "path/to/figure.png",
  "source_hash": "...",
  "media_type": "image",
  "width": 1200,
  "height": 800,
  "aspect_ratio": "3:2",
  "caption_text": "",
  "nearby_text": "",
  "containing_document": "",
  "ocr_layer": [],
  "object_layer": [],
  "region_layer": [],
  "derived_notes": [],
  "authority": "source_local_visual_evidence",
  "approval_status": "preview_only",
  "writes_allowed": {
    "maps": false,
    "counts": false,
    "lifetime": false,
    "lexicon": false
  }
}
```

No image may silently disappear from a source-local intake record.

## UI Changes Needed

### Document Intake

Add a visual preview block when the selected file is an image or when a prepared document references images.

Required display:

- visual record id
- source hash
- native width and height
- aspect ratio
- file format and mode
- authority badge: `source-local visual evidence`
- approval status: `preview only`
- writes blocked: maps/counts/lifetime/lexicon

### Visual Intake Tab

Add a later tab after the contract is stable.

First version should include:

- image/video inventory list
- backend capability list
- visual manifest viewer
- source geometry panel
- derived layers panel
- approval gate panel
- export manifest button

Do not add model execution buttons yet.

### OpenStax Curated Data Review

Add a source-review card for curated data before ingest.

Required display:

- raw source root
- image count
- video count
- files with missing captions
- files with missing dimensions
- manifest status
- ingest hold reason

### Tracer

Tracer should capture:

- visual manifest preview load
- backend capability declaration
- approval status changes
- any blocked write attempt
- visual source skipped with reason

Tracer must not store pixel data.

### Chat / Help

Chat may cite visual evidence only when a visual record exists and a source-local visual layer supports the claim.

Help can explain visual intake from a passive help file. Help must not become a vision actor.

## Forbidden Side Effects

Visual intake preview must not:

- write maps
- write counts
- write lifetime
- write lexicon
- promote source-local visual notes into truth
- resize source pixels as the authoritative record
- silently drop images
- treat OCR as canonical text without review
- treat object labels as sourced document truth without approval

## Build Order

```text
1. Contract
2. Pure schema module
3. Image prep preview manifest
4. Tests
5. UI preview panel
6. Image inventory tool
7. Backend adapter wrapper
8. OCR/object/scene layers
9. Approval gate
10. Optional map/count promotion
```

Current implementation covers steps 1 through 6 and the backend map/count refusal gate.

## Tiny Law

```text
Native pixels stay sovereign.
Derived layers explain them.
Backends are adapters.
UI previews the evidence.
Promotion changes the machine.
```
