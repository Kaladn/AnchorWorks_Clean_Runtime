# AnchorWorks Visual Region Map Contract

Last updated: 2026-05-08

## Purpose

Visual Region Map is the bridge between:

```text
source visual exists
```

and:

```text
recognition happened
```

AnchorForge gives the visual canvas. A Visual Region Map draws candidate geography on that canvas. Recognition layers label those regions. Promotion decides whether anything becomes durable knowledge.

Core law:

```text
Canvas first.
Regions second.
Recognition third.
Promotion last.
```

## Boundary

Visual Region Map is not object recognition.

Visual Region Map is not OCR.

Visual Region Map is not a graph database.

Visual Region Map is not a map/count/lifetime write.

It is a source-local coordinate packet that says:

```text
this part of this visual source may matter
```

## Required Record Shape

```json
{
  "schema_version": "anchorworks_visual_region_map@1",
  "visual_record_id": "visual_596a28bab4021571",
  "region_map_id": "vrmap_...",
  "source_hash": "...",
  "source_name": "figure.png",
  "media_type": "image",
  "coordinate_space": "native_pixels",
  "native_geometry": {
    "width": 1200,
    "height": 800,
    "aspect_ratio": "3:2",
    "frame_index": 0,
    "frame_timestamp_ms": null
  },
  "producer": {
    "backend_id": "anchorforge_region_probe",
    "backend_version": "contract_only",
    "operation_id": "...",
    "created_at": "2026-05-08T00:00:00Z"
  },
  "regions": [
    {
      "region_id": "r1",
      "shape": "box",
      "bounds": {
        "x": 0,
        "y": 0,
        "w": 100,
        "h": 40
      },
      "polygon": [],
      "kind_candidate": "text_block",
      "confidence": 0.82,
      "backend_id": "anchorforge_region_probe",
      "approval_status": "candidate",
      "source_local": true,
      "notes": []
    }
  ],
  "relations": [],
  "approval_status": "preview_only",
  "authority": "source_local_visual_evidence",
  "writes_allowed": {
    "maps": false,
    "counts": false,
    "lifetime": false,
    "lexicon": false
  },
  "trace": {
    "source": "visual_intake_preview",
    "write_intent": "l2_region_map_preview_only",
    "promotion_required": true
  }
}
```

## Required Fields

Each region map must include:

- `schema_version`
- `visual_record_id`
- `region_map_id`
- `source_hash`
- `coordinate_space`
- `native_geometry`
- `producer`
- `regions`
- `approval_status`
- `authority`
- `writes_allowed`
- `trace`

Each region must include:

- `region_id`
- `shape`
- `bounds` or `polygon`
- `kind_candidate`
- `confidence`
- `backend_id`
- `approval_status`

## Coordinate Space

Default coordinate space:

```text
native_pixels
```

Allowed future coordinate spaces:

- `native_pixels`
- `grid_cells`
- `video_frame_native_pixels`
- `document_page_coordinates`
- `derived_model_input`

Rules:

- `native_pixels` means coordinates are measured against the original source image dimensions.
- `grid_cells` is allowed for TrueVision/Forge window records because their canvas is already a grid.
- `derived_model_input` may be used only when the record also includes a pointer back to native geometry.
- A resized model input must never replace native geometry authority.

## Region Shapes

Allowed first shapes:

- `box`
- `polygon`
- `line`
- `point`
- `mask_ref`
- `full_canvas`

Shape rules:

- `box` uses `bounds`.
- `polygon` uses `polygon`.
- `line` uses `points`.
- `point` uses `x` and `y`.
- `mask_ref` points to a source-local mask artifact, if one exists later.
- `full_canvas` is valid as a first preview region when no segmentation has been run.

## Kind Candidates

Allowed first `kind_candidate` values:

- `unknown_region`
- `full_canvas`
- `text_block`
- `figure_body`
- `caption_block`
- `diagram_region`
- `chart_region`
- `table_region`
- `axis_region`
- `legend_region`
- `equation_region`
- `object_candidate`
- `ui_region`
- `background`
- `noise_or_junk`

Rules:

- `kind_candidate` is not semantic truth.
- `kind_candidate` may guide review and recognition only.
- A recognition layer may cite a region id but must keep its own confidence/provenance.

## Visual Relation Placeholder

Region maps may include relation candidates, but these remain preview-only.

Example:

```json
{
  "relation_id": "vrel_0001",
  "subject_region_id": "r_label",
  "predicate": "points_to",
  "object_region_id": "r_object",
  "evidence_region_ids": ["r_arrow"],
  "confidence": 0.7,
  "approval_status": "candidate"
}
```

Allowed first predicates:

- `points_to`
- `contains`
- `overlaps`
- `adjacent_to`
- `labels`
- `caption_describes`
- `row_contains`
- `column_contains`
- `axis_of`
- `legend_describes`
- `moved_to_next_frame`

## TrueVision / Forge Window Fit

For CompuCog/TrueVision Forge windows, the canvas is not native pixels. It is grid coordinate space.

Fit:

```text
TrueVision Forge window
-> visual source record
-> grid geometry
-> full-canvas region map in grid_cells
-> operator flag candidates / recognition layers later
```

TrueVision fields map as:

```text
grid_shape -> native_geometry equivalent for grid canvas
grid_color_count -> palette metadata
operator_flags -> later recognition candidates
operator_scores -> support weights, not truth
eomm_score -> attention/suspicion signal, not proof
session_id/window_id -> source-local scope
```

Hard law:

```text
TrueVision events enter AnchorWorks as observed state, not truth.
```

## Forbidden Side Effects

Visual Region Map creation must not:

- write global maps
- write global counts
- write lifetime
- write Canonical lexicon
- promote object labels
- promote OCR text
- call external models by default
- treat a detector flag as truth
- hide source geometry
- silently drop regions

## Approval Path

The region map can become useful knowledge only through later approval.

Approval may promote:

- selected OCR text to text intake
- selected diagram relations to source-local maps
- selected table structure to source-local maps
- selected visual labels to lexicon review
- selected visual facts to lifetime only after explicit promotion

Until then:

```text
region maps are candidate geography
```

## Tiny Law

```text
AnchorForge gives the canvas.
Region Map draws candidate geography.
Recognition labels candidates.
Promotion decides truth.
```
